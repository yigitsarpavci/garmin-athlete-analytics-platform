"""
Garmin İlk-Prensip Koşu Yük Simülatörü (Next-4 Run Load Predictor)
==================================================================
Sabit/presetli haftalık koşu sırası yerine, son gerçek Garmin koşularının
EPOC yükü ve Training Effect (aTE / anTE) profilini kullanarak sıradaki N (varsayılan 4)
koşuyu kapalı çevrim simüle eder:
  1. Her adımda en düşük Firstbeat yük barını (Düşük Aerobik vs Anaerobik) hedefler.
     (Anaerobik interval Yüksek Aerobik'i de geliştirdiği için ayrı tempo barı hedeflenmez.)
  2. Seçilen türün (zone2 / interval) en son gerçek Garmin koşusunun barlara kattığı
     tahmini yükü hesaplayıp mevcut barların üzerine ekler.
  3. Güncellenen olasılık barlarıyla bir sonraki koşuyu tahminler.
"""

from typing import Any, Dict, List, Optional, Tuple
from .helpers import classify_run_workout


def estimate_run_load_contribution(act: Optional[Dict[str, Any]], kind: str) -> Dict[str, float]:
    """Bir koşu aktivitesinin 3 Firstbeat yük barına (low, high, anaerobic) tahmini katkısını döner."""
    default_load = 95.0 if kind == "zone2" else 135.0
    default_ate = 3.3 if kind == "zone2" else 3.1
    default_ante = 0.0 if kind == "zone2" else 3.0

    total_load = float((act or {}).get("activityTrainingLoad") or default_load)
    a_te = float((act or {}).get("aerobicTrainingEffect") if (act or {}).get("aerobicTrainingEffect") is not None else default_ate)
    an_te = float((act or {}).get("anaerobicTrainingEffect") if (act or {}).get("anaerobicTrainingEffect") is not None else default_ante)

    te_sum = max(0.1, a_te + an_te)
    if kind == "interval":
        an_share = min(0.62, max(0.28, an_te / te_sum))
        aer_load = total_load * (1.0 - an_share)
        low_add = round(aer_load * 0.32, 1)
        high_add = round(aer_load * 0.68, 1)
        an_add = round(total_load * an_share, 1)
    else:
        an_share = min(0.10, max(0.0, an_te / (te_sum * 2.5))) if an_te > 0 else 0.0
        aer_load = total_load * (1.0 - an_share)
        low_add = round(aer_load * 0.88, 1)
        high_add = round(aer_load * 0.12, 1)
        an_add = round(total_load * an_share, 1)

    return {
        "total_load": round(total_load, 1),
        "aerobic_te": round(a_te, 1),
        "anaerobic_te": round(an_te, 1),
        "low_aerobic": low_add,
        "high_aerobic": high_add,
        "anaerobic": an_add,
    }


def get_latest_run_profiles(activities_all: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Geçmiş koşulardan en son gerçek Zone 2 ve İnterval koşu profillerini çıkarır."""
    latest_by_kind: Dict[str, Optional[Dict[str, Any]]] = {"zone2": None, "interval": None}

    sorted_acts = sorted(
        activities_all or [],
        key=lambda x: x.get("startTimeLocal") or "",
        reverse=True,
    )
    for act in sorted_acts:
        t_key = (act.get("activityType") or {}).get("typeKey", "").lower()
        if "run" not in t_key:
            continue
        cls = classify_run_workout(act)
        k = cls.get("kind")
        if k in latest_by_kind and latest_by_kind[k] is None:
            latest_by_kind[k] = act
        if latest_by_kind["zone2"] is not None and latest_by_kind["interval"] is not None:
            break

    profiles: Dict[str, Dict[str, Any]] = {}
    for k in ("zone2", "interval"):
        src = latest_by_kind[k]
        contrib = estimate_run_load_contribution(src, k)
        profiles[k] = {
            "source_date": ((src or {}).get("startTimeLocal") or "")[:10] or None,
            "source_name": (src or {}).get("activityName") or ("Zone 2 Koşusu" if k == "zone2" else "Hız İntervali"),
            **contrib,
        }
    return profiles


def _compute_bar_pcts(
    low_act: float,
    high_act: float,
    an_act: float,
    low_max: float,
    high_max: float,
    an_max: float,
    targets_available: bool,
) -> Tuple[float, float, float]:
    """Hedef tavanı varsa hedef %'si; yoksa Firstbeat standart pay oranı (45/35/20) üzerinden doluluk %'si döner."""
    if targets_available and low_max > 0 and an_max > 0:
        low_pct = round((low_act / low_max) * 100.0, 1)
        high_pct = round((high_act / high_max) * 100.0, 1) if high_max > 0 else 0.0
        an_pct = round((an_act / an_max) * 100.0, 1)
        return low_pct, high_pct, an_pct

    total = max(1.0, low_act + high_act + an_act)
    # Firstbeat hedef verisi yokken referans ideal paylar: %45 Low, %35 High, %20 Anaerobic
    low_pct = round(((low_act / total) / 0.45) * 100.0, 1)
    high_pct = round(((high_act / total) / 0.35) * 100.0, 1)
    an_pct = round(((an_act / total) / 0.20) * 100.0, 1)
    return low_pct, high_pct, an_pct


def predict_next_n_runs(
    load_focus: Dict[str, Any],
    activities_all: List[Dict[str, Any]],
    n: int = 4,
) -> Dict[str, Any]:
    """
    Mevcut Firstbeat yük barlarından başlayarak sıradaki n koşuyu adım adım simüle eder.
    Her adımda en düşük barı seçer, o türün son koşusunun katkısını ekleyip barları günceller.
    """
    al = load_focus.get("aerobic_low") or {}
    ah = load_focus.get("aerobic_high") or {}
    an = load_focus.get("anaerobic") or {}

    low_act = float(al.get("actual") or 0.0)
    high_act = float(ah.get("actual") or 0.0)
    an_act = float(an.get("actual") or 0.0)
    low_max = float(al.get("target_max") or 0.0)
    high_max = float(ah.get("target_max") or 0.0)
    an_max = float(an.get("target_max") or 0.0)
    targets_available = bool(load_focus.get("targets_available", True) and low_max > 0 and an_max > 0)

    profiles = get_latest_run_profiles(activities_all)
    steps: List[Dict[str, Any]] = []

    for step_idx in range(1, n + 1):
        low_pct, high_pct, an_pct = _compute_bar_pcts(
            low_act, high_act, an_act, low_max, high_max, an_max, targets_available
        )
        chosen = "zone2" if low_pct < an_pct else "interval"
        prof = profiles[chosen]

        new_low = round(low_act + prof["low_aerobic"], 1)
        new_high = round(high_act + prof["high_aerobic"], 1)
        new_an = round(an_act + prof["anaerobic"], 1)
        after_low_pct, after_high_pct, after_an_pct = _compute_bar_pcts(
            new_low, new_high, new_an, low_max, high_max, an_max, targets_available
        )

        label_tr = "Zone 2 Rahat Taban" if chosen == "zone2" else "5K Hız İntervali (Z4-5)"
        reason = (
            f"Koşu #{step_idx} öncesi Düşük Aerobik %{low_pct:.0f} < Anaerobik %{an_pct:.0f} -> {label_tr}"
            if chosen == "zone2"
            else f"Koşu #{step_idx} öncesi Anaerobik %{an_pct:.0f} <= Düşük Aerobik %{low_pct:.0f} -> {label_tr}"
        )

        steps.append({
            "step": step_idx,
            "kind": chosen,
            "label": label_tr,
            "reason": reason,
            "source_date": prof["source_date"],
            "estimated_total_load": prof["total_load"],
            "added_load": {
                "low_aerobic": prof["low_aerobic"],
                "high_aerobic": prof["high_aerobic"],
                "anaerobic": prof["anaerobic"],
            },
            "before_pcts": {"low_aerobic": low_pct, "high_aerobic": high_pct, "anaerobic": an_pct},
            "after_pcts": {"low_aerobic": after_low_pct, "high_aerobic": after_high_pct, "anaerobic": after_an_pct},
        })

        low_act, high_act, an_act = new_low, new_high, new_an

    return {
        "n": n,
        "targets_available": targets_available,
        "profiles": profiles,
        "steps": steps,
        "sequence": [s["kind"] for s in steps],
    }
