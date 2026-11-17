#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Garmin Sporcu İlkeleri ve Sistem Hafızası (Athlete Principles & Core Memory)
================================================================================

Bu modül, sporcunun antrenman, kardiyovasküler fizyoloji, kuvvet gelişimi,
makro beslenme ve toparlanma dinamiklerini yöneten kuralların tek doğruluk
kaynağıdır (Single Source of Truth - SSOT).

Mimari Prensipler:
-----------------
1. Arka Planda Derin İstatistik: ACWR, Firstbeat EPOC, EF (Hız/Nabız) formülleri
   matematiksel kesinlikle hesaplanır.
2. Ön Planda Sade Sporcu Dili: Karmaşık ara denklemler yerine doğrudan sahadaki
   eylem (set, tekrar, tempo, nabız zonu) sunulur.
3. Telemetri Gerçekliği: Jenerik veya uydurma egzersizler yerine Garmin sensörlerinden
   alınan gerçek telemetri verileri (kilolar, kadans, yerle temas süresi) kullanılır.
4. Dogmatik Olmayan Gelişim: Sporcunun seviyesine (Başlangıç, Orta, İleri, Elit) göre
   hacim ve periyodizasyon anlık toparlanma sinyallerine göre dinamik olarak evrilir.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional

# ==============================================================================
# 1. SPORCU BİYOMETRİK PROFİLİ VE TEMEL BİLGİLER
# ==============================================================================
# DSÖ (WHO) VKİ Sınıflaması: Normal Kilo: 18.5 - 24.99 kg/m²
# Boy = 186 cm (1.86 m) -> Üst sınır ağırlık = 24.99 * 1.86^2 = 86.45 kg
# 95.0 kg -> 87.0 kg (-8.0 kg / 63 gün = -0.89 kg/hafta)
# İdeal Atletik Hedef: 80.0 - 83.0 kg (5K <25:00 ve Zone 2 5:00 /km için optimal güç/ağırlık oranı)

@dataclass(frozen=True)
class AthleteProfileData:
    """Sporcunun temel antropometrik ve kardiyovasküler parametreleri."""
    age: int = 22
    gender: str = "male"
    height_cm: float = 186.0
    starting_weight_kg: float = 95.0
    current_weight_kg: float = 87.0
    weight_lost_kg: float = 8.0
    days_elapsed: int = 63
    weight_loss_rate_kg_per_week: float = 0.89
    current_bmi: float = 25.15
    who_normal_bmi_max_kg: float = 86.45
    remaining_to_normal_bmi_kg: float = 0.55
    target_weight_optimal_kg: float = 81.0
    target_weight_range_kg: Tuple[float, float] = (80.0, 83.0)
    resting_heart_rate_actual: float = 53.6
    max_heart_rate_actual: int = 203
    lactate_threshold_hr: int = 179
    vo2max_current: float = 45.4
    vo2max_august: float = 43.1
    vo2max_target: float = 51.5

ATHLETE_PROFILE: Dict[str, Any] = {
    "age": 22,
    "gender": "male",
    "height_cm": 186.0,
    "starting_weight_kg": 95.0,  # 15 Eylül 2026
    "current_weight_kg": 87.0,   # 17 Kasım 2026
    "weight_lost_kg": 8.0,
    "days_elapsed": 63,
    "weight_loss_rate_kg_per_week": 0.89,
    "current_bmi": 25.15,
    "who_normal_bmi_max_kg": 86.45,  # DSÖ Normal Kilo Üst Sınırı (VKİ = 24.99)
    "remaining_to_normal_bmi_kg": 0.55,
    "target_weight_optimal_kg": 81.0,  # Atletik form ve 5K hedefi için ideal kilo
    "target_weight_range_kg": (80.0, 83.0),
    "resting_heart_rate_actual": 53.6,
    "max_heart_rate_actual": 203,
    "lactate_threshold_hr": 179,
    "vo2max_current": 45.4,
    "vo2max_august": 43.1,
    "vo2max_target": 51.5
}

# ==============================================================================
# 2. BESLENME VE MAKRO İLKELERİ (87 kg -> 81 kg GEÇİŞİ)
# ==============================================================================
# Formül (Mifflin-St Jeor):
# BMR (Erkek) = (10 * ağırlık_kg) + (6.25 * boy_cm) - (5 * yaş) + 5
# BMR = (10 * 87.0) + (6.25 * 186) - (5 * 22) + 5 = 870 + 1162.5 - 110 + 5 = 1927.5 kcal
# TDEE (Hafif-Orta Aktif, PAL = 1.48 - 1.60) = 2850 - 3100 kcal
# Kalori Açığı = ~500 kcal -> Günlük Hedef = 2400 - 2500 kcal
# Protein Katsayısı: 2.0 - 2.1 g/kg (175 - 180 g) -> Negatif enerji dengesinde yağsız kası korur.

NUTRITION_PRINCIPLES: Dict[str, Any] = {
    "bmr_kcal": 1950,
    "tdee_range_kcal": (2850, 3100),
    "target_calorie_intake_kcal": (2400, 2500),
    "target_deficit_kcal": (400, 550),
    "protein_g_per_day": (175, 180),  # Vücut ağırlığı başına 2.0 - 2.1 g
    "carbs_g_per_day": (240, 280),    # Çift antrenman ve yelken günlerinde artırılır
    "fat_g_per_day": (70, 80),
    "water_daily_liters": (2.5, 3.5),
    "crash_diet_warning": (
        "87 kg sonrasında kas kaybını önlemek için haftalık kilo verme hızı "
        "-0.55 kg/hafta seviyesinde tutulmalı; kalori açığı 550 kcal üzerine çıkmamalıdır."
    )
}

# ==============================================================================
# 3. KUVVET ANTRENMANI VE SALON A/B RUTİNİ (GERÇEK TELEMETRİ)
# ==============================================================================
# Mekanik Gerilim & Progressive Overload Kuralı:
# 5x5 temiz formla tamamlandığında sonraki seansta ağırlık artışı uygulanır:
# - Üst Gövde (Bench Press, Barbell Row, OHP): +2.5 kg
# - Alt Gövde (Back Squat, Deadlift): +2.5 kg ila +5.0 kg
# Gerçek Garmin Set Telemetrisi (raw_gym_exercise_sets.json):
# - Squat: 45 kg -> 65 kg (5x5 PR kilitlendi) -> Sonraki: 67.5 kg
# - Bench Press: 45 kg -> 50 kg (5x5 kilitlendi) -> Sonraki: 52.5 kg
# - Lateral Raise: 20-25 kg x 12-13 tekrar x 3 set
# - Shrug: 45 kg x 12 tekrar x 3 set

STRENGTH_PRINCIPLES: Dict[str, Any] = {
    "routine_name": "A/B Full Body Alternating Split (5x5 Compound Power - Haftada 2 Gün)",
    "weekly_frequency": 2,
    "rest_between_heavy_sets_sec": (120, 180),  # ATP-CP fosfojen sisteminin tam toparlanması
    "rest_between_accessories_sec": (60, 90),
    "target_rpe": (7.5, 8.5),  # RIR 1-2 (Cebinde 1-2 tekrar kalsın, tükenişe gitme)
    "progressive_overload_rule": (
        "Bir harekette 5x5 temiz formla tamamlandığında sonraki seansta "
        "üst vücuda +2.5 kg, alt vücuda +2.5 ila +5.0 kg eklenir."
    ),
    "core_lifts_progression": {
        "back_squat": {
            "history": ["45.0 kg (06 Kas)", "55.0 kg (08 Kas)", "57.5 kg (10 Kas)", "60.0 kg (12 Kas)", "65.0 kg (17 Kas - 5x5 PR)"],
            "delta": "+20.0 kg (11 günde rekor)",
            "next_target": "67.5 kg x 5 tekrar x 5 set"
        },
        "bench_press": {
            "history": ["45.0 kg (06 Kas)", "50.0 kg (10 Kas - 4 set)", "50.0 kg (17 Kas - 5x5 Tamamlandı)"],
            "delta": "+5.0 kg (5x5 kilitlendi)",
            "next_target": "52.5 kg x 5 tekrar x 5 set (Yeni PR Denemesi)"
        },
        "barbell_row": {
            "history": ["45.0 kg (06 Kas)", "55.0 kg (10 Kas)", "60.0 kg (17 Kas - 5x5)"],
            "delta": "+15.0 kg",
            "next_target": "62.5 kg x 5 tekrar x 5 set"
        },
        "overhead_press": {
            "history": ["35.0-37.0 kg (08 Kas)", "37.5-40.0 kg (12 Kas)"],
            "delta": "+5.0 kg",
            "next_target": "40.0 kg x 5 tekrar x 5 set (Tüm setlerde)"
        },
        "deadlift": {
            "history": ["50.0 kg x 6 (08 Kas)", "60.0 kg x 5 (12 Kas)"],
            "delta": "+10.0 kg",
            "next_target": "65.0 kg x 5 tekrar (1 ana ağır set)"
        },
        "lat_pulldown": {
            "history": ["40.0-45.0 kg (08 Kas)", "45.0 kg x 12 (12 Kas)"],
            "delta": "+5.0 kg",
            "next_target": "45.0-50.0 kg x 12 tekrar x 4 set"
        },
        "lateral_raise": {
            "history": ["15.0-20.0 kg (06 Kas)", "20.0-25.0 kg (17 Kas)"],
            "delta": "Stabil Güç",
            "next_target": "22.5-25.0 kg x 12-13 tekrar x 3 set"
        },
        "shrug": {
            "history": ["35.0-45.0 kg (06 Kas)", "45.0 kg x 12 (17 Kas)"],
            "delta": "Stabil 45 kg",
            "next_target": "45.0 kg x 12 tekrar x 3 set"
        }
    }
}

# ==============================================================================
# 4. KOŞU, 80/20 POLARİZE MODEL VE ZONE 2 FİZYOLOJİSİ
# ==============================================================================
# Kardiyak Verimlilik Faktörü Formülü:
# EF = Hız (metre / dakika) / Kalp Atım Hızı (bpm)
# Güncel Zone 2 (6:40 /km = 150 m/dk @ 145 bpm) -> EF = 150 / 145 = 1.034 m/beat
# Hedef Zone 2 (5:00 /km = 200 m/dk @ 145 bpm) -> EF = 200 / 145 = 1.379 m/beat (+%33.4 verimlilik artışı)
# Firstbeat Yük Dağılımı Gerçeği:
# Yüksek Aerobik yükü (High Aerobic) 537.8 birimle hedefin üst bandındadır.
# Yelken ve basketbol anaerobik ve yüksek aerobik sistemi besler; Zone 2 sol ventrikül
# atım hacmini (stroke volume) ve mitokondriyel yoğunluğu inşa eder.

RUNNING_PRINCIPLES: Dict[str, Any] = {
    "distribution_rule": "80/20 Polarize Model (Haftalık 2 koşunun 1'i Zone 2 Taban, 1'i Hız İntervali/Eşik)",
    "weekly_frequency": 2,
    "zone2_heart_rate_range": (140, 150),
    "zone2_pace_current": "6:35 - 6:50 /km",
    "zone2_efficiency_factor_current": 1.03,  # metre / nabız atımı
    "zone2_target_pace": "5:00 /km",
    "zone2_efficiency_factor_target": 1.38,   # +%33 kardiyovasküler verimlilik
    "interval_workout_structure": "10 dk ısınma + 4x1.000m @ 5:15 /km (172-180 bpm, 3 dk dinlenme) + 8 dk soğuma",
    "cadence_target_spm": (160, 165),         # Kasım'da 162 spm yakalandı, korunmalı
    "ground_contact_time_target_ms": 270,     # 291'den 273.5 ms'ye indi
    "z2_pace_5min_timeline": {
        "december_2026": "6:10 - 6:20 /km @ 145 bpm (~85 kg)",
        "january_february_2027": "5:35 - 5:50 /km @ 145 bpm (~83 kg)",
        "march_april_2027": "5:00 - 5:15 /km @ 145 bpm (~80-81 kg, 35-40 km/hf taban)"
    },
    "load_focus_physiological_truth": (
        "Garmin Firstbeat verilerine göre Yüksek Aerobik yükünüz zaten 537.8 birimle "
        "en yüksek kategorinizdir. Haftalık 1 interval koşusu, 2.5-4 saatlik rüzgarlı yelken "
        "ve basketbol maçları High Aerobic ihtiyacını fazlasıyla doyurmaktadır. "
        "Zone 2 koşuları ise bu yapının eksik olan aerobik tabanını (mitokondri ve sol ventrikül) inşa eder."
    )
}

# ==============================================================================
# 5. AYNI GÜN KOŞU VE KUVVET SIRALAMASI KANUNU (GARMIN VERİ KANITI)
# ==============================================================================
# Eşzamanlı Antrenman Girişimi (Interference Effect):
# Salonda ağır bacak/gövde çalışması sonrası yapılan koşularda kas glikojeni tükendiği
# için kardiyak drift oluşur (+7 bpm nabız sıçraması, Zone 4 süresi %26.5'ten %50.0'a çıkar).
# Kanun: Önce koşu, sonra kuvvet (veya seanslar arasına en az 6 saat rejenerasyon penceresi koy).

SAME_DAY_SEQUENCE_LAW: Dict[str, Any] = {
    "rule": "ÖNCE KOŞU, ARDINDAN KUVVET ANTRENMANI (Veya araya en az 6 saat koy)",
    "data_evidence": {
        "strength_first_then_run": {
            "dates": ["10 Kasım", "12 Kasım"],
            "avg_hr_spike": "+7 bpm (168 bpm)",
            "zone4_percentage": "50.0% (İki katına çıktı)",
            "fatigue_state": "Yorgun kaslarla aşırı kardiyovasküler stres ve sakatlık riski"
        },
        "run_first_then_strength": {
            "dates": ["06 Kasım", "08 Kasım"],
            "avg_hr_stability": "159 - 161 bpm stabil",
            "zone4_percentage": "25.0% - 28.0% (Normal)",
            "fatigue_state": "Düşük yorgunluk, salonda hedeflenen ağırlıkların rahat kaldırılması"
        }
    }
}

# ==============================================================================
# 6. YELKEN VE BASKETBOL PROTOKOLLERİ (SPONTANE / İSTEĞE BAĞLI BRANŞLAR)
# ==============================================================================
# Temel Politika: Haftalık mikro-döngü ve sabit takvimde YALNIZCA 2 Koşu + 2 Gym yer alır.
# Yelken ve Basketbol spontane sporlardır. Yapıldıkça saatin telemetrisi çekilip analiz edilir.

CROSS_SPORTS_PROTOCOLS: Dict[str, Any] = {
    "schedule_policy": "Düzenli takvimde YALNIZCA Koşu ve Gym bulunur. Yelken ve Basketbol isteğe bağlıdır.",
    "sailing": {
        "is_scheduled_regular": False,
        "type": "Spontane / Dönemsel Branş",
        "total_sessions_93d": 12,
        "total_duration_hours": 28.1,
        "total_sweat_loss_liters": 16.6,
        "avg_sweat_per_session_liters": 1.38,
        "max_sweat_single_day_liters": 3.1,  # Çeşme / İzmir kampları
        "hydration_rule": "Saat başı 500-600 mL su + 500-800 mg sodyum içeren elektrolit",
        "pre_workout_nutrition": "Seans öncesi 90 dk önce 70-80g kompleks karbonhidrat",
        "conditioning_focus": "Önkol tutuş gücü (Farmer's Walk, Dead Hang) ve Trapez/Hiking core anti-rotasyonu"
    },
    "basketball": {
        "is_scheduled_regular": False,
        "type": "Spontane / Dönemsel Branş",
        "total_matches_93d": 5,
        "avg_heart_rate_bpm": (128, 144),
        "physiological_role": "Doğal anaerobik Zone 4-5 HIIT kondisyon seansı",
        "leg_clash_rule": "Basketbol oynanacak gün ASLA ağır bacak (Squat/Deadlift) yapılmaz",
        "injury_prevention": "10 dk dinamik ayak bileği ısınması, maç sonu 10 dk statik baldır esnemesi"
    }
}

# ==============================================================================
# 7. UYKU, SİRKADİYEN RİTİM VE GARMIN SAAT AYARLARI
# ==============================================================================
# Garmin verileri: 01:45 sonrası yatışlarda sabah 08:25 kalkışı sabit kaldığından
# REM uykusu %32.2 kaybedilmekte, sabah Body Battery puanı 20-23 puan düşük başlamaktadır.

RECOVERY_AND_WATCH_SETTINGS: Dict[str, Any] = {
    "sleep_principles": {
        "fixed_wake_up_time": "08:20 - 08:35",
        "target_bedtime": "00:30 - 00:45",
        "late_bedtime_penalty": (
            "01:45 sonrasında yatılan gecelerde sabah uyanış sabit kaldığı için "
            "REM uykusu %32.2 azalarak 1.18 saate düşmekte, sabah Body Battery "
            "ve Hazırlık puanı 20-23 puan gerilemektedir."
        )
    },
    "garmin_settings_to_fix": [
        {"num": 1, "name": "Dinlenik Nabız (RHR)", "fix": "Otomatik Ortalama (~53 bpm) - 65 bpm sabit kalmış"},
        {"num": 2, "name": "Koşu FTP (Eşik Gücü)", "fix": "340-345 W (87 kg ile uyumlu) - 374 W kalmış"},
        {"num": 3, "name": "Koşu Nabız Profili", "fix": "Özel Koşu (RUNNING) Profili Ekle"},
        {"num": 4, "name": "Yoğunluk Dakikası", "fix": "Otomatik (AUTO) Modu (Z1-Z2 seansları kaybolmasın)"},
        {"num": 5, "name": "Uyku Penceresi", "fix": "00:30 - 08:30 (Eski 00:00-08:00 yerine)"},
        {"num": 6, "name": "İrtifa Düzeltmesi", "fix": "Açık (Sahil koşularında eğim gücü hesaplansın)"},
        {"num": 7, "name": "Kilo Girişi", "fix": "Haftada 2 sabah tartımı düzenli girilmeli"},
        {"num": 8, "name": "Hava/Konum İzni", "fix": "'Her Zaman' izin verilmeli"}
    ]
}

# ==============================================================================
# 8. ÇOK SEVİYELİ SPORCU VE DİNAMİK GELİŞİM ÇERÇEVESİ (DOGMATİK OLMAMA İLKESİ)
# ==============================================================================
# Sporcu programları sabit kalıplar değildir. Seviyeye göre farklılaşır:
# - Başlangıç: Koş-Yürü, Saf Z1-Z2, Vücut Ağırlığı & Dambıl (2 Koşu + 1 Gym)
# - Orta (Sarp): 80/20 Polarize Koşu, A/B 5x5 Bileşik Kuvvet (2 Koşu + 2 Gym)
# - İleri: Piramidal / Eşik, Üst/Alt Vücut veya PPL Split (3-4 Koşu + 3-4 Gym)
# - Elit: Blok Periyodizasyonu, Çift Seanslar, Pliometri (5-6 Koşu + 2 Gym)

ATHLETE_LEVELS_FRAMEWORK: Dict[str, Dict[str, str]] = {
    "beginner": {
        "level_tr": "Başlangıç Seviyesi (Temel Adaptasyon & Fonksiyonellik)",
        "target_audience": "Yeni başlayanlar, uzun süre ara verenler veya spora yeni dönenler",
        "running_approach": "Koş-Yürü (Run/Walk - 2-3 dk koşu / 2 dk yürüyüş) veya Saf Zone 1-2 (Konuşma temposu). Yüksek şiddetli interval ASLA verilmez.",
        "running_frequency": "Haftada 2-3 gün (25-35 dk seanslar)",
        "strength_approach": "Vücut ağırlığı, direnç bantları ve hafif dambıllarla temel hareket kalıpları (Squat, Hinge, Push, Pull, Lunge, Core). 2-3 set x 10-15 tekrar.",
        "strength_frequency": "Haftada 1-2 gün (Tüm Vücut / Full Body)",
        "recommended_split": "2 Koşu/Yürüyüş + 1 Kuvvet (3 gün dinlenme/toparlanma)",
        "progression_gate": "Kesintisiz 30-40 dk Zone 2 koşabilmek ve temel hareketlerde form bozulmadan 3x12 vücut ağırlığı squat/şınav yapabilmek."
    },
    "intermediate": {
        "level_tr": "Orta Seviye (Gelişim, Güç & Aerobik Taban - Sarp'ın Mevcut Seviyesi)",
        "target_audience": "Temel kardiyovasküler altyapısı olan, düzenli ağırlık kaldıran sporcular",
        "running_approach": "80/20 Polarize Model (1 Seans Zone 2 Taban 45-50 dk + 1 Seans 5K Hız/VO2Max İntervali örn. 4x1000m).",
        "running_frequency": "Haftada 2 gün (Toplam 15-22 km/hafta)",
        "strength_approach": "A/B Full Body Alternating 5x5 Bileşik Kuvvet (Squat, Bench Press, Barbell Row, OHP, Deadlift). Progressive overload odaklı.",
        "strength_frequency": "Haftada 2 gün (A ve B günleri)",
        "recommended_split": "2 Koşu + 2 Gym (4 gün antrenman, 3 gün dinlenme/rejenerasyon)",
        "progression_gate": "Squat vücut ağırlığının 1.2 katına, Deadlift 1.5 katına ulaştığında ve 5x5 lineer artışı tükendiğinde; Zone 2 temposu 5:30/km'ye yaklaştığında."
    },
    "advanced": {
        "level_tr": "İleri Seviye (Hacim Artırımı, Bölünmüş Rutinler & Eşik Dönemlemesi)",
        "target_audience": "Yıllık antrenman sürekliliği olan, daha yüksek hacmi tolere edebilen deneyimli sporcular",
        "running_approach": "Piramidal veya Eşik Odaklı Dönemleme (2x Zone 2 Taban, 1x Tempo/Laktat Eşik Koşusu, 1x VO2Max İntervali).",
        "running_frequency": "Haftada 3-4 gün (Toplam 30-45 km/hafta)",
        "strength_approach": "5x5'ten Üst/Alt Vücut (Upper/Lower Split - 4 Gün) veya İtiş-Çekiş-Bacak (PPL - 3-5 Gün) bölünmesine geçiş. RPE/RIR takibi ve dalgalı periyodizasyon.",
        "strength_frequency": "Haftada 3-4 gün",
        "recommended_split": "3 Koşu + 2 Gym veya 2 Koşu + 4 Gym (5-6 gün antrenman, 1-2 gün toparlanma)",
        "progression_gate": "5K süresi <22 dk, haftalık 40+ km rahat tolere edilebilmesi."
    },
    "elite": {
        "level_tr": "Elit / Performans & Yarışmacı Seviyesi (Blok Dönemlemesi & Zirve)",
        "target_audience": "Yarış odaklı atletler, performans sporcuları",
        "running_approach": "Blok Periyodizasyonu, yarış temposu blokları, çift seanslar (Sabah toparlanma koşusu + Akşam eşik koşusu).",
        "running_frequency": "Haftada 5-6 gün (Toplam 60-85+ km/hafta)",
        "strength_approach": "Maksimal kuvvet blokları, pliometri, RFD (Kuvvet Üretim Hızı), patlayıcı güç ve sakatlık önleyici prehab.",
        "strength_frequency": "Haftada 2 gün (Koşuyu bozmayacak patlayıcı/koruyucu mikro-dozlar)",
        "recommended_split": "5 Koşu + 2 Patlayıcı Kuvvet (Çift seans modülleri)",
        "progression_gate": "Yarış zirveleme (Peaking & Tapering) takvimi."
    }
}

DYNAMIC_PROGRESSION_TRIGGERS: Dict[str, Dict[str, Any]] = {
    "volume_increase": {
        "name": "Gün / Hacim Artırma Kriterleri",
        "criteria": [
            "Son 4 haftalık ACWR (Akut/Kronik Yük Oranı) 0.90 - 1.20 arasında stabil kalması",
            "Dinlenik nabzın (RHR) plato yapması veya düşüş eğiliminde olması",
            "Gecelik HRV ve toparlanma skorunun (Recovery Score) sürekli >75 olması",
            "Antrenman sonrası kas ağrısının (DOMS) 24 saat içinde tamamen geçmesi"
        ],
        "action": "Haftalık antrenman gün sayısını 1 artır: Örneğin 2 koşudan 3 koşuya (hafif 30 dk toparlanma koşusu ekleyerek) veya 2 gym'den 3 gym'e geç."
    },
    "style_shift": {
        "name": "Antrenman Stili & Dönemleme Değiştirme Kriterleri",
        "criteria": [
            "5x5 lineer artışında aynı ağırlıkta 3 seans üst üste takılma ve deload sonrası da ilerleyememe (Lineer Plato)",
            "Kuvvet antrenmanında estetik ve bölgesel hipertrofi odağının artması",
            "Zone 2 koşu temposunun 6:00 /km altına inmesi ve aerobik tabanın kemikleşmesi"
        ],
        "action": "Kuvvette A/B 5x5'ten 'Üst/Alt Vücut (Upper/Lower)' veya 'PPL' sistemine geç; Koşuda saf polarizeden 1 gün 'Laktat Eşik / Tempo Koşusu' eklemeye geç."
    },
    "deload_and_recovery": {
        "name": "Geri Adım Atma & Deload Kriterleri (Dogmatik Olmayan Esneklik)",
        "criteria": [
            "ACWR > 1.35 (Tehlikeli akut yük sıçraması)",
            "Gecelik HRV'nin 3 gün üst üste taban çizgisinin %15 altında kalması",
            "Dinlenik nabzın (RHR) normalden +4 bpm yüksek çıkması",
            "Uyku skorunun <65 ve subjektif yorgunluğun yüksek olması"
        ],
        "action": "Planlanan ağır seansı dogmatik şekilde zorlama! Seansı hafif yürüyüş/esnemeye çevir veya o haftanın antrenman hacmini %40-50 azalt (Deload Haftası)."
    }
}

# ==============================================================================
# 9. İLETİŞİM, ESTETİK VE RAPORLAMA İLKELERİ
# ==============================================================================
PRESENTATION_RULES: Dict[str, str] = {
    "computational_rigor": (
        "Arka planda tüm karmaşık ara elemanlar, matematiksel istatistikler (ACWR akut/kronik oranları, "
        "Firstbeat EPOC yük odakları, kardiyak verimlilik faktörü EF = hız/nabız, Pearson korelasyon matrisi, "
        "PGFPlots koordinatları, çeyreklikler, regresyon eğimleri, uyku evresi dakikaları) tavizsiz, eksiksiz "
        "ve en derin matematiksel hassasiyetle hesaplanmaya devam eder."
    ),
    "user_facing_explanation": (
        "Kullanıcıya açıklarken bu karmaşık ara formüller yerine doğrudan NET SONUÇLAR (Ne tespit ettik?) "
        "ve YAPILMASI GEREKEN EYLEMLER (Bugün/yarın sahada veya salonda tam olarak ne yapmalısın?) "
        "sporcunun anlayacağı, sade, doğrudan ve pratik bir dille aktarılır."
    ),
    "tone": "Atletik, doğrudan, motive edici, bilime dayalı ve anlaşılır (Aşırı akademik veya robotik jargon yok)",
    "report_headers": "Kısa, estetik ve işlevsel başlıklar (Üstbilgide uzun monografi/profil ID başlıkları kaldırıldı)",
    "page_budget": "Executive 8 sayfa tam düzen (Taşma, boş sayfa veya yetim başlık bırakılmaz)",
    "real_data_constraint": "Asla uydurma/jenerik egzersiz önerilmez; daima saatin sensörlerinden çekilen gerçek ağırlıklar ve gerçek takvim tarihleri kullanılır."
}
