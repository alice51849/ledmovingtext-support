#!/usr/bin/env python3
"""Generate every LED Moving Text support-site page from one locale source."""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source" / "translations.json"
BASE_URL = "https://alice51849.github.io/ledmovingtext-support/"
UPDATED = "2026-08-23"
EMAIL = "hourstag.app@gmail.com"
SOCIAL_IMAGE_URL = f"{BASE_URL}assets/social-card.png"

LOCALES = [
    "ar-SA",
    "bn-BD",
    "ca",
    "zh-Hans",
    "zh-Hant",
    "hr",
    "cs",
    "da",
    "nl-NL",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-US",
    "fi",
    "fr-CA",
    "fr-FR",
    "de-DE",
    "el",
    "gu-IN",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "kn-IN",
    "ko",
    "ms",
    "ml-IN",
    "mr-IN",
    "no",
    "or-IN",
    "pl",
    "pt-BR",
    "pt-PT",
    "pa-IN",
    "ro",
    "ru",
    "sk",
    "sl-SI",
    "es-MX",
    "es-ES",
    "sv",
    "ta-IN",
    "te-IN",
    "th",
    "tr",
    "uk",
    "ur-PK",
    "vi",
]
RTL = {"ar-SA", "he", "ur-PK"}
OG_LOCALES = {
    "ar-SA": "ar_SA",
    "bn-BD": "bn_BD",
    "ca": "ca_ES",
    "zh-Hans": "zh_CN",
    "zh-Hant": "zh_TW",
    "hr": "hr_HR",
    "cs": "cs_CZ",
    "da": "da_DK",
    "nl-NL": "nl_NL",
    "en-AU": "en_AU",
    "en-CA": "en_CA",
    "en-GB": "en_GB",
    "en-US": "en_US",
    "fi": "fi_FI",
    "fr-CA": "fr_CA",
    "fr-FR": "fr_FR",
    "de-DE": "de_DE",
    "el": "el_GR",
    "gu-IN": "gu_IN",
    "he": "he_IL",
    "hi": "hi_IN",
    "hu": "hu_HU",
    "id": "id_ID",
    "it": "it_IT",
    "ja": "ja_JP",
    "kn-IN": "kn_IN",
    "ko": "ko_KR",
    "ms": "ms_MY",
    "ml-IN": "ml_IN",
    "mr-IN": "mr_IN",
    "no": "nb_NO",
    "or-IN": "or_IN",
    "pl": "pl_PL",
    "pt-BR": "pt_BR",
    "pt-PT": "pt_PT",
    "pa-IN": "pa_IN",
    "ro": "ro_RO",
    "ru": "ru_RU",
    "sk": "sk_SK",
    "sl-SI": "sl_SI",
    "es-MX": "es_MX",
    "es-ES": "es_ES",
    "sv": "sv_SE",
    "ta-IN": "ta_IN",
    "te-IN": "te_IN",
    "th": "th_TH",
    "tr": "tr_TR",
    "uk": "uk_UA",
    "ur-PK": "ur_PK",
    "vi": "vi_VN",
}
PAGES = ("index", "support", "privacy")
PAGE_FILES = {
    "index": "index.html",
    "support": "support.html",
    "privacy": "privacy.html",
}


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def load_translations() -> dict[str, dict[str, Any]]:
    try:
        document = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"translation source is unreadable: {error}") from error
    if document.get("schema_version") != 1:
        raise SystemExit("translation source must use schema_version 1")
    if document.get("source_locale") != "en-US":
        raise SystemExit("source_locale must be en-US")
    translations = document.get("locales")
    if not isinstance(translations, dict):
        raise SystemExit("translation source has no locales object")
    actual = set(translations)
    expected = set(LOCALES)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        extra = ", ".join(sorted(actual - expected)) or "none"
        raise SystemExit(f"locale set mismatch; missing: {missing}; extra: {extra}")
    return translations


def page_url(locale: str | None, page: str) -> str:
    prefix = f"{locale}/" if locale else ""
    if page == "index":
        return f"{BASE_URL}{prefix}"
    return f"{BASE_URL}{prefix}{PAGE_FILES[page]}"


def output_path(locale: str | None, page: str) -> pathlib.Path:
    if locale:
        return ROOT / locale / PAGE_FILES[page]
    return ROOT / PAGE_FILES[page]


def hreflang_markup(page: str) -> str:
    rows = [
        f'<link rel="alternate" hreflang="{code}" href="{page_url(code, page)}">'
        for code in LOCALES
    ]
    rows.append(
        f'<link rel="alternate" hreflang="x-default" href="{page_url(None, page)}">'
    )
    return "\n".join(rows)


def nav_markup(
    locale: str | None, current: str, nav_labels: list[str]
) -> str:
    items = []
    for page, label in zip(PAGES, nav_labels, strict=True):
        current_attribute = ' aria-current="page"' if page == current else ""
        items.append(
            f'<a href="{page_url(locale, page)}"{current_attribute}>{escape(label)}</a>'
        )
    return "\n".join(items)


def language_markup(
    translations: dict[str, dict[str, Any]], current_locale: str, page: str
) -> str:
    links = []
    for code in LOCALES:
        current_attribute = ' aria-current="page"' if code == current_locale else ""
        links.append(
            f'<li><a hreflang="{code}" lang="{code}" dir="auto" '
            f'href="{page_url(code, page)}"{current_attribute}>'
            f'{escape(translations[code]["language_name"])}</a></li>'
        )
    return "\n".join(links)


def contact_markup(block: dict[str, Any]) -> str:
    return f"""
<section class="card contact-card" aria-labelledby="contact-title">
  <h2 id="contact-title">{escape(block["contact_heading"])}</h2>
  <p>{escape(block["contact_body"])}</p>
  <address class="contact-actions">
    <a class="mail-button" href="mailto:{EMAIL}">{escape(block["contact_button"])}</a>
    <a class="mail-address" href="mailto:{EMAIL}" dir="ltr">{EMAIL}</a>
  </address>
</section>""".strip()


def home_markup(locale_data: dict[str, Any]) -> str:
    block = locale_data["home"]
    access_title, access_body = locale_data["support"]["faqs"][7]
    cards = "\n".join(
        (
            '<li><article class="card">'
            f"<h3>{escape(title)}</h3>"
            f"<p>{escape(body)}</p>"
            "</article></li>"
        )
        for title, body in block["features"]
    )
    return f"""
<section class="access-card" aria-labelledby="access-title">
  <div class="access-signal" aria-hidden="true">
    <span></span><span></span><span></span><span></span><span></span>
  </div>
  <div>
    <h2 id="access-title">{escape(access_title)}</h2>
    <p>{escape(access_body)}</p>
  </div>
</section>
<section aria-labelledby="features-title">
  <h2 class="section-heading" id="features-title">{escape(block["features_heading"])}</h2>
  <ul class="feature-grid" role="list">
    {cards}
  </ul>
</section>
<section class="card promise">
  <h2>{escape(block["device_heading"])}</h2>
  <p>{escape(block["device_body"])}</p>
</section>""".strip()


def support_markup(locale_data: dict[str, Any]) -> str:
    block = locale_data["support"]
    entries = "\n".join(
        (
            '<details class="faq">'
            f"<summary>{escape(question)}</summary>"
            f"<p>{escape(answer)}</p>"
            "</details>"
        )
        for question, answer in block["faqs"]
    )
    return f"""
<section aria-labelledby="faq-title">
  <h2 class="section-heading" id="faq-title">{escape(block["faq_heading"])}</h2>
  <div class="faq-list">
    {entries}
  </div>
</section>
{contact_markup(block)}""".strip()


def privacy_markup(locale_data: dict[str, Any]) -> str:
    block = locale_data["privacy"]
    sections = "\n".join(
        (
            '<section class="card">'
            f"<h2>{escape(title)}</h2>"
            f"<p>{escape(body)}</p>"
            "</section>"
        )
        for title, body in block["sections"]
    )
    return f"""
<div class="policy-list">
  {sections}
</div>
{contact_markup(block)}""".strip()


def render_page(
    translations: dict[str, dict[str, Any]],
    locale: str | None,
    page: str,
) -> str:
    content_locale = locale or "en-US"
    locale_data = translations[content_locale]
    block = locale_data["home" if page == "index" else page]
    direction = "rtl" if content_locale in RTL else "ltr"
    canonical = page_url(locale, page)
    title = f'{block["title"]} — LED Moving Text'
    body = {
        "index": home_markup,
        "support": support_markup,
        "privacy": privacy_markup,
    }[page](locale_data)
    updated = ""
    if page == "privacy":
        updated = (
            f'\n        <p class="updated">{escape(block["updated"])}: '
            f'<time datetime="{UPDATED}" dir="ltr">{UPDATED}</time></p>'
        )
    return f"""<!doctype html>
<!-- Generated by scripts/generate_site.py. Do not edit this file directly. -->
<html lang="{content_locale}" dir="{direction}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#fcf9fd" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#130e1b" media="(prefers-color-scheme: dark)">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'none'; connect-src 'none'; font-src 'none'; object-src 'none'; frame-src 'none'; media-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(block["lead"])}">
  <link rel="canonical" href="{canonical}">
  {hreflang_markup(page)}
  <link rel="icon" href="/ledmovingtext-support/assets/site-icon.png" type="image/png" sizes="256x256">
  <link rel="apple-touch-icon" href="/ledmovingtext-support/assets/site-icon.png" sizes="256x256">
  <link rel="stylesheet" href="/ledmovingtext-support/assets/site.css">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="LED Moving Text">
  <meta property="og:locale" content="{OG_LOCALES[content_locale]}">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(block["lead"])}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{SOCIAL_IMAGE_URL}">
  <meta property="og:image:secure_url" content="{SOCIAL_IMAGE_URL}">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="LED Moving Text">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(block["lead"])}">
  <meta name="twitter:image" content="{SOCIAL_IMAGE_URL}">
  <meta name="twitter:image:alt" content="LED Moving Text">
</head>
<body>
  <a class="skip-link" href="#main">{escape(locale_data["skip_link"])}</a>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="{page_url(locale, "index")}" dir="ltr">
        <img src="/ledmovingtext-support/assets/brand-mark.png" width="640" height="320" alt="">
        <span>LED Moving Text</span>
      </a>
      <nav class="primary-nav" aria-label="{escape(locale_data["navigation_label"])}">
        {nav_markup(locale, page, locale_data["nav"])}
      </nav>
      <details class="language-picker">
        <summary>{escape(locale_data["language_label"])}</summary>
        <ul class="language-list" role="list">
          {language_markup(translations, content_locale, page)}
        </ul>
      </details>
    </div>
  </header>
  <main class="page-shell" id="main" tabindex="-1">
    <header class="hero">
      <div>
        <p class="eyebrow">LED Moving Text</p>
        <h1>{escape(block["title"])}</h1>
        <p class="lead">{escape(block["lead"])}</p>{updated}
      </div>
      <div class="hero-art" aria-hidden="true">
        <span class="signal-track signal-track-a"></span>
        <span class="signal-track signal-track-b"></span>
        <img class="hero-mark" src="/ledmovingtext-support/assets/brand-mark.png"
             width="640" height="320" alt="">
      </div>
    </header>
    {body}
  </main>
  <footer class="site-footer">
    <div class="footer-inner">
      <p>{escape(locale_data["footer"])}</p>
      <address><a href="mailto:{EMAIL}" dir="ltr">{EMAIL}</a></address>
    </div>
  </footer>
</body>
</html>
"""


def render_sitemap() -> str:
    urls = [page_url(None, page) for page in PAGES]
    urls.extend(page_url(locale, page) for locale in LOCALES for page in PAGES)
    rows = "\n".join(
        f"  <url><loc>{escape(url)}</loc><lastmod>{UPDATED}</lastmod></url>"
        for url in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{rows}\n"
        "</urlset>\n"
    )


def expected_outputs(
    translations: dict[str, dict[str, Any]]
) -> dict[pathlib.Path, str]:
    outputs: dict[pathlib.Path, str] = {}
    for page in PAGES:
        outputs[output_path(None, page)] = render_page(translations, None, page)
    for locale in LOCALES:
        for page in PAGES:
            outputs[output_path(locale, page)] = render_page(
                translations, locale, page
            )
    outputs[ROOT / "sitemap.xml"] = render_sitemap()
    outputs[ROOT / "robots.txt"] = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {BASE_URL}sitemap.xml\n"
    )
    return outputs


def write_outputs(outputs: dict[pathlib.Path, str]) -> None:
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"Generated {3 * (len(LOCALES) + 1)} HTML pages "
        f"for {len(LOCALES)} locales."
    )


def check_outputs(outputs: dict[pathlib.Path, str]) -> None:
    failures = []
    for path, expected in outputs.items():
        if not path.is_file():
            failures.append(f"missing {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            failures.append(f"stale {path.relative_to(ROOT)}")
    expected_html = {
        path.resolve() for path in outputs if path.suffix.lower() == ".html"
    }
    actual_html = {path.resolve() for path in ROOT.rglob("*.html")}
    for path in sorted(actual_html - expected_html):
        failures.append(f"unexpected {path.relative_to(ROOT.resolve())}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)
    print(
        f"PASS generator check: {len(expected_html)} HTML pages are deterministic."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated files without changing them",
    )
    arguments = parser.parse_args()
    translations = load_translations()
    outputs = expected_outputs(translations)
    if arguments.check:
        check_outputs(outputs)
    else:
        write_outputs(outputs)


if __name__ == "__main__":
    main()
