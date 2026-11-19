"""
Garmin İlk-Prensip Koşu & Yük Simülatörü (Next-4 Load Predictor)
==================================================================
Mevcut Firstbeat 3 yük barı (Düşük Aerobik, Yüksek Aerobik, Anaerobik) üzerinden
sıradaki N (varsayılan 4) seansı kapalı çevrim simüle eder:
  1. 28 günlük pencereden her adımda düşecek (expire olacak) geçmiş antrenman
     yüklerini gerçek Garmin geçmişinden çıkarır.
  2. En düşük doluluktaki barı hedefler:
     - Düşük Aerobik en düşükse -> Zone 2 (zone2)
     - Yüksek Aerobik en düşükse -> Tempo (tempo; yalnızca Garmin hedef bantları varsa)
     - Anaerobik en düşükse -> İnterval (interval)
  3. Seçilen türün en son gerçek Garmin koşusunun EPOC/TE katkısını barlara ekler.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from .helpers import classify_run_workout

OVERFLOW_THRESHOLD_PCT = 85.0
STEP_DAY_OFFSETS = (0, 3, 7, 10)


def estimate_activity_load_contribution(act: Optional[Dict[str, Any]], kind: Optional[str] = None) -> Dict[str, float]:
    """Herhangi bir aktivitenin (veya belirtilen koşu türünün) 3 yük barına tahmini katkısını döner."""
    if kind is None and act is not None:
        t_key = ((act.get("activityType") or {}).get("typeKey") or "").lower()
        if "run" in t_key:
            kind = classify_run_workout(act).get("kind", "zone2")
        else:
            kind = "other"

    default_load = {"zone2": 95.0, "tempo": 105.0, "interval": 135.0}.get(kind or "zone2", 40.0)
    default_ate = {"zone2": 3.3, "tempo": 3.5, "interval": 3.1}.get(kind or "zone2", 2.0)
    default_ante = {"zone2": 0.0, "tempo": 0.0, "interval": 3.0}.get(kind or "zone2", 0.0)

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
    elif kind == "tempo":
        an_share = min(0.15, max(0.0, an_te / (te_sum * 2.0))) if an_te > 0 else 0.0
        aer_load = total_load * (1.0 - an_share)
        low_add = round(aer_load * 0.28, 1)
        high_add = round(aer_load * 0.72, 1)
        an_add = round(total_load * an_share, 1)
    elif kind == "other":
        an_share = min(0.40, max(0.0, an_te / te_sum)) if an_te > 0 else 0.0
        aer_load = total_load * (1.0 - an_share)
        low_add = round(aer_load * 0.75, 1)
        high_add = round(aer_load * 0.25, 1)
        an_add = round(total_load * an_share, 1)
    else:  # zone2
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
    """Geçmiş koşulardan en son gerçek Zone 2, Tempo ve İnterval koşu profillerini çıkarır."""
    latest_by_kind: Dict[str, Optional[Dict[str, Any]]] = {"zone2": None, "tempo": None, "interval": None}

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
        if all(latest_by_kind[x] is not None for x in latest_by_kind):
            break

    default_names = {
        "zone2": "Zone 2 Koşusu",
        "tempo": "Tempo",
        "interval": "İnterval",
    }
    profiles: Dict[str, Dict[str, Any]] = {}
    for k in ("zone2", "tempo", "interval"):
        src = latest_by_kind[k]
        contrib = estimate_activity_load_contribution(src, k)
        profiles[k] = {
            "source_date": ((src or {}).get("startTimeLocal") or "")[:10] or None,
            "source_name": (src or {}).get("activityName") or default_names[k],
            **contrib,
        }
    return profiles


def _compute_expiring_by_step(
    activities_all: List[Dict[str, Any]],
    ref_dt: datetime,
    n: int,
) -> List[Dict[str, float]]:
    """Her gelecek adımın gün penceresinde 28 günlük pencereden düşecek geçmiş yükleri toplar."""
    expiring_steps: List[Dict[str, float]] = [{"low_aerobic": 0.0, "high_aerobic": 0.0, "anaerobic": 0.0} for _ in range(n)]
    if not activities_all:
        return expiring_steps

    # 28 gün önce pencere sınırı: her adım k için [win_start, win_end) tarihli aktiviteler pencereden düşer
    ref_day = ref_dt.date()
    parsed: List[Tuple[Any, Dict[str, float]]] = []
    for act in activities_all:
        d_str = (act.get("startTimeLocal") or "")[:10]
        if not d_str:
            continue
        try:
            d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        parsed.append((d_obj, estimate_activity_load_contribution(act)))

    prev_offset = 0
    for idx in range(n):
        cur_offset = STEP_DAY_OFFSETS[idx] if idx < len(STEP_DAY_OFFSETS) else STEP_DAY_OFFSETS[-1] + 3 * (idx - len(STEP_DAY_OFFSETS) + 1)
        if cur_offset <= prev_offset:
            prev_offset = cur_offset
            continue
        win_start = ref_day - timedelta(days=28 - prev_offset)
        win_end = ref_day - timedelta(days=28 - cur_offset)
        low_d = high_d = an_d = 0.0
        for d_obj, contrib in parsed:
            if win_start <= d_obj < win_end:
                low_d += contrib["low_aerobic"]
                high_d += contrib["high_aerobic"]
                an_d += contrib["anaerobic"]
        expiring_steps[idx] = {
            "low_aerobic": round(low_d, 1),
            "high_aerobic": round(high_d, 1),
            "anaerobic": round(an_d, 1),
        }
        prev_offset = cur_offset
    return expiring_steps


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
    low_pct = round(((low_act / total) / 0.45) * 100.0, 1)
    high_pct = round(((high_act / total) / 0.35) * 100.0, 1)
    an_pct = round(((an_act / total) / 0.20) * 100.0, 1)
    return low_pct, high_pct, an_pct


def predict_next_n_runs(
    load_focus: Dict[str, Any],
    activities_all: List[Dict[str, Any]],
    n: int = 4,
    ref_dt: Optional[datetime] = None,
    overflow_threshold: float = OVERFLOW_THRESHOLD_PCT,
) -> Dict[str, Any]:
    """
    Mevcut Firstbeat yük barlarından başlayarak sıradaki n seansı simüle eder:
    - Her adımda 28 günlük pencereden düşecek geçmiş yükleri çıkarır.
    - Her adımda en düşük barı (zone2 / tempo / interval) seçip son gerçek koşunun katkısını ekler.
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

    now_dt = ref_dt or datetime.now()
    profiles = get_latest_run_profiles(activities_all)
    expiring_by_step = _compute_expiring_by_step(activities_all, now_dt, n)
    steps: List[Dict[str, Any]] = []

    labels = {
        "zone2": "Zone 2",
        "tempo": "Tempo",
        "interval": "İnterval",
    }

    for step_idx in range(1, n + 1):
        exp = expiring_by_step[step_idx - 1]
        low_act = max(0.0, round(low_act - exp["low_aerobic"], 1))
        high_act = max(0.0, round(high_act - exp["high_aerobic"], 1))
        an_act = max(0.0, round(an_act - exp["anaerobic"], 1))

        low_pct, high_pct, an_pct = _compute_bar_pcts(
            low_act, high_act, an_act, low_max, high_max, an_max, targets_available
        )

        pct_map = {"zone2": low_pct, "tempo": high_pct, "interval": an_pct}
        if not targets_available:
            # Hedef tavanı yokken Tempo aşırı tetiklenmesin; sadece Zone 2 vs İnterval dengesi
            pct_map = {"zone2": low_pct, "interval": an_pct}
        chosen = min(pct_map, key=lambda k: pct_map[k])
        prof = profiles[chosen]
        add_low = prof["low_aerobic"]
        add_high = prof["high_aerobic"]
        add_an = prof["anaerobic"]
        src_date = prof["source_date"]
        est_load = prof["total_load"]
        reason = (
            f"Koşu #{step_idx} öncesi en düşük bar {labels[chosen]} "
            f"(Düşük %{low_pct:.0f} · Yüksek %{high_pct:.0f} · Anaer %{an_pct:.0f})."
        )

        new_low = round(low_act + add_low, 1)
        new_high = round(high_act + add_high, 1)
        new_an = round(an_act + add_an, 1)
        after_low_pct, after_high_pct, after_an_pct = _compute_bar_pcts(
            new_low, new_high, new_an, low_max, high_max, an_max, targets_available
        )

        steps.append({
            "step": step_idx,
            "kind": chosen,
            "label": labels[chosen],
            "reason": reason,
            "source_date": src_date,
            "estimated_total_load": est_load,
            "expired_load": exp,
            "added_load": {"low_aerobic": add_low, "high_aerobic": add_high, "anaerobic": add_an},
            "before_pcts": {"low_aerobic": low_pct, "high_aerobic": high_pct, "anaerobic": an_pct},
            "after_pcts": {"low_aerobic": after_low_pct, "high_aerobic": after_high_pct, "anaerobic": after_an_pct},
        })

        low_act, high_act, an_act = new_low, new_high, new_an

    return {
        "n": n,
        "targets_available": targets_available,
        "overflow_threshold_pct": overflow_threshold,
        "profiles": profiles,
        "steps": steps,
        "sequence": [s["kind"] for s in steps],
    }


def compute_maintenance_runs_for_85(
    load_focus: Dict[str, Any],
    activities_all: List[Dict[str, Any]],
    base_run_target: int,
    ref_dt: Optional[datetime] = None,
    threshold: float = OVERFLOW_THRESHOLD_PCT,
) -> int:
    """
    compute_weekly_bar_drift ile birebir aynı hesabı kullanarak:
    Tüm 3 Firstbeat yük barı >= %85 ise ve Pazar sonuna kadar (28G düşüşleri dahil)
    ek koşu yapmadan >= %85 kalıyorsa 0 döner; aksi halde base_run_target döner.
    """
    if base_run_target <= 0 or not load_focus:
        return base_run_target
    drift = compute_weekly_bar_drift(load_focus, activities_all, ref_dt=ref_dt)
    if not drift.get("targets_available"):
        return base_run_target
    bars = (drift["low_aerobic"], drift["high_aerobic"], drift["anaerobic"])
    if min(b["current_pct"] for b in bars) >= threshold and min(b["week_end_pct"] for b in bars) >= threshold:
        return 0
    return base_run_target


def compute_weekly_bar_drift(
    load_focus: Dict[str, Any],
    activities_all: List[Dict[str, Any]],
    ref_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Haftanın kalan günlerinde (bugün -> Pazar) ve tüm hafta boyunca (Pzt -> Pazar)
    28 günlük pencereden düşecek yükler nedeniyle her bir barın yüzde kaç eksileceğini
    ve hafta sonunda kaça ineceğini hesaplar.
    """
    al = (load_focus or {}).get("aerobic_low") or {}
    ah = (load_focus or {}).get("aerobic_high") or {}
    an = (load_focus or {}).get("anaerobic") or {}

    low_act = float(al.get("actual") or 0.0)
    high_act = float(ah.get("actual") or 0.0)
    an_act = float(an.get("actual") or 0.0)
    low_max = float(al.get("target_max") or 0.0)
    high_max = float(ah.get("target_max") or 0.0)
    an_max = float(an.get("target_max") or 0.0)
    targets_available = bool((load_focus or {}).get("targets_available", True) and low_max > 0 and an_max > 0)

    cur_low_pct, cur_high_pct, cur_an_pct = _compute_bar_pcts(
        low_act, high_act, an_act, low_max, high_max, an_max, targets_available
    )

    now_dt = ref_dt or datetime.now()
    ref_day = now_dt.date()
    monday = ref_day - timedelta(days=ref_day.weekday())
    sunday = monday + timedelta(days=6)

    rem_win_start = ref_day - timedelta(days=28)
    rem_win_end = sunday - timedelta(days=27)  # inclusive of sunday - 28d
    wk_win_start = monday - timedelta(days=28)

    rem_exp = [0.0, 0.0, 0.0]
    wk_exp = [0.0, 0.0, 0.0]
    tot_28d = [0.0, 0.0, 0.0]
    for act in activities_all or []:
        d_str = (act.get("startTimeLocal") or "")[:10]
        if not d_str:
            continue
        try:
            d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if wk_win_start <= d_obj <= ref_day:
            c = estimate_activity_load_contribution(act)
            if rem_win_start <= d_obj <= ref_day:
                tot_28d[0] += c["low_aerobic"]
                tot_28d[1] += c["high_aerobic"]
                tot_28d[2] += c["anaerobic"]
            if rem_win_start <= d_obj < rem_win_end:
                rem_exp[0] += c["low_aerobic"]
                rem_exp[1] += c["high_aerobic"]
                rem_exp[2] += c["anaerobic"]
            if wk_win_start <= d_obj < rem_win_end:
                wk_exp[0] += c["low_aerobic"]
                wk_exp[1] += c["high_aerobic"]
                wk_exp[2] += c["anaerobic"]

    # Geçmiş 28G aktivite toplamı Garmin'in bildirdiği bar toplamıyla oranlanarak kesin düşüş hesaplanır
    act_totals = (low_act, high_act, an_act)
    for idx in range(3):
        if tot_28d[idx] > 0 and act_totals[idx] > 0:
            scale = act_totals[idx] / tot_28d[idx]
            rem_exp[idx] *= scale
            wk_exp[idx] *= scale

    end_low_pct, end_high_pct, end_an_pct = _compute_bar_pcts(
        max(0.0, low_act - rem_exp[0]),
        max(0.0, high_act - rem_exp[1]),
        max(0.0, an_act - rem_exp[2]),
        low_max, high_max, an_max, targets_available,
    )

    def _entry(cur_p: float, end_p: float, exp_load: float, wk_load: float) -> Dict[str, float]:
        drop_p = round(max(0.0, cur_p - end_p), 1)
        return {
            "current_pct": round(cur_p, 1),
            "week_end_pct": round(end_p, 1),
            "expiring_pct": drop_p,
            "expiring_load": round(exp_load, 1),
            "week_total_expiring_load": round(wk_load, 1),
        }

    return {
        "targets_available": targets_available,
        "low_aerobic": _entry(cur_low_pct, end_low_pct, rem_exp[0], wk_exp[0]),
        "high_aerobic": _entry(cur_high_pct, end_high_pct, rem_exp[1], wk_exp[1]),
        "anaerobic": _entry(cur_an_pct, end_an_pct, rem_exp[2], wk_exp[2]),
    }
