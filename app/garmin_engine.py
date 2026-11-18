#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin Veri ve Performans Hesaplama Motoru (Ana Orkestratör).
Ham Garmin Connect telemetrisini (günlük özetler, uyku, HRV, tartı/kilo, egzersiz setleri
ve tüm çoklu branş aktiviteleri) yükler ve modüler Mixin sınıflarıyla analitiğe sunar.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    from engine.helpers import fmt_pace_sec, fmt_clock, DATA_DIR, IS_DEMO_MODE, format_sport_tr, classify_sport_bucket
    from engine.fit_stream_parser import load_and_parse_high_res_streams
    from engine.telemetry_mixin import TelemetryMixin
    from engine.sleep_analytics_mixin import SleepAnalyticsMixin
    from engine.training_protocols_mixin import TrainingProtocolsMixin
    from engine.simulation_health_mixin import SimulationHealthMixin
except ImportError:
    from app.engine.helpers import fmt_pace_sec, fmt_clock, DATA_DIR, IS_DEMO_MODE, format_sport_tr, classify_sport_bucket
    from app.engine.fit_stream_parser import load_and_parse_high_res_streams
    from app.engine.telemetry_mixin import TelemetryMixin
    from app.engine.sleep_analytics_mixin import SleepAnalyticsMixin
    from app.engine.training_protocols_mixin import TrainingProtocolsMixin
    from app.engine.simulation_health_mixin import SimulationHealthMixin


class GarminAthleteEngine(TelemetryMixin, SleepAnalyticsMixin, TrainingProtocolsMixin, SimulationHealthMixin):
    """Garmin Çoklu Spor Biyometrik ve Telemetri Hesaplama Motoru."""

    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.height_cm = 186.0
        self.height_m2 = (self.height_cm / 100.0) ** 2
        self.age = 22
        self.load_data()

    def get_weight_history(self) -> List[Dict[str, Any]]:
        """raw_weight.json (Garmin weight-service) içinden tarih sıralı tartı kayıtlarını döner."""
        entries: List[Dict[str, Any]] = []
        raw = getattr(self, "weight_raw", None) or {}
        if isinstance(raw, dict):
            candidates = raw.get("dailyWeightSummaries") or raw.get("dateWeightList") or []
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                latest = item.get("latestWeight") if isinstance(item.get("latestWeight"), dict) else item
                w_val = latest.get("weight")
                dt_str = (item.get("summaryDate") or latest.get("calendarDate") or "")[:10]
                if w_val and dt_str:
                    w_kg = float(w_val) / 1000.0 if float(w_val) > 300 else float(w_val)
                    entries.append({"date": dt_str, "weight_kg": round(w_kg, 2)})
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("weight") and item.get("calendarDate"):
                    w_val = float(item["weight"])
                    w_kg = w_val / 1000.0 if w_val > 300 else w_val
                    entries.append({"date": str(item["calendarDate"])[:10], "weight_kg": round(w_kg, 2)})
        entries.sort(key=lambda x: x["date"])
        return entries

    def get_start_weight(self) -> float:
        """Başlangıç kilosunu canlı tartı geçmişi varsa ilk kayıttan, yoksa baz değerden döner."""
        hist = self.get_weight_history()
        if hist and hist[0]["date"] < "2026-10-01":
            return hist[0]["weight_kg"]
        return 95.0

    def get_current_weight(self, date_str: Optional[str] = None) -> float:
        """Garmin weight-service kaydı varsa güncel kiloyu dinamik döner; yoksa tarihsel güvenli yedeğe düşer."""
        hist = self.get_weight_history()
        if hist:
            if date_str:
                eligible = [e for e in hist if e["date"] <= date_str]
                if eligible:
                    return eligible[-1]["weight_kg"]
            return hist[-1]["weight_kg"]

        # Summaries içinde varsa yakala
        for dt in reversed(self.dates if hasattr(self, "dates") else []):
            if date_str and dt > date_str:
                continue
            s = self.summaries.get(dt, {}) if isinstance(self.summaries.get(dt), dict) else {}
            w_g = s.get("bodyWeightInGrams") or s.get("weight")
            if w_g and float(w_g) > 0:
                return round(float(w_g) / 1000.0 if float(w_g) > 300 else float(w_g), 2)

        if date_str:
            if date_str >= "2026-11-01":
                return 87.0
            if date_str >= "2026-10-01":
                return 91.0
            return 95.0
        return 87.0

    def load_data(self) -> None:
        """Ham telemetri dosyalarını (günlük, uyku, aktivite, yük, VO2, tartı) yükler."""
        daily_path = os.path.join(self.data_dir, "raw_daily_93d.json")
        sleep_path = os.path.join(self.data_dir, "raw_sleep_stats.json")
        acts_path = os.path.join(self.data_dir, "raw_activities.json")
        ts_latest_path = os.path.join(self.data_dir, "raw_training_status_latest.json")
        ts_weekly_path = os.path.join(self.data_dir, "raw_training_status_weekly.json")
        vo2_path = os.path.join(self.data_dir, "raw_vo2max_history.json")
        weight_path = os.path.join(self.data_dir, "raw_weight.json")

        self.daily_raw = json.load(open(daily_path, encoding="utf-8")) if os.path.exists(daily_path) else {"summaries": {}, "readiness": {}}
        self.sleep_stats = json.load(open(sleep_path, encoding="utf-8")) if os.path.exists(sleep_path) else {}
        self.activities_all = json.load(open(acts_path, encoding="utf-8")) if os.path.exists(acts_path) else []
        self.training_status_latest = json.load(open(ts_latest_path, encoding="utf-8")) if os.path.exists(ts_latest_path) else {}
        self.training_status_weekly = json.load(open(ts_weekly_path, encoding="utf-8")) if os.path.exists(ts_weekly_path) else {}
        self.vo2max_history = json.load(open(vo2_path, encoding="utf-8")) if os.path.exists(vo2_path) else []
        self.weight_raw = json.load(open(weight_path, encoding="utf-8")) if os.path.exists(weight_path) else {}

        high_res = load_and_parse_high_res_streams(
            self.data_dir,
            persist_real_fit=(not IS_DEMO_MODE and os.path.basename(os.path.normpath(self.data_dir)) == "data"),
        )
        self.high_res_fits = high_res.get("parsed_fits", {})
        self.high_res_streams = high_res.get("raw_streams", {})
        self.hrv_5min_raw = high_res.get("hrv_5min_raw", {})
        self.resp_daily_raw = high_res.get("resp_daily_raw", {})

        self.summaries = self.daily_raw.get("summaries", {})
        self.readiness = self.daily_raw.get("readiness", {})
        self.dates = sorted(self.summaries.keys())

        rows = []
        for dt in self.dates:
            s = self.summaries.get(dt, {})
            if not isinstance(s, dict) or "error" in s:
                continue
            sl = self.sleep_stats.get(dt, {})
            rd_list = self.readiness.get(dt, [])
            rd = {}
            if isinstance(rd_list, list) and len(rd_list) > 0:
                wakeup = [x for x in rd_list if isinstance(x, dict) and x.get("inputContext") == "AFTER_WAKEUP_RESET"]
                rd = wakeup[0] if wakeup else rd_list[0]

            sleep_start_ms = sl.get("localSleepStartTimeInMillis")
            sleep_end_ms = sl.get("localSleepEndTimeInMillis")
            sleep_start_hr = None
            sleep_end_hr = None
            if sleep_start_ms:
                dt_obj = datetime.fromtimestamp(sleep_start_ms / 1000.0, tz=timezone.utc)
                hr = dt_obj.hour + dt_obj.minute / 60.0
                sleep_start_hr = hr - 24.0 if hr >= 18 else hr
            if sleep_end_ms:
                dt_obj = datetime.fromtimestamp(sleep_end_ms / 1000.0, tz=timezone.utc)
                sleep_end_hr = dt_obj.hour + dt_obj.minute / 60.0

            rows.append({
                "date": dt,
                "month": dt[:7],
                "steps": s.get("totalSteps"),
                "step_goal": s.get("dailyStepGoal"),
                "total_kcal": s.get("totalKilocalories"),
                "active_kcal": s.get("activeKilocalories"),
                "bmr_kcal": s.get("bmrKilocalories"),
                "dist_km": (s.get("totalDistanceMeters") or 0) / 1000.0 if s.get("totalDistanceMeters") is not None else None,
                "floors": s.get("floorsAscended"),
                "rhr": s.get("restingHeartRate") or sl.get("restingHeartRate"),
                "min_hr": s.get("minHeartRate"),
                "max_hr": s.get("maxHeartRate"),
                "avg_stress": s.get("averageStressLevel") if (s.get("averageStressLevel") or -1) > 0 else None,
                "bb_charged": s.get("bodyBatteryChargedValue"),
                "bb_drained": s.get("bodyBatteryDrainedValue"),
                "bb_high": s.get("bodyBatteryHighestValue"),
                "bb_low": s.get("bodyBatteryLowestValue"),
                "bb_wake": s.get("bodyBatteryAtWakeTime"),
                "spo2_avg": s.get("averageSpo2") or sl.get("spO2"),
                "spo2_low": s.get("lowestSpo2"),
                "resp_sleep": sl.get("respiration"),
                "sedentary_h": (s.get("sedentarySeconds") or 0) / 3600.0 if s.get("sedentarySeconds") else None,
                "active_h": ((s.get("activeSeconds") or 0) + (s.get("highlyActiveSeconds") or 0)) / 3600.0 if s.get("activeSeconds") else None,
                "sleep_score": sl.get("sleepScore"),
                "sleep_h": (sl.get("totalSleepTimeInSeconds") or 0) / 3600.0 if sl.get("totalSleepTimeInSeconds") else None,
                "deep_h": (sl.get("deepTime") or 0) / 3600.0 if sl.get("deepTime") is not None else None,
                "light_h": (sl.get("lightTime") or 0) / 3600.0 if sl.get("lightTime") is not None else None,
                "rem_h": (sl.get("remTime") or 0) / 3600.0 if sl.get("remTime") is not None else None,
                "hrv_night": sl.get("avgOvernightHrv"),
                "hrv_7d": sl.get("hrv7dAverage"),
                "sleep_start_hr": sleep_start_hr,
                "sleep_end_hr": sleep_end_hr,
                "readiness_score": rd.get("score") if isinstance(rd, dict) else None,
                "acute_load": rd.get("acuteLoad") if isinstance(rd, dict) else None,
                "recovery_time_min": rd.get("recoveryTime") if isinstance(rd, dict) else None,
                "recovery_timestamp_local": rd.get("timestampLocal") if isinstance(rd, dict) else None,
                "acwr_factor_pct": rd.get("acwrFactorPercent") if isinstance(rd, dict) else None,
                "hrv_weekly_avg": rd.get("hrvWeeklyAverage") if isinstance(rd, dict) else None,
            })
        self.df = pd.DataFrame(rows)

        act_rows = []
        for a in self.activities_all:
            dt_local = a.get("startTimeLocal", "")
            dt_date = dt_local[:10]
            if dt_date < "2026-08-01":
                continue
            t_key = a.get("activityType", {}).get("typeKey", "other")
            dur_s = a.get("duration") or 0
            dist_m = a.get("distance") or 0
            spd = a.get("averageSpeed") or 0
            is_paced = ("running" in t_key.lower()) or any(tok in t_key.lower() for tok in ("hiking", "walking", "ski"))
            pace_s = (1000.0 / spd) if (is_paced and dist_m > 200 and spd > 0) else None
            z1, z2, z3, z4, z5 = (a.get(f"hrTimeInZone_{i}") or 0 for i in range(1, 6))
            ztot = z1 + z2 + z3 + z4 + z5

            w_kg = self.get_current_weight(dt_date)
            npwr = a.get("normPower")
            w_per_kg = (npwr / w_kg) if (npwr and w_kg) else None
            avg_hr = a.get("averageHR") or 0
            ef_spd = ((spd * 60.0) / avg_hr) if (avg_hr > 0 and spd > 0) else None

            act_rows.append({
                "id": a.get("activityId"),
                "date": dt_date,
                "time": dt_local[11:16],
                "month": dt_date[:7],
                "in_3m": dt_date >= self.dates[0] if self.dates else True,
                "name": a.get("activityName") or format_sport_tr(t_key),
                "sport": t_key,
                "sport_tr": format_sport_tr(t_key, a.get("activityName") or ""),
                "bucket": classify_sport_bucket(t_key),
                "dur_m": dur_s / 60.0,
                "dist_km": dist_m / 1000.0,
                "cal": a.get("calories") or 0,
                "avg_hr": avg_hr,
                "max_hr": a.get("maxHR") or 0,
                "pace_s": pace_s,
                "pace_str": fmt_pace_sec(pace_s),
                "cadence": a.get("averageRunningCadenceInStepsPerMinute"),
                "stride_cm": a.get("avgStrideLength"),
                "gct_ms": a.get("avgGroundContactTime"),
                "vert_osc_cm": a.get("avgVerticalOscillation"),
                "vert_ratio": a.get("avgVerticalRatio"),
                "avg_pwr": a.get("avgPower"),
                "norm_pwr": npwr,
                "w_per_kg": round(w_per_kg, 2) if w_per_kg else None,
                "ef_spd": round(ef_spd, 3) if ef_spd else None,
                "aTE": a.get("aerobicTrainingEffect"),
                "anTE": a.get("anaerobicTrainingEffect"),
                "te_label": a.get("trainingEffectLabel"),
                "aTE_msg": a.get("aerobicTrainingEffectMessage"),
                "anTE_msg": a.get("anaerobicTrainingEffectMessage"),
                "load": a.get("activityTrainingLoad") or 0,
                "water_ml": a.get("waterEstimated") or 0,
                "bb_diff": a.get("differenceBodyBattery"),
                "fast_1k": fmt_pace_sec(a.get("fastestSplit_1000")),
                "fast_5k": fmt_pace_sec(a.get("fastestSplit_5000")),
                "z1_pct": round(z1 / ztot * 100, 1) if ztot > 0 else 0,
                "z2_pct": round(z2 / ztot * 100, 1) if ztot > 0 else 0,
                "z3_pct": round(z3 / ztot * 100, 1) if ztot > 0 else 0,
                "z4_pct": round(z4 / ztot * 100, 1) if ztot > 0 else 0,
                "z5_pct": round(z5 / ztot * 100, 1) if ztot > 0 else 0,
            })
        self.adf = pd.DataFrame(act_rows)
        self.adf_3m = self.adf[self.adf["in_3m"]].copy() if not self.adf.empty else self.adf
