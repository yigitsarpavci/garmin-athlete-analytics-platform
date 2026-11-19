#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Esnek Haftalık Kota & Pazartesi Sıfırlama Adaptasyon Mixin'i.
Pazartesi-Pazar penceresinde 2 Koşu + 2 Kuvvet kotasını takip eder; Pazartesi temiz 0/2 açılır
ancak geçen haftadan eksik kalan seans türünü yeni haftada öncelik sırasına yerleştirir.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

try:
    from engine.helpers import request_cached, zone_text, TR_DAYS, TR_MONTHS, format_sport_tr, classify_sport_bucket, classify_run_workout
    from engine.run_load_predictor import predict_next_n_runs, compute_maintenance_runs_for_85
except ImportError:
    from app.engine.helpers import request_cached, zone_text, TR_DAYS, TR_MONTHS, format_sport_tr, classify_sport_bucket, classify_run_workout
    from app.engine.run_load_predictor import predict_next_n_runs, compute_maintenance_runs_for_85


_BASE_QUOTA_TEMPLATES: Dict[str, Dict[str, str]] = {
    "zone2": {
        "category": "running",
        "type": "Zone 2 Koşu",
        "short_label": "Zone 2 Koşu",
        "title_prefix": "Zone 2 Rahat Taban",
        "target_hr": "[[Z2_HR]]",
        "target_pace": "[[Z2_PACE]]",
        "duration": "45-50 dk",
        "badge": "Zone 2 Taban",
        "protocol_day_code": "thursday",
        "coaching_note": "[[Z2_HR]] nabız tavanını aşmadan, 160+ spm kadans ve burundan rahat nefesle haftanın uygun bir gününde uygula.",
    },
    "interval": {
        "category": "running",
        "type": "5K Hız İntervali",
        "short_label": "5K Hız İntervali",
        "title_prefix": "5K Hız İntervali (4x1.000m)",
        "target_hr": "[[INT_HR]]",
        "target_pace": "[[INT_PACE]]",
        "duration": "45 dk",
        "badge": "5K İnterval",
        "protocol_day_code": "monday",
        "coaching_note": "10 dk ısınma + 4x1.000m @ [[INT_PACE]] (aralarda 3 dk yürüyüş/jog) + 8 dk soğuma; bacakların taze olduğu bir günde uygula.",
    },
    "tempo": {
        "category": "running",
        "type": "Tempo Koşusu",
        "short_label": "Tempo Koşusu",
        "title_prefix": "Yüksek Aerobik Tempo (30-35 dk)",
        "target_hr": "[[Z3_HR]]",
        "target_pace": "[[TEMPO_PACE]]",
        "duration": "35 dk",
        "badge": "Yüksek Aerobik",
        "protocol_day_code": "monday",
        "coaching_note": "10 dk ısınma + 20 dk sabit eşik/tempo + 5 dk soğuma; Yüksek Aerobik barını doldurmak için uygula.",
    },
    "gym_a": {
        "category": "strength",
        "type": "Workout A",
        "short_label": "Workout A",
        "title_prefix": "Workout A (5x5)",
        "exercises_summary": "Squat (5x5) · Bench Press (5x5) · Barbell Row (5x5) · Lateral Raise (3x12) · Shrug (3x12)",
        "duration": "55 dk",
        "badge": "Workout A",
        "protocol_day_code": "tuesday",
        "coaching_note": "Aynı gün koşu yapılacaksa ÖNCE koşu, SONRA kuvvet kuralını koruyarak uygun bir günde uygula.",
    },
    "gym_b": {
        "category": "strength",
        "type": "Workout B",
        "short_label": "Workout B",
        "title_prefix": "Workout B (5x5)",
        "exercises_summary": "Squat (5x5) · OHP (5x5) · Deadlift (1x5) · Lat Pulldown (4x12) · Lateral Raise (3x12) · Shrug (3x12)",
        "duration": "55 dk",
        "badge": "Workout B",
        "protocol_day_code": "saturday",
        "coaching_note": "Arka zincir ve omuz gelişimi için bacakların toparlandığı uygun bir günde uygula.",
    },
}


_RUN_SHORT_LABELS: Dict[str, str] = {
    "interval": "İnterval",
    "zone2": "Zone 2",
    "tempo": "Tempo",
}


logger = logging.getLogger(__name__)


@dataclass
class _WeekState:
    """Haftalık plan hesabı sırasında biriken durum (tamamlanan seanslar, sapmalar, gün aktiviteleri). Parametre listelerini sadeleştirir."""

    planned_run_order: List[str]
    planned_gym_order: List[str]
    gym_type_by_date: Dict[str, str]
    run_target: int = 2
    gym_target: int = 2
    day_acts: List[List[Dict[str, Any]]] = field(default_factory=list)
    runs_done_list: List[Dict[str, Any]] = field(default_factory=list)
    gyms_done_list: List[Dict[str, Any]] = field(default_factory=list)
    runs_completed_items: List[Dict[str, Any]] = field(default_factory=list)
    gyms_completed_items: List[Dict[str, Any]] = field(default_factory=list)
    spontaneous_items: List[Dict[str, Any]] = field(default_factory=list)
    completed_run_kinds: List[str] = field(default_factory=list)
    completed_gym_kinds: List[str] = field(default_factory=list)
    run_cls_by_id: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    last_gym_type: Optional[str] = None


@dataclass
class _DayCtx:
    """Haftanın tek bir gününün bağlamı (sıra, tarih, etiket ve bugüne göre konumu)."""

    i: int
    d_str: str
    base_day: str
    is_today: bool
    is_past: bool
    is_tomorrow: bool
    is_completed: bool


class WeeklyQuotaMixin:
    """Pazartesi sıfırlamalı esnek haftalık kota, geçmiş hafta açığı adaptasyonu ve çizelge üretimi."""

    def _get_dynamic_gym_summaries(self) -> Dict[str, str]:
        """Son salon kayıtlarındaki progression hedeflerinden Workout A/B özetlerini üretir."""
        prog = {}
        if hasattr(self, "get_gym_exercise_history"):
            try:
                prog = (self.get_gym_exercise_history() or {}).get("progression", {})
            except Exception:
                logger.warning("_get_dynamic_gym_summaries: yedek davranış uygulandı", exc_info=True)
                prog = {}
        if not prog:
            return {
                "gym_a": _BASE_QUOTA_TEMPLATES["gym_a"]["exercises_summary"],
                "gym_b": _BASE_QUOTA_TEMPLATES["gym_b"]["exercises_summary"],
            }

        sq = prog.get("squat", {}).get("next_target", "--").split(" x ")[0]
        bp = prog.get("bench", {}).get("next_target", "--").split(" x ")[0]
        rw = prog.get("row", {}).get("next_target", "--").split(" x ")[0]
        ohp = prog.get("ohp", {}).get("next_target", "--").split(" x ")[0]
        dl = prog.get("deadlift", {}).get("next_target", "--").split(" x ")[0]
        lat = prog.get("lat_pulldown", {}).get("next_target", "--").split(" x ")[0]
        lr = prog.get("lateral_raise", {}).get("next_target", "--").split(" x ")[0]
        sh = prog.get("shrug", {}).get("next_target", "--").split(" x ")[0]

        return {
            "gym_a": f"Squat {sq} (5x5) · Bench {bp} (5x5) · Row {rw} (5x5) · Lateral {lr} (3x12) · Shrug {sh} (3x12)",
            "gym_b": f"Squat {sq} (5x5) · OHP {ohp} (5x5) · Deadlift {dl} (1x5) · Lat {lat} (4x12) · Lateral {lr} (3x12) · Shrug {sh} (3x12)",
        }

    def _build_quota_remaining_item(self, slot_kind: str, ordinal: int, prioritized_reason: Optional[str] = None) -> Dict[str, Any]:
        """Kalan koşu veya kuvvet kotası kalemini standart şemaya dönüştürür."""
        tpl = dict(_BASE_QUOTA_TEMPLATES[slot_kind])
        gym_summaries = self._get_dynamic_gym_summaries()
        prefix = "Koşu" if tpl["category"] == "running" else "Kuvvet"
        note = tpl["coaching_note"]
        if prioritized_reason:
            note = f"{prioritized_reason} {note}"

        item: Dict[str, Any] = {
            "category": tpl["category"],
            "slot_kind": slot_kind,
            "ordinal": ordinal,
            "type": tpl["type"],
            "short_label": tpl["short_label"],
            "title": f"{prefix} #{ordinal} · {tpl['title_prefix']}",
            "duration": tpl["duration"],
            "badge": tpl["badge"],
            "protocol_day_code": tpl["protocol_day_code"],
            "coaching_note": note,
            "is_prioritized": bool(prioritized_reason),
        }
        if tpl["category"] == "running":
            item["target_hr"] = tpl["target_hr"]
            item["target_pace"] = tpl["target_pace"]
        else:
            item["exercises_summary"] = gym_summaries.get(slot_kind, tpl["exercises_summary"])
        return item

    def compute_dynamic_weekly_targets(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Sporcu gelişmişlik seviyesi, aktif kuvvet split'i ve eksik Firstbeat yük barlarına göre
        haftalık kuvvet/koşu gün sayılarını ve 4-6 seanslık koşu projeksiyonunu hesaplar.
        """
        ref_dt = now or datetime.now()
        try:
            from engine.strength_progression import PROGRAM_SPLIT_CATALOG
        except ImportError:
            from app.engine.strength_progression import PROGRAM_SPLIT_CATALOG

        active_split = "5x5_linear"
        recommended_split = "5x5_linear"
        plateau_score = 0
        if hasattr(self, "get_gym_exercise_history"):
            try:
                gh = self.get_gym_exercise_history() or {}
                active_split = (gh.get("program_state") or {}).get("active_split", "5x5_linear")
                pa = gh.get("plateau_analysis") or {}
                recommended_split = pa.get("recommended_split", active_split)
                plateau_score = int(pa.get("plateau_score") or 0)
            except Exception:
                logger.warning("compute_dynamic_weekly_targets gym_history fallback", exc_info=True)

        chronic_load = 0.0
        vo2max = 0.0
        load_focus: Dict[str, Any] = {}
        if hasattr(self, "get_training_load_analytics"):
            try:
                tl = self.get_training_load_analytics() or {}
                cs = tl.get("current_status") or {}
                chronic_load = float(cs.get("chronic_load") or 0.0)
                vo2max = float(cs.get("vo2max") or 0.0)
                load_focus = tl.get("load_focus") or {}
            except Exception:
                logger.warning("compute_dynamic_weekly_targets load_analytics fallback", exc_info=True)

        # Son 28 günlük gerçek koşu / kuvvet sıklığı ve bu hafta (Pzt-Paz) tamamlanan koşular
        cutoff_date = (ref_dt - timedelta(days=28)).date()
        end_date = ref_dt.date()
        week_monday = end_date - timedelta(days=end_date.weekday())
        week_sunday = week_monday + timedelta(days=6)
        runs_28d = 0
        gyms_28d = 0
        runs_done_this_week = 0
        for act in getattr(self, "activities_all", []) or []:
            d_raw = (act.get("startTimeLocal") or "")[:10]
            if not d_raw:
                continue
            try:
                d_val = datetime.strptime(d_raw, "%Y-%m-%d").date()
            except ValueError:
                continue
            sp_key = act.get("sport") or (act.get("activityType") or {}).get("typeKey") or ""
            bucket = classify_sport_bucket(sp_key)
            if week_monday <= d_val <= min(end_date, week_sunday) and bucket == "running":
                runs_done_this_week += 1
            if not (cutoff_date <= d_val <= end_date):
                continue
            if bucket == "running":
                runs_28d += 1
            elif bucket == "strength":
                gyms_28d += 1

        runs_per_wk = runs_28d / 4.0
        gyms_per_wk = gyms_28d / 4.0

        # 1) Kuvvet kotası daima 2 günlük Workout A / Workout B (hesaplamaya girilmez)
        gym_target = 2
        gym_sequence = ["gym_a", "gym_b"]

        # 2) Koşu fitliğine göre temel gün sayısı (yalnızca 2 veya 3 gün; maks 3)
        if chronic_load >= 360 or (vo2max >= 50 and chronic_load >= 320):
            base_run_target = 3
        else:
            base_run_target = 2

        # Her koşu sonrası güncel fitlik ve load_focus değerlerine göre bu haftaki hedefi ayarla:
        # Tüm barlar >= %85 korunabiliyorsa kalan koşu sayısını eksilt; %85 altı varsa fitlik hedefini ver (ekstra ekleme).
        remaining_fitness_budget = max(0, base_run_target - runs_done_this_week)
        if remaining_fitness_budget > 0:
            needed_additional = compute_maintenance_runs_for_85(
                load_focus, getattr(self, "activities_all", []) or [], remaining_fitness_budget, ref_dt=ref_dt
            )
            run_target = runs_done_this_week + needed_additional
        else:
            run_target = base_run_target

        proj_n = max(4, min(6, max(2, run_target) + 2))
        run_prediction = None
        if load_focus or getattr(self, "activities_all", None):
            try:
                run_prediction = predict_next_n_runs(load_focus, self.activities_all, n=proj_n, ref_dt=ref_dt)
            except Exception:
                logger.warning("compute_dynamic_weekly_targets predict_next_n_runs fallback", exc_info=True)

        pred_seq = list((run_prediction or {}).get("sequence") or [])
        fallback_runs = ["interval", "zone2"] * 3
        run_sequence = pred_seq[:run_target] if run_target > 0 else []
        while len(run_sequence) < run_target:
            run_sequence.append(fallback_runs[len(run_sequence)])

        if run_target == 0:
            run_plan_summary = "Bu hafta 0 Koşu (Tüm yük barları %85+ korunuyor)"
        else:
            suffix = " (%85+ koruma)" if run_target < base_run_target else ""
            run_plan_summary = f"Bu hafta {run_target} Koşu · En eksiği Quick Workout'tan yap{suffix}"

        # Kuvvet program özeti (her zaman 2 günlük A/B)
        split_meta = PROGRAM_SPLIT_CATALOG.get("5x5_linear", {})
        split_short = split_meta.get("short_name", "5x5 Doğrusal (A/B)")
        gym_plan_summary = f"Bu hafta 2 Kuvvet (1x A + 1x B) · {split_short}"

        rec_meta = PROGRAM_SPLIT_CATALOG.get(recommended_split, split_meta)
        athlete_level = (
            "Orta" if (run_target >= 3 or plateau_score >= 45)
            else "Temel / Gelişim"
        )

        return {
            "athlete_level": athlete_level,
            "run_target": run_target,
            "gym_target": gym_target,
            "total_target": run_target + gym_target,
            "run_sequence": run_sequence,
            "gym_sequence": gym_sequence,
            "projection_horizon": proj_n,
            "run_prediction": run_prediction,
            "run_plan_summary": run_plan_summary,
            "gym_plan_summary": gym_plan_summary,
            "active_split": "5x5_linear",
            "active_split_name": split_short,
            "recommended_split": recommended_split,
            "recommended_split_name": rec_meta.get("short_name", recommended_split),
            "plateau_score": plateau_score,
            "runs_28d_per_wk": round(runs_per_wk, 2),
            "gyms_28d_per_wk": round(gyms_per_wk, 2),
        }

    def _analyze_previous_week_carryover(
        self,
        monday_anchor: datetime,
        gym_type_by_date: Dict[str, str],
        dyn: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Geçen Pzt-Paz haftasındaki eksik seansları analiz eder.
        Pazartesi kotası daima temiz 0/N açılır (borç eklenmez), ancak geçen hafta eksik kalan
        seans türü yeni haftanın ilk sırasına önceliklendirilir.
        """
        dyn = dyn or self.compute_dynamic_weekly_targets(now=monday_anchor)
        run_target = dyn["run_target"]
        gym_target = dyn["gym_target"]
        prev_mon = monday_anchor - timedelta(days=7)
        prev_sun = monday_anchor - timedelta(days=1)
        prev_range = f"{prev_mon.day} {TR_MONTHS[prev_mon.month - 1]} – {prev_sun.day} {TR_MONTHS[prev_sun.month - 1]}"
        prev_dates = {(prev_mon + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}

        prev_runs: List[Dict[str, Any]] = []
        prev_gyms: List[Dict[str, Any]] = []
        for act in self.activities_all:
            d_str = (act.get("startTimeLocal") or "")[:10]
            if d_str not in prev_dates:
                continue
            sp_key = act.get("sport") or (act.get("activityType") or {}).get("typeKey") or ""
            bucket = classify_sport_bucket(sp_key)
            if bucket == "running":
                prev_runs.append(act)
            elif bucket == "strength":
                prev_gyms.append(act)

        prev_runs_sorted = sorted(prev_runs, key=lambda x: x.get("startTimeLocal") or "")
        prev_gyms_sorted = sorted(prev_gyms, key=lambda x: x.get("startTimeLocal") or "")

        prev_run_kinds = [classify_run_workout(r)["kind"] for r in prev_runs_sorted]
        prev_had_interval = "interval" in prev_run_kinds
        prev_had_zone2 = "zone2" in prev_run_kinds

        prev_gym_types = [gym_type_by_date.get((g.get("startTimeLocal") or "")[:10], "Kuvvet") for g in prev_gyms_sorted]
        prev_had_a = any("Workout A" in wt for wt in prev_gym_types)
        prev_had_b = any("Workout B" in wt for wt in prev_gym_types)

        # Pazartesi öncesi en son yapılan kuvvet antrenmanını bul (geçen hafta veya daha önceki haftalar)
        monday_str = monday_anchor.strftime("%Y-%m-%d")
        last_prior_gym_type = None
        for wt in reversed(prev_gym_types):
            if "Workout A" in wt or "Workout B" in wt:
                last_prior_gym_type = wt
                break
        if last_prior_gym_type is None:
            prior_gyms = []
            for act in self.activities_all:
                d_str = (act.get("startTimeLocal") or "")[:10]
                if not d_str or d_str >= monday_str:
                    continue
                sp_key = act.get("sport") or (act.get("activityType") or {}).get("typeKey") or ""
                if classify_sport_bucket(sp_key) == "strength":
                    wt = gym_type_by_date.get(d_str, "")
                    if "Workout A" in wt or "Workout B" in wt:
                        prior_gyms.append((d_str, wt))
            if prior_gyms:
                prior_gyms.sort(key=lambda x: x[0])
                last_prior_gym_type = prior_gyms[-1][1]

        missed_sessions: List[str] = []
        run_order = list(dyn["run_sequence"])
        gym_order = ["gym_b", "gym_a"] if (last_prior_gym_type and "Workout A" in last_prior_gym_type) else ["gym_a", "gym_b"]
        run_priority_reason: Optional[str] = None
        gym_priority_reason: Optional[str] = None

        if len(prev_runs_sorted) < run_target and run_target > 0:
            if len(prev_runs_sorted) == 0 and any(True for _ in prev_gyms_sorted):
                missed_sessions.extend(["Zone 2 Koşu", "5K Hız İntervali"])
            elif len(prev_runs_sorted) == 1:
                if prev_had_zone2 and not prev_had_interval:
                    missed_sessions.append("5K Hız İntervali")
                elif prev_had_interval and not prev_had_zone2:
                    missed_sessions.append("Zone 2 Koşu")
                else:
                    missed_sessions.append("2. Koşu seansı")

        if len(prev_gyms_sorted) == 1:
            if prev_had_a and not prev_had_b:
                missed_sessions.append("Workout B")
                gym_priority_reason = "Geçen hafta yalnızca Workout A yapıldığı için bu hafta Workout B → Workout A sırasıyla devam edilir."
            elif prev_had_b and not prev_had_a:
                missed_sessions.append("Workout A")
                gym_priority_reason = "Geçen hafta yalnızca Workout B yapıldığı için bu hafta Workout A → Workout B sırasıyla devam edilir."
            else:
                missed_sessions.append("2. Kuvvet seansı")
        elif len(prev_gyms_sorted) == 0 and any(True for _ in prev_runs_sorted):
            missed_sessions.extend(["Workout A", "Workout B"])

        if gym_priority_reason is None and gym_order[0] == "gym_b":
            gym_priority_reason = "En son Workout A yapıldığı için bu hafta Workout B → Workout A sırasıyla devam edilir."

        # Sıradaki 4-6 koşuyu son gerçek koşuların EPOC/TE katkılarıyla kapalı çevrim simüle et
        run_prediction = dyn.get("run_prediction")
        if run_prediction and not run_priority_reason and len(run_prediction.get("steps", [])) >= 1:
            s1 = run_prediction["steps"][0]
            run_priority_reason = s1["reason"]

        has_prev_data = bool(prev_runs_sorted or prev_gyms_sorted)
        if not has_prev_data:
            adaptation_note = f"Geçen hafta bazlı ek kısıt saptanmadı — bu hafta temiz {run_target} Koşu + {gym_target} Kuvvet kotasıyla başlar."
        elif missed_sessions:
            adaptation_note = (
                f"Pazartesi 0/{run_target} kotası borçsuz sıfırlandı ({prev_range}: {len(prev_runs_sorted)}/{run_target} Koşu, {len(prev_gyms_sorted)}/{gym_target} Kuvvet). "
                f"Geçen hafta eksik kalan {', '.join(missed_sessions)} bu haftanın öncelik sırasına yerleştirildi."
            )
        else:
            adaptation_note = (
                f"Geçen hafta ({prev_range}) {run_target} Koşu + {gym_target} Kuvvet tam tamamlandı; bu hafta dengeli rota ile devam ediyor."
            )

        return {
            "prev_week_range": prev_range,
            "has_previous_week_data": has_prev_data,
            "prev_runs_done": len(prev_runs_sorted),
            "prev_gyms_done": len(prev_gyms_sorted),
            "missed_sessions": missed_sessions,
            "run_order": run_order,
            "gym_order": gym_order,
            "run_priority_reason": run_priority_reason,
            "gym_priority_reason": gym_priority_reason,
            "adaptation_note": adaptation_note,
            "next_4_runs_prediction": run_prediction,
        }

    @request_cached
    def _build_weekly_schedule_entries(self, now: Optional[datetime] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Takvim haftası (Pzt–Paz) içinde tamamlanan Garmin aktivitelerini haftalık
        2 Koşu + 2 Kuvvet kotasından otomatik düşer; kalan seansları geçmiş hafta
        önceliğine ve toparlanmaya göre esnek pencerelere yerleştirir.
        """
        now = now or datetime.now()
        monday_anchor = now - timedelta(days=now.weekday())
        sunday_anchor = monday_anchor + timedelta(days=6)
        week_dates = [monday_anchor + timedelta(days=i) for i in range(7)]
        week_range = (
            f"{monday_anchor.day} {TR_MONTHS[monday_anchor.month - 1]} – "
            f"{sunday_anchor.day} {TR_MONTHS[sunday_anchor.month - 1]}"
        )

        gym_history = self.get_gym_exercise_history().get("sessions", []) if hasattr(self, "get_gym_exercise_history") else []
        gym_type_by_date = {
            s.get("date"): s.get("workout_type")
            for s in gym_history
            if s.get("date")
        }

        dyn = self.compute_dynamic_weekly_targets(now=now)
        run_target = dyn["run_target"]
        gym_target = dyn["gym_target"]
        carryover = self._analyze_previous_week_carryover(monday_anchor, gym_type_by_date, dyn=dyn)
        gym_summaries = self._get_dynamic_gym_summaries()
        st = _WeekState(
            planned_run_order=list(carryover["run_order"]),
            planned_gym_order=list(carryover["gym_order"]),
            gym_type_by_date=gym_type_by_date,
            run_target=run_target,
            gym_target=gym_target,
        )

        for d_date in week_dates:
            d_str = d_date.strftime("%Y-%m-%d")
            day_short = f"{d_date.day} {TR_MONTHS[d_date.month - 1]} {TR_DAYS[d_date.weekday()]}"
            matched = [a for a in self.activities_all if (a.get("startTimeLocal") or "")[:10] == d_str]
            st.day_acts.append(matched)
            for act in matched:
                sport_key = (act.get("sport") or (act.get("activityType") or {}).get("typeKey") or "").lower()
                act_name = act.get("activityName") or "Antrenman"
                dur_m = round((act.get("duration") or 0) / 60.0)
                cal = round(act.get("calories") or 0)
                avg_hr = round(act.get("averageHR") or 0)
                dist_m = act.get("distance") or 0
                hr_txt = f" · {avg_hr} bpm" if avg_hr else ""
                bucket = classify_sport_bucket(sport_key)

                if bucket == "running":
                    self._record_run_activity(st, act, act_name, avg_hr, cal, d_str, day_short, dist_m, dur_m, hr_txt)
                elif bucket == "strength":
                    st.last_gym_type = self._record_strength_activity(st, act, avg_hr, cal, d_str, day_short, dur_m, hr_txt)
                else:
                    self._record_spontaneous_activity(st, act_name, avg_hr, cal, d_str, day_short, dur_m, hr_txt, sport_key)

        runs_done = len(st.runs_done_list)
        gyms_done = len(st.gyms_done_list)
        rem_runs = max(0, run_target - runs_done)
        rem_gyms = max(0, gym_target - gyms_done)
        adapted_recovery_day_idx, assigned_slot, needed_gyms, needed_runs, post_tempo_adapted = self._plan_open_slots(st, carryover, gyms_done, now, rem_gyms, rem_runs, runs_done, week_dates)

        _format_completed_day = self._make_completed_day_formatter(st)

        _build_planned_slot = self._make_planned_slot_builder(st, carryover, gym_summaries, gyms_done, post_tempo_adapted, rem_gyms, rem_runs, runs_done)

        schedule: List[Dict[str, Any]] = []
        meta_days: List[Dict[str, Any]] = []
        run_counter = [0]
        gym_counter = [0]
        total_done = runs_done + gyms_done
        total_rem = rem_runs + rem_gyms

        for i, d_date in enumerate(week_dates):
            d_str = d_date.strftime("%Y-%m-%d")
            d_name = TR_DAYS[d_date.weekday()]
            m_name = TR_MONTHS[d_date.month - 1]
            is_today = (d_str == now.strftime("%Y-%m-%d"))
            is_past = (d_date.date() < now.date())
            is_tomorrow = (d_date.date() == (now + timedelta(days=1)).date())
            base_day = f"{d_date.day} {m_name} {d_name}"

            slot_kind = "completed"
            is_completed = bool(st.day_acts[i])
            day = _DayCtx(i, d_str, base_day, is_today, is_past, is_tomorrow, is_completed)
            day_label, row_data, slot_kind = self._resolve_day_row(
                st, day, _build_planned_slot, _format_completed_day, adapted_recovery_day_idx, assigned_slot,
                gym_counter, run_counter, slot_kind, total_done, total_rem, week_dates,
            )

            entry: Dict[str, Any] = {
                "day": day_label,
                "slot_kind": slot_kind,
                "is_completed": is_completed,
                "is_flexible": not is_completed,
                **row_data,
            }
            schedule.append(entry)
            meta_days.append({
                "date": d_date,
                "date_str": d_str,
                "day_label": day_label,
                "slot_kind": slot_kind,
                "is_completed": is_completed,
                "is_past": is_past,
                **row_data,
            })

        return schedule, {
            "week_range": week_range,
            "run_target": run_target,
            "gym_target": gym_target,
            "dynamic_targets": dyn,
            "runs_done": runs_done,
            "gyms_done": gyms_done,
            "rem_runs": rem_runs,
            "rem_gyms": rem_gyms,
            "needed_runs": needed_runs,
            "needed_gyms": needed_gyms,
            "completed_run_kinds": st.completed_run_kinds,
            "completed_gym_kinds": st.completed_gym_kinds,
            "post_tempo_adapted": post_tempo_adapted,
            "adapted_recovery_day_idx": adapted_recovery_day_idx,
            "runs_completed_items": st.runs_completed_items,
            "gyms_completed_items": st.gyms_completed_items,
            "spontaneous_items": st.spontaneous_items,
            "carryover": carryover,
            "days": meta_days,
        }

    def _plan_open_slots(self, st, carryover, gyms_done, now, rem_gyms, rem_runs, runs_done, week_dates):
        """Kalan koşu/kuvvet seanslarını (öncelik sırası, art arda yük ve toparlanma kurallarıyla) haftanın açık günlerine atar."""
        post_tempo_adapted = False

        needed_runs: List[Tuple[str, int]] = []
        if rem_runs >= 1:
            if runs_done == 0:
                needed_runs = [
                    (st.planned_run_order[idx], idx + 1)
                    for idx in range(min(rem_runs, len(st.planned_run_order)))
                ]
            elif rem_runs == 1 and st.run_target <= 2:
                if "tempo" in st.completed_run_kinds:
                    post_tempo_adapted = True
                    next_kind = st.planned_run_order[0] if st.planned_run_order[0] in ("zone2", "interval", "tempo") else "interval"
                    needed_runs = [(next_kind, runs_done + 1)]
                elif len(st.planned_run_order) >= 2 and st.planned_run_order[0] == st.planned_run_order[1]:
                    needed_runs = [(st.planned_run_order[1], runs_done + 1)]
                elif "interval" in st.completed_run_kinds and "zone2" not in st.completed_run_kinds:
                    needed_runs = [("zone2", runs_done + 1)]
                elif "zone2" in st.completed_run_kinds and "interval" not in st.completed_run_kinds:
                    needed_runs = [("interval", runs_done + 1)]
                else:
                    post_tempo_adapted = True
                    next_kind = st.planned_run_order[0] if st.planned_run_order[0] in ("zone2", "interval", "tempo") else "zone2"
                    needed_runs = [(next_kind, runs_done + 1)]
            else:
                pool = list(st.planned_run_order)
                for ck in st.completed_run_kinds:
                    if ck in pool:
                        pool.remove(ck)
                    elif ck == "tempo":
                        post_tempo_adapted = True
                        if "zone2" in pool:
                            pool.remove("zone2")
                        elif pool:
                            pool.pop(0)
                    elif pool:
                        pool.pop(0)
                while len(pool) < rem_runs:
                    pool.append(st.planned_run_order[len(pool) % len(st.planned_run_order)])
                needed_runs = [(pool[idx], runs_done + idx + 1) for idx in range(rem_runs)]

        needed_gyms: List[Tuple[str, int]] = []
        if rem_gyms >= 1:
            if gyms_done == 0:
                needed_gyms = [
                    (st.planned_gym_order[idx], idx + 1)
                    for idx in range(min(rem_gyms, len(st.planned_gym_order)))
                ]
            elif rem_gyms == 1 and st.gym_target <= 2:
                if "gym_a" in st.completed_gym_kinds and "gym_b" not in st.completed_gym_kinds:
                    next_gym = "gym_b"
                elif "gym_b" in st.completed_gym_kinds and "gym_a" not in st.completed_gym_kinds:
                    next_gym = "gym_a"
                else:
                    next_gym = "gym_a" if st.last_gym_type and "Workout B" in st.last_gym_type else "gym_b"
                needed_gyms = [(next_gym, gyms_done + 1)]
            else:
                g_pool = list(st.planned_gym_order)
                for gk in st.completed_gym_kinds:
                    if gk in g_pool:
                        g_pool.remove(gk)
                    elif g_pool:
                        g_pool.pop(0)
                while len(g_pool) < rem_gyms:
                    g_pool.append(st.planned_gym_order[len(g_pool) % len(st.planned_gym_order)])
                needed_gyms = [(g_pool[idx], gyms_done + idx + 1) for idx in range(rem_gyms)]

        needed_queue: List[Tuple[str, int]] = []
        for idx in range(max(len(needed_runs), len(needed_gyms))):
            if idx < len(needed_runs):
                needed_queue.append(needed_runs[idx])
            if idx < len(needed_gyms):
                needed_queue.append(needed_gyms[idx])

        open_offsets = [i for i in range(7) if not st.day_acts[i] and week_dates[i].date() >= now.date()]
        completed_day_indices = {i for i in range(7) if st.day_acts[i]}
        adapted_recovery_day_idx: Optional[int] = None
        for i in open_offsets:
            if (i - 1) in completed_day_indices and (i - 2) in completed_day_indices:
                later_open = [j for j in open_offsets if j > i]
                if len(later_open) >= len(needed_queue):
                    adapted_recovery_day_idx = i
                    break

        assignable_open = [i for i in open_offsets if i != adapted_recovery_day_idx]
        assigned_slot: Dict[int, Tuple[str, int]] = {}

        if rem_runs == 2 and rem_gyms == 2 and not carryover["missed_sessions"] and {1, 2, 4, 5}.issubset(assignable_open):
            assigned_slot = {
                1: needed_gyms[0],
                2: needed_runs[0],
                4: needed_runs[1],
                5: needed_gyms[1],
            }
        elif needed_queue:
            # Sadece gerçek antrenman yapılan/atanan günleri çakışma kontrolüne ekle (dinlenme günü ertesi güne engel olmamalı)
            occupied = set(completed_day_indices)
            remaining = list(needed_queue)
            for i in assignable_open:
                if not remaining:
                    break
                if (i - 1) not in occupied and (i + 1) not in occupied:
                    assigned_slot[i] = remaining.pop(0)
                    occupied.add(i)
            for i in assignable_open:
                if not remaining:
                    break
                if i not in assigned_slot and (i - 1) not in occupied:
                    assigned_slot[i] = remaining.pop(0)
                    occupied.add(i)
            for i in assignable_open:
                if not remaining:
                    break
                if i not in assigned_slot:
                    assigned_slot[i] = remaining.pop(0)
        return adapted_recovery_day_idx, assigned_slot, needed_gyms, needed_runs, post_tempo_adapted


    def _make_completed_day_formatter(self, st):
        """Tamamlanmış günün özet satırını üreten fonksiyonu döner (sapma ve sınıflandırma verisi yakalanır)."""
        def _format_completed_day(matched: List[Dict[str, Any]], d_str: str, run_c: List[int], gym_c: List[int]) -> Dict[str, Any]:
            titles, details, hr_notes = [], [], []
            has_run = False
            for act in matched:
                sport_key = (act.get("sport") or (act.get("activityType") or {}).get("typeKey") or "").lower()
                act_name = act.get("activityName") or "Antrenman"
                act_time = (act.get("startTimeLocal") or "")[11:16]
                dur_m = round((act.get("duration") or 0) / 60.0)
                cal = round(act.get("calories") or 0)
                avg_hr = round(act.get("averageHR") or 0)
                dist_m = act.get("distance") or 0
                bucket = classify_sport_bucket(sport_key)
                if bucket == "running":
                    has_run = True
                    run_c[0] += 1
                    r_cls = st.run_cls_by_id.get(id(act)) or classify_run_workout(act)
                    dist_txt = f" ({dist_m / 1000.0:.2f} km)" if dist_m > 0 else ""
                    titles.append(f"Koşu #{run_c[0]} • {r_cls['label_tr']} — {act_name}{dist_txt}")
                    te_txt = f" • TE: {r_cls['te_label']}, AnTE: {r_cls['an_te']}"
                    if r_cls.get("kind") == "tempo":
                        exp_lbl = r_cls.get("expected_label", "5K Hız İntervali")
                        details.append(
                            f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm{te_txt}) — "
                            f"{r_cls['label_tr']} haftalık koşu kotasına sayıldı (kota 1 düşüldü); {exp_lbl} kalan koşu kotasında korundu"
                        )
                    elif r_cls.get("is_deviation"):
                        exp_lbl = r_cls.get("expected_label", "Diğer Tür")
                        details.append(
                            f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm{te_txt}) — "
                            f"{r_cls['label_tr']} haftalık koşu kotasına sayıldı; {exp_lbl} kalan kotada korundu"
                        )
                    else:
                        details.append(f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm{te_txt})")
                elif bucket == "strength":
                    gym_c[0] += 1
                    w_type = st.gym_type_by_date.get(d_str) or "Kuvvet"
                    titles.append(f"Kuvvet #{gym_c[0]} • {w_type} (5x5)")
                    details.append(f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm)")
                else:
                    sport_tr = format_sport_tr(sport_key, act_name)
                    titles.append(f"{sport_tr} (Spontane) • {act_name}")
                    details.append(f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm)")
                if avg_hr:
                    hr_notes.append(f"{avg_hr} bpm ort.")
            nut = self.nutrition_texts("run" if has_run else "gym")
            est_cal = nut["calories"]
            macro_txt = nut["macro"]
            return {
                "primary": " + ".join(titles),
                "secondary": " • ".join(details),
                "target": "Gerçekleşen: " + (", ".join(hr_notes) if hr_notes else "Kaydedildi"),
                "calories": est_cal,
                "macro": macro_txt,
            }
        return _format_completed_day


    def _make_planned_slot_builder(self, st, carryover, gym_summaries, gyms_done, post_tempo_adapted, rem_gyms, rem_runs, runs_done):
        """Kalan kota seansları için planlanan slot satırı üreten fonksiyonu döner (kota durumu yakalanır)."""
        def _build_planned_slot(slot_kind: str, ordinal: int) -> Dict[str, str]:
            is_last_run = (rem_runs == 1 and runs_done == st.run_target - 1)
            is_last_gym = (rem_gyms == 1 and gyms_done == st.gym_target - 1)
            prio_hint = ""
            if slot_kind in ("zone2", "interval") and post_tempo_adapted:
                prio_hint = " (Tempo Sonrası Güncel Telafi)"
            elif slot_kind == st.planned_run_order[0] and carryover["run_priority_reason"] and ordinal == 1:
                prio_hint = " (Öncelikli)"
            elif slot_kind == st.planned_gym_order[0] and carryover["gym_priority_reason"] and ordinal == 1:
                prio_hint = " (Öncelikli)"

            if slot_kind in ("gym_a", "gym_b", "gym_c"):
                quota_lbl = f"{st.gym_target}/{st.gym_target} Son Salon Kotası" if is_last_gym else f"{rem_gyms} Kalan Kuvvet Kotası"
                summary = gym_summaries.get(slot_kind, _BASE_QUOTA_TEMPLATES[slot_kind]["exercises_summary"])
                return {
                    "primary": f"Kuvvet #{ordinal} · Kalan Kota{prio_hint} · {summary.split(' · Lateral')[0]}",
                    "secondary": f"Esnek Gün — Bu hafta geriye {rem_gyms} kuvvet kaldı ({quota_lbl}), istediğin uygun gün uygula • {summary}",
                    "target": "115-128 bpm (Zone 1)" if slot_kind == "gym_a" else "115-130 bpm (Zone 1)",
                    **{k: v for k, v in self.nutrition_texts("gym").items() if k in ("calories", "macro")},
                }
            if slot_kind == "tempo":
                quota_lbl = f"{st.run_target}/{st.run_target} Son Koşu Kotası" if is_last_run else f"{rem_runs} Kalan Koşu Kotası"
                return {
                    "primary": f"Koşu #{ordinal} · Kalan Kota{prio_hint} · Yüksek Aerobik Tempo (30-35 dk)",
                    "secondary": f"Esnek Gün — Bu hafta geriye {rem_runs} koşu kaldı ({quota_lbl}), Yüksek Aerobik barını doldurmak için uygula • 10 dk ısınma + 20 dk tempo",
                    "target": "Zone 3-4 Eşik/Tempo",
                    **{k: v for k, v in self.nutrition_texts("tempo").items() if k in ("calories", "macro")},
                }
            if slot_kind == "zone2":
                quota_lbl = f"{st.run_target}/{st.run_target} Son Koşu Kotası" if is_last_run else f"{rem_runs} Kalan Koşu Kotası"
                return {
                    "primary": f"Koşu #{ordinal} · Kalan Kota{prio_hint} · Zone 2 Rahat Taban (45-50 dk)",
                    "secondary": f"Esnek Gün — Bu hafta geriye {rem_runs} koşu kaldı ({quota_lbl}), toparlanmana uygun günde uygula • 160+ kadans, burundan nefes",
                    "target": "[[Z2_HR]] ([[Z2_PACE]])",
                    **{k: v for k, v in self.nutrition_texts("run").items() if k in ("calories", "macro")},
                }
            quota_lbl = f"{st.run_target}/{st.run_target} Son Koşu Kotası" if is_last_run else f"{rem_runs} Kalan Koşu Kotası"
            extra_tempo_note = (
                " · Planlanan İnterval yerine Tempo koşulduğu için Anaerobik (AnTE) hâlâ eksik"
                if post_tempo_adapted else ""
            )
            return {
                "primary": f"Koşu #{ordinal} · Kalan Kota{prio_hint} · 5K Hız İntervali (45 dk, 4x1.000m)",
                "secondary": f"Esnek Gün — Bu hafta geriye {rem_runs} koşu kaldı ({quota_lbl}), taze bacaklarla uygun günde uygula{extra_tempo_note} • [[INT_PACE]] tempo, 3 dk jog",
                "target": "[[Z45_HR]] (Zone 4-5)",
                **{k: v for k, v in self.nutrition_texts("interval").items() if k in ("calories", "macro")},
            }
        return _build_planned_slot


    def _resolve_day_row(self, st, day, _build_planned_slot, _format_completed_day, adapted_recovery_day_idx, assigned_slot, gym_counter, run_counter, slot_kind, total_done, total_rem, week_dates):
        """Günün satırını belirler: tamamlanmış gün, atanmış kalan seans, uyarlanmış toparlanma, esnek kapanış veya dinlenme."""
        if day.is_completed:
            day_label = f"{day.base_day} (Bugün)" if day.is_today else day.base_day
            row_data = _format_completed_day(st.day_acts[day.i], day.d_str, run_counter, gym_counter)
        elif day.i in assigned_slot:
            slot_kind, ordinal = assigned_slot[day.i]
            if day.is_today:
                day_label = f"{day.base_day} (Bugün · Güncel Plan)"
            elif day.is_tomorrow:
                day_label = f"{day.base_day} (Yarın · Güncel Öneri)"
            else:
                day_label = f"{day.base_day} (Güncel Önerilen Pencere)"
            row_data = _build_planned_slot(slot_kind, ordinal)
        elif day.i == adapted_recovery_day_idx:
            slot_kind = "rest"
            day_label = f"{day.base_day} ({'Bugün · ' if day.is_today else ''}Uyarlanmış Toparlanma)"
            prev1_lbl = f"{week_dates[day.i - 1].day} {TR_MONTHS[week_dates[day.i - 1].month - 1]} {TR_DAYS[week_dates[day.i - 1].weekday()]}"
            prev2_lbl = f"{week_dates[day.i - 2].day} {TR_MONTHS[week_dates[day.i - 2].month - 1]} {TR_DAYS[week_dates[day.i - 2].weekday()]}"
            row_data = {
                "primary": "Uyarlanmış Toparlanma / Rejenerasyon Penceresi",
                "secondary": (
                    f"{prev2_lbl} + {prev1_lbl} üst üste yüklendiği için bugün toparlanma günü olarak ayrıldı; "
                    f"kalan {total_rem} seans dinlenmiş günlere kaydırıldı"
                ),
                "target": "<105 bpm (Aktif Dinlenme)",
                **{k: v for k, v in self.nutrition_texts("rest").items() if k in ("calories", "macro")},
            }
        elif day.i == 6:
            slot_kind = "active_recovery"
            day_label = f"{day.base_day} (Esnek Kapanış)" if not day.is_today else f"{day.base_day} (Bugün · Esnek Kapanış)"
            quota_note = (
                "Haftalık 4/4 antrenman kotası tamamlandı"
                if total_rem == 0
                else f"Bu hafta {total_done}/4 seans tamamlandı, geriye {total_rem} esnek seans kaldı"
            )
            row_data = {
                "primary": "Aktif Toparlanma / Mobilite & Esnek Yürüyüş",
                "secondary": f"Esnek Gün — Hafif yürüyüş, esneme, nefes (NSDR) • {quota_note}",
                "target": "<110 bpm (Zone 1)",
                **{k: v for k, v in self.nutrition_texts("rest").items() if k in ("calories", "macro")},
            }
        else:
            slot_kind = "rest"
            if day.is_past:
                day_label = f"{day.base_day} (Geçti · Dinlenme)"
                sec_txt = "Geçmiş Dinlenme / Ekstra Kayıt Yok"
            else:
                prefix = "Bugün · " if day.is_today else ("Yarın · " if day.is_tomorrow else "")
                day_label = f"{day.base_day} ({prefix}Esnek Dinlenme)"
                sec_txt = (
                    f"Esnek Gün — Bu hafta {total_done}/4 seans tamamlandı, geriye {total_rem} seans kaldı; kalan kotayı dilediğin uygun güne taşıyabilirsin"
                    if total_rem > 0
                    else "Haftalık 4/4 antrenman kotası tamamlandı — kas onarımı & 00:30 öncesi uyku"
                )
            row_data = {
                "primary": "Esnek Toparlanma / Rejenerasyon Penceresi",
                "secondary": sec_txt,
                "target": "<100 bpm (Parasempatik gün)",
                **{k: v for k, v in self.nutrition_texts("rest").items() if k in ("calories", "macro")},
            }
        return day_label, row_data, slot_kind


    def _record_run_activity(self, st, act, act_name, avg_hr, cal, d_str, day_short, dist_m, dur_m, hr_txt):
        """Koşu aktivitesini sınıflandırır (interval / Zone 2 / tempo) ve haftalık kotaya sayar."""
        st.runs_done_list.append(act)
        r_cls = classify_run_workout(act)
        actual_kind = r_cls["kind"]
        st.completed_run_kinds.append(actual_kind)
        st.run_cls_by_id[id(act)] = r_cls

        dist_km = round(dist_m / 1000.0, 2) if dist_m > 0 else 0.0
        st.runs_completed_items.append({
            "date": d_str,
            "day_label": day_short,
            "title": act_name,
            "workout_type": r_cls["label_tr"],
            "actual_kind": actual_kind,
            "te_label": r_cls["te_label"],
            "an_te": r_cls["an_te"],
            "distance_km": dist_km,
            "duration_min": dur_m,
            "avg_hr": avg_hr,
            "calories": cal,
            "label": day_short,
        })


    def _record_strength_activity(self, st, act, avg_hr, cal, d_str, day_short, dur_m, hr_txt):
        """Kuvvet aktivitesini haftalık kotaya sayar ve Workout A/B türünü belirler."""
        idx_g = len(st.gyms_done_list)
        st.gyms_done_list.append(act)
        w_type = st.gym_type_by_date.get(d_str) or "Kuvvet"
        st.last_gym_type = w_type if w_type != "Kuvvet" else st.last_gym_type
        g_kind = "gym_a" if "Workout A" in w_type else ("gym_b" if "Workout B" in w_type else st.planned_gym_order[min(idx_g, len(st.planned_gym_order) - 1)])
        st.completed_gym_kinds.append(g_kind)
        st.gyms_completed_items.append({
            "date": d_str,
            "day_label": day_short,
            "workout_type": w_type,
            "actual_kind": g_kind,
            "title": f"Kuvvet #{len(st.gyms_done_list)} · {w_type} (5x5)",
            "duration_min": dur_m,
            "avg_hr": avg_hr,
            "calories": cal,
            "label": f"{day_short} · {w_type} ({dur_m} dk{hr_txt})",
        })
        return st.last_gym_type


    def _record_spontaneous_activity(self, st, act_name, avg_hr, cal, d_str, day_short, dur_m, hr_txt, sport_key):
        """Preset dışı (spontane) bir aktiviteyi haftalık spontane listeye ekler."""
        sport_tr = format_sport_tr(sport_key, act_name)
        st.spontaneous_items.append({
            "date": d_str,
            "day_label": day_short,
            "sport": sport_key or "other",
            "sport_tr": sport_tr,
            "title": act_name,
            "duration_min": dur_m,
            "avg_hr": avg_hr,
            "calories": cal,
            "label": f"{day_short} · {sport_tr}: {act_name} ({dur_m} dk{hr_txt})",
        })


    @zone_text
    def get_weekly_schedule(self) -> List[Dict[str, Any]]:
        """Pazartesi-Pazar takvim haftası için esnek 2 Koşu + 2 Kuvvet görünümünü döner."""
        schedule, _ = self._build_weekly_schedule_entries()
        return schedule

    @request_cached
    @zone_text
    def get_weekly_quota_summary(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Pazartesi sıfırlamalı esnek haftalık kota özetini ve güncel yeniden planlamayı döner."""
        _, week_meta = self._build_weekly_schedule_entries(now=now)
        runs_done = week_meta["runs_done"]
        gyms_done = week_meta["gyms_done"]
        rem_runs = week_meta["rem_runs"]
        rem_gyms = week_meta["rem_gyms"]
        carry = week_meta["carryover"]
        post_tempo_adapted = bool(week_meta.get("post_tempo_adapted"))

        def _run_reason(idx: int, kind: str) -> Optional[str]:
            if idx == 0 and kind == carry["run_order"][0]:
                return carry["run_priority_reason"]
            return None

        rem_run_items = [
            self._build_quota_remaining_item(kind, ordinal, _run_reason(idx, kind))
            for idx, (kind, ordinal) in enumerate(week_meta["needed_runs"])
        ]
        rem_gym_items = [
            self._build_quota_remaining_item(
                kind,
                ordinal,
                carry["gym_priority_reason"] if (idx == 0 and kind == carry["gym_order"][0]) else None,
            )
            for idx, (kind, ordinal) in enumerate(week_meta["needed_gyms"])
        ]

        gym_status_text, headline, run_status_text, spont_status_text, spontaneous_items = self._build_quota_status_texts(gyms_done, post_tempo_adapted, rem_gym_items, rem_gyms, rem_run_items, rem_runs, runs_done, week_meta)

        run_target = week_meta.get("run_target", 2)
        gym_target = week_meta.get("gym_target", 2)
        total_target = run_target + gym_target
        dyn = week_meta.get("dynamic_targets") or {}
        total_done = runs_done + gyms_done
        total_rem = rem_runs + rem_gyms
        capped_done = min(runs_done, run_target) + min(gyms_done, gym_target)

        return {
            "week_range": week_meta["week_range"],
            "headline": headline,
            "flexibility_note": "",
            "post_tempo_adapted": post_tempo_adapted,
            "dynamic_targets": {
                "athlete_level": dyn.get("athlete_level", "Temel / Gelişim"),
                "active_split": dyn.get("active_split", "5x5_linear"),
                "active_split_name": dyn.get("active_split_name", "5x5 Doğrusal (A/B)"),
                "recommended_split": dyn.get("recommended_split", "5x5_linear"),
                "recommended_split_name": dyn.get("recommended_split_name", "5x5 Doğrusal (A/B)"),
                "plateau_score": dyn.get("plateau_score", 0),
                "run_target": run_target,
                "gym_target": gym_target,
                "projection_horizon": dyn.get("projection_horizon", 4),
                "run_plan_summary": dyn.get("run_plan_summary", ""),
                "gym_plan_summary": dyn.get("gym_plan_summary", ""),
            },
            "last_week_adaptation": {
                "prev_week_range": carry["prev_week_range"],
                "prev_runs_done": carry["prev_runs_done"],
                "prev_gyms_done": carry["prev_gyms_done"],
                "missed_sessions": carry["missed_sessions"],
                "adaptation_note": carry["adaptation_note"],
                "monday_reset_enforced": True,
            },
            "next_4_runs_prediction": carry.get("next_4_runs_prediction"),
            "total": {
                "target": total_target,
                "completed": total_done,
                "remaining": total_rem,
                "progress_pct": min(100, round((capped_done / max(1, total_target)) * 100)),
                "is_complete": (rem_runs == 0 and rem_gyms == 0),
            },
            "running": {
                "target": run_target,
                "completed": runs_done,
                "remaining": rem_runs,
                "completed_kinds": week_meta["completed_run_kinds"],
                "progress_pct": min(100, round((min(runs_done, run_target) / max(1, run_target)) * 100)),
                "completed_labels": [r["label"] for r in week_meta["runs_completed_items"]],
                "completed_items": week_meta["runs_completed_items"],
                "remaining_items": rem_run_items,
                "status_text": run_status_text,
                "plan_summary": dyn.get("run_plan_summary", ""),
            },
            "strength": {
                "target": gym_target,
                "completed": gyms_done,
                "remaining": rem_gyms,
                "completed_kinds": week_meta["completed_gym_kinds"],
                "progress_pct": min(100, round((min(gyms_done, gym_target) / max(1, gym_target)) * 100)),
                "completed_labels": [g["label"] for g in week_meta["gyms_completed_items"]],
                "completed_items": week_meta["gyms_completed_items"],
                "remaining_items": rem_gym_items,
                "status_text": gym_status_text,
                "plan_summary": dyn.get("gym_plan_summary", ""),
            },
            "remaining_items": rem_run_items + rem_gym_items,
            "spontaneous": {
                "count": len(spontaneous_items),
                "items": spontaneous_items,
                "labels": [s["label"] for s in spontaneous_items],
                "status_text": spont_status_text,
            },
            "rest_days": {
                "count": sum(
                    1 for d in week_meta["days"]
                    if d.get("is_past") and not d.get("is_completed") and d.get("slot_kind") == "rest"
                ),
                "days": [
                    {
                        "date": d["date_str"],
                        "label": d["day_label"].split(" (")[0].strip(),
                    }
                    for d in week_meta["days"]
                    if d.get("is_past") and not d.get("is_completed") and d.get("slot_kind") == "rest"
                ],
                "importance_note": (
                    "Dinlenme günleri kas glikojenini ve mikro-hasarları onarır, merkezi sinir sistemi "
                    "yorgunluğunu düşürür, HRV/Readiness rezervini yükseltir ve ACWR dengesini koruyarak "
                    "bir sonraki sert antrenmanda yüksek kalite (ve düşük sakatlık riski) sağlar."
                ),
            },
        }

    def _build_quota_status_texts(self, gyms_done, post_tempo_adapted, rem_gym_items, rem_gyms, rem_run_items, rem_runs, runs_done, week_meta):
        """Haftalık kota başlığını ve koşu / kuvvet / spontane durum metinlerini üretir."""
        run_target = week_meta.get("run_target", 2)
        gym_target = week_meta.get("gym_target", 2)
        total_target = run_target + gym_target
        done_parts: List[str] = []
        if runs_done > 0:
            if post_tempo_adapted:
                done_parts.append(f"{runs_done} Koşu (Tempo — Kotaya Sayıldı)")
            else:
                done_parts.append(f"{runs_done} Koşu")
        if gyms_done > 0:
            done_parts.append(f"{gyms_done} Kuvvet")
        done_str = f"Bu hafta {' + '.join(done_parts)} tamamladın" if done_parts else "Bu hafta henüz planlı seans tamamlamadın"

        rem_parts: List[str] = []
        if rem_runs >= 2:
            rem_parts.append(f"{rem_runs} Koşu (" + " + ".join(i["short_label"] for i in rem_run_items) + ")")
        elif rem_runs == 1 and rem_run_items:
            rem_parts.append(f"1 {rem_run_items[0]['short_label']}")
        if rem_gyms >= 2:
            rem_parts.append(f"{rem_gyms} Kuvvet (" + " + ".join(i["short_label"] for i in rem_gym_items) + ")")
        elif rem_gyms == 1 and rem_gym_items:
            rem_parts.append(f"1 {rem_gym_items[0]['short_label']}")

        rem_str = (
            f"Haftalık {total_target}/{total_target} temel antrenman kotan tamamlandı!"
            if (rem_runs == 0 and rem_gyms == 0)
            else f"Geriye {' + '.join(rem_parts)} kaldı"
        )
        headline = f"{done_str} · {rem_str}"

        run_status_text = (
            f"{runs_done}/{run_target} Tamamlandı · Haftalık koşu kotası doldu"
            if rem_runs == 0
            else f"{runs_done}/{run_target} Tamamlandı · Geriye {rem_runs} ({' + '.join(i['short_label'] for i in rem_run_items)}) kaldı"
        )
        gym_status_text = (
            f"{gyms_done}/{gym_target} Tamamlandı · Haftalık kuvvet kotası doldu"
            if rem_gyms == 0
            else f"{gyms_done}/{gym_target} Tamamlandı · Geriye {rem_gyms} ({' + '.join(i['short_label'] for i in rem_gym_items)}) kaldı"
        )
        spontaneous_items = week_meta["spontaneous_items"]
        spont_status_text = (
            f"Bu hafta {len(spontaneous_items)} spontane seans ({', '.join(s['sport_tr'] for s in spontaneous_items)}) kaydedildi"
            if spontaneous_items
            else "Bu hafta henüz spontane branş (Yelken / Basketbol / Kayak vb.) kaydı yok"
        )
        return gym_status_text, headline, run_status_text, spont_status_text, spontaneous_items

