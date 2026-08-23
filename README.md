# LED Moving Text — Support & Privacy Site

Production-ready static GitHub Pages source for **LED Moving Text**. The public
URL is:

`https://alice51849.github.io/ledmovingtext-support/`

## Structure

- `source/translations.json` — the single source of truth for all 50 Apple
  product-page locales
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
  `<locale>/privacy.html` — one complete set for each official Apple locale

Generated HTML must not be edited by hand.

## Generate and validate

Only Python’s standard library is required.

```sh
python3 scripts/generate_site.py
python3 scripts/generate_site.py --check
python3 scripts/validate_site.py
```

The optimized PNGs are checked in, so normal generation needs no image tooling.
When the artwork sources change, rebuild them locally from `source/` with
ImageMagick, then run `pngquant` and `oxipng`; the validator enforces dimensions
and strict size budgets.

The generated site contains 153 HTML pages: 3 canonical en-US pages plus 3
pages for each of the exact 50 locale paths. Every page includes a self
canonical, all 50 `hreflang` alternatives plus `x-default`, localized metadata,
localized navigation, a 50-language selector, strict no-script Content Security
Policy, and consistent OpenGraph/Twitter metadata.

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
