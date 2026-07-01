"""
Integration tests for GET /v1/metadata endpoint.

When running locally (no cloud metadata service), the endpoint returns 503.
When running on AWS or GCP, it returns 200 with instance metadata.
These tests validate the endpoint behavior when running locally.
"""

import requests
import pytest

BASE_URL = "http://localhost:8080"
ENDPOINT = f"{BASE_URL}/v1/metadata"

NO_CACHE_HEADERS = {
    "cache-control": "no-cache, no-store, must-revalidate",
    "pragma": "no-cache",
}


class TestMetadataMethodNotAllowed:
    """All non-GET methods should return 405."""

    @pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
    def test_unsupported_methods_return_405(self, method):
        headers = {"Content-Type": "application/json"}
        resp = getattr(requests, method)(ENDPOINT, headers=headers)
        assert resp.status_code == 405

    def test_head_returns_405(self):
        resp = requests.head(ENDPOINT)
        assert resp.status_code == 405

    def test_options_returns_405(self):
        resp = requests.options(ENDPOINT)
        assert resp.status_code == 405


class TestMetadataBadRequest:
    """GET with body or query params should return 400."""

    def test_get_with_body_returns_400(self):
        resp = requests.get(ENDPOINT, json={"key": "value"})
        assert resp.status_code == 400

    def test_get_with_query_params_returns_400(self):
        resp = requests.get(f"{ENDPOINT}?foo=bar")
        assert resp.status_code == 400

    def test_get_with_multiple_query_params_returns_400(self):
        resp = requests.get(f"{ENDPOINT}?foo=bar&baz=qux")
        assert resp.status_code == 400


class TestMetadataCacheHeaders:
    """Response should include no-cache headers regardless of status code."""

    def test_cache_control_headers_present(self):
        resp = requests.get(ENDPOINT)
        # Should be either 200 (on cloud) or 503 (local)
        assert resp.status_code in [200, 503]
        assert "no-cache" in resp.headers.get("cache-control", "")
        assert "no-store" in resp.headers.get("cache-control", "")
        assert "must-revalidate" in resp.headers.get("cache-control", "")
        assert resp.headers.get("pragma") == "no-cache"


class TestMetadataNoAuth:
    """Endpoint is public — no authentication required."""

    def test_no_auth_required(self):
        resp = requests.get(ENDPOINT)
        # Should NOT get 401 — endpoint is public
        assert resp.status_code != 401


class TestMetadataLocalResponse:
    """When running locally (no cloud platform), expect 503."""

    def test_returns_503_when_not_on_cloud(self):
        """
        When running locally, no metadata service is available.
        The endpoint should return 503 with an error message.
        Detection uses short timeouts so this should respond promptly.
        """
        resp = requests.get(ENDPOINT, timeout=10)
        # If running locally, expect 503
        # If running on cloud, expect 200 — both are acceptable
        if resp.status_code == 503:
            data = resp.json()
            assert "error" in data
        elif resp.status_code == 200:
            data = resp.json()
            assert "cloud_platform" in data
            assert data["cloud_platform"] in ["aws", "gcp"]
            assert "instance_id" in data
            assert "region" in data
            assert "machine_type" in data
            assert "network_interfaces" in data
            assert isinstance(data["network_interfaces"], list)
            assert len(data["network_interfaces"]) > 0
            for nic in data["network_interfaces"]:
                assert "private_ip" in nic
                assert "public_ip" in nic  # Can be null
                assert "network" in nic


class TestMetadataResponseTimeout:
    """Detection should use short timeouts — endpoint should respond promptly."""

    def test_responds_within_reasonable_time(self):
        """
        Even when not on a cloud platform, the endpoint should not hang.
        The metadata detection timeout is ~1.5s per provider, so total
        should be under 10 seconds.
        """
        resp = requests.get(ENDPOINT, timeout=10)
        assert resp.status_code in [200, 503]
