#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sporcu profili testleri.
Kişisel değerler kodda yoktur: profil athlete_profile.json / Garmin verisinden gelir.
Testler sentetik sample_data/ üzerinde çalışır.
"""

import json
import os
import re
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.athlete_profile import load_athlete_profile
from app.garmin_engine import GarminAthleteEngine

SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")



def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

class TestAthleteProfileLoader(unittest.TestCase):
    def _dir_with(self, **files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, payload in files.items():
            with open(os.path.join(tmp.name, name), "w", encoding="utf-8") as f:
                json.dump(payload, f)
        return tmp.name

    def test_empty_dir_uses_neutral_defaults_and_reports_missing(self):
        prof = load_athlete_profile(self._dir_with())
        self.assertFalse(prof["is_complete"])
        self.assertEqual(set(prof["missing"]), {"age", "gender", "height_cm", "target_weight_kg"})
        self.assertEqual(prof["sources"]["height_cm"], "default")

    def test_garmin_user_settings_fill_age_height_gender(self):
        raw = {"userData": {"birthDate": "1990-06-15", "gender": "FEMALE", "height": 168, "weight": 62500, "lactateThresholdHeartRate": 170}}
        prof = load_athlete_profile(self._dir_with(**{"raw_profile.json": raw}))
        self.assertEqual(prof["height_cm"], 168.0)
        self.assertEqual(prof["gender"], "female")
        self.assertEqual(prof["weight_kg"], 62.5)
        self.assertEqual(prof["lactate_threshold_hr"], 170)
        self.assertEqual(prof["sources"]["height_cm"], "garmin")
        self.assertGreaterEqual(prof["age"], 30)
        self.assertEqual(prof["missing"], ["target_weight_kg"])  # Garmin vermez: kullanıcı söylemeli

    def test_manual_profile_overrides_garmin(self):
        d = self._dir_with(**{
            "raw_profile.json": {"userData": {"height": 170, "birthDate": "1990-01-01", "gender": "male"}},
            "athlete_profile.json": {"height_cm": 172, "target_weight_kg": 70, "birth_date": "2000-01-01"},
        })
        prof = load_athlete_profile(d)
        self.assertEqual(prof["height_cm"], 172)
        self.assertEqual(prof["sources"]["height_cm"], "athlete_profile.json")
        self.assertTrue(prof["is_complete"])

    def test_corrupt_profile_file_does_not_crash(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        with open(os.path.join(d, "athlete_profile.json"), "w") as f:
            f.write("{not json")
        self.assertFalse(load_athlete_profile(d)["is_complete"])


class TestZoneTokens(unittest.TestCase):
    """Nabız/tempo şablon belirteçleri ([[Z2_HR]] vb.) hiçbir API çıktısına sızmamalı."""

    def test_zone_tokens_never_leak_into_api_output(self):
        engine = GarminAthleteEngine(SAMPLE_DIR)
        for out in (engine.get_weekly_quota_summary(), engine.get_detailed_daily_workout_protocols(),
                    engine.get_athlete_progression_assessment(), engine.get_post_workout_debrief(0)):
            self.assertNotIn("[[", json.dumps(out, ensure_ascii=False))


class TestNoPersonalDataInSource(unittest.TestCase):
    """Kaynak kodda kişiye özel değer kalmamalı: her şey profilden / Garmin verisinden gelir."""

    FORBIDDEN = [r"\bSarp\b", r"137931626", r"\b186(\.0)?\s?cm\b", r"height_cm\s*=\s*186", r"\bis_sarp\b", r"sarp_default"]

    CALENDAR_LITERALS = [r"\b2027\b", r"datetime\(20\d\d", r"[\"']20\d\d-\d\d-\d\d[\"']", r"Kasım 2026", r"Nisan 2027"]

    def test_app_code_has_no_hardcoded_calendar_dates(self):
        """Makro dönemler, hedef tarihleri ve pencereler veriden/profilden türetilir; koda sabit tarih yazılmaz."""
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(BASE_DIR, "app")):
            if "vendor" in root or "__pycache__" in root:
                continue
            for name in files:
                if not name.endswith((".py", ".js")):
                    continue
                text = _read(os.path.join(root, name))
                for pat in self.CALENDAR_LITERALS:
                    for m in re.finditer(pat, text):
                        line = text[: m.start()].count("\n") + 1
                        line_txt = text.splitlines()[line - 1]
                        if line_txt.lstrip().startswith("#") or '"""' in line_txt or "ör." in line_txt or "z2_goal_date" in line_txt:
                            continue  # yorum / docstring örneği
                        offenders.append(f"{name}:{line}: {pat}")
        self.assertEqual(offenders, [])

    def test_app_python_and_js_have_no_personal_literals(self):
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(BASE_DIR, "app")):
            if "vendor" in root or "__pycache__" in root:
                continue
            for name in files:
                if not name.endswith((".py", ".js", ".html")):
                    continue
                text = _read(os.path.join(root, name))
                for pat in self.FORBIDDEN:
                    if re.search(pat, text):
                        offenders.append(f"{name}: {pat}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
