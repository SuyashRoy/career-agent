"""Load and normalize job descriptions from multiple sources.

Supports three input paths:
    1. URL scraping   — fetch a job posting URL and extract description text
                        (primary path when wired to the Opportunity Discovery Agent)
    2. File loading   — read .txt or .json files from test_data/job_descriptions/
                        (fallback for local testing without the Opportunity Agent)
    3. Direct input   — accept raw text, dicts, or lists programmatically

Always returns a standardized list[dict], each with at minimum:
    {"title": str, "description": str}
"""

import json
import logging
from pathlib import Path
from typing import Union

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path 1: URL Scraping (Opportunity Agent integration)
# ---------------------------------------------------------------------------

def scrape_jd_from_url(url: str) -> dict:
    """Fetch a job posting URL and extract the description text.

    Uses requests + BeautifulSoup for static pages. Strips navigation,
    scripts, and boilerplate to isolate the job description body.

    Args:
        url: Full URL to a job posting page.

    Returns:
        dict with keys: title, url, description.

    Raises:
        ValueError: If the page cannot be fetched or parsed.
    """
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CareerAgent/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch {url}: {e}") from e

    soup = BeautifulSoup(response.text, "html.parser")

    # Strip non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    if len(text.strip()) < 50:
        raise ValueError(f"Extracted text too short from {url} — likely a JS-rendered page")

    title = soup.title.string.strip() if soup.title and soup.title.string else "Unknown"

    return {"title": title, "url": url, "description": text}


# ---------------------------------------------------------------------------
# Path 2: File Loading (local testing fallback)
# ---------------------------------------------------------------------------

# Default path relative to this file: ../test_data/job_descriptions/
DEFAULT_JD_DIR = Path(__file__).parent.parent / "test_data" / "job_descriptions"


def load_from_txt_file(file_path: Path) -> dict:
    """Load a plain-text job description from a .txt file.

    Expects the first non-empty line to be the job title,
    followed by the description body.

    Args:
        file_path: Path to a .txt file.

    Returns:
        dict with keys: title, description, source_file.
    """
    text = file_path.read_text(encoding="utf-8").strip()
    lines = [line for line in text.splitlines() if line.strip()]

    if not lines:
        raise ValueError(f"Empty file: {file_path}")

    title = lines[0].strip()
    description = "\n".join(lines[1:]).strip() if len(lines) > 1 else title

    return {"title": title, "description": description, "source_file": str(file_path)}


def load_from_json_file(file_path: Path) -> list[dict]:
    """Load one or more JDs from a JSON file.

    Accepts either a single JD object or a list of JD objects.

    Args:
        file_path: Path to a .json file.

    Returns:
        list[dict], each with at minimum a 'description' key.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [_normalize_dict(item) for item in data]
    elif isinstance(data, dict):
        return [_normalize_dict(data)]
    else:
        raise ValueError(f"Expected dict or list in {file_path}, got {type(data)}")


def load_all_from_directory(directory: Union[str, Path] = None) -> list[dict]:
    """Load all JD files (.txt and .json) from a directory.

    Args:
        directory: Path to the directory. Defaults to test_data/job_descriptions/.

    Returns:
        list[dict] of all loaded job descriptions.
    """
    dir_path = Path(directory) if directory else DEFAULT_JD_DIR

    if not dir_path.exists():
        raise FileNotFoundError(f"JD directory not found: {dir_path}")

    results = []

    for file_path in sorted(dir_path.iterdir()):
        try:
            if file_path.suffix == ".txt":
                results.append(load_from_txt_file(file_path))
            elif file_path.suffix == ".json":
                results.extend(load_from_json_file(file_path))
            else:
                logger.debug(f"Skipping unsupported file: {file_path}")
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load {file_path}: {e}")

    if not results:
        logger.warning(f"No JDs loaded from {dir_path}")

    return results


# ---------------------------------------------------------------------------
# Path 3: Direct Input (programmatic usage)
# ---------------------------------------------------------------------------

def load_from_text(text: str) -> dict:
    """Wrap raw text into a standardized JD dict."""
    return {"title": "Unknown", "description": text.strip()}


def _normalize_dict(data: dict) -> dict:
    """Normalize a dict from various sources into standard format.

    Handles three dict formats:
        - Opportunity Agent output:  {'company_name', 'open_position_url', ...}
        - Scraped/legacy format:     {'job_description': '...'}
        - Direct input:              {'description': '...'}

    If the dict has an 'open_position_url' but no description text,
    scrapes the URL automatically.
    """
    # Opportunity Agent format — has URL but no description yet
    if "open_position_url" in data and "description" not in data:
        try:
            scraped = scrape_jd_from_url(data["open_position_url"])
            scraped["company"] = data.get("company_name", "")
            scraped["website"] = data.get("company_website", "")
            return scraped
        except ValueError as e:
            logger.warning(f"URL scrape failed, using URL as placeholder: {e}")
            return {
                "title": data.get("company_name", "Unknown"),
                "description": f"Job posting at {data.get('company_name', 'Unknown')}. "
                               f"URL: {data['open_position_url']}",
                "url": data["open_position_url"],
            }

    # Has description text under 'job_description' key
    if "job_description" in data:
        return {
            "title": data.get("title", "Unknown"),
            "location": data.get("location", ""),
            "url": data.get("url", ""),
            "description": data["job_description"],
        }

    # Has description text under 'description' key
    if "description" in data:
        return data

    raise ValueError(
        f"Dict must contain 'description', 'job_description', or "
        f"'open_position_url'. Got keys: {list(data.keys())}"
    )


# ---------------------------------------------------------------------------
# Universal Entry Point
# ---------------------------------------------------------------------------

def load_job_descriptions(source: Union[str, dict, list, Path] = None) -> list[dict]:
    """Universal loader — detects format and returns list[dict].

    Args:
        source: One of:
            - None:  load all files from test_data/job_descriptions/
            - str:   raw text, JSON string, file path, or URL
            - dict:  single JD (direct, Opportunity Agent, or scraped format)
            - list:  list of dicts or strings
            - Path:  path to a .json or .txt file, or a directory

    Returns:
        list[dict], each with at minimum 'title' and 'description' keys.
    """
    # No source → load from default directory (Option C fallback)
    if source is None:
        return load_all_from_directory()

    # Path object
    if isinstance(source, Path):
        if source.is_dir():
            return load_all_from_directory(source)
        elif source.suffix == ".json":
            return load_from_json_file(source)
        elif source.suffix == ".txt":
            return [load_from_txt_file(source)]
        else:
            raise ValueError(f"Unsupported file type: {source.suffix}")

    # String input
    if isinstance(source, str):
        # URL detection
        if source.startswith(("http://", "https://")):
            return [scrape_jd_from_url(source)]

        # File path detection
        path = Path(source)
        if path.exists():
            if path.is_dir():
                return load_all_from_directory(path)
            elif path.suffix == ".json":
                return load_from_json_file(path)
            elif path.suffix == ".txt":
                return [load_from_txt_file(path)]

        # Try JSON string
        try:
            parsed = json.loads(source)
            if isinstance(parsed, list):
                return [_normalize_dict(item) for item in parsed]
            if isinstance(parsed, dict):
                return [_normalize_dict(parsed)]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall through to raw text
        return [load_from_text(source)]

    # Single dict
    if isinstance(source, dict):
        return [_normalize_dict(source)]

    # List of sources
    if isinstance(source, list):
        results = []
        for item in source:
            if isinstance(item, str):
                results.append(load_from_text(item))
            elif isinstance(item, dict):
                results.append(_normalize_dict(item))
            else:
                raise ValueError(f"Unsupported item type in list: {type(item)}")
        return results

    raise ValueError(f"Unsupported source type: {type(source)}")


# ---------------------------------------------------------------------------
# Standalone Testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("JOB DESCRIPTION LOADER — SMOKE TESTS")
    print("=" * 60)

    # Test 1: Raw text
    print("\n[Test 1] Raw text input")
    jds = load_job_descriptions("We need an ML engineer with PyTorch experience.")
    print(f"  Loaded {len(jds)} JD(s): {jds[0]['title']} — {jds[0]['description'][:60]}...")

    # Test 2: Dict (Opportunity Agent format)
    print("\n[Test 2] Opportunity Agent dict format")
    jds = load_job_descriptions({
        "company_name": "Anthropic",
        "company_website": "https://anthropic.com",
        "open_position_url": "https://anthropic.com/careers",
    })
    print(f"  Loaded {len(jds)} JD(s): {jds[0]['title']} — {jds[0]['description'][:60]}...")

    # Test 3: Direct dict with description
    print("\n[Test 3] Direct dict with description")
    jds = load_job_descriptions({"title": "Data Scientist", "description": "Build ML models."})
    print(f"  Loaded {len(jds)} JD(s): {jds[0]['title']}")

    # Test 4: List of strings
    print("\n[Test 4] List of raw strings")
    jds = load_job_descriptions([
        "Senior data scientist for recommendation systems.",
        "ML engineer for real-time inference pipelines.",
    ])
    print(f"  Loaded {len(jds)} JD(s)")

    # Test 5: Load from directory (Option C fallback)
    print("\n[Test 5] Load from test_data/job_descriptions/ directory")
    try:
        jds = load_job_descriptions()
        print(f"  Loaded {len(jds)} JD(s) from directory")
        for jd in jds:
            print(f"    - {jd['title']}: {jd['description'][:50]}...")
    except FileNotFoundError as e:
        print(f"  (Expected) {e}")

    print("\n" + "=" * 60)
    print("ALL SMOKE TESTS PASSED")
    print("=" * 60)