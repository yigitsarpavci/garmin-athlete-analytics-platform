#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sporcu İlkeleri ve Sistem Hafızası Birim Testleri
Single Source of Truth kurallarının, biyometrik normların ve 4 kademeli sporcu çerçevesinin doğruluğunu test eder.
"""

import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.athlete_principles import (
    ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
    RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
    RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
    ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
)


class TestAthletePrinciples(unittest.TestCase):
    def test_athlete_profile_biometrics(self):
        """Sarp'ın gerçek biyometrik verilerinin doğruluğunu test eder."""
        self.assertEqual(ATHLETE_PROFILE["age"], 22)
        self.assertEqual(ATHLETE_PROFILE["height_cm"], 186.0)
        self.assertEqual(ATHLETE_PROFILE["starting_weight_kg"], 95.0)
        self.assertEqual(ATHLETE_PROFILE["current_weight_kg"], 87.0)
        self.assertEqual(ATHLETE_PROFILE["weight_lost_kg"], 8.0)
        self.assertEqual(ATHLETE_PROFILE["current_bmi"], 25.15)
        self.assertEqual(ATHLETE_PROFILE["who_normal_bmi_max_kg"], 86.45)
        self.assertAlmostEqual(ATHLETE_PROFILE["remaining_to_normal_bmi_kg"], 0.55, places=2)
        self.assertEqual(ATHLETE_PROFILE["target_weight_optimal_kg"], 81.0)
        self.assertEqual(ATHLETE_PROFILE["resting_heart_rate_actual"], 53.6)
        self.assertEqual(ATHLETE_PROFILE["max_heart_rate_actual"], 203)

    def test_nutrition_principles(self):
        """Beslenme, kalori açığı ve protein katsayılarını test eder."""
        tdee_min, tdee_max = NUTRITION_PRINCIPLES["tdee_range_kcal"]
        self.assertGreaterEqual(tdee_min, 2800)
        self.assertLessEqual(tdee_max, 3200)

        cal_min, cal_max = NUTRITION_PRINCIPLES["target_calorie_intake_kcal"]
        self.assertEqual(cal_min, 2400)
        self.assertEqual(cal_max, 2500)

        prot_min, prot_max = NUTRITION_PRINCIPLES["protein_g_per_day"]
        self.assertEqual(prot_min, 175)
        self.assertEqual(prot_max, 180)

    def test_strength_principles_and_history(self):
        """Kuvvet antrenmanı telemetrisi ve Progressive Overload kurallarını test eder."""
        self.assertEqual(STRENGTH_PRINCIPLES["weekly_frequency"], 2)
        lifts = STRENGTH_PRINCIPLES["core_lifts_progression"]
        self.assertIn("back_squat", lifts)
        self.assertIn("bench_press", lifts)
        self.assertIn("barbell_row", lifts)
        self.assertIn("overhead_press", lifts)
        self.assertIn("deadlift", lifts)
        self.assertIn("lat_pulldown", lifts)
        self.assertIn("lateral_raise", lifts)
        self.assertIn("shrug", lifts)

        # 17 Kasım rekorları
        self.assertIn("65.0 kg", lifts["back_squat"]["history"][-1])
        self.assertIn("50.0 kg", lifts["bench_press"]["history"][-1])
        self.assertIn("60.0 kg", lifts["barbell_row"]["history"][-1])

    def test_running_principles(self):
        """80/20 polarize koşu modelini ve Zone 2 nabız pencerelerini test eder."""
        self.assertEqual(RUNNING_PRINCIPLES["weekly_frequency"], 2)
        z2_min, z2_max = RUNNING_PRINCIPLES["zone2_heart_rate_range"]
        self.assertEqual(z2_min, 140)
        self.assertEqual(z2_max, 150)
        self.assertEqual(RUNNING_PRINCIPLES["cadence_target_spm"], (160, 165))
        self.assertEqual(RUNNING_PRINCIPLES["ground_contact_time_target_ms"], 270)

    def test_same_day_sequence_law(self):
        """Aynı gün sıralama kanununun telemetri dayanağını test eder."""
        rule_text = SAME_DAY_SEQUENCE_LAW["rule"]
        self.assertIn("ÖNCE KOŞU, ARDINDAN KUVVET", rule_text)
        evidence = SAME_DAY_SEQUENCE_LAW["data_evidence"]
        self.assertEqual(evidence["strength_first_then_run"]["avg_hr_spike"], "+7 bpm (168 bpm)")
        self.assertEqual(evidence["strength_first_then_run"]["zone4_percentage"], "50.0% (İki katına çıktı)")

    def test_cross_sports_schedule_policy(self):
        """Yelken ve basketbolun spontane olduğu ve haftalık sabit takvime yazılmadığı kuralını test eder."""
        self.assertFalse(CROSS_SPORTS_PROTOCOLS["sailing"]["is_scheduled_regular"])
        self.assertFalse(CROSS_SPORTS_PROTOCOLS["basketball"]["is_scheduled_regular"])

    def test_athlete_levels_framework(self):
        """4 kademeli sporcu sınıflandırmasını test eder."""
        levels = ["beginner", "intermediate", "advanced", "elite"]
        for lvl in levels:
            self.assertIn(lvl, ATHLETE_LEVELS_FRAMEWORK)
            tier = ATHLETE_LEVELS_FRAMEWORK[lvl]
            self.assertIn("level_tr", tier)
            self.assertIn("running_approach", tier)
            self.assertIn("strength_approach", tier)
            self.assertIn("recommended_split", tier)
            self.assertIn("progression_gate", tier)

    def test_dynamic_progression_triggers(self):
        """Dogmatik olmayan dinamik tetikleyicilerin varlığını ve kurallarını test eder."""
        triggers = ["volume_increase", "style_shift", "deload_and_recovery"]
        for trg in triggers:
            self.assertIn(trg, DYNAMIC_PROGRESSION_TRIGGERS)
            t = DYNAMIC_PROGRESSION_TRIGGERS[trg]
            self.assertIn("name", t)
            self.assertIn("criteria", t)
            self.assertIn("action", t)
            self.assertGreater(len(t["criteria"]), 0)


if __name__ == "__main__":
    unittest.main()
