#!/usr/bin/env python3
"""Builds the whole site into an output directory, city pages included.

  python3 tools/cities.py --digest digest.json --out _site

The static pages (index, support, privacy, assets, press) are copied as they
are. Everything under /weather/ is written from the digest, a JSON file the
app repo's `site-digest` tool publishes each day. That tool runs the same
statistics as the app and chooses the same words; this script does no
arithmetic about the weather. It formats numbers and lays out pages.

To preview: build, then `python3 -m http.server -d _site`.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://bellweather.dev"
STORE = "https://apps.apple.com/app/apple-store/id6799502613?pt=118929077&amp;ct=city&amp;mt=8"
STATIC = ["index.html", "support.html", "privacy.html", "CNAME", "assets", "press"]
WINDOWS = ["30", "60", "90"]
HERO_WINDOW = "90"
ORDER = ["avgt", "maxt", "mint", "pcpn", "snow"]

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# The app's two ramps (BellWeatherCore/Ramp.swift), light and dark.
RAMPS = {
    "temperature": [(0.00, 0x0A3D6B, 0x0E5A9E), (0.17, 0x007AFF, 0x0A84FF), (0.33, 0x7FCBEA, 0x4FA9CE),
                    (0.50, 0xE9EAEC, 0x3A3A3C), (0.67, 0xFFB340, 0xD9820E), (0.83, 0xFF3B30, 0xFF453A),
                    (1.00, 0x8E1D12, 0xC22B1D)],
    "moisture": [(0.00, 0x6E4A1E, 0x8A6A3C), (0.17, 0xA2845E, 0xAC8E67), (0.33, 0xD8C6A8, 0x8A7A5E),
                 (0.50, 0xE9EAEC, 0x3A3A3C), (0.67, 0x7FCBEA, 0x4FA9CE), (0.83, 0x007AFF, 0x0A84FF),
                 (1.00, 0x3634A3, 0x5E5CE6)],
}

esc = html.escape


# ---------- Formatting ----------

def number(value, digits):
    text = f"{abs(value):.{digits}f}"
    negative = value < 0 and float(text) != 0
    return ("−" if negative else "") + text


def reading(value, element, prose=False):
    """A value with its unit, as the app prints it: 71.3°F, 4.12 in.

    In a sentence the unit is spelled out, or "22.06 in in 1983" happens.
    """
    if element in ("avgt", "maxt", "mint"):
        return number(value, 1) + "°F"
    text = number(value, 2 if element == "pcpn" else 1)
    if not prose:
        return text + " in"
    return text + (" inch" if float(text) == 1 else " inches")


def departure(m, element, prose=False):
    """The app's departure phrase: "1.4°F above average"."""
    diff = m["value"] - m["mean"]
    magnitude = f"{abs(diff):.1f}"
    if magnitude == "0.0":
        return "at the average"
    unit = "°F" if element in ("avgt", "maxt", "mint") else " inches" if prose else " in"
    return f"{magnitude}{unit} {'above' if diff > 0 else 'below'} average"


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def percentile(m):
    return ordinal(max(1, min(99, round(m["percentile"]))))


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def short_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}"


def miles(km):
    return max(1, round(km * 0.621371))


def listed(items):
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def ramp_colors(kind, p):
    """Light and dark hex for a percentile on one of the app's ramps."""
    stops = RAMPS[kind]
    t = max(0.0, min(1.0, p / 100))
    for (t0, l0, d0), (t1, l1, d1) in zip(stops, stops[1:]):
        if t <= t1:
            f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            def mix(a, b):
                out = 0
                for shift in (16, 8, 0):
                    x, y = (a >> shift) & 0xFF, (b >> shift) & 0xFF
                    out |= round(x + (y - x) * f) << shift
                return f"#{out:06x}"
            return mix(l0, l1), mix(d0, d1)
    return f"#{stops[-1][1]:06x}", f"#{stops[-1][2]:06x}"


def swatch(words, element, m):
    light, dark = ramp_colors(words[element]["ramp"], m["percentile"])
    return f'<span class="dot" style="--l:{light};--d:{dark}"></span>'


# ---------- Sentences ----------

def stat_line(words, element, m):
    """The line under the app's verdict: departure, then the count."""
    if m.get("floor"):
        return m["floor"]
    w = words[element]
    phrase = departure(m, element)
    return f"{phrase[0].upper()}{phrase[1:]} · {m['above']} of {m['count']} years {w['more']}"


def summary(words, element, m, station):
    """One plain paragraph about a reading."""
    w = words[element]
    days = f"The {m['window']} days ending {short_date(m['end'])}"
    if element in ("avgt", "maxt", "mint"):
        first = f"{days} averaged {reading(m['value'], element)} at {station}"
        if element != "avgt":
            first = (f"{days} had an average daily {'high' if element == 'maxt' else 'low'} of "
                     f"{reading(m['value'], element)}")
    else:
        first = f"{days} brought {reading(m['value'], element, prose=True)} of {w['noun'].lower()}"
    if m.get("floor"):
        return f"{days} brought no {w['noun'].lower()}. {m['floor']}."
    first = f"{first}, {departure(m, element, prose=True)}. "

    def were(word):
        # "were warmer", but "had less snow".
        return f"had {word}" if word.startswith("less ") else f"were {word}"
    if m["above"] == 0 or m["below"] == 0:
        return first + f"None of the other {m['count']} years {were(w['more'] if m['above'] == 0 else w['less'])}."
    return first + f"{m['above']} of {m['count']} years {were(w['more'])}, and {m['below']} {were(w['less'])}."


def meta_description(city, words, m):
    return (f"The last {m['window']} days in {city['city']} averaged {reading(m['value'], 'avgt')}, "
            f"{departure(m, 'avgt')}: the {percentile(m)} percentile of {m['count']} years on record. "
            f"Updated daily from NOAA station records.")


# ---------- The year strip ----------

def strip(words, element, m):
    """Every year on record along one axis, this year marked.

    The same picture as the app's top scale, without the scrubbing: a tick
    per past year, a dot for this one, a notch at the average.
    """
    years = m["years"]
    current_year = int(m["end"][:4])
    values = [v for _, v in years]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    width, left, right = 640, 10, 630

    def x(v):
        return left + (v - lo) / span * (right - left)

    ticks = "".join(
        f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="14" y2="38"/>'
        for y, v in years if int(y) != current_year)
    light, dark = ramp_colors(words[element]["ramp"], m["percentile"])
    cx, mx = x(m["value"]), x(m["mean"])
    label_anchor = "start" if cx < 60 else "end" if cx > width - 60 else "middle"
    label = (f"{current_year}: {reading(m['value'], element)}. Lowest of {m['count']} earlier years "
             f"{reading(m['lowest']['value'], element)} in {m['lowest']['year']}, highest "
             f"{reading(m['highest']['value'], element)} in {m['highest']['year']}.")
    return f'''<figure class="strip">
  <svg viewBox="0 0 {width} 62" role="img" aria-label="{esc(label)}">
    <g class="ticks">{ticks}</g>
    <path class="mean" d="M{mx:.1f} 40 l-5 8 h10 z"/>
    <circle class="now" cx="{cx:.1f}" cy="26" r="8" style="--l:{light};--d:{dark}"/>
    <text class="year" x="{cx:.1f}" y="9" text-anchor="{label_anchor}">{current_year}</text>
    <text class="avg" x="{min(max(mx, 30), width - 30):.1f}" y="60" text-anchor="middle">average</text>
  </svg>
  <figcaption>
    <span>{reading(m['lowest']['value'], element)}<small>{m['lowest']['year']}</small></span>
    <span>{reading(m['highest']['value'], element)}<small>{m['highest']['year']}</small></span>
  </figcaption>
</figure>'''


# ---------- Page shell ----------

def shell_parts():
    index = (ROOT / "index.html").read_text()
    nav = re.search(r'<nav class="nav">.*?</nav>', index, re.S).group(0)
    footer = re.search(r'<footer>.*?</footer>', index, re.S).group(0)
    nav = (nav.replace('href="#features"', 'href="/#features"').replace('href="#faq"', 'href="/#faq"')
           .replace('href="./"', 'href="/"').replace('src="assets/', 'src="/assets/'))
    return nav, footer.replace('href="#press"', 'href="/#press"')


def page(path, title, description, body, nav, footer):
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="apple-itunes-app" content="app-id=6799502613">
  <meta name="theme-color" content="#bfd6ef" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#0f2743" media="(prefers-color-scheme: dark)">
  <link rel="canonical" href="{SITE}{path}">
  <link rel="icon" type="image/png" href="/assets/img/favicon.png">
  <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/style.css?v=3">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE}{path}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:image" content="{SITE}/assets/img/og.png">
  <meta name="twitter:card" content="summary_large_image">
</head>
<body>

{nav}

{body.strip()}

{footer}

</body>
</html>
'''


def cta():
    return f'''<section class="cta">
  <div class="wrap">
    <img class="icon" src="/assets/img/icon.png" width="88" height="88" alt="">
    <h2>Look up your own town</h2>
    <p>Bell Weather does this for any town in the United States, with each day drawn against the station's history, a national map and a widget. Free on iPhone and iPad.</p>
    <a class="badge" href="{STORE}"><img src="/assets/img/app-store-badge.svg" alt="Download on the App Store" width="162" height="54"></a>
  </div>
</section>'''


# ---------- Pages ----------

def metrics_of(city, window):
    """The city's readings for one window, in display order, with something to show."""
    out = []
    for element in ORDER:
        m = city["metrics"].get(element, {}).get(window)
        if m and not m["nothing"]:
            out.append((element, dict(m, window=window)))
    return out


def city_path(city):
    return f"/weather/{city['slug']}"


def city_row(words, city, with_state=False):
    m = city["metrics"]["avgt"][HERO_WINDOW]
    state = f' <small>{city["state"]}</small>' if with_state else ""
    return (f'<li><a href="{city_path(city)}">{swatch(words, "avgt", m)}'
            f'<span class="name">{esc(city["city"])}{state}</span>'
            f'<span class="says">{esc(m["short"])}</span>'
            f'<span class="pct">{percentile(m)}</span></a></li>')


def city_page(city, words, neighbours, nav, footer):
    name, state = city["city"], STATES[city["state"]]
    hero = dict(city["metrics"]["avgt"][HERO_WINDOW], window=HERO_WINDOW)
    station = city["station"]

    rows = []
    for element in ORDER:
        cells = []
        for window in WINDOWS:
            m = city["metrics"].get(element, {}).get(window)
            if not m or m["nothing"]:
                cells.append('<td class="none">Nothing to compare</td>')
            else:
                detail = "" if m.get("floor") else f'<small>{percentile(m)} percentile</small>'
                cells.append(f'<td><span class="cell">{swatch(words, element, m)}'
                             f'<span>{esc(m["short"])}{detail}</span></span></td>')
        if any('class="none"' not in c for c in cells):
            rows.append(f'<tr><th scope="row">{esc(words[element]["title"])}</th>{"".join(cells)}</tr>')

    sections = []
    for element, m in metrics_of(city, HERO_WINDOW):
        w = words[element]
        facts = (f'{w["highest"].capitalize()} on record: '
                 f'{reading(m["highest"]["value"], element, prose=True)} in {m["highest"]["year"]}.')
        # A total's floor is zero, shared by many years; naming one is noise.
        if m["lowest"]["value"] > 0 or element in ("avgt", "maxt", "mint"):
            facts += (f' {w["lowest"].capitalize()}: '
                      f'{reading(m["lowest"]["value"], element, prose=True)} in {m["lowest"]["year"]}.')
        # The average temperature's sentence is the page's opening line.
        text = facts if element == "avgt" else summary(words, element, m, station) + " " + facts
        sections.append(f'''<section class="metric">
  <h2>{esc(w["title"])}</h2>
  <p class="verdict">{esc(m["verdict"])}</p>
  <p class="stat">{esc(stat_line(words, element, m))}</p>
  {strip(words, element, m)}
  <p>{esc(text)}</p>
</section>''')

    notes = [f"Take the last 90 days at the {station} station and average them. Do the same for the same "
             f"90 days in every other year the station has on record, back to {city['since']}. The "
             f"percentile is where this year lands among them. The 50th is the middle, and the 99th is "
             f"{words['avgt']['more']} than nearly every year.",
             "The numbers come from NOAA's daily station records, through the Regional Climate Centers. "
             "They are updated each day, and the last day or two can still be missing."]
    if city["distanceKm"] >= 16:
        notes.append(f"The station is about {miles(city['distanceKm'])} miles from the middle of {name}. "
                     f"It is the nearest one with a long, mostly complete record.")
    if city["alsoServes"]:
        others = [c.rsplit(",", 1)[0] for c in city["alsoServes"]]
        notes.append(f"It is also the nearest long record for {listed(others)}.")

    nearby = "".join(city_row(words, c) for c in neighbours)
    elsewhere = f'<h2>Elsewhere in {esc(state)}</h2><ul class="cities">{nearby}</ul>' if nearby else ""
    title = f"Is the weather in {name} normal right now? · Bell Weather"
    body = f'''<header class="city-head">
  <div class="wrap">
    <p class="crumbs"><a href="/weather/">Cities</a> › <a href="/weather/{city["state"].lower()}/">{esc(state)}</a></p>
    <h1>Is the weather in {esc(name)} normal right now?</h1>
    <div class="read">
      <p class="numeral" aria-label="{percentile(hero)} percentile">{percentile(hero)[:-2]}<sup>{percentile(hero)[-2:]}</sup><small>percentile</small></p>
      <div>
        <p class="verdict">{esc(hero["verdict"])}</p>
        <p class="lede">{esc(summary(words, "avgt", hero, station))}</p>
      </div>
    </div>
    <p class="fine">Through {long_date(hero["end"])} · {esc(station)} station · Records since {city["since"]}</p>
  </div>
</header>

<main class="city">
  <div class="wrap">
    <section class="glance">
      <h2>At a glance</h2>
      <div class="scroll"><table>
        <thead><tr><th></th><th scope="col">30 days</th><th scope="col">60 days</th><th scope="col">90 days</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table></div>
    </section>

    <h2 class="group">The last 90 days against every year on record</h2>
    {"".join(sections)}

    <p class="in-app">The app draws each of these 90 days against the station's history, and lets you change the stretch and the years it is compared with. <a href="{STORE}">Bell Weather on the App Store</a></p>

    <section class="notes">
      <h2>How this is worked out</h2>
      {"".join(f"<p>{esc(n)}</p>" for n in notes)}
    </section>

    <section class="more">
      {elsewhere}
      <p><a href="/weather/">All cities</a></p>
    </section>
  </div>
</main>

{cta()}'''
    return page(city_path(city), title, meta_description(city, words, hero), body, nav, footer)


def state_page(code, cities, words, nav, footer):
    state = STATES[code]
    body = f'''<header class="city-head">
  <div class="wrap">
    <p class="crumbs"><a href="/weather/">Cities</a></p>
    <h1>Is the weather in {esc(state)} normal right now?</h1>
    <p class="lede">Average temperature over the last 90 days in {esc(state)}'s larger cities, each compared with every year its weather station has on record.</p>
  </div>
</header>

<main class="city">
  <div class="wrap">
    <section class="more">
      <ul class="cities">{"".join(city_row(words, c) for c in cities)}</ul>
      <p><a href="/weather/">All cities</a></p>
    </section>
  </div>
</main>

{cta()}'''
    names = listed([c["city"] for c in cities[:3]])
    return page(f"/weather/{code.lower()}/", f"Is the weather in {state} normal right now? · Bell Weather",
                f"The last 90 days in {names}, compared with every year on record. "
                f"Updated daily from NOAA station records.", body, nav, footer)


def index_page(cities, by_state, words, nav, footer, generated):
    def distance(c):
        return abs(c["metrics"]["avgt"][HERO_WINDOW]["percentile"] - 50)
    extremes = sorted(cities, key=lambda c: (-distance(c), -c["population"]))[:12]
    states = "".join(
        f'<section class="state"><h3><a href="/weather/{code.lower()}/">{esc(STATES[code])}</a></h3>'
        f'<ul class="cities">{"".join(city_row(words, c) for c in by_state[code])}</ul></section>'
        for code in sorted(by_state, key=lambda s: STATES[s]))
    body = f'''<header class="city-head">
  <div class="wrap">
    <h1>Is this weather normal?</h1>
    <p class="lede">The last 90 days in {len(cities)} American cities, each compared with the same 90 days in every year its weather station has on record.</p>
    <p class="fine">Updated {long_date(generated)}</p>
  </div>
</header>

<main class="city">
  <div class="wrap">
    <section class="more">
      <h2>Furthest from normal</h2>
      <ul class="cities">{"".join(city_row(words, c, with_state=True) for c in extremes)}</ul>
    </section>
    <section class="more all">
      <h2>By state</h2>
      {states}
    </section>
  </div>
</main>

{cta()}'''
    return page("/weather/", "Is this weather normal? 90 days in US cities, against every year on record · Bell Weather",
                "Whether the last 90 days have been warmer, cooler, wetter or drier than normal in "
                f"{len(cities)} US cities, from NOAA station records going back a century or more. Updated daily.",
                body, nav, footer)


# ---------- Build ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--minimum", type=int, default=100,
                        help="refuse to build from a digest with fewer cities than this")
    args = parser.parse_args()

    digest = json.loads(pathlib.Path(args.digest).read_text())
    words, generated = digest["elements"], digest["generated"]
    cities = [c for c in digest["cities"] if HERO_WINDOW in c["metrics"].get("avgt", {})]
    if len(cities) < args.minimum:
        raise SystemExit(f"digest has only {len(cities)} usable cities; not publishing")
    cities.sort(key=lambda c: -c["population"])

    out = pathlib.Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in STATIC:
        src = ROOT / name
        (shutil.copytree if src.is_dir() else shutil.copy)(src, out / name)
    (out / ".nojekyll").write_text("")

    nav, footer = shell_parts()
    by_state = {}
    for c in cities:
        by_state.setdefault(c["state"], []).append(c)

    urls = ["/", "/support", "/privacy", "/weather/"]
    weather = out / "weather"
    weather.mkdir()
    (weather / "index.html").write_text(index_page(cities, by_state, words, nav, footer, generated))
    for code, group in by_state.items():
        folder = weather / code.lower()
        folder.mkdir()
        (folder / "index.html").write_text(state_page(code, group, words, nav, footer))
        urls.append(f"/weather/{code.lower()}/")
        for c in group:
            others = [o for o in group if o is not c][:8]
            target = out / (city_path(c).lstrip("/") + ".html")
            target.write_text(city_page(c, words, others, nav, footer))
            urls.append(city_path(c))

    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{generated}</lastmod></url>\n" for u in urls)
        + "</urlset>\n")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"{len(cities)} city pages, {len(by_state)} states, {len(urls)} URLs in {out}")


if __name__ == "__main__":
    main()
