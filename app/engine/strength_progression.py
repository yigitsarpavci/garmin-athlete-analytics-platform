#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyarlanabilir Kuvvet Progresyonu, Çok Faktörlü Ağırlık Hesaplama,
Başarısızlık/Kısmi Tamamlama Sonrası Dinamik Yeniden Planlama ve
Plato Tabanlı Program Evrimi (5x5 -> Push/Pull -> Upper/Lower -> PPL) Motoru.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# Egzersiz biyomekanik ve standart profilleri
# (key, display_label, match_name, target_sets, target_reps, step_kg, rep_suffix,
#  fallback_max_kg, fallback_next_kg, bw_standards: (novice, intermediate, advanced))
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
        "fallback_max": 65.0,
        "fallback_next": 67.5,
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
        "fallback_max": 50.0,
        "fallback_next": 52.5,
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
        "fallback_max": 60.0,
        "fallback_next": 62.5,
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
        "fallback_max": 40.0,
        "fallback_next": 40.0,
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
        "fallback_max": 60.0,
        "fallback_next": 65.0,
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
        "fallback_max": 45.0,
        "fallback_next": 45.0,
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
        "fallback_max": 25.0,
        "fallback_next": 25.0,
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
        "fallback_max": 45.0,
        "fallback_next": 47.5,
        "bw_standards": (0.50, 0.70, 0.95),
        "is_compound": False,
    },
}

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
) -> Dict[str, Any]:
    """Tek bir seanstaki tek bir hareketin set/tekrar kalitesini, düşüş oranını ve e1RM'ini analiz eder."""
    spec = LIFT_PROFILES[lift_key]
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


def load_logged_gym_sessions(data_dir: str) -> List[Dict[str, Any]]:
    """Kullanıcının uygulama üzerinden girdiği tamamlanmış/başarısız kuvvet seanslarını yükler."""
    path = os.path.join(data_dir, "logged_gym_sessions.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_logged_gym_session(data_dir: str, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Yeni manuel kuvvet seansı sonucunu kaydeder."""
    sessions = load_logged_gym_sessions(data_dir)
    sessions.append(entry)
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "logged_gym_sessions.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)
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
    except Exception:
        pass
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
    path = os.path.join(data_dir, "training_program_state.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def compute_adaptive_progression(
    chrono_sessions: List[Dict[str, Any]],
    bodyweight_kg: float = 87.0,
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
        except Exception:
            ref_dt = None

    progression: Dict[str, Any] = {}
    stall_summary: List[str] = []
    total_deloads = 0
    total_stalls = 0
    compound_e1rm_slopes: List[float] = []
    compound_ratios: Dict[str, float] = {}

    for key, spec in LIFT_PROFILES.items():
        match_name = spec["match_name"]
        step_kg = spec["step_kg"]
        rep_suffix = spec["rep_suffix"]
        lift_records: List[Dict[str, Any]] = []

        for sess in chrono_sessions:
            for ex in sess.get("exercises", []):
                if ex.get("name") == match_name:
                    eval_res = evaluate_session_lift(key, ex.get("sets", []))
                    if eval_res.get("has_data"):
                        lift_records.append({
                            "date": sess.get("date", ""),
                            "workout_type": sess.get("workout_type", ""),
                            **eval_res,
                        })

        if not lift_records:
            progression[key] = {
                "name": spec["label"],
                "history": [],
                "delta": "Veri Bekleniyor",
                "max_kg": spec["fallback_max"],
                "effective_kg": spec["fallback_max"],
                "e1rm_kg": compute_e1rm(spec["fallback_max"], spec["target_reps"]),
                "e1rm_slope": 0.0,
                "bw_ratio": round(compute_e1rm(spec["fallback_max"], spec["target_reps"]) / max(40.0, bodyweight_kg), 2),
                "last_date": "-",
                "last_outcome": "UNKNOWN",
                "consecutive_stalls": 0,
                "deload_count": 0,
                "decision": "BASELINE",
                "decision_reason": "Henüz kayıtlı set yok; başlangıç hedefi atandı.",
                "next_kg": spec["fallback_next"],
                "next_target": f"{spec['fallback_next']:.1f} kg {rep_suffix}",
                "projected_weights": [
                    spec["fallback_next"],
                    round_to_plate(spec["fallback_next"] + step_kg, step_kg),
                    round_to_plate(spec["fallback_next"] + 2 * step_kg, step_kg),
                ],
            }
            continue

        # Kronolojik ilerleyişten takılma & deload sayacı çıkar
        consec_stalls = 0
        deloads = 0
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
                if consec_stalls >= 2 and spec["is_compound"]:
                    deloads += 1
            else:
                consec_stalls = 0
            if prev_top > 0 and tw < prev_top * 0.90:
                deloads += 1
            prev_top = tw
            prev_eff = ew

        latest = lift_records[-1]
        first = lift_records[0]
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
            except Exception:
                days_gap = 0

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
                        f"Son seansta {last_w:.1f} kg ile başlanıp {eff_w:.1f} kg ortalamaya düşüldü; "
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
        else:
            # Başarılı tamamlama: artış miktarı belirle
            jump = step_kg
            # Deadlift < 1.25x BW iken +5 kg; sonrasında +2.5 kg'a geç
            if key == "deadlift" and bw_ratio >= 1.30:
                jump = 2.5
            # Eğer AMRAP / ekstra tekrar varsa ve başlangıç seviyesindeyse büyük artış kontrolü
            elif last_outcome == "PASSED_AMRAP" and spec["is_compound"] and bw_ratio < spec["bw_standards"][0]:
                jump = step_kg
            next_kg = round_to_plate(last_w + jump, 2.5)
            decision = "PROGRESS"
            reason = (
                f"Son seansta {last_w:.1f} kg ({latest['reps_pattern']}) temiz tamamlandı "
                f"(e1RM {latest_e1rm:.1f} kg); +{jump:.1f} kg progresyon uygulandı."
            )

        # Çok adımlı gelecek seans projeksiyonları [step0, step1, step2, step3]
        proj_weights = [next_kg]
        sim_w = next_kg
        for step_idx in range(1, 5):
            if key == "lateral_raise":
                # Lateral raise izolasyon olduğu için 2 seans konsolidasyon sonrası +2.5 kg artar
                if step_idx % 2 == 0:
                    sim_w = round_to_plate(sim_w + step_kg, 2.5)
            elif key == "deadlift":
                sim_step = 2.5 if (sim_w / max(40.0, bodyweight_kg)) >= 1.15 else 5.0
                sim_w = round_to_plate(sim_w + sim_step, 2.5)
            else:
                sim_w = round_to_plate(sim_w + step_kg, 2.5)
            proj_weights.append(sim_w)

        diff = round(last_w - first["top_weight_kg"], 1)
        history_strs = [f"{r['top_weight_kg']:.1f} kg ({r['date'][5:]})" for r in lift_records[-5:]]
        delta_str = (
            f"+{diff:.1f} kg ({len(lift_records)} seans)"
            if diff > 0
            else f"Stabil {last_w:.1f} kg ({len(lift_records)} seans)"
        )

        if consec_stalls > 0:
            total_stalls += 1
            stall_summary.append(f"{spec['label']} ({decision})")
        total_deloads += deloads

        if spec["is_compound"]:
            compound_e1rm_slopes.append(slope)
            compound_ratios[key] = bw_ratio

        progression[key] = {
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

    # Plato & Program Evrimi Skoru (0 - 100)
    plateau_score = _compute_plateau_score(
        progression=progression,
        total_deloads=total_deloads,
        total_stalls=total_stalls,
        compound_e1rm_slopes=compound_e1rm_slopes,
        compound_ratios=compound_ratios,
        acwr=acwr,
        hrv_ratio=hrv_ratio,
    )

    return {
        "progression": progression,
        "plateau_analysis": plateau_score,
        "readiness_note": readiness_note,
        "stall_summary": stall_summary,
    }


def _compute_plateau_score(
    progression: Dict[str, Any],
    total_deloads: int,
    total_stalls: int,
    compound_e1rm_slopes: List[float],
    compound_ratios: Dict[str, float],
    acwr: float,
    hrv_ratio: float,
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
        std_interm = LIFT_PROFILES[lk]["bw_standards"][1]
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
        reasons.append("Sistemik yorgunluk (ACWR/HRV) haftada 3 gün Squat yükünü zorlaştırıyor.")

    score = min(100, max(0, score))

    if score >= 55:
        recommended_split = "push_pull"
        tier_label = "Orta Seviye Geçiş Eşiği (Push / Pull Önerilir)"
        recommendation = (
            "5x5 doğrusal yükleme sınırına yaklaşıldı. Her seans Squat yorgunluğunu azaltmak ve "
            "üst/alt hacmini artırmak için Push / Pull programına geçiş önerilir."
        )
    elif score >= 30:
        recommended_split = "5x5_linear"
        tier_label = "Geçişe Yaklaşıyor (5x5 Devam · İzlemede)"
        recommendation = (
            "Doğrusal progresyon hâlâ çalışıyor; ancak takılma yaşayan hareketlerde konsolidasyon/deload "
            "takip edilmeli. 1-2 deload sonrası Push / Pull'a geçilecek."
        )
    else:
        recommended_split = "5x5_linear"
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


def build_projected_gym_summary(
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
        return float(p.get("next_kg") or LIFT_PROFILES[key]["fallback_next"])

    if active_split == "push_pull":
        if slot_kind in ("push", "gym_a"):
            sq, bp, ohp, lr = _w("squat"), _w("bench"), _w("ohp"), _w("lateral_raise")
            inc_db = round_to_plate(bp * 0.34, 2.5)
            return (
                "Push",
                "Kuvvet · Push (İtme & Ön Bacak)",
                f"Squat {sq:.1f} kg (4x6) · Bench {bp:.1f} kg (4x6-8) · OHP {ohp:.1f} kg (3x8) · Incline DB {inc_db:.1f} kg (3x10) · Lateral {lr:.1f} kg (4x12)",
            )
        else:
            dl, rw, lat, sh = _w("deadlift"), _w("row"), _w("lat_pulldown"), _w("shrug")
            rdl = round_to_plate(dl * 0.85, 2.5)
            return (
                "Pull",
                "Kuvvet · Pull (Çekme & Arka Zincir)",
                f"Deadlift {dl:.1f} kg (3x5) · Row {rw:.1f} kg (4x6-8) · Lat Pulldown {lat:.1f} kg (4x10) · RDL {rdl:.1f} kg (3x8) · Shrug {sh:.1f} kg (3x12)",
            )

    if active_split == "upper_lower":
        if slot_kind in ("upper", "gym_a"):
            bp, rw, ohp, lat, lr = _w("bench"), _w("row"), _w("ohp"), _w("lat_pulldown"), _w("lateral_raise")
            return (
                "Upper",
                "Kuvvet · Upper Body (Üst Vücut)",
                f"Bench {bp:.1f} kg (4x6) · Row {rw:.1f} kg (4x6) · OHP {ohp:.1f} kg (3x8) · Lat {lat:.1f} kg (3x10) · Lateral {lr:.1f} kg (3x12)",
            )
        else:
            sq, dl, sh = _w("squat"), _w("deadlift"), _w("shrug")
            rdl = round_to_plate(dl * 0.80, 2.5)
            return (
                "Lower",
                "Kuvvet · Lower Body (Alt Vücut)",
                f"Squat {sq:.1f} kg (4x5-6) · Deadlift {dl:.1f} kg (2x5) · RDL {rdl:.1f} kg (3x8) · Shrug {sh:.1f} kg (3x12)",
            )

    if active_split == "ppl":
        if slot_kind in ("push", "gym_a"):
            bp, ohp, lr = _w("bench"), _w("ohp"), _w("lateral_raise")
            inc_db = round_to_plate(bp * 0.34, 2.5)
            return (
                "Push",
                "Kuvvet · PPL Push",
                f"Bench {bp:.1f} kg (4x6-8) · OHP {ohp:.1f} kg (3x8-10) · Incline DB {inc_db:.1f} kg (3x10) · Lateral {lr:.1f} kg (4x15)",
            )
        elif slot_kind in ("pull", "gym_b"):
            dl, rw, lat, sh = _w("deadlift"), _w("row"), _w("lat_pulldown"), _w("shrug")
            return (
                "Pull",
                "Kuvvet · PPL Pull",
                f"Deadlift {dl:.1f} kg (2x5) · Row {rw:.1f} kg (4x6-8) · Lat {lat:.1f} kg (4x10) · Shrug {sh:.1f} kg (3x12)",
            )
        else:
            sq, dl = _w("squat"), _w("deadlift")
            rdl = round_to_plate(dl * 0.80, 2.5)
            return (
                "Legs",
                "Kuvvet · PPL Legs",
                f"Squat {sq:.1f} kg (4x6) · RDL {rdl:.1f} kg (3x8-10) · Bulgar Squat / Calf (3x12)",
            )

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
