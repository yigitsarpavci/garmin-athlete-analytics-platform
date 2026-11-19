#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veri Bütünlüğü ve Sensör Telemetrisi Testleri
garminmcp/data/ altındaki tüm ham sensör kayıtlarının (aktiviteler, günlük özetler,
salon setleri, uyku verileri) geçerli JSON ve doğru şemada olduğunu doğrular.
"""

import unittest
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REAL_DATA_DIR = os.path.join(BASE_DIR, "data")
_SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")
DATA_DIR = _REAL_DATA_DIR if os.path.exists(os.path.join(_REAL_DATA_DIR, "raw_daily_93d.json")) else _SAMPLE_DATA_DIR


class TestDataIntegrity(unittest.TestCase):
    def test_raw_activities_file(self):
        """raw_activities.json dosyasının veri bütünlüğünü test eder."""
        path = os.path.join(DATA_DIR, "raw_activities.json")
        self.assertTrue(os.path.exists(path), "raw_activities.json dosyası mevcut olmalıdır")
        with open(path, "r", encoding="utf-8") as f:
            acts = json.load(f)
        self.assertIsInstance(acts, list)
        self.assertGreater(len(acts), 30, "En az 30 aktivite kaydı bulunmalıdır")
        first = acts[0]
        self.assertIn("activityId", first)
        self.assertIn("activityName", first)
        self.assertIn("activityType", first)
        self.assertIn("startTimeLocal", first)

    def test_raw_daily_file(self):
        """raw_daily_93d.json dosyasının 93 günlük veri bütünlüğünü test eder."""
        path = os.path.join(DATA_DIR, "raw_daily_93d.json")
        self.assertTrue(os.path.exists(path), "raw_daily_93d.json dosyası mevcut olmalıdır")
        with open(path, "r", encoding="utf-8") as f:
            daily = json.load(f)
        self.assertIsInstance(daily, dict)
        self.assertIn("summaries", daily)
        summaries = daily["summaries"]
        self.assertIsInstance(summaries, dict)
        self.assertGreaterEqual(len(summaries), 90, "90 günden fazla günlük özet kaydı bulunmalıdır")
        sample_date = list(summaries.keys())[-1]
        sample = summaries[sample_date]
        self.assertIn("calendarDate", sample)
        self.assertIn("restingHeartRate", sample)

    def test_raw_gym_exercise_sets_file(self):
        """raw_gym_exercise_sets.json dosyasındaki salon setlerini test eder."""
        path = os.path.join(DATA_DIR, "raw_gym_exercise_sets.json")
        self.assertTrue(os.path.exists(path), "raw_gym_exercise_sets.json dosyası mevcut olmalıdır")
        with open(path, "r", encoding="utf-8") as f:
            gym = json.load(f)
        self.assertIsInstance(gym, dict)
        self.assertGreaterEqual(len(gym), 5, "En az 5 gym seansı kaydedilmiş olmalıdır")
        first_id = next(iter(gym))
        session = gym[first_id]
        sets = session.get("sets") or session.get("exerciseSets") or []
        self.assertGreater(len(sets), 10, "En az 10 set kaydı bulunmalıdır")

    def test_raw_sleep_stats_file(self):
        """raw_sleep_stats.json dosyasının uyku kayıtlarını test eder."""
        path = os.path.join(DATA_DIR, "raw_sleep_stats.json")
        self.assertTrue(os.path.exists(path), "raw_sleep_stats.json dosyası mevcut olmalıdır")
        with open(path, "r", encoding="utf-8") as f:
            sleep_stats = json.load(f)
        self.assertIsInstance(sleep_stats, dict)
        self.assertGreaterEqual(len(sleep_stats), 80, "En az 80 gecelik uyku kaydı bulunmalıdır")


if __name__ == "__main__":
    unittest.main()
