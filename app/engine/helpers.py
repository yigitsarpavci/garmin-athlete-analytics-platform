#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin Veri ve Performans Hesaplama Motoru (Kapsamlı Sürüm)
93 günlük günlük sağlık özetleri, 88 gecelik uyku ve HRV kayıtları ve 49 antrenmanı
bütünleşik bir analitik yapıda işler; forma girme projeksiyonları, korelasyonlar,
aynı gün sıra analizleri ve branş gelişim stratejilerini üretir.
"""

import copy
import functools
import os
import sys
from typing import Dict, Optional, Any
import numpy as np

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(ENGINE_DIR)
BASE_DIR = os.path.dirname(APP_DIR)
_REAL_DATA_DIR = os.path.join(BASE_DIR, "data")
_SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")
_FORCE_DEMO = (
    os.environ.get("GARMIN_DEMO_MODE", "").strip().lower() in ("1", "true", "yes", "demo", "mock")
    or ("--demo" in sys.argv)
)
IS_DEMO_MODE = _FORCE_DEMO or not os.path.exists(os.path.join(_REAL_DATA_DIR, "raw_daily_93d.json"))
DATA_DIR = _SAMPLE_DATA_DIR if IS_DEMO_MODE else _REAL_DATA_DIR

TR_DAYS = ["Pzt", "Salı", "Çar", "Per", "Cuma", "Cmt", "Paz"]
TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

SPORT_TR_MAP: Dict[str, str] = {
    "running": "Koşu",
    "treadmill_running": "Koşu Bandı",
    "trail_running": "Patika Koşusu",
    "track_running": "Pist Koşusu",
    "strength_training": "Kuvvet",
    "fitness_equipment": "Fitness & Kuvvet",
    "sailing_v2": "Yelken",
    "sailing": "Yelken",
    "basketball": "Basketbol",
    "resort_skiing": "Kayak",
    "backcountry_skiing": "Tur Kayağı",
    "cross_country_skiing": "Kros Kayak",
    "skate_skiing": "Kayak (Serbest)",
    "skiing": "Kayak",
    "alpine_skiing": "Alp Disiplini Kayak",
    "snowboarding": "Snowboard",
    "winter_sports": "Kış Sporu",
    "cycling": "Bisiklet",
    "indoor_cycling": "Salon Bisikleti",
    "mountain_biking": "Dağ Bisikleti",
    "swimming": "Yüzme",
    "lap_swimming": "Havuz Yüzme",
    "open_water_swimming": "Açık Su Yüzme",
    "hiking": "Doğa Yürüyüşü",
    "walking": "Yürüyüş",
    "rowing_v2": "Kürek",
    "indoor_rowing": "Kürek Ergometresi",
    "tennis": "Tenis",
    "padel": "Padel",
    "squash": "Squash",
    "pilates": "Pilates",
    "yoga": "Yoga",
    "cardio": "Kardiyo",
    "elliptical": "Eliptik",
    "stair_climbing": "Merdiven Çıkışı",
    "breathwork": "Nefes Egzersizi",
    "hiit": "HIIT",
}

def fnum(value: Any, default: float = 0.0) -> float:
    """Değeri float'a çevirir; None, boş, NaN veya sonsuz ise `default` döner (NaN `or` ile eksik sayılmaz, bu yüzden float(x or d) güvensizdir)."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return out if np.isfinite(out) else float(default)


def format_sport_tr(sport_key: Optional[str], fallback_name: str = "") -> str:
    """Herhangi bir Garmin typeKey spor kodunu Türkçe etikete dönüştürür."""
    raw = (sport_key or "").strip().lower()
    if not raw:
        return fallback_name or "Antrenman"
    if raw in SPORT_TR_MAP:
        return SPORT_TR_MAP[raw]
    for k, label in SPORT_TR_MAP.items():
        if k in raw:
            return label
    cleaned = raw.replace("_v2", "").replace("_", " ").strip().title()
    return cleaned or fallback_name or "Antrenman"


def classify_sport_bucket(sport_key: Optional[str]) -> str:
    """Aktiviteyi kota kovası açısından sınıflar ('running', 'strength' veya 'spontaneous')."""
    raw = (sport_key or "").strip().lower()
    if "running" in raw:
        return "running"
    if "strength" in raw or "fitness_equipment" in raw:
        return "strength"
    return "spontaneous"


def classify_run_workout(act: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Koşu aktivitesini nabız zonları, anaerobik/aerobik training effect (TE) ve başlığa bakarak
    gerçek fizyolojik türüne ('interval', 'zone2' veya 'tempo') sınıflandırır.
    Sürekli Zone 3-4 Tempo koşularını (örn. AnTE=0.0, TE=TEMPO) hatalı şekilde İnterval saymaz.
    """
    a = act or {}
    name_low = str(a.get("activityName") or a.get("name") or "").lower()
    te_label = str(a.get("trainingEffectLabel") or a.get("te_label") or "").upper()
    an_te = float(
        a.get("anaerobicTrainingEffect")
        if a.get("anaerobicTrainingEffect") is not None
        else (a.get("anTE") or 0.0)
    )
    a_te = float(
        a.get("aerobicTrainingEffect")
        if a.get("aerobicTrainingEffect") is not None
        else (a.get("aTE") or 0.0)
    )
    avg_hr = float(a.get("averageHR") or a.get("avg_hr") or 0.0)
    max_hr = float(a.get("maxHR") or a.get("max_hr") or 0.0)

    if any(a.get(f"hrTimeInZone_{i}") is not None for i in range(1, 6)):
        zs = [float(a.get(f"hrTimeInZone_{i}") or 0.0) for i in range(1, 6)]
        tot_z = sum(zs) or 1.0
        _z1, _z2, z3_pct, z4_pct, z5_pct = [z / tot_z * 100.0 for z in zs]
    else:
        z3_pct = float(a.get("z3_pct") or 0.0)
        z4_pct = float(a.get("z4_pct") or 0.0)
        z5_pct = float(a.get("z5_pct") or 0.0)

    has_interval_name = any(
        k in name_low for k in ("interval", "interva", "run workout", "4x", "1000m", "tekrar", "sprint", "hiit", "vo2")
    )
    is_interval = (
        has_interval_name
        or an_te >= 1.5
        or te_label in ("ANAEROBIC_CAPACITY", "SPEED", "VO2MAX")
        or (an_te >= 1.0 and max_hr >= 178 and (z4_pct + z5_pct) >= 20.0)
    )
    if is_interval:
        return {
            "kind": "interval",
            "label_tr": "5K Hız İntervali",
            "short_label": "5K Hız İntervali",
            "badge_tr": "5K Hız İntervali (Z4-5)",
            "is_planned_archetype": True,
            "te_label": te_label or "SPEED",
            "an_te": round(an_te, 1),
            "a_te": round(a_te, 1),
        }

    has_z2_name = any(
        k in name_low for k in ("zone 2", "z2", "taban", "base", "easy", "rahat", "recovery", "toparlanma")
    )
    is_zone2 = (
        has_z2_name
        or (
            an_te < 1.5
            and te_label not in ("TEMPO", "LACTATE_THRESHOLD")
            and 0 < avg_hr <= 152
            and (z3_pct + z4_pct + z5_pct) < 55.0
        )
        or te_label == "RECOVERY"
    )
    if is_zone2:
        return {
            "kind": "zone2",
            "label_tr": "Zone 2 Rahat Taban",
            "short_label": "Zone 2 Koşu",
            "badge_tr": "Zone 2 Taban",
            "is_planned_archetype": True,
            "te_label": te_label or "AEROBIC_BASE",
            "an_te": round(an_te, 1),
            "a_te": round(a_te, 1),
        }

    label_tr = (
        "Laktat Eşiği Tempo Koşusu (Zone 4)"
        if (te_label == "LACTATE_THRESHOLD" or z4_pct >= 55.0)
        else "Tempo Koşusu (Zone 3)"
    )
    return {
        "kind": "tempo",
        "label_tr": label_tr,
        "short_label": "Tempo Koşusu",
        "badge_tr": "Tempo Koşusu (Plan Dışı)",
        "is_planned_archetype": False,
        "te_label": te_label or "TEMPO",
        "an_te": round(an_te, 1),
        "a_te": round(a_te, 1),
    }


def fmt_pace_sec(sec: Optional[float]) -> str:
    """
    Saniye cinsinden tempo değerini standart 'dakika:saniye' (örn. 5:48 /km) formatına dönüştürür.

    Args:
        sec (Optional[float]): Kilometre başına harcanan süre (saniye).

    Returns:
        str: Formatlanmış string ('5:48' veya veri yoksa '--').
    """
    if sec is None or np.isnan(sec) or sec <= 0:
        return "--"
    m = int(sec // 60)
    s = int(round(sec % 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"

def fmt_clock(hr_val: Optional[float]) -> str:
    """
    Kayan noktalı saat değerini (-24.0 ile 24.0) 24 saatlik 'SS:DD' zaman formatına dönüştürür.

    Args:
        hr_val (Optional[float]): Saat cinsinden zaman değeri (örn. 0.5 = 00:30, -0.25 = 23:45).

    Returns:
        str: 24 saatlik formatlanmış zaman dizisi ('00:30' veya '--').
    """
    if hr_val is None or np.isnan(hr_val):
        return "--"
    h = hr_val + 24.0 if hr_val < 0 else hr_val
    hh = int(h) % 24
    mm = int(round((h - int(h)) * 60))
    if mm == 60:
        hh = (hh + 1) % 24
        mm = 0
    return f"{hh:02d}:{mm:02d}"



def zone_text(fn):
    """Metodun sonucundaki [[Z2_HR]] gibi şablon belirteçlerini sporcunun kendi nabız/tempo bölgeleriyle doldurur."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.fill_zone_tokens(fn(self, *args, **kwargs))
    return wrapper


def request_cached(fn):
    """
    Motor metodunu aktif istek kapsamı (engine.request_scope) boyunca önbelleğe alır.
    Kapsam dışında (testler, betikler) her çağrı doğrudan hesaplanır. Önbellekten dönen
    değer derin kopyalanır; çağıranın sonucu değiştirmesi önbelleği bozmaz.
    """
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        cache = getattr(self, "_req_cache", None)
        if cache is None:
            return fn(self, *args, **kwargs)
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        try:
            hash(key)
        except TypeError:
            return fn(self, *args, **kwargs)
        if key not in cache:
            cache[key] = fn(self, *args, **kwargs)
        return copy.deepcopy(cache[key])
    return wrapper
