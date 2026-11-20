#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyarlanabilir Kuvvet Progresyonu, Çok Faktörlü Ağırlık Hesaplama,
Başarısızlık/Kısmi Tamamlama Sonrası Dinamik Yeniden Planlama ve
Plato Tabanlı Program Evrimi (5x5 -> Push/Pull -> Upper/Lower -> PPL) Motoru.
"""

from __future__ import annotations

import logging
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