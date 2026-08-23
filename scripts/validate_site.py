#!/usr/bin/env python3
"""Fail-closed validation for the generated LED Moving Text website."""

from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import re
import struct
import sys
import urllib.parse
from html.parser import HTMLParser
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from generate_site import (  # noqa: E402
    BASE_URL,
    EMAIL,
    LOCALES,
    OG_LOCALES,
    PAGE_FILES,
    PAGES,
    ROOT,
    RTL,
    SOCIAL_IMAGE_URL,
    expected_outputs,
    load_translations,
    page_url,
    render_sitemap,
)

EXPECTED_PAGE_COUNT = 3 * (len(LOCALES) + 1)
EXPECTED_FEATURES = 6
EXPECTED_FAQS = 9
EXPECTED_PRIVACY_SECTIONS = 8
ENGLISH_VARIANTS = {"en-AU", "en-CA", "en-GB", "en-US"}
REQUIRED_CSP = (
    "default-src 'self'; script-src 'none'; connect-src 'none'; "
    "font-src 'none'; object-src 'none'; frame-src 'none'; "
    "media-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; "
    "form-action 'none'"
)
PLACEHOLDER = re.compile(
    r"\b(?:TODO|TBD|FIXME)\b|"
    r"(?i:\b(?:placeholder|lorem ipsum|untranslated)\b)|"
    r"\{\{[^}]+\}\}|\?\?\?"
)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
TRACKING_PATTERN = re.compile(
    r"google-analytics|googletagmanager|gtag\s*\(|facebook(?:\.net| pixel)|"
    r"mixpanel|segment\.com|hotjar|doubleclick|localStorage|document\.cookie|"
    r"fingerprintjs",
    re.IGNORECASE,
)
BANNED_CLAIMS = re.compile(
    r"\b(?:millions? of downloads?|five[- ]star|5[- ]star|award[- ]winning|"
    r"number one|no\.?\s*1|best (?:app|led)|guaranteed results?|"
    r"android|windows app|macos app|coming soon)\b",
    re.IGNORECASE,
)
LEGACY_TIER = re.compile(r"(?<![\w])Pro(?![\w])", re.UNICODE)
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
EXPECTED_LOCALE_KEYS = {
    "language_name",
    "language_label",
    "navigation_label",
    "skip_link",
    "nav",
    "footer",
    "home",
    "support",
    "privacy",
}
EXPECTED_HOME_KEYS = {
    "title",
    "lead",
    "features_heading",
    "features",
    "device_heading",
    "device_body",
}
EXPECTED_SUPPORT_KEYS = {
    "title",
    "lead",
    "faq_heading",
    "faqs",
    "contact_heading",
    "contact_body",
    "contact_button",
}
EXPECTED_PRIVACY_KEYS = {
    "title",
    "lead",
    "updated",
    "sections",
    "contact_heading",
    "contact_body",
    "contact_button",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.stack: list[str] = []
        self.doctype = False
        self.html_attrs: dict[str, str] = {}
        self.canonicals: list[str] = []
        self.alternates: dict[str, list[str]] = collections.defaultdict(list)
        self.hrefs: list[str] = []
        self.sources: list[str] = []
        self.ids: set[str] = set()
        self.nav_links: list[str] = []
        self.language_links: dict[str, str] = {}
        self.nav_depth = 0
        self.title_depth = 0
        self.title_parts: list[str] = []
        self.metas: dict[str, list[str]] = collections.defaultdict(list)
        self.forbidden_tags: list[str] = []
        self.tag_counts: collections.Counter[str] = collections.Counter()
        self.images: list[dict[str, str]] = []
        self.main_attrs: list[dict[str, str]] = []
        self.language_list_count = 0
        self.language_currents: dict[str, str] = {}

    def handle_decl(self, declaration: str) -> None:
        if declaration.lower() == "doctype html":
            self.doctype = True

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        attrs = {key: value or "" for key, value in attributes}
        self.tag_counts[tag] += 1
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        if "style" in attrs:
            self.errors.append(f"inline style on <{tag}>")
        for key in attrs:
            if key.lower().startswith("on"):
                self.errors.append(f"inline event handler {key} on <{tag}>")
        if tag == "html":
            self.html_attrs = attrs
        if tag == "main":
            self.main_attrs.append(attrs)
        if tag == "ul" and "language-list" in attrs.get("class", "").split():
            self.language_list_count += 1
        if "id" in attrs:
            if attrs["id"] in self.ids:
                self.errors.append(f"duplicate id {attrs['id']}")
            self.ids.add(attrs["id"])
        if tag == "title":
            self.title_depth += 1
        if tag == "nav":
            self.nav_depth += 1
        if tag == "a":
            href = attrs.get("href", "")
            self.hrefs.append(href)
            if self.nav_depth:
                self.nav_links.append(href)
            hreflang = attrs.get("hreflang")
            if hreflang:
                self.language_links[hreflang] = href
                self.language_currents[hreflang] = attrs.get("aria-current", "")
        if tag == "img":
            self.images.append(attrs)
        if tag in {"img", "script", "iframe", "source", "video", "audio"}:
            source = attrs.get("src")
            if source:
                self.sources.append(source)
        if tag in {
            "script",
            "iframe",
            "object",
            "embed",
            "form",
            "input",
            "select",
            "textarea",
        }:
            self.forbidden_tags.append(tag)
        if tag == "link":
            relation = set(attrs.get("rel", "").lower().split())
            href = attrs.get("href", "")
            if "canonical" in relation:
                self.canonicals.append(href)
            if "alternate" in relation and "hreflang" in attrs:
                self.alternates[attrs["hreflang"]].append(href)
            if relation & {
                "stylesheet",
                "icon",
                "apple-touch-icon",
                "preload",
                "modulepreload",
            }:
                self.sources.append(href)
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property") or attrs.get("http-equiv")
            if key:
                self.metas[key].append(attrs.get("content", ""))

    def handle_startendtag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attributes)
        if tag not in VOID_TAGS and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)
        if tag == "nav":
            self.nav_depth = max(0, self.nav_depth - 1)
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing tag </{tag}>")
            return
        expected = self.stack.pop()
        if expected != tag:
            self.errors.append(f"closed </{tag}> while <{expected}> was open")

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def flattened_strings(value: Any, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(value, str):
        result[prefix] = value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(flattened_strings(item, f"{prefix}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            result.update(flattened_strings(item, f"{prefix}.{key}"))
    return result


def check_pair_list(
    errors: list[str], locale: str, label: str, value: Any, count: int
) -> None:
    if not isinstance(value, list) or len(value) != count:
        fail(errors, f"{locale}: {label} must contain exactly {count} pairs")
        return
    for index, pair in enumerate(value, 1):
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) and item.strip() for item in pair)
        ):
            fail(errors, f"{locale}: {label} pair {index} is incomplete")


def check_translation_source(
    errors: list[str], translations: dict[str, dict[str, Any]]
) -> None:
    english = flattened_strings(
        {
            "home": translations["en-US"]["home"],
            "support": translations["en-US"]["support"],
            "privacy": translations["en-US"]["privacy"],
        }
    )
    language_names: set[str] = set()
    for locale in LOCALES:
        data = translations[locale]
        if set(data) != EXPECTED_LOCALE_KEYS:
            fail(errors, f"{locale}: locale fields do not match the required schema")
            continue
        if set(data["home"]) != EXPECTED_HOME_KEYS:
            fail(errors, f"{locale}: home fields do not match the required schema")
        if set(data["support"]) != EXPECTED_SUPPORT_KEYS:
            fail(errors, f"{locale}: support fields do not match the required schema")
        if set(data["privacy"]) != EXPECTED_PRIVACY_KEYS:
            fail(errors, f"{locale}: privacy fields do not match the required schema")
        if (
            not isinstance(data["nav"], list)
            or len(data["nav"]) != 3
            or not all(isinstance(item, str) and item.strip() for item in data["nav"])
        ):
            fail(errors, f"{locale}: navigation must have three native labels")
        check_pair_list(
            errors,
            locale,
            "home.features",
            data["home"].get("features"),
            EXPECTED_FEATURES,
        )
        check_pair_list(
            errors,
            locale,
            "support.faqs",
            data["support"].get("faqs"),
            EXPECTED_FAQS,
        )
        check_pair_list(
            errors,
            locale,
            "privacy.sections",
            data["privacy"].get("sections"),
            EXPECTED_PRIVACY_SECTIONS,
        )
        strings = flattened_strings(data)
        for path, value in strings.items():
            if not value.strip():
                fail(errors, f"{locale}: empty value at {path}")
            if PLACEHOLDER.search(value):
                fail(errors, f"{locale}: placeholder at {path}")
        language_name = data["language_name"].strip().casefold()
        if language_name in language_names:
            fail(errors, f"{locale}: duplicate native language name")
        language_names.add(language_name)

        content = flattened_strings(
            {
                "home": data["home"],
                "support": data["support"],
                "privacy": data["privacy"],
            }
        )
        if locale != "en-US":
            comparable = set(content) & set(english)
            same = sum(
                content[path].strip().casefold()
                == english[path].strip().casefold()
                for path in comparable
            )
            required_differences = 8 if locale in ENGLISH_VARIANTS else len(comparable) - 3
            differences = len(comparable) - same
            if differences < required_differences:
                fail(
                    errors,
                    f"{locale}: possible English fallback "
                    f"({differences}/{len(comparable)} fields differ)",
                )
        joined = " ".join(strings.values())
        for token in (
            "3",
            "5",
            "MP4",
            "GIF",
            "Premium",
            "Aurora Pearl",
            "StoreKit",
            "PhotosPicker",
            "Apple",
        ):
            if token not in joined:
                fail(errors, f"{locale}: required factual token {token!r} is missing")
        tier_copy = data["support"]["faqs"][7][1]
        for token in ("3", "5", "MP4", "GIF", "Premium", "Aurora Pearl"):
            if token not in tier_copy:
                fail(
                    errors,
                    f"{locale}: Free/Premium boundary is missing {token!r}",
                )
        if LEGACY_TIER.search(joined):
            fail(errors, f"{locale}: legacy Pro tier label found; use Premium")
        if BANNED_CLAIMS.search(joined):
            fail(errors, f"{locale}: prohibited promotional claim found")

    english_text = " ".join(flattened_strings(translations["en-US"]).values()).lower()
    required_english = [
        "static",
        "scroll",
        "bounce",
        "left, right, up, or down",
        "countdown",
        "rhythm response",
        "mp4",
        "gif",
        "full screen",
        "reduce motion",
        "brightness",
        "auto-lock",
        "microphone",
        "never recorded",
        "photospicker",
        "3 saved boards",
        "5 starter scenarios",
        "aurora pearl",
        "vertical and bounce motion",
        "spacing and visual effects",
        "one-time premium purchase",
        "restore purchase",
        "no account",
        "no developer cloud",
        "no ads",
        "no analytics",
        "no tracking",
        "third-party runtime components or sdks",
        "deleting the app",
    ]
    for phrase in required_english:
        if phrase not in english_text:
            fail(errors, f"en-US: required truth statement {phrase!r} is missing")


def local_path_for_url(url: str) -> pathlib.Path | None:
    parsed = urllib.parse.urlparse(url)
    base = urllib.parse.urlparse(BASE_URL)
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
            return None
        path = parsed.path
    else:
        path = parsed.path
    prefix = urllib.parse.urlparse(BASE_URL).path
    if not path.startswith(prefix):
        return None
    relative = urllib.parse.unquote(path[len(prefix) :])
    if not relative or relative.endswith("/"):
        relative += "index.html"
    return ROOT / relative


def expected_html_pages() -> dict[pathlib.Path, tuple[str, str, str | None]]:
    expected: dict[pathlib.Path, tuple[str, str, str | None]] = {}
    for page in PAGES:
        expected[ROOT / PAGE_FILES[page]] = ("en-US", page, None)
    for locale in LOCALES:
        for page in PAGES:
            expected[ROOT / locale / PAGE_FILES[page]] = (locale, page, locale)
    return expected


def check_page(
    errors: list[str],
    path: pathlib.Path,
    locale: str,
    page: str,
    url_locale: str | None,
) -> None:
    relative = path.relative_to(ROOT)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        fail(errors, f"{relative}: cannot read ({error})")
        return
    parser = PageParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as error:  # HTMLParser errors are uncommon but must fail closed.
        fail(errors, f"{relative}: HTML parse failed ({error})")
        return
    for error in parser.errors:
        fail(errors, f"{relative}: {error}")
    if parser.stack:
        fail(errors, f"{relative}: unclosed tags: {', '.join(parser.stack[-5:])}")
    if not parser.doctype:
        fail(errors, f"{relative}: missing HTML5 doctype")
    if parser.html_attrs.get("lang") != locale:
        fail(errors, f"{relative}: html lang must be {locale}")
    expected_direction = "rtl" if locale in RTL else "ltr"
    if parser.html_attrs.get("dir") != expected_direction:
        fail(errors, f"{relative}: html dir must be {expected_direction}")
    if parser.tag_counts["h1"] != 1:
        fail(errors, f"{relative}: exactly one h1 is required")
    if parser.tag_counts["main"] != 1 or len(parser.main_attrs) != 1:
        fail(errors, f"{relative}: exactly one main landmark is required")
    elif (
        parser.main_attrs[0].get("id") != "main"
        or parser.main_attrs[0].get("tabindex") != "-1"
    ):
        fail(errors, f"{relative}: main must be a focusable skip-link target")
    if parser.tag_counts["nav"] != 1:
        fail(errors, f"{relative}: exactly one primary nav landmark is required")
    if parser.language_list_count != 1:
        fail(errors, f"{relative}: language selector must be a semantic list")
    for image in parser.images:
        if "alt" not in image:
            fail(errors, f"{relative}: every image must declare alt text")
        if not image.get("width", "").isdigit() or not image.get("height", "").isdigit():
            fail(errors, f"{relative}: every image needs intrinsic dimensions")
    if not parser.title:
        fail(errors, f"{relative}: title is empty")
    if len(parser.metas.get("description", [])) != 1 or not parser.metas[
        "description"
    ][0].strip():
        fail(errors, f"{relative}: exactly one non-empty description is required")
    expected_canonical = page_url(url_locale, page)
    if parser.canonicals != [expected_canonical]:
        fail(errors, f"{relative}: canonical is not exact")
    expected_hreflangs = set(LOCALES) | {"x-default"}
    if set(parser.alternates) != expected_hreflangs:
        fail(errors, f"{relative}: hreflang set is not exact")
    for code in LOCALES:
        if parser.alternates.get(code) != [page_url(code, page)]:
            fail(errors, f"{relative}: hreflang {code} has the wrong URL")
    if parser.alternates.get("x-default") != [page_url(None, page)]:
        fail(errors, f"{relative}: x-default has the wrong URL")
    if set(parser.language_links) != set(LOCALES):
        fail(errors, f"{relative}: language selector does not contain exact 50 locales")
    for code in LOCALES:
        if parser.language_links.get(code) != page_url(code, page):
            fail(errors, f"{relative}: language selector URL for {code} is wrong")
        expected_current = "page" if code == locale else ""
        if parser.language_currents.get(code) != expected_current:
            fail(errors, f"{relative}: language selector state for {code} is wrong")
    if len(parser.nav_links) != 3:
        fail(errors, f"{relative}: primary navigation must contain three links")
    expected_nav = [page_url(url_locale, item) for item in PAGES]
    if parser.nav_links != expected_nav:
        fail(errors, f"{relative}: primary navigation does not stay in locale")
    if parser.forbidden_tags:
        fail(errors, f"{relative}: forbidden active/embed tags found")
    for key in (
        "og:type",
        "og:site_name",
        "og:locale",
        "og:title",
        "og:description",
        "og:url",
        "og:image",
    ):
        if len(parser.metas.get(key, [])) != 1 or not parser.metas[key][0].strip():
            fail(errors, f"{relative}: missing or duplicate {key}")
    if parser.metas.get("og:url") != [expected_canonical]:
        fail(errors, f"{relative}: og:url differs from canonical")
    if parser.metas.get("robots") != ["index,follow,max-image-preview:large"]:
        fail(errors, f"{relative}: robots metadata is not exact")
    if parser.metas.get("referrer") != ["no-referrer"]:
        fail(errors, f"{relative}: referrer policy is not exact")
    if parser.metas.get("Content-Security-Policy") != [REQUIRED_CSP]:
        fail(errors, f"{relative}: strict Content Security Policy is missing")
    if parser.metas.get("og:locale") != [OG_LOCALES[locale]]:
        fail(errors, f"{relative}: OpenGraph locale is not canonical")
    if parser.metas.get("og:title") != [parser.title]:
        fail(errors, f"{relative}: OpenGraph title differs from document title")
    if parser.metas.get("og:description") != parser.metas.get("description"):
        fail(errors, f"{relative}: OpenGraph description differs from metadata")
    expected_image_meta = {
        "og:image": SOCIAL_IMAGE_URL,
        "og:image:secure_url": SOCIAL_IMAGE_URL,
        "og:image:type": "image/png",
        "og:image:width": "1200",
        "og:image:height": "630",
        "og:image:alt": "LED Moving Text",
        "twitter:card": "summary_large_image",
        "twitter:title": parser.title,
        "twitter:description": parser.metas.get("description", [""])[0],
        "twitter:image": SOCIAL_IMAGE_URL,
        "twitter:image:alt": "LED Moving Text",
    }
    for key, value in expected_image_meta.items():
        if parser.metas.get(key) != [value]:
            fail(errors, f"{relative}: {key} metadata is not exact")
    if parser.metas.get("twitter:card") != ["summary_large_image"]:
        fail(errors, f"{relative}: twitter card metadata is missing")
    if TRACKING_PATTERN.search(text):
        fail(errors, f"{relative}: tracking or storage construct found")
    if BANNED_CLAIMS.search(text):
        fail(errors, f"{relative}: prohibited promotional claim found")

    for source in parser.sources:
        target = local_path_for_url(source)
        if target is None:
            fail(errors, f"{relative}: external asset is forbidden ({source})")
        elif not target.is_file():
            fail(errors, f"{relative}: missing asset {source}")
    for href in parser.hrefs:
        if href == "#main":
            if "main" not in parser.ids:
                fail(errors, f"{relative}: skip-link target is missing")
            continue
        if href.startswith("mailto:"):
            if href != f"mailto:{EMAIL}":
                fail(errors, f"{relative}: unexpected mail link")
            continue
        target = local_path_for_url(href)
        if target is None:
            fail(errors, f"{relative}: external or invalid link {href}")
        elif not target.is_file():
            fail(errors, f"{relative}: broken internal link {href}")


def check_pages(errors: list[str]) -> None:
    expected = expected_html_pages()
    actual = set(ROOT.rglob("*.html"))
    if actual != set(expected):
        for path in sorted(set(expected) - actual):
            fail(errors, f"missing page {path.relative_to(ROOT)}")
        for path in sorted(actual - set(expected)):
            fail(errors, f"unexpected page {path.relative_to(ROOT)}")
    for path, (locale, page, url_locale) in expected.items():
        if path.is_file():
            check_page(errors, path, locale, page, url_locale)


def check_email_and_assets(errors: list[str]) -> None:
    required = [
        ROOT / ".nojekyll",
        ROOT / "README.md",
        ROOT / "robots.txt",
        ROOT / "sitemap.xml",
        ROOT / "assets" / "site.css",
        ROOT / "assets" / "brand-mark.png",
        ROOT / "assets" / "site-icon.png",
        ROOT / "assets" / "social-card.png",
        ROOT / "source" / "site-icon.svg",
        ROOT / "source" / "social-card.svg",
    ]
    for path in required:
        if not path.is_file():
            fail(errors, f"required file missing: {path.relative_to(ROOT)}")
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or path.suffix in {".png", ".pyc"}
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for address in EMAIL_PATTERN.findall(text):
            if address.casefold() != EMAIL:
                fail(errors, f"{path.relative_to(ROOT)}: unexpected email {address}")
    css_path = ROOT / "assets" / "site.css"
    if css_path.is_file():
        css = css_path.read_text(encoding="utf-8")
        for token in (
            "#fc67aa",
            "#ce5fe8",
            "#8980f7",
            "#5a9efa",
            "prefers-color-scheme: dark",
            "focus-visible",
            "prefers-reduced-motion: reduce",
            "prefers-contrast: more",
            "forced-colors: active",
            "ui-rounded",
            "--focus:",
        ):
            if token not in css.lower():
                fail(errors, f"site.css: required accessibility/design token {token!r} missing")
        if re.search(r"@import|https?://|url\s*\(", css, re.IGNORECASE):
            fail(errors, "site.css: external CSS dependency found")
    expected_images = {
        ROOT / "assets" / "brand-mark.png": ((640, 320), 512_000),
        ROOT / "assets" / "site-icon.png": ((256, 256), 100_000),
        ROOT / "assets" / "social-card.png": ((1200, 630), 512_000),
    }
    for image, (dimensions, maximum_bytes) in expected_images.items():
        if not image.is_file():
            continue
        raw = image.read_bytes()
        if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            fail(errors, f"{image.name} is not a valid PNG")
            continue
        width, height = struct.unpack(">II", raw[16:24])
        if (width, height) != dimensions:
            fail(errors, f"{image.name} dimensions must be {dimensions}")
        if len(raw) > maximum_bytes:
            fail(errors, f"{image.name} exceeds the optimized size budget")
    for source in (
        ROOT / "source" / "site-icon.svg",
        ROOT / "source" / "social-card.svg",
    ):
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8")
        references = re.findall(r"(?:href|src)=[\"']([^\"']+)", text, re.IGNORECASE)
        if re.search(r"<script\b|javascript:", text, re.IGNORECASE) or any(
            reference.startswith(("http://", "https://", "//"))
            for reference in references
        ):
            fail(errors, f"{source.relative_to(ROOT)}: remote or active SVG content")


def check_generated_outputs(
    errors: list[str], translations: dict[str, dict[str, Any]]
) -> None:
    stale: list[str] = []
    for path, expected in expected_outputs(translations).items():
        if not path.is_file():
            stale.append(f"missing {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            stale.append(f"stale {path.relative_to(ROOT)}")
    if stale:
        preview = ", ".join(stale[:8])
        remaining = len(stale) - 8
        suffix = f", and {remaining} more" if remaining > 0 else ""
        fail(errors, f"generated outputs are not current: {preview}{suffix}")


def check_sitemap(errors: list[str]) -> None:
    path = ROOT / "sitemap.xml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    locations = re.findall(r"<loc>([^<]+)</loc>", text)
    expected = [page_url(None, page) for page in PAGES]
    expected.extend(page_url(locale, page) for locale in LOCALES for page in PAGES)
    if text != render_sitemap():
        fail(errors, "sitemap.xml is not the deterministic generated XML")
    if locations != expected:
        fail(errors, "sitemap.xml URLs or order do not match generated pages")
    if len(locations) != EXPECTED_PAGE_COUNT or len(set(locations)) != len(locations):
        fail(
            errors,
            f"sitemap.xml must contain {EXPECTED_PAGE_COUNT} unique URLs",
        )
    robots = ROOT / "robots.txt"
    if robots.is_file():
        expected_line = f"Sitemap: {BASE_URL}sitemap.xml"
        if expected_line not in robots.read_text(encoding="utf-8").splitlines():
            fail(errors, "robots.txt does not point to the canonical sitemap")


def check_static_privacy(errors: list[str]) -> None:
    for path in ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "<script" in text.lower():
            fail(errors, f"{path.relative_to(ROOT)}: scripts are not permitted")
    all_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [
            ROOT / "source" / "translations.json",
            ROOT / "assets" / "site.css",
        ]
        if path.is_file()
    )
    if TRACKING_PATTERN.search(all_text):
        fail(errors, "source or CSS contains a tracking/storage construct")


def main() -> None:
    errors: list[str] = []
    try:
        translations = load_translations()
    except SystemExit as error:
        fail(errors, str(error))
        translations = {}
    if translations:
        check_translation_source(errors, translations)
        check_generated_outputs(errors, translations)
    check_pages(errors)
    check_email_and_assets(errors)
    check_sitemap(errors)
    check_static_privacy(errors)
    if errors:
        for message in errors:
            print(f"FAIL: {message}")
        print(f"FAILED with {len(errors)} error(s).")
        raise SystemExit(1)
    digest = hashlib.sha256(
        (ROOT / "source" / "translations.json").read_bytes()
    ).hexdigest()[:12]
    print(
        f"PASS: {EXPECTED_PAGE_COUNT} pages, {len(LOCALES)} locales, "
        f"exact hreflang/sitemap, source {digest}."
    )


if __name__ == "__main__":
    main()
