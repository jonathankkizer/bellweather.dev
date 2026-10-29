"""Writes support.html and privacy.html, reusing index.html's nav and footer
so the three pages can't drift apart. Run after editing either page's body
below, or after changing the nav/footer in index.html."""
import re, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
index = (root / "index.html").read_text()
nav = re.search(r'<nav class="nav">.*?</nav>', index, re.S).group(0)
footer = re.search(r'<footer>.*?</footer>', index, re.S).group(0)

def page(slug, title, description, body):
    html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="apple-itunes-app" content="app-id=6799502613">
  <meta name="theme-color" content="#bfd6ef" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#0f2743" media="(prefers-color-scheme: dark)">
  <link rel="canonical" href="https://bellweather.dev/{slug}">
  <link rel="icon" type="image/png" href="/assets/img/favicon.png">
  <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/style.css?v=2">
</head>
<body>

{nav.replace('href="#features"', 'href="/#features"').replace('href="#faq"', 'href="/#faq"').replace('href="./"', 'href="/"').replace('src="assets/', 'src="/assets/')}

{body.strip()}

{footer.replace('href="#press"', 'href="/#press"')}

</body>
</html>
'''
    (root / f"{slug}.html").write_text(html)

page("support", "Bell Weather Support",
     "Help with Bell Weather: where the data comes from, how stations are chosen, and how to get in touch.",
     (root / "tools" / "support.body.html").read_text())
page("privacy", "Bell Weather Privacy Policy",
     "Privacy policy for the Bell Weather app.",
     (root / "tools" / "privacy.body.html").read_text())
