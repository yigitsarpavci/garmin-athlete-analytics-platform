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

    def test_plateau_never_recommends_leaving_ab_program(self):
        from app.engine.strength_progression import _compute_plateau_score
        out = _compute_plateau_score({}, 2, 3, [0.2], {"squat": 1.4, "bench": 1.1}, 1.0, 1.0)
        self.assertEqual(out["recommended_split"], "5x5_linear")
        self.assertIn("A/B", out["recommendation"])


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
            self.assertNotIn("(r =", c["insight"])
            self.assertNotIn("n =", c["insight"])
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


class TestEmptyTrainingStatusFallback(unittest.TestCase):
    def test_null_today_status_falls_back_to_latest_filled_week(self):
        eng = GarminAthleteEngine.__new__(GarminAthleteEngine)
        good = {"mostRecentTrainingStatus": {"x": 1}, "mostRecentTrainingLoadBalance": {"y": 2}}
        empty = {"userId": 1, "mostRecentTrainingStatus": None, "mostRecentTrainingLoadBalance": None}
        eng.training_status_latest = dict(empty)
        eng.training_status_weekly = {"2026-11-09": {"mostRecentTrainingStatus": {"x": 0}}, "2026-11-16": good, "2026-11-20": dict(empty)}
        eng._repair_empty_training_status()
        self.assertEqual(eng.training_status_latest, good)
        self.assertNotIn("2026-11-20", eng.training_status_weekly)


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

        # 2. Low Aerobic çok düşük (160/400 = 40%) ve Anaerobik yüksek (220/260 = 84.6%) => 2 koşu da Zone 2
        with patch.object(eng, "get_training_load_analytics", return_value={
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 160.0, "target_max": 400.0, "pct_of_target": 40.0},
                "aerobic_high": {"actual": 400.0, "target_max": 500.0, "pct_of_target": 80.0},
                "anaerobic": {"actual": 220.0, "target_max": 260.0, "pct_of_target": 84.6},
            }
        }):
            res = eng._analyze_previous_week_carryover(mon, {})
            self.assertEqual(res["run_order"], ["zone2", "zone2"])
            self.assertEqual(len(res["next_4_runs_prediction"]["steps"]), 4)

        # 3. Anaerobik çok düşük (70/260 = 26.9%) ve Low Aerobic yüksek (380/400 = 95%) => 2 koşu da İnterval
        with patch.object(eng, "get_training_load_analytics", return_value={
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 380.0, "target_max": 400.0, "pct_of_target": 95.0},
                "aerobic_high": {"actual": 400.0, "target_max": 500.0, "pct_of_target": 80.0},
                "anaerobic": {"actual": 70.0, "target_max": 260.0, "pct_of_target": 26.9},
            }
        }):
            res = eng._analyze_previous_week_carryover(mon, {})
            self.assertEqual(res["run_order"], ["interval", "interval"])

        # 4. Low Aerobic en düşük (280/400 = 70% < 75% < 90%) => 1. adım zone2, sonra interval
        with patch.object(eng, "get_training_load_analytics", return_value={
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 280.0, "target_max": 400.0, "pct_of_target": 70.0},
                "aerobic_high": {"actual": 450.0, "target_max": 500.0, "pct_of_target": 90.0},
                "anaerobic": {"actual": 195.0, "target_max": 260.0, "pct_of_target": 75.0},
            }
        }):
            res = eng._analyze_previous_week_carryover(mon, {})
            self.assertEqual(res["run_order"], ["zone2", "interval"])

        # 5. High Aerobic en düşük (250/500 = 50%) ise doğrudan Tempo önerilir
        from app.engine.run_load_predictor import predict_next_n_runs
        pred_high = predict_next_n_runs({
            "targets_available": True,
            "aerobic_low": {"actual": 350.0, "target_max": 400.0},
            "aerobic_high": {"actual": 250.0, "target_max": 500.0},
            "anaerobic": {"actual": 220.0, "target_max": 260.0},
        }, [], n=4, ref_dt=mon)
        self.assertEqual(pred_high["steps"][0]["kind"], "tempo")

        # 6. Üç bar da >= %85 dolu olsa bile asla ekstra Gym önermez, en düşük yük barına göre koşu seçer
        pred_full = predict_next_n_runs({
            "targets_available": True,
            "aerobic_low": {"actual": 360.0, "target_max": 400.0},
            "aerobic_high": {"actual": 450.0, "target_max": 500.0},
            "anaerobic": {"actual": 230.0, "target_max": 260.0},
        }, [], n=4, ref_dt=mon)
        self.assertNotEqual(pred_full["steps"][0]["kind"], "gym_overflow")
        self.assertIn(pred_full["steps"][0]["kind"], ("zone2", "tempo", "interval"))

        # Sonraki güncellemede 28G pencereden düşüşle Anaerobik %70'e indiyse tekrar İnterval'e döner
        pred_dropped = predict_next_n_runs({
            "targets_available": True,
            "aerobic_low": {"actual": 360.0, "target_max": 400.0},
            "aerobic_high": {"actual": 450.0, "target_max": 500.0},
            "anaerobic": {"actual": 182.0, "target_max": 260.0},
        }, [], n=4, ref_dt=mon)
        self.assertEqual(pred_dropped["steps"][0]["kind"], "interval")


class TestDebriefLoadTunnelInterpretation(unittest.TestCase):
    def test_acute_below_tunnel_reports_below_not_inside(self):
        """Akut yük (208) tünelin (215-404) altındayken 'içindesiniz' dememeli."""
        blk = GarminAthleteEngine._build_debrief_load_block(26.9, 208, 269, 0.70, "LOW", 215, 404)
        self.assertFalse(blk["in_sweet_spot"])
        self.assertIn("altında", blk["interpretation"])
        self.assertNotIn("içindesiniz", blk["interpretation"])

        blk_ok = GarminAthleteEngine._build_debrief_load_block(50.0, 280, 269, 1.04, "OPTIMAL", 215, 404)
        self.assertTrue(blk_ok["in_sweet_spot"])
        self.assertIn("içindesiniz", blk_ok["interpretation"])


class TestDynamicWeeklyQuota(unittest.TestCase):
    def _make_stub(self, split="5x5_linear", plateau=30, chronic=270.0, vo2max=45.0, runs_28d=8, gyms_28d=8):
        from datetime import datetime, timedelta
        from app.engine.weekly_quota_mixin import WeeklyQuotaMixin
        now = datetime(2026, 11, 19, 10, 0)
        acts = []
        for i in range(runs_28d):
            d = (now - timedelta(days=(i * 2) % 27 + 1)).strftime("%Y-%m-%d %H:%M:%S")
            acts.append({"sport": "running", "startTimeLocal": d, "duration": 2400, "distance": 5000, "averageHR": 160, "activityTrainingLoad": 90})
        for i in range(gyms_28d):
            d = (now - timedelta(days=(i * 2) % 27 + 1)).strftime("%Y-%m-%d %H:%M:%S")
            acts.append({"sport": "strength_training", "startTimeLocal": d, "duration": 3300, "averageHR": 120})

        class _Stub(WeeklyQuotaMixin):
            def __init__(self):
                self.activities_all = acts

            def get_gym_exercise_history(self):
                return {
                    "program_state": {"active_split": split},
                    "plateau_analysis": {"plateau_score": plateau, "recommended_split": split},
                    "progression": {},
                    "sessions": [],
                }

            def get_training_load_analytics(self):
                return {
                    "current_status": {"chronic_load": chronic, "vo2max": vo2max, "tunnel_max": 500.0},
                    "load_focus": {
                        "targets_available": True,
                        "aerobic_low": {"actual": 200.0, "target_max": 400.0},
                        "aerobic_high": {"actual": 320.0, "target_max": 500.0},
                        "anaerobic": {"actual": 90.0, "target_max": 250.0},
                    },
                }

        return _Stub(), now

    def test_gym_quota_always_recommends_two_day_ab_regardless_of_fitness(self):
        for sp, gyms_28d, chronic, plateau in [
            ("5x5_linear", 8, 270.0, 30),
            ("push_pull", 14, 440.0, 60),
            ("upper_lower", 14, 450.0, 70),
            ("ppl", 12, 620.0, 90),
        ]:
            stub, now = self._make_stub(split=sp, plateau=plateau, chronic=chronic, gyms_28d=gyms_28d)
            dyn = stub.compute_dynamic_weekly_targets(now=now)
            self.assertEqual(dyn["gym_target"], 2)
            self.assertEqual(dyn["gym_sequence"], ["gym_a", "gym_b"])
            types = [stub._build_quota_remaining_item(k, idx + 1)["type"] for idx, k in enumerate(dyn["gym_sequence"])]
            self.assertEqual(types, ["Workout A", "Workout B"])

    def test_extra_sessions_without_capacity_keep_baseline_targets(self):
        stub, now = self._make_stub(split="5x5_linear", plateau=25, chronic=240.0, vo2max=44.0, runs_28d=12, gyms_28d=12)
        dyn = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn["run_target"], 2)
        self.assertEqual(dyn["gym_target"], 2)

    def test_maintenance_reduction_when_all_bars_stay_above_85(self):
        from datetime import timedelta
        stub, now = self._make_stub(split="push_pull", plateau=58, chronic=480.0, vo2max=53.0, runs_28d=15, gyms_28d=10)
        # Tüm koşuları bu haftanın Pazartesi'sinden önceki son 14 güne çek -> bu hafta 0 koşu yapılmış, önümüzdeki günlerde 28G pencereden düşecek yük yok
        for idx, act in enumerate(stub.activities_all):
            if act["sport"] == "running":
                act["startTimeLocal"] = (now - timedelta(days=(idx % 12) + 4)).strftime("%Y-%m-%d 10:00:00")
        # Tüm 3 bar %92+ ve 28G pencereden düşecek yük yok -> 0 koşu bile %85+ korur
        stub.get_training_load_analytics = lambda: {
            "current_status": {"chronic_load": 480.0, "vo2max": 53.0, "tunnel_max": 500.0},
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 370.0, "target_max": 400.0},
                "aerobic_high": {"actual": 465.0, "target_max": 500.0},
                "anaerobic": {"actual": 240.0, "target_max": 260.0},
            },
        }
        dyn0 = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn0["run_target"], 0)
        self.assertIn("0 Koşu", dyn0["run_plan_summary"])

        # Önümüzdeki günlerde 28G pencereden düşecek eski bir interval barı %85 altına indiriyorsa gelecek koşu yükünü tahmin edip erken eksiltmez (fitlik hedefi 3 korunur)
        exp_date = (now - timedelta(days=25)).strftime("%Y-%m-%d 10:00:00")
        stub.activities_all.append({
            "sport": "running", "startTimeLocal": exp_date, "duration": 2700, "distance": 7000,
            "averageHR": 175, "activityTrainingLoad": 90, "aerobicTrainingEffect": 3.0, "anaerobicTrainingEffect": 2.0,
        })
        stub.get_training_load_analytics = lambda: {
            "current_status": {"chronic_load": 480.0, "vo2max": 53.0, "tunnel_max": 500.0},
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 370.0, "target_max": 400.0},
                "aerobic_high": {"actual": 465.0, "target_max": 500.0},
                "anaerobic": {"actual": 245.0, "target_max": 260.0},  # %94.2 -> düşüşle ~%80'e iner, koşu gerekir -> fitlik hedefi 3 kalır
            },
        }
        dyn1 = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn1["run_target"], 3)

    def test_advanced_runner_scales_run_target_and_projection_horizon(self):
        stub, now = self._make_stub(split="push_pull", plateau=58, chronic=480.0, vo2max=53.0, runs_28d=15, gyms_28d=10)
        dyn = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn["run_target"], 3)
        self.assertIn(dyn["projection_horizon"], (4, 5, 6))
        self.assertEqual(len(dyn["run_prediction"]["steps"]), dyn["projection_horizon"])
        self.assertIn("Bu hafta 3 Koşu", dyn["run_plan_summary"])

    def test_midweek_reevaluation_after_run_adjusts_target_without_counter_overflow(self):
        from datetime import timedelta
        stub, now = self._make_stub(split="5x5_linear", plateau=40, chronic=480.0, vo2max=53.0, runs_28d=0, gyms_28d=0)
        # Bu hafta Pzt günü 1 koşu yapılmış olsun (now = Çarşamba)
        stub.activities_all = [{
            "sport": "running",
            "startTimeLocal": (now - timedelta(days=2)).strftime("%Y-%m-%d 09:00:00"),
            "duration": 2700, "distance": 7000, "averageHR": 165,
            "activityTrainingLoad": 100, "aerobicTrainingEffect": 3.4, "anaerobicTrainingEffect": 2.0,
        }]
        # 1) Koşu sonrası tüm barlar >= %85 ve Pazar'a kadar 0 ek koşu gerekiyorsa: target 1'e düşer
        stub.get_training_load_analytics = lambda: {
            "current_status": {"chronic_load": 480.0, "vo2max": 53.0, "tunnel_max": 500.0},
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 370.0, "target_max": 400.0},
                "aerobic_high": {"actual": 465.0, "target_max": 500.0},
                "anaerobic": {"actual": 240.0, "target_max": 260.0},
            },
        }
        dyn_zero_more = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn_zero_more["run_target"], 1)

        # 2) Koşu sonrası 1 bar < %85 kalmışsa: fitlik hedefi (3) verilir, counter için 4 verilmez
        stub.get_training_load_analytics = lambda: {
            "current_status": {"chronic_load": 480.0, "vo2max": 53.0, "tunnel_max": 500.0},
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 370.0, "target_max": 400.0},
                "aerobic_high": {"actual": 465.0, "target_max": 500.0},
                "anaerobic": {"actual": 150.0, "target_max": 260.0},
            },
        }
        dyn_under_85 = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn_under_85["run_target"], 3)

        # 3) Fitlik 2'ye düşerse (kronik yük tünel üst sınırının %90'ının altında) ve 2 koşu zaten yapılmış + bar < %85 ise bile 2 verilir (ekstra eklenmez)
        stub.activities_all.append({
            "sport": "running",
            "startTimeLocal": (now - timedelta(days=1)).strftime("%Y-%m-%d 09:00:00"),
            "duration": 2700, "distance": 7000, "averageHR": 150,
            "activityTrainingLoad": 80, "aerobicTrainingEffect": 3.0, "anaerobicTrainingEffect": 0.0,
        })
        stub.get_training_load_analytics = lambda: {
            "current_status": {"chronic_load": 260.0, "vo2max": 46.0, "tunnel_max": 500.0},
            "load_focus": {
                "targets_available": True,
                "aerobic_low": {"actual": 300.0, "target_max": 400.0},
                "aerobic_high": {"actual": 350.0, "target_max": 500.0},
                "anaerobic": {"actual": 120.0, "target_max": 260.0},
            },
        }
        dyn_dropped = stub.compute_dynamic_weekly_targets(now=now)
        self.assertEqual(dyn_dropped["run_target"], 2)
        self.assertEqual(dyn_dropped["gym_target"], 2)

    def test_gym_alternates_from_last_session_across_missed_and_extra_weeks(self):
        from datetime import timedelta
        stub, now = self._make_stub(runs_28d=0, gyms_28d=0)
        monday = now - timedelta(days=now.weekday())
        prev_mon = monday - timedelta(days=7)

        cases = [
            ([(0, "Workout A")], ["gym_b", "gym_a"]),
            ([(0, "Workout B")], ["gym_a", "gym_b"]),
            ([(0, "Workout A"), (2, "Workout B"), (4, "Workout A")], ["gym_b", "gym_a"]),
            ([(0, "Workout B"), (2, "Workout A"), (4, "Workout B")], ["gym_a", "gym_b"]),
            ([(0, "Workout B"), (3, "Workout A")], ["gym_b", "gym_a"]),
            ([(-5, "Workout A")], ["gym_b", "gym_a"]),
        ]
        for day_types, expected_order in cases:
            stub.activities_all = []
            gym_type_by_date = {}
            for offset, wtype in day_types:
                d_str = (prev_mon + timedelta(days=offset)).strftime("%Y-%m-%d")
                gym_type_by_date[d_str] = wtype
                stub.activities_all.append({
                    "sport": "strength_training",
                    "startTimeLocal": f"{d_str} 18:00:00",
                    "duration": 3300,
                    "averageHR": 120,
                })
            carry = stub._analyze_previous_week_carryover(monday, gym_type_by_date)
            self.assertEqual(carry["gym_order"], expected_order, msg=f"Failed for {day_types}")


if __name__ == "__main__":
    unittest.main()


class TestHrvBaselineFromGarmin(unittest.TestCase):
    """HRV dengeli aralığı sabit değil: Garmin'in hrvSummary.baseline değerinden, yoksa kişisel çeyreklikten gelir."""

    def test_garmin_baseline_preferred_and_none_without_data(self):
        eng = GarminAthleteEngine.__new__(GarminAthleteEngine)
        eng.hrv_5min_raw = {
            "2026-01-01": {"hrvSummary": {"baseline": {"balancedLow": 40, "balancedUpper": 70}}},
            "2026-01-02": {"hrvSummary": {}},
        }
        eng.get_personal_baseline = lambda col, **k: {"reliable": False}
        self.assertEqual(eng.get_hrv_baseline(), {"low": 40.0, "high": 70.0, "source": "garmin"})
        eng.hrv_5min_raw = {}
        self.assertIsNone(eng.get_hrv_baseline())
        eng.get_personal_baseline = lambda col, **k: {"reliable": True, "p25": 31.0, "p75": 49.0}
        self.assertEqual(eng.get_hrv_baseline(), {"low": 31.0, "high": 49.0, "source": "personal"})


class TestPersonalNutritionAndStatus(unittest.TestCase):
    def test_nutrition_is_derived_from_own_data_and_none_without_data(self):
        import pandas as pd
        eng = GarminAthleteEngine.__new__(GarminAthleteEngine)
        eng.df = pd.DataFrame({"total_kcal": [2600.0] * 10 + [100.0], "bmr_kcal": [1800.0] * 11})
        eng.get_current_weight = lambda: 80.0
        eng.get_target_weight = lambda: 75.0
        run = eng.get_day_nutrition("run")
        rest = eng.get_day_nutrition("rest")
        self.assertGreater(run["spend"], rest["spend"])
        self.assertEqual(run["protein"], 160)
        self.assertEqual(run["intake"], int(round((2600 * 1.02 - 500) / 50) * 50))
        eng.get_target_weight = lambda: 80.0  # hedefte: açık yok
        self.assertEqual(eng.get_day_nutrition("rest")["intake"], int(round(2600 * 0.88 / 50) * 50))
        eng.df = pd.DataFrame()
        self.assertIsNone(eng.get_day_nutrition("run"))
        self.assertEqual(eng.nutrition_texts("run")["macro"], "--")


class TestNanSafety(unittest.TestCase):
    """Gün başında yarım kalan (NaN) satırlar API'yi çökertmemeli veya uydurma değer göstermemeli."""

    def test_fnum_treats_nan_none_and_inf_as_missing(self):
        from app.engine.helpers import fnum
        self.assertEqual(fnum(float("nan"), 5.0), 5.0)
        self.assertEqual(fnum(None, 3.0), 3.0)
        self.assertEqual(fnum(float("inf"), 1.0), 1.0)
        self.assertEqual(fnum("7.5", 0.0), 7.5)

    def test_24h_biometrics_uses_last_valid_values_not_invented_defaults(self):
        import pandas as pd
        from app.engine.progression_debrief_mixin import ProgressionDebriefMixin
        stub = ProgressionDebriefMixin.__new__(ProgressionDebriefMixin)
        nan = float("nan")
        stub.df = pd.DataFrame({
            "sleep_h": [7.0, nan], "deep_h": [1.0, nan], "rem_h": [1.5, nan],
            "bb_wake": [70.0, nan], "bb_low": [12.0, nan], "avg_stress": [30.0, 33.0], "active_kcal": [400.0, 20.0],
        })
        act, bb_low, bb_wake, sleep_h, stages, stress = stub._collect_24h_biometrics({"sleep_hours": nan})
        self.assertEqual((bb_low, bb_wake, stress), (12, 70, 33))
        self.assertEqual(sleep_h, 7.0)
        self.assertIn("Derin: 1s 0dk (%14)", stages)
        stub.df = pd.DataFrame()
        self.assertEqual(stub._collect_24h_biometrics({})[3:5], (0.0, "Uyku evresi verisi yok"))


class TestFixedTwoDayStrengthPolicy(unittest.TestCase):
    """Kuvvet DAİMA haftada 2 gün (A/B), koşu yalnızca 2-3 gün; hiçbir Branşlar çıktısı bununla çelişmemeli."""

    FORBIDDEN = ("upper/lower", "upper / lower", "push / pull", "push/pull", "ppl", "3. kuvvet", "5. gün", "3 gym", "haftada 5 seans")

    def test_progression_and_plateau_texts_never_suggest_other_splits_or_extra_gym_days(self):
        import json
        eng = GarminAthleteEngine()
        blob = json.dumps({
            "prog": eng.get_athlete_progression_assessment(),
            "plateau": eng.get_gym_exercise_history().get("plateau_analysis"),
        }, ensure_ascii=False).lower()
        # athlete_levels / triggers çerçevesi de aynı kuralı taşır
        for token in self.FORBIDDEN:
            self.assertNotIn(token, blob, token)

    def test_every_athlete_level_has_two_strength_days_and_at_most_three_runs(self):
        from app.athlete_principles import ATHLETE_LEVELS_FRAMEWORK
        for key, lvl in ATHLETE_LEVELS_FRAMEWORK.items():
            self.assertIn("Haftada 2 gün", lvl["strength_frequency"], key)
            import re
            nums = [int(n) for n in re.search(r"Haftada ([\d-]+) gün", lvl["running_frequency"]).group(1).split("-")]
            self.assertLessEqual(max(nums), 3, key)

    def test_dynamic_targets_always_two_gym_and_two_or_three_runs(self):
        eng = GarminAthleteEngine()
        dyn = eng.compute_dynamic_weekly_targets()
        self.assertEqual(dyn["gym_target"], 2)
        self.assertIn(dyn["base_run_target"], (2, 3))
        self.assertEqual(eng.get_gym_exercise_history()["program_state"]["active_split"], "5x5_linear")
