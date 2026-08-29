#!/usr/bin/env python3
"""Build and validate LED Moving Text's exact-50 logical support surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))

import generate_site as site  # noqa: E402
import validate_site  # noqa: E402

SURFACES = site.PAGES
OFFICIAL = site.LOCALES


def load_source() -> dict[str, Any]:
    data = site.load_surface_contract()
    if data.get("targets") != []:
        raise SystemExit(
            "support surface targets must remain empty; scripts/generate_site.py "
            "is the only page renderer"
        )
    return data


def unique_routes(
    data: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    routes: dict[str, tuple[str, str]] = {}
    for locale in OFFICIAL:
        for surface in SURFACES:
            relative = data["routes"][locale][surface]
            if relative in routes:
                other_locale, other_surface = routes[relative]
                raise SystemExit(
                    f"duplicate route {relative}: "
                    f"{other_locale}/{other_surface} and {locale}/{surface}"
                )
            routes[relative] = (locale, surface)
    if len(routes) != len(OFFICIAL) * len(SURFACES):
        raise SystemExit("support surface source must resolve to 150 logical files")
    return routes


def build(data: dict[str, Any]) -> str:
    translations = site.load_translations()
    family_links = site.load_family_links()
    outputs = site.expected_outputs(translations, family_links, data)
    site.write_outputs(outputs, data)
    return content_digest(data)


def check(data: dict[str, Any]) -> dict[str, Any]:
    routes = unique_routes(data)
    errors = validate_site.collect_errors()
    if errors:
        raise SystemExit("\n".join(errors[:100]))
    return {
        "site": data["site"],
        "required_cells": len(OFFICIAL) * len(SURFACES),
        "unique_files": len(routes),
        "approved_email": site.EMAIL,
        "javascript": "none",
        "digest": content_digest(data),
        "status": "PASS",
    }


def content_digest(data: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(unique_routes(data)):
        path = ROOT.joinpath(*pathlib.PurePosixPath(relative).parts)
        if not path.is_file():
            raise SystemExit(f"missing required output: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check", "digest"))
    arguments = parser.parse_args()
    data = load_source()
    if arguments.command == "build":
        print(
            json.dumps(
                {"site": data["site"], "digest": build(data)},
                sort_keys=True,
            )
        )
    elif arguments.command == "check":
        print(json.dumps(check(data), sort_keys=True))
    else:
        print(content_digest(data))


if __name__ == "__main__":
    main()
