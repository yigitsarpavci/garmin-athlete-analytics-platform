#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Garmin Sporcu İlkeleri ve Sistem Hafızası (Athlete Principles & Core Memory)
================================================================================

Bu modül, antrenman bilimi ilkelerinin (seviye çerçevesi, dinamik ilerleme tetikleyicileri,
sunum kuralları) ve sporcuya özel ilkelerin üretildiği yerdir.

ÖNEMLİ: Bu dosyada KİŞİYE ÖZEL değer (yaş, boy, kilo, PR, tempo, tarih) YOKTUR.
Sporcuya özel her şey `build_athlete_principles(engine)` ile çalışma anında şu kaynaklardan türetilir:
  - Profil (yaş, boy, hedef kilo): athlete_profile.json / Garmin kullanıcı ayarları (bkz. athlete_profile.py)
  - Fizyoloji ve tempo: kullanıcının kendi Garmin verisi (maks nabız, EF, 5K derecesi ...)
  - Kuvvet: Garmin set verisinden hesaplanan progresyon
Böylece başka biri kendi Garmin verisini yüklediğinde her şey kendi değerleriyle gelir.

Mimari Prensipler:
1. Arka Planda Derin İstatistik: ACWR, EPOC, EF (Hız/Nabız) formülleri matematiksel kesinlikle hesaplanır.
2. Ön Planda Sade Sporcu Dili: Karmaşık ara denklemler yerine doğrudan sahadaki eylem sunulur.
3. Telemetri Gerçekliği: Jenerik veya uydurma egzersizler yerine Garmin sensörlerinden alınan gerçek veriler kullanılır.
4. Dogmatik Olmayan Gelişim: Hacim ve periyodizasyon anlık toparlanma sinyallerine göre dinamik evrilir.
"""

from typing import Any, Dict, List


# ==============================================================================
# SPORCUYA ÖZEL İLKELERİN ÇALIŞMA ANINDA ÜRETİMİ
# ==============================================================================

def _bmr_mifflin(weight_kg: float, height_cm: float, age: int, gender: str) -> int:
    """Mifflin-St Jeor: erkek +5, kadın -161."""
    return int(round(10 * weight_kg + 6.25 * height_cm - 5 * age + (-161 if gender == "female" else 5)))


def build_athlete_profile(engine: Any) -> Dict[str, Any]:
    """Profil, Garmin tartı geçmişi ve fizyolojik eşiklerden sporcunun güncel biyometrik özetini üretir."""
    prof = engine.profile
    phys = engine.get_physiology()
    cur_w = engine.get_current_weight()
    start_w = engine.get_start_weight()
    h2 = engine.height_m2
    who_max_kg = round(24.99 * h2, 2)
    hist = engine.get_weight_history()
    days = 0
    if len(hist) >= 2:
        from datetime import datetime
        days = (datetime.strptime(hist[-1]["date"], "%Y-%m-%d") - datetime.strptime(hist[0]["date"], "%Y-%m-%d")).days
    lost = round(start_w - cur_w, 1)
    target = engine.get_target_weight()
    vo2_vals = [
        float(p["generic"]["vo2MaxPreciseValue"]) for p in (engine.vo2max_history or [])
        if isinstance(p, dict) and isinstance(p.get("generic"), dict) and p["generic"].get("vo2MaxPreciseValue")
    ]
    return {
        "name": prof.get("name"),
        "age": engine.age,
        "gender": prof.get("gender", "male"),
        "height_cm": engine.height_cm,
        "starting_weight_kg": start_w,
        "current_weight_kg": cur_w,
        "weight_lost_kg": lost,
        "days_elapsed": days,
        "weight_loss_rate_kg_per_week": round(lost / (days / 7.0), 2) if days >= 7 else None,
        "current_bmi": round(cur_w / h2, 2),
        "who_normal_bmi_max_kg": who_max_kg,
        "remaining_to_normal_bmi_kg": round(max(0.0, cur_w - who_max_kg), 2),
        "target_weight_optimal_kg": target,
        "target_weight_range_kg": (round(target - 1.0, 1), round(target + 2.0, 1)),
        "resting_heart_rate_actual": phys["rhr"],
        "max_heart_rate_actual": phys["max_hr"],
        "lactate_threshold_hr": phys["lthr"],
        "vo2max_current": vo2_vals[-1] if vo2_vals else None,
        "vo2max_first": vo2_vals[0] if vo2_vals else None,
        "profile_sources": prof.get("sources"),
        "profile_missing": prof.get("missing"),
    }


def build_nutrition_principles(engine: Any) -> Dict[str, Any]:
    """Profil ve güncel kiloya göre Mifflin-St Jeor tabanlı enerji ve makro hedefleri (kişisel sabit yok)."""
    w = engine.get_current_weight()
    bmr = _bmr_mifflin(w, engine.height_cm, engine.age, engine.profile.get("gender", "male"))
    tdee = (round(bmr * 1.48), round(bmr * 1.60))  # hafif-orta aktif PAL 1.48 - 1.60
    deficit = (400, 550) if w > engine.get_target_weight() else (0, 0)
    intake = (tdee[0] - deficit[1], tdee[1] - deficit[0]) if deficit[1] else tdee
    return {
        "bmr_kcal": bmr,
        "tdee_range_kcal": tdee,
        "target_calorie_intake_kcal": intake,
        "target_deficit_kcal": deficit,
        "protein_g_per_day": (round(2.0 * w), round(2.1 * w)),  # 2.0 - 2.1 g/kg: açıkta yağsız kütleyi korur
        "carbs_g_per_day": (round(3.0 * w), round(3.5 * w)),
        "fat_g_per_day": (round(0.8 * w), round(0.95 * w)),
        "water_daily_liters": (2.5, 3.5),
        "crash_diet_warning": (
            "Kas kaybını önlemek için haftalık kilo verme hızı -0.55 kg/hafta civarında tutulmalı; "
            "kalori açığı 550 kcal üzerine çıkmamalıdır."
        ),
    }


def build_strength_principles(engine: Any) -> Dict[str, Any]:
    """Garmin set verisinden hesaplanan gerçek progresyon (geçmiş, değişim, sonraki hedef)."""
    prog = (engine.get_gym_exercise_history() or {}).get("progression", {})
    keys = {
        "back_squat": "squat", "bench_press": "bench", "barbell_row": "row", "overhead_press": "ohp",
        "deadlift": "deadlift", "lat_pulldown": "lat_pulldown", "lateral_raise": "lateral_raise", "shrug": "shrug",
    }
    lifts = {}
    for out_key, k in keys.items():
        p = prog.get(k) or {}
        lifts[out_key] = {
            "history": p.get("history", []),
            "delta": p.get("delta", "Veri Bekleniyor"),
            "next_target": p.get("next_target", "--"),
        }
    return {
        "routine_name": "A/B Full Body Alternating Split (5x5 Compound Power - Haftada 2 Gün)",
        "weekly_frequency": 2,
        "rest_between_heavy_sets_sec": (120, 180),  # ATP-CP fosfojen sisteminin tam toparlanması
        "rest_between_accessories_sec": (60, 90),
        "target_rpe": (7.5, 8.5),  # RIR 1-2
        "progressive_overload_rule": (
            "Bir harekette 5x5 temiz formla tamamlandığında sonraki seansta "
            "üst vücuda +2.5 kg, alt vücuda +2.5 ila +5.0 kg eklenir."
        ),
        "core_lifts_progression": lifts,
    }


def build_running_principles(engine: Any) -> Dict[str, Any]:
    """Nabız bantları ve tempolar sporcunun kendi maksimum nabzından ve verimlilik faktöründen türetilir."""
    z = engine.get_training_zones()
    mx = engine.get_physiology()["max_hr"]
    z2_lo, z2_hi = int(round(0.69 * mx)), int(round(0.74 * mx))
    return {
        "distribution_rule": "80/20 Polarize Model (Haftalık 2 koşunun 1'i Zone 2 Taban, 1'i Hız İntervali/Eşik)",
        "weekly_frequency": 2,
        "zone2_heart_rate_range": (z2_lo, z2_hi),
        "zone2_pace_current": z["[[Z2_PACE]]"],
        "interval_workout_structure": f"10 dk ısınma + 4x1.000m @ {z['[[INT_PACE]]']} ({z['[[INT_HR]]']}, 3 dk dinlenme) + 8 dk soğuma",
        "cadence_target_spm": (160, 165),
        "goal_5k": engine.get_goal_5k()["label"],
    }


def build_same_day_sequence_law(engine: Any) -> Dict[str, Any]:
    """Genel kural + sporcunun kendi aynı-gün (koşu + kuvvet) seanslarından çıkan veri kanıtı."""
    return {
        "rule": "ÖNCE KOŞU, ARDINDAN KUVVET ANTRENMANI (Veya araya en az 6 saat koy)",
        "rationale": (
            "Ağır bacak/gövde çalışması sonrası koşuda kas glikojeni azaldığı için kardiyak drift oluşur "
            "(nabız yükselir, Zone 4 süresi artar)."
        ),
        "data_evidence": engine.get_same_day_sequence(),
    }


def build_cross_sports_protocols(engine: Any) -> Dict[str, Any]:
    """Koşu/kuvvet dışındaki spontane branşlar: yalnızca sporcunun gerçekten yaptıkları (Garmin verisinden)."""
    detected: List[Dict[str, Any]] = []
    if not engine.adf_3m.empty:
        core = {"running", "treadmill_running", "trail_running", "track_running", "strength_training", "fitness_equipment"}
        for sport, grp in engine.adf_3m.groupby("sport"):
            if str(sport).lower() in core:
                continue
            detected.append({
                "sport": str(sport),
                "sessions_93d": int(len(grp)),
                "total_duration_hours": round(float(grp["dur_m"].sum()) / 60.0, 1),
                "avg_heart_rate_bpm": int(round(float(grp["avg_hr"].replace(0, float("nan")).mean()))) if grp["avg_hr"].replace(0, float("nan")).notna().any() else None,
                "total_sweat_loss_liters": round(float(grp["water_ml"].sum()) / 1000.0, 1),
                "is_scheduled_regular": False,
            })
    return {
        "schedule_policy": "Düzenli takvimde YALNIZCA Koşu ve Gym bulunur. Diğer branşlar isteğe bağlıdır; yapıldıkça Garmin verisinden analiz edilir.",
        "hydration_rule": "Uzun seanslarda saat başı 500-600 mL su + 500-800 mg sodyum içeren elektrolit",
        "leg_clash_rule": "Yüksek eksantrik/anaerobik bacak yükü olan branş (maç, kayak) gününde ağır bacak (Squat/Deadlift) yapılmaz",
        "detected_sports": detected,
    }


def build_recovery_and_watch_settings(engine: Any) -> Dict[str, Any]:
    """Uyku düzeni sporcunun kendi ortalamasından; saat ayarları kişisel eşiklerinden (RHR, FTP, uyku) üretilir."""
    df = engine.df
    sleep: Dict[str, Any] = {}
    if not df.empty and df["sleep_start_hr"].notna().any() and df["sleep_end_hr"].notna().any():
        from engine.helpers import fmt_clock  # noqa: WPS433 (döngüsel içe aktarmayı önlemek için yerel)
        sleep = {
            "typical_bedtime": fmt_clock(float(df["sleep_start_hr"].mean())),
            "typical_wake_up_time": fmt_clock(float(df["sleep_end_hr"].mean())),
        }
    return {
        "sleep_principles": {
            **sleep,
            "late_bedtime_penalty": (
                "Geç yatılan gecelerde sabah uyanış sabit kaldığı için REM uykusu azalır ve sabah Body Battery / "
                "Hazırlık puanı geriler; ayrıntılar Analizler > Uyku sekmesinde canlı hesaplanır."
            ),
        },
        "garmin_settings_to_fix": engine.get_garmin_settings_to_fix(),
    }


def build_athlete_principles(engine: Any) -> Dict[str, Any]:
    """`/api/principles` yanıtı: genel çerçeveler + sporcuya özel, veriden türetilmiş ilkeler."""
    return {
        "profile": build_athlete_profile(engine),
        "nutrition": build_nutrition_principles(engine),
        "strength": build_strength_principles(engine),
        "running": build_running_principles(engine),
        "same_day_sequence": build_same_day_sequence_law(engine),
        "cross_sports": build_cross_sports_protocols(engine),
        "recovery_and_watch": build_recovery_and_watch_settings(engine),
        "presentation": PRESENTATION_RULES,
        "athlete_levels": ATHLETE_LEVELS_FRAMEWORK,
        "progression_triggers": DYNAMIC_PROGRESSION_TRIGGERS,
    }


# ==============================================================================
# 8. ÇOK SEVİYELİ SPORCU VE DİNAMİK GELİŞİM ÇERÇEVESİ (DOGMATİK OLMAMA İLKESİ)
# ==============================================================================
# Sporcu programları sabit kalıplar değildir. Seviyeye göre farklılaşır:
# - Başlangıç: Koş-Yürü, Saf Z1-Z2, Vücut Ağırlığı & Dambıl (2 Koşu + 1 Gym)
# - Orta: 80/20 Polarize Koşu, A/B 5x5 Bileşik Kuvvet (2 Koşu + 2 Gym)
# - İleri: Piramidal / Eşik, Üst/Alt Vücut veya PPL Split (3-4 Koşu + 3-4 Gym)
# - Elit: Blok Periyodizasyonu, Çift Seanslar, Pliometri (5-6 Koşu + 2 Gym)

ATHLETE_LEVELS_FRAMEWORK: Dict[str, Dict[str, str]] = {
    "beginner": {
        "level_tr": "Başlangıç Seviyesi (Temel Adaptasyon & Hareket Kalıbı)",
        "target_audience": "Yeni başlayanlar, uzun süre ara verenler veya spora yeni dönenler",
        "running_approach": "Koş-Yürü (Run/Walk - 2-3 dk koşu / 2 dk yürüyüş) veya Saf Zone 1-2 (Konuşma temposu). Yüksek şiddetli interval ASLA verilmez.",
        "running_frequency": "Haftada 2-3 gün (25-35 dk seanslar)",
        "strength_approach": "Vücut ağırlığı, direnç bantları ve hafif barbell/dambılla temel hareket kalıpları (Squat, Hinge, Push, Pull, Lunge, Core). 2-3 set x 10-15 tekrar veya hafif 5x5 adaptasyonu.",
        "strength_frequency": "Haftada 1-2 gün (Tüm Vücut / Full Body)",
        "recommended_split": "2 Koşu/Yürüyüş + 1 Kuvvet (3 gün dinlenme/toparlanma)",
        "progression_gate": "Kesintisiz 30 dk rahat koşabilmek; Squat/Deadlift'te ~0.60x–0.70x Vücut Ağırlığı, Bench'te ~0.50x VA ile 5x5 nizami form yakalamak."
    },
    "intermediate": {
        "level_tr": "Gelişim & Orta Seviye (Lineer 5x5 İnşası & 80/20 Polarize Koşu)",
        "target_audience": "Temel kardiyovasküler altyapısı olan, düzenli 5x5 bileşik kuvvet inşa eden sporcular",
        "running_approach": "80/20 Polarize Model (1 Seans Zone 2 Taban 45-50 dk + 1 Seans 5K Hız/VO2Max İntervali örn. 4x1000m).",
        "running_frequency": "Haftada 2 gün (Toplam 15-22 km/hafta)",
        "strength_approach": "A/B Full Body Alternating 5x5 Bileşik Kuvvet (Mevcut güç oranların Kuvvet sekmesinde canlı hesaplanır). Önce Squat/Deadlift'te 1.0x, Bench'te 0.8x vücut ağırlığına lineer +2.5 kg artışla ulaşma fazı.",
        "strength_frequency": "Haftada 2 gün (A ve B günleri)",
        "recommended_split": "2 Koşu + 2 Gym (4 gün antrenman, 3 gün dinlenme/rejenerasyon)",
        "progression_gate": "Kuvvette vücut ağırlığından fazla yük şartı YOKTUR: İlk hedef Squat/Deadlift'i 1.0x VA'ya, Bench'i 0.80x VA'ya taşımak; Koşuda 5K derecesini ~%15 iyileştirmek ve Zone 2 temposunu kademeli hızlandırmaktır."
    },
    "advanced": {
        "level_tr": "İleri Seviye (Bölünmüş Rutinler & Eşik Dönemlemesi)",
        "target_audience": "Yıllık antrenman sürekliliği olan, daha yüksek hacmi tolere edebilen deneyimli sporcular",
        "running_approach": "Piramidal veya Eşik Odaklı Dönemleme (2x Zone 2 Taban, 1x Tempo/Laktat Eşik Koşusu, 1x VO2Max İntervali).",
        "running_frequency": "Haftada 3-4 gün (Toplam 30-45 km/hafta)",
        "strength_approach": "5x5'ten Üst/Alt Vücut (Upper/Lower Split - 4 Gün) veya İtiş-Çekiş-Bacak (PPL - 3-5 Gün) bölünmesine geçiş. RPE/RIR takibi ve dalgalı periyodizasyon.",
        "strength_frequency": "Haftada 3-4 gün",
        "recommended_split": "3 Koşu + 2 Gym veya 2 Koşu + 4 Gym (5-6 gün antrenman, 1-2 gün toparlanma)",
        "progression_gate": "Squat ≥ 1.0x VA ve Bench ≥ 0.80x VA 5x5 lineer artışı tükendiğinde; 5K hedefine yaklaşıldığında ve haftalık 4/4 kota en az 4 hafta kesintisiz tamamlandığında geçilir."
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
            "Mevcut 2 Koşu + 2 Kuvvet (4/4) kotasının en az 4 hafta kesintisiz ve plan sapmasız tamamlanması",
            "Kuvvet temel gücünün vücut ağırlığı eşiğine ulaşması (Squat ≥ 1.0x VA, Bench ≥ 0.80x VA) veya Zone 2'nin ≤ 6:00 /km bandına oturması",
            "Son 4 haftalık ACWR (Akut/Kronik Yük Oranı) 0.90 - 1.20 arasında stabil ve toparlanma skorunun >75 kalması",
            "Kalori açığının kapanması veya ek yükte DOMS'un 24 saat içinde tamamen geçmesi"
        ],
        "action": "Bu eşikler dolmadan 5. gün EKLENMEZ (2 Koşu + 2 Kuvvet korunur). Eşik sağlandığında haftaya 1 hafif 30 dk toparlanma koşusu veya 3. kuvvet günü eklenir."
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
