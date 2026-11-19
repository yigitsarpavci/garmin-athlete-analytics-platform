#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temel Biyometrik Özetler, 93 Günlük Dinamik İstatistik Tablosu ve Firstbeat Yük Odak Analizi Mixin'i.
"""

import logging
import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any
import numpy as np
import pandas as pd

try:
    from engine.helpers import fnum, request_cached, zone_text, format_sport_tr, classify_sport_bucket
    from engine.run_load_predictor import compute_weekly_bar_drift
except ImportError:
    from app.engine.helpers import fnum, request_cached, zone_text, format_sport_tr, classify_sport_bucket
    from app.engine.run_load_predictor import compute_weekly_bar_drift


logger = logging.getLogger(__name__)


_STATUS_BASE_TR = {
    "MAINTAINING": "Form Korunuyor (Maintaining)",
    "PRODUCTIVE": "Üretken (Productive)",
    "UNPRODUCTIVE": "Verimsiz (Unproductive)",
    "RECOVERY": "Toparlanma (Recovery)",
    "DETRAINING": "Kondisyon Kaybı (Detraining)",
    "OVERREACHING": "Aşırı Yüklenme (Overreaching)",
    "PEAKING": "Zirve Formu (Peaking)",
    "NO_STATUS": "Durum Yok",
}


class _StatusLabels(dict):
    """Garmin antrenman durumu kodlarını (PRODUCTIVE_6, MAINTAINING_3 ...) Türkçe etikete çevirir; sonek rakamı yok sayılır."""

    def get(self, code, default=None):
        raw = str(code or "")
        base = re.sub(r"_\d+$", "", raw.upper())
        if base in _STATUS_BASE_TR:
            return _STATUS_BASE_TR[base]
        if default and default != raw:
            return default
        return raw.replace("_", " ").title() if raw else "--"


class TelemetryMixin:
    """Canlı metrikler, 93 günlük özet istatistikler, dinamik kilometre taşları ve ACWR yük analitiği."""

    def _compute_93d_biometrics_table(self) -> List[Dict[str, Any]]:
        """93 günlük DataFrame üzerinden 14 temel sağlık/biyometrik satırını canlı hesaplar."""
        if self.df.empty:
            return []

        def _fmt(v, dec=1, suffix=""):
            return f"{v:.{dec}f}{suffix}".replace(".", ",") if v is not None and not np.isnan(v) else "--"

        hrv_bl = self.get_hrv_baseline()
        hrv_id_lo, hrv_id_hi = (hrv_bl["low"], hrv_bl["high"]) if hrv_bl else (None, None)
        hrv_ref_txt = f"{hrv_id_lo:.0f} – {hrv_id_hi:.0f} ms" if hrv_bl else None
        specs = [
            ("Günlük Adım Sayısı", "steps", 0, "", None, "Günlük fiziksel hareket hacmi", None, None, "higher_better"),
            ("Günlük Mesafe", "dist_km", 2, " km", None, "Koşu, yürüyüş ve diğer branş toplamı", None, None, "higher_better"),
            ("Günlük Harcama", "total_kcal", 0, " kcal", None, "Bazal + aktif toplam enerji tüketimi", None, None, "range"),
            ("Dinlenik Nabız (RHR)", "rhr", 1, " bpm", None, "Düşük RHR güçlü kardiyak rezervi gösterir", None, None, "lower_better"),
            ("Gece HRV", "hrv_night", 1, " ms", hrv_ref_txt, "Parasempatik otonom denge göstergesi", hrv_id_lo, hrv_id_hi, "higher_better"),
            ("Günlük Ort. Stres", "avg_stress", 1, "", None, "Gün içi sempatik yük puanı", None, None, "lower_better"),
            ("Sabah Body Battery", "bb_wake", 1, "", None, "Gece uykusundan sonraki başlangıç rezervi", None, None, "higher_better"),
            ("Akşam Dip Enerji", "bb_low", 1, "", None, "Gün sonu rezerv dibi", None, None, "range"),
            ("Toplam Uyku Süresi", "sleep_h", 2, " sa", "7,5 – 8,5 sa", "Kas/sinir sistemi yenilenme süresi", 7.5, 8.5, "higher_better"),
            ("Derin Uyku Oranı", "deep_h", 1, "%", "%15 – %20", "Doku tamiri ve anabolik faz", 15.0, 20.0, "higher_better"),
            ("REM Uyku Oranı", "rem_h", 1, "%", "%20 – %25", "Bilişsel ve nörolojik toparlanma fazı", 20.0, 25.0, "higher_better"),
            ("Garmin Uyku Puanı", "sleep_score", 1, "", "80 – 100", "Genel uyku mimarisi skoru", 80.0, 100.0, "higher_better"),
            ("Gece SpO2", "spo2_avg", 1, "%", "%95 – %98", "Gece kandaki oksijen doygunluğu", 95.0, 98.0, "higher_better"),
            ("Antrenman Hazırlığı", "readiness_score", 1, "", "65 – 100", "Günlük antrenman yüküne tolerans puanı", 65.0, 100.0, "higher_better"),
        ]
        rows = []
        n_days = len(self.df)
        for label, col, dec, sfx, ref_rng, note, id_lo, id_hi, polarity in specs:
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
            ideal_source = "reference"
            if id_lo is None or id_hi is None:  # Sabit norm yok: sporcunun KENDİ tipik bandı (çeyrekler) ve Garmin adım hedefi
                id_lo, id_hi = float(ser.quantile(0.25)), float(ser.quantile(0.75))
                if col == "steps" and "step_goal" in self.df.columns:
                    goal = pd.to_numeric(self.df["step_goal"], errors="coerce").dropna()
                    if not goal.empty and float(goal.median()) > 0:
                        id_lo = float(goal.median())
                        id_hi = max(id_hi, id_lo * 1.2)
                if id_hi <= id_lo:
                    id_hi = id_lo + max(1.0, abs(id_lo) * 0.1)
                if dec == 0:
                    ref_rng = f"{int(round(id_lo)):,} – {int(round(id_hi)):,}".replace(",", ".") + sfx
                else:
                    ref_rng = f"{_fmt(id_lo, dec)} – {_fmt(id_hi, dec)}{sfx}"
                ideal_source = "personal"
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
                "ideal_source": ideal_source,
                "status": extra_note,
                "avg_val": round(mean_v, 2),
                "med_val": round(med_v, 2),
                "min_val": round(min_v, 2),
                "max_val": round(max_v, 2),
                "ideal_low": id_lo,
                "ideal_high": id_hi,
                "polarity": polarity,
            })
        return rows

    @staticmethod
    def _num(val, default=0.0):
        """None/NaN güvenli float dönüşümü."""
        return float(val) if val is not None and pd.notnull(val) else float(default)

    def _tail_stat(self, col, op="mean", n=7, default=0.0):
        """Sütunun son n gününün ortalaması (veya toplamı); sütun/veri yoksa varsayılan."""
        if col not in self.df.columns:
            return float(default)
        ser = pd.to_numeric(self.df[col], errors="coerce").dropna().tail(n)
        if ser.empty:
            return float(default)
        return float(ser.sum() if op == "sum" else ser.mean())

    def _snapshot_freshness(self, latest_date: str) -> Dict[str, Any]:
        """
        Günün Garmin özetinin ne zamana ait olduğunu (wellnessEndTimeLocal) ve yaşını döner. Garmin Connect, adım ve kaloriyi
        yalnızca saat telefona/Garmin Connect'e eşitlendiğinde günceller; bu yüzden "saatimle aynı değil" durumunu açıklamak için gerekir.
        """
        s = self.summaries.get(latest_date, {}) if isinstance(self.summaries.get(latest_date), dict) else {}
        raw = str(s.get("wellnessEndTimeLocal") or "")
        out: Dict[str, Any] = {"data_as_of": None, "data_age_min": None, "data_is_stale": False}
        try:
            as_of = datetime.fromisoformat(raw.split(".")[0])
        except ValueError:
            return out
        age_min = max(0, int((datetime.now() - as_of).total_seconds() // 60))
        is_today = latest_date == datetime.now().strftime("%Y-%m-%d")
        out.update({
            "data_as_of": as_of.strftime("%Y-%m-%d %H:%M"),
            "data_age_min": age_min,
            # Bugünün verisi 90 dakikadan eskiyse saat büyük olasılıkla Garmin Connect ile eşitlenmemiştir
            "data_is_stale": bool(is_today and age_min > 90),
        })
        return out

    @request_cached
    def get_latest_metrics(self) -> Dict[str, Any]:
        """Sporcunun güncel kilo, HRV, uyku, Firstbeat ACWR, kilometre taşları ve günlük kararını döner."""
        if self.df.empty:
            return {}
        latest = self.df.iloc[-1]

        current_weight = round(float(self.get_current_weight()), 1)
        start_weight = round(float(self.get_start_weight()), 1)
        current_bmi = current_weight / self.height_m2
        total_loss = round(start_weight - current_weight, 1)
        loss_pct = (total_loss / start_weight) * 100.0 if start_weight > 0 else 0.0

        # Gün başında bugünün uyku/HRV verisi henüz yoktur (NaN); en son uyku verisi olan günü kullan
        sleep_row = latest
        if {"sleep_h", "hrv_night"}.issubset(self.df.columns):
            valid_sleep = self.df[pd.to_numeric(self.df["sleep_h"], errors="coerce").gt(0) & self.df["hrv_night"].notna()]
            if not valid_sleep.empty:
                sleep_row = valid_sleep.iloc[-1]
        deep_h, deep_pct, hrv_7d, hrv_night, rem_h, rem_sleep_pct, rhr, rhr_mean, sleep_h, sleep_h_mean, sleep_score = self._sleep_and_rhr_basics(sleep_row)

        _num = self._num
        _tail_stat = self._tail_stat

        bb_low, bb_wake, hrv_status, readiness_7d_avg, readiness_score, readiness_status, rem_sleep_pct_7d, resp_val, sleep_hours_7d, sleep_score_7d, stress_7d_avg, stress_latest, stress_status = self._readiness_hrv_stress_metrics(hrv_7d, hrv_night, latest, rem_sleep_pct, sleep_h, sleep_score)

        active_kcal, active_kcal_7d_avg, bmr_kcal, bmr_kcal_7d_avg, is_partial_day, kcal_7d_avg, prev_full_day_active_kcal, prev_full_day_bmr_kcal, prev_full_day_kcal, step_goal, steps, steps_7d_avg, steps_7d_total, steps_pct, steps_prev_full_day, stress_prev_full_day, total_kcal = self._activity_energy_metrics(latest, stress_latest)

        tl = self.get_training_load_analytics()
        cur_st = tl.get("current_status", {})
        load_focus = tl.get("load_focus", {})
        acute_load = cur_st.get("acute_load") or int(_num(latest.get("acute_load"), 0))
        chronic_load = cur_st.get("chronic_load") or 0
        acwr_val = float(cur_st.get("acwr") or 1.0)
        acwr_status = cur_st.get("acwr_status") or ("OPTIMAL" if 0.8 <= acwr_val <= 1.3 else ("HIGH" if acwr_val > 1.3 else "LOW"))
        tunnel_min = int(round(_num(cur_st.get("tunnel_min"), 0)))
        tunnel_max = int(round(_num(cur_st.get("tunnel_max"), 0)))
        vo2_val = float(tl.get("vo2max_current") or 0.0)

        load_focus_summary = {
            "targets_available": bool(load_focus.get("targets_available", True)),
            "low_aerobic_pct": float(load_focus.get("aerobic_low", {}).get("pct_of_target", 0.0)),
            "high_aerobic_pct": float(load_focus.get("aerobic_high", {}).get("pct_of_target", 0.0)),
            "anaerobic_pct": float(load_focus.get("anaerobic", {}).get("pct_of_target", 0.0)),
            "low_aerobic_actual": float(load_focus.get("aerobic_low", {}).get("actual", 0.0)),
            "high_aerobic_actual": float(load_focus.get("aerobic_high", {}).get("actual", 0.0)),
            "anaerobic_actual": float(load_focus.get("anaerobic", {}).get("actual", 0.0)),
            "primary_deficit": load_focus.get("primary_deficit", "anaerobic"),
            "recommended_focus_label": load_focus.get("recommended_focus_label", "Anaerobik (İnterval)"),
            "balance_phrase": load_focus.get("balance_phrase", "BALANCED (Dengeli)"),
            "weekly_bar_drift": compute_weekly_bar_drift(load_focus, getattr(self, "activities_all", []) or []),
        }

        workouts_7d = self._summarize_last_7_days(latest)

        latest_5k_str, latest_cadence = self._latest_5k_and_cadence()

        rec, today_str = self._build_daily_recommendation(current_weight, hrv_night, load_focus, readiness_score)

        milestone_data = self._build_weight_milestones(current_weight)

        rec_min = self._remaining_recovery_minutes(latest, today_str)

        hrv_7d_series = self._build_hrv_7d_series()

        vo2max_trend = self._compute_vo2max_trend(vo2_val)

        return {
            "date": latest["date"],
            "weight": current_weight,
            "start_weight": start_weight,
            "target_weight": self.get_target_weight() if current_weight > self.get_target_weight() else round(max(self.get_target_weight() - 6.0, current_weight - 2.0), 1),
            "bmi": round(current_bmi, 2),
            "total_loss_kg": total_loss,
            "loss_pct": round(loss_pct, 1),
            "weekly_pace_kg": self._weekly_weight_pace_kg(),
            "resting_hr": rhr,
            "rhr": rhr_mean,
            "overnight_hrv": hrv_night,
            "hrv_7d": hrv_7d,
            "hrv_baseline_low": (self.get_hrv_baseline() or {}).get("low"),
            "hrv_baseline_high": (self.get_hrv_baseline() or {}).get("high"),
            "hrv_baseline_source": (self.get_hrv_baseline() or {}).get("source"),
            "hrv_status": hrv_status,
            "hrv_7d_series": hrv_7d_series,
            "sleep_score": sleep_score,
            "sleep_score_7d": sleep_score_7d,
            "sleep_hours": round(sleep_h, 2),
            "sleep_hours_7d": sleep_hours_7d,
            "sleep_duration_hours": sleep_h_mean,
            "deep_sleep_pct": deep_pct,
            "deep_sleep_pct_7d": self._sleep_stage_pct_7d("deep_h", deep_pct),
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
            **self._snapshot_freshness(str(latest["date"])[:10]),
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

    def _sleep_and_rhr_basics(self, latest):
        """Dinlenik nabız, gece HRV, uyku süresi/evreleri ve yüzdelerini son günden hesaplar."""
        def _own(col: str, fallback: float = 0.0) -> float:
            return fnum(self.get_personal_baseline(col).get("mean"), fallback)

        rhr = int(round(fnum(latest.get("rhr"), _own("rhr", self.get_physiology()["rhr"]))))
        rhr_mean = round(float(self.df["rhr"].dropna().mean()), 1) if self.df["rhr"].notna().any() else float(rhr)
        hrv_night = fnum(latest.get("hrv_night"), _own("hrv_night"))
        hrv_7d = fnum(latest.get("hrv_7d"), _own("hrv_night"))
        sleep_score = fnum(latest.get("sleep_score"), _own("sleep_score"))
        sleep_h = fnum(latest.get("sleep_h"), _own("sleep_h"))
        sleep_h_mean = round(float(self.df["sleep_h"].dropna().mean()), 2) if self.df["sleep_h"].notna().any() else sleep_h
        deep_h = fnum(latest.get("deep_h"), _own("deep_h"))
        rem_h = fnum(latest.get("rem_h"), _own("rem_h"))
        deep_pct = round((deep_h / max(1.0, sleep_h)) * 100.0, 1)
        rem_sleep_pct = round((rem_h / max(1.0, sleep_h)) * 100.0, 1)
        return deep_h, deep_pct, hrv_7d, hrv_night, rem_h, rem_sleep_pct, rhr, rhr_mean, sleep_h, sleep_h_mean, sleep_score

    def _sleep_stage_pct_7d(self, col: str, fallback: float) -> float:
        """Son 7 günlük uyku evresi (REM/Derin) yüzdelik ortalamasını döner."""
        if {col, "sleep_h"}.issubset(self.df.columns):
            sub_df = self.df[[col, "sleep_h"]].apply(pd.to_numeric, errors="coerce").dropna()
            sub_df = sub_df[sub_df["sleep_h"] > 0].tail(7)
            if not sub_df.empty:
                return round(float(((sub_df[col] / sub_df["sleep_h"].clip(lower=1.0)) * 100.0).mean()), 1)
        return fallback


    def _readiness_hrv_stress_metrics(self, hrv_7d, hrv_night, latest, rem_sleep_pct, sleep_h, sleep_score):
        """Uyku ortalamaları, hazırlık, HRV/stres durumu (kişisel taban çizgisine göre), solunum ve Body Battery değerlerini hesaplar."""
        _num = self._num
        _tail_stat = self._tail_stat
        sleep_score_7d = round(_tail_stat("sleep_score", "mean", 7, sleep_score), 1)
        sleep_hours_7d = round(_tail_stat("sleep_h", "mean", 7, sleep_h), 2)
        rem_sleep_pct_7d = self._sleep_stage_pct_7d("rem_h", rem_sleep_pct)

        readiness_score = int(round(_num(latest.get("readiness_score"), fnum(self.get_personal_baseline("readiness_score").get("mean"), 0.0))))
        readiness_7d_avg = round(_tail_stat("readiness_score", "mean", 7, readiness_score), 1)
        readiness_status = "Yüksek Hazırlık" if readiness_score >= 70 else ("Orta Hazırlık" if readiness_score >= 45 else "Toparlanma Gerekli")

        # Eşikler sporcunun kendi 28 günlük taban çizgisinden (yeterli veri yoksa genel bantlardan) türetilir
        hrv_base = self.get_personal_baseline("hrv_night")
        hrv_band = max(3.0, 0.75 * hrv_base["std"]) if hrv_base["reliable"] else 6.0
        hrv_status = "Dengeli" if abs(hrv_night - hrv_7d) <= hrv_band else ("Yüksek Rezerv" if hrv_night > hrv_7d else "Baskılanmış")
        stress_latest = float(latest.get("avg_stress")) if pd.notnull(latest.get("avg_stress")) else round(_tail_stat("avg_stress", "mean", len(self.df), fnum(self.get_personal_baseline("avg_stress").get("mean"), 0.0)), 1)
        stress_7d_avg = round(_tail_stat("avg_stress", "mean", 7, stress_latest), 1)
        stress_base = self.get_personal_baseline("avg_stress")
        s_lo, s_hi = (stress_base["p25"], stress_base["p75"]) if stress_base["reliable"] else (25.0, 38.0)
        stress_status = "Düşük / Rahat" if stress_latest <= s_lo else ("Normal / Dengeli" if stress_latest <= s_hi else "Yüksek Stres")
        resp_val = round(fnum(latest.get("resp_sleep"), fnum(self.get_personal_baseline("resp_sleep").get("mean"), 0.0)), 1)
        bb_wake = int(round(_num(latest.get("bb_wake"), fnum(self.get_personal_baseline("bb_wake").get("mean"), 0.0))))
        bb_low = int(round(_num(latest.get("bb_low"), fnum(self.get_personal_baseline("bb_low").get("mean"), 0.0))))
        return bb_low, bb_wake, hrv_status, readiness_7d_avg, readiness_score, readiness_status, rem_sleep_pct_7d, resp_val, sleep_hours_7d, sleep_score_7d, stress_7d_avg, stress_latest, stress_status


    def _activity_energy_metrics(self, latest, stress_latest):
        """Adım, hedef ve kalori değerlerini (bugün, önceki tam gün, 7 günlük ortalama) hesaplar."""
        _num = self._num
        _tail_stat = self._tail_stat
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
        return active_kcal, active_kcal_7d_avg, bmr_kcal, bmr_kcal_7d_avg, is_partial_day, kcal_7d_avg, prev_full_day_active_kcal, prev_full_day_bmr_kcal, prev_full_day_kcal, step_goal, steps, steps_7d_avg, steps_7d_total, steps_pct, steps_prev_full_day, stress_prev_full_day, total_kcal


    def _summarize_last_7_days(self, latest):
        """Son 7 günün antrenmanlarını (sayı, süre, mesafe, yük, tür dağılımı) özetler."""
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
        return workouts_7d


    def _latest_5k_and_cadence(self):
        """En iyi 5K koşusunu ve son kadansı aktivite tablosundan bulur."""
        # Son 5K koşusunu ve kadansı dinamik bul
        latest_5k_str = "--"
        latest_cadence = 0
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
        return latest_5k_str, latest_cadence


    def _hrv_ready_floor(self) -> float:
        """'Hazır' sayılmak için gece HRV alt sınırı: kişisel tabanın 0,5 std altı (yeterli veri yoksa 40 ms)."""
        base = self.get_personal_baseline("hrv_night")
        return base["mean"] - 0.5 * base["std"] if base["reliable"] else 40.0

    def _build_daily_recommendation(self, current_weight, hrv_night, load_focus, readiness_score):
        """Hazırlık, HRV ve bugünkü antrenman durumuna göre günün trafik ışığı kararını üretir."""
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
        elif readiness_score >= 75 and hrv_night >= self._hrv_ready_floor():
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
                "suggestion": "Quick Workout'tan Zone 2 veya planlı kuvvet seansı (hafif).",
            }
        else:
            rec = {
                "status": "Kırmızı Işık (Dinlenme Günü)",
                "color": "rose",
                "summary": "Otonom yorgunluk yüksek veya uyku yetersiz.",
                "suggestion": "Sert antrenmanı erteleyin; kalan kotayı daha dinç bir güne kaydırın.",
            }
        return rec, today_str


    def _build_weight_milestones(self, current_weight):
        """Kilo hedeflerine (kilometre taşlarına) hızlı ve optimal tempoda ulaşma projeksiyonlarını üretir."""
        # Kilometre taşları artık calculate_custom_projection() çıktısından dinamik hesaplanır!
        # Aşamalar sporcunun KENDİ hedef kilosuna (profil) göre kurulur: DSÖ normal VKİ sınırı, hedef+4, hedef+2, hedef, hedef-2.
        target = self.get_target_weight()
        who_cutoff = math.floor(24.99 * self.height_m2 * 10) / 10.0
        stage_defs = [
            ("Aşama 1: Normal VKİ Sınırı", who_cutoff if current_weight > who_cutoff else round(current_weight - 0.5, 1)),
            ("Aşama 2: Kısa Vadeli Form", round(target + 4.0, 1) if current_weight > target + 4.0 else round(current_weight - 1.5, 1)),
            ("Aşama 3: Atletik Form Başlangıcı", round(target + 2.0, 1) if current_weight > target + 2.0 else round(current_weight - 2.5, 1)),
            ("Aşama 4: İdeal Çoklu-Branş Formu", target if current_weight > target else round(current_weight - 3.5, 1)),
            ("Aşama 5: Saf Koşucu Kütlesi", round(target - 2.0, 1) if current_weight > target - 2.0 else round(max(target - 7.0, current_weight - 5.0), 1)),
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
        return milestone_data


    def _remaining_recovery_minutes(self, latest, today_str):
        """Garmin toparlanma süresinden, anlık görüntüden bu yana geçen süreyi düşerek kalan dakikayı hesaplar."""
        raw_rec_min = latest.get("recovery_time_min")
        rec_ts_str = latest.get("recovery_timestamp_local")
        rec_date = latest.get("date")
        if not pd.notna(raw_rec_min) and "recovery_time_min" in self.df.columns:
            valid_rec = self.df[self.df["recovery_time_min"].notna()]
            if not valid_rec.empty:
                last_r = valid_rec.iloc[-1]
                raw_rec_min = last_r.get("recovery_time_min")
                rec_ts_str = last_r.get("recovery_timestamp_local")
                rec_date = last_r.get("date")
        if pd.notna(raw_rec_min):
            rec_min = float(raw_rec_min)
            if rec_ts_str and rec_date == today_str:
                try:
                    snap_dt = datetime.fromisoformat(str(rec_ts_str).split(".")[0])
                    elapsed_min = max(0.0, (datetime.now() - snap_dt).total_seconds() / 60.0)
                    rec_min = max(0.0, rec_min - elapsed_min)
                except (ValueError, TypeError):
                    logger.debug("get_latest_metrics: yedek davranış uygulandı", exc_info=True)
        else:
            rec_min = 0.0
        return rec_min


    def _build_hrv_7d_series(self):
        """Son 7 gecenin HRV serisini, 7 günlük taban değerine göre gece durumuyla birlikte üretir."""
        # Son 7 günün gece HRV bar grafiği serisi
        hrv_7d_series = []
        for _, row in self.df.tail(7).iterrows():
            v_hrv = row.get("hrv_night")
            hrv_val = None if v_hrv is None or pd.isna(v_hrv) else round(float(v_hrv), 1)
            v_base = row.get("hrv_7d")
            night_status = None
            if hrv_val is not None and v_base is not None and not pd.isna(v_base):
                diff = hrv_val - float(v_base)
                night_status = "Dengeli" if abs(diff) <= 6 else ("Yüksek" if diff > 0 else "Düşük")
            hrv_7d_series.append({
                "date": str(row.get("date") or ""),
                "hrv": hrv_val,
                "status": night_status,
            })
        return hrv_7d_series


    def _compute_vo2max_trend(self, vo2_val):
        """Garmin VO2 Max geçmişinden trend yönünü (yukarı / aşağı / sabit) ve son iki ölçümü hesaplar."""
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
        return vo2max_trend


    def _weekly_weight_pace_kg(self, window_days: int = 56) -> float:
        """Son ~8 haftanın tartı kayıtlarından doğrusal regresyonla haftalık kilo değişimini (kg/hf) hesaplar."""
        hist = self.get_weight_history() if hasattr(self, "get_weight_history") else []
        if len(hist) < 2:
            return 0.0  # Tartı geçmişi yoksa tempo bilinmiyor
        last_dt = datetime.strptime(hist[-1]["date"], "%Y-%m-%d")
        pts = [
            ((datetime.strptime(h["date"], "%Y-%m-%d") - last_dt).days, h["weight_kg"])
            for h in hist
            if (last_dt - datetime.strptime(h["date"], "%Y-%m-%d")).days <= window_days
        ]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 7:
            return 0.0
        n = len(pts)
        mx = sum(x for x, _ in pts) / n
        my = sum(y for _, y in pts) / n
        den = sum((x - mx) ** 2 for x, _ in pts)
        if den <= 0:
            return 0.0
        slope_per_day = sum((x - mx) * (y - my) for x, y in pts) / den
        return round(slope_per_day * 7.0, 2)

    @staticmethod
    def _interpret_acwr(acwr: float) -> str:
        """ACWR değerini Gabbett bantlarına göre sporcu diliyle yorumlar."""
        val = f"{acwr:.2f}".replace(".", ",")
        if acwr < 0.80:
            return f"ACWR {val}: 0,80 altı — akut yük kronik tabanın gerisinde; form kaybı riskine karşı yükü kademeli artır."
        if acwr <= 1.30:
            return f"ACWR {val}: 0,80–1,30 Sweet Spot bandında; sakatlık riski düşük, plana devam."
        if acwr < 1.50:
            return f"ACWR {val}: 1,30–1,50 dikkat bandı; yeni yük ekleme, sert seansları seyrelt."
        return f"ACWR {val}: 1,50 üzeri tehlike bölgesi; bu hafta hacmi %40-50 azalt ve toparlanmaya öncelik ver."

    @request_cached
    @zone_text
    def get_training_load_analytics(self) -> Dict[str, Any]:
        """Firstbeat Training Load, ACWR ve gerçek bar doluluklarına göre enerji odak tavsiyesi döner."""
        lb_map = (self.training_status_latest.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap") or {}
        lb = list(lb_map.values())[0] if lb_map else {}

        st_map = (self.training_status_latest.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
        st = list(st_map.values())[0] if st_map else {}
        ac = st.get("acuteTrainingLoadDTO", {}) or {}

        status_tr_map = _StatusLabels()
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

        weekly_progression = self._build_weekly_load_progression(balance_tr_map, status_tr_map)

        sport_loads = self._summarize_sport_loads()

        top_load_acts = self._top_load_activities()

        vo2_current, vo2_points = self._collect_vo2_points()

        cur_acwr = float(ac.get("dailyAcuteChronicWorkloadRatio") or 1.0)
        cur_acute = ac.get("dailyTrainingLoadAcute") or 0
        cur_chronic = ac.get("dailyTrainingLoadChronic") or 0
        cur_acwr_status = ac.get("acwrStatus") or "OPTIMAL"
        cur_status_code = st.get("trainingStatusFeedbackPhrase") or "NO_STATUS"
        cur_status_tr = status_tr_map.get(cur_status_code, cur_status_code)

        # Load Focus Hesaplaması — Gerçek bar doluluk oranına göre eksik sistemi seç.
        # Garmin hedef bantlarını (TargetMax) vermiyorsa yüzde "hedefe oran" yerine üç yükün toplam içindeki payıdır.
        low_act = round(float(lb.get("monthlyLoadAerobicLow", 0.0)), 1)
        high_act = round(float(lb.get("monthlyLoadAerobicHigh", 0.0)), 1)
        an_act = round(float(lb.get("monthlyLoadAnaerobic", 0.0)), 1)
        low_min = lb.get("monthlyLoadAerobicLowTargetMin", 0)
        high_min = lb.get("monthlyLoadAerobicHighTargetMin", 0)
        an_min = lb.get("monthlyLoadAnaerobicTargetMin", 0)
        low_max = lb.get("monthlyLoadAerobicLowTargetMax", 0) or 0
        high_max = lb.get("monthlyLoadAerobicHighTargetMax", 0) or 0
        an_max = lb.get("monthlyLoadAnaerobicTargetMax", 0) or 0
        targets_available = bool(low_max and high_max and an_max)
        if targets_available:
            low_pct = round((low_act / low_max) * 100.0, 1)
            high_pct = round((high_act / high_max) * 100.0, 1)
            an_pct = round((an_act / an_max) * 100.0, 1)
        else:
            total = (low_act + high_act + an_act) or 1.0
            low_pct, high_pct, an_pct = (round(v / total * 100.0, 1) for v in (low_act, high_act, an_act))

        def _bucket_status(actual, t_min, pct):
            if not targets_available:
                return f"HEDEF VERİSİ YOK (toplam yükün %{pct:.0f}'i)"
            if actual < t_min:
                return f"EKSİK (Hedef Altı · %{pct:.0f})"
            if pct < 72.0:
                return f"ORTA BANT · GELİŞİME AÇIK (%{pct:.0f})"
            return f"ÜST BANT · OPTİMAL (%{pct:.0f})"

        deload_info = None
        if targets_available and min(low_pct, high_pct, an_pct) >= 85.0:
            # Tüm barlar dolu: ekstra kuvvet ÖNERİLMEZ. Barlar Pazar'a kadar da %85 üstünde kalıyorsa (28G pencereden düşüş yetmiyorsa)
            # hafta sonuna kadar deload; bir bar Pazar'dan önce %85 altına inecekse en düşük bara koşu önerisine devam edilir.
            try:
                drift = compute_weekly_bar_drift(
                    {
                        "targets_available": True,
                        "aerobic_low": {"actual": low_act, "target_max": low_max},
                        "aerobic_high": {"actual": high_act, "target_max": high_max},
                        "anaerobic": {"actual": an_act, "target_max": an_max},
                    },
                    getattr(self, "activities_all", []) or [],
                )
                week_end = {k: drift[k]["week_end_pct"] for k in ("low_aerobic", "high_aerobic", "anaerobic")}
            except Exception:
                logger.warning("load_focus deload drift hesaplanamadı", exc_info=True)
                week_end = {"low_aerobic": low_pct, "high_aerobic": high_pct, "anaerobic": an_pct}
            if min(week_end.values()) >= 85.0:
                lowest_zone = "deload"
                deload_info = week_end
            else:
                fill_map = {"aerobic_low": low_pct, "aerobic_high": high_pct, "anaerobic": an_pct}
                lowest_zone = min(fill_map, key=fill_map.get)
        elif targets_available:
            fill_map = {"aerobic_low": low_pct, "aerobic_high": high_pct, "anaerobic": an_pct}
            lowest_zone = min(fill_map, key=fill_map.get)
        else:
            lowest_zone = "aerobic_low" if low_pct < an_pct else "anaerobic"

        prio_label, rec_workout = self._pick_load_focus(an_act, an_max, an_pct, high_pct, low_pct, lowest_zone, deload_info)

        raw_bal_phrase = lb.get("trainingBalanceFeedbackPhrase", "BALANCED")
        return {
            "acwr": {"acwr_ratio": cur_acwr, "status": cur_acwr_status},
            "vo2max_current": round(vo2_current, 1),
            "current_status": {
                "status_code": cur_status_code,
                "status_tr": cur_status_tr,
                "status_as_of": getattr(self, "training_status_as_of", None),
                "status_is_fallback": bool(getattr(self, "training_status_is_fallback", False)) or not st,
                "vo2max": round(vo2_current, 1),
                "fitness_trend": (
                    "Düşük Akut Yük" if cur_acwr < 0.8
                    else ("Pozitif / Dengeli" if cur_acwr <= 1.3 else "Yüksek Akut Yük")
                ),
                "acute_load": cur_acute,
                "chronic_load": cur_chronic,
                "acwr": cur_acwr,
                "acwr_status": cur_acwr_status,
                "acwr_interpretation": self._interpret_acwr(cur_acwr),
                "tunnel_min": ac.get("minTrainingLoadChronic", 0.0),
                "tunnel_max": ac.get("maxTrainingLoadChronic", 0.0),
            },
            "load_focus": {
                "aerobic_low": {"actual": low_act, "target_min": low_min, "target_max": low_max, "status": _bucket_status(low_act, low_min, low_pct), "pct_of_target": low_pct},
                "aerobic_high": {"actual": high_act, "target_min": high_min, "target_max": high_max, "status": _bucket_status(high_act, high_min, high_pct), "pct_of_target": high_pct},
                "anaerobic": {"actual": an_act, "target_min": an_min, "target_max": an_max, "status": _bucket_status(an_act, an_min, an_pct), "pct_of_target": an_pct},
                "targets_available": targets_available,
                "pct_basis": "target" if targets_available else "share",
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

    def _build_weekly_load_progression(self, balance_tr_map, status_tr_map):
        """Haftalık Firstbeat durum, ACWR ve yük dengesi serisini üretir."""
        weekly_progression = []
        for dt, obj in sorted(self.training_status_weekly.items()):
            dev_map_w = (obj.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap") or {}
            lb_w = list(dev_map_w.values())[0] if dev_map_w else {}
            st_map_w = (obj.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
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
        return weekly_progression


    def _summarize_sport_loads(self):
        """Son 3 ayın branş bazında toplam/ortalama yük dağılımını hesaplar."""
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
        return sport_loads


    def _top_load_activities(self):
        """En yüksek antrenman yüküne sahip 10 aktiviteyi listeler."""
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
        return top_load_acts


    def _collect_vo2_points(self):
        """VO2 Max geçmişinden grafik noktalarını ve güncel değeri çıkarır."""
        vo2_points = []
        vo2_current = 0.0
        for pt in self.vo2max_history:
            cal = pt.get("generic", {})
            if cal.get("vo2MaxPreciseValue"):
                val = float(cal.get("vo2MaxPreciseValue"))
                vo2_current = val
                vo2_points.append({"date": cal.get("calendarDate"), "vo2": val, "sport": cal.get("sport", "RUNNING")})
        return vo2_current, vo2_points


    def _pick_load_focus(self, an_act, an_max, an_pct, high_pct, low_pct, lowest_zone, deload_info=None):
        """En boş yük barına göre koşu odağı seçer; tüm barlar dolu ve düşmüyorsa hafta sonuna kadar deload (ekstra kuvvet önerilmez)."""
        if lowest_zone == "deload":
            we = deload_info or {}
            prio_label = "Deload (Yük Barları Dolu)"
            rec_workout = (
                "Üç yük barı da (Düşük %{:.0f} · Yüksek %{:.0f} · Anaer %{:.0f}) %85 üstünde ve Pazar'a kadar da düşmüyor "
                "(Pazar tahmini: %{:.0f} / %{:.0f} / %{:.0f}). Ekstra antrenman ekleme; hafta sonuna kadar deload: "
                "koşu yok, planlı kuvvet seanslarını hafif tut (hacim ~%40 düşür), yürüyüş ve mobilite ile toparlan."
            ).format(low_pct, high_pct, an_pct, we.get("low_aerobic", 0), we.get("high_aerobic", 0), we.get("anaerobic", 0))
        elif lowest_zone == "aerobic_low":
            prio_label = "Düşük Aerobik (Zone 2)"
            rec_workout = (
                "Düşük Aerobik barı (%{:.0f}) en düşük dolulukta olduğu için "
                "Quick Workout'tan Zone 2 ([[Z2_HR]]) seç."
            ).format(low_pct)
        elif lowest_zone == "aerobic_high":
            prio_label = "Yüksek Aerobik (Tempo)"
            rec_workout = (
                "Yüksek Aerobik barı (%{:.0f}) en düşük dolulukta olduğu için "
                "Quick Workout'tan Tempo seç."
            ).format(high_pct)
        else:
            prio_label = "Anaerobik (İnterval)"
            high_note = (
                " (Yüksek Aerobik %{:.0f} açığını da birlikte kapatır)".format(high_pct)
                if high_pct < 75.0 else ""
            )
            rec_workout = (
                "Anaerobik barı (%{:.0f}{}) en boş bantta olduğu için Quick Workout'tan İnterval seç{}; Düşük Aerobik %{:.0f} seviyesindedir."
            ).format(an_pct, f" · {an_act}/{an_max} birim" if an_max else f" · {an_act} birim", high_note, low_pct)
        return prio_label, rec_workout

