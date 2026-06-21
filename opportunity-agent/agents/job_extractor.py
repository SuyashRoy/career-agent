"""Given a careers page URL, extract one active job posting URL."""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Segments that signal a careers section on the same domain
_CAREER_SECTION_RE = re.compile(
    r"/(job|jobs|career|careers|position|positions|opening|openings|"
    r"role|roles|requisition|posting|apply)s?/",
    re.IGNORECASE,
)

# A specific job posting must have a numeric ID or UUID-like slug
_JOB_ID_RE = re.compile(
    r"/\d{4,}([^/]*$|/)|/[a-f0-9]{8}-[a-f0-9-]{26,}/|/[A-Za-z0-9_-]{20,}$",
    re.IGNORECASE,
)

# External ATS platforms
_ATS_DOMAIN_RE = re.compile(
    r"(greenhouse\.io|lever\.co|myworkdayjobs\.com|smartrecruiters\.com|"
    r"icims\.com|taleo\.net|brassring\.com|ashbyhq\.com|"
    r"jobs\.ashbyhq\.com|apply\.workable\.com|jobvite\.com|"
    r"recruitingbypaycor\.com|dayforce\.com|rippling\.com)",
    re.IGNORECASE,
)


_SPA_INDICATORS = (
    "you need to enable javascript",
    "enable javascript to run this app",
    "javascript is required",
    "<noscript>",
)


def _is_spa_shell(html: str) -> bool:
    """True when HTML is a JS-app shell with no real content."""
    snippet = html[:5000].lower()
    return any(ind in snippet for ind in _SPA_INDICATORS)


def _fetch_html(url: str, wait_ms: int = 2500) -> str:
    # ATS platforms are JS-heavy SPAs — requests returns a shell with no links
    if not _ATS_DOMAIN_RE.search(url):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=12, allow_redirects=True)
            if resp.ok and len(resp.text) > 2000 and not _is_spa_shell(resp.text):
                return resp.text
        except requests.RequestException:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(_HEADERS)
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_ms)
            return page.content()
        except Exception:
            return ""
        finally:
            browser.close()


def _is_direct_job_link(href: str, career_base: str) -> bool:
    """True when href is a same-domain URL that looks like a specific job posting."""
    base_netloc = urlparse(career_base).netloc
    href_parts = urlparse(href)
    if href_parts.netloc and href_parts.netloc != base_netloc:
        return False
    if not _CAREER_SECTION_RE.search(href):
        return False
    return bool(_JOB_ID_RE.search(href))


def _find_job_in_ats(ats_url: str) -> str:
    """Navigate to an ATS landing page and return the first specific job link."""
    html = _fetch_html(ats_url, wait_ms=5000)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    ats_netloc = urlparse(ats_url).netloc
    base_segments = [s for s in urlparse(ats_url).path.split("/") if s]
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(ats_url, a["href"])
        if href in seen or href == ats_url:
            continue
        seen.add(href)

        link_parts = urlparse(href)
        if link_parts.netloc != ats_netloc:
            continue

        link_segments = [s for s in link_parts.path.split("/") if s]
        # Must be substantially deeper than the board landing page
        if len(link_segments) < len(base_segments) + 3:
            continue
        # Must look like a job posting (career path segment or numeric/UUID ID)
        if _CAREER_SECTION_RE.search(href) or _JOB_ID_RE.search(href):
            return href

    return ""


def extract_job_url(career_page_url: str) -> str:
    if not career_page_url:
        return ""

    html = _fetch_html(career_page_url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    ats_landing_pages: list[str] = []
    direct_job_links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = urljoin(career_page_url, a["href"])
        if href in seen or href == career_page_url:
            continue
        seen.add(href)

        if _ATS_DOMAIN_RE.search(href):
            link_netloc = urlparse(href).netloc
            link_path = urlparse(href).path
            # Check if this is already a deep/specific ATS job URL
            if "/" in link_path.strip("/") and link_path.count("/") >= 3:
                direct_job_links.append(href)
            else:
                ats_landing_pages.append(href)
        elif _is_direct_job_link(href, career_page_url):
            direct_job_links.append(href)

    # Prefer specific job postings already found
    if direct_job_links:
        return direct_job_links[0]

    # Navigate into ATS landing pages to find a specific job
    for ats_url in ats_landing_pages[:2]:
        job = _find_job_in_ats(ats_url)
        if job:
            return job

    # Last resort: return ATS landing page itself
    if ats_landing_pages:
        return ats_landing_pages[0]

    return ""


if __name__ == "__main__":
    print(extract_job_url("https://www.boozallen.com/careers"))
    print(extract_job_url("https://stripe.com/jobs/listing"))
    print(extract_job_url("https://www.anthropic.com/careers"))
