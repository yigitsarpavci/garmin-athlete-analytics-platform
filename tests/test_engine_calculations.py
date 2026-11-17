#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin Performans ve Fizyoloji Hesaplama Motoru Birim Testleri
Matematiksel formüllerin (Mifflin-St Jeor, ACWR, Kardiyak Verimlilik Faktörü EF,
1RM, Makro bölüşümleri, Projeksiyonlar) doğruluğunu test eder.
"""

import unittest
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.garmin_engine import GarminAthleteEngine


class TestEngineCalculations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GarminAthleteEngine()

    def test_mifflin_st_jeor_bmr_formula(self):
        """Mifflin-St Jeor BMR formülünün matematiksel doğruluğunu test eder."""
        # Erkek: 10 * kg + 6.25 * cm - 5 * yaş + 5
        # Sarp: 10 * 87 + 6.25 * 186 - 5 * 22 + 5 = 870 + 1162.5 - 110 + 5 = 1927.5 -> round: 1928 kcal
        weight = 87.0
        height = 186.0
        age = 22
        expected_bmr = round(10 * weight + 6.25 * height - 5 * age + 5)
        self.assertEqual(expected_bmr, 1928)

        # Kadın formülü testi: 10 * kg + 6.25 * cm - 5 * yaş - 161
        w_f, h_f, a_f = 65.0, 168.0, 28
        expected_female_bmr = round(10 * w_f + 6.25 * h_f - 5 * a_f - 161)
        self.assertEqual(expected_female_bmr, 1399)

    def test_tdee_and_macro_distribution(self):
        """TDEE ve makro besin dağılımı hesaplamalarını test eder."""
        plan = self.engine.generate_custom_plan({
            "name": "Test Sporcu",
            "age": 22,
            "gender": "male",
            "height_cm": 186.0,
            "current_weight_kg": 87.0,
            "target_weight_kg": 81.0,
            "weekly_weight_loss_rate": 0.55,
            "running_days": 2,
            "gym_days": 2
        })
        metrics = plan["metrics"]
        self.assertEqual(metrics["protein_g"], round(87.0 * 2.0)) # 174 g
        self.assertEqual(metrics["fat_g"], round(87.0 * 0.85))    # 74 g
        # Kalori dengesi: (Protein*4 + Karb*4 + Yağ*9) == target_calories (+/- 10 kcal yuvarlama)
        total_macro_kcal = (metrics["protein_g"] * 4) + (metrics["carbs_g"] * 4) + (metrics["fat_g"] * 9)
        self.assertAlmostEqual(total_macro_kcal, metrics["target_calories_kcal"], delta=15)

    def test_custom_projection_math(self):
        """Kilo projeksiyonunun gün ve hedef tarih matematiğini test eder."""
        proj = self.engine.calculate_custom_projection(target_kg=81.0, weekly_pace_kg=0.55)
        # 87 kg -> 81 kg = 6.0 kg / 0.55 = 10.909 hafta * 7 = 76.36 -> 76 gün
        self.assertEqual(proj["days_needed"], 76)
        self.assertEqual(proj["remaining_kg"], 6.0)
        self.assertIn("1 Şubat 2027", proj["target_date"])

    def test_efficiency_factor_math(self):
        """Kardiyak Verimlilik Faktörü (EF = Hız / Nabız) formülünü test eder."""
        # 145 bpm nabızda 6:40 /km (1000m / 400sn = 2.5 m/s)
        speed_mps = 1000.0 / 400.0 # 2.5 m/s
        hr = 145.0
        ef = round((speed_mps / hr) * 60, 2)
        self.assertEqual(ef, 1.03) # 1.03 metre / nabız atımı

        # Hedef: 145 bpm nabızda 5:00 /km (1000m / 300sn = 3.333 m/s)
        target_speed_mps = 1000.0 / 300.0 # 3.333 m/s
        target_ef = round((target_speed_mps / hr) * 60, 2)
        self.assertEqual(target_ef, 1.38) # 1.38 metre / nabız atımı (+%33 verimlilik)

    def test_acwr_sweet_spot(self):
        """Firstbeat Akut/Kronik Yük Oranı (ACWR) hesaplamasını test eder."""
        tl = self.engine.get_training_load_analytics()
        acwr_data = tl.get("acwr", {})
        ratio = acwr_data.get("acwr_ratio", 1.0)
        self.assertIsInstance(ratio, float)
        # Gabbett tatlı noktası (0.8 - 1.3)
        self.assertGreater(ratio, 0.5)
        self.assertLess(ratio, 2.0)

    def test_progressive_overload_rules(self):
        """A/B 5x5 Progressive Overload kurallarını ve sonraki hedefleri test eder."""
        proto = self.engine.get_detailed_daily_workout_protocols()
        self.assertEqual(len(proto), 7)
        # Salı Workout A
        tue = proto[0]
        self.assertEqual(tue["category"], "gym")
        ex_names = [e["name"] for e in tue["exercises"]]
        self.assertIn("Barbell Back Squat", ex_names)
        self.assertIn("Barbell Bench Press", ex_names)
        self.assertIn("Barbell Bent-Over Row", ex_names)
        self.assertIn("Dumbbell Lateral Raise (Yan Açış)", ex_names)
        self.assertIn("Dumbbell / Barbell Shrug (Trapez)", ex_names)

        # Cumartesi Workout B
        sat = proto[4]
        self.assertEqual(sat["category"], "gym")
        sat_ex = [e["name"] for e in sat["exercises"]]
        self.assertIn("Barbell Back Squat", sat_ex)
        self.assertIn("Barbell Overhead Press (OHP)", sat_ex)
        self.assertIn("Barbell Deadlift", sat_ex)
        self.assertIn("Lat Pulldown (Geniş Tutuş)", sat_ex)
        self.assertIn("Dumbbell Lateral Raise (Yan Açış)", sat_ex)
        self.assertIn("Dumbbell / Barbell Shrug (Trapez)", sat_ex)

    def test_z2_tracker_dynamic_countdown(self):
        """Zone 2 5:00 pace sayacının dinamik gün ve seans hesaplamasını test eder."""
        tracker = self.engine.get_z2_pace_5min_tracker()
        self.assertGreater(tracker["remaining_days"], 0)
        self.assertIn("remaining_zone2_sessions", tracker["workout_counts"])
        self.assertIn("remaining_interval_sessions", tracker["workout_counts"])
        self.assertIn("remaining_strength_sessions", tracker["workout_counts"])

    def test_weekly_schedule_respects_completed_quota(self):
        """Hafta başında tamamlanan seansların 2 Koşu + 2 Gym kotasından düşülmesini doğrular."""
        from datetime import datetime
        from unittest.mock import patch

        ref_now = datetime(2026, 11, 17, 15, 0, 0)  # Salı (16 Kas Pzt + 17 Kas Salı takvim haftası)
        sample_acts = [
            {
                "startTimeLocal": "2026-11-16 10:24:35",
                "activityType": {"typeKey": "running"},
                "activityName": "Besiktas Running",
                "duration": 1807.0,
                "distance": 5191.2,
                "calories": 401,
                "averageHR": 161,
            },
            {
                "startTimeLocal": "2026-11-17 10:35:00",
                "activityType": {"typeKey": "strength_training"},
                "activityName": "Strength",
                "duration": 3194.6,
                "calories": 340,
                "averageHR": 112,
            },
        ]
        with patch.object(self.engine, "activities_all", sample_acts):
            sched, meta = self.engine._build_weekly_schedule_entries(now=ref_now)
        self.assertEqual(len(sched), 7)
        self.assertTrue(sched[0]["day"].startswith("16 Kas Pzt"))
        self.assertEqual(meta["runs_done"], 1)
        self.assertEqual(meta["gyms_done"], 1)
        self.assertEqual(meta["rem_runs"], 1)
        self.assertEqual(meta["rem_gyms"], 1)

        completed_rows = [r for r in sched if "TAMAMLANDI" in r["secondary"]]
        planned_workouts = [
            r for r in sched
            if "TAMAMLANDI" not in r["secondary"]
            and (r["primary"].startswith("Koşu #") or r["primary"].startswith("Kuvvet #"))
        ]
        self.assertEqual(len(completed_rows), 2)
        self.assertEqual(len(planned_workouts), 2)
        self.assertEqual(len(completed_rows) + len(planned_workouts), 4)


if __name__ == "__main__":
    unittest.main()
