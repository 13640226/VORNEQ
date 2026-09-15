from pathlib import Path

ROOT = Path(__file__).resolve().parent

HTML_FILE = ROOT / "templates" / "index.html"
CSS_FILE = ROOT / "assets" / "css" / "homepage.css"

OLD_IMAGE = "images/vorneq-platform-cover.webp"
NEW_IMAGE = "images/vorneq-hero-integrated.png"

MARKER = "/* FINAL VORNEQ HERO LAYOUT */"

FINAL_CSS = """
/* FINAL VORNEQ HERO LAYOUT */

@media (min-width: 901px) {
  .world-hero {
    align-items: center;
    min-height: 520px;
    padding-bottom: 64px;
  }

  .world-hero__copy {
    display: block;
    grid-column: 1 / span 6;
    align-self: center;
    position: relative;
    z-index: 2;
  }

  .world-hero-cover {
    grid-column: 7 / -1;
    align-self: center;
    justify-self: end;
    width: 100%;
    max-width: 720px;
    margin: 0;
    padding: 0;
    transform: none !important;
  }

  .world-hero-cover__image {
    display: block;
    width: 100%;
    max-width: 720px;
    height: auto;
    object-fit: contain;
    border-radius: 0;
    opacity: 0.96;
  }
}

@media (max-width: 900px) {
  .world-hero {
    display: block;
  }

  .world-hero__copy {
    display: block;
    width: 100%;
  }

  .world-hero-cover {
    width: 100%;
    max-width: none;
    margin-top: 32px;
    transform: none !important;
  }

  .world-hero-cover__image {
    display: block;
    width: 100%;
    max-width: 100%;
    height: auto;
    object-fit: contain;
  }
}
"""

html = HTML_FILE.read_text(encoding="utf-8")

html = html.replace(OLD_IMAGE, NEW_IMAGE)

HTML_FILE.write_text(html, encoding="utf-8")

css = CSS_FILE.read_text(encoding="utf-8")

if MARKER not in css:
    css = css.rstrip() + "\n\n" + FINAL_CSS.strip() + "\n"
    CSS_FILE.write_text(css, encoding="utf-8")

print("Hero updated successfully.")
print(f"HTML: {HTML_FILE}")
print(f"CSS:  {CSS_FILE}")