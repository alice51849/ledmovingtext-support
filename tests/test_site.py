from __future__ import annotations

import contextlib
import html
import io
import os
import pathlib
import re
import shutil
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))

import generate_site as site  # noqa: E402
import validate_site  # noqa: E402


class SiteGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.translations = site.load_translations()
        cls.family_links = site.load_family_links()
        cls.surface_contract = site.load_surface_contract()
        cls.outputs = site.expected_outputs(
            cls.translations,
            cls.family_links,
            cls.surface_contract,
        )
        cls.html_outputs = {
            path: text
            for path, text in cls.outputs.items()
            if path.suffix.lower() == ".html"
        }

    def test_exact_50_logical_routes_resolve_to_150_unique_files(self) -> None:
        routes = {
            self.surface_contract["routes"][locale][surface]
            for locale in site.LOCALES
            for surface in site.PAGES
        }
        self.assertEqual(50, len(site.LOCALES))
        self.assertEqual(150, len(routes))
        self.assertEqual(150, len(self.html_outputs))
        self.assertEqual(
            {
                "index": "index.html",
                "support": "support.html",
                "privacy": "privacy.html",
            },
            self.surface_contract["routes"]["en-US"],
        )
        self.assertFalse(any(route.startswith("en-US/") for route in routes))

    def test_every_output_keeps_all_approved_app_links(self) -> None:
        required_urls = site.managed_external_urls(self.family_links)
        for path, text in self.html_outputs.items():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual([], validate_site.managed_link_errors(text))
                self.assertIn(f"/id{site.OWN_APP_ID}?", html.unescape(text))
                self.assertEqual(1, text.count("<!-- ls-family:start -->"))
                self.assertEqual(1, text.count("<!-- ls-family:end -->"))
                self.assertIn(site.EMAIL, text)
                self.assertNotRegex(text, re.compile(r"<script\b", re.IGNORECASE))
                unescaped = html.unescape(text)
                for url in required_urls:
                    self.assertEqual(1, unescaped.count(url), url)

    def test_root_is_the_en_us_canonical_and_hreflang_target(self) -> None:
        for surface in site.PAGES:
            root_path = ROOT / site.PAGE_FILES[surface]
            root_text = self.html_outputs[root_path]
            root_url = site.page_url("en-US", surface)
            self.assertIn(f'<link rel="canonical" href="{root_url}">', root_text)
            self.assertIn(
                f'<link rel="alternate" hreflang="en-US" href="{root_url}">',
                root_text,
            )
        for path, text in self.html_outputs.items():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(f"{site.BASE_URL}en-US/", text)

    def test_sitemap_has_150_unique_urls_without_en_us_directory(self) -> None:
        sitemap = self.outputs[ROOT / "sitemap.xml"]
        locations = re.findall(r"<loc>([^<]+)</loc>", sitemap)
        self.assertEqual(150, len(locations))
        self.assertEqual(150, len(set(locations)))
        self.assertFalse(any("/en-US/" in location for location in locations))
        for surface in site.PAGES:
            self.assertIn(site.page_url("en-US", surface), locations)

    def test_missing_family_link_mutation_is_rejected(self) -> None:
        text = self.html_outputs[ROOT / "index.html"]
        missing_url = site.managed_external_urls(self.family_links)[1]
        mutated = text.replace(html.escape(missing_url, quote=True), "#removed", 1)
        self.assertNotEqual(text, mutated)
        errors = validate_site.managed_link_errors(mutated, self.family_links)
        self.assertTrue(any("required managed link" in error for error in errors))

    def test_two_builds_are_idempotent_and_stale_cleanup_is_exact(self) -> None:
        sandbox = ROOT / ".site-test-sandboxes" / f"generation-{os.getpid()}"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        sandbox.mkdir(parents=True)
        try:
            retired = sandbox / "en-US"
            retired.mkdir()
            for filename in site.PAGE_FILES.values():
                (retired / filename).write_text(
                    f"<!doctype html>\n{site.GENERATED_MARKER}\n",
                    encoding="utf-8",
                )

            with mock.patch.object(site, "ROOT", sandbox):
                outputs = site.expected_outputs(
                    self.translations,
                    self.family_links,
                    self.surface_contract,
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    site.write_outputs(outputs, self.surface_contract)
                first = self._snapshot(sandbox)
                with contextlib.redirect_stdout(io.StringIO()):
                    site.write_outputs(outputs, self.surface_contract)
                second = self._snapshot(sandbox)

            self.assertEqual(first, second)
            self.assertFalse(retired.exists())
            self.assertEqual(150, len(list(sandbox.rglob("*.html"))))
        finally:
            shutil.rmtree(sandbox)

    def test_stale_cleanup_preserves_other_files_in_retired_directory(self) -> None:
        sandbox = ROOT / ".site-test-sandboxes" / f"preserved-{os.getpid()}"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        retired = sandbox / "en-US"
        retired.mkdir(parents=True)
        for filename in site.PAGE_FILES.values():
            (retired / filename).write_text(
                f"<!doctype html>\n{site.GENERATED_MARKER}\n",
                encoding="utf-8",
            )
        preserved = retired / "keep.txt"
        preserved.write_text("not generated by the site builder\n", encoding="utf-8")
        try:
            with mock.patch.object(site, "ROOT", sandbox):
                outputs = site.expected_outputs(
                    self.translations,
                    self.family_links,
                    self.surface_contract,
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    site.write_outputs(outputs, self.surface_contract)
            self.assertTrue(preserved.is_file())
            for filename in site.PAGE_FILES.values():
                self.assertFalse((retired / filename).exists())
        finally:
            shutil.rmtree(sandbox)

    def test_unmanaged_stale_file_is_never_deleted(self) -> None:
        sandbox = ROOT / ".site-test-sandboxes" / f"unmanaged-{os.getpid()}"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        target = sandbox / "en-US" / "index.html"
        target.parent.mkdir(parents=True)
        target.write_text("owner-managed content\n", encoding="utf-8")
        try:
            with mock.patch.object(site, "ROOT", sandbox):
                outputs = site.expected_outputs(
                    self.translations,
                    self.family_links,
                    self.surface_contract,
                )
                with self.assertRaisesRegex(SystemExit, "unmanaged stale output"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        site.write_outputs(outputs, self.surface_contract)
            self.assertEqual(
                "owner-managed content\n",
                target.read_text(encoding="utf-8"),
            )
            self.assertFalse((sandbox / "support.html").exists())
        finally:
            shutil.rmtree(sandbox)

    def test_stale_cleanup_never_traverses_a_symlinked_directory(self) -> None:
        sandbox = ROOT / ".site-test-sandboxes" / f"symlink-{os.getpid()}"
        outside = ROOT / ".site-test-sandboxes" / f"outside-{os.getpid()}"
        for path in (sandbox, outside):
            if path.exists():
                shutil.rmtree(path)
        outside.mkdir(parents=True)
        protected = outside / "index.html"
        protected.write_text(
            f"<!doctype html>\n{site.GENERATED_MARKER}\n",
            encoding="utf-8",
        )
        sandbox.mkdir(parents=True)
        (sandbox / "en-US").symlink_to(outside, target_is_directory=True)
        try:
            with mock.patch.object(site, "ROOT", sandbox):
                outputs = site.expected_outputs(
                    self.translations,
                    self.family_links,
                    self.surface_contract,
                )
                with self.assertRaisesRegex(SystemExit, "through symlink"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        site.write_outputs(outputs, self.surface_contract)
            self.assertTrue(protected.is_file())
        finally:
            shutil.rmtree(sandbox)
            shutil.rmtree(outside)

    @staticmethod
    def _snapshot(root: pathlib.Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
