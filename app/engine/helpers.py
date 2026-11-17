#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin Veri ve Performans Hesaplama Motoru (Kapsamlı Sürüm)
93 günlük günlük sağlık özetleri, 88 gecelik uyku ve HRV kayıtları ve 49 antrenmanı
bütünleşik bir analitik yapıda işler; forma girme projeksiyonları, korelasyonlar,
aynı gün sıra analizleri ve branş gelişim stratejilerini üretir.
"""

import json
import os
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
import numpy as np
import pandas as pd

try:
    from athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
except ImportError:
    from app.athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(ENGINE_DIR)
BASE_DIR = os.path.dirname(APP_DIR)
_REAL_DATA_DIR = os.path.join(BASE_DIR, "data")
_SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")
IS_DEMO_MODE = not os.path.exists(os.path.join(_REAL_DATA_DIR, "raw_daily_93d.json"))
DATA_DIR = _SAMPLE_DATA_DIR if IS_DEMO_MODE else _REAL_DATA_DIR

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

