# bellweather.dev

The website for [Bell Weather](https://apps.apple.com/app/id6799502613). Plain static HTML and CSS, no build step, served by GitHub Pages.

- `index.html`, `assets/style.css`: the page
- `assets/img/`: web-sized screenshots and icons, made from the app repo's `screenshots/raw/` and `App/dark-hill-icon.icon` (rendered with Icon Composer's `ictool`)
- `press/`: full-size icon and screenshot zip for the press kit
- `tools/og.html`: template for `assets/img/og.png`, the 1200×630 link preview. Screenshot it at that size to regenerate.

Colors come from `BellWeatherCore/Sky.swift` in the app, so the page matches the app's ground in light and dark mode.

To preview locally: `python3 -m http.server` and open http://localhost:8000.
