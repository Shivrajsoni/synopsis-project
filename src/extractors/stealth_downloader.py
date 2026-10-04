"""
Stealth Downloader for University & Aggregator Portals.
Bypasses bot restrictions, Cloudflare WAF, TLS fingerprinting, and SSL certificate issues
using curl_cffi (JA3/JA4 Chrome impersonation), cloudscraper, and resilient sessions.
"""
import logging
import subprocess
import time
from typing import Optional, Tuple

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("StealthDownloader")

# Realistic macOS Chrome Headers
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
}

def fetch_with_curl_cffi(url: str, timeout: int = 30) -> Optional[Tuple[bytes, str, int]]:
    """
    Attempt fetch using curl_cffi with Chrome TLS impersonation (JA3/JA4 fingerprinting bypass).
    Returns (content_bytes, content_type, status_code) or None.
    """
    try:
        from curl_cffi import requests as cffi_requests
        response = cffi_requests.get(
            url,
            headers=BROWSER_HEADERS,
            impersonate="chrome120",
            timeout=timeout,
            verify=False,
            allow_redirects=True
        )
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            return response.content, content_type, response.status_code
        else:
            logger.debug(f"[curl_cffi] Status {response.status_code} for {url}")
    except Exception as e:
        logger.debug(f"[curl_cffi] Failed for {url}: {e}")
    return None

def fetch_with_cloudscraper(url: str, timeout: int = 30) -> Optional[Tuple[bytes, str, int]]:
    """
    Attempt fetch using cloudscraper for Cloudflare JavaScript challenge bypass.
    """
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'desktop': True
            }
        )
        response = scraper.get(url, headers=BROWSER_HEADERS, timeout=timeout, verify=False)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            return response.content, content_type, response.status_code
        else:
            logger.debug(f"[cloudscraper] Status {response.status_code} for {url}")
    except Exception as e:
        logger.debug(f"[cloudscraper] Failed for {url}: {e}")
    return None

def fetch_with_requests(url: str, timeout: int = 30) -> Optional[Tuple[bytes, str, int]]:
    """
    Attempt fetch using requests with full browser headers and disabled SSL verification.
    """
    try:
        import requests
        session = requests.Session()
        response = session.get(
            url,
            headers=BROWSER_HEADERS,
            timeout=timeout,
            verify=False,
            allow_redirects=True
        )
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            return response.content, content_type, response.status_code
        else:
            logger.debug(f"[requests] Status {response.status_code} for {url}")
    except Exception as e:
        logger.debug(f"[requests] Failed for {url}: {e}")
    return None

def fetch_with_system_curl(url: str, timeout: int = 30) -> Optional[Tuple[bytes, str, int]]:
    """
    Final fallback: Execute native macOS curl with compression and relaxed TLS.
    """
    try:
        cmd = [
            "curl",
            "-s", "-L", "-k",
            "--compressed",
            "--max-time", str(timeout),
            "-A", BROWSER_HEADERS["User-Agent"],
            "-H", f"Accept: {BROWSER_HEADERS['Accept']}",
            "-H", f"Accept-Language: {BROWSER_HEADERS['Accept-Language']}",
            url
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 5)
        if result.returncode == 0 and len(result.stdout) > 0:
            content = result.stdout
            content_type = "application/pdf" if content.startswith(b"%PDF") else "text/html"
            return content, content_type, 200
    except Exception as e:
        logger.debug(f"[system_curl] Failed for {url}: {e}")
    return None

def download_stealth(url: str, max_retries: int = 3, timeout: int = 30) -> Optional[Tuple[bytes, str]]:
    """
    Multi-tier stealth downloader.
    Tries curl_cffi -> cloudscraper -> requests -> system_curl in cascade.
    Returns:
        (content_bytes, content_type) or None if all tiers failed.
    """
    for attempt in range(1, max_retries + 1):
        logger.info(f"Downloading [{attempt}/{max_retries}]: {url}")

        # Tier 1: curl_cffi (JA3 TLS fingerprint bypass)
        res = fetch_with_curl_cffi(url, timeout=timeout)
        if res:
            logger.info(f"  ✓ Success via [curl_cffi]: {url} ({len(res[0])} bytes)")
            return res[0], res[1]

        # Tier 2: cloudscraper (Cloudflare JS challenge solver)
        res = fetch_with_cloudscraper(url, timeout=timeout)
        if res:
            logger.info(f"  ✓ Success via [cloudscraper]: {url} ({len(res[0])} bytes)")
            return res[0], res[1]

        # Tier 3: standard requests with browser headers
        res = fetch_with_requests(url, timeout=timeout)
        if res:
            logger.info(f"  ✓ Success via [requests]: {url} ({len(res[0])} bytes)")
            return res[0], res[1]

        # Tier 4: macOS system curl
        res = fetch_with_system_curl(url, timeout=timeout)
        if res:
            logger.info(f"  ✓ Success via [system_curl]: {url} ({len(res[0])} bytes)")
            return res[0], res[1]

        logger.warning(f"  ✗ Attempt {attempt} failed for {url}. Waiting before retry...")
        time.sleep(2 * attempt)

    logger.error(f"  ✗ All extraction tiers failed for {url}")
    return None
