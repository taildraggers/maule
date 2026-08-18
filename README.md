# Maule

Daily aggregator of Maule aircraft classified listings (M-4, M-5, M-6, M-7,
MX-7, MT-7, etc.) from [Barnstormers.com](https://www.barnstormers.com),
published as a static page (`docs/index.html`) meant to be embedded via
`<iframe>` on taildraggers.com.

Controller.com was evaluated (in the companion [Aeronca](https://github.com/taildraggers/aeronca)
repo) and dropped: its search results are only reachable through an internal
client-side widget (not a plain URL), which a headless browser can't drive
reliably for an unattended daily job.

Note: in the companion [Aviat](https://github.com/taildraggers/aviat),
[CubCrafters](https://github.com/taildraggers/cub-crafters), and
[de Havilland](https://github.com/taildraggers/de-Havilland) repos,
Barnstormers' single-manufacturer category pages turned out to include
unrelated listings mixed in with no distinguishing HTML markup. This repo
is built with the same fix from day one: `scraper/barnstormers.py` filters
by title against a small allowlist of Maule product names
(`TARGET_MODEL_PHRASES`: Maule, M-4 through M-9, MX-7, MXT-7, MT-7) before
publishing.

On top of that brand allowlist, only whole-aircraft-for-sale listings are
kept. Each ad's title must state a model year and match a recognized Maule
model code (see `_extract_model` in `scraper/barnstormers.py`); titles that
read as parts, accessories, services, or raffles are dropped. Every
surviving listing's title is rewritten to a canonical **`YEAR Maule MODEL`**
form (e.g. `2015 Maule M-7-235`), regardless of how the original ad was
worded, so the page reads consistently. A real side effect: ads that never
state a model year in the title can't be reformatted and are dropped too,
even if they're genuine aircraft.

## How it works

- `scraper/barnstormers.py` searches Barnstormers.com's Maule category for
  listings, follows pagination, then keeps only the ones whose URL slug
  matches the Maule product-name allowlist (Barnstormers builds each
  listing's URL slug directly from the ad's own title, so this runs before
  any detail page is fetched). For the matches, it visits each listing's
  detail page to pull out the price, location, and posted date (falling
  back to regex heuristics over the visible text since the site doesn't
  expose structured data). The title is derived from the listing URL's own
  SEO slug, since every detail page shares one generic `<title>`/`<h1>`;
  the final parsed title is checked against the allowlist again as a safety
  net.
- `main.py` runs the scraper, de-duplicates results, sorts them
  newest-posted-first, and renders them into `docs/index.html` titled
  **"Other Maule Ads on the Web"**, with one row per listing: Title (linked
  to the original ad), Price, Location, Date Posted, and Site Posted On.
  Links use `rel="noopener noreferrer"` and the page sets a `no-referrer`
  meta policy, so Barnstormers never sees that the click came from
  taildraggers.com.
- `.github/workflows/daily-scrape.yml` runs the whole thing once a day (13:00 UTC),
  commits the regenerated `docs/index.html` if it changed, and can also be triggered
  manually from the Actions tab (`workflow_dispatch`).

## One-time setup: enable GitHub Pages

This repo publishes `docs/index.html` as a plain static file — GitHub Pages just needs
to be pointed at it once:

1. Go to **Settings → Pages** in this repository.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. GitHub will publish the page at `https://taildraggers.github.io/maule/`
   (may take a minute or two the first time).

Also check **Settings → Actions → General**:
- **Actions permissions**: "Allow all actions and reusable workflows".
- **Workflow permissions**: "Read and write permissions" (needed so the daily
  job can commit the regenerated page back to the repo).

## Embedding on taildraggers.com

```html
<iframe
  src="https://taildraggers.github.io/maule/"
  title="Other Maule Ads on the Web"
  style="width: 100%; height: 800px; border: 0;"
  loading="lazy">
</iframe>
```

## Running locally

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
python main.py
```

This writes/overwrites `docs/index.html`.

## Notes

- If Barnstormers changes its markup or is briefly unreachable, the run logs will
  show a `[warn]`/`[error]` line pointing at what broke rather than failing silently.
- The scraper identifies itself with a browser-like `User-Agent` and adds a short
  delay between requests to be polite to the site.
- Only one Barnstormers category is currently configured
  (`category-20575-Maule.html`). If listings turn out to be split across
  additional categories, add more URLs to `CATEGORY_URLS` in
  `scraper/barnstormers.py`.
