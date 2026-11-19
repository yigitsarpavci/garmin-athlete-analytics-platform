#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temel Biyometrik Özetler, 93 Günlük Dinamik İstatistik Tablosu ve Firstbeat Yük Odak Analizi Mixin'i.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Any
import numpy as np
import pandas as pd

try:
    from engine.helpers import format_sport_tr, fmt_pace_sec, classify_sport_bucket
except ImportError:
    from app.engine.helpers import format_sport_tr, fmt_pace_sec, classify_sport_bucket


class TelemetryMixin:
    """Canlı metrikler, 93 günlük özet istatistikler, dinamik kilometre taşları ve ACWR yük analitiği."""

    def _compute_93d_biometrics_table(self) -> List[Dict[str, Any]]:
        """93 günlük DataFrame üzerinden 14 temel sağlık/biyometrik satırını canlı hesaplar."""
        if self.df.empty:
            return []

        def _fmt(v, dec=1, suffix=""):
            return f"{v:.{dec}f}{suffix}".replace(".", ",") if v is not None and not np.isnan(v) else "--"

        specs = [
            ("Günlük Adım Sayısı", "steps", 0, "", "8.000 – 12.000", "Günlük fiziksel hareket hacmi"),
            ("Günlük Mesafe", "dist_km", 2, " km", "7,0 – 12,0 km", "Koşu, yürüyüş ve diğer branş toplamı"),
            ("Günlük Harcama", "total_kcal", 0, " kcal", "2.800 – 3.200", "Bazal + aktif toplam enerji tüketimi"),
            ("Dinlenik Nabız (RHR)", "rhr", 1, " bpm", "48 – 56 bpm", "Düşük RHR güçlü kardiyak rezervi gösterir"),
            ("Gece HRV", "hrv_night", 1, " ms", "37 – 58 ms", "Parasempatik otonom denge göstergesi"),
            ("Günlük Ort. Stres", "avg_stress", 1, "", "25 – 35", "Gün içi sempatik yük puanı"),
            ("Sabah Body Battery", "bb_wake", 1, "", "75 – 100", "Gece uykusundan sonraki başlangıç rezervi"),
            ("Akşam Dip Enerji", "bb_low", 1, "", "15 – 30", "Gün sonu rezerv dibi"),
            ("Toplam Uyku Süresi", "sleep_h", 2, " sa", "7,5 – 8,5 sa", "Kas/sinir sistemi yenilenme süresi"),
            ("Derin Uyku Oranı", "deep_h", 1, "%", "%15 – %20", "Doku tamiri ve anabolik faz"),
            ("REM Uyku Oranı", "rem_h", 1, "%", "%20 – %25", "Bilişsel ve nörolojik toparlanma fazı"),
            ("Garmin Uyku Puanı", "sleep_score", 1, "", "80 – 100", "Genel uyku mimarisi skoru"),
            ("Gece SpO2", "spo2_avg", 1, "%", "%95 – %98", "Gece kandaki oksijen doygunluğu"),
            ("Antrenman Hazırlığı", "readiness_score", 1, "", "65 – 100", "Günlük antrenman yüküne tolerans puanı"),
        ]
        rows = []
        n_days = len(self.df)
        for label, col, dec, sfx, ref_rng, note in specs:
            if col not in self.df.columns:
                continue
            if col in ("deep_h", "rem_h") and "sleep_h" in self.df.columns:
                pair = self.df[[col, "sleep_h"]].apply(pd.to_numeric, errors="coerce").dropna()
                pair = pair[pair["sleep_h"] > 0.5]
                if pair.empty:
                    continue
                ser = (pair[col] / pair["sleep_h"]) * 100.0
            else:
                ser = pd.to_numeric(self.df[col], errors="coerce").dropna()
                if ser.empty:
                    continue
            mean_v = float(ser.mean())
            med_v = float(ser.median())
            min_v = float(ser.min())
            max_v = float(ser.max())
            extra_note = note
            if col == "steps" and "step_goal" in self.df.columns:
                goals = pd.to_numeric(self.df["step_goal"], errors="coerce").fillna(10000)
                steps_num = pd.to_numeric(self.df["steps"], errors="coerce").fillna(0)
                hit = int((steps_num >= goals).sum())
                pct = round(hit / max(1, n_days) * 100)
                extra_note = f"{n_days} günün {hit}'inde hedef aşıldı (%{pct})"
            elif col == "dist_km":
                extra_note = f"Toplam {ser.sum():,.1f} km kat edildi".replace(",", ".")
            elif col == "total_kcal" and "active_kcal" in self.df.columns:
                bmr_m = float(pd.to_numeric(self.df["bmr_kcal"], errors="coerce").mean() or 0)
                act_m = float(pd.to_numeric(self.df["active_kcal"], errors="coerce").mean() or 0)
                extra_note = f"Bazal {round(bmr_m)} + Aktif {round(act_m)} kcal ort."

            if dec == 0:
                avg_str = f"{int(round(mean_v)):,} ({int(round(med_v)):,})".replace(",", ".") + sfx
                rng_str = f"{int(round(min_v)):,} – {int(round(max_v)):,}".replace(",", ".") + sfx
            else:
                avg_str = f"{_fmt(mean_v, dec)} ({_fmt(med_v, dec)}){sfx}"
                rng_str = f"{_fmt(min_v, dec)} – {_fmt(max_v, dec)}{sfx}"
            rows.append({
                "metric": label,
                "avg_median": avg_str,
                "min_max": rng_str,
                "ideal_ref": ref_rng,
                "status": extra_note,
            })
        return rows

    def get_latest_metrics(self) -> Dict[str, Any]:
        """Sporcunun güncel kilo, HRV, uyku, Firstbeat ACWR, kilometre taşları ve günlük kararını döner."""
        if self.df.empty:
            return {}
        latest = self.df.iloc[-1]

        current_weight = round(float(self.get_current_weight() if hasattr(self, "get_current_weight") else 87.0), 1)
        start_weight = round(float(self.get_start_weight() if hasattr(self, "get_start_weight") else 95.0), 1)
        current_bmi = current_weight / self.height_m2
        total_loss = round(start_weight - current_weight, 1)
        loss_pct = (total_loss / start_weight) * 100.0 if start_weight > 0 else 0.0

        rhr = int(round(float(latest.get("rhr") or 53)))
        rhr_mean = round(float(self.df["rhr"].dropna().mean()), 1) if self.df["rhr"].notna().any() else float(rhr)
        hrv_night = float(latest.get("hrv_night") or 44)
        hrv_7d = float(latest.get("hrv_7d") or 44)
        sleep_score = float(latest.get("sleep_score") or 82)
        sleep_h = float(latest.get("sleep_h") or 7.0)
        sleep_h_mean = round(float(self.df["sleep_h"].dropna().mean()), 2) if self.df["sleep_h"].notna().any() else sleep_h
        deep_h = float(latest.get("deep_h") or 1.3)
        rem_h = float(latest.get("rem_h") or 1.4)
        deep_pct = round((deep_h / max(1.0, sleep_h)) * 100.0, 1)
        rem_sleep_pct = round((rem_h / max(1.0, sleep_h)) * 100.0, 1)

        def _num(val, default=0.0):
            return float(val) if val is not None and pd.notnull(val) else float(default)

        def _tail_stat(col, op="mean", n=7, default=0.0):
            if col not in self.df.columns:
                return float(default)
            ser = pd.to_numeric(self.df[col], errors="coerce").dropna().tail(n)
            if ser.empty:
                return float(default)
            return float(ser.sum() if op == "sum" else ser.mean())

        sleep_score_7d = round(_tail_stat("sleep_score", "mean", 7, sleep_score), 1)
        sleep_hours_7d = round(_tail_stat("sleep_h", "mean", 7, sleep_h), 2)
        if {"rem_h", "sleep_h"}.issubset(self.df.columns):
            rem_df = self.df[["rem_h", "sleep_h"]].apply(pd.to_numeric, errors="coerce").dropna()
            rem_df = rem_df[rem_df["sleep_h"] > 0].tail(7)
            rem_sleep_pct_7d = round(float(((rem_df["rem_h"] / rem_df["sleep_h"].clip(lower=1.0)) * 100.0).mean()), 1) if not rem_df.empty else rem_sleep_pct
        else:
            rem_sleep_pct_7d = rem_sleep_pct

        readiness_score = int(round(_num(latest.get("readiness_score"), 77)))
        readiness_7d_avg = round(_tail_stat("readiness_score", "mean", 7, readiness_score), 1)
        readiness_status = "Yüksek Hazırlık" if readiness_score >= 70 else ("Orta Hazırlık" if readiness_score >= 45 else "Toparlanma Gerekli")

        hrv_status = "Dengeli" if abs(hrv_night - hrv_7d) <= 6 else ("Yüksek Rezerv" if hrv_night > hrv_7d else "Baskılanmış")
        stress_latest = float(latest.get("avg_stress")) if pd.notnull(latest.get("avg_stress")) else round(_tail_stat("avg_stress", "mean", len(self.df), 28.4), 1)
        stress_7d_avg = round(_tail_stat("avg_stress", "mean", 7, stress_latest), 1)
        stress_status = "Düşük / Rahat" if stress_latest <= 25 else ("Normal / Dengeli" if stress_latest <= 38 else "Yüksek Stres")
        resp_val = round(float(latest.get("resp_sleep") or self.df["resp_sleep"].dropna().mean() or 13.8), 1)
        bb_wake = int(round(_num(latest.get("bb_wake"), 78)))
        bb_low = int(round(_num(latest.get("bb_low"), 20)))

        steps = int(round(_num(latest.get("steps"), 0)))
        step_goal = int(round(_num(latest.get("step_goal"), 10000))) or 10000
        steps_pct = round((steps / max(1, step_goal)) * 100.0, 1)
        steps_7d_avg = int(round(_tail_stat("steps", "mean", 7, steps)))
        steps_7d_total = int(round(_tail_stat("steps", "sum", 7, steps)))

        total_kcal = int(round(_num(latest.get("total_kcal"), 0)))
        active_kcal = int(round(_num(latest.get("active_kcal"), 0)))
        bmr_kcal = int(round(_num(latest.get("bmr_kcal"), 0)))
        is_partial_day = bool(bmr_kcal < 1800)

        prev_row = self.df.iloc[-2] if len(self.df) >= 2 else latest
        steps_prev_full_day = int(round(_num(prev_row.get("steps"), steps)))
        stress_prev_full_day = round(_num(prev_row.get("avg_stress"), stress_latest), 1)
        prev_full_day_kcal = int(round(_num(prev_row.get("total_kcal"), total_kcal)))
        prev_full_day_active_kcal = int(round(_num(prev_row.get("active_kcal"), active_kcal)))
        prev_full_day_bmr_kcal = int(round(_num(prev_row.get("bmr_kcal"), bmr_kcal)))

        kcal_7d_avg = int(round(_tail_stat("total_kcal", "mean", 7, total_kcal)))
        active_kcal_7d_avg = int(round(_tail_stat("active_kcal", "mean", 7, active_kcal)))
        bmr_kcal_7d_avg = int(round(_tail_stat("bmr_kcal", "mean", 7, bmr_kcal)))

        tl = self.get_training_load_analytics()
        cur_st = tl.get("current_status", {})
        load_focus = tl.get("load_focus", {})
        acute_load = cur_st.get("acute_load") or int(_num(latest.get("acute_load"), 279))
        chronic_load = cur_st.get("chronic_load") or 279
        acwr_val = float(cur_st.get("acwr") or 1.0)
        acwr_status = cur_st.get("acwr_status") or ("OPTIMAL" if 0.8 <= acwr_val <= 1.3 else ("HIGH" if acwr_val > 1.3 else "LOW"))
        tunnel_min = int(round(_num(cur_st.get("tunnel_min"), 223)))
        tunnel_max = int(round(_num(cur_st.get("tunnel_max"), 419)))
        vo2_val = float(tl.get("vo2max_current") or 45.4)

        load_focus_summary = {
            "low_aerobic_pct": float(load_focus.get("aerobic_low", {}).get("pct_of_target", 92.3)),
            "high_aerobic_pct": float(load_focus.get("aerobic_high", {}).get("pct_of_target", 91.5)),
            "anaerobic_pct": float(load_focus.get("anaerobic", {}).get("pct_of_target", 61.9)),
            "low_aerobic_actual": float(load_focus.get("aerobic_low", {}).get("actual", 385.9)),
            "high_aerobic_actual": float(load_focus.get("aerobic_high", {}).get("actual", 537.8)),
            "anaerobic_actual": float(load_focus.get("anaerobic", {}).get("actual", 162.3)),
            "primary_deficit": load_focus.get("primary_deficit", "anaerobic"),
            "recommended_focus_label": load_focus.get("recommended_focus_label", "Anaerobik & Laktat İntervali"),
            "balance_phrase": load_focus.get("balance_phrase", "BALANCED (Dengeli)"),
        }

        # Son 7 gün yapılan antrenmanların özeti (tarih penceresi en güncel kayıt üzerinden kurulur)
        end_dt_str = str(latest["date"])[:10]
        if self.activities_all:
            newest_act_dt = max(((a.get("startTimeLocal") or "")[:10] for a in self.activities_all), default=end_dt_str)
            if newest_act_dt > end_dt_str:
                end_dt_str = newest_act_dt
        end_dt = datetime.strptime(end_dt_str, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=6)
        start_dt_str = start_dt.strftime("%Y-%m-%d")
        acts_7d = [
            a for a in self.activities_all
            if start_dt_str <= (a.get("startTimeLocal") or "")[:10] <= end_dt_str
        ]
        run_count = 0
        gym_count = 0
        other_count = 0
        w7_items = []
        for a in sorted(acts_7d, key=lambda x: x.get("startTimeLocal") or "", reverse=True):
            sp_key = a.get("sport") or (a.get("activityType") or {}).get("typeKey") or ""
            bkt = classify_sport_bucket(sp_key)
            if bkt == "running":
                run_count += 1
            elif bkt == "strength":
                gym_count += 1
            else:
                other_count += 1
            w7_items.append({
                "date": (a.get("startTimeLocal") or "")[:10],
                "sport": sp_key,
                "sport_tr": format_sport_tr(sp_key, a.get("activityName") or ""),
                "name": a.get("activityName") or format_sport_tr(sp_key),
                "duration_min": int(round((a.get("duration") or 0) / 60.0)),
                "distance_km": round((a.get("distance") or 0) / 1000.0, 2),
                "calories": int(round(a.get("calories") or 0)),
                "load": round(float(a.get("activityTrainingLoad") or 0), 1),
            })
        bd_parts = []
        if run_count:
            bd_parts.append(f"{run_count} Koşu")
        if gym_count:
            bd_parts.append(f"{gym_count} Kuvvet")
        if other_count:
            bd_parts.append(f"{other_count} Diğer")
        workouts_7d = {
            "count": len(acts_7d),
            "active_days": len({(a.get("startTimeLocal") or "")[:10] for a in acts_7d}),
            "total_duration_min": int(round(sum((a.get("duration") or 0) / 60.0 for a in acts_7d))),
            "total_distance_km": round(sum((a.get("distance") or 0) / 1000.0 for a in acts_7d), 2),
            "total_calories": int(round(sum(a.get("calories") or 0 for a in acts_7d))),
            "total_load": round(sum(float(a.get("activityTrainingLoad") or 0) for a in acts_7d), 1),
            "run_count": run_count,
            "gym_count": gym_count,
            "other_count": other_count,
            "breakdown_tr": " · ".join(bd_parts) if bd_parts else "0 Seans",
            "window_label": f"{start_dt_str[8:10]}.{start_dt_str[5:7]} – {end_dt_str[8:10]}.{end_dt_str[5:7]}",
            "items": w7_items,
        }

        # Son 5K koşusunu ve kadansı dinamik bul
        latest_5k_str = "29:07 (5:48 /km)"
        latest_cadence = 162
        if hasattr(self, "adf") and not self.adf.empty:
            r_5k = self.adf[
                self.adf["sport"].str.contains("running", case=False, na=False)
                & (self.adf["dist_km"] >= 4.8)
                & self.adf["pace_s"].notna()
            ]
            if not r_5k.empty:
                best_r = r_5k.sort_values("pace_s").iloc[0]
                tot_s = int(round(float(best_r["pace_s"]) * 5.0))
                latest_5k_str = f"{tot_s // 60}:{tot_s % 60:02d} ({best_r['pace_str']} /km)"
            cads = self.adf[self.adf["cadence"].notna()]["cadence"]
            if not cads.empty:
                latest_cadence = int(round(float(cads.iloc[0])))

        # Antrenman Kararı
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_acts = [a for a in self.activities_all if (a.get("startTimeLocal") or "")[:10] == today_str]
        prot_g = round(current_weight * 2.0)

        if today_acts:
            act = today_acts[0]
            act_name = act.get("activityName") or format_sport_tr((act.get("activityType") or {}).get("typeKey"))
            act_cals = act.get("calories") or 0
            act_dur = round((act.get("duration") or 0) / 60.0)
            act_hr = act.get("averageHR") or 0
            rec = {
                "status": "Bugünkü Antrenman Tamamlandı",
                "color": "emerald",
                "summary": f"Bugün {act_name} başarıyla tamamlandı ({act_dur} dk • {act_cals} kcal • {act_hr} bpm).",
                "suggestion": f"Toparlanmaya geçin: ~{prot_g}g protein hedefi, hidrasyon ve erken yatış (00:30 öncesi).",
            }
        elif readiness_score >= 75 and hrv_night >= 40:
            rec = {
                "status": "Yeşil Işık (Hazır)",
                "color": "emerald",
                "summary": "Toparlanma iyi durumda, planlı antrenman için uygun gün.",
                "suggestion": load_focus.get("recommended_workout", "Bu haftanın kalan antrenmanını uygulayabilirsin."),
            }
        elif readiness_score >= 50:
            rec = {
                "status": "Sarı Işık (Orta Hazırlık)",
                "color": "amber",
                "summary": "Toparlanma orta seviyede. Aşırı yük yerine kontrollü tempo seçin.",
                "suggestion": "40-45 dk rahat Zone 2 veya teknik üst vücut kuvvet seansı.",
            }
        else:
            rec = {
                "status": "Kırmızı Işık (Dinlenme Günü)",
                "color": "rose",
                "summary": "Otonom yorgunluk yüksek veya uyku yetersiz.",
                "suggestion": "Sert antrenmanı erteleyin; kalan kotayı daha dinç bir güne kaydırın.",
            }

        # Kilometre taşları artık calculate_custom_projection() çıktısından dinamik hesaplanır!
        stage_defs = [
            ("Aşama 1: Normal VKİ Sınırı", round(min(24.99 * self.height_m2, 86.4), 1) if current_weight > 86.4 else round(current_weight - 0.5, 1)),
            ("Aşama 2: Kısa Vadeli Form", 85.0 if current_weight > 85.0 else round(current_weight - 1.5, 1)),
            ("Aşama 3: Atletik Form Başlangıcı", 83.0 if current_weight > 83.0 else round(current_weight - 2.5, 1)),
            ("Aşama 4: İdeal Çoklu-Branş Formu", 81.0 if current_weight > 81.0 else round(current_weight - 3.5, 1)),
            ("Aşama 5: Saf Koşucu Kütlesi", 79.0 if current_weight > 79.0 else round(max(74.0, current_weight - 5.0), 1)),
        ]
        milestone_data = []
        for title, t_kg in stage_defs:
            p_fast = self.calculate_custom_projection(t_kg, 0.89, current_weight=current_weight)
            p_opt = self.calculate_custom_projection(t_kg, 0.55, current_weight=current_weight)
            milestone_data.append({
                "level": title,
                "target_kg": t_kg,
                "target_bmi": round(t_kg / self.height_m2, 2),
                "diff_kg": round(t_kg - current_weight, 1),
                "days_current": p_fast.get("days_needed", 0),
                "days_optimal": p_opt.get("days_needed", 0),
                "target_date_current": p_fast.get("target_date", "Ulaşıldı"),
                "target_date_optimal": p_opt.get("target_date", "Ulaşıldı"),
                "expected_5k": p_opt.get("expected_5k", "--"),
                "expected_vo2": p_opt.get("expected_vo2", "--"),
            })

        raw_rec_min = latest.get("recovery_time_min")
        rec_ts_str = latest.get("recovery_timestamp_local")
        if raw_rec_min is not None:
            rec_min = float(raw_rec_min)
            if rec_ts_str and latest.get("date") == today_str:
                try:
                    snap_dt = datetime.fromisoformat(str(rec_ts_str).split(".")[0])
                    elapsed_min = max(0.0, (datetime.now() - snap_dt).total_seconds() / 60.0)
                    rec_min = max(0.0, rec_min - elapsed_min)
                except Exception:
                    pass
        else:
            rec_min = 0.0

        # Son 7 günün gece HRV bar grafiği serisi
        hrv_7d_series = []
        for _, row in self.df.tail(7).iterrows():
            v_hrv = row.get("hrv_night")
            hrv_val = None if v_hrv is None or pd.isna(v_hrv) else round(float(v_hrv), 1)
            v_st = row.get("hrv_status")
            hrv_7d_series.append({
                "date": str(row.get("date") or ""),
                "hrv": hrv_val,
                "status": None if v_st is None or pd.isna(v_st) else str(v_st),
            })

        # VO2 Max trend yönü (yukarı / aşağı / sabit)
        vo2_vals = []
        for item in (getattr(self, "vo2max_history", None) or []):
            gen = item.get("generic") if isinstance(item, dict) else None
            if isinstance(gen, dict):
                v_num = gen.get("vo2MaxPreciseValue") if gen.get("vo2MaxPreciseValue") is not None else gen.get("vo2MaxValue")
                if v_num is not None:
                    vo2_vals.append((gen.get("calendarDate") or "", float(v_num)))
        vo2_vals.sort(key=lambda x: x[0])
        if len(vo2_vals) >= 2:
            v_cur = vo2_vals[-1][1]
            v_prev = vo2_vals[-2][1]
            v_base = vo2_vals[max(0, len(vo2_vals) - 4)][1]
            v_delta = round(v_cur - v_prev, 1)
            v_span_delta = round(v_cur - v_base, 1)
            if v_delta > 0.05 or (abs(v_delta) <= 0.05 and v_span_delta > 0.05):
                v_dir, v_arrow, v_txt = "up", "↗", "Yükseliş"
            elif v_delta < -0.05 or (abs(v_delta) <= 0.05 and v_span_delta < -0.05):
                v_dir, v_arrow, v_txt = "down", "↘", "Düşüş"
            else:
                v_dir, v_arrow, v_txt = "flat", "→", "Sabit"
            vo2max_trend = {
                "direction": v_dir,
                "arrow": v_arrow,
                "label": v_txt,
                "delta": v_delta,
                "span_delta": v_span_delta,
                "prev": round(v_prev, 1),
                "current": round(v_cur, 1),
                "prev_date": vo2_vals[-2][0],
                "current_date": vo2_vals[-1][0],
            }
        else:
            vo2max_trend = {
                "direction": "flat",
                "arrow": "→",
                "label": "Sabit",
                "delta": 0.0,
                "span_delta": 0.0,
                "prev": vo2_val,
                "current": vo2_val,
                "prev_date": None,
                "current_date": None,
            }

        return {
            "date": latest["date"],
            "weight": current_weight,
            "start_weight": start_weight,
            "target_weight": 81.0 if current_weight > 81.0 else round(max(75.0, current_weight - 2.0), 1),
            "bmi": round(current_bmi, 2),
            "total_loss_kg": total_loss,
            "loss_pct": round(loss_pct, 1),
            "weekly_pace_kg": -0.89,
            "resting_hr": rhr,
            "rhr": rhr_mean,
            "overnight_hrv": hrv_night,
            "hrv_7d": hrv_7d,
            "hrv_status": hrv_status,
            "hrv_7d_series": hrv_7d_series,
            "sleep_score": sleep_score,
            "sleep_score_7d": sleep_score_7d,
            "sleep_hours": round(sleep_h, 2),
            "sleep_hours_7d": sleep_hours_7d,
            "sleep_duration_hours": sleep_h_mean,
            "deep_sleep_pct": deep_pct,
            "rem_sleep_pct": rem_sleep_pct,
            "rem_sleep_pct_7d": rem_sleep_pct_7d,
            "rem_hours": round(rem_h, 2),
            "deep_hours": round(deep_h, 2),
            "readiness_score": readiness_score,
            "readiness_7d_avg": readiness_7d_avg,
            "readiness_status": readiness_status,
            "stress": round(stress_latest, 1),
            "stress_7d_avg": stress_7d_avg,
            "stress_prev_full_day": stress_prev_full_day,
            "stress_status": stress_status,
            "resp_sleep": resp_val,
            "bb_wake": bb_wake,
            "bb_low": bb_low,
            "steps": steps,
            "step_goal": step_goal,
            "steps_pct": steps_pct,
            "steps_7d_avg": steps_7d_avg,
            "steps_7d_total": steps_7d_total,
            "steps_prev_full_day": steps_prev_full_day,
            "total_kcal": total_kcal,
            "active_kcal": active_kcal,
            "bmr_kcal": bmr_kcal,
            "is_partial_day": is_partial_day,
            "prev_full_day_kcal": prev_full_day_kcal,
            "prev_full_day_active_kcal": prev_full_day_active_kcal,
            "prev_full_day_bmr_kcal": prev_full_day_bmr_kcal,
            "kcal_7d_avg": kcal_7d_avg,
            "active_kcal_7d_avg": active_kcal_7d_avg,
            "bmr_kcal_7d_avg": bmr_kcal_7d_avg,
            "vo2max": vo2_val,
            "vo2max_trend": vo2max_trend,
            "acute_load": acute_load,
            "chronic_load": chronic_load,
            "acwr": acwr_val,
            "acwr_status": acwr_status,
            "tunnel_min": tunnel_min,
            "tunnel_max": tunnel_max,
            "load_focus_summary": load_focus_summary,
            "workouts_7d": workouts_7d,
            "training_status": cur_st.get("status_tr", "Form Korunuyor"),
            "training_balance": load_focus.get("balance_phrase", "BALANCED"),
            "recovery_time_h": round(rec_min / 60.0, 1),
            "recommendation": rec,
            "milestones": milestone_data,
            "latest_5k": latest_5k_str,
            "latest_cadence": latest_cadence,
            "biometrics_93d": self._compute_93d_biometrics_table(),
        }

    def get_training_load_analytics(self) -> Dict[str, Any]:
        """Firstbeat Training Load, ACWR ve gerçek bar doluluklarına göre enerji odak tavsiyesi döner."""
        lb_map = self.training_status_latest.get("mostRecentTrainingLoadBalance", {}).get("metricsTrainingLoadBalanceDTOMap", {})
        lb = list(lb_map.values())[0] if lb_map else {}

        st_map = self.training_status_latest.get("mostRecentTrainingStatus", {}).get("latestTrainingStatusData", {})
        st = list(st_map.values())[0] if st_map else {}
        ac = st.get("acuteTrainingLoadDTO", {}) or {}

        status_tr_map = {
            "MAINTAINING_1": "Form Korunuyor (Maintaining)",
            "MAINTAINING_3": "Form Korunuyor (Maintaining)",
            "MAINTAINING_4": "Form Korunuyor (Maintaining)",
            "MAINTAINING_6": "Form Korunuyor (Maintaining)",
            "MAINTAINING_7": "Form Korunuyor (Maintaining)",
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
            "ANAEROBIC_SHORTAGE": "Anaerobik Eksiği",
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
                "balance_tr": balance_tr_map.get(raw_bal, raw_bal),
            })

        sport_loads = []
        if hasattr(self, "adf_3m") and not self.adf_3m.empty:
            sp_grp = self.adf_3m.groupby("sport").agg(
                total_load=("load", "sum"),
                count=("id", "count"),
                avg_load=("load", "mean"),
            ).reset_index()
            total_load_all = float(sp_grp["total_load"].sum()) or 1.0
            for _, r in sp_grp.sort_values("total_load", ascending=False).iterrows():
                sport_loads.append({
                    "sport": r["sport"],
                    "name_tr": format_sport_tr(r["sport"], str(r["sport"])),
                    "total_load": round(float(r["total_load"]), 1),
                    "avg_load": round(float(r["avg_load"]), 1),
                    "pct": round((float(r["total_load"]) / total_load_all) * 100, 1),
                    "count": int(r["count"]),
                })

        top_load_acts = []
        if hasattr(self, "adf") and not self.adf.empty:
            for _, r in self.adf.sort_values("load", ascending=False).head(10).iterrows():
                top_load_acts.append({
                    "date": r["date"],
                    "sport": r["sport"],
                    "sport_tr": format_sport_tr(r["sport"], r["name"]),
                    "name": r["name"],
                    "dur_m": round(float(r["dur_m"]), 0),
                    "load": round(float(r["load"]), 1),
                    "aTE": r.get("aTE"),
                    "anTE": r.get("anTE"),
                    "te_label": r.get("te_label") or "--",
                })

        vo2_points = []
        vo2_current = 45.4
        for pt in self.vo2max_history:
            cal = pt.get("generic", {})
            if cal.get("vo2MaxPreciseValue"):
                val = float(cal.get("vo2MaxPreciseValue"))
                vo2_current = val
                vo2_points.append({"date": cal.get("calendarDate"), "vo2": val, "sport": cal.get("sport", "RUNNING")})

        cur_acwr = float(ac.get("dailyAcuteChronicWorkloadRatio") or 1.0)
        cur_acute = ac.get("dailyTrainingLoadAcute") or 279
        cur_chronic = ac.get("dailyTrainingLoadChronic") or 279
        cur_acwr_status = ac.get("acwrStatus") or "OPTIMAL"
        cur_status_code = st.get("trainingStatusFeedbackPhrase", "MAINTAINING_3")
        cur_status_tr = status_tr_map.get(cur_status_code, cur_status_code)

        # Load Focus Hesaplaması — Gerçek bar doluluk oranına göre eksik sistemi seç
        low_act = round(float(lb.get("monthlyLoadAerobicLow", 385.9)), 1)
        low_min = lb.get("monthlyLoadAerobicLowTargetMin", 155)
        low_max = lb.get("monthlyLoadAerobicLowTargetMax", 418) or 418
        low_pct = round((low_act / low_max) * 100.0, 1)

        high_act = round(float(lb.get("monthlyLoadAerobicHigh", 537.8)), 1)
        high_min = lb.get("monthlyLoadAerobicHighTargetMin", 325)
        high_max = lb.get("monthlyLoadAerobicHighTargetMax", 588) or 588
        high_pct = round((high_act / high_max) * 100.0, 1)

        an_act = round(float(lb.get("monthlyLoadAnaerobic", 162.3)), 1)
        an_min = lb.get("monthlyLoadAnaerobicTargetMin", 0)
        an_max = lb.get("monthlyLoadAnaerobicTargetMax", 262) or 262
        an_pct = round((an_act / an_max) * 100.0, 1)

        def _bucket_status(actual, t_min, pct):
            if actual < t_min:
                return f"EKSİK (Hedef Altı · %{pct:.0f})"
            if pct < 72.0:
                return f"ORTA BANT · GELİŞİME AÇIK (%{pct:.0f})"
            return f"ÜST BANT · OPTİMAL (%{pct:.0f})"

        fill_map = {"aerobic_low": low_pct, "aerobic_high": high_pct, "anaerobic": an_pct}
        lowest_zone = min(fill_map, key=fill_map.get)

        if lowest_zone == "anaerobic":
            prio_label = "Anaerobik & Laktat İntervali"
            rec_workout = "Anaerobik barı (%{:.0f} · {}/{} birim) en boş/orta bantta olduğu için öncelik 4x1000m @ Z4-5 Hız İntervali veya patlayıcı sprint çalışmasıdır; Düşük Aerobik zaten %{:.0f} ile üst tavana yakındır.".format(an_pct, an_act, an_max, low_pct)
        elif lowest_zone == "aerobic_low":
            prio_label = "Düşük Aerobik (Zone 2 Taban)"
            rec_workout = "Düşük Aerobik barı en düşük dolulukta (%{:.0f}) olduğu için 45-50 dk Zone 2 (140-150 bpm) koşu önerilir.".format(low_pct)
        else:
            prio_label = "Yüksek Aerobik (Tempo / Eşik)"
            rec_workout = "Yüksek Aerobik barı en düşük dolulukta (%{:.0f}) olduğu için 25-30 dk tempo koşusu önerilir.".format(high_pct)

        raw_bal_phrase = lb.get("trainingBalanceFeedbackPhrase", "BALANCED")
        return {
            "acwr": {"acwr_ratio": cur_acwr, "status": cur_acwr_status},
            "vo2max_current": round(vo2_current, 1),
            "current_status": {
                "status_code": cur_status_code,
                "status_tr": cur_status_tr,
                "vo2max": round(vo2_current, 1),
                "fitness_trend": "Pozitif / Dengeli" if cur_acwr <= 1.3 else "Yüksek Akut Yük",
                "acute_load": cur_acute,
                "chronic_load": cur_chronic,
                "acwr": cur_acwr,
                "acwr_status": cur_acwr_status,
                "acwr_interpretation": f"ACWR oranı {cur_acwr:.2f} seviyesinde; 0,80–1,30 Sweet Spot bandı içinde sakatlık riski düşüktür.",
                "tunnel_min": ac.get("minTrainingLoadChronic", 223.2),
                "tunnel_max": ac.get("maxTrainingLoadChronic", 418.5),
            },
            "load_focus": {
                "aerobic_low": {"actual": low_act, "target_min": low_min, "target_max": low_max, "status": _bucket_status(low_act, low_min, low_pct), "pct_of_target": low_pct},
                "aerobic_high": {"actual": high_act, "target_min": high_min, "target_max": high_max, "status": _bucket_status(high_act, high_min, high_pct), "pct_of_target": high_pct},
                "anaerobic": {"actual": an_act, "target_min": an_min, "target_max": an_max, "status": _bucket_status(an_act, an_min, an_pct), "pct_of_target": an_pct},
                "primary_deficit": lowest_zone,
                "recommended_focus_label": prio_label,
                "recommended_workout": rec_workout,
                "balance_phrase": f"{raw_bal_phrase} ({balance_tr_map.get(raw_bal_phrase, raw_bal_phrase)})",
                "balance_note": rec_workout,
            },
            "weekly_progression": weekly_progression,
            "sport_loads": sport_loads,
            "top_load_acts": top_load_acts,
            "vo2_points": vo2_points,
        }
