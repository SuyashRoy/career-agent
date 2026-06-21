"""Given a company website URL, find the careers page."""
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

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


def _get_homepage_links(url: str) -> list[tuple[str, str]]:
    """Return [(link_text, absolute_href), ...] from the homepage."""
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


def _llm_identify_career_url(company_name: str, company_url: str, links_text: str) -> str:
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Company: {company_name}\nHomepage: {company_url}\n\n"
                        "From the following links scraped from the company homepage, "
                        "identify which URL leads to their careers or jobs page. "
                        "Return ONLY the URL, nothing else.\n\n"
                        f"Links:\n{links_text}"
                    ),
                }
            ],
            max_tokens=100,
        )
        raw = response.choices[0].message.content.strip()
        m = re.search(r"https?://[^\s,;\"'<>]+", raw)
        return m.group(0).rstrip(".,)") if m else ""
    except Exception:
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

    # Strategy 3: LLM picks from scanned links
    if links:
        snippet = "\n".join(f"{text} -> {href}" for text, href in links[:60])
        result = _llm_identify_career_url(company_name, company_website, snippet)
        if result and result.rstrip("/") != base_normalized:
            return result

    return ""


if __name__ == "__main__":
    print(find_career_page("Stripe", "https://stripe.com"))
    print(find_career_page("Anthropic", "https://anthropic.com"))
