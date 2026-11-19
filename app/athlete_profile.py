#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sporcu profili: yaş, boy, cinsiyet, hedef kilo gibi KİŞİYE ÖZEL değerlerin tek kaynağı.

Kod içine kişisel değer gömülmez. Değerler şu öncelikle okunur:
  1. <data_dir>/athlete_profile.json   (kullanıcının elle yazdığı geçersiz kılmalar; git'e girmez)
  2. <data_dir>/raw_profile.json       (Garmin Connect "user-settings" yanıtı; `make fetch` ile indirilir)
  3. Nötr varsayılanlar                (profil eksik uyarısıyla birlikte)

Garmin'den gelen ve gelmeyen alanlar `missing` listesinde raporlanır; arayüz ve API bu listeyi
kullanıcıya "profilini tamamla" ipucu olarak gösterebilir.
"""

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Nötr (kimseye ait olmayan) varsayılanlar: yalnızca hiçbir kaynakta değer yoksa kullanılır.
NEUTRAL_DEFAULTS: Dict[str, Any] = {
    "age": 30,
    "gender": "male",
    "height_cm": 175.0,
}

# Kullanıcının mutlaka kendisinin söylemesi gereken (Garmin'in vermediği) alanlar
USER_ONLY_FIELDS = ("target_weight_kg",)


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        logger.warning("Profil dosyası okunamadı: %s", path, exc_info=True)
        return {}


def _age_from_birth_date(birth_date: Any, today: Optional[date] = None) -> Optional[int]:
    """'YYYY-MM-DD' doğum tarihinden yaşı hesaplar; geçersizse None."""
    try:
        born = datetime.strptime(str(birth_date)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _from_garmin(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Garmin 'user-settings' yanıtından (userData bloğu) kullanılabilir alanları çıkarır."""
    ud = raw.get("userData") if isinstance(raw.get("userData"), dict) else raw
    out: Dict[str, Any] = {}
    age = _age_from_birth_date(ud.get("birthDate"))
    if age is not None and 10 <= age <= 100:
        out["age"] = age
    gender = str(ud.get("gender") or "").strip().lower()
    if gender in ("male", "female"):
        out["gender"] = gender
    height = ud.get("height")
    if isinstance(height, (int, float)) and 120 <= float(height) <= 230:
        out["height_cm"] = float(height)
    weight = ud.get("weight")  # Garmin gram cinsinden verir
    if isinstance(weight, (int, float)) and weight > 0:
        out["weight_kg"] = round(float(weight) / 1000.0 if weight > 300 else float(weight), 1)
    lthr = ud.get("lactateThresholdHeartRate")
    if isinstance(lthr, (int, float)) and 100 <= lthr <= 220:
        out["lactate_threshold_hr"] = int(lthr)
    return out


def load_athlete_profile(data_dir: str) -> Dict[str, Any]:
    """Profili yükler ve her alanın kaynağını (`sources`) ile eksik alanları (`missing`) raporlar."""
    garmin = _from_garmin(_read_json(os.path.join(data_dir, "raw_profile.json")))
    manual = _read_json(os.path.join(data_dir, "athlete_profile.json"))

    profile: Dict[str, Any] = dict(NEUTRAL_DEFAULTS)
    sources: Dict[str, str] = {k: "default" for k in NEUTRAL_DEFAULTS}
    for key, value in garmin.items():
        profile[key] = value
        sources[key] = "garmin"
    for key, value in manual.items():
        if value is None or key.startswith("_"):
            continue
        profile[key] = value
        sources[key] = "athlete_profile.json"

    # athlete_profile.json'da doğum tarihi verilmişse yaş otomatik güncel kalır
    if "birth_date" in manual and manual.get("age") is None:
        age = _age_from_birth_date(manual["birth_date"])
        if age is not None:
            profile["age"] = age
            sources["age"] = "athlete_profile.json"

    missing: List[str] = [k for k in NEUTRAL_DEFAULTS if sources.get(k) == "default"]
    missing += [k for k in USER_ONLY_FIELDS if profile.get(k) is None]
    profile["name"] = manual.get("name")
    profile["sources"] = sources
    profile["missing"] = missing
    profile["is_complete"] = not missing
    return profile
