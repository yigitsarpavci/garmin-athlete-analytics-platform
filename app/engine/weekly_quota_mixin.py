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
    from engine.helpers import TR_DAYS, TR_MONTHS, format_sport_tr, classify_sport_bucket
except ImportError:
    from app.engine.helpers import TR_DAYS, TR_MONTHS, format_sport_tr, classify_sport_bucket


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
        "exercises_summary": "Squat 67.5 kg (5x5) · Bench Press 52.5 kg (5x5 PR) · Barbell Row 62.5 kg (5x5) · Lateral Raise 25 kg · Shrug 45 kg",
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
        "exercises_summary": "Squat 67.5 kg (5x5) · OHP 40.0 kg (5x5) · Deadlift 65.0 kg (1x5) · Lat Pulldown 45.0 kg (4x12) · Lateral Raise 25 kg · Shrug 45 kg",
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
            "gym_a": f"Squat {sq} (5x5) · Bench {bp} (5x5) · Row {rw} (5x5) · Lateral {lr} · Shrug {sh}",
            "gym_b": f"Squat {sq} (5x5) · OHP {ohp} (5x5) · Deadlift {dl} (1x5) · Lat {lat} (4x12) · Lateral {lr}",
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

        prev_had_interval = any(((r.get("averageHR") or 0) >= 152 or (r.get("anaerobicTrainingEffect") or 0) >= 1.5) for r in prev_runs_sorted)
        prev_had_zone2 = any(((r.get("averageHR") or 0) > 0 and (r.get("averageHR") or 0) < 152) for r in prev_runs_sorted)
        if len(prev_runs_sorted) >= 2 and not prev_had_zone2 and not prev_had_interval:
            prev_had_zone2 = prev_had_interval = True

        prev_gym_types = [gym_type_by_date.get((g.get("startTimeLocal") or "")[:10], "Kuvvet") for g in prev_gyms_sorted]
        prev_had_a = any("Workout A" in wt for wt in prev_gym_types)
        prev_had_b = any("Workout B" in wt for wt in prev_gym_types)

        missed_sessions: List[str] = []
        run_order = ["zone2", "interval"]
        gym_order = ["gym_a", "gym_b"]
        run_priority_reason: Optional[str] = None
        gym_priority_reason: Optional[str] = None

        if len(prev_runs_sorted) == 1:
            if prev_had_zone2 and not prev_had_interval:
                missed_sessions.append("5K Hız İntervali")
                run_order = ["interval", "zone2"]
                run_priority_reason = "Geçen hafta eksik kalan 5K Hız İntervali bu hafta ilk koşu önceliğine alındı."
            elif prev_had_interval and not prev_had_zone2:
                missed_sessions.append("Zone 2 Koşu")
                run_order = ["zone2", "interval"]
                run_priority_reason = "Geçen hafta eksik kalan Zone 2 Koşu bu hafta ilk koşu önceliğine alındı."
            else:
                missed_sessions.append("2. Koşu seansı")
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

        day_acts: List[List[Dict[str, Any]]] = []
        runs_done_list: List[Dict[str, Any]] = []
        gyms_done_list: List[Dict[str, Any]] = []
        runs_completed_items: List[Dict[str, Any]] = []
        gyms_completed_items: List[Dict[str, Any]] = []
        spontaneous_items: List[Dict[str, Any]] = []
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
                    runs_done_list.append(act)
                    dist_km = round(dist_m / 1000.0, 2) if dist_m > 0 else 0.0
                    dist_txt = f"{dist_km:.2f} km · " if dist_km > 0 else ""
                    runs_completed_items.append({
                        "date": d_str,
                        "day_label": day_short,
                        "title": act_name,
                        "distance_km": dist_km,
                        "duration_min": dur_m,
                        "avg_hr": avg_hr,
                        "calories": cal,
                        "label": f"{day_short} · {act_name} ({dist_txt}{dur_m} dk{hr_txt})",
                    })
                elif bucket == "strength":
                    gyms_done_list.append(act)
                    w_type = gym_type_by_date.get(d_str) or "Kuvvet"
                    last_gym_type = w_type if w_type != "Kuvvet" else last_gym_type
                    gyms_completed_items.append({
                        "date": d_str,
                        "day_label": day_short,
                        "workout_type": w_type,
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

        needed_runs: List[Tuple[str, int]] = []
        if rem_runs == 2:
            r_ord = carryover["run_order"]
            needed_runs = [(r_ord[0], 1), (r_ord[1], 2)]
        elif rem_runs == 1:
            done_hr = runs_done_list[0].get("averageHR") or 0
            next_kind = "zone2" if done_hr >= 152 else "interval"
            needed_runs = [(next_kind, runs_done + 1)]

        needed_gyms: List[Tuple[str, int]] = []
        if rem_gyms == 2:
            g_ord = carryover["gym_order"]
            needed_gyms = [(g_ord[0], 1), (g_ord[1], 2)]
        elif rem_gyms == 1:
            next_gym = "gym_a" if last_gym_type and "Workout B" in last_gym_type else "gym_b"
            needed_gyms = [(next_gym, gyms_done + 1)]

        needed_queue: List[Tuple[str, int]] = []
        for idx in range(max(len(needed_runs), len(needed_gyms))):
            if idx < len(needed_runs):
                needed_queue.append(needed_runs[idx])
            if idx < len(needed_gyms):
                needed_queue.append(needed_gyms[idx])

        open_offsets = [i for i in range(7) if not day_acts[i] and week_dates[i].date() >= now.date()]
        assigned_slot: Dict[int, Tuple[str, int]] = {}

        if rem_runs == 2 and rem_gyms == 2 and not carryover["missed_sessions"] and {1, 2, 4, 5}.issubset(open_offsets):
            assigned_slot = {
                1: needed_gyms[0],
                2: needed_runs[0],
                4: needed_runs[1],
                5: needed_gyms[1],
            }
        elif needed_queue:
            occupied = {i for i in range(7) if day_acts[i]}
            remaining = list(needed_queue)
            for i in open_offsets:
                if not remaining:
                    break
                if (i - 1) not in occupied and (i + 1) not in occupied:
                    assigned_slot[i] = remaining.pop(0)
                    occupied.add(i)
            for i in open_offsets:
                if not remaining:
                    break
                if i not in assigned_slot and (i - 1) not in occupied:
                    assigned_slot[i] = remaining.pop(0)
                    occupied.add(i)
            for i in open_offsets:
                if not remaining:
                    break
                if i not in assigned_slot:
                    assigned_slot[i] = remaining.pop(0)

        def _format_completed_day(matched: List[Dict[str, Any]], d_str: str, run_c: List[int], gym_c: List[int]) -> Dict[str, str]:
            titles, details, hr_notes = [], [], []
            has_run = False
            has_gym = False
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
                    dist_txt = f" ({dist_m / 1000.0:.2f} km)" if dist_m > 0 else ""
                    titles.append(f"Koşu #{run_c[0]} • {act_name}{dist_txt}")
                elif bucket == "strength":
                    has_gym = True
                    gym_c[0] += 1
                    w_type = gym_type_by_date.get(d_str) or "Kuvvet"
                    titles.append(f"Kuvvet #{gym_c[0]} • {w_type} (5x5)")
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
            }

        def _build_planned_slot(slot_kind: str, ordinal: int) -> Dict[str, str]:
            is_last_run = (rem_runs == 1 and runs_done == 1)
            is_last_gym = (rem_gyms == 1 and gyms_done == 1)
            prio_hint = ""
            if slot_kind == carryover["run_order"][0] and carryover["run_priority_reason"] and ordinal == 1:
                prio_hint = " (Öncelikli)"
            elif slot_kind == carryover["gym_order"][0] and carryover["gym_priority_reason"] and ordinal == 1:
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
            return {
                "primary": f"Koşu #{ordinal} · Kalan Kota{prio_hint} · 5K Hız İntervali (45 dk, 4x1.000m)",
                "secondary": f"Esnek Gün — Bu hafta geriye {rem_runs} koşu kaldı ({quota_lbl}), taze bacaklarla uygun günde uygula • 5:15 /km tempo, 3 dk jog",
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
                    day_label = f"{base_day} (Bugün · Esnek Öneri)"
                elif is_tomorrow:
                    day_label = f"{base_day} (Yarın · Esnek Pencere)"
                else:
                    day_label = f"{base_day} (Önerilen Esnek Pencere)"
                row_data = _build_planned_slot(slot_kind, ordinal)
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
        """Pazartesi sıfırlamalı esnek haftalık kota özetini ve geçen hafta adaptasyonunu döner."""
        _, week_meta = self._build_weekly_schedule_entries(now=now)
        runs_done = week_meta["runs_done"]
        gyms_done = week_meta["gyms_done"]
        rem_runs = week_meta["rem_runs"]
        rem_gyms = week_meta["rem_gyms"]
        carry = week_meta["carryover"]

        rem_run_items = [
            self._build_quota_remaining_item(
                kind,
                ordinal,
                carry["run_priority_reason"] if (idx == 0 and kind == carry["run_order"][0]) else None,
            )
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
            "flexibility_note": (
                "Sabit gün zorunluluğu yok — Pazartesi kota 0/2 temiz sıfırlanır; geçen haftadan eksik kalan türler bu hafta öne çekilir."
            ),
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
        }
