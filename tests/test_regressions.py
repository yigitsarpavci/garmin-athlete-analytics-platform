#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kod incelemesinde bulunan hataların regresyon testleri (veri dosyalarından bağımsız)."""

import os
import sys
import tempfile
import time
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.engine.telemetry_mixin import TelemetryMixin
from app.engine.strength_progression import (
    compute_adaptive_progression,
    load_program_state,
    select_program_split,
)
from app.garmin_engine import GarminAthleteEngine


def _session(date, name, weight, reps_list):
    return {
        "date": date,
        "time": "18:00",
        "workout_type": "Workout A",
        "exercises": [{"name": name, "sets": [{"weight_kg": weight, "reps": r} for r in reps_list]}],
    }


class TestAcwrInterpretation(unittest.TestCase):
    def test_bands_follow_acwr_value(self):
        f = TelemetryMixin._interpret_acwr
        self.assertIn("0,80 altı", f(0.6))
        self.assertIn("Sweet Spot", f(1.0))
        self.assertIn("dikkat", f(1.4))
        self.assertIn("tehlike", f(1.6))


class TestReadinessInputs(unittest.TestCase):
    def test_gym_history_reads_real_metric_keys(self):
        """HRV/ACWR hazırlık girdileri get_latest_metrics()'in gerçek anahtarlarından okunmalı."""
        from unittest.mock import patch
        eng = GarminAthleteEngine()
        seen = {}
        import app.engine.workout_protocols_mixin as w
        orig = w.compute_adaptive_progression

        def spy(*a, **k):
            seen.update(k.get("readiness_ctx") or {})
            return orig(*a, **k)

        fake = {"overnight_hrv": 30.0, "hrv_7d": 50.0, "sleep_score": 70, "acwr": 1.7, "weight": 87.0, "date": "2026-11-19"}
        with patch.object(w, "compute_adaptive_progression", spy), patch.object(eng, "get_latest_metrics", return_value=fake):
            eng.get_gym_exercise_history()
        self.assertEqual(seen.get("acwr"), 1.7)
        self.assertAlmostEqual(seen.get("hrv_ratio"), 0.6, places=2)


class TestStrengthLogic(unittest.TestCase):
    def test_lateral_raise_needs_two_clean_sessions_and_projection_agrees(self):
        sessions = [
            _session("2026-11-01", "Lateral Raise (Yana Açış)", 20.0, [12, 12, 12]),
            _session("2026-11-08", "Lateral Raise (Yana Açış)", 20.0, [12, 12, 12]),
            _session("2026-11-15", "Lateral Raise (Yana Açış)", 22.5, [12, 12, 12]),
        ]
        prog = compute_adaptive_progression(sessions, 87.0)["progression"]["lateral_raise"]
        self.assertEqual(prog["decision"], "CONSOLIDATE")
        self.assertEqual(prog["next_kg"], 22.5)
        self.assertEqual(prog["projected_weights"][:3], [22.5, 25.0, 25.0])

    def test_scheduled_deload_not_double_counted(self):
        sessions = [
            _session("2026-11-01", "Back Squat", 70.0, [5, 5, 4, 3, 3]),
            _session("2026-11-04", "Back Squat", 70.0, [5, 4, 4, 3, 2]),
            _session("2026-11-08", "Back Squat", 62.5, [5, 5, 5, 5, 5]),
        ]
        res = compute_adaptive_progression(sessions, 87.0)
        self.assertEqual(res["plateau_analysis"]["total_deloads"], 1)

    def test_recommendation_names_selected_split(self):
        from app.engine.strength_progression import _compute_plateau_score
        out = _compute_plateau_score({}, 2, 3, [0.2], {"squat": 1.4, "bench": 1.1}, 1.0, 1.0)
        self.assertEqual(select_program_split(out["plateau_score"]), out["recommended_split"])
        if out["recommended_split"] != "5x5_linear":
            from app.engine.strength_progression import PROGRAM_SPLIT_CATALOG
            self.assertIn(PROGRAM_SPLIT_CATALOG[out["recommended_split"]]["short_name"], out["recommendation"])


class TestNoWriteOnRead(unittest.TestCase):
    def test_get_gym_history_does_not_touch_program_state(self):
        eng = GarminAthleteEngine()
        path = os.path.join(eng.data_dir, "training_program_state.json")
        before = os.path.getmtime(path) if os.path.exists(path) else None
        for _ in range(3):
            eng.get_gym_exercise_history()
        after = os.path.getmtime(path) if os.path.exists(path) else None
        self.assertEqual(before, after)

    def test_persist_writes_only_on_change(self):
        from unittest.mock import patch
        eng = GarminAthleteEngine()
        with tempfile.TemporaryDirectory() as tmp, patch.object(eng, "data_dir", tmp):
            eng.persist_program_state()
            first = load_program_state(tmp)
            eng.persist_program_state()
            second = load_program_state(tmp)
        self.assertEqual(first.get("transition_history"), second.get("transition_history"))


class TestPeriodLabels(unittest.TestCase):
    def test_current_period_end_label_is_readable_date(self):
        """Son dönem bitiş etiketi '19 Kas' gibi olmalı ('11-19' yedek biçimine düşmemeli)."""
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        current = eng.get_periods_and_weeks()["periods"][-1]["dates"]
        self.assertRegex(current, r"- \d{2} \D{3} \(Mevcut Dönem\)")


class TestCalendarIsDataDriven(unittest.TestCase):
    """Takvim ve hedef yapıları sporcunun kendi veri aralığından / profilinden türetilir; sabit tarih yoktur."""

    def test_macro_periods_cover_the_athletes_own_date_range(self):
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        res = eng.get_periods_and_weeks()
        self.assertEqual(len(res["periods"]), 4)
        first_lbl = res["periods"][0]["dates"].split(" - ")[0]
        d0 = eng.dates[0]
        self.assertTrue(first_lbl.startswith(d0[8:10]), (first_lbl, d0))
        blob = " ".join(p["period"] + p["summary"] for p in res["periods"])
        for stale in ("Su Sporları", "Seyahat", "Basketbol & Yelken"):
            self.assertNotIn(stale, blob)

    def test_activity_window_starts_before_first_daily_record(self):
        from datetime import datetime, timedelta
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        expected = (datetime.strptime(eng.dates[0], "%Y-%m-%d") - timedelta(days=18)).strftime("%Y-%m-%d")
        self.assertEqual(eng._activity_cutoff(), expected)

    def test_z2_goal_from_profile_overrides_derived_values(self):
        from datetime import datetime
        from unittest.mock import patch
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        with patch.dict(eng.profile, {"z2_goal_pace": "5:30", "z2_goal_date": "2030-01-01"}):
            tr = eng.get_z2_pace_5min_tracker(now=datetime(2026, 6, 1))
        self.assertEqual(tr["target_pace"], "5:30 /km")
        self.assertIn("2030", tr["target_date"])
        self.assertFalse(tr["goal_auto_advanced"])

    def test_guest_plan_heart_rates_scale_with_age(self):
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        young = eng.generate_custom_plan({"name": "A", "age": 20, "running_days": 2, "gym_days": 2})
        older = eng.generate_custom_plan({"name": "B", "age": 60, "running_days": 2, "gym_days": 2})
        hr = lambda plan: int(__import__("re").search(r"(\d+)-\d+ bpm", plan["quota_summary"]["remaining_items"][0]["target_hr"]).group(1))
        self.assertGreater(hr(young), hr(older))

    def test_sports_guidance_has_no_fixed_sailing_or_basketball_cards(self):
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        sp = eng.get_sports_guidance()
        self.assertNotIn("sailing", sp)
        self.assertNotIn("basketball", sp)


class TestDataDrivenAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))

    def test_load_focus_without_targets_uses_share_not_division_by_one(self):
        """Hedef bandı olmayan veride yüzdeler toplam yük payıdır (%32000 gibi saçma değerler çıkmaz)."""
        lf = self.engine.get_training_load_analytics()["load_focus"]
        self.assertFalse(lf["targets_available"])
        self.assertEqual(lf["pct_basis"], "share")
        pcts = [lf[k]["pct_of_target"] for k in ("aerobic_low", "aerobic_high", "anaerobic")]
        self.assertAlmostEqual(sum(pcts), 100.0, delta=0.5)
        self.assertTrue(all(0 <= p <= 100 for p in pcts))

    def test_every_garmin_status_code_has_a_turkish_label(self):
        from app.engine.telemetry_mixin import _StatusLabels
        labels = _StatusLabels()
        for code in ("PRODUCTIVE_6", "MAINTAINING_3", "UNPRODUCTIVE_1", "RECOVERY_2", "PEAKING_1", "OVERREACHING_5", "DETRAINING_1"):
            txt = labels.get(code, code)
            self.assertNotRegex(txt, r"[A-Z_]{5,}\d?", code)
        self.assertEqual(labels.get("PRODUCTIVE_6", ""), "Üretken (Productive)")
        self.assertEqual(labels.get("BILINMEYEN_KOD_9", ""), "Bilinmeyen Kod 9")

    def test_student_t_p_values_match_reference_values(self):
        from app.engine.sleep_analytics_mixin import SleepAnalyticsMixin as M
        self.assertAlmostEqual(M._student_t_p_two_sided(2.0, 10), 0.0734, places=3)
        self.assertAlmostEqual(M._student_t_p_two_sided(3.0, 20), 0.0071, places=3)
        self.assertAlmostEqual(M._student_t_p_two_sided(0.0, 15), 1.0, places=6)
        self.assertLess(M._student_t_p_two_sided(14.0, 88), 1e-10)

    def test_correlation_insight_follows_the_sign_of_r(self):
        for c in self.engine.get_correlations():
            self.assertEqual(c["direction"], "negatif" if c["r"] < 0 else "pozitif")
            self.assertIn(f"r = {c['r']:.2f}"[:7], c["insight"])
            if not c["significant"]:
                self.assertIn("Anlamlı bir ilişki saptanmadı", c["insight"])

    def test_personal_baseline_excludes_today_and_flags_small_samples(self):
        base = self.engine.get_personal_baseline("hrv_night")
        series = self.engine.df["hrv_night"].dropna().iloc[:-1].tail(28)
        self.assertAlmostEqual(base["mean"], float(series.mean()), places=6)
        self.assertTrue(base["reliable"])
        tiny = self.engine.get_personal_baseline("hrv_night", days=5, min_points=10)
        self.assertFalse(tiny["reliable"])

    def test_channel_status_is_honest_about_derived_data(self):
        from app.engine.morphology_health_mixin import MorphologyHealthMixin as M
        self.assertEqual(M._channel_status(0, 0), "VERİ YOK")
        self.assertTrue(M._channel_status(5, 0).startswith("AKTİF"))
        self.assertTrue(M._channel_status(0, 5).startswith("TÜRETİLMİŞ"))
        self.assertTrue(M._channel_status(3, 2).startswith("KISMİ"))

    def test_write_json_if_changed_skips_identical_content(self):
        from app.engine.fit_stream_parser import _write_json_if_changed
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.json")
            self.assertTrue(_write_json_if_changed(path, {"a": 1, "updated_at": "t1"}))
            mtime = os.path.getmtime(path)
            self.assertFalse(_write_json_if_changed(path, {"a": 1, "updated_at": "t2"}))  # yalnızca zaman damgası farklı
            self.assertEqual(os.path.getmtime(path), mtime)
            self.assertTrue(_write_json_if_changed(path, {"a": 2, "updated_at": "t3"}))

    def test_engine_reload_does_not_rewrite_unchanged_streams(self):
        """load_data(): içerik değişmediyse yüksek çözünürlüklü akış dosyaları yeniden yazılmaz."""
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "data")
            shutil.copytree(os.path.join(BASE_DIR, "sample_data"), dst)
            from app.engine.fit_stream_parser import load_and_parse_high_res_streams
            load_and_parse_high_res_streams(dst, persist_real_fit=True)
            f = os.path.join(dst, "raw_high_res_streams.json")
            before = os.path.getmtime(f)
            time.sleep(0.05)
            load_and_parse_high_res_streams(dst, persist_real_fit=True)
            self.assertEqual(os.path.getmtime(f), before)

    def test_principles_endpoint_data_is_request_cached(self):
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        with eng.request_scope():
            a = eng.get_athlete_principles()
            b = eng.get_athlete_principles()
        self.assertEqual(a, b)
        self.assertIsNot(a, b)  # önbellekten derin kopya döner


class TestWeekStateRefactor(unittest.TestCase):
    def test_week_helpers_take_a_state_object_not_fifteen_parameters(self):
        import inspect
        from app.engine.weekly_quota_mixin import WeeklyQuotaMixin as W
        for name in ("_record_run_activity", "_record_strength_activity", "_plan_open_slots", "_resolve_day_row"):
            params = inspect.signature(getattr(W, name)).parameters
            self.assertIn("st", params, name)
            self.assertLessEqual(len(params), 14, f"{name}: {len(params)} parametre")


class TestSnapshotFreshness(unittest.TestCase):
    def test_stale_today_snapshot_is_flagged(self):
        """Bugünün Garmin özeti 90 dk'dan eskiyse (saat eşitlenmemiş) arayüze 'güncel değil' bilgisi gider."""
        from datetime import datetime, timedelta
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        today = datetime.now().strftime("%Y-%m-%d")
        old = (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S.0")
        fresh = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.0")
        eng.summaries[today] = {"wellnessEndTimeLocal": old}
        res = eng._snapshot_freshness(today)
        self.assertTrue(res["data_is_stale"])
        self.assertGreaterEqual(res["data_age_min"], 299)
        eng.summaries[today] = {"wellnessEndTimeLocal": fresh}
        self.assertFalse(eng._snapshot_freshness(today)["data_is_stale"])
        self.assertIsNone(eng._snapshot_freshness("1999-01-01")["data_as_of"])


class TestRequestScope(unittest.TestCase):
    def test_scope_computes_once_and_returns_isolated_copies(self):
        eng = GarminAthleteEngine()
        with eng.request_scope():
            a = eng.get_latest_metrics()
            a["weight"] = -1
            b = eng.get_latest_metrics()
        self.assertNotEqual(b["weight"], -1)
        self.assertIsNone(eng._req_cache)


class TestGymExerciseSetsFormat(unittest.TestCase):
    def test_reads_both_sets_and_raw_exerciseSets_keys(self):
        """Hem eski {'sets': [...]} hem yeni {'exerciseSets': [...]} Garmin formatı okunmalı."""
        import json
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            sample = os.path.join(BASE_DIR, "sample_data")
            for fn in os.listdir(sample):
                src = os.path.join(sample, fn)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(tmp, fn))

            with open(os.path.join(tmp, "raw_activities.json"), "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "activityId": 999001,
                        "startTimeLocal": "2026-11-19 18:00:00",
                        "duration": 3000,
                        "activityType": {"typeKey": "strength_training"},
                    }
                ], f)

            with open(os.path.join(tmp, "raw_gym_exercise_sets.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "999001": {
                        "activityId": 999001,
                        "exerciseSets": [
                            {
                                "setType": "ACTIVE",
                                "repetitionCount": 5,
                                "weight": 70000,
                                "exercises": [{"category": "SQUAT"}],
                            }
                        ],
                    }
                }, f)

            eng = GarminAthleteEngine(tmp)
            hist = eng.get_gym_exercise_history()
            self.assertEqual(len(hist["sessions"]), 1)
            self.assertEqual(hist["sessions"][0]["date"], "2026-11-19")
            self.assertEqual(hist["sessions"][0]["exercises"][0]["sets"][0]["weight_kg"], 70.0)


class TestLoadFocusRunSelection(unittest.TestCase):
    def test_low_aerobic_deficit_and_double_same_run_recommendation(self):
        """Low Aerobic düşükse Zone 2 öne çekilmeli; çok düşükse 2 koşu da aynı tür önerilmeli; High Aerobic ayrı tempo önermemeli."""
        from datetime import datetime
        from unittest.mock import patch
        eng = GarminAthleteEngine(os.path.join(BASE_DIR, "sample_data"))
        mon = datetime(2026, 11, 16)

        # 1. High Aerobic en düşük (30%) olsa bile ayrı tempo önerilmez; Low (50) < Anaerobic (80) => aerobic_low / Zone 2
        prio, rec = eng._pick_load_focus(120, 150, 80.0, 30.0, 50.0, "aerobic_low")
        self.assertIn("Zone 2", prio)
        self.assertNotIn("tempo", rec.lower())

        # 2. Low Aerobic çok düşük (40%) ve Anaerobik yüksek (85%) => 2 koşu da Zone 2
        with patch.object(eng, "get_training_load_analytics", return_value={
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"pct_of_target": 40.0},
                "aerobic_high": {"pct_of_target": 80.0},
                "anaerobic": {"pct_of_target": 85.0},
            }
        }):
            res = eng._analyze_previous_week_carryover(mon, {})
            self.assertEqual(res["run_order"], ["zone2", "zone2"])

        # 3. Anaerobik çok düşük (35%) ve Low Aerobic yüksek (90%) => 2 koşu da İnterval
        with patch.object(eng, "get_training_load_analytics", return_value={
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"pct_of_target": 90.0},
                "aerobic_high": {"pct_of_target": 80.0},
                "anaerobic": {"pct_of_target": 35.0},
            }
        }):
            res = eng._analyze_previous_week_carryover(mon, {})
            self.assertEqual(res["run_order"], ["interval", "interval"])

        # 4. Low Aerobic hafifçe düşük (70% vs 85%) => ["zone2", "interval"]
        with patch.object(eng, "get_training_load_analytics", return_value={
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"pct_of_target": 70.0},
                "aerobic_high": {"pct_of_target": 60.0},
                "anaerobic": {"pct_of_target": 85.0},
            }
        }):
            res = eng._analyze_previous_week_carryover(mon, {})
            self.assertEqual(res["run_order"], ["zone2", "interval"])


if __name__ == "__main__":
    unittest.main()
