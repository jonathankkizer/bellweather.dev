# bellweather.dev

The website for [Bell Weather](https://apps.apple.com/app/id6799502613). Static HTML and CSS, served by GitHub Pages. The pages in the repo are written by hand; the city pages under `/weather/` are generated when the site deploys.

- `index.html`, `assets/style.css`: the page
- `assets/img/`: web-sized screenshots and icons, made from the app repo's `screenshots/raw/` and `App/dark-hill-icon.icon` (rendered with Icon Composer's `ictool`)
- `tools/cities.py`: builds the whole site into `_site/`, writing a page per city from the digest the app repo publishes at `data.bellweather.dev/site/v1/cities.json`. `.github/workflows/site.yml` runs it twice a day and on every push to main, then deploys
- `press/`: full-size icon and screenshot zip for the press kit
- `tools/og.html`: template for `assets/img/og.png`, the 1200×630 link preview. Screenshot it at that size to regenerate.

Colors come from `BellWeatherCore/Sky.swift` in the app, so the page matches the app's ground in light and dark mode.

To preview the hand-written pages: `python3 -m http.server` and open http://localhost:8000.

To preview everything, city pages included:

    curl --compressed -o /tmp/digest.json https://data.bellweather.dev/site/v1/cities.json
    python3 tools/cities.py --digest /tmp/digest.json --out _site
    python3 -m http.server -d _site
