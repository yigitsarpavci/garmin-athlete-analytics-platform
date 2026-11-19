#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Önyüzün çevrimdışı çalıştığını ve vendored bağımlılıkların bütünlüğünü doğrular."""

import hashlib
import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE_DIR, "app", "static")
VENDOR = os.path.join(STATIC, "vendor")



def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

class TestStaticAssets(unittest.TestCase):
    def test_index_has_no_external_script_or_stylesheet(self):
        """index.html hiçbir script/stylesheet'i CDN'den yüklememeli (internetsiz çalışma, sürüm sabitleme)."""
        html = _read(os.path.join(STATIC, "index.html"))
        external = re.findall(r'<(?:script|link)[^>]+(?:src|href)="(https?://[^"]+)"', html)
        self.assertEqual(external, [], f"Harici kaynak bulundu: {external}")

    def test_css_and_js_have_no_remote_urls(self):
        for sub in ("css", "js"):
            folder = os.path.join(STATIC, sub)
            for name in os.listdir(folder):
                text = _read(os.path.join(folder, name))
                remote = re.findall(r'(?:url\(|import\s+["\']|src=["\'])(https?://[^"\')]+)', text)
                self.assertEqual(remote, [], f"{name}: {remote}")

    def test_vendored_files_match_recorded_sha256(self):
        """vendor/VENDOR.md içindeki SHA-256 değerleri dosyalarla eşleşmeli (sessiz değişiklik tespiti)."""
        doc = _read(os.path.join(VENDOR, "VENDOR.md"))
        rows = re.findall(r"\| `([^`]+\.js)` \|[^|]+\|[^|]+\|[^|]+\| `([0-9a-f]{64})` \|", doc)
        self.assertGreaterEqual(len(rows), 1)
        for name, expected in rows:
            with open(os.path.join(VENDOR, name), "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(digest, expected, name)

    def test_font_css_points_only_to_existing_local_files(self):
        css = _read(os.path.join(VENDOR, "fonts.css"))
        urls = re.findall(r"url\(([^)]+)\)", css)
        self.assertGreater(len(urls), 0)
        for url in urls:
            self.assertTrue(url.startswith("/vendor/fonts/"), url)
            self.assertTrue(os.path.exists(os.path.join(STATIC, url.lstrip("/"))), url)


if __name__ == "__main__":
    unittest.main()


class TestTailwindStaticCss(unittest.TestCase):
    def test_tailwind_is_precompiled_not_runtime(self):
        """Tarayıcıda Tailwind derleyicisi çalışmamalı; statik css/tailwind.css kullanılmalı ve güncel olmalı."""
        html = _read(os.path.join(STATIC, "index.html"))
        self.assertNotIn("tailwind.config", html)
        self.assertIn("/css/tailwind.css", html)
        css = _read(os.path.join(STATIC, "css", "tailwind.css"))
        self.assertGreater(len(css), 5000)
        # index.html ve JS şablonlarında kullanılan sık sınıflar CSS'te bulunmalı (üretim güncel mi?)
        for cls in ("hidden", "flex", "font-mono", "truncate"):
            self.assertIn("." + cls, css)
        used = set(re.findall(r'text-\[(\d+(?:\.\d+)?px)\]', html))
        for size in used:
            self.assertIn(size.replace(".", "\\."), css, f"text-[{size}] sınıfı derlenmiş CSS'te yok: `make css` çalıştırın")
