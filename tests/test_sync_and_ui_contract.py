#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Garmin sync sonuç yorumlama (401, hata, zaman aşımı), oturum çözümü ve arayüz-JS sözleşmesi testleri."""

import base64
import json
import os
import re
from html.parser import HTMLParser
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import server  # noqa: E402  (ilk içe aktarma motoru yükler; test ortamında yan etkisi yoktur)


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=["node"], returncode=returncode, stdout=stdout, stderr=stderr)



def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)

class TestSyncResultInterpretation(unittest.TestCase):
    def _sync(self, **run_kwargs):
        with patch.object(server, "IS_DEMO_MODE", False), \
             patch.object(server, "_reload_engine"), \
             patch.object(server.subprocess, "run", **run_kwargs):
            return server.sync_garmin_live()

    def test_exit_code_2_means_session_expired(self):
        res = self._sync(return_value=_completed(returncode=2))
        self.assertTrue(res["session_expired"])
        self.assertFalse(res["success"])

    def test_explicit_401_flag_means_session_expired(self):
        res = self._sync(return_value=_completed(stdout='{"remote_401":true}', returncode=0))
        self.assertTrue(res["session_expired"])

    def test_activity_id_containing_401_is_not_a_false_expiry(self):
        """Regresyon: çıktıdaki aktivite kimliklerinde '401' geçmesi oturumu 'doldu' saymamalı."""
        res = self._sync(return_value=_completed(stdout="Salon seti çekildi (25140123401)\nTamamlandı", returncode=0))
        self.assertTrue(res["success"])
        self.assertFalse(res["session_expired"])

    def test_nonzero_exit_without_401_is_a_plain_failure(self):
        res = self._sync(return_value=_completed(stderr="Hata: ağ kesildi", returncode=1))
        self.assertFalse(res["success"])
        self.assertFalse(res["session_expired"])
        self.assertIn("başarısız", res["message"])

    def test_timeout_is_reported_not_raised(self):
        res = self._sync(side_effect=subprocess.TimeoutExpired(cmd="node", timeout=180))
        self.assertFalse(res["success"])
        self.assertFalse(res["session_expired"])

    def test_demo_mode_never_runs_the_garmin_script(self):
        with patch.object(server, "IS_DEMO_MODE", True), patch.object(server, "_reload_engine"), \
             patch.object(server.subprocess, "run") as run:
            res = server.sync_garmin_live()
        run.assert_not_called()
        self.assertTrue(res["success"])


class TestSessionInspection(unittest.TestCase):
    def _session_with_jwt(self, exp):
        payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
        return {"cookies": [{"name": "JWT_WEB", "value": f"h.{payload}.s", "domain": "garmin.com"}], "last_keepalive_at": "2026-01-01T00:00:00Z"}

    def test_real_cookie_expiry_is_used_and_nothing_is_invented(self):
        exp = int(time.time()) + 600
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "session.json")
            _dump(path, self._session_with_jwt(exp))
            with patch.object(server, "_SESSION_FILE_PATH", path):
                info = server._inspect_session_jwt()
        self.assertEqual(info["jwt_expires_at"], exp)
        self.assertTrue(0 < info["jwt_remaining_sec"] <= 600)

    def test_expired_cookie_reports_zero_remaining(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "session.json")
            _dump(path, self._session_with_jwt(int(time.time()) - 100))
            with patch.object(server, "_SESSION_FILE_PATH", path):
                info = server._inspect_session_jwt()
        self.assertEqual(info["jwt_remaining_sec"], 0)

    def test_missing_or_corrupt_session_gives_unknown_not_a_fake_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(server, "_SESSION_FILE_PATH", os.path.join(tmp, "yok.json")):
                self.assertIsNone(server._inspect_session_jwt()["jwt_expires_at"])
            bad = os.path.join(tmp, "bad.json")
            _write(bad, "{bozuk")
            with patch.object(server, "_SESSION_FILE_PATH", bad):
                self.assertIsNone(server._inspect_session_jwt()["jwt_expires_at"])

    def test_long_running_endpoints_do_not_hold_the_engine_lock(self):
        for path in ("/api/sync", "/api/chat", "/api/session/keepalive"):
            self.assertIn(path, server.AthleteAppHandler._UNSCOPED_PATHS)


class TestUiJsContract(unittest.TestCase):
    """data-calls ile çağrılan her fonksiyonun JS'te tanımlı olduğunu doğrular (satır içi onclick dönüşümünün bütünlüğü)."""

    STATIC = os.path.join(BASE_DIR, "app", "static")

    def _js_text(self):
        parts = []
        jsdir = os.path.join(self.STATIC, "js")
        for name in sorted(os.listdir(jsdir)):
            parts.append(_read(os.path.join(jsdir, name)))
        return "\n".join(parts)

    def test_no_inline_event_handlers_remain(self):
        html = _read(os.path.join(self.STATIC, "index.html"))
        self.assertEqual(re.findall(r'\son(?:click|input|keydown|change|submit)="', html), [])
        for name in os.listdir(os.path.join(self.STATIC, "js")):
            txt = _read(os.path.join(self.STATIC, "js", name))
            self.assertEqual(re.findall(r'\son(?:click|input|keydown|change)="', txt), [], name)

    def test_every_data_call_targets_a_defined_function(self):
        html = _read(os.path.join(self.STATIC, "index.html"))
        js = self._js_text()
        called = set()
        for blob in re.findall(r'data-calls="([^"]*)"', html):
            for call in json.loads(blob.replace("&quot;", '"').replace("&amp;", "&")):
                called.add(call[0])
        called |= set(re.findall(r'data-(?:input|enter)-call="(\w+)"', html))
        called |= set(re.findall(r"&quot;(\w+)&quot;, \$\{", js)) | set(re.findall(r"\[\['(\w+)'", js))
        self.assertGreater(len(called), 10)
        for fn in sorted(called):
            self.assertRegex(js, rf"function\s+{fn}\s*\(", f"{fn}() tanımlı değil")

    def test_every_dom_id_used_by_js_exists(self):
        """JS'in getElementById ile aradığı her öğe HTML'de (veya JS'in ürettiği şablonlarda) bulunmalı; taşınan/silinen paneller sessizce kırılmasın."""
        html = _read(os.path.join(self.STATIC, "index.html"))
        js = self._js_text()
        missing = [i for i in sorted(set(re.findall(r"getElementById\('([\w-]+)'\)", js)))
                   if f'id="{i}"' not in html and f'id="{i}"' not in js]
        self.assertEqual(missing, [])

    def test_every_nav_tab_has_a_section(self):
        html = _read(os.path.join(self.STATIC, "index.html"))
        tabs = re.findall(r'id="nav-([\w-]+)"', html)
        self.assertGreaterEqual(len(tabs), 3)
        for t in tabs:
            self.assertIn(f'id="section-{t}"', html, t)

    def test_csp_compatible_no_inline_scripts(self):
        html = _read(os.path.join(self.STATIC, "index.html"))
        inline = []

        class _ScriptFinder(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "script" and "src" not in dict(attrs):
                    inline.append(self.getpos())

        _ScriptFinder().feed(html)
        self.assertEqual(inline, [])

    def test_mobile_nav_and_status_markup_present(self):
        html = _read(os.path.join(self.STATIC, "index.html"))
        for needle in ('class="mobile-title"', 'id="statusBanner"', 'role="dialog"'):
            self.assertIn(needle, html)


if __name__ == "__main__":
    unittest.main()


class TestSyncResilience(unittest.TestCase):
    """Senkron sorunları kalıcı çözüm: dış güncellemeyi algılama, eksik veride hızlı yeniden deneme, çift çekim kilidi."""

    def test_data_signature_tracks_raw_files_but_not_program_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("raw_daily_93d.json", "training_program_state.json"):
                with open(os.path.join(tmp, name), "w") as fh:
                    fh.write("{}")
            with patch.object(server.engine, "data_dir", tmp):
                base = server._data_signature()
                with open(os.path.join(tmp, "training_program_state.json"), "w") as fh:
                    fh.write('{"a": 1}')
                self.assertEqual(server._data_signature(), base)  # sunucunun kendi yazdığı dosya yeniden yüklemeyi tetiklemez
                with open(os.path.join(tmp, "raw_daily_93d.json"), "w") as fh:
                    fh.write('{"summaries": {}}')
                self.assertNotEqual(server._data_signature(), base)

    def test_refresh_reloads_engine_only_when_signature_changed(self):
        with patch.object(server, "IS_DEMO_MODE", False), \
                patch.object(server, "_data_signature", side_effect=["new", "new", "new"]), \
                patch.object(server, "DATA_SIGNATURE", "old"), \
                patch.object(server, "_reload_engine") as reload_mock:
            server.refresh_if_data_changed()
            reload_mock.assert_called_once()
        with patch.object(server, "IS_DEMO_MODE", False), \
                patch.object(server, "_data_signature", return_value="same"), \
                patch.object(server, "DATA_SIGNATURE", "same"), \
                patch.object(server, "_reload_engine") as reload_mock:
            server.refresh_if_data_changed()
            reload_mock.assert_not_called()

    def test_sync_incomplete_when_training_status_is_fallback_or_missing(self):
        with patch.object(server.engine, "training_status_is_fallback", True, create=True):
            self.assertFalse(server._sync_is_complete())
        with patch.object(server.engine, "training_status_is_fallback", False, create=True), \
                patch.object(server.engine, "training_status_latest", {"mostRecentTrainingStatus": {"x": 1}}, create=True):
            self.assertTrue(server._sync_is_complete())

    def test_fetch_script_exits_3_when_another_sync_holds_the_lock(self):
        import shutil
        if not shutil.which("node"):
            self.skipTest("node yok")
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "fetch_garmin_data.mjs")
        data_dir = os.path.join(os.path.dirname(script), "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        lock = os.path.join(data_dir, ".sync.lock")
        if os.path.exists(lock):
            self.skipTest("gerçek bir senkronizasyon çalışıyor olabilir")
        with open(lock, "w") as fh:
            json.dump({"pid": os.getpid(), "at": int(time.time() * 1000)}, fh)
        try:
            res = subprocess.run(["node", script], capture_output=True, text=True, timeout=60)
        finally:
            os.remove(lock)
        self.assertEqual(res.returncode, 3)
        self.assertIn('"already_running":true', res.stdout)


class TestSyncInProgressFlag(unittest.TestCase):
    def test_flag_is_set_during_sync_and_cleared_after(self):
        seen = {}

        def fake_impl():
            seen["during"] = server.SYNC_STATE["sync_in_progress"]
            return {"success": True}

        with patch.object(server, "_sync_garmin_live_impl", fake_impl):
            server.sync_garmin_live()
        self.assertTrue(seen["during"])
        self.assertFalse(server.SYNC_STATE["sync_in_progress"])

    def test_flag_is_cleared_even_when_sync_raises(self):
        def boom():
            raise RuntimeError("x")

        with patch.object(server, "_sync_garmin_live_impl", boom):
            with self.assertRaises(RuntimeError):
                server.sync_garmin_live()
        self.assertFalse(server.SYNC_STATE["sync_in_progress"])
