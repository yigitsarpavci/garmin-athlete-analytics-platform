#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Branş Rehberliği, Salon Set Tarihçesi, Bilinmeyen/Preset Dışı Sporlar ve Seans Reçeteleri Mixin'i.
Tüm egzersiz hedefleri ve branş istatistikleri canlı Garmin telemetrisinden dinamik hesaplanır.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any

try:
    from athlete_principles import build_athlete_principles
    from engine.helpers import request_cached, zone_text, DATA_DIR, format_sport_tr
    from engine.strength_progression import (
        PROGRAM_SPLIT_CATALOG,
        build_projected_gym_summary,
        build_split_protocol,
        compute_adaptive_progression,
        load_logged_gym_sessions,
        load_program_state,
        save_logged_gym_session,
        save_program_state,
        inject_split_derived_lifts,
        select_program_split,
    )
except ImportError:
    from app.athlete_principles import build_athlete_principles
    from app.engine.helpers import request_cached, zone_text, DATA_DIR, format_sport_tr
    from app.engine.strength_progression import (
        PROGRAM_SPLIT_CATALOG,
        build_projected_gym_summary,
        build_split_protocol,
        compute_adaptive_progression,
        load_logged_gym_sessions,
        load_program_state,
        save_logged_gym_session,
        save_program_state,
        inject_split_derived_lifts,
        select_program_split,
    )


logger = logging.getLogger(__name__)


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

class WorkoutProtocolsMixin:
    """Salon ağırlık geçmişi, branş rehberliği, bilinmeyen spor desteği ve seans reçeteleri."""

    @request_cached
    def get_gym_exercise_history(self) -> Dict[str, Any]:
        """Garmin kuvvet seanslarının tüm set, tekrar ve dinamik progression hedeflerini döner."""
        data_dir = self.data_dir if hasattr(self, "data_dir") else DATA_DIR
        gym_file = os.path.join(data_dir, "raw_gym_exercise_sets.json")
        raw_data: Dict[str, Any] = {}
        if os.path.exists(gym_file):
            try:
                with open(gym_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except (OSError, ValueError):
                logger.warning("get_gym_exercise_history: yedek davranış uygulandı", exc_info=True)
                raw_data = {}

        manual_sessions = load_logged_gym_sessions(data_dir)
        program_state = load_program_state(data_dir)
        if not raw_data and not manual_sessions:
            baseline = compute_adaptive_progression([], bodyweight_kg=self.get_current_weight())
            return {
                "sessions": [],
                "progression": baseline["progression"],
                "plateau_analysis": {"plateau_score": 0, "recommended_split": "5x5_linear", "tier_label": "Doğrusal İvme Aktif", "recommendation": "Veri bekleniyor.", "signals": []},
                "program_state": program_state,
                "split_catalog": PROGRAM_SPLIT_CATALOG,
                "manual_log_count": 0,
            }

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
            sets = info.get("sets") or info.get("exerciseSets") or []

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
            is_b = bool(cat_set.intersection({"SHOULDER_PRESS", "DEADLIFT", "PULL_UP"}))
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

        for m in manual_sessions:
            sessions.append({
                "activity_id": m.get("activity_id") or f"manual_{m.get('date', '')}",
                "date": m.get("date", ""),
                "time": m.get("time", ""),
                "workout_type": m.get("workout_type", "Workout A"),
                "duration_min": m.get("duration_min", 55),
                "calories": m.get("calories", 350),
                "avg_hr": m.get("avg_hr"),
                "total_volume_kg": m.get("total_volume_kg", 0.0),
                "exercises": m.get("exercises", []),
                "is_manual": True,
            })

        sessions.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)

        # Canlı biyometri ve Garmin yük durumu ile çok faktörlü progresyon hesapla
        metrics = self.get_latest_metrics() if hasattr(self, "get_latest_metrics") else {}
        bw_kg = float(metrics.get("weight") or self.get_current_weight())
        hrv_val = float(metrics.get("overnight_hrv") or 45.0)
        hrv_7d = float(metrics.get("hrv_7d") or hrv_val or 45.0)
        sleep_sc = float(metrics.get("sleep_score") or 80.0)
        acwr_val = float(metrics.get("acwr") or 1.0)

        chrono_sessions = sorted(sessions, key=lambda x: (x.get("date", ""), x.get("time", "")))
        ref_date = str(metrics.get("date") or "")[:10] or None
        adaptive = compute_adaptive_progression(
            chrono_sessions=chrono_sessions,
            bodyweight_kg=bw_kg,
            readiness_ctx={
                "hrv_ratio": round(hrv_val / max(1.0, hrv_7d), 2),
                "sleep_score": sleep_sc,
                "acwr": acwr_val,
            },
            reference_date=ref_date,
        )

        # Program, plato analizine göre otomatik seçilir (kullanıcı seçimi yok).
        # Okuma yolu diske yazmaz; kalıcı kayıt yalnızca veri değiştiğinde persist_program_state() ile yapılır.
        auto_split = select_program_split(int((adaptive["plateau_analysis"] or {}).get("plateau_score", 0)))
        program_state = {
            **program_state,
            "active_split": auto_split,
            "persisted_split": program_state.get("active_split"),
        }

        inject_split_derived_lifts(adaptive["progression"], auto_split, bodyweight_kg=bw_kg)

        return {
            "sessions": sessions,
            "progression": adaptive["progression"],
            "plateau_analysis": adaptive["plateau_analysis"],
            "readiness_note": adaptive["readiness_note"],
            "stall_summary": adaptive["stall_summary"],
            "program_state": program_state,
            "split_catalog": PROGRAM_SPLIT_CATALOG,
            "manual_log_count": len(manual_sessions),
        }

    def log_gym_session_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Kullanıcının tamamladığı/kısmi kaldığı kuvvet seansını kaydedip tüm progresyonu günceller."""
        data_dir = self.data_dir if hasattr(self, "data_dir") else DATA_DIR
        date_str = str(payload.get("date") or "").strip()
        if not date_str:
            metrics = self.get_latest_metrics() if hasattr(self, "get_latest_metrics") else {}
            date_str = str(metrics.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
        workout_type = str(payload.get("workout_type") or "Workout A").strip()
        exercises_in = payload.get("exercises") or []

        normalized_ex: List[Dict[str, Any]] = []
        total_vol = 0.0
        for ex in exercises_in:
            name = str(ex.get("name") or "").strip()
            sets_in = ex.get("sets") or []
            clean_sets = []
            for s in sets_in:
                w = round(float(s.get("weight_kg") or 0.0), 1)
                r = int(s.get("reps") or 0)
                if w > 0 and r > 0:
                    clean_sets.append({"weight_kg": w, "reps": r})
                    total_vol += (w * r)
            if name and clean_sets:
                normalized_ex.append({"name": name, "sets": clean_sets})

        entry = {
            "activity_id": f"manual_{date_str}_{workout_type.lower().replace(' ', '_')}",
            "date": date_str,
            "time": str(payload.get("time") or "18:00"),
            "workout_type": workout_type,
            "duration_min": float(payload.get("duration_min") or 55.0),
            "calories": int(payload.get("calories") or 360),
            "total_volume_kg": round(total_vol, 1),
            "exercises": normalized_ex,
        }
        save_logged_gym_session(data_dir, entry)

        # Yeni seans verisi plato skorunu değiştirmiş olabilir; program geçişini kalıcılaştır
        if getattr(self, "_req_cache", None) is not None:
            self._req_cache.clear()
        self.persist_program_state()
        updated = self.get_gym_exercise_history()
        return {
            "status": "ok",
            "logged_entry": entry,
            "gym_history": updated,
        }

    def persist_program_state(self) -> Dict[str, Any]:
        """
        Plato analizinin seçtiği programı, diskteki kayıttan farklıysa training_program_state.json'a yazar.
        Yalnızca veri değiştiğinde (Garmin sync, manuel seans kaydı/silme) çağrılır; GET istekleri yazmaz.
        """
        data_dir = self.data_dir if hasattr(self, "data_dir") else DATA_DIR
        gh = self.get_gym_exercise_history()
        auto_split = (gh.get("program_state") or {}).get("active_split", "5x5_linear")
        stored = load_program_state(data_dir)
        if stored.get("active_split") == auto_split:
            return stored
        score = (gh.get("plateau_analysis") or {}).get("plateau_score", 0)
        try:
            return save_program_state(
                data_dir,
                new_split=auto_split,
                reason=f"Plato skoru {score}/100 -> otomatik program seçimi",
                source="auto",
            )
        except (OSError, ValueError):
            logger.warning("persist_program_state: yedek davranış uygulandı", exc_info=True)
            return stored


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
        elif "sail" in low:
            water_l = round(float(rows_df["water_ml"].sum()) / 1000.0, 1)
            goal = "Uzun seanslarda core/önkol dayanıklılığı ve sıvı-elektrolit dengesi"
            tips = [
                "İzometrik Tutuş Gücü: Farmer's Walk ve Dead Hang, halat/kol yorgunluğunu önler.",
                f"Sıvı & Elektrolit Protokolü: {water_l} L toplam tahmini ter kaybı gözlendi; saat başı 500-600 mL su + sodyum tüketin.",
                "Glikojen Ön-Yüklemesi: 3 saat üzeri seanslardan 90 dk önce 70-80g kompleks karbonhidrat alın.",
            ]
            upcoming = {"day": "Spontane Seans (Çıktıkça İşlenir)", "type": f"{label} Seansı", "title": f"Uzun {label} Antrenmanı", "duration": "2,5 - 4 saat", "details": "2 x 750 mL matara (su + 500-800 mg sodyum). Saat başı düzenli yudumlayın."}
        elif any(k in low for k in ("basket", "football", "soccer", "tennis", "padel", "squash", "volley", "handball")):
            goal = "Patlayıcı hızlanma, yön değiştirme ve anaerobik dayanıklılık"
            tips = [
                "Doğal HIIT Katkısı: Anaerobik yük eksiğini kapatmaya doğal destek sağlar.",
                "Yük Çakışması Kuralı: Maç günü ağır bacak (Squat/Deadlift) yerine üst vücut veya dinlenme tercih edin.",
                "Maç Öncesi & Sonrası: 10 dk dinamik ayak bileği ısınması + 10 dk statik hamstring esnemesi.",
            ]
            upcoming = {"day": "Spontane Maç (Çıktıkça İşlenir)", "type": f"{label} (İsteğe Bağlı)", "title": f"{label} Maçı", "duration": "60 - 90 dk", "details": "Maç öncesi 10 dk dinamik bacak ısınması; maç sonrası 10 dk esneme."}
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

    @request_cached
    @zone_text
    def get_sports_guidance(self) -> Dict[str, Any]:
        """Kuvvet ve Garmin'den gelen tüm preset dışı sporlar için dinamik rehberlik döner."""
        weekly_quota = self.get_weekly_quota_summary()
        gyms_done = weekly_quota["strength"]["completed"]
        rem_gyms = weekly_quota["strength"]["remaining"]
        prog = self.get_gym_exercise_history().get("progression", {})

        gym_cnt, gym_hours, gym_kcal = self._compute_strength_stats()


        gym_hist_data = self.get_gym_exercise_history()
        gym_sessions = gym_hist_data.get("sessions", [])
        active_split = (gym_hist_data.get("program_state") or {}).get("active_split", "5x5_linear")
        split_slots = PROGRAM_SPLIT_CATALOG.get(active_split, PROGRAM_SPLIT_CATALOG["5x5_linear"])["slots"]

        gym_upcoming = self._build_gym_upcoming(active_split, gym_sessions, prog, split_slots, weekly_quota)

        last_workout = self._build_last_workout(gym_sessions)

        sq_t = prog.get("squat", {}).get("next_target", "--")
        ohp_t = prog.get("ohp", {}).get("next_target", "--")
        dl_t = prog.get("deadlift", {}).get("next_target", "--")
        lat_t = prog.get("lat_pulldown", {}).get("next_target", "--")
        lr_t = prog.get("lateral_raise", {}).get("next_target", "--")
        sh_t = prog.get("shrug", {}).get("next_target", "--")

        sq_pr = prog.get("squat", {}).get("max_kg", 0.0)
        bp_pr = prog.get("bench", {}).get("max_kg", 0.0)
        rw_pr = prog.get("row", {}).get("max_kg", 0.0)

        extra_sports = self._collect_extra_sports_cards()

        gym_sched_status = (
            f"Esnek Haftalık Kota (A/B 5x5 • Bu Hafta: {gyms_done}/2 Tamamlandı · Kota Doldu)"
            if rem_gyms == 0 else f"Esnek Haftalık Kota (A/B 5x5 • Bu Hafta: {gyms_done}/2 Yapıldı · Kalan: {rem_gyms})"
        )

        return {
            "weekly_quota": weekly_quota,
            "extra_sports": extra_sports,
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
        }

    def _compute_strength_stats(self):
        """Kuvvet seansı sayısını, toplam saati ve kaloriyi hesaplar."""
        # Canlı kuvvet istatistikleri
        gym_cnt, gym_hours, gym_kcal = 0, 0.0, 0
        if hasattr(self, "adf") and not self.adf.empty:
            g_df = self.adf_3m[self.adf_3m["sport"].str.contains("strength|fitness_equipment", case=False, na=False)]
            if not g_df.empty:
                gym_cnt = int(len(g_df))
                gym_hours = round(float(g_df["dur_m"].sum()) / 60.0, 1)
                gym_kcal = int(round(float(g_df["cal"].sum())))
        return gym_cnt, gym_hours, gym_kcal


    def _build_gym_upcoming(self, active_split, gym_sessions, prog, split_slots, weekly_quota):
        """Kalan kuvvet kotası ve sonraki döngü projeksiyonlarını (aktif split'e göre) üretir."""
        ex_counts: Dict[str, int] = {}
        gym_upcoming: List[Dict[str, str]] = []
        for idx_rem, item in enumerate(weekly_quota["strength"]["remaining_items"]):
            raw_kind = item.get("slot_kind", "gym_a")
            eff_kind = split_slots[idx_rem % len(split_slots)] if active_split != "5x5_linear" else raw_kind
            p_type, p_title, p_details = build_projected_gym_summary(
                eff_kind, prog, step_idx=idx_rem, active_split=active_split, ex_counts=ex_counts
            )
            gym_upcoming.append({
                "day": "Bu Hafta Kalan Kota (Esnek Gün)" + (" · Öncelikli" if item.get("is_prioritized") else ""),
                "type": f"{p_type} · Kalan",
                "title": p_title if active_split != "5x5_linear" else item["title"],
                "duration": item["duration"],
                "details": p_details,
            })

        gym_kinds_chain = [
            (split_slots[i % len(split_slots)] if active_split != "5x5_linear" else item.get("slot_kind"))
            for i, item in enumerate(weekly_quota["strength"]["remaining_items"])
            if item.get("slot_kind")
        ]
        rem_gym_count = len(gym_upcoming)
        while len(gym_upcoming) < 3:
            if not gym_kinds_chain:
                last_wt = (gym_sessions[0].get("workout_type", "") if gym_sessions else "")
                if active_split != "5x5_linear":
                    next_cycle_kind = split_slots[0]
                    if len(split_slots) > 1 and split_slots[0].lower() in last_wt.lower():
                        next_cycle_kind = split_slots[1]
                else:
                    next_cycle_kind = "gym_b" if "Workout A" in last_wt else "gym_a"
                prev_gym = None
            else:
                prev_gym = gym_kinds_chain[-1]
                if active_split != "5x5_linear":
                    cur_i = split_slots.index(prev_gym) if prev_gym in split_slots else 0
                    next_cycle_kind = split_slots[(cur_i + 1) % len(split_slots)]
                else:
                    next_cycle_kind = "gym_b" if prev_gym == "gym_a" else "gym_a"

            step_idx = len(gym_upcoming)
            step_num = len(gym_upcoming) - rem_gym_count + 1
            p_type, p_title, p_details = build_projected_gym_summary(
                next_cycle_kind, prog, step_idx=step_idx, active_split=active_split, ex_counts=ex_counts
            )
            prev_label = (
                "Workout A" if prev_gym == "gym_a"
                else ("Workout B" if prev_gym == "gym_b" else (prev_gym or "").title())
            )
            day_lbl = (
                "Sıradaki Projeksiyon (Yeni Döngü #1)"
                if step_num == 1
                else f"{prev_label} Sonrası Projeksiyon (Yeni Döngü #{step_num})"
            )
            gym_upcoming.append({
                "day": day_lbl,
                "type": f"{p_type} · Projeksiyon",
                "title": p_title,
                "duration": "55 dk",
                "details": p_details,
            })
            gym_kinds_chain.append(next_cycle_kind)
        return gym_upcoming


    def _build_last_workout(self, gym_sessions):
        """Son kuvvet seansının özet kartını üretir."""
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
                "exercises": ["Henüz Garmin'den kuvvet seansı alınmadı"],
            }
        return last_workout


    def _collect_extra_sports_cards(self):
        """Preset dışı (Kayak, Yüzme, Bisiklet vb.) sporları otomatik bulup rehber kartlarını üretir."""
        # Bilinmeyen / Preset dışı sporları otomatik tara (Kayak, Yüzme, Bisiklet vb.)
        extra_sports: List[Dict[str, Any]] = []
        known_core = {"running", "strength_training"}
        if hasattr(self, "adf_3m") and not self.adf_3m.empty:
            for sp_key, grp in self.adf_3m.groupby("sport"):
                if str(sp_key).lower() not in known_core:
                    extra_sports.append(self._build_dynamic_extra_sport_card(str(sp_key), grp))
        return extra_sports


    @request_cached
    @zone_text
    def get_detailed_daily_workout_protocols(self) -> List[Dict[str, Any]]:
        """Canlı gym PR hedeflerine, kiloya ve haftalık kota durumuna bağlı 7 seans/şablon reçetesi döner."""
        quota = self.get_weekly_quota_summary()
        runs_done = quota["running"]["completed"]
        rem_runs = quota["running"]["remaining"]
        gyms_done = quota["strength"]["completed"]
        rem_gyms = quota["strength"]["remaining"]
        total_done = quota["total"]["completed"]
        total_rem = quota["total"]["remaining"]
        completed_run_kinds = set(quota["running"].get("completed_kinds") or [])
        completed_gym_kinds = set(quota["strength"].get("completed_kinds") or [])
        rem_run_kinds = {i["slot_kind"] for i in quota["running"]["remaining_items"]}
        rem_gym_kinds = {i["slot_kind"] for i in quota["strength"]["remaining_items"]}
        post_tempo_adapted = bool(quota.get("post_tempo_adapted"))

        # ÖNEMLİ: Yapılan seans planlanandan farklı (örn. Tempo) ise unperformed türler 'completed' sayılmaz!
        gym_a_done = "gym_a" in completed_gym_kinds
        gym_b_done = "gym_b" in completed_gym_kinds
        z2_done = "zone2" in completed_run_kinds
        tempo_done = "tempo" in completed_run_kinds
        int_done = "interval" in completed_run_kinds
        z2_status = "completed" if z2_done else ("remaining" if ("zone2" in rem_run_kinds or (rem_runs > 0 and not z2_done)) else "optional")
        tempo_status = "completed" if tempo_done else ("remaining" if "tempo" in rem_run_kinds else "optional")
        int_status = "completed" if int_done else ("remaining" if ("interval" in rem_run_kinds or (rem_runs > 0 and not int_done)) else "optional")

        def _quota_note(is_remaining: bool, done_count: int, rem_count: int, label_tr: str, next_hint: str) -> str:
            if is_remaining:
                return f"Bu Hafta Kalan Kota ({done_count}/2 {label_tr} Yapıldı, {rem_count} Kaldı) • {next_hint}"
            return f"Bu Haftaki İhtiyaç Tamamlandı ({done_count}/2 {label_tr}) • Bir Sonraki Döngü İçin Şablon"

        if post_tempo_adapted:
            int_note = (
                f"{runs_done}/2 Koşu Yapıldı ({rem_runs} Kaldı) • Planlanan İnterval yerine Tempo Koşusu (TE: TEMPO, AnTE: 0.0) "
                "yapıldığı için İnterval tamamlanmadı sayıldı; Anaerobik eksiği kapatmak için öncelikli telafi seansı"
            )
            z2_note = (
                f"{runs_done}/2 Koşu Yapıldı ({rem_runs} Kaldı) • Plan dışı Zone 3 Tempo sonrası Zone 2 de henüz yapılmadı; "
                "bacaklar yorgunsa kalan 1 koşu kotasında alternatif dengeleme olarak seçilebilir"
            )
        else:
            int_note = _quota_note(int_status == "remaining", runs_done, rem_runs, "Koşu", "Taze bacakla ve Anaerobik eksiği kapatmak için uygun günde uygula")
            z2_note = _quota_note(z2_status == "remaining", runs_done, rem_runs, "Koşu", "Bacakların taze olduğu herhangi bir günde uygula")

        if tempo_done:
            tempo_note = f"{runs_done}/2 Koşu Yapıldı · Bu hafta Yüksek Aerobik Tempo koşusu tamamlandı"
        elif tempo_status == "remaining":
            tempo_note = _quota_note(True, runs_done, rem_runs, "Koşu", "Yüksek Aerobik barını doldurmak için sabit eşik temposunda uygula")
        else:
            tempo_note = "Esnek Şablon • Yüksek Aerobik (Zone 3–4 Tempo) barı açıldığında uygulanır"

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
        cur_w = float(metrics.get("weight") or self.get_current_weight())
        prot_g = round(cur_w * 2.0)

        gym_hist_full = self.get_gym_exercise_history()
        active_split = (gym_hist_full.get("program_state") or {}).get("active_split", "5x5_linear")
        protocols = [
                self._protocol_tuesday_gym_a(_quota_note, bp, gym_a_done, gyms_done, lr, prot_g, rem_gym_kinds, rem_gyms, rw, sh, sq),
                self._protocol_wednesday_rest(gyms_done, prot_g, runs_done, total_done, total_rem),
                self._protocol_thursday_zone2_run(prot_g, z2_note, z2_status),
                self._protocol_friday_prep_rest(prot_g, rem_gyms, rem_runs),
                self._protocol_saturday_gym_b(_quota_note, dl, gym_b_done, gyms_done, lat, lr, ohp, prot_g, rem_gym_kinds, rem_gyms, sh, sq),
                self._protocol_sunday_active_recovery(prot_g, total_rem),
                self._protocol_monday_interval_run(int_note, int_status, prot_g),
                self._protocol_tempo_run(tempo_note, tempo_status, prot_g),
        ]
        if active_split != "5x5_linear":
            slots = PROGRAM_SPLIT_CATALOG.get(active_split, {}).get("slots", ["push", "pull"])
            gym_idx = 0
            for proto in protocols:
                if proto.get("category") == "gym" and gym_idx < len(slots):
                    slot_k = slots[gym_idx]
                    sp_proto = build_split_protocol(slot_k, prog, active_split)
                    if sp_proto:
                        proto["slot_label"] = sp_proto["badge"]
                        proto["badge"] = sp_proto["badge"]
                        proto["day_title"] = sp_proto["day_title"]
                        proto["objective"] = sp_proto["objective"]
                        proto["warmup"] = sp_proto["warmup"]
                        proto["exercises"] = sp_proto["exercises"]
                    gym_idx += 1
            while gym_idx < len(slots):
                slot_k = slots[gym_idx]
                sp_proto = build_split_protocol(slot_k, prog, active_split)
                if sp_proto:
                    protocols.append({
                        "day_code": f"gym_{slot_k}",
                        "slot_label": sp_proto["badge"],
                        "quota_status": "remaining",
                        "day_title": sp_proto["day_title"],
                        "category": "gym",
                        "badge": sp_proto["badge"],
                        "objective": sp_proto["objective"],
                        "warmup": sp_proto["warmup"],
                        "exercises": sp_proto["exercises"],
                        "status_note": "",
                    })
                gym_idx += 1
        return protocols

    def _protocol_tuesday_gym_a(self, _quota_note, bp, gym_a_done, gyms_done, lr, prot_g, rem_gym_kinds, rem_gyms, rw, sh, sq) -> Dict[str, Any]:
        """Salı: Workout A (tüm vücut güç & hipertrofi) kuvvet reçetesi."""
        return {
            "day_code": "tuesday",
            "slot_label": "Workout A",
            "quota_status": "completed" if gym_a_done else ("remaining" if "gym_a" in rem_gym_kinds else "completed"),
            "day_title": "Kuvvet Reçetesi A: Workout A (Tüm Vücut Güç & Hipertrofi)",
            "category": "gym",
            "badge": "Workout A",
            "badge_color": "blue",
            "status_note": _quota_note((not gym_a_done) and ("gym_a" in rem_gym_kinds), gyms_done, rem_gyms, "Kuvvet", "Uygun olduğun herhangi bir günde uygula"),
            "objective": "Nöromüsküler güç inşası, göğüs, bacak, sırt ve yan omuz gelişimi (Progressive Overload). Sabit gün zorunluluğu olmadan haftanın uygun gününe yerleştirilir.",
            "warmup": "5 dk dinamik kalça & omuz mobilitesi + Boş bar ile 2x10 Squat ve 2x10 Bench Press hafif ısınma setleri.",
            "exercises": [
                {
                    "num": 1, "name": "Barbell Back Squat", "sets": 5, "reps": 5,
                    "current_achieved": f"{sq.get('max_kg', 0.0):.1f} kg ({sq.get('last_date', 'Son')})",
                    "target_weight": sq.get("next_target", "--"),
                    "rest_sec": "150 - 180 sn", "target_rpe": "8.0",
                    "coaching_cue": "Paralel altı derinlik, göğüs dik, topuklardan dengeli zemin itişi.",
                },
                {
                    "num": 2, "name": "Barbell Bench Press", "sets": 5, "reps": 5,
                    "current_achieved": f"{bp.get('max_kg', 0.0):.1f} kg ({bp.get('last_date', 'Son')})",
                    "target_weight": bp.get("next_target", "--"),
                    "rest_sec": "120 - 150 sn", "target_rpe": "8.5",
                    "coaching_cue": "Kürek kemikleri geride kilitli, barı kontrollü göğüs ucuna indirip patlayıcı itiş.",
                },
                {
                    "num": 3, "name": "Barbell Bent-Over Row", "sets": 5, "reps": 5,
                    "current_achieved": f"{rw.get('max_kg', 0.0):.1f} kg ({rw.get('last_date', 'Son')})",
                    "target_weight": rw.get("next_target", "--"),
                    "rest_sec": "120 - 150 sn", "target_rpe": "8.0",
                    "coaching_cue": "Gövde 45 derece eğik, bel nötr, barı alt karına çekip kürek kemiklerini sıkıştırın.",
                },
                {
                    "num": 4, "name": "Dumbbell Lateral Raise (Yan Açış)", "sets": 3, "reps": 12,
                    "current_achieved": f"{lr.get('max_kg', 0.0):.1f} kg ({lr.get('last_date', 'Son')})",
                    "target_weight": lr.get("next_target", "--"),
                    "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                    "coaching_cue": "Yan deltoid hipertrofisi ve V-Taper omuz genişliği için dirsekler hafif kırık, tepe noktada 1 sn bekleme.",
                },
                {
                    "num": 5, "name": "Dumbbell / Barbell Shrug (Trapez)", "sets": 3, "reps": 12,
                    "current_achieved": f"{sh.get('max_kg', 0.0):.1f} kg ({sh.get('last_date', 'Son')})",
                    "target_weight": sh.get("next_target", "--"),
                    "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                    "coaching_cue": "Trapez kalınlığı ve tutuş gücü; yelkende hiking ve deadlift kilitlenişini korur.",
                },
            ],
            "cooldown": "5 dk hafif statik esneme (göğüs açış, kalça fleksör ve hamstring).",
            "telemetry_targets": {
                "hr_range": "115 - 130 bpm (Zone 1)",
                "est_calories": self.nutrition_texts("gym").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('gym')['line']} | 3.0 L Su",
            },
        }

    def _protocol_wednesday_rest(self, gyms_done, prot_g, runs_done, total_done, total_rem) -> Dict[str, Any]:
        """Çarşamba: tam dinlenme ve kas onarımı şablonu."""
        return {
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
                "est_calories": self.nutrition_texts("rest").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('rest')['line']} | 2.5 - 3.0 L Su",
            },
        }

    def _protocol_thursday_zone2_run(self, prot_g, z2_note, z2_status) -> Dict[str, Any]:
        """Perşembe: Zone 2 aerobik taban koşu reçetesi."""
        return {
            "day_code": "thursday",
            "slot_label": "Zone 2",
            "quota_status": z2_status,
            "day_title": "Koşu Reçetesi #1: Zone 2 Aerobik Taban (45-50 dk)",
            "category": "running",
            "badge": "Zone 2 Taban",
            "badge_color": "emerald",
            "status_note": z2_note,
            "objective": "Sol karıncık atım hacmini büyütmek ve aerobik tabanı nabız tavanını aşmadan korumak.",
            "warmup": "5-8 dk dinamik kalça ve ayak bileği mobilitesi.",
            "exercises": [
                {
                    "num": 1, "name": "Ana Koşu: Zone 2 Taban Koşusu",
                    "duration": "45 - 50 dakika kesintisiz",
                    "distance_est": "6.8 - 7.5 km",
                    "target_hr": "[[Z2_HR]] (Katı Tavan [[Z2_HR_CAP]] bpm)",
                    "target_pace": "[[Z2_PACE]]",
                    "cadence_target": "160 - 165 spm",
                    "ground_contact_time": "Hedef <275 ms",
                    "coaching_cue": "Burundan rahat konuşma temposu. Nabız [[Z2_HR_CAP]]+ bpm olduğunda yürüyüşe düşüp indirin.",
                }
            ],
            "cooldown": "8 dk baldır, aşil ve kuadriseps statik esnemesi.",
            "telemetry_targets": {
                "hr_range": "[[Z2_HR]] (Zone 2 Taban)",
                "est_calories": self.nutrition_texts("run").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('run')['line']} | 3.5 L Su",
            },
        }

    def _protocol_tempo_run(self, tempo_note, tempo_status, prot_g) -> Dict[str, Any]:
        """Yüksek Aerobik: Tempo / Eşik koşu reçetesi."""
        mx = float(getattr(self, "max_hr_estimate", 0) or 200)
        z3_lo = int(round(0.77 * mx))
        z3_hi = int(round(0.84 * mx))
        return {
            "day_code": "tempo",
            "slot_label": "Tempo",
            "quota_status": tempo_status,
            "day_title": "Koşu Reçetesi #3: Yüksek Aerobik Tempo (30-35 dk)",
            "category": "running",
            "badge": "Yüksek Aerobik",
            "badge_color": "amber",
            "status_note": tempo_note,
            "objective": "Laktat eşiği altında sürekli tempo ile Yüksek Aerobik barını verimli doldurmak.",
            "warmup": "10 dk kolay jog + dinamik kalça açma.",
            "exercises": [
                {
                    "num": 1, "name": "Ana Koşu: Sürekli Tempo / Eşik Bloğu",
                    "duration": "10 dk ısınma + 20 dk Tempo + 5 dk soğuma",
                    "distance_est": "5.0 - 6.0 km",
                    "target_hr": f"{z3_lo} - {z3_hi} bpm (Zone 3 - 4)",
                    "cadence_target": "162 - 168 spm",
                    "coaching_cue": "10 dk rahat ısınma sonrası 20 dk kontrollü ve akıcı eşik temposunu koruyun; sprinte kaçmadan Yüksek Aerobik yükü biriktirin.",
                }
            ],
            "cooldown": "5 dk yürüyüş + baldır ve hamstring esnemesi.",
            "telemetry_targets": {
                "hr_range": f"{z3_lo} - {z3_hi} bpm (Zone 3-4 Tempo)",
                "est_calories": self.nutrition_texts("tempo").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('tempo')['line']} | 3.5 L Su",
            },
        }

    def _protocol_friday_prep_rest(self, prot_g, rem_gyms, rem_runs) -> Dict[str, Any]:
        """Cuma: hafif mobilite ve kuvvet öncesi hazırlık şablonu."""
        return {
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
                "est_calories": self.nutrition_texts("rest").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('rest')['line']} | 3.0 L Su",
            },
        }

    def _protocol_saturday_gym_b(self, _quota_note, dl, gym_b_done, gyms_done, lat, lr, ohp, prot_g, rem_gym_kinds, rem_gyms, sh, sq) -> Dict[str, Any]:
        """Cumartesi: Workout B (arka zincir, omuz & çekiş) kuvvet reçetesi."""
        return {
            "day_code": "saturday",
            "slot_label": "Workout B",
            "quota_status": "completed" if gym_b_done else ("remaining" if "gym_b" in rem_gym_kinds else "completed"),
            "day_title": "Kuvvet Reçetesi B: Workout B (Arka Zincir, Omuz & Çekiş)",
            "category": "gym",
            "badge": "Workout B",
            "badge_color": "blue",
            "status_note": _quota_note((not gym_b_done) and ("gym_b" in rem_gym_kinds), gyms_done, rem_gyms, "Kuvvet", "Toparlanmana uygun herhangi bir günde uygula"),
            "objective": "Arka zincir, omuz itiş gücü, kanat hipertrofisi ve trapez dayanıklılığı.",
            "warmup": "5-8 dk dinamik eklem açma + Boş bar ile Squat ve OHP ısınma setleri.",
            "exercises": [
                {
                    "num": 1, "name": "Barbell Back Squat", "sets": 5, "reps": 5,
                    "current_achieved": f"{sq.get('max_kg', 0.0):.1f} kg ({sq.get('last_date', 'Son')})",
                    "target_weight": sq.get("next_target", "--"),
                    "rest_sec": "150 - 180 sn", "target_rpe": "8.0",
                    "coaching_cue": "Haftanın 2. bacak seansı; hacim ve alt vücut gücü.",
                },
                {
                    "num": 2, "name": "Barbell Overhead Press (OHP)", "sets": 5, "reps": 5,
                    "current_achieved": f"{ohp.get('max_kg', 0.0):.1f} kg ({ohp.get('last_date', 'Son')})",
                    "target_weight": ohp.get("next_target", "--"),
                    "rest_sec": "120 - 150 sn", "target_rpe": "8.5",
                    "coaching_cue": "Kalça ve karın kilitli, barı dik çizgide baş üzerine itiş.",
                },
                {
                    "num": 3, "name": "Barbell Deadlift", "sets": 1, "reps": 5,
                    "current_achieved": f"{dl.get('max_kg', 0.0):.1f} kg ({dl.get('last_date', 'Son')})",
                    "target_weight": dl.get("next_target", "--"),
                    "rest_sec": "180 sn (Tek ağır ana set)", "target_rpe": "8.5",
                    "coaching_cue": "Bel omurları nötr, bar kaval kemiğine yakın, kalçadan kilitleniş.",
                },
                {
                    "num": 4, "name": "Lat Pulldown (Geniş Tutuş)", "sets": 4, "reps": 12,
                    "current_achieved": f"{lat.get('max_kg', 0.0):.1f} kg ({lat.get('last_date', 'Son')})",
                    "target_weight": lat.get("next_target", "--"),
                    "rest_sec": "75 - 90 sn", "target_rpe": "8.0",
                    "coaching_cue": "Kanat genişliği için göğüs üstüne çekiş ve tepe sıkıştırma.",
                },
                {
                    "num": 5, "name": "Dumbbell Lateral Raise (Yan Açış)", "sets": 3, "reps": 12,
                    "current_achieved": f"{lr.get('max_kg', 0.0):.1f} kg ({lr.get('last_date', 'Son')})",
                    "target_weight": lr.get("next_target", "--"),
                    "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                    "coaching_cue": "Yan omuz başı hipertrofisi.",
                },
                {
                    "num": 6, "name": "Dumbbell / Barbell Shrug (Trapez)", "sets": 3, "reps": 12,
                    "current_achieved": f"{sh.get('max_kg', 0.0):.1f} kg ({sh.get('last_date', 'Son')})",
                    "target_weight": sh.get("next_target", "--"),
                    "rest_sec": "60 - 75 sn", "target_rpe": "8.0",
                    "coaching_cue": "Üst trapez izolasyonu ve tutuş dayanıklılığı.",
                },
            ],
            "cooldown": "5 dk arka bacak ve sırt açma esnemesi.",
            "telemetry_targets": {
                "hr_range": "115 - 130 bpm (Zone 1)",
                "est_calories": self.nutrition_texts("gym").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('gym')['line']} | 3.0 L Su",
            },
        }

    def _protocol_sunday_active_recovery(self, prot_g, total_rem) -> Dict[str, Any]:
        """Pazar: aktif toparlanma, mobilite ve esnek kapanış şablonu."""
        return {
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
                "est_calories": self.nutrition_texts("rest").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('rest')['line']} | 2.5 - 3.0 L Su",
            },
        }

    def _protocol_monday_interval_run(self, int_note, int_status, prot_g) -> Dict[str, Any]:
        """Pazartesi: 5K hız intervali ve anaerobik yük koşu reçetesi."""
        return {
            "day_code": "monday",
            "slot_label": "5K İnterval",
            "quota_status": int_status,
            "day_title": "Koşu Reçetesi #2: 5K Hız İntervali & Anaerobik Yük (4 x 1.000m)",
            "category": "running",
            "badge": "5K İnterval",
            "badge_color": "purple",
            "status_note": int_note,
            "objective": "Laktat eşiğini ve barın ortasında kalan Anaerobik (Zone 5) yükünü yukarı çekmek.",
            "warmup": "10 dk hafif jog @ [[WARM_HR]] + 3 adet 50m strides + kalça mobilitesi.",
            "exercises": [
                {
                    "num": 1, "name": "4 x 1.000 Metre Hız Tekrarları (Laktat Eşiği & Anaerobik)",
                    "sets": 4, "reps": "1.000 Metre",
                    "target_pace": "[[INT_PACE]] tempo",
                    "target_hr": "[[Z45_HR]] (Zone 4 - 5)",
                    "rest_between_reps": "Her 1000m sonrası 3 DAKİKA yavaş yürüyüş / hafif jog",
                    "cadence_target": "165 - 170 spm",
                    "coaching_cue": "Ağır bacak gününün ertesi günü değil, taze bacakla (veya kuvvetten önce) 4 tekrar boyunca eşit [[INT_PACE]] temposu koruyun.",
                }
            ],
            "cooldown": "8-10 dk hafif toparlanma jogu + derin baldır esnemesi.",
            "telemetry_targets": {
                "hr_range": "[[Z45_HR]] (Zirve Zone 4-5)",
                "est_calories": self.nutrition_texts("interval").get("spend_line", "--"),
                "nutrition": f"{self.nutrition_texts('interval')['line']} | 3.5 L Su + Elektrolit",
            },
        }

    @request_cached
    def get_athlete_principles(self) -> Dict[str, Any]:
        """Genel antrenman çerçeveleri + sporcunun kendi profilinden ve Garmin verisinden türetilen ilkeler."""
        return build_athlete_principles(self)
