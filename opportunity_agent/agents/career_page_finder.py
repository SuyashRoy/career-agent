"""Given a company website URL, find the careers page."""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

_AGENT_ROOT = Path(__file__).parent.parent        # opportunity-agent/
_REPO_ROOT = Path(__file__).parent.parent.parent  # career-agent/
for _p in (_AGENT_ROOT, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import requests
from bs4 import BeautifulSoup
from groq import Groq
from playwright.sync_api import sync_playwright

from shared.config import get_groq_api_key

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_CAREER_PATHS = [
    "/careers", "/jobs", "/join-us", "/join", "/work-with-us",
    "/hiring", "/open-positions", "/careers/jobs", "/about/careers",
    "/company/careers", "/en/careers", "/us/careers", "/work-here",
    "/careers/openings", "/careers/listings",
]

_CAREER_KEYWORDS = {
    "career", "careers", "jobs", "job openings", "hiring",
    "join us", "work with us", "open positions", "opportunities",
    "vacancies", "work here", "join our team", "we're hiring",
    "join the team", "see open roles", "view openings",
}


def _check_url(url: str) -> bool:
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=6, allow_redirects=True)
        if resp.status_code == 200:
            return True
        if resp.status_code in (405, 403):
            resp = requests.get(url, headers=_HEADERS, timeout=8, allow_redirects=True)
            return resp.status_code == 200
    except requests.RequestException:
        pass
    return False


def _get_homepage_links_requests(url: str) -> list[tuple[str, str]]:
    """Fast path: fetch homepage with requests and parse static links."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        if not resp.ok:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = urljoin(url, a["href"])
            if href.startswith("http"):
                links.append((text, href))
        return links
    except requests.RequestException:
        return []


def _get_homepage_links_playwright(url: str) -> list[tuple[str, str]]:
    """Load page with Playwright to capture JS-rendered navigation links."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(_HEADERS)
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            links_data = page.evaluate("""
                () => Array.from(document.querySelectorAll('a'))
                    .map(a => ({
                        text: a.innerText.trim().toLowerCase(),
                        href: a.href
                    }))
                    .filter(l => l.text && l.href && l.href.startsWith('http'))
            """)
            return [(l["text"], l["href"]) for l in links_data]
        except Exception:
            return []
        finally:
            browser.close()


def _get_homepage_links(url: str) -> list[tuple[str, str]]:
    """Try requests first; fall back to Playwright if too few links returned."""
    links = _get_homepage_links_requests(url)
    if len(links) < 5:
        playwright_links = _get_homepage_links_playwright(url)
        if playwright_links:
            return playwright_links
    return links


def _llm_identify_career_url(company_name: str, company_url: str, links_text: str) -> str:
    try:
        client = Groq(api_key=get_groq_api_key())
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a web navigation agent. Your task is to identify "
                        "which link on a company's website leads to their careers "
                        "or jobs page. Analyze the link text and URL patterns to "
                        "make your decision."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Company: {company_name}\n"
                        f"Homepage: {company_url}\n\n"
                        "Here are all the links found on this page:\n\n"
                        f"{links_text}\n\n"
                        "Which link leads to the careers/jobs page?\n\n"
                        "Think step by step:\n"
                        "1. Which links have career-related text (careers, jobs, "
                        "join us, hiring, open positions, work with us)?\n"
                        "2. Which links have career-related URL patterns "
                        "(/careers, /jobs, /join)?\n"
                        "3. If multiple candidates exist, which is most likely "
                        "the main careers page (not a specific job listing)?\n\n"
                        "After your reasoning, output ONLY the URL on the final "
                        "line. If no careers link exists, output NONE."
                    ),
                },
            ],
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        # Take the last URL found (after any chain-of-thought reasoning)
        urls = re.findall(r"https?://[^\s,;\"'<>]+", raw)
        return urls[-1].rstrip(".,)") if urls else ""
    except Exception:
        return ""


def _google_search_career_page(company_name: str) -> str:
    """Search Google for the company's career page as a last resort."""
    try:
        from googlesearch import search as gsearch
        query = f"{company_name} careers jobs page"
        for result_url in gsearch(query, num_results=5):
            lower = result_url.lower()
            if any(kw in lower for kw in ("career", "jobs", "hiring", "join")):
                return result_url
    except Exception:
        pass
    return ""


def find_career_page(company_name: str, company_website: str) -> str:
    if not company_website:
        return ""

    base = company_website.rstrip("/")

    # Strategy 1: common URL path patterns
    for path in _CAREER_PATHS:
        candidate = base + path
        if _check_url(candidate):
            return candidate

    # Strategy 2: scan homepage links for career keywords
    links = _get_homepage_links(base)
    base_normalized = base.rstrip("/")
    for text, href in links:
        href_normalized = href.rstrip("/")
        if href_normalized == base_normalized:
            continue
        if any(kw in text for kw in _CAREER_KEYWORDS):
            return href

    # Strategy 3: LLM agent reasons over the full link list
    if links:
        snippet = "\n".join(f"{text} -> {href}" for text, href in links[:60])
        result = _llm_identify_career_url(company_name, company_website, snippet)
        if result and result.rstrip("/") != base_normalized:
            return result

    # Strategy 4: Google search fallback
    return _google_search_career_page(company_name)


if __name__ == "__main__":
    print(find_career_page("Stripe", "https://stripe.com"))
    print(find_career_page("Anthropic", "https://anthropic.com"))
