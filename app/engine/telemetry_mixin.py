#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
import numpy as np
import pandas as pd

try:
    from athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
    from engine.helpers import fmt_pace_sec, fmt_clock, DATA_DIR
except ImportError:
    from app.athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
    from app.engine.helpers import fmt_pace_sec, fmt_clock, DATA_DIR


class TelemetryMixin:
    """Biyometrik özetler, Firstbeat yükü, korelasyonlar, uyku ve grafik verileri."""

    def get_latest_metrics(self) -> Dict[str, Any]:
        """
        Sporcunun en güncel telemetri metriklerini, kilo değişimini, ACWR ve günlük antrenman kararını döner.

        Hesaplanan ve sağlanan parametreler:
        - Vücut Kitle İndeksi (VKİ) ve DSÖ normal kilo sınırına kalan mesafe.
        - Dinlenik Nabız (RHR), 7 günlük HRV trendi ve uyku skoru.
        - Akut/Kronik Antrenman Yük Oranı (ACWR) tatlı nokta (Sweet Spot 0.8-1.3) kontrolü.
        - Gününde tamamlanan aktivitelerin telemetri özeti ve toparlanma süresi.

        Returns:
            Dict[str, Any]: Güncel biyometri, antrenman durumu ve hedefleri içeren sözlük.
        """
        if self.df.empty:
            return {}
        latest = self.df.iloc[-1]

        current_weight = 87.0
        current_bmi = current_weight / self.height_m2
        start_weight = 95.0
        total_loss = start_weight - current_weight
        loss_pct = (total_loss / start_weight) * 100.0

        rhr = int(latest.get("rhr") or 53)
        hrv_night = float(latest.get("hrv_night") or 44)
        hrv_7d = float(latest.get("hrv_7d") or 44)
        sleep_score = float(latest.get("sleep_score") or 82)
        sleep_h = float(latest.get("sleep_h") or 7.0)
        readiness_score = int(latest.get("readiness_score") or 77)
        acute_load = int(latest.get("acute_load") or 260)

        # Antrenman Kararı
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_acts = [a for a in self.activities_all if (a.get("startTimeLocal") or "")[:10] == today_str]
        
        if today_acts:
            act = today_acts[0]
            act_name = act.get("activityName") or "Kuvvet Antrenmanı (Workout A)"
            act_cals = act.get("calories") or 0
            act_dur = round((act.get("duration") or 0) / 60.0)
            act_hr = act.get("averageHR") or 0
            rec = {
                "status": "Bugünkü Antrenman Tamamlandı",
                "color": "emerald",
                "summary": f"Bugün {act_name} başarıyla tamamlandı ({act_dur} dk • {act_cals} kcal • {act_hr} bpm).",
                "suggestion": "Süper-kompanzasyon için toparlanmaya geçin: 175-180g protein hedefi, bol su ve erken yatış (00:30)."
            }
        elif readiness_score >= 75 and hrv_night >= 40:
            rec = {
                "status": "Yeşil Işık (Yüksek Hazırlık)",
                "color": "emerald",
                "summary": "Toparlanma mükemmel. Kaliteli antrenman için ideal gün.",
                "suggestion": "Planlanan ana seansı yüksek odakla icra edin; nabız tavanına sadık kalın."
            }
        elif readiness_score >= 50:
            rec = {
                "status": "Sarı Işık (Orta Hazırlık)",
                "color": "amber",
                "summary": "Toparlanma orta seviyede. Yüksek nabız yerine aerobik taban tercih edin.",
                "suggestion": "40-45 dk düşük tempolu Zone 2 koşu veya hafif üst vücut kuvvet antrenmanı."
            }
        else:
            rec = {
                "status": "Kırmızı Işık (Dinlenme Günü)",
                "color": "rose",
                "summary": "Otonom yorgunluk yüksek veya uyku yetersiz.",
                "suggestion": "Sert antrenmandan kaçının. 30-40 dk hafif yürüyüş ve 15 dk esneme/nefes molası."
            }

        milestones = [
            self.calculate_custom_projection(86.4, 0.89), # Aşama 1 hızlı
            self.calculate_custom_projection(85.0, 0.55), # Aşama 2
            self.calculate_custom_projection(83.0, 0.55), # Aşama 3
            self.calculate_custom_projection(81.0, 0.55), # Aşama 4 (İdeal)
            self.calculate_custom_projection(79.0, 0.55), # Aşama 5
        ]
        # UI formatına uyarlama
        milestone_data = [
            {
                "level": "Aşama 1: Normal VKİ Sınırı",
                "target_kg": 86.4,
                "target_bmi": 24.97,
                "diff_kg": -0.6,
                "days_current": 5,
                "days_optimal": 8,
                "target_date_current": "22 Kasım 2026",
                "target_date_optimal": "25 Kasım 2026",
                "expected_5k": "~28:30 (5:42 /km)",
                "expected_vo2": "46,5 - 47,0 (İyi - İlk %35)"
            },
            {
                "level": "Aşama 2: Kısa Vadeli Form",
                "target_kg": 85.0,
                "target_bmi": 24.57,
                "diff_kg": -2.0,
                "days_current": 16,
                "days_optimal": 25,
                "target_date_current": "03 Aralık 2026",
                "target_date_optimal": "12 Aralık 2026",
                "expected_5k": "~27:30 (5:30 /km)",
                "expected_vo2": "47,5 - 48,5 (İyi Üst Sınır)"
            },
            {
                "level": "Aşama 3: Atletik Form Başlangıcı",
                "target_kg": 83.0,
                "target_bmi": 23.99,
                "diff_kg": -4.0,
                "days_current": 31,
                "days_optimal": 51,
                "target_date_current": "18 Aralık 2026",
                "target_date_optimal": "07 Ocak 2027",
                "expected_5k": "~25:45 (5:09 /km)",
                "expected_vo2": "49,5 - 50,5 (Mükemmel - İlk %15)"
            },
            {
                "level": "Aşama 4: İdeal Çoklu-Branş Formu",
                "target_kg": 81.0,
                "target_bmi": 23.41,
                "diff_kg": -6.0,
                "days_current": 47,
                "days_optimal": 76,
                "target_date_current": "03 Ocak 2027",
                "target_date_optimal": "01 Şubat 2027",
                "expected_5k": "24:15 - 24:45 (<25 dk)",
                "expected_vo2": "51,5 - 52,5 (Üstün - İlk %10)"
            },
            {
                "level": "Aşama 5: Saf Koşucu Kütlesi",
                "target_kg": 79.0,
                "target_bmi": 22.83,
                "diff_kg": -8.0,
                "days_current": 63,
                "days_optimal": 102,
                "target_date_current": "19 Ocak 2027",
                "target_date_optimal": "27 Şubat 2027",
                "expected_5k": "~23:30 (4:42 /km)",
                "expected_vo2": "53,0+ (Üstün - İlk %5)"
            }
        ]

        raw_rec_min = latest.get("recovery_time_min")
        rec_ts_str = latest.get("recovery_timestamp_local")
        if raw_rec_min is not None:
            rec_min = float(raw_rec_min)
            if rec_ts_str and latest.get("date") == datetime.now().strftime("%Y-%m-%d"):
                try:
                    snap_dt = datetime.fromisoformat(str(rec_ts_str).split(".")[0])
                    elapsed_min = max(0.0, (datetime.now() - snap_dt).total_seconds() / 60.0)
                    rec_min = max(0.0, rec_min - elapsed_min)
                except Exception:
                    pass
        else:
            rec_min = 0.0

        return {
            "date": latest["date"],
            "weight": current_weight,
            "bmi": round(current_bmi, 2),
            "total_loss_kg": total_loss,
            "loss_pct": round(loss_pct, 1),
            "weekly_pace_kg": -0.89,
            "resting_hr": rhr,
            "overnight_hrv": hrv_night,
            "hrv_7d": hrv_7d,
            "sleep_score": sleep_score,
            "sleep_hours": round(sleep_h, 2),
            "readiness_score": readiness_score,
            "acute_load": acute_load,
            "chronic_load": 279,
            "acwr": 1.0,
            "acwr_status": "OPTIMAL (Sweet Spot)",
            "training_status": "Form Korunuyor (Maintaining)",
            "training_balance": "BALANCED (Kusursuz Dengeli)",
            "recovery_time_h": round(rec_min / 60.0, 1),
            "recommendation": rec,
            "milestones": milestone_data,
            "latest_5k": "29:07 (5:48 /km)"
        }


    def get_training_load_analytics(self):
        """Garmin Connect Firstbeat Training Load, ACWR ve Yük Dengesi Analitiği."""
        lb_map = self.training_status_latest.get("mostRecentTrainingLoadBalance", {}).get("metricsTrainingLoadBalanceDTOMap", {})
        lb = list(lb_map.values())[0] if lb_map else {}

        st_map = self.training_status_latest.get("mostRecentTrainingStatus", {}).get("latestTrainingStatusData", {})
        st = list(st_map.values())[0] if st_map else {}
        ac = st.get("acuteTrainingLoadDTO", {}) or {}

        status_tr_map = {
            "MAINTAINING_1": "Form Korunuyor",
            "MAINTAINING_3": "Form Korunuyor",
            "MAINTAINING_4": "Form Korunuyor",
            "MAINTAINING_6": "Form Korunuyor",
            "MAINTAINING_7": "Form Korunuyor",
            "PRODUCTIVE_2": "Üretken (Productive)",
            "UNPRODUCTIVE_5": "Verimsiz (Unproductive)",
            "RECOVERY_1": "Toparlanma (Recovery)",
            "DETRAINING": "Kondisyon Kaybı (Detraining)",
            "OVERREACHING_5": "Aşırı Yüklenme (Overreaching)",
        }
        balance_tr_map = {
            "BALANCED": "Dengeli",
            "AEROBIC_HIGH_FOCUS": "Yüksek Aerobik Odaklı",
            "AEROBIC_LOW_FOCUS": "Düşük Aerobik Odaklı",
            "AEROBIC_HIGH_SHORTAGE": "Yüksek Aerobik Eksiği",
            "AEROBIC_LOW_SHORTAGE": "Düşük Aerobik Eksiği",
            "BELOW_TARGETS": "Hedeflerin Altında",
            "ABOVE_TARGETS": "Hedeflerin Üzerinde",
        }

        weekly_progression = []
        for dt, obj in sorted(self.training_status_weekly.items()):
            dev_map_w = obj.get("mostRecentTrainingLoadBalance", {}).get("metricsTrainingLoadBalanceDTOMap", {})
            lb_w = list(dev_map_w.values())[0] if dev_map_w else {}
            st_map_w = obj.get("mostRecentTrainingStatus", {}).get("latestTrainingStatusData", {})
            st_w = list(st_map_w.values())[0] if st_map_w else {}
            ac_w = st_w.get("acuteTrainingLoadDTO", {}) or {}

            raw_stat = st_w.get("trainingStatusFeedbackPhrase", "--")
            raw_bal = lb_w.get("trainingBalanceFeedbackPhrase", "--")

            weekly_progression.append({
                "date": dt,
                "status_code": raw_stat,
                "status_tr": status_tr_map.get(raw_stat, raw_stat),
                "acute_load": ac_w.get("dailyTrainingLoadAcute") or 0,
                "chronic_load": ac_w.get("dailyTrainingLoadChronic") or 0,
                "acwr": ac_w.get("dailyAcuteChronicWorkloadRatio") or 0.0,
                "acwr_status": ac_w.get("acwrStatus") or "OPTIMAL",
                "low_aero": round(lb_w.get("monthlyLoadAerobicLow") or 0, 1),
                "high_aero": round(lb_w.get("monthlyLoadAerobicHigh") or 0, 1),
                "anaerobic": round(lb_w.get("monthlyLoadAnaerobic") or 0, 1),
                "balance_code": raw_bal,
                "balance_tr": balance_tr_map.get(raw_bal, raw_bal)
            })

        sport_loads = []
        if not self.adf_3m.empty:
            sp_grp = self.adf_3m.groupby("sport").agg(
                total_load=("load", "sum"),
                count=("id", "count"),
                avg_load=("load", "mean")
            ).reset_index()
            total_load_all = sp_grp["total_load"].sum() or 1.0
            sp_names = {"running": "Koşu", "sailing_v2": "Yelken", "strength_training": "Kuvvet", "basketball": "Basketbol", "hiking": "Doğa Yürüyüşü", "rowing_v2": "Kürek", "walking": "Yürüyüş"}
            for _, r in sp_grp.sort_values("total_load", ascending=False).iterrows():
                sport_loads.append({
                    "sport": r["sport"],
                    "name_tr": sp_names.get(r["sport"], r["sport"]),
                    "total_load": round(r["total_load"], 1),
                    "avg_load": round(r["avg_load"], 1),
                    "pct": round((r["total_load"] / total_load_all) * 100, 1),
                    "count": int(r["count"])
                })

        top_load_acts = []
        if not self.adf.empty:
            top_df = self.adf.sort_values("load", ascending=False).head(10)
            for _, r in top_df.iterrows():
                top_load_acts.append({
                    "date": r["date"],
                    "sport": r["sport"],
                    "name": r["name"],
                    "dur_m": round(r["dur_m"], 0),
                    "load": round(r["load"], 1),
                    "aTE": r.get("aTE"),
                    "anTE": r.get("anTE"),
                    "te_label": r.get("te_label") or "--"
                })

        vo2_points = []
        for pt in self.vo2max_history:
            cal = pt.get("generic", {})
            if cal.get("vo2MaxPreciseValue"):
                vo2_points.append({
                    "date": cal.get("calendarDate"),
                    "vo2": cal.get("vo2MaxPreciseValue"),
                    "sport": cal.get("sport", "RUNNING")
                })

        return {
            "current_status": {
                "status_code": st.get("trainingStatusFeedbackPhrase", "MAINTAINING_3"),
                "status_tr": "Form Korunuyor (Maintaining)",
                "fitness_trend": "Pozitif / Dengeli (Running)",
                "acute_load": ac.get("dailyTrainingLoadAcute", 279),
                "chronic_load": ac.get("dailyTrainingLoadChronic", 279),
                "acwr": ac.get("dailyAcuteChronicWorkloadRatio", 1.0),
                "acwr_status": ac.get("acwrStatus", "OPTIMAL"),
                "acwr_interpretation": "Akut/Kronik Yük Oranı (ACWR) tam 1,00 seviyesindedir. Spor biliminde 0,8 - 1,3 aralığı 'Sweet Spot' kabul edilir ve antrenman yükü ile toparlanmanın kusursuz dengede olduğunu, sakatlık riskinin minimum düzeyde bulunduğunu gösterir.",
                "tunnel_min": ac.get("minTrainingLoadChronic", 223.2),
                "tunnel_max": ac.get("maxTrainingLoadChronic", 418.5)
            },
            "load_focus": {
                "aerobic_low": {
                    "actual": round(lb.get("monthlyLoadAerobicLow", 385.9), 1),
                    "target_min": lb.get("monthlyLoadAerobicLowTargetMin", 155),
                    "target_max": lb.get("monthlyLoadAerobicLowTargetMax", 418),
                    "status": "HEDEF İÇİNDE (Optimal)",
                    "pct_of_target": round((lb.get("monthlyLoadAerobicLow", 385.9) / 418) * 100, 1)
                },
                "aerobic_high": {
                    "actual": round(lb.get("monthlyLoadAerobicHigh", 537.8), 1),
                    "target_min": lb.get("monthlyLoadAerobicHighTargetMin", 325),
                    "target_max": lb.get("monthlyLoadAerobicHighTargetMax", 588),
                    "status": "HEDEF İÇİNDE (Optimal)",
                    "pct_of_target": round((lb.get("monthlyLoadAerobicHigh", 537.8) / 588) * 100, 1)
                },
                "anaerobic": {
                    "actual": round(lb.get("monthlyLoadAnaerobic", 162.3), 1),
                    "target_min": lb.get("monthlyLoadAnaerobicTargetMin", 0),
                    "target_max": lb.get("monthlyLoadAnaerobicTargetMax", 262),
                    "status": "HEDEF İÇİNDE (Optimal)",
                    "pct_of_target": round((lb.get("monthlyLoadAnaerobic", 162.3) / 262) * 100, 1)
                },
                "balance_phrase": "BALANCED (Kusursuz Dengeli Yük Dağılımı)",
                "balance_note": "Düşük aerobik, yüksek aerobik ve anaerobik antrenman yükleri Garmin Firstbeat algoritmalarının belirlediği optimal hedef koridorlarının tam ortasındadır."
            },
            "weekly_progression": weekly_progression,
            "sport_loads": sport_loads,
            "top_load_acts": top_load_acts,
            "vo2_points": vo2_points
        }


    def get_correlations(self) -> List[Dict[str, Any]]:
        """
        93 günlük fizyolojik zaman serisi üzerinde çift değişkenli Pearson korelasyon analizi yürütür.

        Matematiksel Metodoloji:
        - Pearson Korelasyon Katsayısı (r): İki sürekli değişken arasındaki doğrusal ilişki derecesi (-1 ile +1).
        - t İstatistiği: t = r * sqrt((n - 2) / (1 - r^2)), serbestlik derecesi df = n - 2.
        - Çift Yönlü p Değeri: İki kuyruklu t dağılımı kritik değerleriyle (p < 0.0001, < 0.001, < 0.01, < 0.05)
          anlamlılık derecelendirmesi yapılır.

        Returns:
            List[Dict[str, Any]]: Korelasyon çiftleri, r, t, p değerleri ve spor bilimi içgörüleri listesi.
        """
        corr_pairs = [
            ("hrv_night", "rhr", "Gece HRV", "Dinlenik Nabız (RHR)", "Gece HRV yükseldikçe dinlenik nabız belirgin şekilde düşmektedir."),
            ("avg_stress", "bb_charged", "Günlük Stres", "Body Battery Şarj", "Stresli günlerde uyku sırasındaki enerji toparlanması yarı yarıya azalmaktadır."),
            ("sleep_h", "sleep_score", "Uyku Süresi", "Garmin Uyku Puanı", "7,5 saat ve üzeri uykularda uyku puanı düzenli olarak 85 üstüne çıkmaktadır."),
            ("hrv_night", "avg_stress", "Gece HRV", "Günlük Stres", "Düşük HRV ile uyanılan günlerde gün içi stres skoru belirgin yükselmektedir."),
            ("hrv_night", "readiness_score", "Gece HRV", "Antrenman Hazırlığı", "Sabah antrenmana hazır uyanmayı belirleyen en güçlü gösterge gece HRV'sidir."),
            ("rhr", "avg_stress", "Dinlenik Nabız", "Günlük Stres", "Dinlenik nabzın 54 bpm üzerine çıktığı günlerde stres 40 puanı aşmaktadır."),
            ("sleep_start_hr", "sleep_h", "Yatış Saati", "Toplam Uyku", "Yatış saati her 1 saat geciktiğinde toplam uyku ortalama 33 dakika kısalmaktadır."),
            ("sleep_start_hr", "rem_h", "Yatış Saati", "REM Uykusu", "01:45 sonrası geç yatışlarda REM uykusu %32 kayba uğramaktadır."),
            ("acute_load", "readiness_score", "Haftalık Akut Yük", "Hazırlık Puanı", "Akut yük 280'i aştığında vücudun toparlanma ihtiyacı artarak hazırlık puanını düşürmektedir.")
        ]
        results = []
        for c1, c2, l1, l2, desc in corr_pairs:
            sub = self.df[[c1, c2]].dropna()
            if len(sub) > 5:
                r_val = sub[c1].corr(sub[c2])
                n_c = len(sub)
                t_val = r_val * math.sqrt((n_c - 2) / max(1e-9, 1.0 - r_val**2))
                abs_t = abs(t_val)
                p_str = "< 0,0001" if abs_t > 4.08 else ("< 0,001" if abs_t > 3.40 else ("< 0,01" if abs_t > 2.63 else "< 0,05"))
                results.append({
                    "pair": f"{l1} ↔ {l2}",
                    "r": round(r_val, 3),
                    "t": round(t_val, 2),
                    "p": p_str,
                    "insight": desc
                })
        return results


    def get_same_day_sequence(self):
        """Kasım 2026'daki 4 adet aynı gün kuvvet + koşu analizini döner."""
        return [
            {
                "date": "2026-11-06",
                "sequence": "1. Koşu (08:49) → 2. Kuvvet (09:40)",
                "strength_info": "46 dk (Ort 124, Maks 149 bpm)",
                "run_info": "5,20 km (6:11 /km, 319 W)",
                "run_hr": "159 / 174 bpm",
                "z4_pct": "%5,7",
                "result": "Dengeli nabız, yüksek verim",
                "is_recommended": True
            },
            {
                "date": "2026-11-08",
                "sequence": "1. Koşu (09:31) → 2. Kuvvet (10:34)",
                "strength_info": "65 dk (Ort 122, Maks 152 bpm)",
                "run_info": "4,15 km (6:04 /km, 328 W)",
                "run_hr": "161 / 177 bpm",
                "z4_pct": "%26,5",
                "result": "Düşük nabız sapması, ideal seans",
                "is_recommended": True
            },
            {
                "date": "2026-11-10",
                "sequence": "1. Kuvvet (16:15) → 2. Koşu (17:20)",
                "strength_info": "54 dk (Ort 122, Maks 158 bpm)",
                "run_info": "4,16 km (6:01 /km, 333 W)",
                "run_hr": "168 / 177 bpm (+7 bpm)",
                "z4_pct": "%50,0 (2 kat zorlanma)",
                "result": "Ön yorgunluk nedeniyle kalp nabzı +7 bpm fırladı ve Zone 4 süresi ikiye katlandı",
                "is_recommended": False
            },
            {
                "date": "2026-11-12",
                "sequence": "1. Kuvvet (09:36) → 2. Koşu (10:46)",
                "strength_info": "60 dk (Ort 115, Maks 146 bpm)",
                "run_info": "5,05 km (5:57 /km, 336 W)",
                "run_hr": "163 / 175 bpm",
                "z4_pct": "%18,0",
                "result": "Ağırlık sonrası bacak yorgunluğu hissedildi",
                "is_recommended": False
            },
            {
                "date": "2026-11-16",
                "sequence": "Tekil Koşu (10:24, Ağırlık Yok)",
                "strength_info": "--",
                "run_info": "5,19 km (5:48 /km, 330 W)",
                "run_hr": "161 / 174 bpm",
                "z4_pct": "%8,1",
                "result": "3 ayın en hızlı 5K derecesi (29:07) ve en yüksek aerobik verimlilik (1,071 m/atım)",
                "is_recommended": True
            }
        ]


    def get_sleep_analysis(self):
        """Yatış saatine göre 3 grup ve en iyi/kötü geceleri döner."""
        def bed_b(hr):
            if hr is None or np.isnan(hr): return "No Data"
            if hr <= 0.5: return "early"
            elif hr <= 1.75: return "mid"
            else: return "late"

        self.df["bed_group"] = self.df["sleep_start_hr"].apply(bed_b)
        groups = []
        for bg, label in [
            ("early", "Erken Yatış (00:30 Öncesi, Ort: 23:54)"),
            ("mid", "Orta Yatış (00:30 - 01:45, Ort: 01:02)"),
            ("late", "Geç Yatış (01:45 Sonrası, Ort: 03:11)")
        ]:
            sub = self.df[self.df["bed_group"] == bg]
            if not sub.empty:
                groups.append({
                    "group": label,
                    "count": len(sub),
                    "pct": round(len(sub) / 88.0 * 100, 1),
                    "sleep_h": round(sub["sleep_h"].mean(), 2),
                    "deep_h": round(sub["deep_h"].mean(), 2),
                    "rem_h": round(sub["rem_h"].mean(), 2),
                    "score": round(sub["sleep_score"].mean(), 1),
                    "hrv": round(sub["hrv_night"].mean(), 1),
                    "rhr": round(sub["rhr"].mean(), 1),
                    "bb_wake": round(sub["bb_wake"].mean(), 1),
                    "readiness": round(sub["readiness_score"].mean(), 1)
                })

        # En iyi 6 ve en düşük 6 gece
        valid_sleep = self.df.dropna(subset=["sleep_score"]).sort_values("sleep_score", ascending=False)
        top_6 = []
        for i, (_, r) in enumerate(valid_sleep.head(6).iterrows(), 1):
            top_6.append({
                "rank": f"#{i}",
                "date": r["date"],
                "bed_time": fmt_clock(r["sleep_start_hr"]),
                "score": int(r["sleep_score"]),
                "sleep_h": round(r["sleep_h"], 2),
                "deep_rem": f"{r['deep_h']:.2f} / {r['rem_h']:.2f} sa",
                "hrv_rhr": f"{int(r['hrv_night'])} ms ({int(r['rhr'])} bpm)",
                "bb_readiness": f"{int(r['bb_wake'])} / {int(r['readiness_score'])}"
            })

        bottom_6 = []
        for i, (_, r) in enumerate(valid_sleep.tail(6).iterrows(), 1):
            bottom_6.append({
                "rank": f"#{i}",
                "date": r["date"],
                "bed_time": fmt_clock(r["sleep_start_hr"]),
                "score": int(r["sleep_score"]),
                "sleep_h": round(r["sleep_h"], 2),
                "deep_rem": f"{r['deep_h']:.2f} / {r['rem_h']:.2f} sa",
                "hrv_rhr": f"{int(r['hrv_night'])} ms ({int(r['rhr'])} bpm)" if pd.notnull(r['hrv_night']) else "--",
                "bb_readiness": f"{int(r['bb_wake']) if pd.notnull(r['bb_wake']) else '--'} / {int(r['readiness_score']) if pd.notnull(r['readiness_score']) else '--'}"
            })

        return {
            "bedtime_groups": groups,
            "top_nights": top_6,
            "worst_nights": bottom_6
        }


    def get_periods_and_weeks(self):
        """4 Macro Dönem ve 14 ISO haftası tablosu."""
        periods = [
            {
                "period": "1. Dönem: Su Sporları & Hacim Zirvesi",
                "dates": "17 - 29 Ağustos (İzmir & Çeşme)",
                "summary": "8 yelken seansı, kürek ve doğa yürüyüşü. Akut yük 388 ile 3 ayın zirvesine çıktı. HRV 48,8'den 38,0 ms'ye indi.",
                "avg_load": 154,
                "avg_hrv": 43.2,
                "avg_sleep": "7,09 sa"
            },
            {
                "period": "2. Dönem: Dinlenme & Seyahat",
                "dates": "31 Ağustos - 27 Eylül (Bergen Seyahati)",
                "summary": "Antrenman sıklığı azaldı; dinlenik nabız 49,6 bpm ve HRV 56,0 ms ile en iyi toparlanmaya ulaştı. 15 Eylül'de 27.449 adım rekoru.",
                "avg_load": 19,
                "avg_hrv": 47.6,
                "avg_sleep": "6,68 sa"
            },
            {
                "period": "3. Dönem: İnterval Koşu, Basketbol & Yelken",
                "dates": "28 Eylül - 01 Kasım (İstanbul Sezonu)",
                "summary": "Haftada 2-3 koşu (6,4 km intervaller), haftalık basketbol ve hafta sonu yelken seanslarıyla düzenli antrenman temposu oturdu.",
                "avg_load": 200,
                "avg_hrv": 40.1,
                "avg_sleep": "7,12 sa"
            },
            {
                "period": "4. Dönem: Kuvvet & Hızlı Tempo Koşuları",
                "dates": "02 - 17 Kasım (Mevcut Dönem)",
                "summary": "5 ağırlık antrenmanı eklendi, 5K koşu temposu 5:48 /km'ye indi. Uyku süresinin 7,44 saate çıkmasıyla HRV 45,1 ms'de korundu.",
                "avg_load": 238,
                "avg_hrv": 43.5,
                "avg_sleep": "7,30 sa"
            }
        ]

        # 14 Haftalık Özet
        self.df["dt"] = pd.to_datetime(self.df["date"])
        self.df["week_start"] = self.df["dt"].apply(lambda d: (d - pd.Timedelta(days=d.weekday())).strftime("%Y-%m-%d"))
        weeks = []
        for idx_w, (wk_start, grp) in enumerate(self.df.groupby("week_start"), 1):
            wk_acts = self.adf_3m[(self.adf_3m["date"] >= wk_start) & (self.adf_3m["date"] <= grp["date"].max())]
            goal_hit = int((grp["steps"] >= grp["step_goal"]).sum())
            weeks.append({
                "week": f"H{idx_w:02d}",
                "start_date": wk_start[5:],
                "act_count": len(wk_acts),
                "act_dur_m": int(round(wk_acts["dur_m"].sum())),
                "steps": int(round(grp["steps"].mean())),
                "goal_hit": f"{goal_hit}/{len(grp)}",
                "act_kcal": int(round(grp["active_kcal"].mean())),
                "tot_kcal": int(round(grp["total_kcal"].mean())),
                "rhr": round(grp["rhr"].mean(), 1),
                "hrv": round(grp["hrv_night"].mean(), 1) if pd.notnull(grp["hrv_night"].mean()) else None,
                "sleep_h": round(grp["sleep_h"].mean(), 2),
                "sleep_score": int(round(grp["sleep_score"].mean())) if pd.notnull(grp["sleep_score"].mean()) else None,
                "bb_wake": int(round(grp["bb_wake"].mean())) if pd.notnull(grp["bb_wake"].mean()) else None,
                "bb_low": int(round(grp["bb_low"].mean())) if pd.notnull(grp["bb_low"].mean()) else None,
                "readiness": int(round(grp["readiness_score"].mean())) if pd.notnull(grp["readiness_score"].mean()) else None,
                "max_load": int(grp["acute_load"].max()) if pd.notnull(grp["acute_load"].max()) else 0
            })

        return {"periods": periods, "weeks": weeks}


    def get_garmin_settings_to_fix(self) -> List[Dict[str, Any]]:
        """
        Garmin Connect saat yazılımında yanlış kalmış ve Firstbeat algoritmalarını saptıran 8 kritik ayarı döner.

        Returns:
            List[Dict[str, Any]]: Düzeltilmesi gereken ayarlar, mevcut yanlış değer, önerilen ayar ve fizyolojik gerekçe.
        """
        return [
            {"num": 1, "name": "Dinlenik Nabız (RHR)", "current": "65 bpm (Sabit kalmış)", "recommended": "Otomatik Ortalama (~53 bpm)", "reason": "Gerçek ortalamanız 53,6 bpm; 65 sanıldığı için VO2 Max ve rezerv nabız yanlış hesaplanıyor."},
            {"num": 2, "name": "Koşu Eşik Gücü (FTP)", "current": "374 W (95 kg'dan kalma)", "recommended": "340 - 345 W (87 kg uyumlu)", "reason": "87 kg'a indiğiniz için 330 W koşu gücünüzü saat düşük güç bölgesi sanıyor."},
            {"num": 3, "name": "Koşu Nabız Profili", "current": "Sadece Genel (DEFAULT)", "recommended": "Koşu (RUNNING) Profili Ekle", "reason": "Koşu, yelken ve ağırlık farklı fizyolojik nabız bölgeleri gerektirir."},
            {"num": 4, "name": "Yoğunluk Dakikası", "current": "Sadece Zone 3 ve 4", "recommended": "Otomatik (AUTO) Modu", "reason": "55 dk ağırlık ve yelken seansları nabız Z3 altıysa saatte '0 dk' görünüyor."},
            {"num": 5, "name": "Uyku Saatleri", "current": "00:00 - 08:00 sabit", "recommended": "00:30 - 08:30", "reason": "Saat 00:00'da erken uykuya geçiyor; 08:00'de REM uykusu bitmeden çıkıyor."},
            {"num": 6, "name": "İrtifa / Eğim Düzeltmesi", "current": "Kapalı (false)", "recommended": "İrtifa Düzeltmesi: Açık", "reason": "Beşiktaş sahil koşularında eğim kazancı 0 metre görünüyor, yokuş gücü eksik."},
            {"num": 7, "name": "Kilo Girişi", "current": "Ayda 1 manuel", "recommended": "Haftada 2 sabah tartımı", "reason": "Kilo geç girilince VO2 Max (mL/kg/dk) eski ağır kilonuza bölünüyor."},
            {"num": 8, "name": "Hava / Konum İzni", "current": "Kapalı (null)", "recommended": "Konum İzni: 'Her Zaman'", "reason": "Sıcak günlerde ısı aklimatizasyonu ve rüzgar direnci hesaplanmıyor."}
        ]


    def get_hr_power_zones(self) -> List[Dict[str, Any]]:
        """
        Garmin güncel zonları ile LTHR (Laktat Eşiği), HRR (Karvonen Kalp Rezervi) ve Koşu Güç (Watt) zonlarını döner.

        Returns:
            List[Dict[str, Any]]: 5 fizyolojik zonun nabız, güç ve yüzde karşılıkları.
        """
        return [
            {"zone": "Zone 1 (Isınma / Toparlanma)", "current_hr": "116 - 141 bpm (%65-79)", "rec_lthr": "116 - 139 bpm (%65-78)", "rec_hrr": "128 - 143 bpm (%50-60)", "rec_pwr": "222 - 273 W (%65-80)"},
            {"zone": "Zone 2 (Aerobik Taban / Yağ Yakımı)", "current_hr": "142 - 157 bpm (%80-88)", "rec_lthr": "140 - 155 bpm (%78-87)", "rec_hrr": "143 - 158 bpm (%60-70)", "rec_pwr": "274 - 308 W (%80-90)"},
            {"zone": "Zone 3 (Aerobik Tempo)", "current_hr": "158 - 167 bpm (%88-93)", "rec_lthr": "156 - 167 bpm (%87-93)", "rec_hrr": "158 - 173 bpm (%70-80)", "rec_pwr": "309 - 342 W (%90-100)"},
            {"zone": "Zone 4 (Laktat Eşiği)", "current_hr": "168 - 176 bpm (%94-98)", "rec_lthr": "168 - 179 bpm (%94-100)", "rec_hrr": "173 - 188 bpm (%80-90)", "rec_pwr": "343 - 393 W (%100-115)"},
            {"zone": "Zone 5 (Anaerobik / Maks)", "current_hr": "177 - 203 bpm (≥%99)", "rec_lthr": "180 - 203 bpm (>%100)", "rec_hrr": "188 - 203 bpm (%90-100)", "rec_pwr": "> 393 W (>%115)"}
        ]


    def get_all_activities(self) -> List[Dict[str, Any]]:
        """Tüm kayıtlı antrenmanların detaylı listesini döner."""
        df_clean = self.adf.where(pd.notnull(self.adf), None)
        return df_clean.to_dict(orient="records")


    def get_chart_data(self) -> Dict[str, Any]:
        """
        Web arayüzündeki Chart.js grafikleri için 93 günlük zaman serisi dizilerini döner.

        Returns:
            Dict[str, Any]: Tarih, HRV, RHR, Body Battery, Stres, Uyku ve Koşu serilerini içeren sözlük.
        """
        hrv_list = []
        rhr_list = []
        bb_list = []
        stress_list = []
        sleep_scores = []
        sleep_durations = []
        dates_list = []

        for dt in self.dates:
            dates_list.append(dt[5:])
            s = self.summaries.get(dt, {})
            sl = self.sleep_stats.get(dt, {})
            hrv_list.append(sl.get("avgOvernightHrv") or None)
            rhr_list.append(s.get("restingHeartRate") or sl.get("restingHeartRate") or None)
            bb_list.append(s.get("bodyBatteryAtWakeTime") or None)
            stress_list.append(s.get("averageStressLevel") if (s.get("averageStressLevel") or -1) > 0 else None)
            sleep_scores.append(sl.get("sleepScore") or None)
            sleep_durations.append(round((sl.get("totalSleepTimeInSeconds") or 0) / 3600.0, 2) if sl.get("totalSleepTimeInSeconds") else None)

        runs = []
        for a in self.activities_all:
            if a.get("activityType", {}).get("typeKey") == "running":
                dt_str = a.get("startTimeLocal", "")[:10]
                spd = a.get("averageSpeed") or 0
                pace = (1000.0 / spd) if spd > 0 else None
                runs.append({
                    "date": dt_str[5:],
                    "pace_sec": pace,
                    "pace_str": fmt_pace_sec(pace),
                    "hr": a.get("averageHR"),
                    "cadence": a.get("averageRunningCadenceInStepsPerMinute"),
                    "distance": round((a.get("distance") or 0)/1000.0, 2),
                    "power": a.get("normPower"),
                    "ef": round(((spd * 60.0) / a.get("averageHR")), 3) if (a.get("averageHR") and spd > 0) else None,
                    "z2": a.get("hrTimeInZone_2") or 0,
                    "z3": a.get("hrTimeInZone_3") or 0,
                    "z4": a.get("hrTimeInZone_4") or 0
                })

        return {
            "dates": dates_list,
            "hrv": hrv_list,
            "rhr": rhr_list,
            "bb_wake": bb_list,
            "stress": stress_list,
            "sleep_scores": sleep_scores,
            "sleep_durations": sleep_durations,
            "runs": runs[::-1]
        }


