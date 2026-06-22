"""Given a LinkedIn job URL, return company name + company website URL."""
import json
import re
import sys
from pathlib import Path
from typing import List

# Ensure both opportunity-agent/ (for models) and career-agent/ (for shared) are on the path
# when this file is run directly from any working directory.
_AGENT_ROOT = Path(__file__).parent.parent        # opportunity-agent/
_REPO_ROOT = Path(__file__).parent.parent.parent  # career-agent/
for _p in (_AGENT_ROOT, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import requests
from bs4 import BeautifulSoup
from groq import Groq
from playwright.sync_api import sync_playwright

from models.schemas import JobSourceOutput
from shared.config import get_groq_api_key

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _fetch_html_requests(url: str) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12, allow_redirects=True)
        if resp.ok and len(resp.text) > 3000:
            return resp.text
    except requests.RequestException:
        pass
    return ""


def _fetch_html_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(_HEADERS)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)
            return page.content()
        except Exception:
            return ""
        finally:
            browser.close()


def _parse_company_info(html: str) -> tuple[str, str]:
    """Return (company_name, company_website) from LinkedIn job page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    company_name = ""
    company_website = ""

    # Strategy 1: JSON-LD structured data (served server-side for SEO)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = next(
                    (d for d in data if isinstance(d, dict) and d.get("@type") == "JobPosting"),
                    {},
                )
            if data.get("@type") == "JobPosting":
                org = data.get("hiringOrganization", {})
                company_name = org.get("name", "")
                for key in ("url", "sameAs"):
                    val = org.get(key, "")
                    if val and "linkedin.com" not in val:
                        company_website = val
                        break
                if company_name:
                    break
        except (json.JSONDecodeError, AttributeError):
            pass

    # Strategy 2: og:title / page <title>
    # LinkedIn uses two formats:
    #   "Job Title at Company | LinkedIn"
    #   "Company hiring Job Title in Location | LinkedIn"
    if not company_name:
        candidates = [
            soup.find("meta", property="og:title"),
            soup.find("title"),
        ]
        for el in candidates:
            if el is None:
                continue
            text = el.get("content", "") if el.name == "meta" else el.get_text()
            # Format A: "... at Company | LinkedIn"
            m = re.search(r" at (.+?)(?:\s*[\|–\-]\s*LinkedIn|\s*\|)", text)
            if m:
                company_name = m.group(1).strip()
                break
            # Format B: "Company hiring ..."
            m = re.match(r"^(.+?) hiring ", text)
            if m:
                company_name = m.group(1).strip()
                break

    return company_name, company_website


def _llm_get_website(company_name: str) -> str:
    """Ask Groq to return the company's official homepage URL."""
    try:
        client = Groq(api_key=get_groq_api_key())
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Return ONLY the official homepage URL of '{company_name}'. "
                        "No explanation — just the URL (e.g. https://stripe.com)."
                    ),
                }
            ],
            max_tokens=60,
        )
        raw = response.choices[0].message.content.strip()
        m = re.search(r"https?://[^\s,;\"'<>]+", raw)
        return m.group(0).rstrip(".,)") if m else ""
    except Exception:
        return ""


def _google_search_website(company_name: str) -> str:
    """Search Google for the company's official website."""
    try:
        from googlesearch import search as gsearch
        query = f"{company_name} official website"
        skip = (
            "linkedin.com", "glassdoor", "indeed.com", "facebook.com",
            "twitter.com", "instagram.com", "crunchbase.com",
        )
        for result_url in gsearch(query, num_results=5):
            if not any(s in result_url.lower() for s in skip):
                return result_url
    except Exception:
        pass
    return ""


def _guess_company_website(company_name: str) -> str:
    """Fallback: probe common domain patterns and verify the page belongs to the company."""
    slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
    name_lower = company_name.lower()
    candidates = [
        f"https://www.{slug}.com",
        f"https://{slug}.com",
        f"https://{slug}.co",
        f"https://www.{slug}.co",
        f"https://{slug}.io",
    ]
    for url in candidates:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=7, allow_redirects=True)
            if not resp.ok:
                continue
            from bs4 import BeautifulSoup as _BS
            soup = _BS(resp.text, "html.parser")
            title_el = soup.find("title")
            title = title_el.get_text().lower() if title_el else ""
            # Reject generic parking pages (GoDaddy, etc.)
            if "godaddy" in title or "for sale" in title or not title:
                continue
            # Prefer pages whose title or content references the company name
            first_word = name_lower.split()[0]
            if first_word in title or first_word in resp.text.lower()[:3000]:
                return url
        except requests.RequestException:
            pass
    return ""


def extract_company_info(linkedin_job_url: str) -> tuple[str, str]:
    """Return (company_name, company_website) from a LinkedIn job URL."""
    html = _fetch_html_requests(linkedin_job_url) or _fetch_html_playwright(linkedin_job_url)
    company_name, company_website = _parse_company_info(html)

    if company_name and not company_website:
        candidate = _llm_get_website(company_name)
        if candidate:
            # Reject parked/placeholder domains
            try:
                from bs4 import BeautifulSoup as _BS
                r = requests.get(candidate, headers=_HEADERS, timeout=7, allow_redirects=True)
                if r.ok:
                    t = _BS(r.text, "html.parser").find("title")
                    title = t.get_text().lower() if t else ""
                    if "godaddy" not in title and "for sale" not in title:
                        company_website = candidate
            except requests.RequestException:
                pass
    if company_name and not company_website:
        company_website = _google_search_website(company_name)
    if company_name and not company_website:
        company_website = _guess_company_website(company_name)

    return company_name, company_website


def extract_linkedin_job_info(linkedin_job_url: str) -> JobSourceOutput:
    company_name, company_website = extract_company_info(linkedin_job_url)
    return JobSourceOutput(
        company_name=company_name,
        career_page_url=company_website,
        open_position_url=linkedin_job_url,
    )


def extract_linkedin_jobs_info(linkedin_job_urls: List[str]) -> List[JobSourceOutput]:
    return [extract_linkedin_job_info(url) for url in linkedin_job_urls]


if __name__ == "__main__":
    sample_urls = [
        "https://www.linkedin.com/jobs/view/4422987353/",
        "https://www.linkedin.com/jobs/view/4428315173/",
    ]
    for info in extract_linkedin_jobs_info(sample_urls):
        print(info)
