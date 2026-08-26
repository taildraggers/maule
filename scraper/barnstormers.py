"""Scraper for Maule aircraft listings on barnstormers.com.

Barnstormers' single-manufacturer category pages (the same pattern seen in
the companion Aviat, CubCrafters, and de Havilland repos) can mix in
off-brand or off-topic listings with no distinguishing HTML markup from the
genuine ones. So results are filtered by title against a small allowlist of
Maule product names before being published.

On top of that brand allowlist, only whole-aircraft-for-sale listings are
kept: each ad's title must state a model year and match a recognized Maule
model, and titles that look like parts/accessories/services/raffles are
dropped. Surviving titles are rewritten to a canonical "YEAR Maule MODEL"
form so every listing follows the same format.
"""
from __future__ import annotations

import re
from urllib.parse import quote, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from .common import (
    Listing,
    extract_date,
    extract_location,
    extract_price,
    fetch,
    format_aircraft_title,
)

SITE_NAME = "Barnstormers.com"
BASE = "https://www.barnstormers.com"
MAKE = "Maule"

# Category page for Maule listings on Barnstormers.
CATEGORY_URLS = [
    f"{BASE}/category-20575-Maule.html",
]

# Only ads whose title matches one of these (case/hyphen/space-insensitive)
# are kept - the category page itself isn't reliably Maule-only.
# Compact (no spaces/hyphens) forms, since _title_from_url() turns every
# hyphen in the source URL slug into a space, so a model written "M-7" in
# the original ad can arrive here as "M 7", "M-7", or (if the seller's own
# slug had none) "M7" - comparing against a fully compacted title sidesteps
# the formatting difference.
TARGET_MODEL_PHRASES = [
    "maule",
    "m4",
    "m5",
    "m6",
    "m7",
    "m8",
    "m9",
    "mx7",
    "mxt7",
    "mt7",
]

MAX_PAGES = 10
LISTING_LINK_RE = re.compile(r"^/classified-(\d+)-(.+)\.html$")
GENERIC_SITE_TITLE_SNIPPET = "barnstormers.com find aircraft"


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _compact(text: str) -> str:
    return re.sub(r"[\s-]", "", text.lower())


def _matches_target_models(title: str) -> bool:
    compact = _compact(title)
    return any(phrase in compact for phrase in TARGET_MODEL_PHRASES)


# Maule model codes are "M"/"MX"/"MXT"/"MT" + a digit (4-9), optionally
# followed by a horsepower/variant suffix and a trailing letter (e.g.
# "M-7-235C", "M 7 235C", "MX-7-160", "M5"). The prefix/number and the
# number/variant may be separated by a space, a hyphen, or nothing, since
# _title_from_url() turns the source URL's hyphens into spaces. Longest
# prefixes are tried first so "MXT-7" isn't shadowed by the generic "M"
# alternative.
_MODEL_CODE_RE = re.compile(
    r"\b(mxt|mx|mt|m)[\s-]?(\d)(?:[\s-](\d{2,3})([a-z])?)?\b", re.IGNORECASE
)


def _extract_model(title: str) -> tuple[str, str] | None:
    match = _MODEL_CODE_RE.search(title)
    if not match:
        return None
    prefix, number, variant, suffix = match.groups()
    model = f"{prefix.upper()}-{number}"
    if variant:
        model += f"-{variant}{(suffix or '').upper()}"
    return MAKE, model


def _title_from_url(url: str) -> str:
    """Listing pages share a generic <title>/<h1>, but the URL slug is the ad's own title."""
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    match = LISTING_LINK_RE.match("/" + slug)
    if not match:
        return unquote(slug)
    return unquote(match.group(2)).replace("-", " ").strip()


def _find_listing_links(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if LISTING_LINK_RE.match(href):
            links.add(urljoin(BASE, href))
    return links


def _page_url(category_url: str, page: int) -> str:
    """Build a category page's URL directly.

    Barnstormers' category pager renders as page-number buttons with no
    "Next" text or rel="next" attribute for a link-following heuristic to
    find (confirmed on the companion Van's RV, Stearman, Waco, Pitts,
    Taylorcraft, Swift, and Beech repos, where that approach silently
    stopped after page 1) - so each page's URL is built from the known
    ?seocategory=<url-encoded-path>&page=<n> pattern instead.
    """
    if page <= 1:
        return category_url
    path = urlparse(category_url).path
    return f"{category_url}?seocategory={quote(path, safe='')}&page={page}"


def _debug_dump_hrefs(html: str, limit: int = 25) -> None:
    soup = BeautifulSoup(html, "lxml")
    hrefs = [a["href"] for a in soup.find_all("a", href=True)]
    interesting = [h for h in hrefs if "classified" in h.lower() or "maule" in h.lower()]
    sample = interesting[:limit] or hrefs[:limit]
    print(f"  [debug] {len(hrefs)} total <a href> on page; sample: {sample}")


def _parse_detail_page(url: str, html: str) -> Listing | None:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    if title:
        title = re.sub(r"\s*[\|\-]\s*Barnstormers.*$", "", title, flags=re.IGNORECASE).strip()
    if not title or GENERIC_SITE_TITLE_SNIPPET in title.lower():
        title = _title_from_url(url)
    if not title:
        return None

    if not _matches_target_models(title):
        return None

    text = soup.get_text(" ", strip=True)

    formatted_title = format_aircraft_title(title, text, _extract_model)
    if not formatted_title:
        return None
    title = formatted_title

    price = extract_price(text)
    location = extract_location(text)
    date_posted = extract_date(text)

    return Listing(
        title=title,
        price=price,
        location=location,
        date_posted=date_posted,
        site=SITE_NAME,
        url=url,
    )


def scrape() -> list[Listing]:
    print(f"[{SITE_NAME}] starting scrape")
    all_links: set[str] = set()

    for category_url in CATEGORY_URLS:
        seen_this_category: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            url = _page_url(category_url, page)
            html = fetch(url)
            if not html:
                break
            links = _find_listing_links(html)
            new_links = links - seen_this_category
            print(f"  [{category_url}] page {page}: {len(links)} links ({len(new_links)} new)")
            if page == 1 and not links:
                _debug_dump_hrefs(html)
            seen_this_category |= links
            if not new_links:
                break
        all_links |= seen_this_category

    print(f"[{SITE_NAME}] {len(all_links)} unique listing URLs found")

    candidate_links = {url for url in all_links if _matches_target_models(_title_from_url(url))}
    print(f"[{SITE_NAME}] {len(candidate_links)} match Maule product names")

    listings: list[Listing] = []
    for url in sorted(candidate_links):
        html = fetch(url)
        if not html:
            continue
        listing = _parse_detail_page(url, html)
        if listing:
            listings.append(listing)

    print(f"[{SITE_NAME}] parsed {len(listings)} listings")
    return listings
