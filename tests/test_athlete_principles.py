#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sporcu profili ve ilkeler testleri.
Kişisel değerler kodda yoktur: profil athlete_profile.json / Garmin verisinden gelir ve ilkeler çalışma anında türetilir.
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

from app.athlete_principles import (
    ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS, PRESENTATION_RULES,
    build_athlete_principles,
)
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


class TestDerivedPrinciples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GarminAthleteEngine(SAMPLE_DIR)
        cls.p = build_athlete_principles(cls.engine)

    def test_profile_comes_from_profile_file_and_garmin_data(self):
        prof = self.p["profile"]
        with open(os.path.join(SAMPLE_DIR, "athlete_profile.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(prof["age"], cfg["age"])
        self.assertEqual(prof["height_cm"], float(cfg["height_cm"]))
        self.assertEqual(prof["target_weight_optimal_kg"], cfg["target_weight_kg"])
        h2 = (cfg["height_cm"] / 100.0) ** 2
        self.assertAlmostEqual(prof["current_bmi"], prof["current_weight_kg"] / h2, places=1)
        self.assertAlmostEqual(prof["who_normal_bmi_max_kg"], 24.99 * h2, places=1)
        self.assertGreater(prof["max_heart_rate_actual"], prof["resting_heart_rate_actual"])

    def test_nutrition_uses_mifflin_st_jeor_with_athlete_values(self):
        n = self.p["nutrition"]
        w, h, age = self.engine.get_current_weight(), self.engine.height_cm, self.engine.age
        self.assertEqual(n["bmr_kcal"], round(10 * w + 6.25 * h - 5 * age + 5))
        self.assertEqual(n["tdee_range_kcal"], (round(n["bmr_kcal"] * 1.48), round(n["bmr_kcal"] * 1.60)))
        lo, hi = n["protein_g_per_day"]
        self.assertEqual((lo, hi), (round(2.0 * w), round(2.1 * w)))

    def test_nutrition_for_female_athlete_uses_female_constant(self):
        from unittest.mock import patch
        with patch.dict(self.engine.profile, {"gender": "female"}):
            n = build_athlete_principles(self.engine)["nutrition"]
        w, h, age = self.engine.get_current_weight(), self.engine.height_cm, self.engine.age
        self.assertEqual(n["bmr_kcal"], round(10 * w + 6.25 * h - 5 * age - 161))

    def test_strength_principles_are_derived_from_garmin_sets(self):
        lifts = self.p["strength"]["core_lifts_progression"]
        for key in ("back_squat", "bench_press", "barbell_row", "overhead_press", "deadlift", "lat_pulldown", "lateral_raise", "shrug"):
            self.assertIn(key, lifts)
            self.assertIn("next_target", lifts[key])
        self.assertTrue(lifts["back_squat"]["history"])  # sample_data'da gerçek set geçmişi var

    def test_running_zones_follow_athlete_max_hr(self):
        mx = self.engine.get_physiology()["max_hr"]
        z2_min, z2_max = self.p["running"]["zone2_heart_rate_range"]
        self.assertEqual((z2_min, z2_max), (round(0.69 * mx), round(0.74 * mx)))
        self.assertEqual(self.p["running"]["weekly_frequency"], 2)

    def test_same_day_sequence_and_cross_sports_use_real_activity_data(self):
        self.assertIn("ÖNCE KOŞU, ARDINDAN KUVVET", self.p["same_day_sequence"]["rule"])
        self.assertIsInstance(self.p["same_day_sequence"]["data_evidence"], list)
        for sport in self.p["cross_sports"]["detected_sports"]:
            self.assertFalse(sport["is_scheduled_regular"])

    def test_watch_settings_are_personalised_not_canned(self):
        items = self.p["recovery_and_watch"]["garmin_settings_to_fix"]
        self.assertEqual(len(items), 8)
        self.assertFalse(any("374 W" in str(i) or "65 bpm (Sabit" in str(i) for i in items))

    def test_zone_tokens_never_leak_into_api_output(self):
        for out in (self.engine.get_weekly_quota_summary(), self.engine.get_sports_guidance(),
                    self.engine.get_detailed_daily_workout_protocols(), self.engine.get_athlete_progression_assessment()):
            self.assertNotIn("[[", json.dumps(out, ensure_ascii=False))


class TestFrameworks(unittest.TestCase):
    def test_athlete_levels_framework(self):
        for lvl in ("beginner", "intermediate", "advanced", "elite"):
            self.assertIn(lvl, ATHLETE_LEVELS_FRAMEWORK)
            tier = ATHLETE_LEVELS_FRAMEWORK[lvl]
            for key in ("level_tr", "running_approach", "strength_approach", "recommended_split", "progression_gate"):
                self.assertIn(key, tier)

    def test_dynamic_progression_triggers(self):
        for trg in ("volume_increase", "style_shift", "deload_and_recovery"):
            t = DYNAMIC_PROGRESSION_TRIGGERS[trg]
            for key in ("name", "criteria", "action"):
                self.assertIn(key, t)
            self.assertGreater(len(t["criteria"]), 0)

    def test_presentation_rules_present(self):
        self.assertIn("tone", PRESENTATION_RULES)


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
