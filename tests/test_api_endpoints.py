#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REST API Uç Noktaları Entegrasyon Testleri
HTTP sunucusunun sunduğu tüm GET ve POST uç noktalarının durum kodlarını,
JSON yanıtlarını ve şema geçerliliğini test eder.
"""

import unittest
import urllib.request
import urllib.error
import json
import os
import sys

BASE_URL = "http://127.0.0.1:8085"


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import socket, threading, time
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        is_running = (sock.connect_ex(('127.0.0.1', 8085)) == 0)
        sock.close()

        cls.server_thread = None
        cls.httpd = None
        if not is_running:
            app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app'))
            if app_dir not in sys.path:
                sys.path.insert(0, app_dir)
            from server import AthleteAppHandler
            from http.server import HTTPServer
            cls.httpd = HTTPServer(('127.0.0.1', 8085), AthleteAppHandler)
            cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
            cls.server_thread.start()
            time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        if cls.httpd:
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def get_json(self, path):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            return data

    def post_json(self, path, payload):
        raw = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}{path}", data=raw, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            return data

    def test_status_endpoint(self):
        """GET /api/status endpointini test eder."""
        data = self.get_json("/api/status")
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("profile_id", data)

    def test_overview_endpoint(self):
        """GET /api/overview endpointini test eder."""
        data = self.get_json("/api/overview")
        self.assertIn("weight", data)
        self.assertIn("schedule", data)
        self.assertEqual(len(data["schedule"]), 7)
        for key in (
            "overnight_hrv", "vo2max", "sleep_score", "sleep_hours", "rem_sleep_pct",
            "steps", "acute_load", "load_focus_summary", "stress", "readiness_score",
            "workouts_7d", "total_kcal", "kcal_7d_avg"
        ):
            self.assertIn(key, data, f"İlk ekran metriği eksik: {key}")
        self.assertGreater(data["workouts_7d"]["count"], 0)
        self.assertIn("anaerobic_pct", data["load_focus_summary"])

    def test_training_load_endpoint(self):
        """GET /api/training-load endpointini test eder."""
        data = self.get_json("/api/training-load")
        self.assertIn("current_status", data)
        self.assertIn("acute_load", data["current_status"])
        self.assertIn("chronic_load", data["current_status"])
        self.assertIn("load_focus", data)

    def test_gym_history_endpoint(self):
        """GET /api/gym-history endpointini test eder."""
        data = self.get_json("/api/gym-history")
        self.assertIn("progression", data)
        self.assertIn("sessions", data)

    def test_progression_assessment_endpoint(self):
        """GET /api/progression dogmatik olmayan seviye analizi endpointini test eder."""
        data = self.get_json("/api/progression")
        self.assertIn("volume_progression", data)
        self.assertIn("style_transition", data)
        self.assertIn("fatigue_and_deload", data)
        self.assertIn("athlete_levels", data)

    def test_daily_protocols_endpoint(self):
        """GET /api/daily-protocols detaylı antrenman reçetesini test eder."""
        data = self.get_json("/api/daily-protocols")
        self.assertEqual(len(data), 7)
        # Salı Workout A kontrolü
        tue = data[0]
        self.assertEqual(tue["category"], "gym")
        ex_names = [e["name"] for e in tue["exercises"]]
        self.assertIn("Barbell Back Squat", ex_names)
        self.assertIn("Dumbbell Lateral Raise (Yan Açış)", ex_names)
        self.assertIn("Dumbbell / Barbell Shrug (Trapez)", ex_names)

    def test_custom_profile_presets_endpoint(self):
        """GET /api/custom-profile/presets endpointini test eder."""
        data = self.get_json("/api/custom-profile/presets")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["id"], "sarp_default")

    def test_calculator_post_endpoint(self):
        """POST /api/calculator endpointini test eder."""
        from datetime import datetime, timedelta
        from app.engine.morphology_health_mixin import _TR_FULL_MONTHS

        res = self.post_json("/api/calculator", {"target_kg": 81.0, "weekly_pace_kg": 0.55})
        self.assertEqual(res.get("days_needed"), 76)
        target_dt = datetime.now() + timedelta(days=res.get("days_needed", 76))
        expected_date = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year}"
        self.assertIn(expected_date, res.get("target_date", ""))

    def test_custom_profile_plan_post_endpoint(self):
        """POST /api/custom-profile/plan endpointini test eder."""
        res = self.post_json("/api/custom-profile/plan", {
            "name": "Caner",
            "age": 30,
            "running_days": 3,
            "gym_days": 2
        })
        self.assertEqual(res.get("athlete_name"), "Caner")
        self.assertIn("athlete_tier", res)
        self.assertEqual(len(res.get("schedule", [])), 7)

    def test_post_workout_debrief_endpoint(self):
        """GET /api/post-workout-debrief 5 maddelik antrenman sonu debrief endpointini test eder."""
        data = self.get_json("/api/post-workout-debrief")
        self.assertIn("activity", data)
        self.assertIn("training_load", data)
        self.assertIn("productive_evaluation", data)
        self.assertIn("daily_biometrics_24h", data)
        self.assertIn("hr_comparison_with_prev_same_sport", data)
        self.assertIn("gym_volume_progression", data)
        self.assertIn("executive_coaching_verdict", data)
        # 17 Kasım Kuvvet seansı doğrulaması
        self.assertEqual(data["activity"]["sport"], "strength_training")
        self.assertEqual(data["gym_volume_progression"]["workout_type"], "Workout A")
        self.assertEqual(data["gym_volume_progression"]["current_volume_kg"], 7430.0)
        self.assertTrue(data["training_load"]["in_sweet_spot"])

    def test_garmin_expansion_high_res_endpoint(self):
        """GET /api/garmin-expansion yüksek çözünürlüklü FIT/HRV/RD kanallarını ve FIT kodlamayı test eder."""
        from app.engine.fit_stream_parser import encode_records_to_fit_bytes, parse_fit_bytes

        # 1. Pure Python FIT binary roundtrip & CRC-16 doğrulaması
        fit_raw = encode_records_to_fit_bytes([
            {"unix_ts": 1794900915, "distance_m": 100.0, "heart_rate": 144, "cadence_spm": 162, "speed_mps": 3.0, "power_w": 310, "stance_time_ms": 270.0, "vertical_oscillation_cm": 8.4},
            {"unix_ts": 1794900920, "distance_m": 115.0, "heart_rate": 146, "cadence_spm": 164, "speed_mps": 3.1, "power_w": 318, "stance_time_ms": 268.5, "vertical_oscillation_cm": 8.3},
        ])
        decoded = parse_fit_bytes(fit_raw, file_name="unit_test.fit")
        self.assertTrue(decoded["valid"])
        self.assertTrue(decoded["crc_ok"])
        self.assertEqual(decoded["record_count"], 2)
        self.assertEqual(decoded["summary"]["avg_hr"], 145.0)
        self.assertEqual(decoded["summary"]["avg_gct_ms"], 269.2)

        # 2. /api/garmin-expansion uç noktası
        data = self.get_json("/api/garmin-expansion")
        for key in (
            "new_high_resolution_channels",
            "implementation_steps_detail",
            "fit_stream_summary",
            "hrv_5min_summary",
            "running_dynamics_summary",
            "respiration_thermal_summary",
        ):
            self.assertIn(key, data, f"Eksik high-res anahtarı: {key}")

        self.assertEqual(len(data["new_high_resolution_channels"]), 4)
        self.assertEqual(len(data["implementation_steps_detail"]), 3)
        self.assertTrue(all(ch["status"] == "TAMAMLANDI & AKTİF" for ch in data["new_high_resolution_channels"]))
        self.assertTrue(all(st["status"] == "TAMAMLANDI & AKTİF" for st in data["implementation_steps_detail"]))
        self.assertGreater(len(data["hrv_5min_summary"]["readings"]), 0)
        if os.path.exists("data/archive/act_25105660179_details.json"):
            self.assertGreaterEqual(data["fit_stream_summary"]["binary_fit_count"], 8)
            self.assertGreaterEqual(data["fit_stream_summary"]["total_sample_points"], 245)
            self.assertGreaterEqual(data["running_dynamics_summary"]["rd_covered_runs"], 40)

        # 3. /api/garmin-settings Z1-Z5 nabız bölge grafiği verileri
        s_data = self.get_json("/api/garmin-settings")
        zones = s_data.get("zones", [])
        self.assertEqual(len(zones), 5)
        for z in zones:
            for zkey in ("zone_short", "zone", "rec_lthr", "rec_pwr", "run_minutes", "run_pct", "all_minutes", "all_pct", "color"):
                self.assertIn(zkey, z)
        self.assertAlmostEqual(sum(z["run_pct"] for z in zones), 100.0, places=0)


if __name__ == "__main__":
    unittest.main()
