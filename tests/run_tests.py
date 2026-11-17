#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin Sporcu Platformu - Birleşik Test Koşucusu (Test Suite Runner)
Tüm birim, entegrasyon, hesaplama ve veri bütünlüğü testlerini tek seferde koşturur.
"""

import unittest
import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TEST_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def run_all_tests():
    print("=" * 70)
    print("🏃 Garmin Sporcu Platformu Test Süiti Başlatılıyor")
    print(f"📁 Proje Dizini: {BASE_DIR}")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover(TEST_DIR, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("📊 Test Sonuç Özeti:")
    print(f"Toplam Koşturulan Test: {result.testsRun}")
    print(f"Başarılı: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Hatalar: {len(result.errors)}")
    print(f"Başarısızlıklar: {len(result.failures)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("🎉 TÜM TESTLER BAŞARIYLA TAMAMLANDI! (%100 Geçti)")
        return 0
    else:
        print("❌ BAZI TESTLER BAŞARISIZ OLDU!")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
