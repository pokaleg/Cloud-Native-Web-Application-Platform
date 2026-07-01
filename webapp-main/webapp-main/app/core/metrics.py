import statsd

# Module-level singleton — created once, reused across all requests
_statsd_client = None


def get_statsd() -> statsd.StatsClient:
    """
    Returns a StatsD client that sends UDP packets to localhost:8125.
    CloudWatch agent listens on :8125 and forwards metrics to CloudWatch
    under the namespace CSYE6225/WebApp.
    No connection errors are raised — StatsD uses UDP (fire and forget).
    """
    global _statsd_client
    if _statsd_client is None:
        _statsd_client = statsd.StatsClient(
            host="localhost",
            port=8125,
            prefix="csye6225"   # all metrics appear as csye6225.*
        )
    return _statsd_client


def record_api_call(endpoint: str) -> None:
    """Increment counter for an API call. Metric: csye6225.api.<endpoint>.count"""
    try:
        get_statsd().incr(f"api.{endpoint}.count")
    except Exception:
        pass  # Never let metrics failure affect the API response


def record_api_time(endpoint: str, elapsed_ms: float) -> None:
    """Record API total response time. Metric: csye6225.api.<endpoint>.time"""
    try:
        get_statsd().timing(f"api.{endpoint}.time", elapsed_ms)
    except Exception:
        pass


def record_db_query_time(query_name: str, elapsed_ms: float) -> None:
    """Record DB query duration. Metric: csye6225.db.<query_name>.time"""
    try:
        get_statsd().timing(f"db.{query_name}.time", elapsed_ms)
    except Exception:
        pass


def record_s3_time(operation: str, elapsed_ms: float) -> None:
    """Record S3 operation duration. Metric: csye6225.s3.<operation>.time"""
    try:
        get_statsd().timing(f"s3.{operation}.time", elapsed_ms)
    except Exception:
        pass
