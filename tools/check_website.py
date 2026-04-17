"""
AI Holding Company — Tool: check_website
Checks website uptime, response time, and SSL certificate expiry.
"""

import ssl
import socket
import time
import json
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ============================================================
# CONFIGURATION — Edit these URLs to match YOUR websites
# ============================================================

WEBSITES = [
    {
        "name": "Main Website",
        "url": "https://your-website-1.com",       # <-- EDIT THIS
        "expected_status": 200,
    },
    {
        "name": "Secondary Site",
        "url": "https://your-website-2.com",        # <-- EDIT THIS
        "expected_status": 200,
    },
    # Add more sites as needed:
    # {
    #     "name": "Blog",
    #     "url": "https://blog.example.com",
    #     "expected_status": 200,
    # },
]

# Thresholds
SLOW_RESPONSE_MS = 2000   # Flag if response takes longer than this
SSL_WARN_DAYS = 30        # Flag if SSL expires within this many days


# ============================================================
# CHECK FUNCTIONS
# ============================================================

def check_http(url: str, timeout: int = 15) -> dict:
    """Check HTTP status and response time for a URL."""
    result = {
        "url": url,
        "status_code": None,
        "response_time_ms": None,
        "error": None,
    }
    try:
        req = Request(url, headers={"User-Agent": "AIHoldingCompany-Monitor/1.0"})
        start = time.time()
        response = urlopen(req, timeout=timeout)
        elapsed = (time.time() - start) * 1000  # ms

        result["status_code"] = response.getcode()
        result["response_time_ms"] = round(elapsed)
    except HTTPError as e:
        result["status_code"] = e.code
        result["error"] = str(e.reason)
    except URLError as e:
        result["error"] = f"Connection failed: {e.reason}"
    except Exception as e:
        result["error"] = str(e)

    return result


def check_ssl(hostname: str) -> dict:
    """Check SSL certificate expiry date for a hostname."""
    result = {
        "hostname": hostname,
        "ssl_expiry": None,
        "ssl_days_remaining": None,
        "ssl_error": None,
    }
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert["notAfter"]
                # Format: 'Mar 15 12:00:00 2027 GMT'
                expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                days_remaining = (expiry_date - datetime.utcnow()).days

                result["ssl_expiry"] = expiry_date.strftime("%Y-%m-%d")
                result["ssl_days_remaining"] = days_remaining
    except Exception as e:
        result["ssl_error"] = str(e)

    return result


def extract_hostname(url: str) -> str:
    """Extract hostname from URL."""
    # Simple extraction without importing urllib.parse
    url = url.replace("https://", "").replace("http://", "")
    return url.split("/")[0].split(":")[0]


# ============================================================
# MAIN CHECK
# ============================================================

def check_website(url: str = None) -> str:
    """
    Check one or all websites. Pass a URL to check one, or None for all.
    Returns a formatted report string.
    """
    sites_to_check = []
    if url:
        sites_to_check = [{"name": url, "url": url, "expected_status": 200}]
    else:
        sites_to_check = WEBSITES

    reports = []
    for site in sites_to_check:
        name = site["name"]
        site_url = site["url"]
        expected = site["expected_status"]

        # HTTP check
        http = check_http(site_url)

        # SSL check (only for HTTPS)
        ssl_info = {}
        if site_url.startswith("https://"):
            hostname = extract_hostname(site_url)
            ssl_info = check_ssl(hostname)

        # Determine status
        alerts = []
        if http["error"]:
            status = "🔴 DOWN"
            alerts.append(f"HTTP Error: {http['error']}")
        elif http["status_code"] != expected:
            status = "🟡 WARN"
            alerts.append(f"Expected {expected}, got {http['status_code']}")
        elif http["response_time_ms"] and http["response_time_ms"] > SLOW_RESPONSE_MS:
            status = "🟡 SLOW"
            alerts.append(f"Response time {http['response_time_ms']}ms > {SLOW_RESPONSE_MS}ms threshold")
        else:
            status = "🟢 UP"

        if ssl_info.get("ssl_error"):
            alerts.append(f"SSL Error: {ssl_info['ssl_error']}")
        elif ssl_info.get("ssl_days_remaining") is not None:
            if ssl_info["ssl_days_remaining"] < SSL_WARN_DAYS:
                alerts.append(
                    f"⚠️ SSL expires in {ssl_info['ssl_days_remaining']} days "
                    f"({ssl_info['ssl_expiry']})"
                )

        # Format report
        response_str = f"{http['response_time_ms']}ms" if http["response_time_ms"] else "N/A"
        ssl_str = ssl_info.get("ssl_expiry", "N/A")
        ssl_days = ssl_info.get("ssl_days_remaining", "?")

        report = (
            f"Site: {name} | Status: {status}\n"
            f"  URL: {site_url}\n"
            f"  HTTP {http['status_code'] or 'N/A'} | Response: {response_str}\n"
            f"  SSL expires: {ssl_str} ({ssl_days} days)\n"
        )
        if alerts:
            report += "  Alerts:\n"
            for alert in alerts:
                report += f"    - {alert}\n"

        reports.append(report)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"═══ WEBSITE STATUS REPORT — {timestamp} ═══\n\n"
    return header + "\n".join(reports)


# ============================================================
# CLI entry point for testing
# ============================================================
if __name__ == "__main__":
    import sys
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(check_website(url_arg))
