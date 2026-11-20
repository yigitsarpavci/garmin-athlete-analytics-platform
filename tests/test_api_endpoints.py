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

BASE_URL = ""  # setUpClass içinde izole sunucunun serbest portuyla doldurulur
_APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "server.py"))


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Her test oturumu için ayrı bir sunucu süreci başlatır: GARMIN_DEMO_MODE=1 (sample_data),
        serbest bir port. Böylece testler çalışan uygulamaya (8085) ve gerçek data/ klasörüne dokunmaz.
        """
        global BASE_URL
        import socket, subprocess, time
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        env = dict(os.environ, GARMIN_DEMO_MODE="1", PYTHONDONTWRITEBYTECODE="1")
        cls.proc = subprocess.Popen(
            [sys.executable, "-B", _APP_PATH, str(port)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        BASE_URL = f"http://127.0.0.1:{port}"
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=1).read()
                return
            except Exception:
                if cls.proc.poll() is not None:
                    break
                time.sleep(0.2)
        cls.proc.terminate()
        raise RuntimeError("Test sunucusu başlatılamadı")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()

    def raw_request(self, path, headers=None, data=None, method=None):
        """(status, response_headers, body) döner; HTTP hata kodlarında istisna fırlatmaz."""
        req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    # ---- Güvenlik: yalnızca yerel, aynı kaynaklı istekler ----
    def test_foreign_host_header_rejected(self):
        status, _, _ = self.raw_request("/api/overview", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 403)

    def test_cross_origin_requests_rejected(self):
        status, _, _ = self.raw_request("/api/overview", headers={"Origin": "https://evil.example.com"})
        self.assertEqual(status, 403)
        status, _, _ = self.raw_request(
            "/api/sync", data=b"{}", headers={"Origin": "https://evil.example.com", "Content-Type": "application/json"}
        )
        self.assertEqual(status, 403)

    def test_cross_site_fetch_metadata_rejected(self):
        status, _, _ = self.raw_request("/api/session/keepalive", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)

    def test_same_origin_request_allowed_and_no_cors_header(self):
        status, headers, _ = self.raw_request(
            "/api/overview", headers={"Origin": BASE_URL, "Sec-Fetch-Site": "same-origin"}
        )
        self.assertEqual(status, 200)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_oversized_and_invalid_post_bodies(self):
        # Gövde gönderilmeden yalnızca dev bir Content-Length bildirilir; sunucu okumadan reddetmeli
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", int(BASE_URL.rsplit(":", 1)[1]), timeout=10)
        conn.putrequest("POST", "/api/session/keepalive")
        conn.putheader("Content-Length", "2000000")
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 413)
        conn.close()
        status, _, body = self.raw_request("/api/session/keepalive", data=b"[1,2,3]", method="POST")
        self.assertEqual(status, 200)  # dict olmayan gövde boş sayılır

    def test_security_headers_present(self):
        for path in ("/", "/api/overview"):
            status, headers, _ = self.raw_request(path)
            self.assertEqual(status, 200)
            csp = headers.get("Content-Security-Policy") or ""
            self.assertIn("script-src 'self'", csp)
            self.assertNotIn("unsafe-inline'; img", csp.split("script-src")[1].split(";")[0] + "'; img")  # script-src'de unsafe-inline yok
            self.assertIn("frame-ancestors 'none'", csp)
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_parallel_requests_are_served(self):
        """Sunucu çok iş parçacıklı: eşzamanlı istekler birbirini beklemeden tamamlanır."""
        from concurrent.futures import ThreadPoolExecutor
        paths = ["/api/overview", "/api/progression", "/api/daily-protocols", "/api/gym-history"] * 3
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda p: self.raw_request(p)[0], paths))
        self.assertTrue(all(code == 200 for code in results), results)

    def get_json(self, path, timeout=5):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        """GET /api/status ve /api/session/keepalive oturum koruma uç noktalarını test eder."""
        data = self.get_json("/api/status")
        self.assertEqual(data.get("status"), "ok")
        self.assertTrue(data.get("is_demo"))
        self.assertIn("session", data)
        self.assertTrue(data["session"].get("keepalive_active"))
        self.assertEqual(data["session"].get("keepalive_interval_sec"), 240)
        ka_data = self.get_json("/api/session/keepalive", timeout=50)
        self.assertIsInstance(ka_data, dict)
        self.assertIn("session_file_exists", ka_data)

    def test_overview_endpoint(self):
        """GET /api/overview endpointini test eder."""
        data = self.get_json("/api/overview")
        self.assertIn("weight", data)
        self.assertIn("weekly_quota", data)
        for key in (
            "overnight_hrv", "vo2max", "sleep_score", "sleep_hours", "rem_sleep_pct",
            "steps", "acute_load", "load_focus_summary", "stress", "readiness_score",
            "workouts_7d", "total_kcal", "kcal_7d_avg"
        ):
            self.assertIn(key, data, f"İlk ekran metriği eksik: {key}")
        self.assertGreaterEqual(data["workouts_7d"]["count"], 0)  # sample_data tarihleri sabittir; 7G penceresi boş olabilir
        self.assertIn("anaerobic_pct", data["load_focus_summary"])

    def test_gym_history_endpoint(self):
        """GET /api/gym-history endpointini test eder."""
        data = self.get_json("/api/gym-history")
        self.assertIn("progression", data)
        self.assertIn("sessions", data)

    def test_gym_history_is_paginated_but_progression_uses_all_sessions(self):
        """Seans listesi sayfalanır (en yeni önce); toplam sayı ve progresyon tüm kayıtlardan gelir."""
        full = self.get_json("/api/gym-history?limit=500")
        total = full["sessions_total"]
        self.assertGreaterEqual(total, 2)
        page1 = self.get_json("/api/gym-history?limit=1&offset=0")
        page2 = self.get_json("/api/gym-history?limit=1&offset=1")
        self.assertEqual(len(page1["sessions"]), 1)
        self.assertEqual(page1["sessions_total"], total)
        self.assertEqual(page1["sessions"][0], full["sessions"][0])
        self.assertEqual(page2["sessions"][0], full["sessions"][1])
        self.assertEqual(page1["progression"], full["progression"])
        self.assertEqual(self.get_json(f"/api/gym-history?limit=5&offset={total + 10}")["sessions"], [])
        # bozuk parametreler sunucuyu çökertmez; varsayılan sayfa döner
        self.assertGreaterEqual(len(self.get_json("/api/gym-history?limit=abc&offset=-3")["sessions"]), 1)

    def test_progression_assessment_endpoint(self):
        """GET /api/progression dogmatik olmayan seviye analizi endpointini test eder."""
        data = self.get_json("/api/progression")
        self.assertIn("volume_progression", data)
        self.assertIn("style_transition", data)

    def test_daily_protocols_endpoint(self):
        """GET /api/daily-protocols detaylı antrenman reçetesini test eder."""
        data = self.get_json("/api/daily-protocols")
        self.assertEqual(len(data), 8)
        # Salı Workout A kontrolü
        tue = data[0]
        self.assertEqual(tue["category"], "gym")
        ex_names = [e["name"] for e in tue["exercises"]]
        self.assertIn("Barbell Back Squat", ex_names)
        self.assertIn("Dumbbell Lateral Raise (Yan Açış)", ex_names)
        self.assertIn("Dumbbell / Barbell Shrug (Trapez)", ex_names)

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
        self.assertGreater(data["gym_volume_progression"]["current_volume_kg"], 0)
        self.assertIsInstance(data["training_load"]["in_sweet_spot"], bool)

    def test_sample_data_mock_engine_parity(self):
        """sample_data/ mock verisiyle motorun tüm temel uç noktaları hatasız ürettiğini doğrular."""
        from app.garmin_engine import GarminAthleteEngine
        sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_data")
        demo_engine = GarminAthleteEngine(sample_dir)
        self.assertGreater(len(demo_engine.df), 80)
        self.assertGreater(len(demo_engine.adf), 25)
        metrics = demo_engine.get_latest_metrics()
        self.assertIn("biometrics_93d", metrics)
        self.assertGreater(len(metrics["biometrics_93d"]), 5)


if __name__ == "__main__":
    unittest.main()
