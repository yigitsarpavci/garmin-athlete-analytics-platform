#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Branş Rehberliği, Salon Set Tarihçesi, Bilinmeyen/Preset Dışı Sporlar ve Seans Reçeteleri Mixin'i.
Tüm egzersiz hedefleri ve branş istatistikleri canlı Garmin telemetrisinden dinamik hesaplanır.
"""

import json
import os
from typing import Dict, List, Any

try:
    from athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
    from engine.helpers import DATA_DIR, fmt_pace_sec, format_sport_tr, classify_sport_bucket
except ImportError:
    from app.athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
    from app.engine.helpers import DATA_DIR, fmt_pace_sec, format_sport_tr, classify_sport_bucket


_EXERCISE_NAME_MAP = {
    "SQUAT": "Back Squat",
    "BENCH_PRESS": "Bench Press",
    "ROW": "Barbell Row",
    "SHOULDER_PRESS": "Overhead Press (OHP)",
    "DEADLIFT": "Barbell Deadlift",
    "PULL_UP": "Lat Pulldown",
    "LATERAL_RAISE": "Lateral Raise (Yana Açış)",
    "SHRUG": "Dumbbell Shrug",
}

_PROGRESSION_SPECS = [
    ("squat", "Back Squat", "Back Squat", 2.5, "x 5 reps x 5 set", 67.5),
    ("bench", "Bench Press", "Bench Press", 2.5, "x 5 reps x 5 set", 52.5),
    ("row", "Barbell Row", "Barbell Row", 2.5, "x 5 reps x 5 set", 62.5),
    ("ohp", "Overhead Press (OHP)", "Overhead Press (OHP)", 2.5, "x 5 reps x 5 set", 40.0),
    ("deadlift", "Barbell Deadlift", "Barbell Deadlift", 5.0, "x 5 reps (1 ana set)", 65.0),
    ("lat_pulldown", "Lat Pulldown", "Lat Pulldown", 2.5, "x 12 reps x 4 set", 47.5),
    ("lateral_raise", "Lateral Raise", "Lateral Raise (Yana Açış)", 2.5, "x 12 reps x 3 set", 25.0),
    ("shrug", "Dumbbell Shrug", "Dumbbell Shrug", 2.5, "x 12 reps x 3 set", 45.0),
]

_DEFAULT_PROGRESSION = {
    "squat": {"name": "Back Squat", "history": ["45.0 kg", "65.0 kg (5x5)"], "delta": "+20.0 kg", "max_kg": 65.0, "last_date": "17 Kas", "next_kg": 67.5, "next_target": "67.5 kg x 5 reps x 5 set"},
    "bench": {"name": "Bench Press", "history": ["45.0 kg", "50.0 kg (5x5)"], "delta": "+5.0 kg", "max_kg": 50.0, "last_date": "17 Kas", "next_kg": 52.5, "next_target": "52.5 kg x 5 reps x 5 set"},
    "row": {"name": "Barbell Row", "history": ["45.0 kg", "60.0 kg (5x5)"], "delta": "+15.0 kg", "max_kg": 60.0, "last_date": "17 Kas", "next_kg": 62.5, "next_target": "62.5 kg x 5 reps x 5 set"},
    "ohp": {"name": "Overhead Press (OHP)", "history": ["35.0 kg", "40.0 kg"], "delta": "+5.0 kg", "max_kg": 40.0, "last_date": "12 Kas", "next_kg": 40.0, "next_target": "40.0 kg x 5 reps x 5 set"},
    "deadlift": {"name": "Barbell Deadlift", "history": ["50.0 kg", "60.0 kg x 5"], "delta": "+10.0 kg", "max_kg": 60.0, "last_date": "12 Kas", "next_kg": 65.0, "next_target": "65.0 kg x 5 reps (1 ana set)"},
    "lat_pulldown": {"name": "Lat Pulldown", "history": ["40.0 kg", "45.0 kg x 12"], "delta": "+5.0 kg", "max_kg": 45.0, "last_date": "12 Kas", "next_kg": 47.5, "next_target": "47.5 kg x 12 reps x 4 set"},
    "lateral_raise": {"name": "Lateral Raise", "history": ["20.0 kg", "25.0 kg x 12"], "delta": "Stabil Güç", "max_kg": 25.0, "last_date": "17 Kas", "next_kg": 25.0, "next_target": "25.0 kg x 12 reps x 3 set"},
    "shrug": {"name": "Dumbbell Shrug", "history": ["35.0 kg", "45.0 kg x 12"], "delta": "Stabil 45 kg", "max_kg": 45.0, "last_date": "17 Kas", "next_kg": 45.0, "next_target": "45.0 kg x 12 reps x 3 set"},
}


class WorkoutProtocolsMixin:
    """Salon ağırlık geçmişi, branş rehberliği, bilinmeyen spor desteği ve seans reçeteleri."""

    def get_gym_exercise_history(self) -> Dict[str, Any]:
        """Garmin kuvvet seanslarının tüm set, tekrar ve dinamik progression hedeflerini döner."""
        gym_file = os.path.join(self.data_dir if hasattr(self, "data_dir") else DATA_DIR, "raw_gym_exercise_sets.json")
        if not os.path.exists(gym_file):
            return {"sessions": [], "progression": dict(_DEFAULT_PROGRESSION)}

        try:
            with open(gym_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception:
            return {"sessions": [], "progression": dict(_DEFAULT_PROGRESSION)}

        act_meta_map = {}
        for a in self.activities_all:
            aid = str(a.get("activityId"))
            act_meta_map[aid] = {
                "date": (a.get("startTimeLocal") or "")[:10],
                "time": (a.get("startTimeLocal") or "")[11:16],
                "duration_min": round((a.get("duration") or 0) / 60.0, 1),
                "calories": a.get("calories"),
                "avg_hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"),
                "aerobic_te": a.get("aerobicTrainingEffect"),
                "anaerobic_te": a.get("anaerobicTrainingEffect"),
            }

        sessions: List[Dict[str, Any]] = []
        for act_id, info in raw_data.items():
            meta = act_meta_map.get(str(act_id), {})
            sets = info.get("sets", [])

            grouped_ex: List[Dict[str, Any]] = []
            last_name = None
            curr_sets: List[Dict[str, Any]] = []
            total_vol = 0.0
            cat_set = set()

            for s in sets:
                if s.get("setType") == "ACTIVE":
                    ex_list = s.get("exercises") or []
                    cat = ex_list[0].get("category") if ex_list else "UNKNOWN"
                    cat_set.add(cat)
                    display_name = _EXERCISE_NAME_MAP.get(cat, cat.replace("_", " ").title())
                    w_kg = round((s.get("weight") or 0) / 1000.0, 1)
                    reps = s.get("repetitionCount") or 0
                    total_vol += (w_kg * reps)

                    if display_name != last_name:
                        if curr_sets:
                            grouped_ex.append({"name": last_name, "sets": curr_sets})
                        curr_sets = [{"reps": reps, "weight_kg": w_kg}]
                        last_name = display_name
                    else:
                        curr_sets.append({"reps": reps, "weight_kg": w_kg})
            if curr_sets:
                grouped_ex.append({"name": last_name, "sets": curr_sets})

            # Yeni gelecek Garmin seanslarını da egzersiz içeriğine göre otomatik A/B sınıfla
            is_b = (
                bool(cat_set.intersection({"SHOULDER_PRESS", "DEADLIFT", "PULL_UP"}))
                or str(act_id) in ("25005174809", "25051460770")
            )
            workout_type = "Workout B" if is_b else "Workout A"

            sessions.append({
                "activity_id": act_id,
                "date": meta.get("date", ""),
                "time": meta.get("time", ""),
                "workout_type": workout_type,
                "duration_min": meta.get("duration_min", 55),
                "calories": meta.get("calories", 370),
                "avg_hr": meta.get("avg_hr"),
                "total_volume_kg": round(total_vol, 1),
                "exercises": grouped_ex,
            })

        sessions.sort(key=lambda x: x["date"], reverse=True)

        # Tüm hareket geçmişinden dinamik PR ve sonraki kilo artışlarını çıkar
        progression: Dict[str, Any] = {}
        chrono_sessions = sorted(sessions, key=lambda x: x["date"])
        for key, label, match_name, step_kg, rep_suffix, fallback_next in _PROGRESSION_SPECS:
            points: List[tuple] = []
            for sess in chrono_sessions:
                max_w = 0.0
                for ex in sess.get("exercises", []):
                    if ex.get("name") == match_name:
                        for st in ex.get("sets", []):
                            max_w = max(max_w, float(st.get("weight_kg") or 0.0))
                if max_w > 0:
                    d_lbl = sess.get("date", "")[5:]
                    points.append((d_lbl, max_w))

            if points:
                first_w = points[0][1]
                last_date, last_w = points[-1]
                diff = round(last_w - first_w, 1)
                history_strs = [f"{w:.1f} kg ({d})" for d, w in points[-5:]]
                delta_str = f"+{diff:.1f} kg ({len(points)} seans)" if diff > 0 else f"Stabil {last_w:.1f} kg"
                next_kg = round(last_w + step_kg, 1) if key not in ("ohp", "lateral_raise", "shrug") or last_w < fallback_next else last_w
                progression[key] = {
                    "name": label,
                    "history": history_strs,
                    "delta": delta_str,
                    "max_kg": last_w,
                    "last_date": last_date,
                    "next_kg": next_kg,
                    "next_target": f"{next_kg:.1f} kg {rep_suffix}",
                }
            else:
                progression[key] = dict(_DEFAULT_PROGRESSION[key])

        return {"sessions": sessions, "progression": progression}

    def _build_dynamic_extra_sport_card(self, sport_key: str, rows_df) -> Dict[str, Any]:
        """Kayak, yüzme, bisiklet veya Garmin'den gelebilecek herhangi yeni spor için hazır rehber üretir."""
        label = format_sport_tr(sport_key, sport_key)
        cnt = int(len(rows_df))
        tot_h = round(float(rows_df["dur_m"].sum()) / 60.0, 1)
        tot_kcal = int(round(float(rows_df["cal"].sum())))
        avg_hr = int(round(float(rows_df["avg_hr"].replace(0, float("nan")).mean()))) if rows_df["avg_hr"].replace(0, float("nan")).notna().any() else 0
        tot_load = round(float(rows_df["load"].sum()), 1)

        low = sport_key.lower()
        if "ski" in low or "snow" in low or "winter" in low:
            goal = "Yüksek rakımda eksantrik kuadriseps dayanıklılığı ve soğuk havada hidrasyon/glikojen korunumu"
            tips = [
                "Eksantrik Kuadriseps Yükü: Kayak inişleri yoğun eksantrik bacak gerilimi yaratır; dönüş gününde ağır Squat yerine hafif mobilite/yürüyüş seçin.",
                "Soğuk & İrtifa Sıvı Kaybı: Kuru soğuk havada susama hissi baskılanır; saat başı 400-500 mL sıvı ve sodyum alımını sürdürün.",
                "Anaerobik & Yüksek Aerobik Katkısı: Kayak sprint inişleri haftalık kotadan yer çalmayan ekstra yük üretir; ertesi gün ACWR ve HRV puanını izleyin.",
            ]
            upcoming = {"day": "Spontane Kış Branşı", "type": f"{label} Seansı", "title": f"{label} Pist / İrtifa Günü", "duration": "2 - 5 saat", "details": "Saat başı sıvı + kompleks karbonhidrat desteği; seans sonrası 10 dk kalça fleksör ve kuadriseps esnemesi."}
        elif "swim" in low:
            goal = "Sıfır eklem darbesiyle üst vücut/lat dayanıklılığı ve aktif kardiyovasküler toparlanma"
            tips = [
                "Aktif Toparlanma Sinergisi: Koşu ve Squat sonrası eklem yükünü sıfırlayarak kan akışını hızlandırır.",
                "Omuz & Sırt Dengesi: Lat Pulldown ve OHP ile birlikte omuz kuşağı hareket açıklığını korur.",
            ]
            upcoming = {"day": "Spontane Su Branşı", "type": label, "title": f"{label} Seansı", "duration": "30 - 50 dk", "details": "Rahat ritimde sürekli aerobik yüzme; ekstra bacak yorgunluğu oluşturmaz."}
        elif "cycl" in low or "bik" in low:
            goal = "Düşük darbeli Zone 2 aerobik kapasite artışı ve kuadriseps oksidatif verimliliği"
            tips = [
                "Yüksek Kadans Koruyun (85-95 rpm): Düşük viteste yüksek devir bacakları ağırlaştırmadan kalp atım hacmini geliştirir.",
                "ACWR Takibi: Uzun sürüşler sonrası haftalık yük artışına göre koşu temposunu esnek ayarlayın.",
            ]
            upcoming = {"day": "Spontane Dayanıklılık", "type": label, "title": f"{label} Aerobik Sürüş", "duration": "45 - 90 dk", "details": "Zone 2 nabız koridorunu koruyarak eklemlere darbe bindirmeden aerobik hacim ekler."}
        else:
            goal = f"{label} aktivitelerini Garmin sensörlerinden otomatik algılayarak haftalık ACWR yük dengesine entegre etmek"
            tips = [
                f"Otomatik Algılama Hazır: {label} Garmin'den yüklendiğinde kota dengesini bozmadan Spontane Branşlar ve Antrenman Yükü analizine dahil edilir.",
                "Ertesi Gün Toparlanma Kuralı: Yüksek EPOC veya bacak yorgunluğu oluşturan seanslar sonrasında kalan haftalık kotadaki yoğun günü ileri kaydırın.",
            ]
            upcoming = {"day": "Spontane Branş", "type": label, "title": f"{label} Seansı", "duration": "Değişken", "details": f"Garmin saat üzerinden kaydedildiğinde kalp atımı, kalori ve yük puanı ({tot_load} toplam) otomatik işlenir."}

        return {
            "name": label,
            "sport_key": sport_key,
            "is_dynamic_extra": True,
            "schedule_status": "Spontane / Otomatik Algılanan Branş (Garmin Hazır)",
            "current_status": f"{cnt} seans ({tot_h} saat · {tot_load} yük · {avg_hr} bpm ort.)",
            "goal": goal,
            "stats_summary": f"{cnt} Seans • {tot_h} Saat • {tot_load} Yük • {tot_kcal} kcal (Kotadan düşmez; saat yükledikçe otomatik analiz edilir)",
            "how_to_improve": tips,
            "upcoming_sessions": [upcoming],
        }

    def get_sports_guidance(self) -> Dict[str, Any]:
        """Koşu, Kuvvet, Yelken, Basketbol ve Garmin'den gelen tüm preset dışı sporlar için dinamik rehberlik döner."""
        weekly_quota = self.get_weekly_quota_summary()
        runs_done = weekly_quota["running"]["completed"]
        rem_runs = weekly_quota["running"]["remaining"]
        gyms_done = weekly_quota["strength"]["completed"]
        rem_gyms = weekly_quota["strength"]["remaining"]
        metrics = self.get_latest_metrics() if hasattr(self, "get_latest_metrics") else {}
        cur_w = metrics.get("weight", 87.0)
        prog = self.get_gym_exercise_history().get("progression", {})

        # Canlı koşu istatistikleri
        run_cnt, run_km, run_hr, latest_cadence, latest_ef = 15, 79.5, 158, 162, 1.03
        if hasattr(self, "adf") and not self.adf.empty:
            r_df = self.adf_3m[self.adf_3m["sport"].str.contains("running", case=False, na=False)]
            if not r_df.empty:
                run_cnt = int(len(r_df))
                run_km = round(float(r_df["dist_km"].sum()), 1)
                valid_hr = r_df["avg_hr"].replace(0, float("nan")).dropna()
                if not valid_hr.empty:
                    run_hr = int(round(float(valid_hr.mean())))
                valid_cad = r_df["cadence"].dropna()
                if not valid_cad.empty:
                    latest_cadence = int(round(float(valid_cad.iloc[0])))
                valid_ef = r_df["ef_spd"].dropna()
                if not valid_ef.empty:
                    latest_ef = round(float(valid_ef.iloc[0]), 2)

        # Canlı kuvvet istatistikleri
        gym_cnt, gym_hours, gym_kcal = 5, 4.7, 1851
        if hasattr(self, "adf") and not self.adf.empty:
            g_df = self.adf_3m[self.adf_3m["sport"].str.contains("strength|fitness_equipment", case=False, na=False)]
            if not g_df.empty:
                gym_cnt = int(len(g_df))
                gym_hours = round(float(g_df["dur_m"].sum()) / 60.0, 1)
                gym_kcal = int(round(float(g_df["cal"].sum())))

        # Canlı yelken & basketbol istatistikleri
        sail_cnt, sail_hours, sail_km, sail_kcal, sail_water_l = 12, 28.1, 259.8, 8561, 16.6
        bask_cnt, bask_hours, bask_hr_min, bask_hr_max = 5, 6.5, 128, 144
        if hasattr(self, "adf_3m") and not self.adf_3m.empty:
            s_df = self.adf_3m[self.adf_3m["sport"].str.contains("sailing", case=False, na=False)]
            if not s_df.empty:
                sail_cnt = int(len(s_df))
                sail_hours = round(float(s_df["dur_m"].sum()) / 60.0, 1)
                sail_km = round(float(s_df["dist_km"].sum()), 1)
                sail_kcal = int(round(float(s_df["cal"].sum())))
                sail_water_l = round(float(s_df["water_ml"].sum()) / 1000.0, 1)
            b_df = self.adf_3m[self.adf_3m["sport"].str.contains("basketball", case=False, na=False)]
            if not b_df.empty:
                bask_cnt = int(len(b_df))
                bask_hours = round(float(b_df["dur_m"].sum()) / 60.0, 1)
                b_hrs = b_df["avg_hr"].replace(0, float("nan")).dropna()
                if not b_hrs.empty:
                    bask_hr_min = int(round(float(b_hrs.min())))
                    bask_hr_max = int(round(float(b_hrs.max())))

        running_upcoming: List[Dict[str, str]] = [
            {
                "day": "Bu Hafta Kalan Kota (Esnek Gün)" + (" · Öncelikli" if item.get("is_prioritized") else ""),
                "type": item["type"],
                "title": item["title"],
                "duration": item["duration"],
                "target_hr": item["target_hr"],
                "target_pace": item["target_pace"],
                "details": item["coaching_note"],
            }
            for item in weekly_quota["running"]["remaining_items"]
        ]
        if len(running_upcoming) < 2:
            fallback_kind = "zone2" if (running_upcoming and "İnterval" in running_upcoming[0].get("type", "")) else "interval"
            tpl_item = self._build_quota_remaining_item(fallback_kind, 1)
            running_upcoming.append({
                "day": "Kota Tamamlandıktan Sonra (Yeni Döngü)",
                "type": f"{tpl_item['type']} (Yeni Döngü)",
                "title": tpl_item["title"],
                "duration": tpl_item["duration"],
                "target_hr": tpl_item["target_hr"],
                "target_pace": tpl_item["target_pace"],
                "details": f"Bu haftanın 2/2 koşu kotası tamamlandıktan sonraki döngü seçeneği: {tpl_item['coaching_note']}",
            })

        gym_upcoming: List[Dict[str, str]] = [
            {
                "day": "Bu Hafta Kalan Kota (Esnek Gün)" + (" · Öncelikli" if item.get("is_prioritized") else ""),
                "type": f"{item['type']} (Bu Hafta Kalan Kota)",
                "title": item["title"],
                "duration": item["duration"],
                "details": item["exercises_summary"],
            }
            for item in weekly_quota["strength"]["remaining_items"]
        ]
        if len(gym_upcoming) < 2:
            next_cycle_kind = "gym_b" if (gym_upcoming and "Workout A" in gym_upcoming[0]["type"]) else "gym_a"
            tpl_item = self._build_quota_remaining_item(next_cycle_kind, 1)
            gym_upcoming.append({
                "day": "Kota Tamamlandıktan Sonra (Yeni Döngü)",
                "type": f"{tpl_item['type']} (Yeni Döngü)",
                "title": tpl_item["title"],
                "duration": tpl_item["duration"],
                "details": tpl_item["exercises_summary"],
            })

        gym_sessions = self.get_gym_exercise_history().get("sessions", [])
        if gym_sessions:
            latest_gym = gym_sessions[0]
            date_str = latest_gym.get("date", "")
            time_str = latest_gym.get("time", "")
            last_workout = {
                "date": f"{date_str} ({time_str})" if time_str else date_str,
                "title": f"{latest_gym.get('workout_type', 'Workout A')} (TAMAMLANDI)",
                "exercises": [
                    f"{ex['name']}: " + ", ".join(f"{s['weight_kg']}kg x {s['reps']}" for s in ex.get("sets", [])[-2:])
                    for ex in latest_gym.get("exercises", [])
                ],
            }
        else:
            last_workout = {
                "date": "Son Kuvvet Seansı",
                "title": "Workout A (TAMAMLANDI)",
                "exercises": ["Back Squat: 65.0 kg x 5x5", "Bench Press: 50.0 kg x 5x5", "Barbell Row: 60.0 kg x 5x5"],
            }

        sq_t = prog.get("squat", {}).get("next_target", "67.5 kg x 5x5")
        ohp_t = prog.get("ohp", {}).get("next_target", "40.0 kg x 5x5")
        dl_t = prog.get("deadlift", {}).get("next_target", "65.0 kg x 5")
        lat_t = prog.get("lat_pulldown", {}).get("next_target", "47.5 kg x 12")
        lr_t = prog.get("lateral_raise", {}).get("next_target", "25.0 kg x 12")
        sh_t = prog.get("shrug", {}).get("next_target", "45.0 kg x 12")

        sq_pr = prog.get("squat", {}).get("max_kg", 65.0)
        bp_pr = prog.get("bench", {}).get("max_kg", 50.0)
        rw_pr = prog.get("row", {}).get("max_kg", 60.0)

        # Bilinmeyen / Preset dışı sporları otomatik tara (Kayak, Yüzme, Bisiklet vb.)
        extra_sports: List[Dict[str, Any]] = []
        known_core = {"running", "strength_training", "sailing_v2", "sailing", "basketball"}
        if hasattr(self, "adf_3m") and not self.adf_3m.empty:
            for sp_key, grp in self.adf_3m.groupby("sport"):
                if str(sp_key).lower() not in known_core:
                    extra_sports.append(self._build_dynamic_extra_sport_card(str(sp_key), grp))

        run_sched_status = (
            f"Esnek Haftalık Kota (Bu Hafta: {runs_done}/2 Tamamlandı · Kota Doldu)"
            if rem_runs == 0 else f"Esnek Haftalık Kota (Bu Hafta: {runs_done}/2 Yapıldı · Kalan: {rem_runs})"
        )
        gym_sched_status = (
            f"Esnek Haftalık Kota (A/B 5x5 • Bu Hafta: {gyms_done}/2 Tamamlandı · Kota Doldu)"
            if rem_gyms == 0 else f"Esnek Haftalık Kota (A/B 5x5 • Bu Hafta: {gyms_done}/2 Yapıldı · Kalan: {rem_gyms})"
        )

        return {
            "weekly_quota": weekly_quota,
            "extra_sports": extra_sports,
            "running": {
                "name": "Koşu (Running)",
                "schedule_status": run_sched_status,
                "current_pace": metrics.get("latest_5k", "5:48 /km"),
                "target_pace": "4:54 /km (5K: <24:30)",
                "efficiency_factor": latest_ef,
                "cadence": f"{latest_cadence} spm (Harika Form ve Düşük Darbe)",
                "stats_summary": f"{run_cnt} Koşu • {run_km} km Mesafe • {run_hr} bpm Ortalama Nabız",
                "how_to_improve": [
                    "80/20 Polarize Model: Haftalık 2 koşu kotasının 1'ini Zone 2 (140-150 bpm, konuşma temposu), 1'ini hız intervali (Anaerobik eksik kapatıcı) olarak uygulayın.",
                    "Laktat Eşiği İntervali: 4x1.000m @ 5:15 /km (172-180 bpm) ile yüksek hız toleransını ve anaerobik yük barını yukarı taşıyın.",
                    f"{latest_cadence} spm Kadans Kontrolü: Kısa, elastik adımlarla diz/eklem darbesini minimumda tutun.",
                    f"Kilo Adaptasyonu ({cur_w:.1f} -> 81.0 kg): Her -1 kg hafifleme 5K süresini ~14 sn hızlandırır.",
                ],
                "upcoming_sessions": running_upcoming,
                "next_workout": running_upcoming[0],
            },
            "strength": {
                "name": "Kuvvet Antrenmanı (Strength)",
                "schedule_status": gym_sched_status,
                "current_status": f"A/B Bölünmüş Rutin ({gym_cnt} seans tamamlandı)",
                "goal": "Yağ yakımı döneminde kas kütlesini ve omurga/omuz gücünü korumak (Progressive Overload)",
                "stats_summary": f"{gym_cnt} Seans • {gym_hours} Saat • {gym_kcal:,} kcal • Squat: {sq_pr:.0f}kg • Bench: {bp_pr:.0f}kg • Row: {rw_pr:.0f}kg",
                "how_to_improve": [
                    "Bileşik 5x5 Odaklanması: Workout A ve B ile tüm büyük kas gruplarında mekanik gerilim sağlar.",
                    "Lineer Progressive Overload: Temiz tamamlanan her 5x5 sonrası üst vücuda +2.5 kg, bacağa +2.5–5.0 kg ekleyin.",
                    "Aynı Gün Sıralama Kuralı: Koşu ile aynı gün yapılacaksa ÖNCE KOŞU, SONRA KUVVET veya araya ≥6 saat koyun.",
                ],
                "last_workout": last_workout,
                "upcoming_sessions": gym_upcoming,
                "next_workout": {
                    "day": gym_upcoming[0]["day"],
                    "title": gym_upcoming[0]["title"],
                    "duration": gym_upcoming[0]["duration"],
                    "exercises": [sq_t, ohp_t, dl_t, lat_t, lr_t, sh_t],
                },
            },
            "sailing": {
                "name": "Yelken (Sailing)",
                "schedule_status": "Spontane / Dönemsel Branş (Garmin Otomatik Algılama)",
                "current_status": f"Son dönemde {sail_cnt} seans ({sail_hours} saat, {sail_km} km, {sail_kcal:,} kcal)",
                "goal": "Uzun deniz seanslarında core/önkol dayanıklılığı ve sıvı-elektrolit dengesi",
                "stats_summary": f"{sail_cnt} Seans • {sail_km} km • {sail_water_l} L Tahmini Ter Kaybı (Kotadan yer tutmaz; saatten otomatik işlenir)",
                "how_to_improve": [
                    "İzometrik Tutuş Gücü: Farmer's Walk ve Dead Hang halat çekişi yorgunluğunu önler.",
                    f"Sıvı & Elektrolit Protokolü: {sail_water_l} L toplam ter kaybı gözlendi; saat başı 500-600 mL su + sodyum tüketin.",
                    "Glikojen Ön-Yüklemesi: 3 saat üzeri seanslardan 90 dk önce 70-80g kompleks karbonhidrat alın.",
                ],
                "upcoming_sessions": [
                    {
                        "day": "Spontane Seans (Çıktıkça İşlenir)",
                        "type": "Yelken Seansı (İsteğe Bağlı)",
                        "title": "Rüzgar & Kondisyon Seansı",
                        "duration": "2,5 - 4 saat",
                        "details": "Teknede 2 x 750 mL matara (su + 500-800 mg sodyum). Saat başı düzenli yudumlayın.",
                    }
                ],
                "next_workout": {
                    "day": "İsteğe Bağlı / Çıktıkça",
                    "title": "Uzun Yelken Antrenmanı",
                    "duration": "2,5 - 4 saat",
                    "hydration_plan": "2 x 750 mL elektrolitli su.",
                },
            },
            "basketball": {
                "name": "Basketbol",
                "schedule_status": "Spontane / Dönemsel Branş (Garmin Otomatik Algılama)",
                "current_status": f"{bask_cnt} maç • {bask_hours} saat • Ort. nabız {bask_hr_min}-{bask_hr_max} bpm",
                "goal": "Patlayıcı hızlanma, yön değiştirme ve anaerobik dayanıklılık",
                "stats_summary": f"{bask_cnt} Maç • {bask_hours} Saat • Zone 4-5 Doğal HIIT (Saatten otomatik algılanır)",
                "how_to_improve": [
                    "Doğal HIIT Katkısı: Anaerobik güç eksiğini kapatmaya doğal destek sağlar.",
                    "Yük Çakışması Kuralı: Maç günü ağır bacak (Squat/Deadlift) yerine üst vücut veya dinlenme tercih edin.",
                    "Maç Öncesi & Sonrası: 10 dk dinamik ayak bileği ısınması + 10 dk statik hamstring esnemesi.",
                ],
                "upcoming_sessions": [
                    {
                        "day": "Spontane Maç (Çıktıkça İşlenir)",
                        "type": "Haftalık Maç (İsteğe Bağlı)",
                        "title": "Basketbol Maçı",
                        "duration": "60 - 90 dk",
                        "details": "Maç öncesi 10 dk dinamik bacak ısınması; maç sonrası 10 dk esneme.",
                    }
                ],
                "next_workout": {
                    "day": "İsteğe Bağlı / Çıktıkça",
                    "title": "Basketbol Maçı",
                    "duration": "60 - 90 dk",
                    "target_hr": "Z2 - Z4 arası değişken",
                },
            },
        }

    def get_detailed_daily_workout_protocols(self) -> List[Dict[str, Any]]:
        """Canlı gym PR hedeflerine, kiloya ve haftalık kota durumuna bağlı 7 seans/şablon reçetesi döner."""
        quota = self.get_weekly_quota_summary()
        runs_done = quota["running"]["completed"]
        rem_runs = quota["running"]["remaining"]
        gyms_done = quota["strength"]["completed"]
        rem_gyms = quota["strength"]["remaining"]
        total_done = quota["total"]["completed"]
        total_rem = quota["total"]["remaining"]
        rem_run_kinds = {i["slot_kind"] for i in quota["running"]["remaining_items"]}
        rem_gym_kinds = {i["slot_kind"] for i in quota["strength"]["remaining_items"]}

        prog = self.get_gym_exercise_history().get("progression", {})
        sq = prog.get("squat", {})
        bp = prog.get("bench", {})
        rw = prog.get("row", {})
        ohp = prog.get("ohp", {})
        dl = prog.get("deadlift", {})
        lat = prog.get("lat_pulldown", {})
        lr = prog.get("lateral_raise", {})
        sh = prog.get("shrug", {})

        metrics = self.get_latest_metrics() if hasattr(self, "get_latest_metrics") else {}
        cur_w = float(metrics.get("weight", 87.0))
        prot_g = round(cur_w * 2.0)

        def _quota_note(is_remaining: bool, done_count: int, rem_count: int, label_tr: str, next_hint: str) -> str:
            if is_remaining:
                return f"Bu Hafta Kalan Kota ({done_count}/2 {label_tr} Yapıldı, {rem_count} Kaldı) • {next_hint}"
            return f"Bu Haftaki İhtiyaç Tamamlandı ({done_count}/2 {label_tr}) • Bir Sonraki Döngü İçin Şablon"

        return [
            {
                "day_code": "tuesday",
                "slot_label": "Workout A",
                "quota_status": "remaining" if "gym_a" in rem_gym_kinds else "completed",
                "day_title": "Kuvvet Reçetesi A: Workout A (Tüm Vücut Güç & Hipertrofi)",
                "category": "gym",
                "badge": "Workout A",
                "badge_color": "blue",
                "status_note": _quota_note("gym_a" in rem_gym_kinds, gyms_done, rem_gyms, "Kuvvet", "Uygun olduğun herhangi bir günde uygula"),
                "objective": "Nöromüsküler güç inşası, göğüs, bacak, sırt ve yan omuz gelişimi (Progressive Overload). Sabit gün zorunluluğu olmadan haftanın uygun gününe yerleştirilir.",
                "warmup": "5 dk dinamik kalça & omuz mobilitesi + Boş bar ile 2x10 Squat ve 2x10 Bench Press hafif ısınma setleri.",
                "exercises": [
                    {
                        "num": 1, "name": "Barbell Back Squat", "sets": 5, "reps": 5,
                        "current_achieved": f"{sq.get('max_kg', 65.0):.1f} kg ({sq.get('last_date', 'Son')})",
                        "target_weight": sq.get("next_target", "67.5 kg (+2.5 kg Artış)"),
                        "rest_sec": "150 - 180 sn", "target_rpe": "8.0",
                        "coaching_cue": "Paralel altı derinlik, göğüs dik, topuklardan dengeli zemin itişi.",
                    },
                    {
                        "num": 2, "name": "Barbell Bench Press", "sets": 5, "reps": 5,
                        "current_achieved": f"{bp.get('max_kg', 50.0):.1f} kg ({bp.get('last_date', 'Son')})",
                        "target_weight": bp.get("next_target", "52.5 kg (Yeni PR Denemesi)"),
                        "rest_sec": "120 - 150 sn", "target_rpe": "8.5",
                        "coaching_cue": "Kürek kemikleri geride kilitli, barı kontrollü göğüs ucuna indirip patlayıcı itiş.",
                    },
                    {
                        "num": 3, "name": "Barbell Bent-Over Row", "sets": 5, "reps": 5,
                        "current_achieved": f"{rw.get('max_kg', 60.0):.1f} kg ({rw.get('last_date', 'Son')})",
                        "target_weight": rw.get("next_target", "62.5 kg (+2.5 kg Artış)"),
                        "rest_sec": "120 - 150 sn", "target_rpe": "8.0",
                        "coaching_cue": "Gövde 45 derece eğik, bel nötr, barı alt karına çekip kürek kemiklerini sıkıştırın.",
                    },
                    {
                        "num": 4, "name": "Dumbbell Lateral Raise (Yan Açış)", "sets": 3, "reps": 12,
                        "current_achieved": f"{lr.get('max_kg', 25.0):.1f} kg ({lr.get('last_date', 'Son')})",
                        "target_weight": lr.get("next_target", "25.0 kg x 12"),
                        "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                        "coaching_cue": "Yan deltoid hipertrofisi ve V-Taper omuz genişliği için dirsekler hafif kırık, tepe noktada 1 sn bekleme.",
                    },
                    {
                        "num": 5, "name": "Dumbbell / Barbell Shrug (Trapez)", "sets": 3, "reps": 12,
                        "current_achieved": f"{sh.get('max_kg', 45.0):.1f} kg ({sh.get('last_date', 'Son')})",
                        "target_weight": sh.get("next_target", "45.0 kg x 12"),
                        "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                        "coaching_cue": "Trapez kalınlığı ve tutuş gücü; yelkende hiking ve deadlift kilitlenişini korur.",
                    },
                ],
                "cooldown": "5 dk hafif statik esneme (göğüs açış, kalça fleksör ve hamstring).",
                "telemetry_targets": {
                    "hr_range": "115 - 130 bpm (Zone 1)",
                    "est_calories": "~2.850 kcal toplam harcama",
                    "nutrition": f"2.450 kcal alım | {prot_g}g Protein | 250g Karbonhidrat | 80g Sağlıklı Yağ | 3.0 L Su",
                },
            },
            {
                "day_code": "wednesday",
                "slot_label": "Toparlanma",
                "quota_status": "optional",
                "day_title": "Rejenerasyon Şablonu: Tam Dinlenme & Kas Onarımı",
                "category": "rest",
                "badge": "Esnek Dinlenme",
                "badge_color": "slate",
                "status_note": f"Esnek Toparlanma Penceresi • Bu hafta {total_done}/4 seans tamamlandı, {total_rem} seans kaldı",
                "objective": "Arka arkaya yüklenen kasları onarmak ve kalan haftalık kota seanslarına yüksek hazırlıkla girmek.",
                "warmup": "Gerekli değil.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Rejenerasyon Protokolü",
                        "duration": "Tüm Gün Dinlenme",
                        "protocol": "10 dk Foam Roller masajı, kalça mobilitesi ve 20 dk hafif yürüyüş.",
                        "coaching_cue": f"Bu hafta {total_done}/4 planlı seans ({runs_done} Koşu + {gyms_done} Kuvvet) tamamlandı. Yorgunluk günlerinde bu şablonu seçin.",
                    }
                ],
                "cooldown": "00:30 öncesi uyku hazırlığı (8 saat tam toparlanma).",
                "telemetry_targets": {
                    "hr_range": "<100 bpm (Parasempatik Toparlanma)",
                    "est_calories": "~2.500 kcal toplam harcama",
                    "nutrition": f"2.350 kcal alım | {prot_g}g Protein | 220g Karbonhidrat | 80g Sağlıklı Yağ | 2.5 - 3.0 L Su",
                },
            },
            {
                "day_code": "thursday",
                "slot_label": "Zone 2",
                "quota_status": "remaining" if "zone2" in rem_run_kinds else "completed",
                "day_title": "Koşu Reçetesi #1: Zone 2 Aerobik Taban (45-50 dk)",
                "category": "running",
                "badge": "Zone 2 Taban",
                "badge_color": "emerald",
                "status_note": _quota_note("zone2" in rem_run_kinds, runs_done, rem_runs, "Koşu", "Bacakların taze olduğu herhangi bir günde uygula"),
                "objective": "Sol karıncık atım hacmini büyütmek ve aerobik tabanı nabız tavanını aşmadan korumak.",
                "warmup": "5-8 dk dinamik kalça ve ayak bileği mobilitesi.",
                "exercises": [
                    {
                        "num": 1, "name": "Ana Koşu: Zone 2 Taban Koşusu",
                        "duration": "45 - 50 dakika kesintisiz",
                        "distance_est": "6.8 - 7.5 km",
                        "target_hr": "140 - 150 bpm (Katı Tavan 150 bpm)",
                        "target_pace": "6:35 - 6:50 /km",
                        "cadence_target": "160 - 165 spm",
                        "ground_contact_time": "Hedef <275 ms",
                        "coaching_cue": "Burundan rahat konuşma temposu. Nabız 151 bpm olduğunda yürüyüşe düşüp indirin.",
                    }
                ],
                "cooldown": "8 dk baldır, aşil ve kuadriseps statik esnemesi.",
                "telemetry_targets": {
                    "hr_range": "140 - 150 bpm (Zone 2 Taban)",
                    "est_calories": "~2.950 kcal toplam harcama",
                    "nutrition": f"2.550 kcal alım | {prot_g}g Protein | 275g Karbonhidrat | 80g Yağ | 3.5 L Su",
                },
            },
            {
                "day_code": "friday",
                "slot_label": "Hazırlık",
                "quota_status": "optional",
                "day_title": "Rejenerasyon Şablonu: Hafif Mobilite & Kuvvet Öncesi Hazırlık",
                "category": "rest",
                "badge": "Esnek Hazırlık",
                "badge_color": "slate",
                "status_note": f"Esnek Ara Gün • Kalan Kota: {rem_runs} Koşu + {rem_gyms} Kuvvet",
                "objective": "Bacak ve merkezi sinir sistemini sıradaki seans için tazelemek.",
                "warmup": "Gerekli değil.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Hafif Mobilite & Uyku Hazırlığı",
                        "duration": "Tüm Gün Dinlenme",
                        "protocol": "10 dk kalça/omuz eklem açma ve hafif akşam yürüyüşü.",
                        "coaching_cue": f"Kalan kotanı ({rem_runs} Koşu, {rem_gyms} Kuvvet) dağıtırken ağır bacak kuvveti ile interval arasına yerleştir.",
                    }
                ],
                "cooldown": "Gece 00:30 öncesi yatış ve glikojen dengelemesi.",
                "telemetry_targets": {
                    "hr_range": "<100 bpm (Parasempatik Gün)",
                    "est_calories": "~2.450 kcal toplam harcama",
                    "nutrition": f"2.350 kcal alım | {prot_g}g Protein | 230g Karbonhidrat | 80g Yağ | 3.0 L Su",
                },
            },
            {
                "day_code": "saturday",
                "slot_label": "Workout B",
                "quota_status": "remaining" if "gym_b" in rem_gym_kinds else "completed",
                "day_title": "Kuvvet Reçetesi B: Workout B (Arka Zincir, Omuz & Çekiş)",
                "category": "gym",
                "badge": "Workout B",
                "badge_color": "blue",
                "status_note": _quota_note("gym_b" in rem_gym_kinds, gyms_done, rem_gyms, "Kuvvet", "Toparlanmana uygun herhangi bir günde uygula"),
                "objective": "Arka zincir, omuz itiş gücü, kanat hipertrofisi ve trapez dayanıklılığı.",
                "warmup": "5-8 dk dinamik eklem açma + Boş bar ile Squat ve OHP ısınma setleri.",
                "exercises": [
                    {
                        "num": 1, "name": "Barbell Back Squat", "sets": 5, "reps": 5,
                        "current_achieved": f"{sq.get('max_kg', 65.0):.1f} kg ({sq.get('last_date', 'Son')})",
                        "target_weight": sq.get("next_target", "67.5 kg x 5x5"),
                        "rest_sec": "150 - 180 sn", "target_rpe": "8.0",
                        "coaching_cue": "Haftanın 2. bacak seansı; hacim ve alt vücut gücü.",
                    },
                    {
                        "num": 2, "name": "Barbell Overhead Press (OHP)", "sets": 5, "reps": 5,
                        "current_achieved": f"{ohp.get('max_kg', 40.0):.1f} kg ({ohp.get('last_date', 'Son')})",
                        "target_weight": ohp.get("next_target", "40.0 kg x 5x5"),
                        "rest_sec": "120 - 150 sn", "target_rpe": "8.5",
                        "coaching_cue": "Kalça ve karın kilitli, barı dik çizgide baş üzerine itiş.",
                    },
                    {
                        "num": 3, "name": "Barbell Deadlift", "sets": 1, "reps": 5,
                        "current_achieved": f"{dl.get('max_kg', 60.0):.1f} kg ({dl.get('last_date', 'Son')})",
                        "target_weight": dl.get("next_target", "65.0 kg (+5.0 kg Artış)"),
                        "rest_sec": "180 sn (Tek ağır ana set)", "target_rpe": "8.5",
                        "coaching_cue": "Bel omurları nötr, bar kaval kemiğine yakın, kalçadan kilitleniş.",
                    },
                    {
                        "num": 4, "name": "Lat Pulldown (Geniş Tutuş)", "sets": 4, "reps": 12,
                        "current_achieved": f"{lat.get('max_kg', 45.0):.1f} kg ({lat.get('last_date', 'Son')})",
                        "target_weight": lat.get("next_target", "47.5 kg x 12"),
                        "rest_sec": "75 - 90 sn", "target_rpe": "8.0",
                        "coaching_cue": "Kanat genişliği için göğüs üstüne çekiş ve tepe sıkıştırma.",
                    },
                    {
                        "num": 5, "name": "Dumbbell Lateral Raise (Yan Açış)", "sets": 3, "reps": 12,
                        "current_achieved": f"{lr.get('max_kg', 25.0):.1f} kg ({lr.get('last_date', 'Son')})",
                        "target_weight": lr.get("next_target", "25.0 kg"),
                        "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                        "coaching_cue": "Yan omuz başı hipertrofisi.",
                    },
                    {
                        "num": 6, "name": "Dumbbell / Barbell Shrug (Trapez)", "sets": 3, "reps": 12,
                        "current_achieved": f"{sh.get('max_kg', 45.0):.1f} kg ({sh.get('last_date', 'Son')})",
                        "target_weight": sh.get("next_target", "45.0 kg"),
                        "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                        "coaching_cue": "Üst trapez izolasyonu ve tutuş dayanıklılığı.",
                    },
                ],
                "cooldown": "5 dk arka bacak ve sırt açma esnemesi.",
                "telemetry_targets": {
                    "hr_range": "115 - 130 bpm (Zone 1)",
                    "est_calories": "~2.900 kcal toplam harcama",
                    "nutrition": f"2.500 kcal alım | {prot_g}g Protein | 270g Karbonhidrat | 80g Yağ | 3.0 L Su",
                },
            },
            {
                "day_code": "sunday",
                "slot_label": "Aktif Dinlenme",
                "quota_status": "optional",
                "day_title": "Aktif Toparlanma Şablonu: Mobilite, Yürüyüş & Esnek Kapanış",
                "category": "active_recovery",
                "badge": "Aktif Dinlenme",
                "badge_color": "emerald",
                "status_note": (
                    "Haftalık 4/4 Antrenman Kotası Tamamlandı • Aktif Toparlanma"
                    if total_rem == 0
                    else f"Esnek Aktif Toparlanma • Haftalık Kotadan Kalan: {total_rem} Seans"
                ),
                "objective": "Laktat temizliği, parasempatik tonus artışı ve eklem sağlığı.",
                "warmup": "Gerekli değil.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Açık Hava Tempolu Yürüyüş & Esneme",
                        "duration": "30 - 45 dakika",
                        "target_hr": "<110 bpm (Zone 1 Hafif)",
                        "protocol": "Açık havada tempolu yürüyüş + 15 dk tüm vücut statik esneme ve NSDR.",
                        "coaching_cue": "Kan dolaşımını artırarak sonraki hafta kotasına taze giriş sağlamak.",
                    }
                ],
                "cooldown": "Ekranlardan uzaklaşma.",
                "telemetry_targets": {
                    "hr_range": "<110 bpm (Zone 1)",
                    "est_calories": "~2.500 kcal toplam harcama",
                    "nutrition": f"2.350 kcal alım | {prot_g}g Protein | 220g Karbonhidrat | 80g Yağ | 2.5 - 3.0 L Su",
                },
            },
            {
                "day_code": "monday",
                "slot_label": "5K İnterval",
                "quota_status": "remaining" if "interval" in rem_run_kinds else "completed",
                "day_title": "Koşu Reçetesi #2: 5K Hız İntervali & Anaerobik Yük (4 x 1.000m)",
                "category": "running",
                "badge": "5K İnterval",
                "badge_color": "purple",
                "status_note": _quota_note("interval" in rem_run_kinds, runs_done, rem_runs, "Koşu", "Taze bacakla ve Anaerobik eksiği kapatmak için uygun günde uygula"),
                "objective": "Laktat eşiğini ve barın ortasında kalan Anaerobik (Zone 5) yükünü yukarı çekmek.",
                "warmup": "10 dk hafif jog @ 135-145 bpm + 3 adet 50m strides + kalça mobilitesi.",
                "exercises": [
                    {
                        "num": 1, "name": "4 x 1.000 Metre Hız Tekrarları (Laktat Eşiği & Anaerobik)",
                        "sets": 4, "reps": "1.000 Metre",
                        "target_pace": "5:15 /km tempo",
                        "target_hr": "172 - 182 bpm (Zone 4 - 5)",
                        "rest_between_reps": "Her 1000m sonrası 3 DAKİKA yavaş yürüyüş / hafif jog",
                        "cadence_target": "165 - 170 spm",
                        "coaching_cue": "Ağır bacak gününün ertesi günü değil, taze bacakla (veya kuvvetten önce) 4 tekrar boyunca eşit 5:15 temposu koruyun.",
                    }
                ],
                "cooldown": "8-10 dk hafif toparlanma jogu + derin baldır esnemesi.",
                "telemetry_targets": {
                    "hr_range": "172 - 183 bpm (Zirve Zone 4-5)",
                    "est_calories": "~3.050 kcal toplam harcama",
                    "nutrition": f"2.650 kcal alım | {prot_g}g Protein | 300g Karbonhidrat | 80g Yağ | 3.5 L Su + Elektrolit",
                },
            },
        ]

    def get_athlete_principles(self) -> Dict[str, Any]:
        """Kullanıcının belirlediği temel sporcu ilkelerini döner."""
        return {
            "profile": ATHLETE_PROFILE,
            "nutrition": NUTRITION_PRINCIPLES,
            "strength": STRENGTH_PRINCIPLES,
            "running": RUNNING_PRINCIPLES,
            "same_day_sequence": SAME_DAY_SEQUENCE_LAW,
            "cross_sports": CROSS_SPORTS_PROTOCOLS,
            "recovery_and_watch": RECOVERY_AND_WATCH_SETTINGS,
            "presentation": PRESENTATION_RULES,
            "athlete_levels": ATHLETE_LEVELS_FRAMEWORK,
            "progression_triggers": DYNAMIC_PROGRESSION_TRIGGERS,
        }
