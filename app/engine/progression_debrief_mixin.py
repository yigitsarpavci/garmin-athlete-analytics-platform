#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dinamik İlerleme Analizi ve Antrenman Sonu 5 Maddelik Debrief Motoru Mixin'i.
Anahtar uyuşmazlıkları giderilmiş, tüm PR'lar, ACWR ve 24s biyometri canlı verilerden çekilir.
"""

from typing import Dict, Any

try:
    from athlete_principles import ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    from engine.helpers import format_sport_tr, classify_run_workout
except ImportError:
    from app.athlete_principles import ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    from app.engine.helpers import format_sport_tr, classify_run_workout


class ProgressionDebriefMixin:
    """Seviye/progresyon değerlendirmesi ve 5 maddelik antrenman sonrası debrief üretimi."""

    def get_athlete_progression_assessment(self) -> Dict[str, Any]:
        """Canlı ACWR, RHR, stres, Load Focus ve gym PR değerlerinden gelişim tavsiyesi üretir."""
        tl = self.get_training_load_analytics()
        cur_status = tl.get("current_status", {})
        load_focus = tl.get("load_focus", {})
        metrics = self.get_latest_metrics()
        gym = self.get_gym_exercise_history()
        prog = gym.get("progression", {})

        acwr = float(cur_status.get("acwr") or 1.0)
        acute_load = cur_status.get("acute_load") or 279
        rhr = float(metrics.get("resting_hr") or metrics.get("rhr") or 53.6)
        stress = float(metrics.get("stress") or 28.4)
        cur_weight = float(metrics.get("weight") or 87.0)
        squat_pr = float(prog.get("squat", {}).get("max_kg") or 65.0)
        bench_pr = float(prog.get("bench", {}).get("max_kg") or 50.0)
        row_pr = float(prog.get("row", {}).get("max_kg") or 60.0)
        deadlift_pr = float(prog.get("deadlift", {}).get("max_kg") or 60.0)

        squat_ratio = round(squat_pr / max(1.0, cur_weight), 2)
        bench_ratio = round(bench_pr / max(1.0, cur_weight), 2)
        dl_ratio = round(deadlift_pr / max(1.0, cur_weight), 2)

        vo2max = float(metrics.get("vo2max") or 45.4)
        latest_5k = metrics.get("latest_5k", "29:07 (5:48 /km)")
        cadence = int(metrics.get("latest_cadence") or 159)

        # 1. Gün Arttırma Analizi (Gerçek kuvvet temeli + yük dengesi kapısı)
        strength_ready_for_5th_day = (
            squat_pr >= round(cur_weight * 0.98, 1)
            and bench_pr >= round(cur_weight * 0.78, 1)
        )
        acwr_ok = (0.85 <= acwr <= 1.25) and (rhr <= 56.0) and (stress < 42.0)
        can_increase_days = bool(strength_ready_for_5th_day and acwr_ok)
        if can_increase_days:
            volume_verdict = "HAZIR (5. Gün Eklenebilir)"
            volume_advice = (
                f"Kuvvet eşikleri (Squat {squat_pr:.0f} kg · Bench {bench_pr:.0f} kg), ACWR ({acwr:.2f}) ve "
                f"dinlenik nabız ({rhr:.0f} bpm) 5. antrenman gününü destekliyor; programa hafif 30 dk ek koşu veya "
                "3. kuvvet günü eklenebilir."
            )
            next_level_days = "3 Koşu + 2 Gym veya 2 Koşu + 3 Gym (Haftada 5 Seans)"
        else:
            volume_verdict = "4 GÜN SABİT KALSIN (Ek Gün Önerilmez)"
            volume_advice = (
                f"Toparlanma verileriniz (ACWR {acwr:.2f}, RHR {rhr:.0f} bpm) iyi olsa da mevcut ağırlıklarınız "
                f"(Squat {squat_pr:.0f} kg = {squat_ratio:.2f}x VA, Bench {bench_pr:.0f} kg = {bench_ratio:.2f}x VA) "
                f"henüz vücut ağırlığı ({cur_weight:.0f} kg) eşiğinin altındadır ve kalori açığındasınız. "
                "Bu aşamada 5. günü eklemek bar üzerindeki +2.5 kg artışları yavaşlatır; haftalık 2 Koşu + 2 Kuvvet (4 gün) kotasını koruyun."
            )
            next_level_days = "Şimdilik 4 Gün Korunur (Hedef: Squat ~85 kg · 4/4 İstikrar)"

        # 2. Kuvvet Branşı Seviye & Stil Analizi
        if squat_pr >= 85.0 and bench_pr >= 70.0:
            style_verdict = f"İLERİ BÖLÜNMEYE HAZIR ({squat_ratio:.2f}x VA)"
            style_advice = (
                f"Squat ({squat_pr:.0f} kg = {squat_ratio:.2f}x VA) ve Bench ({bench_pr:.0f} kg = {bench_ratio:.2f}x VA) "
                "vücut ağırlığı eşiklerine ulaştı. Merkezi sinir sistemi toparlanması için Üst/Alt Vücut (Upper/Lower 4 Gün) veya PPL bölünmesine geçilebilir."
            )
        else:
            style_verdict = f"TEMEL–ORTA GEÇİŞ ({squat_ratio:.2f}x VA · 5x5 Lineer İnşa)"
            style_advice = (
                f"Vücut ağırlığından ({cur_weight:.0f} kg) ağır kaldırma şartı ileri seviye içindir. Şu an "
                f"Squat {squat_pr:.0f} kg ({squat_ratio:.2f}x VA), Deadlift {deadlift_pr:.0f} kg ({dl_ratio:.2f}x VA), "
                f"Barbell Row {row_pr:.0f} kg ve Bench {bench_pr:.0f} kg ({bench_ratio:.2f}x VA) ile temel güç inşa fazındasınız; "
                "ilk gerçekçi hedef haftada 2 gün A/B 5x5 ile kendi vücut ağırlığınıza (~85 kg Squat/Deadlift, ~65–70 kg Bench) ulaşmaktır."
            )

        # 3. Koşu Branşı & Load Focus Yönlendirmesi
        low_pct = load_focus.get("aerobic_low", {}).get("pct_of_target", 92.0)
        high_pct = load_focus.get("aerobic_high", {}).get("pct_of_target", 91.0)
        an_pct = load_focus.get("anaerobic", {}).get("pct_of_target", 62.0)
        running_style_advice = (
            f"Firstbeat yük dengesinde Yüksek Aerobik (%{high_pct:.0f}) ve Düşük Aerobik (%{low_pct:.0f}) "
            f"barın üst sınırına yakınken Anaerobik yük (%{an_pct:.0f}) daha düşüktür. Öncelikle 5K hız intervalini (4x1000m @ Z4-5) uygulayın; "
            "Zone 2 hızınız 145 bpm'de 6:00 /km altına indiğinde haftalık 3. koşu veya Laktat Eşik temposu değerlendirilir."
        )

        # 4. Deload Analizi
        needs_deload = (acwr > 1.35) or (stress > 48.0) or (rhr > 60.0)
        deload_status = "GEREKMİYOR (Kondisyon Yüksek)" if not needs_deload else "DİKKAT: DELOAD ÖNERİLİR"
        deload_note = (
            "Toparlanma ve ACWR göstergeleri güvenli bantta; planlı kota seanslarını güvenle uygulayabilirsiniz."
            if not needs_deload else
            "Yorgunluk/stres sinyali yüksek; bu hafta kota hacmini %40 düşürüp aktif dinlenmeye öncelik verin."
        )

        return {
            "current_tier_label": f"Kuvvet: Temel Güç İnşası ({squat_ratio:.2f}x VA) · Koşu: Orta Seviye (VO2 {vo2max:.1f})",
            "volume_progression": {
                "verdict": volume_verdict,
                "can_increase_days": can_increase_days,
                "current_days": "2 Koşu + 2 Gym (Esnek 4 Seans Kotası)",
                "next_level_days": next_level_days,
                "advice": volume_advice,
            },
            "style_transition": {
                "verdict": style_verdict,
                "current_style": f"A/B Full Body 5x5 (Squat {squat_pr:.0f} kg · Bench {bench_pr:.0f} kg · DL {deadlift_pr:.0f} kg)",
                "suggested_next_style": "Önce 5x5 ile 1.0x VA (~85 kg), Sonra Upper/Lower",
                "advice": style_advice,
                "running_style_advice": running_style_advice,
            },
            "running_progression": {
                "verdict": "ORTA SEVİYE AEROBİK TABAN (80/20 Polarize)",
                "current_metrics": f"VO2 Max: {vo2max:.1f} · En İyi 5K: {latest_5k} · Kadans: {cadence} spm",
                "load_balance": f"Düşük Aer: %{low_pct:.0f} · Yüksek Aer: %{high_pct:.0f} · Anaerobik: %{an_pct:.0f}",
                "current_model": "Haftada 2 Koşu: 1x 5K Hız İntervali (4x1000m @ 5:15/km) + 1x Zone 2 Taban (45-50 dk @ 140-150 bpm)",
                "next_milestone": "Kısa Vade: 5K < 27:00 & Zone 2 @ 6:00 /km · Orta Vade: 5K < 24:30 (4:54 /km)",
                "advice": running_style_advice,
            },
            "fatigue_and_deload": {
                "status": deload_status,
                "needs_deload": needs_deload,
                "note": deload_note,
            },
            "athlete_levels": ATHLETE_LEVELS_FRAMEWORK,
            "triggers": DYNAMIC_PROGRESSION_TRIGGERS,
        }

    def get_post_workout_debrief(self, activity_idx: int = 0) -> Dict[str, Any]:
        """Seçili aktivite için canlı yük, HRV/uyku, aynı branş HR kıyası, tonaj ve kalan esnek kotayı döner."""
        acts = self.get_all_activities()
        if not acts:
            return {}

        idx = max(0, min(activity_idx, len(acts) - 1))
        act = acts[idx]
        sport = act.get("sport")
        sport_tr = format_sport_tr(sport, act.get("name") or "")
        act_date = act.get("date")

        prev_same = next((a for a in acts[idx + 1:] if a.get("sport") == sport), None)
        tl = self.get_training_load_analytics()
        cur_status = tl.get("current_status", {})
        load_focus = tl.get("load_focus", {})
        daily = self.get_latest_metrics()

        hr_comparison: Dict[str, Any] = {}
        if prev_same:
            avg_diff = int((act.get("avg_hr") or 0) - (prev_same.get("avg_hr") or 0))
            max_diff = int((act.get("max_hr") or 0) - (prev_same.get("max_hr") or 0))
            dur_diff = round((act.get("dur_m") or 0) - (prev_same.get("dur_m") or 0), 1)
            load_diff = round((act.get("load") or 0) - (prev_same.get("load") or 0), 1)
            ef_txt = f" (Kardiyak Verimlilik EF: {act.get('ef_spd')} m/atım)" if act.get("ef_spd") else ""

            if sport == "strength_training":
                insight = (
                    f"Önceki seansa ({prev_same.get('date')}) kıyasla ortalama nabız {abs(avg_diff)} bpm daha düşük "
                    f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm). Set arası parasempatik toparlanma daha verimli."
                    if avg_diff <= 0 else
                    f"Önceki gym seansına ({prev_same.get('date')}) kıyasla ortalama nabız {avg_diff} bpm daha yüksek "
                    f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm); mekanik yoğunluk arttı."
                )
            elif sport == "running":
                insight = (
                    f"Önceki koşuya ({prev_same.get('date')}) göre ortalama nabız {abs(avg_diff)} bpm daha düşük "
                    f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm){ef_txt}."
                    if avg_diff <= 0 else
                    f"Önceki koşuya ({prev_same.get('date')}) göre ortalama nabız {avg_diff} bpm daha yüksek "
                    f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm){ef_txt}."
                )
            else:
                insight = f"Önceki {sport_tr} seansına ({prev_same.get('date')}) kıyasla ortalama nabız farkı: {avg_diff:+d} bpm."

            hr_comparison = {
                "previous_date": prev_same.get("date"),
                "previous_name": prev_same.get("name"),
                "previous_avg_hr": prev_same.get("avg_hr"),
                "previous_max_hr": prev_same.get("max_hr"),
                "previous_dur_m": round(prev_same.get("dur_m") or 0, 1),
                "previous_load": round(prev_same.get("load") or 0, 1),
                "avg_hr_diff": avg_diff,
                "max_hr_diff": max_diff,
                "dur_diff_min": dur_diff,
                "load_diff": load_diff,
                "insight": insight,
            }

        gym_prog: Dict[str, Any] = {}
        if sport == "strength_training":
            gym_data = self.get_gym_exercise_history()
            sessions = gym_data.get("sessions", [])
            cur_sess = next((s for s in sessions if s.get("date") == act_date), sessions[0] if sessions else None)
            if cur_sess:
                prev_sess = next((s for s in sessions if s.get("date") < cur_sess.get("date")), None)
                prev_same_type = next(
                    (s for s in sessions if s.get("date") < cur_sess.get("date") and s.get("workout_type") == cur_sess.get("workout_type")),
                    None,
                )
                vol_cur = cur_sess.get("total_volume_kg", 0)
                vol_prev = prev_sess.get("total_volume_kg", 0) if prev_sess else 0
                vol_prev_same = prev_same_type.get("total_volume_kg", 0) if prev_same_type else 0
                gym_prog = {
                    "workout_type": cur_sess.get("workout_type"),
                    "current_volume_kg": vol_cur,
                    "current_tonnage": round(vol_cur / 1000.0, 2),
                    "prev_session_date": prev_sess.get("date") if prev_sess else None,
                    "prev_session_type": prev_sess.get("workout_type") if prev_sess else None,
                    "prev_session_volume_kg": vol_prev,
                    "volume_delta_kg": round(vol_cur - vol_prev, 1) if prev_sess else 0,
                    "prev_same_type_date": prev_same_type.get("date") if prev_same_type else None,
                    "prev_same_type_volume_kg": vol_prev_same,
                    "same_type_volume_delta_kg": round(vol_cur - vol_prev_same, 1) if prev_same_type else 0,
                    "exercises": cur_sess.get("exercises", []),
                    "progression_milestones": gym_data.get("progression", {}),
                }

        status_code = cur_status.get("status_code", "MAINTAINING_3")
        status_tr = cur_status.get("status_tr", "Form Korunuyor (Maintaining)")
        session_load = round(act.get("load") or 0, 1)
        acute_load = cur_status.get("acute_load", 279)
        chronic_load = cur_status.get("chronic_load", 279)
        acwr = float(cur_status.get("acwr") or 1.0)
        tunnel_min = float(cur_status.get("tunnel_min") or 200.0)
        tunnel_max = float(cur_status.get("tunnel_max") or 340.0)
        vo2_val = daily.get("vo2max", 45.4)

        # Son günün canlı uyku / Body Battery / stres değerleri
        latest_row = self.df.iloc[-1] if hasattr(self, "df") and not self.df.empty else {}
        deep_h = float(latest_row.get("deep_h") or 1.3)
        rem_h = float(latest_row.get("rem_h") or 1.4)
        sleep_h_total = float(daily.get("sleep_hours") or 7.0) or 7.0
        deep_pct = round(deep_h / sleep_h_total * 100) if sleep_h_total > 0 else 20
        rem_pct = round(rem_h / sleep_h_total * 100) if sleep_h_total > 0 else 20
        sleep_stages_txt = f"Derin: {int(deep_h)}s {int((deep_h % 1) * 60)}dk (%{deep_pct}), REM: {int(rem_h)}s {int((rem_h % 1) * 60)}dk (%{rem_pct})"
        bb_wake = int(latest_row.get("bb_wake") or 78) if latest_row.get("bb_wake") == latest_row.get("bb_wake") else 78
        bb_low = int(latest_row.get("bb_low") or 25) if latest_row.get("bb_low") == latest_row.get("bb_low") else 25
        stress_latest = int(latest_row.get("avg_stress") or daily.get("stress") or 25) if (latest_row.get("avg_stress") or daily.get("stress")) else 25
        active_cals_latest = int(latest_row.get("active_kcal") or 340) if latest_row.get("active_kcal") == latest_row.get("active_kcal") else 340

        weekly_quota = self.get_weekly_quota_summary()
        rem_run_items = weekly_quota["running"]["remaining_items"]
        rem_gym_items = weekly_quota["strength"]["remaining_items"]

        if sport == "strength_training" and rem_run_items:
            next_item = rem_run_items[0]
        elif sport == "running" and rem_gym_items:
            next_item = rem_gym_items[0]
        elif rem_run_items:
            next_item = rem_run_items[0]
        elif rem_gym_items:
            next_item = rem_gym_items[0]
        else:
            next_item = None

        if next_item and next_item["category"] == "running":
            next_session_info = {
                "day": "Bu Hafta Esnek Kota · Toparlanmana Uygun Bir Gün",
                "title": f"{next_item['title']} ({next_item['duration']})",
                "target_hr": next_item["target_hr"],
                "target_pace": next_item["target_pace"],
                "purpose": f"{weekly_quota['headline']}. Toparlanmana ve programına göre uygun bir günde uygulayabilirsin.",
            }
        elif next_item and next_item["category"] == "strength":
            next_session_info = {
                "day": "Bu Hafta Esnek Kota · Toparlanmana Uygun Bir Gün",
                "title": f"{next_item['title']} ({next_item['duration']})",
                "target_hr": "115 - 130 bpm (Zone 1)",
                "target_pace": next_item["exercises_summary"],
                "purpose": f"{weekly_quota['headline']}. Bacak toparlanmana göre uygun bir günde kuvvet kotanı tamamlayabilirsin.",
            }
        else:
            next_session_info = {
                "day": "Haftalık 4/4 Kota Tamamlandı · Esnek Toparlanma",
                "title": "Aktif Toparlanma / Mobilite veya Spontane Branş",
                "target_hr": "<110 bpm (Zone 1)",
                "target_pace": "Hafif yürüyüş, esneme veya isteğe bağlı spontane branş",
                "purpose": f"{weekly_quota['headline']}. Sonraki Pazartesi temiz 0/2 kotasına taze başla.",
            }

        cur_w = float(daily.get("weight", 87.0))
        prot_g = round(cur_w * 2.0)

        run_cls = classify_run_workout(act) if sport == "running" else None
        workout_type_label = run_cls["label_tr"] if run_cls else (gym_prog.get("workout_type") or sport_tr)
        is_plan_dev = bool(run_cls and not run_cls["is_planned_archetype"])
        verdict_txt = (
            f"Plan Dışı {run_cls['label_tr']} Algılandı (TE: {run_cls['te_label']}, AnTE: {run_cls['an_te']}) • "
            "İnterval / Zone 2 Kotası Güncel Duruma Göre Yeniden Planlandı"
            if is_plan_dev else
            "Antrenman Başarıyla Kilitlendi • Süper-Kompanzasyon Başladı"
        )

        return {
            "activity": {
                "name": act.get("name"),
                "sport": sport,
                "sport_tr": sport_tr,
                "workout_type": workout_type_label,
                "is_plan_deviation": is_plan_dev,
                "date": act_date,
                "time": act.get("time", ""),
                "duration_min": round(act.get("dur_m") or 0, 1),
                "calories": act.get("cal", 0),
                "avg_hr": act.get("avg_hr"),
                "max_hr": act.get("max_hr"),
                "load": session_load,
                "aerobic_te": round(act.get("aTE") or 0, 1),
                "anaerobic_te": round(act.get("anTE") or 0, 1),
                "te_label": act.get("te_label", "TOPARLANMA"),
                "water_loss_ml": act.get("water_ml", 0),
            },
            "training_load": {
                "session_epoc_load": session_load,
                "acute_load": acute_load,
                "chronic_load": chronic_load,
                "acwr": acwr,
                "acwr_status": cur_status.get("acwr_status", "OPTIMAL (Sweet Spot)"),
                "tunnel_min": tunnel_min,
                "tunnel_max": tunnel_max,
                "in_sweet_spot": 0.8 <= acwr <= 1.3,
                "interpretation": (
                    f"Akut yük ({acute_load}) ve kronik yük ({chronic_load}) dengede (ACWR: {acwr:.2f}). "
                    f"Garmin Firstbeat yük tüneli ({tunnel_min:.0f} - {tunnel_max:.0f}) içindesiniz."
                ),
            },
            "productive_evaluation": {
                "status_code": status_code,
                "status_tr": status_tr,
                "is_productive": "PRODUCTIVE" in status_code,
                "status_reason": (
                    f"Akut ({acute_load}) / Kronik ({chronic_load}) dengesi (ACWR {acwr:.2f}) ve güncel VO2 Max ({vo2_val} mL/kg/dk) bazında durum '{status_tr}'."
                ),
                "how_to_reach_productive": load_focus.get("recommended_workout", "Anaerobik & VO2 Max İnterval (4x1000m @ Z4-5) ile barın orta bandındaki anaerobik odağı doldurun."),
                "load_focus": load_focus,
            },
            "daily_biometrics_24h": {
                "date": daily.get("date"),
                "weight_kg": cur_w,
                "total_loss_kg": daily.get("total_loss_kg", -8.0),
                "resting_hr_bpm": daily.get("resting_hr", 54),
                "overnight_hrv_ms": daily.get("overnight_hrv", 43.0),
                "hrv_7d_avg_ms": daily.get("hrv_7d", 46.0),
                "hrv_status": "Dengeli (Optimal Parasempatik Toparlanma)" if (daily.get("overnight_hrv") or 43) >= 38 else "Yük Altında (Dinlenme İzle)",
                "sleep_score": daily.get("sleep_score", 82.0),
                "sleep_hours": round(sleep_h_total, 2),
                "sleep_stages": sleep_stages_txt,
                "body_battery_wake": bb_wake,
                "body_battery_current": bb_low,
                "stress_score": stress_latest,
                "active_calories": active_cals_latest,
                "recovery_time_hours": daily.get("recovery_time_h", 5.5),
            },
            "hr_comparison_with_prev_same_sport": hr_comparison,
            "gym_volume_progression": gym_prog,
            "weekly_quota": weekly_quota,
            "executive_coaching_verdict": {
                "verdict": verdict_txt,
                "nutrition_action": f"{prot_g}g protein hedefi tamamlanmalı; toparlanma için kompleks karbonhidrat ve hidrasyon sağlanmalı.",
                "sleep_action": "Growth Hormone piki için 00:30 öncesi yatış (hedef 8+ saat uyku).",
                "next_session": next_session_info,
            },
        }
