# LED Moving Text — Support & Privacy Site

Production-ready static GitHub Pages source for **LED Moving Text**. The public
URL is:

`https://alice51849.github.io/ledmovingtext-support/`

## Structure

- `source/translations.json` — the single source of truth for all 50 Apple
  product-page locales
- `source/family_links.json` — the verified, localized App Store family module
  and LED Moving Text CTA
- `source/support_surfaces.json` — the exact logical locale-to-route manifest
- `scripts/generate_site.py` — deterministic page, sitemap, and robots generator
- `scripts/validate_site.py` — fail-closed localization, privacy, link, metadata,
  asset, and sitemap validation
- `assets/site.css` — responsive Aurora Pearl presentation with dark mode,
  high-contrast focus, RTL, forced-colour, print, and reduced-motion support
- `assets/brand-mark.png` — original LED Moving Text brand artwork
- `source/social-card.svg`, `source/site-icon.svg` — editable local artwork
  sources for the optimized OpenGraph card and site icon in `assets/`
- `index.html`, `support.html`, `privacy.html` — canonical en-US pages
- `<locale>/index.html`, `<locale>/support.html`,
  `<locale>/privacy.html` — one complete set for each non-en-US Apple locale

Generated HTML must not be edited by hand.

## Generate and validate

Only Python’s standard library is required.

```sh
python3 scripts/generate_site.py
python3 scripts/generate_site.py --check
python3 scripts/validate_site.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The optimized PNGs are checked in, so normal generation needs no image tooling.
When the artwork sources change, rebuild them locally from `source/` with
ImageMagick, then run `pngquant` and `oxipng`; the validator enforces dimensions
and strict size budgets.

The generated site contains 150 HTML pages for 50 logical locales. The root
three pages are the en-US routes; the other 49 locales each have three
directory routes, so no duplicate `/en-US/` cluster is published. Every page
includes a self canonical, all 50 reciprocal `hreflang` alternatives plus
`x-default`, localized metadata and navigation, the managed family links, the
LED Moving Text App Store CTA, a 50-language selector, strict no-script Content
Security Policy, and consistent OpenGraph/Twitter metadata.

## Privacy and product facts

- Board creation and MP4/GIF processing happen on the device.
- Text, boards, style choices, templates, and selected background photos remain
  in local app storage.
- Microphone input is used only after the user enables rhythm response; it is
  analysed live and is not recorded, saved, or transmitted.
- Apple PhotosPicker exposes only the item selected by the user.
- The user controls any export or share destination.
- Apple processes the one-time Premium purchase and restoration through StoreKit.
- The app has no account, developer cloud, ads, analytics, tracking, or
  third-party runtime components or SDKs.
- The static site loads no third-party fonts, scripts, analytics, or assets and
  sets no cookies.
- The only public contact address is `hourstag.app@gmail.com`.

## Exact-50 support surfaces

The required `index`, `support`, and `privacy` routes are declared by
`source/support_surfaces.json` and rendered only by `scripts/generate_site.py`:

```bash
python3 tools/support_surfaces.py build
python3 tools/support_surfaces.py check
```

The source records the verified public catalogue and app/privacy authority
digests used for the copy. The wrapper never applies a second HTML rewrite.
Do not hand-edit generated locale pages.
