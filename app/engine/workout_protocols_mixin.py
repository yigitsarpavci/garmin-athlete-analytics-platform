#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Branş Rehberliği, Salon Set Tarihçesi, Bilinmeyen/Preset Dışı Sporlar ve Seans Reçeteleri Mixin'i.
Tüm egzersiz hedefleri ve branş istatistikleri canlı Garmin telemetrisinden dinamik hesaplanır.
"""

import logging
import json
import os
from typing import Dict, List, Any

try:
    from engine.helpers import fnum, request_cached, zone_text, DATA_DIR
    from engine.strength_progression import (
        PROGRAM_SPLIT_CATALOG,
        compute_adaptive_progression,
    )
except ImportError:
    from app.engine.helpers import fnum, request_cached, zone_text, DATA_DIR
    from app.engine.strength_progression import (
        PROGRAM_SPLIT_CATALOG,
        compute_adaptive_progression,
    )


logger = logging.getLogger(__name__)

# Kuvvet programı sabit: haftada 2 gün Workout A / Workout B (5x5 doğrusal). Plato analizi yalnızca öneri üretir, programı değiştirmez.
PROGRAM_STATE = {"active_split": "5x5_linear"}


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

        if not raw_data:
            baseline = compute_adaptive_progression([], bodyweight_kg=self.get_current_weight())
            return {
                "sessions": [],
                "progression": baseline["progression"],
                "plateau_analysis": {"plateau_score": 0, "recommended_split": "5x5_linear", "tier_label": "Doğrusal İvme Aktif", "recommendation": "Veri bekleniyor.", "signals": []},
                "program_state": PROGRAM_STATE,
                "split_catalog": PROGRAM_SPLIT_CATALOG,
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

        sessions.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)

        # Canlı biyometri ve Garmin yük durumu ile çok faktörlü progresyon hesapla
        metrics = self.get_latest_metrics() if hasattr(self, "get_latest_metrics") else {}
        bw_kg = float(metrics.get("weight") or self.get_current_weight())
        hrv_val = fnum(metrics.get("overnight_hrv"), 45.0)
        hrv_7d = fnum(metrics.get("hrv_7d") or hrv_val, 45.0)
        sleep_sc = fnum(metrics.get("sleep_score"), 80.0)
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

        return {
            "sessions": sessions,
            "progression": adaptive["progression"],
            "plateau_analysis": adaptive["plateau_analysis"],
            "readiness_note": adaptive["readiness_note"],
            "stall_summary": adaptive["stall_summary"],
            "program_state": PROGRAM_STATE,
            "split_catalog": PROGRAM_SPLIT_CATALOG,
        }

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
                "hr_range": "[[Z1_HR]] (Zone 1)",
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
                "hr_range": "<[[REST_CAP]] bpm (Parasempatik Toparlanma)",
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
        mx = fnum(getattr(self, "max_hr_estimate", 0), 200)
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
                "hr_range": "<[[REST_CAP]] bpm (Parasempatik Gün)",
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
                "hr_range": "[[Z1_HR]] (Zone 1)",
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
                    "target_hr": "<[[Z1_CAP]] bpm (Zone 1 Hafif)",
                    "protocol": "Açık havada tempolu yürüyüş + 15 dk tüm vücut statik esneme ve NSDR.",
                    "coaching_cue": "Kan dolaşımını artırarak sonraki hafta kotasına taze giriş sağlamak.",
                }
            ],
            "cooldown": "Ekranlardan uzaklaşma.",
            "telemetry_targets": {
                "hr_range": "<[[Z1_CAP]] bpm (Zone 1)",
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
