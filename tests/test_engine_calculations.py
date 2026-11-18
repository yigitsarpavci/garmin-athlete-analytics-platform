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
from datetime import datetime, timedelta

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
        from app.engine.morphology_health_mixin import _TR_FULL_MONTHS

        proj = self.engine.calculate_custom_projection(target_kg=81.0, weekly_pace_kg=0.55)
        # 87 kg -> 81 kg = 6.0 kg / 0.55 = 10.909 hafta * 7 = 76.36 -> 76 gün
        self.assertEqual(proj["days_needed"], 76)
        self.assertEqual(proj["remaining_kg"], 6.0)
        target_dt = datetime.now() + timedelta(days=proj["days_needed"])
        expected_date = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year}"
        self.assertIn(expected_date, proj["target_date"])

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
        from datetime import datetime, timedelta
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

    def test_weekly_quota_summary_states(self):
        """get_weekly_quota_summary() metodunun 1+1, 0+0 (+spontane) ve 2+2 senaryolarını doğrular."""
        from unittest.mock import patch

        ref_now = datetime(2026, 11, 17, 15, 0, 0)  # 16 Kas – 22 Kas haftası
        run_interval = {
            "startTimeLocal": "2026-11-16 10:24:35",
            "activityType": {"typeKey": "running"},
            "activityName": "Besiktas - Run Workout (4x1000m)",
            "duration": 2700.0,
            "distance": 6400.0,
            "calories": 520,
            "averageHR": 158,
            "anaerobicTrainingEffect": 2.8,
            "trainingEffectLabel": "ANAEROBIC_CAPACITY",
        }
        run_tempo = {
            "startTimeLocal": "2026-11-16 10:24:35",
            "activityType": {"typeKey": "running"},
            "activityName": "Besiktas Running",
            "duration": 1807.0,
            "distance": 5191.2,
            "calories": 401,
            "averageHR": 161,
            "maxHR": 174,
            "aerobicTrainingEffect": 3.6,
            "anaerobicTrainingEffect": 0.0,
            "trainingEffectLabel": "TEMPO",
            "hrTimeInZone_2": 285.0,
            "hrTimeInZone_3": 1236.0,
            "hrTimeInZone_4": 146.0,
        }
        gym_1 = {
            "startTimeLocal": "2026-11-17 10:35:00",
            "activityType": {"typeKey": "strength_training"},
            "activityName": "Strength",
            "duration": 3194.6,
            "calories": 340,
            "averageHR": 112,
        }
        sailing_1 = {
            "startTimeLocal": "2026-11-18 14:00:00",
            "activityType": {"typeKey": "sailing_v2"},
            "activityName": "Bosphorus Sailing",
            "duration": 7200.0,
            "calories": 650,
            "averageHR": 124,
        }

        # 1) Gerçek İnterval Koşu + 1 Kuvvet tamamlandı -> geriye Zone 2 + Workout B kalmalı
        with patch.object(self.engine, "activities_all", [run_interval, gym_1]):
            q_half = self.engine.get_weekly_quota_summary(now=ref_now)
        self.assertEqual(q_half["week_range"], "16 Kas – 22 Kas")
        self.assertEqual(q_half["total"]["target"], 4)
        self.assertEqual(q_half["total"]["completed"], 2)
        self.assertEqual(q_half["total"]["remaining"], 2)
        self.assertFalse(q_half["total"]["is_complete"])
        self.assertEqual(q_half["running"]["completed"], 1)
        self.assertEqual(q_half["running"]["remaining"], 1)
        self.assertEqual(q_half["running"]["remaining_items"][0]["slot_kind"], "zone2")
        self.assertEqual(q_half["strength"]["completed"], 1)
        self.assertEqual(q_half["strength"]["remaining"], 1)
        self.assertEqual(q_half["strength"]["remaining_items"][0]["slot_kind"], "gym_b")
        self.assertEqual(q_half["spontaneous"]["count"], 0)
        self.assertIn("1 Koşu + 1 Kuvvet", q_half["headline"])
        self.assertIn("Zone 2", q_half["headline"])
        self.assertIn("Workout B", q_half["headline"])

        # 2) Plan dışı Tempo koşusu (run_tempo, AnTE 0.0, TE=TEMPO) İnterval sayılmamalı
        with patch.object(self.engine, "activities_all", [run_tempo, gym_1]):
            q_tempo = self.engine.get_weekly_quota_summary(now=ref_now)
        self.assertTrue(q_tempo["post_tempo_adapted"])
        self.assertEqual(q_tempo["running"]["completed_kinds"], ["tempo"])
        self.assertEqual(q_tempo["running"]["remaining_items"][0]["slot_kind"], "interval")
        self.assertTrue(len(q_tempo["plan_deviations"]) >= 1)
        self.assertIn("Tempo Koşusu", q_tempo["plan_deviations"][0]["actual_label"])

        # 3) 0 Koşu + 0 Kuvvet (+ 1 spontane Yelken kotadan yemez)
        with patch.object(self.engine, "activities_all", [sailing_1]):
            q_zero = self.engine.get_weekly_quota_summary(now=ref_now)
        self.assertEqual(q_zero["total"]["completed"], 0)
        self.assertEqual(q_zero["total"]["remaining"], 4)
        self.assertEqual(q_zero["total"]["progress_pct"], 0)
        self.assertEqual(len(q_zero["running"]["remaining_items"]), 2)
        self.assertEqual(len(q_zero["strength"]["remaining_items"]), 2)
        self.assertEqual(q_zero["spontaneous"]["count"], 1)
        self.assertEqual(q_zero["spontaneous"]["items"][0]["sport_tr"], "Yelken")

        # 4) 2 Koşu + 2 Kuvvet tamamlandı
        run_2 = {**run_interval, "startTimeLocal": "2026-11-19 09:00:00", "averageHR": 144, "anaerobicTrainingEffect": 0.0, "trainingEffectLabel": "AEROBIC_BASE", "activityName": "Zone 2 Easy"}
        gym_2 = {**gym_1, "startTimeLocal": "2026-11-21 11:00:00"}
        with patch.object(self.engine, "activities_all", [run_interval, gym_1, run_2, gym_2]):
            q_full = self.engine.get_weekly_quota_summary(now=ref_now)
        self.assertEqual(q_full["total"]["completed"], 4)
        self.assertEqual(q_full["total"]["remaining"], 0)
        self.assertEqual(q_full["total"]["progress_pct"], 100)
        self.assertTrue(q_full["total"]["is_complete"])
        self.assertEqual(q_full["running"]["remaining_items"], [])
        self.assertEqual(q_full["strength"]["remaining_items"], [])
        self.assertEqual(q_full["remaining_items"], [])
        self.assertIn("tamamlandı", q_full["headline"].lower())

        # Esnek model doğrulaması: debrief ve reçetelerde sabit Perşembe/Cumartesi zorunluluğu yok
        debrief = self.engine.get_post_workout_debrief(0)
        self.assertIn("weekly_quota", debrief)
        self.assertNotIn("19 Kasım Perşembe", debrief["executive_coaching_verdict"]["next_session"]["day"])

    def test_off_plan_tempo_run_not_counted_as_interval_and_replans_week(self):
        """Pazartesi (2026-11-16) Tempo koşusu yapıldığında İnterval sayılmadığını, yapılanın yazıldığını ve kalan haftanın yeniden planlandığını doğrular."""
        from unittest.mock import patch
        from app.engine.helpers import classify_run_workout

        # Gerçek Pazartesi 2026-11-16 koşusu verisi (161 bpm, TE: TEMPO, AnTE: 0.0)
        mon_tempo = {
            "startTimeLocal": "2026-11-16 10:24:35",
            "activityType": {"typeKey": "running"},
            "activityName": "Besiktas Running",
            "duration": 1807.0,
            "distance": 5191.2,
            "calories": 401,
            "averageHR": 161,
            "maxHR": 174,
            "aerobicTrainingEffect": 3.6,
            "anaerobicTrainingEffect": 0.0,
            "trainingEffectLabel": "TEMPO",
            "hrTimeInZone_2": 285.3,
            "hrTimeInZone_3": 1236.9,
            "hrTimeInZone_4": 146.0,
        }
        tue_gym_a = {
            "startTimeLocal": "2026-11-17 10:35:00",
            "activityType": {"typeKey": "strength_training"},
            "activityName": "Strength",
            "duration": 3194.6,
            "calories": 340,
            "averageHR": 112,
        }

        cls_res = classify_run_workout(mon_tempo)
        self.assertEqual(cls_res["kind"], "tempo")
        self.assertEqual(cls_res["label_tr"], "Tempo Koşusu (Zone 3)")
        self.assertFalse(cls_res["is_planned_archetype"])

        with patch.object(self.engine, "activities_all", [mon_tempo, tue_gym_a]):
            ref_tue = datetime(2026, 11, 17, 20, 0, 0)
            sched, meta = self.engine._build_weekly_schedule_entries(now=ref_tue)
            quota = self.engine.get_weekly_quota_summary(now=ref_tue)
            # get_detailed_daily_workout_protocols() içindeki quota_status kontrolü (gerçek veride Pzt tempo var)
            with patch.object(self.engine, "get_weekly_quota_summary", return_value=quota):
                protocols = self.engine.get_detailed_daily_workout_protocols()

        # 1) Pazartesi (sched[0]) İnterval değil Tempo Koşusu yazmalı
        self.assertIn("Tempo Koşusu", sched[0]["primary"])
        self.assertIn("5K Hız İntervali yerine Tempo Koşusu", sched[0]["secondary"])
        self.assertEqual(sched[0].get("deviation_badge"), "Plan Dışı: Tempo Koşusu")

        # 2) Arka arkaya Pzt Tempo + Salı Gym A yapıldığı için Çarşamba (sched[2]) uyarlanmış toparlanma olmalı
        self.assertEqual(sched[2]["slot_kind"], "rest")
        self.assertIn("Uyarlanmış Toparlanma", sched[2]["primary"])

        # 3) Kalan günler (Perşembe İnterval telafisi, Cumartesi Workout B) güncel duruma göre planlanmalı
        self.assertEqual(sched[3]["slot_kind"], "interval")
        self.assertIn("Tempo Sonrası Güncel Telafi", sched[3]["primary"])
        self.assertEqual(sched[5]["slot_kind"], "gym_b")

        # 4) Reçeteler sekmesinde 5K Hız İntervali ve Zone 2 'completed' olarak işaretlenmemiş olmalı!
        int_proto = next(p for p in protocols if p["day_code"] == "monday")
        z2_proto = next(p for p in protocols if p["day_code"] == "thursday")
        gym_a_proto = next(p for p in protocols if p["day_code"] == "tuesday")
        self.assertEqual(int_proto["quota_status"], "remaining")
        self.assertEqual(z2_proto["quota_status"], "remaining")
        self.assertEqual(gym_a_proto["quota_status"], "completed")

    def test_monday_reset_with_last_week_deficit_adaptation(self):
        """Pazartesi 0/2 sıfırlamasını korurken geçen hafta eksik kalan türlerin yeni haftada öne alınmasını doğrular."""
        from unittest.mock import patch

        ref_mon = datetime(2026, 11, 23, 10, 0, 0)  # Yeni Pazartesi (geçen hafta: 16–22 Kas)
        # Geçen hafta yalnızca 1 rahat koşu (144 bpm -> Zone 2) ve 1 Workout A yapılmış;
        # yani Hız İntervali (1) ve Workout B (25005174809 yok, A yapılmış) eksik kalmış!
        prev_week_acts = [
            {
                "startTimeLocal": "2026-11-18 09:00:00",
                "activityType": {"typeKey": "running"},
                "activityName": "Zone 2 Base",
                "duration": 2700.0,
                "distance": 6800.0,
                "calories": 420,
                "averageHR": 144,
            },
            {
                "startTimeLocal": "2026-11-19 18:00:00",
                "activityType": {"typeKey": "strength_training"},
                "activityName": "Workout A Only",
                "duration": 3100.0,
                "calories": 330,
                "averageHR": 114,
            },
        ]
        sample_gym_hist = {
            "sessions": [{"date": "2026-11-19", "workout_type": "Workout A", "exercises": [], "total_volume_kg": 7000}],
            "progression": {},
        }
        with patch.object(self.engine, "activities_all", prev_week_acts), \
             patch.object(self.engine, "get_gym_exercise_history", return_value=sample_gym_hist):
            q = self.engine.get_weekly_quota_summary(now=ref_mon)

        # Pazartesi borç eklemez: kota daima 0/2 koşu + 0/2 kuvvet açılır (toplam 4)
        self.assertEqual(q["total"]["target"], 4)
        self.assertEqual(q["running"]["target"], 2)
        self.assertEqual(q["running"]["completed"], 0)
        self.assertEqual(q["running"]["remaining"], 2)
        self.assertEqual(q["strength"]["target"], 2)
        self.assertEqual(q["strength"]["completed"], 0)
        self.assertEqual(q["strength"]["remaining"], 2)
        # Geçen haftadan eksik kalan İnterval ve Workout B ilk sıraya önceliklendirilmeli
        self.assertEqual(q["running"]["remaining_items"][0]["slot_kind"], "interval")
        self.assertEqual(q["strength"]["remaining_items"][0]["slot_kind"], "gym_b")
        self.assertIn("5K Hız İntervali", q["last_week_adaptation"]["missed_sessions"])
        self.assertIn("Workout B", q["last_week_adaptation"]["missed_sessions"])

    def test_unknown_sport_dynamic_weight_and_anaerobic_focus(self):
        """Preset dışı sporları (Kayak), dinamik kilo/tarih değişimini ve Anaerobik Load Focus önceliğini doğrular."""
        from unittest.mock import patch

        tl = self.engine.get_training_load_analytics()
        self.assertEqual(tl["load_focus"]["primary_deficit"], "anaerobic")
        self.assertIn("Anaerobik", tl["load_focus"]["recommended_focus_label"])

        # Yeni tarih geçtiğinde Zone 2 otomatik bir sonraki kademeye (4:45 /km) geçmeli
        z2_future = self.engine.get_z2_pace_5min_tracker(now=datetime(2027, 4, 20, 12, 0, 0))
        self.assertTrue(z2_future["goal_auto_advanced"])
        self.assertEqual(z2_future["target_pace"], "4:45 /km")

        # Kayak gibi preset dışı spor hem kotada spontane hem spor kartlarında desteklenmeli
        ski_acts = [
            {
                "startTimeLocal": "2026-11-18 11:00:00",
                "activityType": {"typeKey": "resort_skiing"},
                "activityName": "Uludağ Kayak",
                "duration": 7200.0,
                "distance": 18500.0,
                "calories": 780,
                "averageHR": 136,
                "activityTrainingLoad": 95.0,
            }
        ]
        with patch.object(self.engine, "activities_all", ski_acts):
            q_ski = self.engine.get_weekly_quota_summary(now=datetime(2026, 11, 18, 15, 0, 0))
        self.assertEqual(q_ski["spontaneous"]["count"], 1)
        self.assertEqual(q_ski["spontaneous"]["items"][0]["sport_tr"], "Kayak")

        # Güncel kilo düştüğünde morfoloji aşamalarının dinamik güncellenmesi
        with patch.object(self.engine, "get_current_weight", return_value=83.0):
            morph = self.engine.get_physique_morphology_tracker(now=datetime(2026, 12, 1, 10, 0, 0))
        self.assertEqual(morph["current"]["weight_kg"], 83.0)
        self.assertEqual(morph["stages"][1]["target_kg"], 81.0)
        self.assertGreater(morph["stages"][1]["days_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
