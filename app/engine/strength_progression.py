#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyarlanabilir Kuvvet Progresyonu, Çok Faktörlü Ağırlık Hesaplama,
Başarısızlık/Kısmi Tamamlama Sonrası Dinamik Yeniden Planlama ve
Plato Tabanlı Program Evrimi (5x5 -> Push/Pull -> Upper/Lower -> PPL) Motoru.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# Egzersiz biyomekanik ve standart profilleri
# (key, display_label, match_name, target_sets, target_reps, step_kg, rep_suffix,
#  bw_standards: (novice, intermediate, advanced) vücut ağırlığı oranları; başlangıç yükü bundan türetilir)
LIFT_PROFILES: Dict[str, Dict[str, Any]] = {
    "squat": {
        "label": "Back Squat",
        "match_name": "Back Squat",
        "category": "SQUAT",
        "target_sets": 5,
        "target_reps": 5,
        "step_kg": 2.5,
        "rep_suffix": "x 5 reps x 5 set",
        "short_rep": "5x5",
        "bw_standards": (1.00, 1.35, 1.75),
        "is_compound": True,
    },
    "bench": {
        "label": "Bench Press",
        "match_name": "Bench Press",
        "category": "BENCH_PRESS",
        "target_sets": 5,
        "target_reps": 5,
        "step_kg": 2.5,
        "rep_suffix": "x 5 reps x 5 set",
        "short_rep": "5x5",
        "bw_standards": (0.75, 1.05, 1.40),
        "is_compound": True,
    },
    "row": {
        "label": "Barbell Row",
        "match_name": "Barbell Row",
        "category": "ROW",
        "target_sets": 5,
        "target_reps": 5,
        "step_kg": 2.5,
        "rep_suffix": "x 5 reps x 5 set",
        "short_rep": "5x5",
        "bw_standards": (0.70, 0.95, 1.25),
        "is_compound": True,
    },
    "ohp": {
        "label": "Overhead Press (OHP)",
        "match_name": "Overhead Press (OHP)",
        "category": "SHOULDER_PRESS",
        "target_sets": 5,
        "target_reps": 5,
        "step_kg": 2.5,
        "rep_suffix": "x 5 reps x 5 set",
        "short_rep": "5x5",
        "bw_standards": (0.45, 0.65, 0.90),
        "is_compound": True,
    },
    "deadlift": {
        "label": "Barbell Deadlift",
        "match_name": "Barbell Deadlift",
        "category": "DEADLIFT",
        "target_sets": 1,
        "target_reps": 5,
        "step_kg": 5.0,
        "rep_suffix": "x 5 reps (1 ana set)",
        "short_rep": "1x5",
        "bw_standards": (1.25, 1.65, 2.15),
        "is_compound": True,
    },
    "lat_pulldown": {
        "label": "Lat Pulldown",
        "match_name": "Lat Pulldown",
        "category": "PULL_UP",
        "target_sets": 4,
        "target_reps": 12,
        "step_kg": 2.5,
        "rep_suffix": "x 12 reps x 4 set",
        "short_rep": "4x12",
        "bw_standards": (0.55, 0.80, 1.05),
        "is_compound": False,
    },
    "lateral_raise": {
        "label": "Lateral Raise",
        "match_name": "Lateral Raise (Yana Açış)",
        "category": "LATERAL_RAISE",
        "target_sets": 3,
        "target_reps": 12,
        "step_kg": 2.5,
        "rep_suffix": "x 12 reps x 3 set",
        "short_rep": "3x12",
        "bw_standards": (0.20, 0.30, 0.40),
        "is_compound": False,
    },
    "shrug": {
        "label": "Dumbbell Shrug",
        "match_name": "Dumbbell Shrug",
        "category": "SHRUG",
        "target_sets": 3,
        "target_reps": 12,
        "step_kg": 2.5,
        "rep_suffix": "x 12 reps x 3 set",
        "short_rep": "3x12",
        "bw_standards": (0.50, 0.70, 0.95),
        "is_compound": False,
    },
}

# Dambıl izolasyonunda +2.5 kg büyük bir göreli artış: 2 temiz seans sonrası yükselt (çift progresyon)
logger = logging.getLogger(__name__)


DOUBLE_PROGRESSION_LIFTS = {"lateral_raise"}
# Deadlift e1RM / vücut ağırlığı bu oranı geçince artış +5 kg'dan +2.5 kg'a iner
DEADLIFT_SMALL_JUMP_BW_RATIO = 1.30

PROGRAM_SPLIT_CATALOG: Dict[str, Dict[str, Any]] = {
    "5x5_linear": {
        "id": "5x5_linear",
        "name": "StrongLifts 5x5 · Doğrusal Progresyon (Full Body A/B)",
        "short_name": "5x5 Doğrusal (A/B)",
        "frequency": "Haftada 2-3 Kuvvet",
        "target_tier": "Başlangıç / Erken Orta Seviye",
        "description": "Her seans Squat temelinde doğrusal ağırlık artışı (+2.5 kg / +5.0 kg). Sinir sistemi adaptasyonu hızlıyken maksimum verim sağlar.",
        "slots": ["gym_a", "gym_b"],
    },
    "push_pull": {
        "id": "push_pull",
        "name": "Push / Pull · İtme & Çekme Hibrit (Güç + Hipertrofi)",
        "short_name": "Push / Pull",
        "frequency": "Haftada 2-4 Kuvvet (A/B Rotasyon)",
        "target_tier": "Orta Seviye (5x5 Platosu Sonrası)",
        "description": "Squat'ı her antrenmanda yapma yorgunluğunu kaldırır; İtme (Squat, Bench, OHP, Incline, Lateral) ve Çekme (Deadlift/RDL, Row, Lat Pulldown, Rear Delt) günleriyle çift progresyon (6-8 & 8-12 tekrar) uygular.",
        "slots": ["push", "pull"],
    },
    "upper_lower": {
        "id": "upper_lower",
        "name": "Upper / Lower · Üst & Alt Vücut Periyotlaması",
        "short_name": "Upper / Lower",
        "frequency": "Haftada 2-4 Kuvvet",
        "target_tier": "Orta - İleri Seviye",
        "description": "Üst vücut itme-çekme dengesini ve alt vücut kuvvet hacmini ayrı günlerde optimize eder; Top Set + Back-off set yapısıyla plato kırar.",
        "slots": ["upper", "lower"],
    },
    "ppl": {
        "id": "ppl",
        "name": "Push / Pull / Legs (PPL) · Blok Periyotlama",
        "short_name": "Push / Pull / Legs",
        "frequency": "Haftada 3+ Kuvvet",
        "target_tier": "İleri Seviye / Yüksek Hacim",
        "description": "İtme, Çekme ve Bacak günlerini tamamen ayırarak her kas grubunda yüksek hipertrofi ve maksimum toparlanma penceresi sunar.",
        "slots": ["push", "pull", "legs"],
    },
}


def round_to_plate(weight_kg: float, step: float = 2.5) -> float:
    """Ağırlığı en yakın standart plaka/dambıl artışına (varsayılan 2.5 kg) yuvarlar."""
    if weight_kg <= 0:
        return 0.0
    return round(round(weight_kg / step) * step, 1)


def default_start_kg(spec: Dict[str, Any], bodyweight_kg: float = 75.0) -> Tuple[float, float]:
    """
    Henüz kayıtlı seti olmayan bir hareket için başlangıç (mevcut, sonraki) yükünü sporcunun vücut ağırlığından türetir:
    'başlangıç' standart oranının yarısı kadar (ör. Squat 0.5x VA). Kişisel sabit kilo içermez.
    Garmin'den gelen dinamik hareketler kendi fallback değerlerini taşır.
    """
    if spec.get("is_dynamic"):
        return float(spec["fallback_max"]), float(spec["fallback_next"])
    step = float(spec["step_kg"])
    cur = max(step, round_to_plate(spec["bw_standards"][0] * 0.5 * bodyweight_kg, 2.5))
    return cur, round_to_plate(cur + step, 2.5)


def compute_e1rm(weight_kg: float, reps: int) -> float:
    """Epley + Brzycki hibrit formülü ile Tahmini 1RM (e1RM) hesaplar."""
    if weight_kg <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return round(weight_kg, 1)
    epley = weight_kg * (1.0 + reps / 30.0)
    if reps <= 10:
        brzycki = weight_kg * (36.0 / max(1.0, (37.0 - reps)))
        return round((epley + brzycki) / 2.0, 1)
    return round(epley, 1)


def _filter_working_sets(sets: List[Dict[str, Any]], is_compound: bool) -> List[Dict[str, Any]]:
    """Isınma setlerini (ör. 20 kg boş bar x 10) ayıklayıp gerçek çalışma setlerini döndürür."""
    valid = [s for s in sets if float(s.get("weight_kg") or 0) > 0 and int(s.get("reps") or 0) > 0]
    if not valid:
        return []
    peak_w = max(float(s["weight_kg"]) for s in valid)
    if len(valid) == 1:
        return valid
    working = []
    for idx, s in enumerate(valid):
        w = float(s["weight_kg"])
        r = int(s["reps"])
        # İlk set veya pik ağırlığın %62'sinin altındaki hafif ısınma setlerini ele
        is_warmup_bar = is_compound and peak_w >= 40.0 and w <= 25.0 and idx == 0
        is_light_ramp = w < peak_w * 0.62 and (r >= 8 or idx == 0)
        if is_warmup_bar or is_light_ramp:
            continue
        working.append(s)
    return working if working else valid


def _linear_slope(values: List[float]) -> float:
    """Son seanslardaki değerlerin seans başına doğrusal eğimini (kg/seans) hesaplar."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den = sum((x - mean_x) ** 2 for x in xs)
    return round(num / den, 2) if den > 0 else 0.0


def evaluate_session_lift(
    lift_key: str,
    raw_sets: List[Dict[str, Any]],
    spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Tek bir seanstaki tek bir hareketin set/tekrar kalitesini, düşüş oranını ve e1RM'ini analiz eder."""
    spec = spec or LIFT_PROFILES[lift_key]
    working = _filter_working_sets(raw_sets, spec["is_compound"])
    if not working:
        return {"has_data": False}

    target_sets = spec["target_sets"]
    target_reps = spec["target_reps"]
    total_target_reps = target_sets * target_reps

    weights = [float(s["weight_kg"]) for s in working]
    reps_list = [int(s["reps"]) for s in working]
    top_w = max(weights)
    min_w = min(weights)
    total_reps = sum(reps_list)
    effective_w = round(sum(w * r for w, r in zip(weights, reps_list)) / max(1, total_reps), 1)
    peak_e1rm = max(compute_e1rm(w, r) for w, r in zip(weights, reps_list))

    # Ağırlık düşüşü veya eksik tekrar analizi
    weight_drop_kg = round(top_w - min_w, 1)
    completion_ratio = round(total_reps / max(1, total_target_reps), 3)

    # Tüm çalışma setleri en az hedef set sayısı kadar ve hepsi top_w ağırlığında ve target_reps tekrarında mı?
    sets_at_top_and_target = sum(
        1 for w, r in zip(weights, reps_list)
        if w >= (top_w - 0.1) and r >= target_reps
    )
    all_sets_clean = (
        len(working) >= target_sets
        and sets_at_top_and_target >= target_sets
        and weight_drop_kg <= 0.5
    )

    avg_reps = total_reps / max(1, len(working))
    if all_sets_clean and avg_reps > target_reps + 0.4:
        outcome = "PASSED_AMRAP"
    elif all_sets_clean:
        outcome = "PASSED_CLEAN"
    elif not spec["is_compound"] and completion_ratio >= 0.72 and top_w > 0:
        # İzolasyon/aksesuar hareketlerinde piramit veya 3 set tamamlama normal konsolidasyon sayılır
        outcome = "PASSED_CLEAN" if (len(working) >= target_sets and weight_drop_kg <= 2.5 and completion_ratio >= 0.95) else "PARTIAL_STALL"
    elif completion_ratio >= 0.80 and len(working) >= max(1, target_sets - 1):
        outcome = "PARTIAL_STALL"
    else:
        outcome = "FAILED"

    return {
        "has_data": True,
        "working_sets": working,
        "top_weight_kg": top_w,
        "effective_weight_kg": effective_w,
        "weight_drop_kg": weight_drop_kg,
        "total_reps": total_reps,
        "target_total_reps": total_target_reps,
        "completion_ratio": completion_ratio,
        "peak_e1rm": peak_e1rm,
        "outcome": outcome,
        "reps_pattern": "/".join(str(r) for r in reps_list),
    }


def _write_json_atomic(path: str, payload: Any) -> None:
    """JSON'u geçici dosyaya yazıp os.replace ile atomik olarak yerine koyar."""
    tmp_path = f"{path}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def load_logged_gym_sessions(data_dir: str) -> List[Dict[str, Any]]:
    """Kullanıcının uygulama üzerinden girdiği tamamlanmış/başarısız kuvvet seanslarını yükler."""
    path = os.path.join(data_dir, "logged_gym_sessions.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        logger.warning("load_logged_gym_sessions: yedek davranış uygulandı", exc_info=True)
        return []


def save_logged_gym_session(data_dir: str, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Yeni manuel kuvvet seansı sonucunu kaydeder."""
    sessions = load_logged_gym_sessions(data_dir)
    sessions.append(entry)
    os.makedirs(data_dir, exist_ok=True)
    _write_json_atomic(os.path.join(data_dir, "logged_gym_sessions.json"), sessions)
    return sessions


def reset_logged_gym_sessions(data_dir: str, mode: str = "last") -> List[Dict[str, Any]]:
    """Son manuel kaydı siler (mode='last') veya tüm manuel kayıtları temizler (mode='all')."""
    path = os.path.join(data_dir, "logged_gym_sessions.json")
    sessions = load_logged_gym_sessions(data_dir)
    if mode == "all":
        sessions = []
    elif sessions:
        sessions.pop()
    os.makedirs(data_dir, exist_ok=True)
    _write_json_atomic(path, sessions)
    return sessions


def load_program_state(data_dir: str) -> Dict[str, Any]:
    """Aktif kuvvet programı split durumunu yükler."""
    path = os.path.join(data_dir, "training_program_state.json")
    default = {
        "active_split": "5x5_linear",
        "auto_transition": True,
        "transition_history": [],
        "updated_at": None,
    }
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("active_split") in PROGRAM_SPLIT_CATALOG:
            return {**default, **data}
    except (OSError, ValueError):
        logger.warning("load_program_state: yedek davranış uygulandı", exc_info=True)
    return default


def save_program_state(data_dir: str, new_split: str, reason: str = "", source: str = "manual") -> Dict[str, Any]:
    """Aktif kuvvet programını günceller (5x5 -> Push/Pull -> Upper/Lower -> PPL)."""
    if new_split not in PROGRAM_SPLIT_CATALOG:
        raise ValueError(f"Geçersiz program split: {new_split}")
    state = load_program_state(data_dir)
    old_split = state.get("active_split", "5x5_linear")
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
    if old_split != new_split:
        hist = state.get("transition_history") or []
        hist.append({
            "from": old_split,
            "to": new_split,
            "reason": reason or f"{old_split} -> {new_split} geçişi",
            "source": source,
            "timestamp": now_iso,
        })
        state["transition_history"] = hist[-15:]
    state["active_split"] = new_split
    state["updated_at"] = now_iso
    os.makedirs(data_dir, exist_ok=True)
    _write_json_atomic(os.path.join(data_dir, "training_program_state.json"), state)
    return state


_COMPOUND_KEYWORDS = ("squat", "press", "deadlift", "row", "pull", "lunge", "dip", "bench", "clean", "thrust", "chin")
_PULL_KEYWORDS = ("row", "pull", "curl", "lat", "deadlift", "shrug", "face", "rear", "chin")
_LEG_KEYWORDS = ("squat", "lunge", "leg", "calf", "deadlift", "thrust", "rdl", "hamstring", "glute")


def _slugify(name: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "hareket"


def build_dynamic_profiles(chrono_sessions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Çekirdek 8 hareket dışında Garmin'den gelen her yeni hareket için otomatik profil üretir."""
    known = {spec["match_name"] for spec in LIFT_PROFILES.values()}
    profiles: Dict[str, Dict[str, Any]] = {}
    for sess in chrono_sessions:
        for ex in sess.get("exercises", []):
            name = ex.get("name")
            if not name or name in known:
                continue
            low = name.lower()
            is_compound = any(k in low for k in _COMPOUND_KEYWORDS)
            working = _filter_working_sets(ex.get("sets", []), is_compound)
            if not working:
                continue
            reps = sorted(int(x["reps"]) for x in working)
            t_reps = max(1, reps[len(reps) // 2])
            t_sets = max(1, len(working))
            top_w = max(float(x["weight_kg"]) for x in working)
            key = _slugify(name)
            profiles[key] = {
                "label": name,
                "match_name": name,
                "category": "DYNAMIC",
                "target_sets": t_sets,
                "target_reps": t_reps,
                "step_kg": 2.5,
                "rep_suffix": f"x {t_reps} reps x {t_sets} set",
                "short_rep": f"{t_sets}x{t_reps}",
                "fallback_max": top_w,
                "fallback_next": round_to_plate(top_w + 2.5, 2.5),
                "bw_standards": (0.30, 0.50, 0.80) if is_compound else (0.15, 0.25, 0.40),
                "is_compound": is_compound,
                "is_dynamic": True,
                "is_pull": any(k in low for k in _PULL_KEYWORDS),
                "is_leg": any(k in low for k in _LEG_KEYWORDS),
            }
    return profiles


PROGRAM_SPLIT_ORDER = ["5x5_linear", "push_pull", "upper_lower", "ppl"]


def select_program_split(plateau_score: int) -> str:
    """Plato skoruna göre en uygun programı otomatik seçer (kullanıcı seçimi yok)."""
    if plateau_score >= 90:
        return "ppl"
    if plateau_score >= 75:
        return "upper_lower"
    if plateau_score >= 55:
        return "push_pull"
    return "5x5_linear"



def compute_adaptive_progression(
    chrono_sessions: List[Dict[str, Any]],
    bodyweight_kg: float = 75.0,
    readiness_ctx: Optional[Dict[str, Any]] = None,
    reference_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tüm geçmiş setlerden çok faktörlü kuvvet progresyonu, e1RM eğimi,
    takılma/deload tespiti ve çok adımlı gelecek seans projeksiyonlarını hesaplar.
    """
    r_ctx = readiness_ctx or {}
    hrv_ratio = float(r_ctx.get("hrv_ratio", 1.0))
    sleep_score = float(r_ctx.get("sleep_score", 80.0))
    acwr = float(r_ctx.get("acwr", 1.0))

    # Hazırbulunuşluk katsayısı (0.85 - 1.05)
    readiness_penalty = False
    readiness_note = "Normal Toparlanma"
    if acwr > 1.50 or sleep_score < 60 or hrv_ratio < 0.80:
        readiness_penalty = True
        readiness_note = "Yorgunluk/HRV Düşüşü: Agresif artış yerine konsolidasyon önerilir"

    ref_dt = None
    if reference_date:
        try:
            ref_dt = datetime.strptime(reference_date[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            logger.debug("compute_adaptive_progression: yedek davranış uygulandı", exc_info=True)
            ref_dt = None

    progression: Dict[str, Any] = {}
    stall_summary: List[str] = []
    total_deloads = 0
    total_stalls = 0
    compound_e1rm_slopes: List[float] = []
    compound_ratios: Dict[str, float] = {}

    profiles: Dict[str, Dict[str, Any]] = dict(LIFT_PROFILES)
    profiles.update(build_dynamic_profiles(chrono_sessions))

    total_deloads, total_stalls = _evaluate_all_lifts(bodyweight_kg, chrono_sessions, compound_e1rm_slopes, compound_ratios, profiles, progression, readiness_note, readiness_penalty, ref_dt, stall_summary, total_deloads, total_stalls)

    # Plato & Program Evrimi Skoru (0 - 100)
    plateau_score = _compute_plateau_score(
        progression=progression,
        total_deloads=total_deloads,
        total_stalls=total_stalls,
        compound_e1rm_slopes=compound_e1rm_slopes,
        compound_ratios=compound_ratios,
        acwr=acwr,
        hrv_ratio=hrv_ratio,
        profiles=profiles,
    )

    return {
        "progression": progression,
        "plateau_analysis": plateau_score,
        "readiness_note": readiness_note,
        "stall_summary": stall_summary,
    }

def _evaluate_all_lifts(bodyweight_kg, chrono_sessions, compound_e1rm_slopes, compound_ratios, profiles, progression, readiness_note, readiness_penalty, ref_dt, stall_summary, total_deloads, total_stalls):
    """Tüm hareketleri (çekirdek + dinamik) değerlendirip progresyon kartlarını, takılma/deload sayaçlarını ve bileşik e1RM istatistiklerini üretir."""
    for key, spec in profiles.items():
        match_name = spec["match_name"]
        step_kg = spec["step_kg"]
        rep_suffix = spec["rep_suffix"]
        lift_records = _collect_lift_records(chrono_sessions, key, match_name, spec)

        if not lift_records:
            fb_max, fb_next = default_start_kg(spec, bodyweight_kg)
            progression[key] = {
                "is_core": key in LIFT_PROFILES,
                "name": spec["label"],
                "history": [],
                "delta": "Veri Bekleniyor",
                "max_kg": fb_max,
                "effective_kg": fb_max,
                "e1rm_kg": compute_e1rm(fb_max, spec["target_reps"]),
                "e1rm_slope": 0.0,
                "bw_ratio": round(compute_e1rm(fb_max, spec["target_reps"]) / max(40.0, bodyweight_kg), 2),
                "last_date": "-",
                "last_outcome": "UNKNOWN",
                "consecutive_stalls": 0,
                "deload_count": 0,
                "decision": "BASELINE",
                "decision_reason": "Henüz kayıtlı set yok; başlangıç hedefi atandı.",
                "next_kg": fb_next,
                "next_target": f"{fb_next:.1f} kg {rep_suffix}",
                "projected_weights": [
                    fb_next,
                    round_to_plate(fb_next + step_kg, step_kg),
                    round_to_plate(fb_next + 2 * step_kg, step_kg),
                ],
            }
            continue

        consec_stalls, deloads = _count_stalls_and_deloads(lift_records, spec)

        latest = lift_records[-1]
        first = lift_records[0]
        clean_streak = 0
        for rec in reversed(lift_records):
            if rec["outcome"].startswith("PASSED") and abs(rec["top_weight_kg"] - latest["top_weight_kg"]) <= 0.1:
                clean_streak += 1
            else:
                break
        last_w = latest["top_weight_kg"]
        eff_w = latest["effective_weight_kg"]
        last_outcome = latest["outcome"]
        e1rms = [r["peak_e1rm"] for r in lift_records]
        latest_e1rm = e1rms[-1]
        slope = _linear_slope(e1rms[-5:])
        bw_ratio = round(latest_e1rm / max(40.0, bodyweight_kg), 2)

        # Son seanstan bu yana geçen gün (detraining kontrolü)
        days_gap = 0
        if ref_dt and latest.get("date"):
            try:
                l_dt = datetime.strptime(latest["date"][:10], "%Y-%m-%d")
                days_gap = max(0, (ref_dt - l_dt).days)
            except (ValueError, TypeError):
                logger.debug("compute_adaptive_progression: yedek davranış uygulandı", exc_info=True)
                days_gap = 0

        decision, next_kg, reason = _decide_next_weight(bw_ratio, clean_streak, consec_stalls, days_gap, eff_w, key, last_outcome, last_w, latest, latest_e1rm, readiness_note, readiness_penalty, spec, step_kg)

        proj_weights = _project_weights(bodyweight_kg, clean_streak, key, last_outcome, last_w, next_kg, spec, step_kg)

        diff = round(last_w - first["top_weight_kg"], 1)
        history_strs = [f"{r['top_weight_kg']:.1f} kg ({r['date'][5:]})" for r in lift_records[-5:]]
        delta_str = (
            f"+{diff:.1f} kg ({len(lift_records)} seans)"
            if diff > 0
            else f"Stabil {last_w:.1f} kg ({len(lift_records)} seans)"
        )

        if spec["is_compound"]:
            if consec_stalls > 0:
                total_stalls += 1
                stall_summary.append(f"{spec['label']} ({decision})")
            total_deloads += deloads
            compound_e1rm_slopes.append(slope)
            compound_ratios[key] = bw_ratio

        progression[key] = {
            "is_core": key in LIFT_PROFILES,
            "is_pull": bool(spec.get("is_pull")),
            "is_leg": bool(spec.get("is_leg")),
            "short_rep": spec.get("short_rep", ""),
            "slot_hint": latest.get("workout_type", ""),
            "last_full_date": latest.get("date", ""),
            "name": spec["label"],
            "history": history_strs,
            "delta": delta_str,
            "max_kg": last_w,
            "effective_kg": eff_w,
            "e1rm_kg": latest_e1rm,
            "e1rm_slope": slope,
            "bw_ratio": bw_ratio,
            "last_date": latest["date"][5:] if latest.get("date") else "-",
            "last_outcome": last_outcome,
            "last_reps_pattern": latest["reps_pattern"],
            "consecutive_stalls": consec_stalls,
            "deload_count": deloads,
            "decision": decision,
            "decision_reason": reason,
            "next_kg": next_kg,
            "next_target": f"{next_kg:.1f} kg {rep_suffix}",
            "projected_weights": proj_weights,
        }
    return total_deloads, total_stalls


def _collect_lift_records(chrono_sessions, key, match_name, spec):
    """Bir hareketin tüm seanslardaki değerlendirilmiş kayıtlarını kronolojik toplar."""
    lift_records: List[Dict[str, Any]] = []

    for sess in chrono_sessions:
        for ex in sess.get("exercises", []):
            if ex.get("name") == match_name:
                eval_res = evaluate_session_lift(key, ex.get("sets", []), spec)
                if eval_res.get("has_data"):
                    lift_records.append({
                        "date": sess.get("date", ""),
                        "workout_type": sess.get("workout_type", ""),
                        **eval_res,
                    })
    return lift_records


def _count_stalls_and_deloads(lift_records, spec):
    """Kronolojik kayıtlardan ardışık takılma sayısını ve deload sayısını çıkarır."""
    # Kronolojik ilerleyişten takılma & deload sayacı çıkar
    consec_stalls = 0
    deloads = 0
    deload_prescribed = False  # 2. takılmada reçete edilen deload, ardından gelen ağırlık düşüşüyle tekrar sayılmaz
    prev_top = 0.0
    prev_eff = 0.0
    for rec in lift_records:
        oc = rec["outcome"]
        tw = rec["top_weight_kg"]
        ew = rec["effective_weight_kg"]
        if oc in ("PARTIAL_STALL", "FAILED"):
            # Eğer bir önceki seansa göre hem pik hem efektif ağırlık arttıysa bu yeni ağırlıkta ilk denemedir (takılma sıfırlanır -> 1)
            if prev_top > 0 and (tw > prev_top + 0.5 or ew > prev_eff + 0.5):
                consec_stalls = 1
            elif tw >= prev_top - 0.5:
                consec_stalls += 1
            else:
                consec_stalls = 1
            if consec_stalls == 2 and spec["is_compound"]:
                deloads += 1
                deload_prescribed = True
        else:
            consec_stalls = 0
        if prev_top > 0 and tw < prev_top * 0.90:
            if deload_prescribed:
                deload_prescribed = False
            else:
                deloads += 1
        prev_top = tw
        prev_eff = ew
    return consec_stalls, deloads


def _decide_next_weight(bw_ratio, clean_streak, consec_stalls, days_gap, eff_w, key, last_outcome, last_w, latest, latest_e1rm, readiness_note, readiness_penalty, spec, step_kg):
    """Son seans sonucuna göre bir sonraki seansın ağırlık kararını (artış, pekiştirme, deload, hazırlık beklemesi) verir."""
    # Bir sonraki seans ağırlık kararı
    decision = "PROGRESS"
    if days_gap >= 21:
        next_kg = round_to_plate(last_w * 0.90, step_kg)
        decision = "DETRAINING_RESET"
        reason = f"Son seanstan {days_gap} gün geçti; güvenli adaptasyon için %10 hafifletildi."
    elif last_outcome in ("PARTIAL_STALL", "FAILED"):
        if consec_stalls >= 2 and (spec["is_compound"] or last_outcome == "FAILED"):
            next_kg = round_to_plate(last_w * 0.90, step_kg)
            decision = "DELOAD_10PCT"
            reason = (
                f"{consec_stalls}. ardışık takılma ({last_w:.1f} kg · {latest['reps_pattern']}): "
                f"%10 Deload ({next_kg:.1f} kg) ile yorgunluk boşaltılıp yeni ivme kurulacak."
            )
        else:
            next_kg = last_w
            decision = "CONSOLIDATE"
            if latest["weight_drop_kg"] > 0.5:
                reason = (
                    f"Son seansta en yüksek {last_w:.1f} kg çalışıldı (set ortalaması {eff_w:.1f} kg); "
                    f"tüm setler {last_w:.1f} kg'da sabitlenene kadar artış bekletildi."
                )
            else:
                reason = (
                    f"Son seansta tekrar hedefi tam dolmadı ({latest['reps_pattern']}); "
                    f"{last_w:.1f} kg tekrar denenerek pekiştirilecek."
                )
    elif readiness_penalty and bw_ratio >= spec["bw_standards"][0]:
        next_kg = last_w
        decision = "READINESS_HOLD"
        reason = f"{readiness_note}; mevcut {last_w:.1f} kg korunuyor."
    elif key in DOUBLE_PROGRESSION_LIFTS and clean_streak < 2:
        next_kg = last_w
        decision = "CONSOLIDATE"
        reason = (
            f"{last_w:.1f} kg temiz tamamlandı ({latest['reps_pattern']}); dambıl izolasyonunda +2.5 kg büyük bir sıçrama "
            f"olduğu için aynı kiloda 2. temiz seans bekleniyor."
        )
    else:
        # Başarılı tamamlama: artış miktarı belirle
        jump = step_kg
        # Deadlift: e1RM < 1.30x vücut ağırlığı iken +5 kg; sonrasında +2.5 kg
        if key == "deadlift" and bw_ratio >= DEADLIFT_SMALL_JUMP_BW_RATIO:
            jump = 2.5
        next_kg = round_to_plate(last_w + jump, 2.5)
        decision = "PROGRESS"
        reason = (
            f"Son seansta {last_w:.1f} kg ({latest['reps_pattern']}) temiz tamamlandı "
            f"(e1RM {latest_e1rm:.1f} kg); +{jump:.1f} kg progresyon uygulandı."
        )
    return decision, next_kg, reason


def _project_weights(bodyweight_kg, clean_streak, key, last_outcome, last_w, next_kg, spec, step_kg):
    """Sonraki seanslar için ağırlık projeksiyonunu üretir (her seansın temiz tamamlandığı varsayılır; karar kurallarıyla aynı artış mantığı)."""
    # Çok adımlı gelecek seans projeksiyonları [step0, step1, step2, step3]
    # (Her projeksiyon seansının temiz tamamlandığı varsayılır; kararla aynı kurallar uygulanır.)
    proj_weights = [next_kg]
    sim_w = next_kg
    sim_streak = clean_streak if (key in DOUBLE_PROGRESSION_LIFTS and next_kg == last_w and last_outcome.startswith("PASSED")) else 0
    for step_idx in range(1, 5):
        if key in DOUBLE_PROGRESSION_LIFTS:
            sim_streak += 1
            if sim_streak >= 2:
                sim_w = round_to_plate(sim_w + step_kg, 2.5)
                sim_streak = 0
        elif key == "deadlift":
            sim_ratio = compute_e1rm(sim_w, spec["target_reps"]) / max(40.0, bodyweight_kg)
            sim_step = 2.5 if sim_ratio >= DEADLIFT_SMALL_JUMP_BW_RATIO else 5.0
            sim_w = round_to_plate(sim_w + sim_step, 2.5)
        else:
            sim_w = round_to_plate(sim_w + step_kg, 2.5)
        proj_weights.append(sim_w)
    return proj_weights



def _compute_plateau_score(
    progression: Dict[str, Any],
    total_deloads: int,
    total_stalls: int,
    compound_e1rm_slopes: List[float],
    compound_ratios: Dict[str, float],
    acwr: float,
    hrv_ratio: float,
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    5x5 Doğrusal Progresyon'dan Push/Pull veya Upper/Lower split'e geçiş ihtiyacını
    0-100 arası bilimsel skorla hesaplar.
    """
    score = 0
    reasons: List[str] = []

    # 1. Deload geçmişi (max 35 puan)
    if total_deloads >= 2:
        score += 35
        reasons.append(f"Ana bileşik hareketlerde {total_deloads} deload döngüsü tespit edildi.")
    elif total_deloads == 1:
        score += 18
        reasons.append("1 bileşik harekette deload ihtiyacı oluştu.")

    # 2. Eşzamanlı takılma sayısı (max 25 puan)
    if total_stalls >= 2:
        score += 25
        reasons.append(f"{total_stalls} harekette eşzamanlı takılma/konsolidasyon var.")
    elif total_stalls == 1:
        score += 12
        reasons.append("1 harekette tekrar konsolidasyonu mevcut.")

    # 3. Kuvvet/Kilo Oranı Orta Seviye Eşikleri (max 25 puan)
    interm_hits = 0
    for lk, ratio in compound_ratios.items():
        std_interm = (profiles or LIFT_PROFILES).get(lk, LIFT_PROFILES["squat"])["bw_standards"][1]
        if ratio >= std_interm:
            interm_hits += 1
    if interm_hits >= 2:
        score += 25
        reasons.append(f"{interm_hits} temel lift vücut ağırlığı orta seviye oranına ulaştı.")
    elif interm_hits == 1:
        score += 12

    # 4. e1RM Eğim Yavaşlaması (max 15 puan)
    if compound_e1rm_slopes:
        avg_slope = sum(compound_e1rm_slopes) / len(compound_e1rm_slopes)
        if avg_slope <= 0.8:
            score += 15
            reasons.append(f"Ortalama e1RM artış hızı yavaşladı ({avg_slope:.1f} kg/seans).")
        elif avg_slope <= 2.0:
            score += 6

    # 5. Toparlanma baskısı bonusu
    if acwr > 1.35 or hrv_ratio < 0.85:
        score = min(100, score + 10)
        reasons.append("Sistemik yorgunluk (ACWR/HRV) Squat yükünü zorlaştırıyor.")

    score = min(100, max(0, score))

    # Program her zaman haftada 2 gün A/B (5x5); plato yalnızca yükleme stratejisini (mikro-yükleme/deload) etkiler.
    recommended_split = "5x5_linear"
    if score >= 55:
        tier_label = "Plato Sinyali (5x5 A/B · Mikro-yükleme / Deload)"
        recommendation = (
            "5x5 doğrusal yükleme sınırına yaklaşıldı. Haftalık 2 gün A/B düzeni değişmez; takılan hareketlerde "
            "mikro-yükleme (+1.25 kg), tekrar/set varyasyonu veya deload uygula."
        )
    elif score >= 30:
        tier_label = "İzlemede (5x5 A/B Devam)"
        recommendation = (
            "Doğrusal progresyon hâlâ çalışıyor; ancak takılma yaşayan hareketlerde konsolidasyon/deload "
            "takip edilmeli. Program A/B 5x5 olarak devam eder."
        )
    else:
        tier_label = "Doğrusal İvme Aktif (5x5 Optimal)"
        recommendation = (
            "Tüm ana bileşiklerde e1RM eğimi güçlü. 5x5 doğrusal artış ile en hızlı kuvvet kazanımı devam ediyor."
        )

    if not reasons:
        reasons.append("Bileşik hareketlerde henüz plato sinyali yok; doğrusal artış verimli.")

    return {
        "plateau_score": score,
        "recommended_split": recommended_split,
        "tier_label": tier_label,
        "recommendation": recommendation,
        "signals": reasons,
        "total_deloads": total_deloads,
        "total_stalls": total_stalls,
        "compound_ratios": compound_ratios,
    }


# Split bazlı seans şablonları: slot -> (rozet, başlık, hedef, ısınma, [(key, kısa_ad, uzun_ad, set, tekrar, dinlenme, RPE, türetme)])
# türetme: (kaynak_key, katsayı) -> ağırlık kaynak hareketten türetilir (tahmini); None -> doğrudan progresyon.
SPLIT_SESSION_TEMPLATES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "push_pull": {
        "push": {
            "type": "Push", "title": "Kuvvet · Push (İtme & Ön Bacak)",
            "day_title": "Kuvvet Reçetesi · Push (İtme & Ön Bacak)",
            "objective": "Squat, göğüs ve omuz itişlerinde ana güç; yan deltoid hacmi. Çekme günüyle dönüşümlü uygulanır.",
            "warmup": "5 dk dinamik kalça & omuz mobilitesi + boş bar ile Squat ve Bench Press için 2x8 ısınma.",
            "lifts": [
                ("squat", "Squat", "Barbell Back Squat", 4, "6", "150 - 180 sn", "8.0", None),
                ("bench", "Bench", "Barbell Bench Press", 4, "6-8", "120 - 150 sn", "8.5", None),
                ("ohp", "OHP", "Barbell Overhead Press (OHP)", 3, "8", "120 sn", "8.0", None),
                ("incline_db", "Incline DB", "Incline Dumbbell Press", 3, "10", "90 sn", "8.0", ("bench", 0.34)),
                ("lateral_raise", "Lateral", "Dumbbell Lateral Raise (Yan Açış)", 4, "12", "60 - 75 sn", "8.0", None),
            ],
        },
        "pull": {
            "type": "Pull", "title": "Kuvvet · Pull (Çekme & Arka Zincir)",
            "day_title": "Kuvvet Reçetesi · Pull (Çekme & Arka Zincir)",
            "objective": "Deadlift, kürek ve lat çekişleriyle arka zincir gücü; trapez ve tutuş gelişimi.",
            "warmup": "5 dk kalça menteşesi mobilitesi + boş bar ile Deadlift ve Row için 2x8 ısınma.",
            "lifts": [
                ("deadlift", "Deadlift", "Barbell Deadlift", 3, "5", "180 sn", "8.5", None),
                ("row", "Row", "Barbell Bent-Over Row", 4, "6-8", "120 - 150 sn", "8.0", None),
                ("lat_pulldown", "Lat Pulldown", "Lat Pulldown (Geniş Tutuş)", 4, "10", "90 sn", "8.0", None),
                ("rdl", "RDL", "Romanian Deadlift (RDL)", 3, "8", "120 sn", "8.0", ("deadlift", 0.85)),
                ("shrug", "Shrug", "Dumbbell / Barbell Shrug (Trapez)", 3, "12", "60 - 75 sn", "8.0", None),
            ],
        },
    },
    "upper_lower": {
        "upper": {
            "type": "Upper", "title": "Kuvvet · Upper Body (Üst Vücut)",
            "day_title": "Kuvvet Reçetesi · Upper Body (Üst Vücut Güç)",
            "objective": "İtme-çekme dengesini koruyan üst vücut güç ve hipertrofi günü (Top Set + Back-off).",
            "warmup": "5 dk omuz/skapula mobilitesi + hafif Bench ve Row ısınma setleri.",
            "lifts": [
                ("bench", "Bench", "Barbell Bench Press", 4, "6", "120 - 150 sn", "8.5", None),
                ("row", "Row", "Barbell Bent-Over Row", 4, "6", "120 - 150 sn", "8.0", None),
                ("ohp", "OHP", "Barbell Overhead Press (OHP)", 3, "8", "120 sn", "8.0", None),
                ("lat_pulldown", "Lat", "Lat Pulldown (Geniş Tutuş)", 3, "10", "90 sn", "8.0", None),
                ("lateral_raise", "Lateral", "Dumbbell Lateral Raise (Yan Açış)", 3, "12", "60 - 75 sn", "8.0", None),
            ],
        },
        "lower": {
            "type": "Lower", "title": "Kuvvet · Lower Body (Alt Vücut)",
            "day_title": "Kuvvet Reçetesi · Lower Body (Alt Vücut Güç)",
            "objective": "Squat ve Deadlift ile alt vücut kuvvet hacmi; arka zincir ve trapez desteği.",
            "warmup": "5 dk kalça & ayak bileği mobilitesi + boş bar Squat ısınma setleri.",
            "lifts": [
                ("squat", "Squat", "Barbell Back Squat", 4, "5-6", "150 - 180 sn", "8.5", None),
                ("deadlift", "Deadlift", "Barbell Deadlift", 2, "5", "180 sn", "8.5", None),
                ("rdl", "RDL", "Romanian Deadlift (RDL)", 3, "8", "120 sn", "8.0", ("deadlift", 0.80)),
                ("shrug", "Shrug", "Dumbbell / Barbell Shrug (Trapez)", 3, "12", "60 - 75 sn", "8.0", None),
            ],
        },
    },
    "ppl": {
        "push": {
            "type": "Push", "title": "Kuvvet · PPL Push",
            "day_title": "Kuvvet Reçetesi · PPL Push (Göğüs / Omuz / Triceps)",
            "objective": "Göğüs, omuz ve triceps hacmi; yüksek tekrarlı yan deltoid.",
            "warmup": "5 dk omuz mobilitesi + hafif Bench ısınma setleri.",
            "lifts": [
                ("bench", "Bench", "Barbell Bench Press", 4, "6-8", "120 - 150 sn", "8.5", None),
                ("ohp", "OHP", "Barbell Overhead Press (OHP)", 3, "8-10", "120 sn", "8.0", None),
                ("incline_db", "Incline DB", "Incline Dumbbell Press", 3, "10", "90 sn", "8.0", ("bench", 0.34)),
                ("lateral_raise", "Lateral", "Dumbbell Lateral Raise (Yan Açış)", 4, "15", "60 sn", "8.0", None),
            ],
        },
        "pull": {
            "type": "Pull", "title": "Kuvvet · PPL Pull",
            "day_title": "Kuvvet Reçetesi · PPL Pull (Sırt / Arka Omuz / Biceps)",
            "objective": "Sırt kalınlığı ve genişliği; trapez ve tutuş gücü.",
            "warmup": "5 dk skapula mobilitesi + hafif Row ısınma setleri.",
            "lifts": [
                ("deadlift", "Deadlift", "Barbell Deadlift", 2, "5", "180 sn", "8.5", None),
                ("row", "Row", "Barbell Bent-Over Row", 4, "6-8", "120 - 150 sn", "8.0", None),
                ("lat_pulldown", "Lat", "Lat Pulldown (Geniş Tutuş)", 4, "10", "90 sn", "8.0", None),
                ("shrug", "Shrug", "Dumbbell / Barbell Shrug (Trapez)", 3, "12", "60 - 75 sn", "8.0", None),
            ],
        },
        "legs": {
            "type": "Legs", "title": "Kuvvet · PPL Legs",
            "day_title": "Kuvvet Reçetesi · PPL Legs (Bacak & Core)",
            "objective": "Bacak hacmi ve alt vücut gücü; toparlanma penceresi için ayrı gün.",
            "warmup": "5 dk kalça & ayak bileği mobilitesi + boş bar Squat ısınma setleri.",
            "lifts": [
                ("squat", "Squat", "Barbell Back Squat", 4, "6", "150 - 180 sn", "8.5", None),
                ("rdl", "RDL", "Romanian Deadlift (RDL)", 3, "8-10", "120 sn", "8.0", ("deadlift", 0.80)),
                ("bulgarian", "Bulgar Squat / Calf", "Bulgarian Split Squat / Calf Raise", 3, "12", "75 sn", "8.0", "bodyweight"),
            ],
        },
    },
}


def _template_weight(key: str, derived: Any, progression: Dict[str, Any], idx_of) -> Optional[float]:
    """Şablondaki bir hareket için bir sonraki seans kilosunu verir (türetilmişse kaynak hareketten)."""
    if derived == "bodyweight":
        return None
    if derived:
        base_key, factor = derived
        base = progression.get(base_key) or {}
        pw = base.get("projected_weights") or []
        i = idx_of(base_key)
        base_kg = float(pw[i]) if i < len(pw) else float(base.get("next_kg") or default_start_kg(LIFT_PROFILES[base_key])[1])
        return round_to_plate(base_kg * factor, 2.5)
    p = progression.get(key) or {}
    pw = p.get("projected_weights") or []
    i = idx_of(key)
    if i < len(pw):
        return float(pw[i])
    return float(p.get("next_kg") or default_start_kg(LIFT_PROFILES[key])[1])


def build_split_protocol(slot_kind: str, progression: Dict[str, Any], active_split: str) -> Optional[Dict[str, Any]]:
    """Push/Pull, Upper/Lower veya PPL için gerçek hareketler + hedef kilolarla günlük reçete döner."""
    tpl = (SPLIT_SESSION_TEMPLATES.get(active_split) or {}).get(slot_kind)
    if not tpl:
        return None
    exercises: List[Dict[str, Any]] = []
    for i, (key, _short, long_name, sets, reps, rest, rpe, derived) in enumerate(tpl["lifts"], start=1):
        kg = _template_weight(key, derived, progression, lambda _k: 0)
        entry = progression.get(key) or {}
        achieved = ""
        if entry.get("max_kg"):
            achieved = f"{float(entry['max_kg']):.1f} kg ({entry.get('last_date', 'Son')})"
        target = f"{kg:.1f} kg x {reps} reps x {sets} set" if kg is not None else f"Vücut ağırlığı / hafif dambıl x {reps} reps x {sets} set"
        if derived and derived != "bodyweight":
            target += " (tahmini)"
        exercises.append({
            "num": i, "name": long_name, "sets": sets, "reps": reps,
            "current_achieved": achieved, "target_weight": target,
            "rest_sec": rest, "target_rpe": rpe, "coaching_cue": "",
        })
    return {
        "day_title": tpl["day_title"], "badge": tpl["type"], "objective": tpl["objective"],
        "warmup": tpl["warmup"], "exercises": exercises,
    }


def _build_core_summary(
    slot_kind: str,
    progression: Dict[str, Any],
    step_idx: int = 0,
    active_split: str = "5x5_linear",
    ex_counts: Optional[Dict[str, int]] = None,
) -> Tuple[str, str, str]:
    """
    Belirtilen seans slotu için her hareketin kendi projeksiyon sayacını (ex_counts)
    kullanarak gerçek kilo progresyonlu başlık ve egzersiz özeti üretir.
    """
    def _w(key: str) -> float:
        idx = ex_counts.get(key, 0) if ex_counts is not None else step_idx
        if ex_counts is not None:
            ex_counts[key] = idx + 1
        p = progression.get(key) or {}
        pw = p.get("projected_weights") or []
        if idx < len(pw):
            return float(pw[idx])
        return float(p.get("next_kg") or default_start_kg(LIFT_PROFILES[key])[1])

    tpl_map = SPLIT_SESSION_TEMPLATES.get(active_split)
    if tpl_map:
        tpl = tpl_map.get(slot_kind)
        if tpl is None:
            ordered = list(tpl_map.keys())
            tpl = tpl_map[ordered[0] if slot_kind == "gym_a" else ordered[min(1, len(ordered) - 1)]]
        parts: List[str] = []
        for key, short, _long, sets, reps, _rest, _rpe, derived in tpl["lifts"]:
            if derived == "bodyweight":
                parts.append(f"{short} ({sets}x{reps})")
                continue
            if derived:
                kg = _template_weight(key, derived, progression, lambda k: ex_counts.get(k, 0) if ex_counts is not None else step_idx)
            else:
                kg = _w(key)
            parts.append(f"{short} {kg:.1f} kg ({sets}x{reps})")
        return (tpl["type"], tpl["title"], " · ".join(parts))

    # Varsayılan: 5x5_linear (Workout A: 5 egzersiz, Workout B: 6 egzersiz)
    if slot_kind == "gym_a":
        sq, bp, rw, lr, sh = _w("squat"), _w("bench"), _w("row"), _w("lateral_raise"), _w("shrug")
        return (
            "Workout A",
            "Kuvvet #1 · Workout A (5x5)",
            f"Squat {sq:.1f} kg (5x5) · Bench {bp:.1f} kg (5x5) · Row {rw:.1f} kg (5x5) · Lateral {lr:.1f} kg (3x12) · Shrug {sh:.1f} kg (3x12)",
        )
    sq, ohp, dl, lat, lr, sh = _w("squat"), _w("ohp"), _w("deadlift"), _w("lat_pulldown"), _w("lateral_raise"), _w("shrug")
    return (
        "Workout B",
        "Kuvvet #2 · Workout B (5x5)",
        f"Squat {sq:.1f} kg (5x5) · OHP {ohp:.1f} kg (5x5) · Deadlift {dl:.1f} kg (1x5) · Lat {lat:.1f} kg (4x12) · Lateral {lr:.1f} kg (3x12) · Shrug {sh:.1f} kg (3x12)",
    )


def _extra_slot_for(entry: Dict[str, Any], active_split: str) -> str:
    """Çekirdek dışı yeni bir hareketin hangi seans slotuna ait olduğunu belirler."""
    if active_split == "5x5_linear":
        return "gym_a" if "Workout A" in str(entry.get("slot_hint", "")) else "gym_b"
    if active_split == "upper_lower":
        return "lower" if entry.get("is_leg") and not entry.get("is_pull") else "upper"
    if active_split == "ppl":
        if entry.get("is_leg") and not entry.get("is_pull"):
            return "legs"
        return "pull" if entry.get("is_pull") else "push"
    return "pull" if entry.get("is_pull") else "push"


def build_projected_gym_summary(
    slot_kind: str,
    progression: Dict[str, Any],
    step_idx: int = 0,
    active_split: str = "5x5_linear",
    ex_counts: Optional[Dict[str, int]] = None,
) -> Tuple[str, str, str]:
    """Çekirdek hareketler + Garmin'den gelen yeni hareketleri (güncel kiloları ile) seans özetine ekler."""
    p_type, p_title, details = _build_core_summary(slot_kind, progression, step_idx, active_split, ex_counts)

    dated = [e.get("last_full_date", "") for e in progression.values() if e.get("last_full_date")]
    newest = max(dated) if dated else ""
    canonical = {"gym_a": "gym_a", "gym_b": "gym_b"}
    eff_slot = canonical.get(slot_kind, slot_kind)
    parts: List[str] = []
    for key, entry in progression.items():
        if entry.get("is_core") or entry.get("is_split_derived") or not entry.get("last_full_date"):
            continue
        try:
            gap = (datetime.strptime(newest[:10], "%Y-%m-%d") - datetime.strptime(entry["last_full_date"][:10], "%Y-%m-%d")).days
        except (ValueError, TypeError):
            logger.debug("build_projected_gym_summary: yedek davranış uygulandı", exc_info=True)
            gap = 0
        if gap > 21:
            continue
        slot_for = _extra_slot_for(entry, active_split)
        if slot_for != eff_slot and not (active_split != "5x5_linear" and slot_kind == "gym_a" and slot_for == "push") \
                and not (active_split != "5x5_linear" and slot_kind == "gym_b" and slot_for == "pull"):
            continue
        idx = ex_counts.get(key, 0) if ex_counts is not None else step_idx
        if ex_counts is not None:
            ex_counts[key] = idx + 1
        pw = entry.get("projected_weights") or []
        kg = float(pw[idx]) if idx < len(pw) else float(entry.get("next_kg") or 0)
        parts.append(f"{entry.get('name')} {kg:.1f} kg ({entry.get('short_rep') or ''})".replace(" ()", ""))
    if parts:
        details = details + " · " + " · ".join(parts)
    return p_type, p_title, details


def inject_split_derived_lifts(progression: Dict[str, Any], active_split: str, bodyweight_kg: float = 75.0) -> None:
    """Push/Pull, Upper/Lower veya PPL aktif olduğunda türetilmiş yeni hareketleri (Incline DB, RDL vb.) progresyon kartlarına ekler."""
    tpl_map = SPLIT_SESSION_TEMPLATES.get(active_split)
    if not tpl_map:
        return
    for slot_kind, tpl in tpl_map.items():
        for key, _short, long_name, sets, reps, _rest, _rpe, derived in tpl["lifts"]:
            if key in progression or not derived or derived == "bodyweight":
                continue
            base_key, factor = derived
            base = progression.get(base_key) or {}
            base_next = float(base.get("next_kg") or default_start_kg(LIFT_PROFILES[base_key])[1] if base_key in LIFT_PROFILES else 20.0)
            kg0 = round_to_plate(base_next * factor, 2.5)
            kg1 = round_to_plate(kg0 + 2.5, 2.5)
            kg2 = round_to_plate(kg1 + 2.5, 2.5)
            progression[key] = {
                "is_core": False,
                "is_split_derived": True,
                "is_pull": slot_kind == "pull",
                "is_leg": slot_kind in ("lower", "legs"),
                "short_rep": f"{sets}x{reps}",
                "slot_hint": tpl["type"],
                "last_full_date": base.get("last_full_date") or datetime.now().strftime("%Y-%m-%d"),
                "name": long_name,
                "history": [f"Türetildi: {base.get('name', base_key)} ({base_next:.1f} kg)"],
                "delta": f"{tpl['type']} Yeni Hareket",
                "max_kg": kg0,
                "effective_kg": kg0,
                "e1rm_kg": compute_e1rm(kg0, 10),
                "e1rm_slope": 0.0,
                "bw_ratio": round(compute_e1rm(kg0, 10) / max(40.0, bodyweight_kg), 2),
                "last_date": "Yeni",
                "last_outcome": "DERIVED",
                "consecutive_stalls": 0,
                "deload_count": 0,
                "decision": "PROGRESS",
                "decision_reason": f"{base.get('name', base_key)} e1RM gücünden {tpl['type']} seansı için hesaplandı.",
                "next_kg": kg0,
                "next_target": f"{kg0:.1f} kg x {reps} reps x {sets} set",
                "projected_weights": [kg0, kg1, kg2],
            }
