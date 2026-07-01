"""
Cloud platform auto-detection and instance metadata retrieval.

Detects AWS or GCP by probing metadata service endpoints with short timeouts.
Caches the detected platform for the lifetime of the process.
"""

import httpx
import logging

logger = logging.getLogger(__name__)

# Short timeout to avoid hanging when not on a cloud platform
METADATA_TIMEOUT = 1.5  # seconds

# Cached detection result
_detected_platform: str | None = None
_detection_done: bool = False


async def detect_cloud_platform() -> str | None:
    """
    Detect whether running on AWS or GCP by probing metadata endpoints.
    Result is cached after first call.
    Returns 'aws', 'gcp', or None.
    """
    global _detected_platform, _detection_done

    if _detection_done:
        return _detected_platform

    # Try GCP first (usually faster to respond)
    if await _probe_gcp():
        _detected_platform = "gcp"
        _detection_done = True
        logger.info("Detected cloud platform: GCP")
        return _detected_platform

    # Try AWS
    if await _probe_aws():
        _detected_platform = "aws"
        _detection_done = True
        logger.info("Detected cloud platform: AWS")
        return _detected_platform

    _detection_done = True
    logger.warning("No supported cloud platform detected")
    return None


async def _probe_gcp() -> bool:
    """Check if running on GCP by hitting metadata server."""
    try:
        async with httpx.AsyncClient(timeout=METADATA_TIMEOUT) as client:
            resp = await client.get(
                "http://metadata.google.internal/computeMetadata/v1/",
                headers={"Metadata-Flavor": "Google"},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def _probe_aws() -> bool:
    """Check if running on AWS by hitting IMDSv2 token endpoint, fall back to IMDSv1."""
    try:
        async with httpx.AsyncClient(timeout=METADATA_TIMEOUT) as client:
            # Try IMDSv2 first
            token_resp = await client.put(
                "http://169.254.169.254/latest/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            )
            if token_resp.status_code == 200:
                return True
            # Fall back to IMDSv1
            resp = await client.get("http://169.254.169.254/latest/meta-data/")
            return resp.status_code == 200
    except Exception:
        return False


async def get_metadata() -> dict:
    """
    Retrieve instance metadata from the detected cloud platform.
    Raises RuntimeError if platform not detected or metadata retrieval fails.
    """
    platform = await detect_cloud_platform()

    if platform is None:
        raise RuntimeError("No supported cloud platform detected")

    if platform == "gcp":
        return await _get_gcp_metadata()
    else:
        return await _get_aws_metadata()


async def _get_gcp_metadata() -> dict:
    """Retrieve and parse GCP instance metadata."""
    headers = {"Metadata-Flavor": "Google"}
    base = "http://metadata.google.internal/computeMetadata/v1/instance"

    try:
        async with httpx.AsyncClient(timeout=METADATA_TIMEOUT) as client:
            # Fetch basic instance info
            instance_id = (await client.get(f"{base}/id", headers=headers)).text
            zone_full = (await client.get(f"{base}/zone", headers=headers)).text
            machine_full = (await client.get(f"{base}/machine-type", headers=headers)).text

            # Parse short-form values: projects/123/zones/us-east1-b -> us-east1-b
            region = zone_full.split("/")[-1]
            machine_type = machine_full.split("/")[-1]

            # Fetch network interfaces
            nics_resp = await client.get(
                f"{base}/network-interfaces/?recursive=true",
                headers={**headers, "Accept": "application/json"},
            )
            nics_data = nics_resp.json()

            network_interfaces = []
            for nic in nics_data:
                private_ip = nic.get("ip")
                # Access configs contain external IPs
                access_configs = nic.get("accessConfigs", [])
                public_ip = None
                if access_configs:
                    public_ip = access_configs[0].get("externalIp") or None

                network_raw = nic.get("network", "")
                network = network_raw.split("/")[-1]

                network_interfaces.append({
                    "private_ip": private_ip,
                    "public_ip": public_ip,
                    "network": network,
                })

            return {
                "cloud_platform": "gcp",
                "instance_id": instance_id,
                "region": region,
                "machine_type": machine_type,
                "network_interfaces": network_interfaces,
            }
    except Exception as e:
        logger.error(f"Failed to retrieve GCP metadata: {e}")
        raise RuntimeError(f"Failed to retrieve GCP metadata: {e}")


async def _get_aws_metadata() -> dict:
    """Retrieve and parse AWS instance metadata."""
    base = "http://169.254.169.254/latest"

    try:
        async with httpx.AsyncClient(timeout=METADATA_TIMEOUT) as client:
            # Try to get IMDSv2 token
            token = None
            try:
                token_resp = await client.put(
                    f"{base}/api/token",
                    headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                )
                if token_resp.status_code == 200:
                    token = token_resp.text
            except Exception:
                pass  # Fall back to IMDSv1

            headers = {}
            if token:
                headers["X-aws-ec2-metadata-token"] = token

            # Fetch basic instance info
            instance_id = (await client.get(f"{base}/meta-data/instance-id", headers=headers)).text
            region = (await client.get(f"{base}/meta-data/placement/availability-zone", headers=headers)).text
            instance_type = (await client.get(f"{base}/meta-data/instance-type", headers=headers)).text

            # Fetch network interfaces via MAC addresses
            macs_resp = await client.get(f"{base}/meta-data/network/interfaces/macs/", headers=headers)
            macs = [m.strip("/") for m in macs_resp.text.strip().split("\n") if m.strip()]

            network_interfaces = []
            for mac in macs:
                mac_base = f"{base}/meta-data/network/interfaces/macs/{mac}"

                private_ip = (await client.get(f"{mac_base}/local-ipv4s", headers=headers)).text.split("\n")[0]

                public_ip = None
                try:
                    pub_resp = await client.get(f"{mac_base}/public-ipv4s", headers=headers)
                    if pub_resp.status_code == 200 and pub_resp.text.strip():
                        public_ip = pub_resp.text.split("\n")[0]
                except Exception:
                    pass

                vpc_id = (await client.get(f"{mac_base}/vpc-id", headers=headers)).text

                network_interfaces.append({
                    "private_ip": private_ip,
                    "public_ip": public_ip,
                    "network": vpc_id,
                })

            return {
                "cloud_platform": "aws",
                "instance_id": instance_id,
                "region": region,
                "machine_type": instance_type,
                "network_interfaces": network_interfaces,
            }
    except Exception as e:
        logger.error(f"Failed to retrieve AWS metadata: {e}")
        raise RuntimeError(f"Failed to retrieve AWS metadata: {e}")
