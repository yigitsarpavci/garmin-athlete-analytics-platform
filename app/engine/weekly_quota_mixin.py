#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Esnek Haftalık Kota & Pazartesi Sıfırlama Adaptasyon Mixin'i.
Pazartesi-Pazar penceresinde 2 Koşu + 2 Kuvvet kotasını takip eder; Pazartesi temiz 0/2 açılır
ancak geçen haftadan eksik kalan seans türünü yeni haftada öncelik sırasına yerleştirir.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

try:
    from engine.helpers import TR_DAYS, TR_MONTHS, format_sport_tr, classify_sport_bucket, classify_run_workout
except ImportError:
    from app.engine.helpers import TR_DAYS, TR_MONTHS, format_sport_tr, classify_sport_bucket, classify_run_workout


_BASE_QUOTA_TEMPLATES: Dict[str, Dict[str, str]] = {
    "zone2": {
        "category": "running",
        "type": "Zone 2 Koşu",
        "short_label": "Zone 2 Koşu",
        "title_prefix": "Zone 2 Rahat Taban",
        "target_hr": "140 - 150 bpm",
        "target_pace": "6:35 - 6:50 /km",
        "duration": "45-50 dk",
        "badge": "Zone 2 Taban",
        "protocol_day_code": "thursday",
        "coaching_note": "140-150 bpm nabız tavanını aşmadan, 160+ spm kadans ve burundan rahat nefesle haftanın uygun bir gününde uygula.",
    },
    "interval": {
        "category": "running",
        "type": "5K Hız İntervali",
        "short_label": "5K Hız İntervali",
        "title_prefix": "5K Hız İntervali (4x1.000m)",
        "target_hr": "172 - 180 bpm",
        "target_pace": "5:15 /km",
        "duration": "45 dk",
        "badge": "5K İnterval",
        "protocol_day_code": "monday",
        "coaching_note": "10 dk ısınma + 4x1.000m @ 5:15 /km (aralarda 3 dk yürüyüş/jog) + 8 dk soğuma; bacakların taze olduğu bir günde uygula.",
    },
    "gym_a": {
        "category": "strength",
        "type": "Workout A",
        "short_label": "Workout A",
        "title_prefix": "Workout A (5x5)",
        "exercises_summary": "Squat 67.5 kg (5x5) · Bench Press 52.5 kg (5x5 PR) · Barbell Row 62.5 kg (5x5) · Lateral Raise 25 kg (3x12) · Shrug 45 kg (3x12)",
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
        "exercises_summary": "Squat 67.5 kg (5x5) · OHP 40.0 kg (5x5) · Deadlift 65.0 kg (1x5) · Lat Pulldown 45.0 kg (4x12) · Lateral Raise 25 kg (3x12) · Shrug 45 kg (3x12)",
        "duration": "55 dk",
        "badge": "Workout B",
        "protocol_day_code": "saturday",
        "coaching_note": "Arka zincir ve omuz gelişimi için bacakların toparlandığı uygun bir günde uygula.",
    },
}


class WeeklyQuotaMixin:
    """Pazartesi sıfırlamalı esnek haftalık kota, geçmiş hafta açığı adaptasyonu ve çizelge üretimi."""

    def _get_dynamic_gym_summaries(self) -> Dict[str, str]:
        """Son salon kayıtlarındaki progression hedeflerinden Workout A/B özetlerini üretir."""
        prog = {}
        if hasattr(self, "get_gym_exercise_history"):
            try:
                prog = (self.get_gym_exercise_history() or {}).get("progression", {})
            except Exception:
                prog = {}
        if not prog:
            return {
                "gym_a": _BASE_QUOTA_TEMPLATES["gym_a"]["exercises_summary"],
                "gym_b": _BASE_QUOTA_TEMPLATES["gym_b"]["exercises_summary"],
            }

        sq = prog.get("squat", {}).get("next_target", "67.5 kg x 5x5").split(" x ")[0]
        bp = prog.get("bench", {}).get("next_target", "52.5 kg").split(" x ")[0]
        rw = prog.get("row", {}).get("next_target", "62.5 kg").split(" x ")[0]
        ohp = prog.get("ohp", {}).get("next_target", "40.0 kg").split(" x ")[0]
        dl = prog.get("deadlift", {}).get("next_target", "65.0 kg").split(" x ")[0]
        lat = prog.get("lat_pulldown", {}).get("next_target", "45.0-50.0 kg").split(" x ")[0]
        lr = prog.get("lateral_raise", {}).get("next_target", "22.5-25.0 kg").split(" x ")[0]
        sh = prog.get("shrug", {}).get("next_target", "45.0 kg").split(" x ")[0]

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

    def _analyze_previous_week_carryover(
        self,
        monday_anchor: datetime,
        gym_type_by_date: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Geçen Pzt-Paz haftasındaki eksik seansları analiz eder.
        Pazartesi kotası daima temiz 0/2 açılır (borç eklenmez), ancak geçen hafta eksik kalan
        seans türü yeni haftanın ilk sırasına önceliklendirilir.
        """
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
        prev_had_tempo = "tempo" in prev_run_kinds

        prev_gym_types = [gym_type_by_date.get((g.get("startTimeLocal") or "")[:10], "Kuvvet") for g in prev_gyms_sorted]
        prev_had_a = any("Workout A" in wt for wt in prev_gym_types)
        prev_had_b = any("Workout B" in wt for wt in prev_gym_types)

        missed_sessions: List[str] = []
        run_order = ["interval", "zone2"]
        gym_order = ["gym_a", "gym_b"]
        run_priority_reason: Optional[str] = None
        gym_priority_reason: Optional[str] = None

        if len(prev_runs_sorted) == 1:
            if prev_had_tempo and not prev_had_interval and not prev_had_zone2:
                missed_sessions.append("5K Hız İntervali (Geçen hafta Tempo koşuldu, AnTE 0.0)")
                run_order = ["interval", "zone2"]
                run_priority_reason = "Geçen hafta koşu Tempo (AnTE 0.0) yapıldığı için 5K Hız İntervali bu hafta ilk sıraya alındı."
            elif prev_had_zone2 and not prev_had_interval:
                missed_sessions.append("5K Hız İntervali")
                run_order = ["interval", "zone2"]
                run_priority_reason = "Geçen hafta eksik kalan 5K Hız İntervali bu hafta ilk koşu önceliğine alındı."
            elif prev_had_interval and not prev_had_zone2:
                missed_sessions.append("Zone 2 Koşu")
                run_order = ["zone2", "interval"]
                run_priority_reason = "Geçen hafta eksik kalan Zone 2 Koşu bu hafta ilk koşu önceliğine alındı."
            else:
                missed_sessions.append("2. Koşu seansı")
        elif len(prev_runs_sorted) >= 2 and prev_had_tempo and not prev_had_interval and not prev_had_zone2:
            missed_sessions.append("5K Hız İntervali (Geçen hafta Tempo koşuldu, AnTE 0.0)")
            run_order = ["interval", "zone2"]
            run_priority_reason = "Geçen hafta koşular sürekli Tempo (AnTE 0.0) olarak yapıldığı ve Anaerobik yük eksik kaldığı için 5K Hız İntervali ilk önceliğe alındı."
        elif len(prev_runs_sorted) == 0 and any(True for _ in prev_gyms_sorted):
            missed_sessions.extend(["Zone 2 Koşu", "5K Hız İntervali"])

        if len(prev_gyms_sorted) == 1:
            if prev_had_a and not prev_had_b:
                missed_sessions.append("Workout B")
                gym_order = ["gym_b", "gym_a"]
                gym_priority_reason = "Geçen hafta yalnızca Workout A yapıldığı için eksik kalan Workout B bu hafta ilk kuvvet önceliğine alındı."
            elif prev_had_b and not prev_had_a:
                missed_sessions.append("Workout A")
                gym_order = ["gym_a", "gym_b"]
                gym_priority_reason = "Geçen hafta yalnızca Workout B yapıldığı için eksik kalan Workout A bu hafta ilk kuvvet önceliğine alındı."
            else:
                missed_sessions.append("2. Kuvvet seansı")
        elif len(prev_gyms_sorted) == 0 and any(True for _ in prev_runs_sorted):
            missed_sessions.extend(["Workout A", "Workout B"])

        # Firstbeat Anaerobik eksiği daha büyükse (ve geçen hafta Z2 eksik kalmadıysa) İnterval'i öne çek
        if not run_priority_reason and hasattr(self, "get_training_load_analytics"):
            try:
                tl = self.get_training_load_analytics() or {}
                foc = tl.get("load_focus", {})
                low_pct = foc.get("aerobic_low", {}).get("pct_of_target", 90)
                an_pct = foc.get("anaerobic", {}).get("pct_of_target", 90)
                if len(prev_runs_sorted) >= 2 and an_pct + 15 < low_pct:
                    run_order = ["interval", "zone2"]
                    run_priority_reason = (
                        f"Anaerobik yük (%{round(an_pct)}) Düşük Aerobik barından (%{round(low_pct)}) daha düşük olduğu için hız intervali ilk sıraya önerildi."
                    )
            except Exception:
                pass

        has_prev_data = bool(prev_runs_sorted or prev_gyms_sorted)
        if not has_prev_data:
            adaptation_note = "Geçen hafta bazlı ek kısıt saptanmadı — bu hafta temiz 2 Koşu + 2 Kuvvet kotasıyla başlar."
        elif missed_sessions:
            adaptation_note = (
                f"Pazartesi 0/2 kotası borçsuz sıfırlandı ({prev_range}: {len(prev_runs_sorted)}/2 Koşu, {len(prev_gyms_sorted)}/2 Kuvvet). "
                f"Geçen hafta eksik kalan {', '.join(missed_sessions)} bu haftanın öncelik sırasına yerleştirildi."
            )
        else:
            adaptation_note = (
                f"Geçen hafta ({prev_range}) 2 Koşu + 2 Kuvvet tam tamamlandı; bu hafta dengeli rota ile devam ediyor."
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
        }

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

        carryover = self._analyze_previous_week_carryover(monday_anchor, gym_type_by_date)
        gym_summaries = self._get_dynamic_gym_summaries()

        planned_run_order = list(carryover["run_order"])
        planned_gym_order = list(carryover["gym_order"])

        day_acts: List[List[Dict[str, Any]]] = []
        runs_done_list: List[Dict[str, Any]] = []
        gyms_done_list: List[Dict[str, Any]] = []
        runs_completed_items: List[Dict[str, Any]] = []
        gyms_completed_items: List[Dict[str, Any]] = []
        spontaneous_items: List[Dict[str, Any]] = []
        completed_run_kinds: List[str] = []
        completed_gym_kinds: List[str] = []
        plan_deviations: List[Dict[str, Any]] = []
        run_cls_by_id: Dict[int, Dict[str, Any]] = {}
        day_deviations: Dict[str, List[Dict[str, Any]]] = {}
        last_gym_type: Optional[str] = None

        for d_date in week_dates:
            d_str = d_date.strftime("%Y-%m-%d")
            day_short = f"{d_date.day} {TR_MONTHS[d_date.month - 1]} {TR_DAYS[d_date.weekday()]}"
            matched = [a for a in self.activities_all if (a.get("startTimeLocal") or "")[:10] == d_str]
            day_acts.append(matched)
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
                    idx_r = len(runs_done_list)
                    runs_done_list.append(act)
                    r_cls = classify_run_workout(act)
                    actual_kind = r_cls["kind"]
                    completed_run_kinds.append(actual_kind)

                    expected_kind = planned_run_order[idx_r] if idx_r < len(planned_run_order) else planned_run_order[-1]
                    if expected_kind in completed_run_kinds[:-1]:
                        alt = [k for k in planned_run_order if k != expected_kind]
                        if alt:
                            expected_kind = alt[0]
                    expected_label = _BASE_QUOTA_TEMPLATES[expected_kind]["short_label"]
                    r_cls["expected_kind"] = expected_kind
                    r_cls["expected_label"] = expected_label
                    r_cls["is_deviation"] = (actual_kind != expected_kind)
                    run_cls_by_id[id(act)] = r_cls

                    dist_km = round(dist_m / 1000.0, 2) if dist_m > 0 else 0.0
                    dist_txt = f"{dist_km:.2f} km · " if dist_km > 0 else ""

                    if actual_kind == "tempo":
                        item_label = (
                            f"{day_short} · {r_cls['label_tr']} [Haftalık Koşu Kotasına Sayıldı] "
                            f"({dist_txt}{dur_m} dk{hr_txt} · TE: {r_cls['te_label']}, AnTE: {r_cls['an_te']})"
                        )
                        dev = {
                            "date": d_str,
                            "day_label": day_short,
                            "category": "running",
                            "planned_kind": expected_kind,
                            "planned_label": expected_label,
                            "actual_kind": actual_kind,
                            "actual_label": r_cls["label_tr"],
                            "badge": f"Kota Güncellendi: {r_cls['short_label']}",
                            "note": (
                                f"{day_short} yapılan {r_cls['label_tr']} ({avg_hr} bpm, TE: {r_cls['te_label']}, AnTE: {r_cls['an_te']}) "
                                f"haftalık koşu kotasına sayıldı ve koşu kotası 1 düşürüldü. "
                                f"{expected_label} ise henüz yapılmadığı için haftanın kalan koşu kotası olarak korundu."
                            ),
                        }
                        plan_deviations.append(dev)
                        day_deviations.setdefault(d_str, []).append(dev)
                    elif r_cls["is_deviation"]:
                        item_label = (
                            f"{day_short} · {r_cls['label_tr']} [Haftalık Koşu Kotasına Sayıldı] "
                            f"({dist_txt}{dur_m} dk{hr_txt})"
                        )
                        dev = {
                            "date": d_str,
                            "day_label": day_short,
                            "category": "running",
                            "planned_kind": expected_kind,
                            "planned_label": expected_label,
                            "actual_kind": actual_kind,
                            "actual_label": r_cls["label_tr"],
                            "badge": f"Kota Güncellendi: {r_cls['short_label']}",
                            "note": (
                                f"{day_short} yapılan {r_cls['label_tr']} haftalık koşu kotasına sayıldı ve kota 1 düşürüldü; "
                                f"kalan koşu kotası {expected_label} olarak güncellendi."
                            ),
                        }
                        plan_deviations.append(dev)
                        day_deviations.setdefault(d_str, []).append(dev)
                    else:
                        item_label = f"{day_short} · {r_cls['label_tr']} ({dist_txt}{dur_m} dk{hr_txt})"

                    runs_completed_items.append({
                        "date": d_str,
                        "day_label": day_short,
                        "title": act_name,
                        "workout_type": r_cls["label_tr"],
                        "actual_kind": actual_kind,
                        "expected_kind": expected_kind,
                        "is_deviation": r_cls["is_deviation"],
                        "te_label": r_cls["te_label"],
                        "an_te": r_cls["an_te"],
                        "distance_km": dist_km,
                        "duration_min": dur_m,
                        "avg_hr": avg_hr,
                        "calories": cal,
                        "label": item_label,
                    })
                elif bucket == "strength":
                    idx_g = len(gyms_done_list)
                    gyms_done_list.append(act)
                    w_type = gym_type_by_date.get(d_str) or "Kuvvet"
                    last_gym_type = w_type if w_type != "Kuvvet" else last_gym_type
                    g_kind = "gym_a" if "Workout A" in w_type else ("gym_b" if "Workout B" in w_type else planned_gym_order[min(idx_g, len(planned_gym_order) - 1)])
                    completed_gym_kinds.append(g_kind)
                    expected_g = planned_gym_order[idx_g] if idx_g < len(planned_gym_order) else planned_gym_order[-1]
                    if g_kind != expected_g and w_type != "Kuvvet":
                        exp_g_lbl = _BASE_QUOTA_TEMPLATES[expected_g]["short_label"]
                        dev = {
                            "date": d_str,
                            "day_label": day_short,
                            "category": "strength",
                            "planned_kind": expected_g,
                            "planned_label": exp_g_lbl,
                            "actual_kind": g_kind,
                            "actual_label": w_type,
                            "badge": f"Kota Güncellendi: {w_type}",
                            "note": f"{day_short} günü {w_type} uygulandı ve haftalık kuvvet kotasına sayıldı; kalan kuvvet kotası {exp_g_lbl} olarak güncellendi.",
                        }
                        plan_deviations.append(dev)
                        day_deviations.setdefault(d_str, []).append(dev)
                    gyms_completed_items.append({
                        "date": d_str,
                        "day_label": day_short,
                        "workout_type": w_type,
                        "actual_kind": g_kind,
                        "title": f"Kuvvet #{len(gyms_done_list)} · {w_type} (5x5)",
                        "duration_min": dur_m,
                        "avg_hr": avg_hr,
                        "calories": cal,
                        "label": f"{day_short} · {w_type} ({dur_m} dk{hr_txt})",
                    })
                else:
                    sport_tr = format_sport_tr(sport_key, act_name)
                    spontaneous_items.append({
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

        runs_done = len(runs_done_list)
        gyms_done = len(gyms_done_list)
        rem_runs = max(0, 2 - runs_done)
        rem_gyms = max(0, 2 - gyms_done)
        post_tempo_adapted = False

        needed_runs: List[Tuple[str, int]] = []
        if rem_runs == 2:
            needed_runs = [(planned_run_order[0], 1), (planned_run_order[1], 2)]
        elif rem_runs == 1:
            if "interval" in completed_run_kinds and "zone2" not in completed_run_kinds:
                needed_runs = [("zone2", runs_done + 1)]
            elif "zone2" in completed_run_kinds and "interval" not in completed_run_kinds:
                needed_runs = [("interval", runs_done + 1)]
            else:
                post_tempo_adapted = True
                next_kind = "interval" if planned_run_order[0] == "interval" else "zone2"
                needed_runs = [(next_kind, runs_done + 1)]

        needed_gyms: List[Tuple[str, int]] = []
        if rem_gyms == 2:
            needed_gyms = [(planned_gym_order[0], 1), (planned_gym_order[1], 2)]
        elif rem_gyms == 1:
            if "gym_a" in completed_gym_kinds and "gym_b" not in completed_gym_kinds:
                next_gym = "gym_b"
            elif "gym_b" in completed_gym_kinds and "gym_a" not in completed_gym_kinds:
                next_gym = "gym_a"
            else:
                next_gym = "gym_a" if last_gym_type and "Workout B" in last_gym_type else "gym_b"
            needed_gyms = [(next_gym, gyms_done + 1)]

        needed_queue: List[Tuple[str, int]] = []
        for idx in range(max(len(needed_runs), len(needed_gyms))):
            if idx < len(needed_runs):
                needed_queue.append(needed_runs[idx])
            if idx < len(needed_gyms):
                needed_queue.append(needed_gyms[idx])

        open_offsets = [i for i in range(7) if not day_acts[i] and week_dates[i].date() >= now.date()]
        completed_day_indices = {i for i in range(7) if day_acts[i]}
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

        def _format_completed_day(matched: List[Dict[str, Any]], d_str: str, run_c: List[int], gym_c: List[int]) -> Dict[str, Any]:
            titles, details, hr_notes = [], [], []
            has_run = False
            has_gym = False
            devs_today = day_deviations.get(d_str, [])
            dev_badge = devs_today[0]["badge"] if devs_today else None
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
                    r_cls = run_cls_by_id.get(id(act)) or classify_run_workout(act)
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
                    has_gym = True
                    gym_c[0] += 1
                    w_type = gym_type_by_date.get(d_str) or "Kuvvet"
                    titles.append(f"Kuvvet #{gym_c[0]} • {w_type} (5x5)")
                    details.append(f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm)")
                else:
                    sport_tr = format_sport_tr(sport_key, act_name)
                    titles.append(f"{sport_tr} (Spontane) • {act_name}")
                    details.append(f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm)")
                if avg_hr:
                    hr_notes.append(f"{avg_hr} bpm ort.")
            est_cal = "~2.950 kcal" if has_run else ("~2.850 kcal" if has_gym else "~2.900 kcal")
            macro_txt = "2.500 kcal (175g P / 265g K / 80g Y)" if has_run else "2.450 kcal (175g P / 250g K / 80g Y)"
            return {
                "primary": " + ".join(titles),
                "secondary": " • ".join(details),
                "target": "Gerçekleşen: " + (", ".join(hr_notes) if hr_notes else "Kaydedildi"),
                "calories": est_cal,
                "macro": macro_txt,
                "deviation_badge": dev_badge,
            }

        def _build_planned_slot(slot_kind: str, ordinal: int) -> Dict[str, str]:
            is_last_run = (rem_runs == 1 and runs_done == 1)
            is_last_gym = (rem_gyms == 1 and gyms_done == 1)
            prio_hint = ""
            if slot_kind in ("zone2", "interval") and post_tempo_adapted:
                prio_hint = " (Tempo Sonrası Güncel Telafi)"
            elif slot_kind == planned_run_order[0] and carryover["run_priority_reason"] and ordinal == 1:
                prio_hint = " (Öncelikli)"
            elif slot_kind == planned_gym_order[0] and carryover["gym_priority_reason"] and ordinal == 1:
                prio_hint = " (Öncelikli)"

            if slot_kind == "gym_a":
                quota_lbl = "2/2 Son Salon Kotası" if is_last_gym else f"{rem_gyms} Kalan Kuvvet Kotası"
                return {
                    "primary": f"Kuvvet #{ordinal} · Kalan Kota{prio_hint} · {gym_summaries['gym_a'].split(' · Lateral')[0]}",
                    "secondary": f"Esnek Gün — Bu hafta geriye {rem_gyms} kuvvet kaldı ({quota_lbl}), istediğin uygun gün uygula • {gym_summaries['gym_a']}",
                    "target": "115-128 bpm (Zone 1)",
                    "calories": "~2.850 kcal",
                    "macro": "2.450 kcal (175g P / 250g K / 80g Y)",
                }
            if slot_kind == "gym_b":
                quota_lbl = "2/2 Son Salon Kotası" if is_last_gym else f"{rem_gyms} Kalan Kuvvet Kotası"
                return {
                    "primary": f"Kuvvet #{ordinal} · Kalan Kota{prio_hint} · {gym_summaries['gym_b'].split(' · Lateral')[0]}",
                    "secondary": f"Esnek Gün — Bu hafta geriye {rem_gyms} kuvvet kaldı ({quota_lbl}), istediğin uygun gün uygula • {gym_summaries['gym_b']}",
                    "target": "115-130 bpm (Zone 1)",
                    "calories": "~2.900 kcal",
                    "macro": "2.500 kcal (180g P / 270g K / 80g Y)",
                }
            if slot_kind == "zone2":
                quota_lbl = "2/2 Son Koşu Kotası" if is_last_run else f"{rem_runs} Kalan Koşu Kotası"
                return {
                    "primary": f"Koşu #{ordinal} · Kalan Kota{prio_hint} · Zone 2 Rahat Taban (45-50 dk)",
                    "secondary": f"Esnek Gün — Bu hafta geriye {rem_runs} koşu kaldı ({quota_lbl}), toparlanmana uygun günde uygula • 160+ kadans, burundan nefes",
                    "target": "140-150 bpm (6:35-6:50 /km)",
                    "calories": "~2.950 kcal",
                    "macro": "2.550 kcal (175g P / 275g K / 80g Y)",
                }
            quota_lbl = "2/2 Son Koşu Kotası" if is_last_run else f"{rem_runs} Kalan Koşu Kotası"
            extra_tempo_note = (
                " · Planlanan İnterval yerine Tempo koşulduğu için Anaerobik (AnTE) hâlâ eksik"
                if post_tempo_adapted else ""
            )
            return {
                "primary": f"Koşu #{ordinal} · Kalan Kota{prio_hint} · 5K Hız İntervali (45 dk, 4x1.000m)",
                "secondary": f"Esnek Gün — Bu hafta geriye {rem_runs} koşu kaldı ({quota_lbl}), taze bacaklarla uygun günde uygula{extra_tempo_note} • 5:15 /km tempo, 3 dk jog",
                "target": "170-183 bpm (Zone 4-5)",
                "calories": "~3.050 kcal",
                "macro": "2.650 kcal (175g P / 300g K / 80g Y)",
            }

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
            is_completed = bool(day_acts[i])
            if is_completed:
                day_label = f"{base_day} (Bugün)" if is_today else base_day
                row_data = _format_completed_day(day_acts[i], d_str, run_counter, gym_counter)
            elif i in assigned_slot:
                slot_kind, ordinal = assigned_slot[i]
                if is_today:
                    day_label = f"{base_day} (Bugün · Güncel Plan)"
                elif is_tomorrow:
                    day_label = f"{base_day} (Yarın · Güncel Öneri)"
                else:
                    day_label = f"{base_day} (Güncel Önerilen Pencere)"
                row_data = _build_planned_slot(slot_kind, ordinal)
            elif i == adapted_recovery_day_idx:
                slot_kind = "rest"
                day_label = f"{base_day} ({'Bugün · ' if is_today else ''}Uyarlanmış Toparlanma)"
                prev1_lbl = f"{week_dates[i - 1].day} {TR_MONTHS[week_dates[i - 1].month - 1]} {TR_DAYS[week_dates[i - 1].weekday()]}"
                prev2_lbl = f"{week_dates[i - 2].day} {TR_MONTHS[week_dates[i - 2].month - 1]} {TR_DAYS[week_dates[i - 2].weekday()]}"
                row_data = {
                    "primary": "Uyarlanmış Toparlanma / Rejenerasyon Penceresi",
                    "secondary": (
                        f"{prev2_lbl} + {prev1_lbl} üst üste yüklendiği için bugün toparlanma günü olarak ayrıldı; "
                        f"kalan {total_rem} seans dinlenmiş günlere kaydırıldı"
                    ),
                    "target": "<105 bpm (Aktif Dinlenme)",
                    "calories": "~2.450 kcal",
                    "macro": "2.350 kcal (175g P / 220g K / 80g Y)",
                }
            elif i == 6:
                slot_kind = "active_recovery"
                day_label = f"{base_day} (Esnek Kapanış)" if not is_today else f"{base_day} (Bugün · Esnek Kapanış)"
                quota_note = (
                    "Haftalık 4/4 antrenman kotası tamamlandı"
                    if total_rem == 0
                    else f"Bu hafta {total_done}/4 seans tamamlandı, geriye {total_rem} esnek seans kaldı"
                )
                row_data = {
                    "primary": "Aktif Toparlanma / Mobilite & Esnek Yürüyüş",
                    "secondary": f"Esnek Gün — Hafif yürüyüş, esneme, nefes (NSDR) • {quota_note}",
                    "target": "<110 bpm (Zone 1)",
                    "calories": "~2.500 kcal",
                    "macro": "2.350 kcal (175g P / 220g K / 80g Y)",
                }
            else:
                slot_kind = "rest"
                if is_past:
                    day_label = f"{base_day} (Geçti · Dinlenme)"
                    sec_txt = "Geçmiş Dinlenme / Ekstra Kayıt Yok"
                else:
                    prefix = "Bugün · " if is_today else ("Yarın · " if is_tomorrow else "")
                    day_label = f"{base_day} ({prefix}Esnek Dinlenme)"
                    sec_txt = (
                        f"Esnek Gün — Bu hafta {total_done}/4 seans tamamlandı, geriye {total_rem} seans kaldı; kalan kotayı dilediğin uygun güne taşıyabilirsin"
                        if total_rem > 0
                        else "Haftalık 4/4 antrenman kotası tamamlandı — kas onarımı & 00:30 öncesi uyku"
                    )
                row_data = {
                    "primary": "Esnek Toparlanma / Rejenerasyon Penceresi",
                    "secondary": sec_txt,
                    "target": "<100 bpm (Parasempatik gün)",
                    "calories": "~2.450 kcal",
                    "macro": "2.350 kcal (175g P / 220g K / 80g Y)",
                }

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
            "runs_done": runs_done,
            "gyms_done": gyms_done,
            "rem_runs": rem_runs,
            "rem_gyms": rem_gyms,
            "needed_runs": needed_runs,
            "needed_gyms": needed_gyms,
            "completed_run_kinds": completed_run_kinds,
            "completed_gym_kinds": completed_gym_kinds,
            "plan_deviations": plan_deviations,
            "post_tempo_adapted": post_tempo_adapted,
            "adapted_recovery_day_idx": adapted_recovery_day_idx,
            "runs_completed_items": runs_completed_items,
            "gyms_completed_items": gyms_completed_items,
            "spontaneous_items": spontaneous_items,
            "carryover": carryover,
            "days": meta_days,
        }

    def get_weekly_schedule(self) -> List[Dict[str, Any]]:
        """Pazartesi-Pazar takvim haftası için esnek 2 Koşu + 2 Kuvvet görünümünü döner."""
        schedule, _ = self._build_weekly_schedule_entries()
        return schedule

    def get_weekly_quota_summary(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Pazartesi sıfırlamalı esnek haftalık kota özetini, plan sapmalarını ve güncel yeniden planlamayı döner."""
        _, week_meta = self._build_weekly_schedule_entries(now=now)
        runs_done = week_meta["runs_done"]
        gyms_done = week_meta["gyms_done"]
        rem_runs = week_meta["rem_runs"]
        rem_gyms = week_meta["rem_gyms"]
        carry = week_meta["carryover"]
        deviations = week_meta.get("plan_deviations") or []
        post_tempo_adapted = bool(week_meta.get("post_tempo_adapted"))

        def _run_reason(idx: int, kind: str) -> Optional[str]:
            if idx == 0 and post_tempo_adapted:
                tempo_dev = next((d for d in deviations if d.get("actual_kind") == "tempo"), None)
                if tempo_dev:
                    return (
                        f"{tempo_dev['day_label']} yapılan {tempo_dev['actual_label']} haftalık koşu kotasını 1 düşürdü; "
                        f"{tempo_dev['planned_label']} ise henüz yapılmadığı için haftanın kalan koşu kotası olarak ayrıldı."
                    )
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
        if rem_runs == 2:
            rem_parts.append("2 Koşu (" + " + ".join(i["short_label"] for i in rem_run_items) + ")")
        elif rem_runs == 1 and rem_run_items:
            rem_parts.append(f"1 {rem_run_items[0]['short_label']}")
        if rem_gyms == 2:
            rem_parts.append("2 Kuvvet (" + " + ".join(i["short_label"] for i in rem_gym_items) + ")")
        elif rem_gyms == 1 and rem_gym_items:
            rem_parts.append(f"1 {rem_gym_items[0]['short_label']}")

        rem_str = (
            "Haftalık 4/4 temel antrenman kotan tamamlandı!"
            if (rem_runs == 0 and rem_gyms == 0)
            else f"Geriye {' + '.join(rem_parts)} kaldı"
        )
        headline = f"{done_str} · {rem_str}"

        run_status_text = (
            f"{runs_done}/2 Tamamlandı · Haftalık koşu kotası doldu"
            if rem_runs == 0
            else f"{runs_done}/2 Tamamlandı · Geriye {rem_runs} ({' + '.join(i['short_label'] for i in rem_run_items)}) kaldı"
        )
        gym_status_text = (
            f"{gyms_done}/2 Tamamlandı · Haftalık kuvvet kotası doldu"
            if rem_gyms == 0
            else f"{gyms_done}/2 Tamamlandı · Geriye {rem_gyms} ({' + '.join(i['short_label'] for i in rem_gym_items)}) kaldı"
        )
        spontaneous_items = week_meta["spontaneous_items"]
        spont_status_text = (
            f"Bu hafta {len(spontaneous_items)} spontane seans ({', '.join(s['sport_tr'] for s in spontaneous_items)}) kaydedildi"
            if spontaneous_items
            else "Bu hafta henüz spontane branş (Yelken / Basketbol / Kayak vb.) kaydı yok"
        )

        total_done = runs_done + gyms_done
        total_rem = rem_runs + rem_gyms
        capped_done = min(runs_done, 2) + min(gyms_done, 2)

        return {
            "week_range": week_meta["week_range"],
            "headline": headline,
            "flexibility_note": "",
            "plan_deviations": deviations,
            "post_tempo_adapted": post_tempo_adapted,
            "last_week_adaptation": {
                "prev_week_range": carry["prev_week_range"],
                "prev_runs_done": carry["prev_runs_done"],
                "prev_gyms_done": carry["prev_gyms_done"],
                "missed_sessions": carry["missed_sessions"],
                "adaptation_note": carry["adaptation_note"],
                "monday_reset_enforced": True,
            },
            "total": {
                "target": 4,
                "completed": total_done,
                "remaining": total_rem,
                "progress_pct": min(100, round((capped_done / 4) * 100)),
                "is_complete": (rem_runs == 0 and rem_gyms == 0),
            },
            "running": {
                "target": 2,
                "completed": runs_done,
                "remaining": rem_runs,
                "completed_kinds": week_meta["completed_run_kinds"],
                "progress_pct": min(100, round((min(runs_done, 2) / 2) * 100)),
                "completed_labels": [r["label"] for r in week_meta["runs_completed_items"]],
                "completed_items": week_meta["runs_completed_items"],
                "remaining_items": rem_run_items,
                "status_text": run_status_text,
            },
            "strength": {
                "target": 2,
                "completed": gyms_done,
                "remaining": rem_gyms,
                "completed_kinds": week_meta["completed_gym_kinds"],
                "progress_pct": min(100, round((min(gyms_done, 2) / 2) * 100)),
                "completed_labels": [g["label"] for g in week_meta["gyms_completed_items"]],
                "completed_items": week_meta["gyms_completed_items"],
                "remaining_items": rem_gym_items,
                "status_text": gym_status_text,
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
