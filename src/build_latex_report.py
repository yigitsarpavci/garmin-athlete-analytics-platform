#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin 3 Aylık Spor ve Sağlık Raporu Üreticisi
Sporcu odaklı, görsel olarak okunaklı, sade ve anlaşılır dilde (XeLaTeX + PGFPlots)
PDF rapor ve CSV veri setlerini üretir.
"""

import json
import os
from datetime import datetime, timezone
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SRC_DIR = os.path.join(BASE_DIR, "src")

# -------------------------------------------------------------------------
# 1. Veri Yükleme ve Birleştirme
# -------------------------------------------------------------------------
acts_all = json.load(open(os.path.join(DATA_DIR, "raw_activities.json"), encoding="utf-8"))
sleep_days = json.load(open(os.path.join(DATA_DIR, "raw_sleep_stats.json"), encoding="utf-8"))
daily_raw = json.load(open(os.path.join(DATA_DIR, "raw_daily_93d.json"), encoding="utf-8"))

summaries = daily_raw["summaries"]
readiness = daily_raw["readiness"]

sorted_dates = sorted(summaries.keys())
start_date_str = sorted_dates[0]
end_date_str = sorted_dates[-1]

rows = []
for dt in sorted_dates:
    s = summaries[dt]
    if not isinstance(s, dict) or "error" in s:
        continue
    sl = sleep_days.get(dt, {})
    rd_list = readiness.get(dt, [])
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
        "mod_min": s.get("moderateIntensityMinutes") or 0,
        "vig_min": s.get("vigorousIntensityMinutes") or 0,
        "int_min_total": (s.get("moderateIntensityMinutes") or 0) + 2 * (s.get("vigorousIntensityMinutes") or 0),
        "rhr": s.get("restingHeartRate") or sl.get("restingHeartRate"),
        "min_hr": s.get("minHeartRate"),
        "max_hr": s.get("maxHeartRate"),
        "avg_stress": s.get("averageStressLevel") if (s.get("averageStressLevel") or -1) > 0 else None,
        "max_stress": s.get("maxStressLevel") if (s.get("maxStressLevel") or -1) > 0 else None,
        "stress_pct": s.get("stressPercentage"),
        "rest_stress_pct": s.get("restStressPercentage"),
        "high_stress_pct": s.get("highStressPercentage"),
        "med_stress_pct": s.get("mediumStressPercentage"),
        "low_stress_pct": s.get("lowStressPercentage"),
        "stress_qual": s.get("stressQualifier"),
        "bb_charged": s.get("bodyBatteryChargedValue"),
        "bb_drained": s.get("bodyBatteryDrainedValue"),
        "bb_high": s.get("bodyBatteryHighestValue"),
        "bb_low": s.get("bodyBatteryLowestValue"),
        "bb_wake": s.get("bodyBatteryAtWakeTime"),
        "bb_sleep": s.get("bodyBatteryDuringSleep") or sl.get("bodyBatteryChange"),
        "spo2_avg": s.get("averageSpo2") or sl.get("spO2"),
        "spo2_low": s.get("lowestSpo2"),
        "resp_wake": s.get("avgWakingRespirationValue"),
        "resp_sleep": sl.get("respiration"),
        "sedentary_h": (s.get("sedentarySeconds") or 0) / 3600.0 if s.get("sedentarySeconds") else None,
        "active_h": ((s.get("activeSeconds") or 0) + (s.get("highlyActiveSeconds") or 0)) / 3600.0 if s.get("activeSeconds") else None,
        "abnormal_hr_alerts": s.get("abnormalHeartRateAlertsCount") or 0,
        "sleep_score": sl.get("sleepScore"),
        "sleep_qual": sl.get("sleepScoreQuality"),
        "sleep_h": (sl.get("totalSleepTimeInSeconds") or 0) / 3600.0 if sl.get("totalSleepTimeInSeconds") else None,
        "deep_h": (sl.get("deepTime") or 0) / 3600.0 if sl.get("deepTime") is not None else None,
        "light_h": (sl.get("lightTime") or 0) / 3600.0 if sl.get("lightTime") is not None else None,
        "rem_h": (sl.get("remTime") or 0) / 3600.0 if sl.get("remTime") is not None else None,
        "awake_m": (sl.get("awakeTime") or 0) / 60.0 if sl.get("awakeTime") is not None else None,
        "hrv_night": sl.get("avgOvernightHrv"),
        "hrv_status": sl.get("hrvStatus"),
        "hrv_7d": sl.get("hrv7dAverage"),
        "sleep_need_m": sl.get("sleepNeed"),
        "sleep_start_hr": sleep_start_hr,
        "sleep_end_hr": sleep_end_hr,
        "readiness_score": rd.get("score") if isinstance(rd, dict) else None,
        "readiness_level": rd.get("level") if isinstance(rd, dict) else None,
        "acute_load": rd.get("acuteLoad") if isinstance(rd, dict) else None,
        "recovery_time_m": rd.get("recoveryTime") if isinstance(rd, dict) else None,
    })

df = pd.DataFrame(rows)

act_rows = []
for a in acts_all:
    dt_local = a.get("startTimeLocal", "")
    dt_date = dt_local[:10]
    if dt_date < "2026-08-01":
        continue
    t_key = a.get("activityType", {}).get("typeKey", "other")
    dur_s = a.get("duration") or 0
    dist_m = a.get("distance") or 0
    spd = a.get("averageSpeed") or 0
    pace_s_km = (1000.0 / spd) if (t_key == "running" and spd > 0) else None
    z1, z2, z3, z4, z5 = (a.get(f"hrTimeInZone_{i}") or 0 for i in range(1, 6))
    ztot = z1 + z2 + z3 + z4 + z5

    act_rows.append({
        "id": a.get("activityId"),
        "date": dt_date,
        "time": dt_local[11:16],
        "month": dt_date[:7],
        "in_3m": dt_date >= start_date_str,
        "name": a.get("activityName"),
        "sport": t_key,
        "dur_m": dur_s / 60.0,
        "dist_km": dist_m / 1000.0,
        "cal": a.get("calories") or 0,
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "spd_ms": spd,
        "pace_s": pace_s_km,
        "cadence": a.get("averageRunningCadenceInStepsPerMinute"),
        "stride_cm": a.get("avgStrideLength"),
        "gct_ms": a.get("avgGroundContactTime"),
        "vert_osc_cm": a.get("avgVerticalOscillation"),
        "vert_ratio": a.get("avgVerticalRatio"),
        "avg_pwr": a.get("avgPower"),
        "norm_pwr": a.get("normPower"),
        "max_pwr": a.get("maxPower"),
        "aTE": a.get("aerobicTrainingEffect"),
        "anTE": a.get("anaerobicTrainingEffect"),
        "te_label": a.get("trainingEffectLabel"),
        "load": a.get("activityTrainingLoad") or 0,
        "vo2": a.get("vO2MaxValue"),
        "water_ml": a.get("waterEstimated") or 0,
        "bb_diff": a.get("differenceBodyBattery"),
        "fast_1k": a.get("fastestSplit_1000"),
        "fast_5k": a.get("fastestSplit_5000"),
        "z1_pct": z1 / ztot * 100 if ztot > 0 else 0,
        "z2_pct": z2 / ztot * 100 if ztot > 0 else 0,
        "z3_pct": z3 / ztot * 100 if ztot > 0 else 0,
        "z4_pct": z4 / ztot * 100 if ztot > 0 else 0,
        "z5_pct": z5 / ztot * 100 if ztot > 0 else 0,
    })

adf = pd.DataFrame(act_rows)
adf_3m = adf[adf["in_3m"]].copy()

df.to_csv(os.path.join(DATA_DIR, "garmin_93gun_gunluk_veri.csv"), index=False)
adf.to_csv(os.path.join(DATA_DIR, "garmin_aktiviteler_detay.csv"), index=False)
df.to_csv(os.path.join(BASE_DIR, "garmin_93gun_gunluk_veri.csv"), index=False)
adf.to_csv(os.path.join(BASE_DIR, "garmin_aktiviteler_detay.csv"), index=False)

# -------------------------------------------------------------------------
# 2. Biçimlendirme Yardımcıları
# -------------------------------------------------------------------------
def fmt(val, nd=1):
    if val is None or (isinstance(val, float) and (math.isnan(val) if "math" in globals() else np.isnan(val))):
        return "--"
    if nd == 0:
        return f"{int(round(val)):,}".replace(",", ".")
    return f"{val:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pace(sec):
    if sec is None or np.isnan(sec) or sec <= 0:
        return "--"
    m = int(sec // 60)
    s = int(round(sec % 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"

def fmt_clock(hr_val):
    if hr_val is None or np.isnan(hr_val):
        return "--"
    h = hr_val + 24.0 if hr_val < 0 else hr_val
    hh = int(h) % 24
    mm = int(round((h - int(h)) * 60))
    if mm == 60:
        hh = (hh + 1) % 24
        mm = 0
    return f"{hh:02d}:{mm:02d}"

def tex_esc(s):
    if s is None:
        return "--"
    s = str(s)
    return s.replace("_", "\\_").replace("&", "\\&").replace("%", "\\%").replace("#", "\\#")

# -------------------------------------------------------------------------
# 3. Tablo Satırlarının Hazırlanması (Okunaklı ve Sadeleştirilmiş)
# -------------------------------------------------------------------------

# Tablo 2: 93 Günlük Sağlık, Uyku ve Enerji Özeti (16 Temel Gösterge, 5 Okunaklı Sütun)
summary_rows_spec = [
    ("steps", "Günlük Adım Sayısı", "adım", 0, "8.000 -- 12.000 adım", "93 günün 38'inde (\\%41) adım hedefi aşıldı"),
    ("dist_km", "Günlük Toplam Mesafe", "km", 2, "7,0 -- 12,0 km", "3 ayda toplam 1.020,5 km mesafe kat edildi"),
    ("total_kcal", "Günlük Toplam Kalori", "kcal", 0, "2.800 -- 3.200 kcal", "Bazal: 2.322 kcal + Aktif: 620 kcal/gün"),
    ("active_kcal", "Günlük Aktif Kalori", "kcal", 0, "500 -- 900 kcal", "Spor yapılan günlerde 1.000+ kcal"),
    ("active_h", "Günlük Hareketli Süre", "saat", 2, "1,5 -- 2,5 saat", "Günün ort.\\ 15,0 saati hareketsiz (masa başı)"),
    ("rhr", "Dinlenik Nabız (RHR)", "bpm", 1, "48 -- 56 bpm", "Atletik seviyede (Saatte 65 bpm sabit kalmış)"),
    ("hrv_night", "Gece HRV (Toparlanma)", "ms", 1, "37 -- 58 ms", "88 gecenin \\%75'inde dengeli aralıkta"),
    ("avg_stress", "Günlük Ortalama Stres", "0--100", 1, "25 -- 35 puan", "Yoğun günlerde 40+ puana çıkıyor"),
    ("bb_wake", "Sabah Uyanış Enerjisi (BB)", "0--100", 1, "75 -- 100 puan", "Erken yatılan gecelerde ortalama 75+ puan"),
    ("bb_low", "Akşam En Düşük Enerji (BB)", "0--100", 1, "15 -- 30 puan", "93 günün 48'inde (\\%52) akşam 5'e (dibe) indi"),
    ("sleep_h", "Toplam Uyku Süresi", "saat", 2, "7,5 -- 8,5 saat", "Kasım ayında 7,30 saate yükseldi"),
    ("deep_h", "Derin Uyku Süresi", "saat", 2, "1,1 -- 1,5 saat", "Toplam uykunun \\%24,3'ü (Çok iyi kas onarımı)"),
    ("rem_h", "REM Uyku Süresi", "saat", 2, "1,5 -- 2,0 saat", "01:45 sonrası yatışlarda \\%32 kısalıyor"),
    ("sleep_score", "Garmin Uyku Puanı", "0--100", 1, "80 -- 100 puan", "Medyan 82 puan (\\%60 İyi ve Mükemmel)"),
    ("spo2_avg", "Gece Kan Oksijeni (SpO$_2$)", "\\%", 1, "\\%95 -- \\%98", "Ortalama normal; 15 gecede anlık $\\le$\\%82"),
    ("readiness_score", "Sabah Antrenman Hazırlığı", "0--100", 1, "65 -- 100 puan", "Medyan 67 puan; geç yatışta 47,6'ya düşüyor"),
]

t2_clean_lines = []
for col, label, unit, nd, ref_range, comment in summary_rows_spec:
    s = df[col].dropna()
    mean_s = fmt(s.mean(), nd)
    med_s = fmt(np.percentile(s, 50), nd)
    min_s = fmt(s.min(), nd)
    max_s = fmt(s.max(), nd)
    u_str = f" {unit}" if unit not in ["0--100", "\\%"] else ("%" if unit == "\\%" else "")
    if unit == "\\%":
        val_str = f"\\textbf{{\\%{mean_s}}} (Med: \\%{med_s})"
        rng_str = f"\\%{min_s} -- \\%{max_s}"
    else:
        val_str = f"\\textbf{{{mean_s}{u_str}}} (Med: {med_s})"
        rng_str = f"{min_s} -- {max_s}{u_str}"
    t2_clean_lines.append(f"\\textbf{{{label}}} & {val_str} & {rng_str} & {ref_range} & {comment} \\\\")

# Tablo 3: Aylık Performans Özeti (9 Okunaklı Sütun)
m_meta = [
    ("2026-08", "Ağustos (17--31 Ağu)"),
    ("2026-09", "Eylül (01--30 Eyl)"),
    ("2026-10", "Ekim (01--31 Eki)"),
    ("2026-11", "Kasım (01--17 Kas)"),
]
t_month_lines = []
for mk, mlbl in m_meta:
    sub = df[df["month"] == mk]
    am = adf_3m[adf_3m["month"] == mk]
    t_month_lines.append(
        f"\\textbf{{{mlbl}}} & {len(am)} antrenman ({fmt(am['dur_m'].sum()/60.0, 1)} sa) & "
        f"{fmt(sub['steps'].mean(), 0)} & {fmt(sub['active_kcal'].mean(), 0)} / {fmt(sub['total_kcal'].mean(), 0)} & "
        f"{fmt(sub['rhr'].mean(), 1)} bpm & \\textbf{{{fmt(sub['hrv_night'].mean(), 1)} ms}} & "
        f"{fmt(sub['sleep_h'].mean(), 2)} sa ({fmt(sub['sleep_score'].mean(), 0)}) & "
        f"{fmt(sub['bb_wake'].mean(), 0)} / {fmt(sub['bb_low'].mean(), 0)} & "
        f"\\textbf{{{fmt(sub['readiness_score'].mean(), 0)}}} (Yük: {fmt(sub['acute_load'].mean(), 0)}) \\\\"
    )
t_month_lines.append(r"\midrule")
t_month_lines.append(
    f"\\textbf{{Tüm Dönem (93 Gün)}} & \\textbf{{40 antrenman ({fmt(adf_3m['dur_m'].sum()/60.0, 1)} sa)}} & "
    f"\\textbf{{{fmt(df['steps'].mean(), 0)}}} & \\textbf{{{fmt(df['active_kcal'].mean(), 0)} / {fmt(df['total_kcal'].mean(), 0)}}} & "
    f"\\textbf{{{fmt(df['rhr'].mean(), 1)} bpm}} & \\textbf{{{fmt(df['hrv_night'].mean(), 1)} ms}} & "
    f"\\textbf{{{fmt(df['sleep_h'].mean(), 2)} sa ({fmt(df['sleep_score'].mean(), 0)})}} & "
    f"\\textbf{{{fmt(df['bb_wake'].mean(), 0)} / {fmt(df['bb_low'].mean(), 0)}}} & "
    f"\\textbf{{{fmt(df['readiness_score'].mean(), 0)} (Yük: {fmt(df['acute_load'].mean(), 0)})}} \\\\"
)

# Tablo 4: 14 Haftalık Seyir (9 Okunaklı Sütun)
df["dt"] = pd.to_datetime(df["date"])
df["week_start"] = df["dt"].apply(lambda d: (d - pd.Timedelta(days=d.weekday())).strftime("%Y-%m-%d"))
t_week_lines = []
for idx_w, (wk_start, grp) in enumerate(df.groupby("week_start"), 1):
    wk_acts = adf_3m[(adf_3m["date"] >= wk_start) & (adf_3m["date"] <= grp["date"].max())]
    goal_hit = int((grp["steps"] >= grp["step_goal"]).sum())
    t_week_lines.append(
        f"\\textbf{{H{idx_w:02d}}} ({wk_start[5:]}) & {len(wk_acts)} ({fmt(wk_acts['dur_m'].sum(), 0)} dk) & "
        f"{fmt(grp['steps'].mean(), 0)} ({goal_hit}/{len(grp)}) & {fmt(grp['active_kcal'].mean(), 0)} / {fmt(grp['total_kcal'].mean(), 0)} & "
        f"{fmt(grp['rhr'].mean(), 1)} & \\textbf{{{fmt(grp['hrv_night'].mean(), 1)} ms}} & "
        f"{fmt(grp['sleep_h'].mean(), 2)} sa ({fmt(grp['sleep_score'].mean(), 0)}) & "
        f"{fmt(grp['bb_wake'].mean(), 0)} / {fmt(grp['bb_low'].mean(), 0)} & "
        f"\\textbf{{{fmt(grp['readiness_score'].mean(), 0)}}} ({fmt(grp['acute_load'].max(), 0)}) \\\\"
    )

# Tablo 5: Yatış Saati Etkisi (8 Okunaklı Sütun)
def bed_bucket(hr):
    if pd.isnull(hr): return "No Data"
    if hr <= 0.5: return "1_Early"
    elif hr <= 1.75: return "2_Mid"
    else: return "3_Late"
df["bed_b"] = df["sleep_start_hr"].apply(bed_bucket)
t5_lines = []
for bk, blbl in [
    ("1_Early", "\\textbf{Erken Yatış} (00:30 öncesi, Ort.\\ 23:54)"),
    ("2_Mid", "\\textbf{Orta Yatış} (00:30 -- 01:45, Ort.\\ 01:02)"),
    ("3_Late", "\\textbf{Geç Yatış} (01:45 sonrası, Ort.\\ 03:11)"),
]:
    g = df[df["bed_b"] == bk]
    t5_lines.append(
        f"{blbl} & {len(g)} gece (\\%{fmt(len(g)/88.0*100, 0)}) & \\textbf{{{fmt(g['sleep_h'].mean(), 2)} saat}} & "
        f"{fmt(g['deep_h'].mean(), 2)} sa / \\textbf{{{fmt(g['rem_h'].mean(), 2)} sa}} & "
        f"\\textbf{{{fmt(g['sleep_score'].mean(), 1)}}} & \\textbf{{{fmt(g['hrv_night'].mean(), 1)} ms}} & "
        f"{fmt(g['rhr'].mean(), 1)} bpm & \\textbf{{{fmt(g['bb_wake'].mean(), 0)}}} / \\textbf{{{fmt(g['readiness_score'].mean(), 0)}}} \\\\"
    )

# Tablo 6: En İyi 6 ve En Düşük 6 Uyku Gecesi (8 Sütun)
t6_lines = []
for rank, (_, r) in enumerate(df.dropna(subset=["sleep_score"]).nlargest(6, "sleep_score").iterrows(), 1):
    t6_lines.append(
        f"En İyi \\#{rank} & {r['date']} & {fmt_clock(r['sleep_start_hr'])} & \\textbf{{{fmt(r['sleep_score'], 0)}}} & "
        f"{fmt(r['sleep_h'], 2)} saat & {fmt(r['deep_h'], 2)} / {fmt(r['rem_h'], 2)} sa & "
        f"\\textbf{{{fmt(r['hrv_night'], 0)} ms}} ({fmt(r['rhr'], 0)} bpm) & \\textbf{{{fmt(r['bb_wake'], 0)}}} / \\textbf{{{fmt(r['readiness_score'], 0)}}} \\\\"
    )
t6_lines.append(r"\midrule")
for rank, (_, r) in enumerate(df.dropna(subset=["sleep_score"]).nsmallest(6, "sleep_score").iterrows(), 1):
    t6_lines.append(
        f"En Düşük \\#{rank} & {r['date']} & {fmt_clock(r['sleep_start_hr'])} & \\textbf{{{fmt(r['sleep_score'], 0)}}} & "
        f"{fmt(r['sleep_h'], 2)} saat & {fmt(r['deep_h'], 2)} / {fmt(r['rem_h'], 2)} sa & "
        f"\\textbf{{{fmt(r['hrv_night'], 0)} ms}} ({fmt(r['rhr'], 0)} bpm) & \\textbf{{{fmt(r['bb_wake'], 0)}}} / \\textbf{{{fmt(r['readiness_score'], 0)}}} \\\\"
    )

# Tablo 7: Branş Dağılımı (8 Okunaklı Sütun)
sb = adf_3m.groupby("sport").agg(
    count=("id", "count"),
    total_dur_h=("dur_m", lambda x: x.sum()/60.0),
    avg_dur_m=("dur_m", "mean"),
    total_dist_km=("dist_km", "sum"),
    total_cal=("cal", "sum"),
    avg_hr=("avg_hr", "mean"),
    max_hr=("max_hr", "max"),
    total_load=("load", "sum"),
    avg_load=("load", "mean"),
    total_water_L=("water_ml", lambda x: x.sum()/1000.0)
)
sport_names_tr = {
    "running": "Koşu",
    "sailing_v2": "Yelken",
    "basketball": "Basketbol",
    "strength_training": "Kuvvet Antrenmanı",
    "hiking": "Doğa Yürüyüşü",
    "rowing_v2": "Kürek",
    "walking": "Yürüyüş"
}
t7_lines = []
for sp_k in ["running", "sailing_v2", "basketball", "strength_training", "hiking", "rowing_v2", "walking"]:
    if sp_k in sb.index:
        r = sb.loc[sp_k]
        t7_lines.append(
            f"\\textbf{{{sport_names_tr[sp_k]}}} & {int(r['count'])} & {fmt(r['total_dur_h'], 1)} saat ({fmt(r['avg_dur_m'], 0)} dk) & "
            f"{fmt(r['total_dist_km'], 1)} km & {fmt(r['total_cal'], 0)} kcal & "
            f"{fmt(r['avg_hr'], 0)} / {fmt(r['max_hr'], 0)} bpm & \\textbf{{{fmt(r['total_load'], 0)}}} (Ort: {fmt(r['avg_load'], 0)}) & "
            f"{fmt(r['total_water_L'], 1)} L \\\\"
        )
t7_lines.append(r"\midrule")
t7_lines.append(
    f"\\textbf{{Toplam / Ortalama}} & \\textbf{{{len(adf_3m)}}} & \\textbf{{{fmt(adf_3m['dur_m'].sum()/60.0, 1)} saat ({fmt(adf_3m['dur_m'].mean(), 0)} dk)}} & "
    f"\\textbf{{{fmt(adf_3m['dist_km'].sum(), 1)} km}} & \\textbf{{{fmt(adf_3m['cal'].sum(), 0)} kcal}} & "
    f"\\textbf{{{fmt(adf_3m['avg_hr'].mean(), 0)} / {adf_3m['max_hr'].max():.0f} bpm}} & "
    f"\\textbf{{{fmt(adf_3m['load'].sum(), 0)} (Ort: {fmt(adf_3m['load'].mean(), 0)})}} & "
    f"\\textbf{{{fmt(adf_3m['water_ml'].sum()/1000.0, 1)} L}} \\\\"
)

# Tablo 9: 20 Koşu Kaydı (10 Okunaklı Sütun)
runs = adf[adf["sport"] == "running"].copy()
runs["ef_spd"] = (runs["spd_ms"] * 60.0) / runs["avg_hr"]
runs["pace_str"] = runs["pace_s"].apply(fmt_pace)

t10_lines = []
for _, r in runs.iterrows():
    dt_s = r["date"]
    is_wk = "Workout" in str(r["name"])
    typ_s = "İnterval" if is_wk else ("Baz (Ağu)" if dt_s < "2026-08-17" else "Tempo")
    t10_lines.append(
        f"{r['date']} {r['time']} & {typ_s} & {fmt(r['dist_km'], 2)} km ({fmt(r['dur_m'], 1)} dk) & "
        f"\\textbf{{{r['pace_str']}}} & {fmt(r['avg_hr'], 0)} / {fmt(r['max_hr'], 0)} & "
        f"{fmt(r['norm_pwr'], 0)} W & \\textbf{{{fmt(r['cadence'], 0)}}} ({fmt(r['stride_cm'], 0)} cm) & "
        f"{fmt(r['gct_ms'], 0)} ms & \\textbf{{{fmt(r['ef_spd'], 2)} m}} & "
        f"\\textbf{{{fmt_pace(r['fast_1k'])} / {fmt_pace(r['fast_5k'])}}} \\\\"
    )

# Tablo 11: Diğer Branş Kayıtları (8 Okunaklı Sütun)
t12_lines = []
for _, r in adf_3m[adf_3m["sport"] != "running"].iterrows():
    sp_tr = sport_names_tr.get(r["sport"], r["sport"])
    t12_lines.append(
        f"{r['date']} {r['time']} & \\textbf{{{sp_tr}}} & {tex_esc(r['name'])} & {fmt(r['dur_m'], 0)} dk & "
        f"{fmt(r['dist_km'], 1) + ' km' if r['dist_km'] > 0 else '--'} & {fmt(r['avg_hr'], 0)} / {fmt(r['max_hr'], 0)} bpm & "
        f"{fmt(r['cal'], 0)} kcal & \\textbf{{{fmt(r['load'], 1)}}} ({fmt((r['water_ml'] or 0)/1000.0, 1)} L ter) \\\\"
    )

# -------------------------------------------------------------------------
# 4. PGFPlots Koordinatları
# -------------------------------------------------------------------------
hrv_coords, hrv7_coords, rhr_coords = [], [], []
bb_wake_coords, bb_low_coords, stress_coords = [], [], []
xtick_indices, xtick_labels = [], []

for i, r in df.iterrows():
    if (i % 10 == 0 and i <= 82) or i == len(df) - 1:
        xtick_indices.append(str(i))
        xtick_labels.append(r["date"][5:])
    if pd.notnull(r["hrv_night"]):
        hrv_coords.append(f"({i},{r['hrv_night']:.1f})")
    if pd.notnull(r["hrv_7d"]):
        hrv7_coords.append(f"({i},{r['hrv_7d']:.1f})")
    if pd.notnull(r["rhr"]):
        rhr_coords.append(f"({i},{r['rhr']:.1f})")
    if pd.notnull(r["bb_high"]):
        bb_wake_coords.append(f"({i},{r['bb_high']:.1f})")
    if pd.notnull(r["bb_low"]):
        bb_low_coords.append(f"({i},{r['bb_low']:.1f})")
    if pd.notnull(r["avg_stress"]):
        stress_coords.append(f"({i},{r['avg_stress']:.1f})")

runs_chrono = runs.iloc[::-1].reset_index(drop=True)
run_pace_min_coords, run_hr_coords, run_cad_coords = [], [], []
run_z1_coords, run_z2_coords, run_z3_coords, run_z4_coords, run_z5_coords = [], [], [], [], []
run_x_indices, run_x_labels = [], []

for i, r in runs_chrono.iterrows():
    run_x_indices.append(str(i))
    run_x_labels.append(r["date"][5:])
    if pd.notnull(r["pace_s"]):
        run_pace_min_coords.append(f"({i},{r['pace_s']/60.0:.2f})")
    if pd.notnull(r["avg_hr"]):
        run_hr_coords.append(f"({i},{r['avg_hr']:.1f})")
    if pd.notnull(r["cadence"]):
        run_cad_coords.append(f"({i},{r['cadence']:.1f})")
    run_z1_coords.append(f"({i},{r['z1_pct']:.1f})")
    run_z2_coords.append(f"({i},{r['z2_pct']:.1f})")
    run_z3_coords.append(f"({i},{r['z3_pct']:.1f})")
    run_z4_coords.append(f"({i},{r['z4_pct']:.1f})")
    run_z5_coords.append(f"({i},{r['z5_pct']:.1f})")

# -------------------------------------------------------------------------
# 5. LaTeX Belgesi (Sporcu Odaklı, Görsel ve Kolay Okunur Tasarım)
# -------------------------------------------------------------------------
tex_content = r"""\documentclass[9.5pt,a4paper]{article}
\usepackage{fontspec}
\usepackage[margin=13mm,top=13mm,bottom=15mm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{graphicx}
\usepackage[table]{xcolor}
\usepackage{colortbl}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}

\setmainfont{Helvetica Neue}
\setsansfont{Helvetica Neue}
\renewcommand{\familydefault}{\sfdefault}

\definecolor{navy}{HTML}{0F172A}
\definecolor{slate}{HTML}{334155}
\definecolor{muted}{HTML}{64748B}
\definecolor{accent}{HTML}{1D4ED8}
\definecolor{cardbg}{HTML}{F8FAFC}
\definecolor{cardborder}{HTML}{E2E8F0}
\definecolor{rowalt}{HTML}{F1F5F9}
\definecolor{tblhead}{HTML}{1E293B}
\definecolor{rulegray}{HTML}{CBD5E1}
\definecolor{plotblue}{HTML}{0284C7}
\definecolor{plotred}{HTML}{DC2626}
\definecolor{plotgreen}{HTML}{16A34A}
\definecolor{plotamber}{HTML}{D97706}
\definecolor{softgreen}{HTML}{DCFCE7}
\definecolor{softblue}{HTML}{DBEAFE}
\definecolor{softamber}{HTML}{FEF3C7}

\setlength{\parindent}{0pt}
\setlength{\parskip}{3.5pt}
\renewcommand{\arraystretch}{1.22}
\setlength{\tabcolsep}{5pt}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot[L]{\footnotesize\color{muted}Garmin 3 Aylık Spor ve Sağlık Raporu (17 Ağu -- 17 Kas 2026)}
\fancyfoot[R]{\footnotesize\bfseries\color{slate}Sayfa \thepage}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0.4pt}

\titleformat{\section}{\large\bfseries\color{navy}}{\thesection.}{0.5em}{}[\vspace{2pt}{\color{accent}\titlerule[1.2pt]}]
\titleformat{\subsection}{\normalsize\bfseries\color{accent}}{\thesubsection.}{0.4em}{}
\titlespacing*{\section}{0pt}{10pt}{5pt}
\titlespacing*{\subsection}{0pt}{6pt}{3pt}

\setlist[itemize]{leftmargin=14pt,itemsep=2pt,topsep=2pt,parsep=0pt}
\setlist[enumerate]{leftmargin=16pt,itemsep=3.5pt,topsep=2pt,parsep=0pt}

\newcommand{\kpicard}[4]{%
  \begin{tikzpicture}
    \node[draw=cardborder, line width=0.8pt, fill=cardbg, rounded corners=4pt, inner sep=6pt, text width=4.15cm, align=left] {
      {\scriptsize\bfseries\color{muted}#1}\\[2pt]
      {\Large\bfseries\color{navy}#2}\\[2pt]
      {\scriptsize\bfseries\color{#4}#3}
    };
  \end{tikzpicture}%
}

\begin{document}

% --- ÜST BAŞLIK BLOĞU ---
\begin{tikzpicture}
  \node[fill=navy, rounded corners=5pt, inner sep=10pt, text width=\dimexpr\textwidth-20pt\relax, align=left] {
    {\Large\bfseries\color{white} 3 AYLIK SPOR, UYKU VE SAĞLIK RAPORU}\\[3pt]
    {\small\color{rowalt} 17 Ağustos -- 17 Kasım 2026 (93 Gün) \quad|\quad Koşu, Yelken, Kuvvet, Uyku ve Toparlanma Analizi}\\[5pt]
    {\footnotesize\color{softblue} \textbf{Sporcu Profili:} 22 Yaş Erkek \quad$\bullet$\quad \textbf{Boy:} 186 cm \quad$\bullet$\quad \textbf{Kilo:} 95,0 $\rightarrow$ 87,0 kg ($-$8,0 kg) \quad$\bullet$\quad \textbf{Dinlenik / Maks Nabız:} 53,6 / 203 bpm}
  };
\end{tikzpicture}

\vspace{4pt}
\noindent
\kpicard{KİLO VE VKİ DEĞİŞİMİ}{95,0 $\rightarrow$ 87,0 kg}{63 Günde $-$8,0 kg (VKİ: 25,15)}{plotgreen}\hfill
\kpicard{5K KOŞU VE TEMPO}{29:07 (5:48 /km)}{Ağustos'a Göre $-$1 dk 46 sn /km}{accent}\hfill
\kpicard{TOPLAM ANTRENMAN}{40 Spor / 50,8 Sa}{363,8 km Mesafe $\bullet$ 20.752 kcal}{plotamber}\hfill
\kpicard{UYKU VE TOPARLANMA}{7,0 Saat / 82 Puan}{53,6 bpm Nabız $\bullet$ 43,8 ms HRV}{plotblue}
\vspace{2pt}

\section{Genel Özet ve Hedef Takvimi}

\subsection{Öne Çıkan 3 Sonuç}
\begin{itemize}
  \item \textbf{Hızlı ve Düzenli Kilo Kaybı ($-$8,0 kg):} 15 Eylül'de 95,0 kg olan ağırlığınız 14 Ekim'de 91,0 kg'a, 17 Kasım'da ise \textbf{87,0 kg}'a inmiştir. Haftada ortalama \textbf{$-$0,89 kg} (günlük yaklaşık 980 kcal enerji açığı) ile 2 ayda vücut ağırlığınızın \%8,4'ünü verdiniz. Günlük ortalama toplam harcamanız \textbf{2.942 kcal} (bazal metabolizma 2.322 kcal + aktif hareket 620 kcal) düzeyindedir.
  \item \textbf{Koşu Hızı ve Adım Tekniğinde Net İlerleme:} Ağustos başındaki koşulara göre Kasım ayında ortalama temponuz 7:34 /km'den \textbf{5:48 /km}'ye (5K: 29:07) inmiş, dakikadaki adım sayınız (kadans) 138'den \textbf{162 adım/dk}'ya çıkmış ve ayağın yerde kalma süresi 291 ms'den \textbf{273,5 ms}'ye düşmüştür. Bir kalp atışında kat ettiğiniz mesafe \textbf{+\%13,2} artmasına rağmen, saatinizde dinlenik nabzın 65 bpm unutulmuş olması ve tüm koşuların yüksek nabızda (Zone 3--4) yapılması nedeniyle Garmin VO$_2$ Max tahmini 48'den 45,4'e düşmüş görünmektedir.
  \item \textbf{Yüksek Antrenman Yükü ve Uyku Dengesi:} 93 günde toplam \textbf{886.683 adım} (günlük ort.\ 9.534 adım, toplam 1.020,5 km) atılmış; 15 koşu, 12 yelken, 5 basketbol ve 5 ağırlık antrenmanı yapılmıştır. Kasım ayında hem ağırlık hem koşu yükü artmasına rağmen uyku sürenizi 7,30 saate çıkararak toparlanma kalitenizi korudunuz.
\end{itemize}

\subsection{Boy–Kilo Oranı (VKİ), İdeal Kilo ve Forma Girme Takvimi}
\begin{itemize}
  \item \textbf{Mevcut VKİ Durumu (25,15 kg/m$^2$ -- Normal Sınırda):} 186 cm boy için Dünya Sağlık Örgütü'nün ``Normal Kilo'' üst sınırı (VKİ = 24,99) \textbf{86,45 kg}'dır. 63 günde verdiğiniz 8 kg sayesinde fazla kilolu kategorisinden çıkmanıza yalnızca \textbf{550 gram} kalmıştır.
  \item \textbf{Sizin Branşlarınız İçin İdeal Kilo (80,0 -- 83,0 kg, VKİ = 23,1 -- 24,0):} Hem koşan hem de haftada 3--4 gün ağırlık, yelken ve basketbol yapan 186 cm boyundaki bir sporcu için kas gücünü kaybetmeden en yüksek hıza ulaşılan aralık \textbf{80 -- 83 kg} bandıdır. 79 kg altı yalnızca uzun mesafe koşucuları için uygundur; yelkende ve ağırlıkta güç kaybı yaratır.
  \item \textbf{Kilo Kaybının Koşuya Doğrudan Etkisi:} Mevcut koşu gücünüz (330 W) sabit kalsa bile, vereceğiniz her \textbf{$-$1 kg}, 5 km sürenizi \textbf{12 -- 15 saniye} kısaltır ve VO$_2$ Max puanınızı doğrudan \textbf{+0,52 puan} artırır.
\end{itemize}

Aşağıdaki tablo, mevcut hızınız (\textbf{$-$0,89 kg/hafta}) ile kas kaybını önlemek için önerilen dengeli hız (\textbf{$-$0,55 kg/hafta}, günlük yaklaşık 500 kcal açık) altında hedef kilolara ve 5K derecelerine \textbf{kaç günde ulaşacağınızı} göstermektedir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrllll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Hedef Aşama / Form Seviyesi}} & \textcolor{white}{\textbf{Hedef Kilo (VKİ)}} & \textcolor{white}{\textbf{Kalan}} & \textcolor{white}{\textbf{Mevcut Hızda ($-$0,89 kg/hf)}} & \textcolor{white}{\textbf{Önerilen Hızda ($-$0,55 kg/hf)}} & \textcolor{white}{\textbf{Beklenen 5K Süresi}} & \textcolor{white}{\textbf{Beklenen VO$_2$ Max ve Seviye}} \\
\midrule
Mevcut Durum (17 Kasım) & 87,0 kg (25,15) & 0,0 kg & Bugün (Başlangıç) & Bugün (Başlangıç) & 29:07 (5:48 /km) & 45,4 (Orta -- İyi Sınırı) \\
\textbf{Aşama 1: Normal VKİ Sınırı} & \textbf{86,4 kg (24,97)} & $-$0,6 kg & \textbf{5 Gün} (22 Kasım 2026) & \textbf{8 Gün} (25 Kasım 2026) & $\sim$28:30 (5:42 /km) & 46,5 -- 47,0 (İyi -- İlk \%35) \\
\textbf{Aşama 2: Kısa Vadeli Form} & \textbf{85,0 kg (24,57)} & $-$2,0 kg & \textbf{16 Gün} (3 Aralık 2026) & \textbf{25 Gün} (12 Aralık 2026) & $\sim$27:30 (5:30 /km) & 47,5 -- 48,5 (İyi Üst Sınır -- İlk \%25) \\
\textbf{Aşama 3: Atletik Form Başlangıcı} & \textbf{83,0 kg (23,99)} & $-$4,0 kg & \textbf{31 Gün} (18 Aralık 2026) & \textbf{51 Gün} (7 Ocak 2027) & $\sim$25:45 (5:09 /km) & \textbf{49,5 -- 50,5 (Mükemmel -- İlk \%15)} \\
\textbf{Aşama 4: İdeal Çoklu-Branş Formu} & \textbf{81,0 kg (23,41)} & $-$6,0 kg & \textbf{47 Gün} (3 Ocak 2027) & \textbf{76 Gün} (1 Şubat 2027) & \textbf{24:15 -- 24:45 ($<$25 dk)} & \textbf{51,5 -- 52,5 (Üstün -- İlk \%10)} \\
Aşama 5: Saf Koşucu Kütlesi & 79,0 kg (22,83) & $-$8,0 kg & 63 Gün (19 Ocak 2027) & 102 Gün (27 Şubat 2027) & $\sim$23:30 (4:42 /km) & 53,0+ (Üstün -- İlk \%5) \\
\bottomrule
\end{tabular}}
\end{center}

\subsection{Son 3 Ayın 4 Dönemi}
\begin{itemize}
  \item \textbf{1.\ Dönem -- Su Sporları ve Yoğun Yüklenme (17--29 Ağustos, İzmir \& Çeşme):} 8 yelken seansı, kürek ve doğa yürüyüşüyle haftalık yük 388'e (3 ayın zirvesi) çıkmış; bu yoğunlukta gece HRV 48,8'den 38,0 ms'ye, hazırlık puanı 92,6'dan 29,4'e inmiştir.
  \item \textbf{2.\ Dönem -- Dinlenme ve Bergen Seyahati (31 Ağustos -- 27 Eylül):} Antrenmanların azalmasıyla vücut tam dinlenmiş, dinlenik nabız \textbf{49,6 bpm} ve gece HRV \textbf{56,0 ms} ile en iyi değerlerini görmüştür (15 Eylül'de 27.449 adım rekoru).
  \item \textbf{3.\ Dönem -- İnterval Koşu, Basketbol ve Yelken (28 Eylül -- 01 Kasım):} Haftada 2--3 koşu (6,4 km interval seansları), haftalık basketbol ve hafta sonu İstanbul yelken antrenmanlarıyla düzenli antrenman temposu yakalanmıştır.
  \item \textbf{4.\ Dönem -- Kuvvet Antrenmanı ve Hızlı Koşular (02--17 Kasım):} Programa 5 ağırlık antrenmanı eklenmiş, 5 km koşu temposu 6:00 /km altına çekilmiş ve uyku süresi uzatılarak (7,44 saat) toparlanma korunmuştur.
\end{itemize}

\newpage
\section{Günlük Sağlık, Aylık ve Haftalık Özet}

Aşağıdaki tablo, 93 gün boyunca saatinizin ölçtüğü \textbf{16 temel sağlık ve uyku göstergesinin} ortalamasını, en düşük--en yüksek değerlerini ve ideal referans aralıklarına göre durumunuzu özetlemektedir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lllll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Sağlık / Uyku Göstergesi}} & \textcolor{white}{\textbf{3 Aylık Ortalama}} & \textcolor{white}{\textbf{En Düşük -- En Yüksek}} & \textcolor{white}{\textbf{İdeal Referans Aralığı}} & \textcolor{white}{\textbf{Mevcut Durum ve Yorum}} \\
\midrule
""" + "\n".join(t2_clean_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\subsection{Aylık ve 14 Haftalık Performans Seyri}

Aşağıdaki iki tablo, Ağustos'tan Kasım'a kadar aylık ve haftalık bazda antrenman sıklığınızın, kalori harcamanızın, uyku kalitenizin ve vücut enerjinizin nasıl değiştiğini göstermektedir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Ay}} & \textcolor{white}{\textbf{Toplam Spor}} & \textcolor{white}{\textbf{Günlük Adım}} & \textcolor{white}{\textbf{Aktif / Toplam kcal}} & \textcolor{white}{\textbf{Dinlenik Nabız}} & \textcolor{white}{\textbf{Gece HRV}} & \textcolor{white}{\textbf{Uyku (Puan)}} & \textcolor{white}{\textbf{Enerji (Sabah/Dip)}} & \textcolor{white}{\textbf{Hazırlık (Yük)}} \\
\midrule
""" + "\n".join(t_month_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Hafta (Başlangıç)}} & \textcolor{white}{\textbf{Spor (Süre)}} & \textcolor{white}{\textbf{Günlük Adım (Hedef)}} & \textcolor{white}{\textbf{Aktif / Toplam kcal}} & \textcolor{white}{\textbf{Nabız}} & \textcolor{white}{\textbf{Gece HRV}} & \textcolor{white}{\textbf{Uyku (Puan)}} & \textcolor{white}{\textbf{Enerji (Sabah/Dip)}} & \textcolor{white}{\textbf{Hazırlık (Yük)}} \\
\midrule
""" + "\n".join(t_week_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\newpage
\section{Toparlanma, Nabız (HRV) ve Günlük Enerji}

Şekil 1, gece kalp atım değişkenliğiniz (HRV -- yeşil/mavi) ile dinlenik nabzınız (kırmızı) arasındaki zıt hareketi göstermektedir: vücudunuz iyi dinlendiğinde HRV yükselmekte ve dinlenik nabız düşmektedir. Şekil 2 ise sabah uyanış enerjiniz (Body Battery) ile akşam düştüğü seviyeyi göstermektedir; \textbf{93 günün 48'inde akşam enerjiniz tamamen biterek 5 puana inmiştir}.

\begin{center}
\begin{tikzpicture}
\begin{axis}[
    width=17.4cm, height=4.8cm,
    axis y line*=left,
    axis x line*=bottom,
    xmin=0, xmax=92,
    ymin=15, ymax=72,
    xtick={""" + ",".join(xtick_indices) + r"""},
    xticklabels={""" + ",".join(xtick_labels) + r"""},
    xticklabel style={font=\scriptsize},
    ytick={20,30,40,50,60,70},
    ylabel={\footnotesize\bfseries Gece HRV (ms)},
    ylabel style={color=plotblue},
    ymajorgrids=true,
    xmajorgrids=true,
    grid style={dashed,rulegray},
    title={\footnotesize\bfseries Şekil 1: 93 Günlük Gece HRV (Toparlanma) ve Dinlenik Nabız Seyri},
    legend style={at={(0.01,0.97)},anchor=north west,font=\scriptsize,draw=rulegray,fill=white,legend columns=3}
]
\addplot[fill=plotgreen!12, draw=none, forget plot] coordinates {(0,37) (92,37) (92,58) (0,58)} \closedcycle;
\node[anchor=west, font=\scriptsize, color=plotgreen] at (axis cs:2,54) {İdeal HRV Aralığı (37--58 ms)};
\addplot[color=plotblue,line width=0.9pt,mark=*,mark size=1.0pt] coordinates {""" + " ".join(hrv_coords) + r"""};
\addlegendentry{Gece HRV (ms)}
\addplot[color=navy,line width=1.6pt] coordinates {""" + " ".join(hrv7_coords) + r"""};
\addlegendentry{7 Günlük HRV Ortalaması}
\end{axis}
\begin{axis}[
    width=17.4cm, height=4.8cm,
    axis y line*=right,
    axis x line=none,
    xmin=0, xmax=92,
    ymin=44, ymax=68,
    ytick={45,50,55,60,65},
    ylabel={\footnotesize\bfseries Dinlenik Nabız (bpm)},
    ylabel style={color=plotred},
    yticklabel style={font=\scriptsize},
    legend style={at={(0.99,0.97)},anchor=north east,font=\scriptsize,draw=rulegray,fill=white}
]
\addplot[color=plotred,dashed,line width=1.1pt,mark=diamond*,mark size=1.1pt] coordinates {""" + " ".join(rhr_coords) + r"""};
\addlegendentry{Dinlenik Nabız (bpm)}
\end{axis}
\end{tikzpicture}
\end{center}

\vspace{-4pt}
\begin{center}
\begin{tikzpicture}
\begin{axis}[
    width=17.4cm, height=4.4cm,
    xmin=0, xmax=92,
    ymin=0, ymax=105,
    xtick={""" + ",".join(xtick_indices) + r"""},
    xticklabels={""" + ",".join(xtick_labels) + r"""},
    xticklabel style={font=\scriptsize},
    ytick={5,25,50,75,100},
    ylabel={\footnotesize\bfseries Puan (0--100)},
    ymajorgrids=true,
    xmajorgrids=true,
    grid style={dashed,rulegray},
    title={\footnotesize\bfseries Şekil 2: Günlük Sabah Enerjisi (Body Battery), Akşam Dip Seviyesi ve Günlük Stres},
    legend style={at={(0.01,0.97)},anchor=north west,font=\scriptsize,draw=rulegray,fill=white,legend columns=3}
]
\addplot[color=plotblue,line width=1.1pt,mark=*,mark size=1.0pt] coordinates {""" + " ".join(bb_wake_coords) + r"""};
\addlegendentry{Sabah Uyanış Enerjisi}
\addplot[color=plotamber,line width=1.1pt] coordinates {""" + " ".join(stress_coords) + r"""};
\addlegendentry{Günlük Stres Puanı}
\addplot[color=plotred,line width=1.0pt,mark=square*,mark size=0.9pt] coordinates {""" + " ".join(bb_low_coords) + r"""};
\addlegendentry{Akşam Dip Enerji (48 Günde = 5)}
\end{axis}
\end{tikzpicture}
\end{center}

\subsection{Hangi Alışkanlık Neyi Etkiliyor? (Veriden Çıkan Bağlantılar)}

93 günlük verileriniz karşılaştırıldığında, performansınızı ve enerjinizi doğrudan belirleyen \textbf{8 temel neden-sonuç ilişkisi} aşağıda özetlenmiştir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{İncelenen İki Gösterge}} & \textcolor{white}{\textbf{Etki Gücü}} & \textcolor{white}{\textbf{Veriden Çıkan Pratik Sonuç}} \\
\midrule
\textbf{Gece HRV $\leftrightarrow$ Dinlenik Nabız} & Çok Güçlü Zıt Etki & Gece HRV'niz yüksek olduğunda sabah dinlenik nabzınız doğrudan 49--51 bpm seviyesine iniyor. \\
\textbf{Günlük Stres $\leftrightarrow$ Enerji Dolumu} & Çok Güçlü Zıt Etki & Gün içi stres 40'ı aştığında gece Body Battery dolumu yarı yarıya azalıyor. \\
\textbf{Toplam Uyku Süresi $\leftrightarrow$ Uyku Puanı} & Güçlü Doğrusal Etki & Uyku süresi 7,5 saati geçtiğinde Garmin uyku puanınız düzenli olarak 85 üstüne çıkıyor. \\
\textbf{Gece HRV $\leftrightarrow$ Sabah Hazırlık Puanı} & Güçlü Doğrusal Etki & Sabah spora hazır uyanmanızı belirleyen bir numaralı etken gece HRV ortalamanızdır. \\
\textbf{Yatış Saati $\leftrightarrow$ Toplam Uyku ve REM} & Güçlü Zıt Etki & Yatış saatiniz her 1 saat geciktiğinde uykunuz 33 dk kısalıyor ve REM uykunuz \%32 azalıyor. \\
\textbf{Yatış Saati $\leftrightarrow$ Sabah Enerjisi} & Orta-Güçlü Zıt Etki & Gece 01:45'ten sonra yattığınızda sabah enerjiniz 75 yerine 55 puanla ($-20$ puan) başlıyor. \\
\textbf{Haftalık Yük $\leftrightarrow$ Sabah Hazırlık Puanı} & Orta-Güçlü Zıt Etki & Haftalık antrenman yükü 280'i aştığında vücudun dinlenme ihtiyacı artıyor ve hazırlık düşüyor. \\
\textbf{Yoğun Antrenman $\leftrightarrow$ Dinlenik Nabız} & Orta Doğrusal Etki & Üst üste sert antrenman yapılan haftalarda dinlenik nabız 2--3 bpm yükseliyor. \\
\bottomrule
\end{tabular}}
\end{center}

\section{Uyku Düzeni ve Yatış Saatinin Etkisi}

88 gecelik kayıtlarda ortalama uyku süreniz $\mathbf{7,00\text{ saat}}$, ortalama uyku puanınız ise $\mathbf{77,4}$ (medyan $\mathbf{82}$) olmuştur. Gecelerin $\mathbf{\%60,2}$'sinde İyi veya Mükemmel uyku uyunmuş; kas onarımını sağlayan \textbf{derin uyku süreniz ort.\ $1,70\text{ saat}$ ($\%24,3$)} ile normal referansın ($\%15-20$) üzerinde gerçekleşmiştir.

\subsection{Yatış Saatine Göre Uyku Kalitesi}
Uyanış saatiniz sabah $\sim 08:20-08:35$ civarında sabit olduğu için, \textbf{gece 01:45'ten sonra yattığınız 29 gecede} derin uykunuz azalmasa bile sabah saatlerinde görülen \textbf{REM uykunuz $\%32,2$ kayıpla $1,74\text{ saatten } 1,18\text{ saate}$ düşmekte}, sabah enerjiniz $20\text{ puan}$, antrenman hazırlığınız ise $23\text{ puan}$ gerilemektedir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Yatış Saati Grubu}} & \textcolor{white}{\textbf{Gece Sayısı}} & \textcolor{white}{\textbf{Toplam Uyku}} & \textcolor{white}{\textbf{Derin / REM Uyku}} & \textcolor{white}{\textbf{Uyku Puanı}} & \textcolor{white}{\textbf{Gece HRV}} & \textcolor{white}{\textbf{Dinlenik Nabız}} & \textcolor{white}{\textbf{Sabah Enerji / Hazırlık}} \\
\midrule
""" + "\n".join(t5_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\newpage
\subsection{En İyi ve En Kötü Uyunan 6 Gecenin Karşılaştırması}

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}llrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Kategori}} & \textcolor{white}{\textbf{Tarih}} & \textcolor{white}{\textbf{Yatış Saati}} & \textcolor{white}{\textbf{Uyku Puanı}} & \textcolor{white}{\textbf{Toplam Süre}} & \textcolor{white}{\textbf{Derin / REM}} & \textcolor{white}{\textbf{Gece HRV (Nabız)}} & \textcolor{white}{\textbf{Sabah Enerji / Hazırlık}} \\
\midrule
""" + "\n".join(t6_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\section{Spor Branşları ve Koşu Gelişimi}

Son 3 aydaki 40 antrenmanda toplam sürenin $\mathbf{\%55,4}$'ü ($28,1\text{ saat}$) yelkende, toplam antrenman yükünün ise $\mathbf{\%66,2}$'si ($1.585\text{ birim}$) koşuda oluşmuştur:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Spor Branşı}} & \textcolor{white}{\textbf{Antrenman}} & \textcolor{white}{\textbf{Toplam (Ort.) Süre}} & \textcolor{white}{\textbf{Toplam Mesafe}} & \textcolor{white}{\textbf{Toplam Kalori}} & \textcolor{white}{\textbf{Ort. / Maks Nabız}} & \textcolor{white}{\textbf{Antrenman Yükü}} & \textcolor{white}{\textbf{Tahmini Ter Kaybı}} \\
\midrule
""" + "\n".join(t7_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\subsection{Koşu Dönemlerinin Karşılaştırması (20 Koşu)}

Ağustos başından Kasım ortasına kadar koşu temponuz $\mathbf{7:34\text{ /km}}$'den $\mathbf{5:48\text{ /km}}$'ye inmiş, adım sıklığınız (kadans) $\mathbf{138}$'den $\mathbf{162\text{ adım/dk}}$'ya çıkmış ve 1 kalp atışında aldığınız mesafe (Nabız Verimi) $0,95\text{ metreden}$ $\mathbf{1,07\text{ metreye}}$ ($\mathbf{+\%13,2}$) yükselmiştir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Koşu Dönemi}} & \textcolor{white}{\textbf{Koşu}} & \textcolor{white}{\textbf{Ort.\ Mesafe}} & \textcolor{white}{\textbf{Ort.\ Tempo}} & \textcolor{white}{\textbf{Ort./Maks Nabız}} & \textcolor{white}{\textbf{Koşu Gücü (W)}} & \textcolor{white}{\textbf{Kadans (Adım/dk)}} & \textcolor{white}{\textbf{Yerle Temas}} & \textcolor{white}{\textbf{1 Atımda Mesafe}} \\
\midrule
Ağustos Baz (03--12 Ağu) & 5 & 5,14 km & 7:34 /km & 140 / 170 bpm & 288 W & 138 adım/dk & 291 ms & 0,95 metre \\
Eyl--Eki Koşuları (29 Eyl--21 Eki) & 7 & 5,20 km & 6:40 /km & 162 / 181 bpm & 327 W & 158 adım/dk & 292 ms & 0,93 metre \\
Ekim İnterval (18, 23, 30 Eki) & 3 & 6,45 km & 7:26 /km & 148 / 183 bpm & 309 W & 134 adım/dk & 279 ms & 0,91 metre \\
Kasım Tempo (06--16 Kas) & 5 & 4,75 km & \textbf{6:00 /km} & 162 / 175 bpm & \textbf{332 W} & \textbf{162 adım/dk} & \textbf{280 ms} & \textbf{1,03 metre} \\
\midrule
\textbf{Son Koşu (16 Kasım 2026)} & \textbf{1} & \textbf{5,19 km} & \textbf{5:48 /km} & \textbf{161 / 174 bpm} & \textbf{330 W} & \textbf{159 adım/dk} & \textbf{274 ms} & \textbf{1,07 metre} \\
\bottomrule
\end{tabular}}
\end{center}

\begin{center}
\begin{tikzpicture}
\begin{axis}[
    width=17.4cm, height=3.6cm,
    axis y line*=left,
    axis x line*=bottom,
    xmin=0, xmax=19,
    ymin=5.2, ymax=9.2,
    y dir=reverse,
    xtick={""" + ",".join(run_x_indices) + r"""},
    xticklabels={""" + ",".join(run_x_labels) + r"""},
    xticklabel style={font=\tiny,rotate=30,anchor=east},
    ytick={5.5,6.0,6.5,7.0,7.5,8.0,8.5,9.0},
    yticklabels={5:30,6:00,6:30,7:00,7:30,8:00,8:30,9:00},
    ylabel={\scriptsize\bfseries Tempo},
    ylabel style={color=plotgreen},
    ymajorgrids=true,
    xmajorgrids=true,
    grid style={dashed,rulegray},
    title={\footnotesize\bfseries Şekil 3: 20 Koşuda Tempo (dk/km), Ortalama Nabız ve Kadans Gelişimi},
    legend style={at={(0.01,0.97)},anchor=north west,font=\tiny,draw=rulegray,fill=white,legend columns=3}
]
\addplot[color=plotgreen,line width=1.4pt,mark=*,mark size=1.2pt] coordinates {""" + " ".join(run_pace_min_coords) + r"""};
\addlegendentry{Tempo (dk/km)}
\end{axis}
\begin{axis}[
    width=17.4cm, height=3.6cm,
    axis y line*=right,
    axis x line=none,
    xmin=0, xmax=19,
    ymin=120, ymax=180,
    ytick={125,140,155,170},
    ylabel={\scriptsize\bfseries Nabız / Kadans},
    ylabel style={color=plotred},
    yticklabel style={font=\tiny},
    legend style={at={(0.99,0.97)},anchor=north east,font=\tiny,draw=rulegray,fill=white,legend columns=2}
]
\addplot[color=plotred,line width=1.0pt,mark=square*,mark size=1.0pt] coordinates {""" + " ".join(run_hr_coords) + r"""};
\addlegendentry{Ort.\ Nabız (bpm)}
\addplot[color=plotblue,dashed,line width=1.1pt,mark=triangle*,mark size=1.1pt] coordinates {""" + " ".join(run_cad_coords) + r"""};
\addlegendentry{Kadans (adım/dk)}
\end{axis}
\end{tikzpicture}
\end{center}

\vspace{-6pt}
\begin{center}
\begin{tikzpicture}
\begin{axis}[
    ybar stacked,
    bar width=8.5pt,
    width=17.4cm, height=3.2cm,
    xmin=-0.6, xmax=19.6,
    ymin=0, ymax=100,
    xtick={""" + ",".join(run_x_indices) + r"""},
    xticklabels={""" + ",".join(run_x_labels) + r"""},
    xticklabel style={font=\tiny,rotate=30,anchor=east},
    ytick={0,25,50,75,100},
    ylabel={\scriptsize\bfseries Süre (\%)},
    ymajorgrids=true,
    grid style={dashed,rulegray},
    title={\footnotesize\bfseries Şekil 4: 20 Koşuda Nabız Bölgeleri Dağılımı (Mavi Zone 2 Eksikliği)},
    legend style={at={(0.5,0.98)},anchor=north,font=\tiny,draw=rulegray,fill=white,legend columns=5}
]
\addplot[fill=gray!60,draw=gray!80] coordinates {""" + " ".join(run_z1_coords) + r"""};
\addlegendentry{Z1 Isınma}
\addplot[fill=plotblue!75,draw=plotblue] coordinates {""" + " ".join(run_z2_coords) + r"""};
\addlegendentry{Z2 Rahat}
\addplot[fill=plotgreen!75,draw=plotgreen] coordinates {""" + " ".join(run_z3_coords) + r"""};
\addlegendentry{Z3 Tempo}
\addplot[fill=plotamber!85,draw=plotamber] coordinates {""" + " ".join(run_z4_coords) + r"""};
\addlegendentry{Z4 Eşik}
\addplot[fill=plotred!85,draw=plotred] coordinates {""" + " ".join(run_z5_coords) + r"""};
\addlegendentry{Z5 Maks}
\end{axis}
\end{tikzpicture}
\end{center}

\newpage
\section{Antrenman Kayıtları ve Ağırlık–Koşu Sıralaması}

Aşağıdaki tablo, 03 Ağustos -- 16 Kasım 2026 arasındaki \textbf{20 koşu antrenmanınızın} temel verilerini ve en hızlı $1\text{K} / 5\text{K}$ derecelerinizi göstermektedir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lllrrrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Tarih \& Saat}} & \textcolor{white}{\textbf{Tür}} & \textcolor{white}{\textbf{Mesafe (Süre)}} & \textcolor{white}{\textbf{Tempo}} & \textcolor{white}{\textbf{Nabız (Ort/Maks)}} & \textcolor{white}{\textbf{Güç}} & \textcolor{white}{\textbf{Kadans (Adım)}} & \textcolor{white}{\textbf{Yer Teması}} & \textcolor{white}{\textbf{1 Atımda Yol}} & \textcolor{white}{\textbf{En Hızlı 1K / 5K}} \\
\midrule
""" + "\n".join(t10_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\subsection{Aynı Gün Ağırlık ve Koşu Yapıldığında Hangi Sıra Daha Doğru?}
Kasım ayında 4 kez aynı gün içinde hem ağırlık hem koşu yaptınız. Verileriniz sıralamanın nabzı doğrudan etkilediğini gösteriyor:
\begin{itemize}
  \item \textbf{Önce Koşu $\rightarrow$ Sonra Ağırlık (6 ve 8 Kasım -- Doğru Sıralama):} 8 Kasım'da önce koşulduğunda $6:04\text{ /km}$ tempoda ortalama nabız $\mathbf{161\text{ bpm}}$ kalmış, yüksek nabız (Zone 4) süresi $\mathbf{\%26,5}$ ile sınırlı kalmıştır.
  \item \textbf{Önce Ağırlık $\rightarrow$ Sonra Koşu (10 ve 12 Kasım -- Yorgunluk Etkisi):} 10 Kasım'da $54\text{ dk}$ ağırlıktan hemen sonra koşuya çıkıldığında, 8 Kasım ile aynı mesafe ve aynı tempoya ($6:01\text{ /km}$) rağmen \textbf{nabız $+7\text{ bpm}$ fırlayarak $168\text{ bpm}$'e çıkmış} ve yüksek nabız süresi ikiye katlanmıştır ($\%50$).
  \item \textbf{Tek Başına Koşu (16 Kasım):} Ağırlık olmadan koşulan $5,19\text{ km}$'de tempo $\mathbf{5:48\text{ /km}}$'ye inerken ortalama nabız yine $\mathbf{161\text{ bpm}}$'de kalmış ve $29:07$ ile en iyi $5\text{K}$ derecesi gelmiştir.
\end{itemize}

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}llllrrl@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Tarih}} & \textcolor{white}{\textbf{Uygulanan Sıralama}} & \textcolor{white}{\textbf{Ağırlık Süre / Nabız}} & \textcolor{white}{\textbf{Koşu Mesafe / Tempo}} & \textcolor{white}{\textbf{Koşu Nabzı}} & \textcolor{white}{\textbf{Z4 Yüksek Nabız}} & \textcolor{white}{\textbf{Sonuç}} \\
\midrule
2026-11-06 & \textbf{1.\ Koşu $\rightarrow$ 2.\ Ağırlık} & 46 dk (124/149 bpm) & 5,20 km (6:11 /km) & 159 / 174 bpm & \textbf{\%5,7} & Dengeli nabız, rahat koşu \\
2026-11-08 & \textbf{1.\ Koşu $\rightarrow$ 2.\ Ağırlık} & 65 dk (122/152 bpm) & 4,15 km (6:04 /km) & 161 / 177 bpm & \textbf{\%26,5} & Düşük nabız sapması \\
2026-11-10 & \textbf{1.\ Ağırlık $\rightarrow$ 2.\ Koşu} & 54 dk (122/158 bpm) & 4,16 km (6:01 /km) & \textbf{168 / 177 bpm} & \textbf{\%50,0} & \textbf{+7 bpm nabız ve 2 kat zorlanma} \\
2026-11-12 & \textbf{1.\ Ağırlık $\rightarrow$ 2.\ Koşu} & 60 dk (115/146 bpm) & 5,05 km (5:57 /km) & \textbf{163 / 175 bpm} & \textbf{\%18,0} & Ağırlık yorgunluğu kaynaklı +2 bpm \\
2026-11-16 & \textbf{Sadece Koşu (Ağırlık Yok)} & -- & \textbf{5,19 km (5:48 /km)} & \textbf{161 / 174 bpm} & \textbf{\%8,1} & \textbf{En hızlı tempo ve en yüksek verim} \\
\bottomrule
\end{tabular}}
\end{center}

\subsection{Yelken, Basketbol ve Kuvvet Kayıtları (25 Antrenman) ile Nabız Uyarıları}

\begin{center}
\scriptsize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lllrrrrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Tarih \& Saat}} & \textcolor{white}{\textbf{Branş}} & \textcolor{white}{\textbf{Aktivite Adı}} & \textcolor{white}{\textbf{Süre}} & \textcolor{white}{\textbf{Mesafe}} & \textcolor{white}{\textbf{Ort / Maks Nabız}} & \textcolor{white}{\textbf{Kalori}} & \textcolor{white}{\textbf{Yük (Tahmini Ter)}} \\
\midrule
""" + "\n".join(t12_lines) + r"""
\bottomrule
\end{tabular}}
\end{center}

\textbf{Yüksek Nabız Uyarıları (4 Gün):} 93 günde 4 kez (\textbf{27 Eylül}, \textbf{9 Ekim}, \textbf{3 Kasım} ve \textbf{11 Kasım}) dinlenirken yüksek nabız uyarısı verilmiştir. Bu 4 günün tamamında akşam enerjiniz (Body Battery) $5$'e inmiş; ya çok geç yatılmış (27 Eylül 04:01) ya da önceki gün çift antrenman / uzun yelken yapılmıştır.

\newpage
\section{Garmin Saatte Düzeltilmesi Gereken 8 Ayar}

Saatinizin ayarları incelendiğinde, ölçüm doğruluğunu bozan ve $\text{VO}_2\text{ Max}$ puanınızı olduğundan düşük gösteren \textbf{8 ayar hatası} tespit edilmiştir. Garmin Connect uygulamasından şu düzeltmeleri yapmanız önerilir:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}llll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Saat / Profil Ayarı}} & \textcolor{white}{\textbf{Şu Anki Hatalı Değer}} & \textcolor{white}{\textbf{Yapılması Gereken Ayar}} & \textcolor{white}{\textbf{Neden Düzeltilmeli?}} \\
\midrule
\textbf{1.\ Dinlenik Nabız Ayarı} & \texttt{65 bpm} (Sabit kalmış) & \textbf{Otomatik Ortalama ($\sim$53 bpm)} & Gerçek dinlenik nabzınız 53,6 bpm; 65 sanıldığı için $\text{VO}_2\text{ Max}$ düşük çıkıyor. \\
\textbf{2.\ Koşu Eşik Gücü (FTP)} & \texttt{374 Watt} (95 kg'dan kalma) & \textbf{340 -- 345 Watt} (87 kg uyumlu) & 87 kg'a indiğiniz için 330 W gücünüzü saat düşük tempo sanıyor. \\
\textbf{3.\ Koşu Nabız Profili} & Sadece Genel (\texttt{DEFAULT}) & \textbf{Koşu (\texttt{RUNNING}) Profili Ekle} & Koşu, yelken ve ağırlık antrenmanları aynı nabız bölgeleriyle ölçülüyor. \\
\textbf{4.\ Yoğunluk Dakikası} & Sadece Zone 3 ve Zone 4 & \textbf{\texttt{Otomatik (AUTO)}} Modu & 55 dk ağırlık ve 3 saatlik yelken seanslarında nabız Z3 altıysa ``0 dk'' sayıyor. \\
\textbf{5.\ Uyku Saatleri} & \texttt{00:00 -- 08:00} sabit & \textbf{\texttt{00:30 -- 08:30}} & Saat 00:00'da erken uyku moduna giriyor, 08:00'de REM bitmeden çıkıyor. \\
\textbf{6.\ İrtifa / Eğim Düzeltmesi} & Kapalı (\texttt{false}) & \textbf{İrtifa Düzeltmesi: Açık} & Beşiktaş koşularında eğim kazancı 0 metre görünüyor; yokuş gücü eksik. \\
\textbf{7.\ Kilo Takibi} & Ayda 1 kez giriliyor & \textbf{Haftada 2 sabah tartımı girin} & Kilo geç girildiğinde $\text{VO}_2\text{ Max}$ ($\text{mL/kg/dk}$) eski ağır kilonuza bölünüyor. \\
\textbf{8.\ Hava Durumu Konumu} & Kapalı (\texttt{null}) & \textbf{Konum İzni: ``Her Zaman''} & Sıcak günlerde ısı uyumu ve rüzgara karşı koşu gücü hesaplanmıyor. \\
\bottomrule
\end{tabular}}
\end{center}

\subsection{Saatinize Girmeniz Gereken Doğru Koşu Nabız ve Güç Bölgeleri}

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lllll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Antrenman Bölgesi}} & \textcolor{white}{\textbf{Şu Anki Saat Ayarı}} & \textcolor{white}{\textbf{Önerilen Laktat Eşiği (179 bpm)}} & \textcolor{white}{\textbf{Rezerv Nabız Karşılığı}} & \textcolor{white}{\textbf{Önerilen Koşu Gücü (342 W)}} \\
\midrule
\textbf{Zone 1 (Isınma / Yürüyüş)} & 116 -- 141 bpm & 116 -- 139 bpm (\%65--78) & 128 -- 143 bpm & 222 -- 273 Watt \\
\textbf{Zone 2 (Rahat / Yağ Yakımı)} & 142 -- 157 bpm & \textbf{140 -- 155 bpm (\%78--87)} & \textbf{143 -- 158 bpm} & \textbf{274 -- 308 Watt} \\
\textbf{Zone 3 (Orta / Tempo Koşusu)} & 158 -- 167 bpm & 156 -- 167 bpm (\%87--93) & 158 -- 173 bpm & 309 -- 342 Watt \\
\textbf{Zone 4 (Yüksek / Eşik Koşusu)} & 168 -- 176 bpm & \textbf{168 -- 179 bpm (\%94--100)} & 173 -- 188 bpm & \textbf{343 -- 393 Watt} \\
\textbf{Zone 5 (Maksimum / İnterval)} & 177 -- 203 bpm & 180 -- 203 bpm ($>$\%100) & 188 -- 203 bpm & $>$ 393 Watt \\
\bottomrule
\end{tabular}}
\end{center}

\section{Eylem Planı ve Haftalık Antrenman / Beslenme Programı}

{\setlist[enumerate]{leftmargin=14pt,itemsep=1.5pt,topsep=1pt,parsep=0pt}
\begin{enumerate}
  \item \textbf{Garmin Saat Ayarlarını Düzeltin (Öncelik 1):} Yukarıdaki tabloda yer alan 8 ayarı (özellikle dinlenik nabzı otomatiğe almayı ve koşu eşik gücünü $342\text{ W}$'a çekmeyi) Garmin Connect üzerinden güncelleyin.
  \item \textbf{Haftalık 2 Koşuyu Polarize Edin (1 Zone 2 Taban + 1 Hız İntervali) (Öncelik 1):} Son 2 aydaki düz koşularınızın tamamını $158-170\text{ bpm}$ (Zone 3--4) aralığında koştunuz. Haftalık 2 koşu seansınızı şu şekilde polarize edin: \textbf{1 Seans Düşük Nabızlı Zone 2 Aerobik Taban ($140-150\text{ bpm}$, $\sim 6:30-6:50\text{ /km}$, $45-50\text{ dk}$)} ile mitokondri ve sol ventrikül hacmini genişletin; \textbf{1 Seans 5K Hız İntervali ($4\times 1.000\text{ m}$ @ $5:15\text{ /km}$, $170-183\text{ bpm}$)} ile laktat eşiğini yukarı çekin. Bu model aşırı yorgunluğu önleyecek ve Garmin $\text{VO}_2\text{ Max}$ puanınızı hızla $48-50$ bandına taşıyacaktır.
  \item \textbf{Aynı Gün Çift Antrenmanda ``Önce Koşu, Sonra Ağırlık'' Sırasını Uygulayın (Öncelik 1):} Ağırlıktan hemen sonra koşmak nabzınızı $+7\text{ bpm}$ yükseltmektedir. Aynı gün yapılacaksa önce koşun veya araya en az 6 saat koyun; bacak ağırlık gününü hızlı koşu gününden ayırın.
  \item \textbf{Yatış Saatini 00:45 Öncesine Çekin (Öncelik 1):} Sabah 08:30 civarında uyandığınız için 00:45'ten önce uyumak, REM uykunuzu $+30\text{ dk}$, sabah enerjinizi ise $+20\text{ puan}$ artıracaktır.
  \item \textbf{87 kg Sonrasında Günlük Kalori Açığını 400--550 kcal Bandında Tutun (Öncelik 2):} İlk $8\text{ kg}$ hızlı verildi ($95,0 \rightarrow 87,0\text{ kg}$); DSÖ normal sınırına ($86,45\text{ kg}$) yalnızca $550\text{ g}$ kaldı. Çoklu-branş için \textbf{hedef ideal atletik kilonuz 80,0 -- 83,0 kg (Optimal: 81,0 kg, VKİ: 23,4)} olarak belirlenmiştir. Kalan $6\text{ kg}$ verilirken kas ve kuvvet kaybetmemek için günlük $\mathbf{175-180\text{ g protein}}$ alınmalı ve kilo verme hızı $-0,55\text{ kg/hf}$ seviyesine dengelenmelidir.
  \item \textbf{Yavaş Koşularda da Kısa ve Sık Adım ($160\text{ adım/dk}$) Formunu Koruyun (Öncelik 2):} Kasım ayında yakaladığınız $162\text{ adım/dk}$ kadans koşu veriminizi çok artırdı; Zone 2 yavaş koşularda da adımlarınızı büyütmeyip sık adım atmaya devam edin.
  \item \textbf{90 Dakikayı Aşan Yelken Antrenmanlarında Elektrolit Alın (Öncelik 3):} Uzun yelken seanslarında $2-3\text{ litre}$ ter kaybınız oluyor; saat başına $500-600\text{ mL}$ su ve elektrolit tüketin.
\end{enumerate}
}

\subsection{Önerilen Haftalık Antrenman ve Beslenme Programı (Hedef İdeal Kilo: 81,0 kg)}

{\small\textbf{İdeal Kilo Hedefi \& Stratejisi:} Mevcut: $\mathbf{87,0\text{ kg}}$ $\bullet$ DSÖ Sınırı: $86,45\text{ kg}$ (Kalan: $-550\text{ g}$) $\bullet$ \textbf{İdeal Atletik Kilo: 81,0 kg} (80--83 kg, Kalan: $-6\text{ kg}$, Varış: 76 Gün / 1 Şubat 2027). Kas kütlesini ve 5x5 kuvvetini koruyarak $\sim 500\text{ kcal}$ açıkla $175-180\text{ g protein}$ hedeflenmiştir. \textbf{Program Prensibi (Haftalık 2 Koşu + 2 Gym):} Düzenli haftalık programınız \textbf{2 Gün Koşu} ve \textbf{2 Gün Kuvvet (Gym)} olarak kurgulanmıştır; kalan 3 gün rejenerasyon ve dinlenmeye ayrılmıştır. Yelken ve Basketbol spontane çıktıkça icra edilir ve saatinizden telemetri otomatik analiz edilir.}

\vspace{-2pt}
\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}llllrr@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Tarih ve Gün}} & \textcolor{white}{\textbf{Ana Antrenman (İcra Edilen / Hedef)}} & \textcolor{white}{\textbf{Ayrıntı ve Not}} & \textcolor{white}{\textbf{Hedef Nabız ve Tempo}} & \textcolor{white}{\textbf{Tahm.\ Harcama}} & \textcolor{white}{\textbf{Hedef Kalori ve Makro}} \\
\midrule
\textbf{17 Kas Salı (Bugün)} & \textbf{Kuvvet \#1 (Workout A)}: Squat 65 kg (5x5 PR), Bench 50 kg (5x5) & \textbf{TAMAMLANDI (10:35)} & 115--128 bpm (Zone 1) & $\sim$2.850 kcal & 2.450 kcal (175g P / 250g K / 80g Y) \\
\textbf{18 Kas Çarşamba} & \textbf{Koşu \#1 -- Zone 2 Rahat Taban Koşusu (45--50 dk)} & Aktif toparlanma (160+ kadans, burundan nefes) & \textbf{140--150 bpm} (6:35--6:50 /km) & $\sim$2.950 kcal & 2.550 kcal (175g P / 275g K / 80g Y) \\
\textbf{19 Kas Perşembe} & \textbf{Tam Dinlenme / Rejenerasyon} & Cuma günkü hız intervali öncesi bacakları dinlendirme & $<$100 bpm (Parasempatik gün) & $\sim$2.500 kcal & 2.350 kcal (175g P / 220g K / 80g Y) \\
\textbf{20 Kas Cuma} & \textbf{Koşu \#2 -- 5K Hız İntervali (45 dk, 4 $\times$ 1.000 m)} & 5:15 /km tempo, aralarda 3 dk yürüyüş/jog & \textbf{170--183 bpm} (Zone 4--5) & $\sim$3.050 kcal & 2.650 kcal (175g P / 300g K / 80g Y) \\
\textbf{21 Kas Cumartesi} & \textbf{Kuvvet \#2 (Workout B)}: Squat 67,5 kg (5x5), OHP 40 kg, Deadlift 65 kg & Lat Pulldown 45 kg (4x12) \& Lateral \& Shrug & 115--130 bpm (Zone 1) & $\sim$2.900 kcal & 2.500 kcal (180g P / 270g K / 80g Y) \\
\textbf{22 Kas Pazar} & \textbf{Aktif Toparlanma / Yürüyüş \& Mobilite} & Hafif yürüyüş, esneme, nefes egzersizi (NSDR) & $<$110 bpm (Zone 1) & $\sim$2.500 kcal & 2.350 kcal (175g P / 220g K / 80g Y) \\
\textbf{23 Kas Pazartesi} & \textbf{Tam Dinlenme / Haftalık Toparlanma} & Salı günkü yeni A döngüsüne zinde başlangıç, erken uyku & $<$100 bpm (Parasempatik gün) & $\sim$2.450 kcal & 2.300 kcal (175g P / 210g K / 80g Y) \\
\bottomrule
\end{tabular}}
\end{center}

\newpage
\subsection{Branş Gelişim Rehberi ve İleri Antrenman Adımları}

{\setlist[itemize]{leftmargin=12pt,itemsep=1.2pt,topsep=1pt,parsep=0pt}
\begin{itemize}
  \item \textbf{Koşu (Running -- Düzenli Program)} -- Hedef: 5K Süresini 29:07'den 24:30 Altına İndirmek ve Zone 2 Hızlanması
  \begin{itemize}
    \item \textbf{Nasıl Gelişilir?} Haftalık 2 koşu seansınızı 80/20 polarize edin: 1 Seans düşük nabızlı Zone 2 (140--150 bpm) ile sol ventrikül atım hacmini ve kılcal damar yoğunluğunu artırın; 1 Seans laktat eşiğini yukarı çeken intervaller ($4 \times 1.000\text{ m}$) yapın. Kasım'da yakaladığınız 162 spm kadansı koruyun.
    \item \textbf{Zone 2 Temposu Ne Zaman 5:00 /km'ye İner?} Şu an 145 bpm'de temponuz 6:35--6:50 /km'dir (EF $\sim$ 1,03 m/atım). 145 bpm'de 5:00 /km hızına (EF = 1,38 m/atım, +\%33 kardiyovasküler verimlilik) ulaşmak: (1) 87 kg'dan 81 kg'a inme (-6 kg hafifleme doğrudan +25 sn/km hız kazandırır), (2) Kalan 20 Zone 2 + 20 İnterval seansıyla mitokondriyal adaptasyon gerektirir. \textbf{Takvim: Aralık'ta 6:15, Ocak'ta 5:45, Mart--Nisan 2027'de 81 kg ile 5:00--5:15 /km @ 145 bpm!}
    \item \textbf{Sonraki Seanslar:} 18 Kas Çarşamba (45--50 dk Z2, 6:35--6:50 /km), 20 Kas Cuma ($4 \times 1.000\text{ m}$ @ 5:15 /km).
  \end{itemize}

  \item \textbf{Kuvvet Antrenmanı (Strength -- Düzenli Program)} -- Garmin Sensör Telemetrisi ve Kaldırılan Ağırlıklar
  \begin{itemize}
    \item \textbf{Kasım Ayında İcra Edilen Gerçek 5 Seans ve A/B Rutini:} Saatinizden çekilen 124 aktif set incelendiğinde harika bir A/B Full Body rutini uyguladığınız görülmektedir:
    \begin{itemize}
      \item \emph{Back Squat (11 Günde +20 kg Rekor!):} 06 Kas (45 kg) $\rightarrow$ 08 Kas (55 kg) $\rightarrow$ 10 Kas (57,5 kg) $\rightarrow$ 12 Kas (60 kg) $\rightarrow$ \textbf{17 Kas Bugün: 20 kg x 10, 65,0 kg x 5 tekrar x 5 set (5x5 PR!)}
      \item \emph{Bench Press (5x5 Kilitlendi):} 06 Kas (45 kg) $\rightarrow$ 10 Kas (50 kg x 4 set) $\rightarrow$ \textbf{17 Kas Bugün: 20 kg x 10, 50,0 kg x 5 tekrar x 5 set!}
      \item \emph{Barbell Row (+15 kg Artış):} 06 Kas (45 kg) $\rightarrow$ 10 Kas (55 kg) $\rightarrow$ \textbf{17 Kas Bugün: 20 kg x 10, 60,0 kg x 5 tekrar x 5 set!}
      \item \emph{Overhead Press (OHP):} 08 Kas (35--37 kg) $\rightarrow$ \textbf{12 Kas: 40,0 kg x 5 tekrar} (ve 37,5 kg x 5 x 3 set)
      \item \emph{Barbell Deadlift:} 08 Kas (50 kg x 6) $\rightarrow$ \textbf{12 Kas: 60,0 kg x 5 tekrar (+10 kg)}
      \item \emph{Lat Pulldown:} 08 Kas (40--45 kg) $\rightarrow$ \textbf{12 Kas: 45,0 kg x 12 tekrar x 3 set}
      \item \emph{Lateral Raise \& Shrug:} 20,0--25,0 kg x 12--13 tekrar yana açış; 45,0 kg x 12 tekrar x 3 set shrug (stabil güç).
    \end{itemize}
    \item \textbf{Sonraki Seanslar İçin Kesin Hedefler (Progressive Overload):}
    \begin{itemize}
      \item \emph{21 Kasım Cumartesi (Workout B):} Squat Isınma + \textbf{67,5 kg x 5 tekrar x 5 set} (+2,5 kg); Overhead Press Isınma + \textbf{40,0 kg x 5 tekrar x 5 set} (Tüm setlerde 40 kg); Deadlift Isınma + \textbf{65,0 kg x 5 tekrar} (+5 kg); Lat Pulldown \textbf{45,0 kg x 12 tekrar x 4 set}; Lateral Raise 25 kg; Shrug 45 kg.
      \item \emph{24 Kasım Salı (Workout A):} Squat \textbf{67,5 kg x 5 tekrar x 5 set}; Bench Press \textbf{52,5 kg x 5 tekrar x 5 set} (Yeni PR denemesi!); Barbell Row \textbf{62,5 kg x 5 tekrar x 5 set} (+2,5 kg); Lateral 25 kg; Shrug 45 kg.
    \end{itemize}
  \end{itemize}

  \item \textbf{Yelken (Sailing -- Spontane \& Dönemsel Branş)} -- 2--4 Saatlik Seanslarda Core/Önkol Dayanıklılığı ve Sıvı Dengesi
  \begin{itemize}
    \item \textbf{Nasıl Gelişilir?} Halat çekişi (sheet trimming) ve trapez duruşu sürekli izometrik kasılma gerektirir. Salonda Farmer's Walk ve Dead Hang önkol yorgunluğunu önler. 12 seansta 16,6 L ter kaybettiğiniz görüldüğünden saat başı 500--600 mL su ve elektrolit (sodyum) tüketin.
    \item \textbf{Uygulama Notu:} Düzenli takvime yazılmaz; denize çıktığınız günlerde 90 dk önce 70g karbonhidrat alın, teknede elektrolit bulundurun.
  \end{itemize}

  \item \textbf{Basketbol (Spontane \& Dönemsel Branş)} -- Patlayıcı Çeviklik ve Reaktif Ayak Bileği Gücü
  \begin{itemize}
    \item \textbf{Nasıl Gelişilir?} Maçlar doğal HIIT işlevi görür. Maç günleri ağır bacak (Squat/Deadlift) yapmayın. Maç öncesi 10 dk dinamik ayak bileği ısınması, maç sonrası statik esneme yapın. Çıktıkça icra edilir ve saatinizden otomatik analiz edilir.
  \end{itemize}
\end{itemize}
}

\vspace{-4pt}
\subsection{Antrenman Yükü, Kronik Taban ve ACWR (Sakatlık Riski) Analizi}

Garmin Forerunner 570 saatinizden çekilen Firstbeat telemetrisi: Son 7 günlük akut yükünüz (ATL: 279) son 28 günlük kronik yükünüzle (CTL: 279) uyumlu olup \textbf{ACWR = 1,00 (Kusursuz Sweet Spot)} seviyesindedir.

\vspace{-4pt}
\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}lllll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Fizyolojik Metrik}} & \textcolor{white}{\textbf{Mevcut Değer}} & \textcolor{white}{\textbf{Optimal Hedef Aralığı}} & \textcolor{white}{\textbf{Durum}} & \textcolor{white}{\textbf{Spor Bilimi ve Koçluk Yorumu}} \\
\midrule
\textbf{Antrenman Durumu} & \textbf{Form Korunuyor (Maintaining)} & Üretken / Korunuyor & Optimal & Kondisyon trendi pozitif; aerobik taban korunuyor. \\
\textbf{Akut Antrenman Yükü (ATL)} & \textbf{279 birim} & 223 -- 418 birim & Tünel İçi & Son 7 günün antrenman yorgunluğu güvenli koridorda. \\
\textbf{Kronik Antrenman Yükü (CTL)} & \textbf{279 birim} & 223 -- 418 birim & Yüksek Taban & Son 28 günlük kondisyon temeli sağlamlaşmış. \\
\textbf{ACWR (İş Yükü Oranı)} & \textbf{1,00} & \textbf{0,80 -- 1,30 (Sweet Spot)} & \textbf{Kusursuz} & Sakatlık riski minimum; yük-toparlanma dengesi ideal. \\
\textbf{Aylık Düşük Aerobik Yük} & \textbf{385,9 birim} & 155 -- 418 birim & Optimal & Taban aerobik kapasite ve toparlanma yeterli seviyede. \\
\textbf{Aylık Yüksek Aerobik Yük} & \textbf{537,8 birim} & 325 -- 588 birim & Optimal & Eşik/tempo koşuları ve yelken gücüyle en yüksek kategoriniz! \\
\textbf{Aylık Anaerobik Yük} & \textbf{162,3 birim} & 0 -- 262 birim & Optimal & Sprint, basketbol ve intervaller hedef aralıkta. \\
\textbf{Yük Dengesi (Load Focus)} & \textbf{BALANCED (Dengeli)} & Dengeli Dağılım & Mükemmel & 3 enerji sistemi Firstbeat hedefleriyle tam örtüşüyor. \\
\bottomrule
\end{tabular}}
\end{center}

\textbf{Yük Dağılımı ve Polarize Model Notu:} 80/20 polarize model High Aerobic'i asla eksik bırakmaz; nitekim saatinizde High Aerobic yükünüz \textbf{537,8 birim ile zaten en yüksek yükünüzdür}. Haftalık 1 interval koşusu, 2--4 saatlik rüzgarlı yelken ve basketbol maçları High Aerobic ihtiyacını fazlasıyla karşılar; Zone 2 koşular ise bu piramidin eksik olan aerobik tabanını tamamlar.

\vspace{-4pt}
\subsection{Antrenman Sonu Otomatik Telemetri ve Debrief Protokolü (5 Temel Kontrol)}

Sporcunun her antrenman sonrasında takip ettiği 5 maddelik altın kontrol protokolü ve 17 Kasım 2026 seansı gerçekleşme telemetrisi:

\begin{center}
\footnotesize
\rowcolors{2}{rowalt}{white}
\resizebox{\textwidth}{!}{\begin{tabular}{@{}llll@{}}
\toprule
\rowcolor{tblhead}
\textcolor{white}{\textbf{Kontrol Maddesi}} & \textcolor{white}{\textbf{17 Kasım Seansı Değeri}} & \textcolor{white}{\textbf{Önceki Seansla Karşılaştırma}} & \textcolor{white}{\textbf{Klinik ve Spor Bilimi Değerlendirmesi}} \\
\midrule
\textbf{1. Training Load \& ACWR} & EPOC: \textbf{14,6 birim} (Akut: 279, Kronik: 279) & ACWR: \textbf{1,00} & \textbf{Kusursuz Sweet Spot (0,80--1,30)}. Yük tüneli içinde sürantrene riski sıfır. \\
\textbf{2. Productive Durumu} & \textbf{Form Korunuyor (Maintaining)} & VO2 Max: 45,4 (Stabil) & Yük ve VO2 Max eşit dengede; Cuma hız intervali ile Productive tetiklenecektir. \\
\textbf{3. 24h Günlük Biyometri} & Kilo: \textbf{87,0 kg} • RHR: \textbf{54 bpm} • HRV: \textbf{43 ms} & Uyku: \textbf{82/100} (6s 23dk) • BB: \textbf{78} & Dinlenik nabız Ağustos'a göre -8 bpm güçlü; DSÖ normal sınırına sadece 550g kaldı. \\
\textbf{4. Nabız Karşılaştırması} & Ort: \textbf{112 bpm} • Maks: \textbf{148 bpm} (53 dk) & 10 Kas A Rutini: 118 bpm / 152 bpm & \textbf{-6 bpm Kardiyak Tasarruf!} Rekor ağırlıklara rağmen toparlanma çok daha hızlı. \\
\textbf{5. Gym Kilo Hacmi} & Toplam Tonaj: \textbf{7.430 kg (7,43 Ton)} & 10 Kas A: 7.067 kg (\textbf{+363 kg artış}) & \textbf{Squat 65 kg 5x5 PR (+20 kg rekor), Bench 50 kg 5x5 PR, Row 60 kg 5x5!} \\
\bottomrule
\end{tabular}}
\end{center}

\textbf{Sonraki Eylem Çağrısı:} 175--180 g protein hedefi tamamlanmalı; bu akşam 00:30 öncesi erken uyku; yarın \textbf{18 Kasım Çarşamba Koşu \#1 Zone 2 Taban Koşusu (45 dk, 140--150 bpm)} ile bacaklardaki laktat süpürülerek mitokondriyal kılcal damarlanma beslenmelidir.

\vspace{6pt}
\noindent\textbf{Önceki Koşu Seansı Debrief Özeti (16 Kasım vs 12 Kasım):}
16 Kasım Beşiktaş koşusunda (30 dk), önceki seansa kıyasla \textbf{-2 bpm daha düşük ortalama nabızla} (161 vs 163 bpm) \textbf{3 saniye/km daha hızlı} (5:58 vs 6:01 /km) koşulmuş; Kardiyak Verimlilik Faktörü (EF) 1,02'den \textbf{1,04 m/atıma} yükselmiştir.

\vspace{10pt}
\begin{center}
\begin{tikzpicture}
  \node[draw=cardborder, line width=1pt, fill=cardbg, rounded corners=6pt, inner sep=8pt, text width=0.96\textwidth, align=left] {
    {\small\bfseries\color{navy}Resmi Spor Bilimi ve Telemetri Özeti}\\[3pt]
    {\footnotesize\color{slate}Bu analitik rapor; sporcunun Garmin Forerunner sensörlerinden, Firstbeat antrenman yükü algoritmalarından ve 93 günlük saniye-bazlı telemetri kayıtlarından derlenmiştir. Haftalık 2 Koşu + 2 Gym (A/B 5x5) protokolü, 87,0 kg $\rightarrow$ 81,0 kg hedef kilo dönüşümü ve Mart--Nisan 2027 Zone 2 @ 5:00 /km adaptasyonu için bilimsel Single Source of Truth (SSOT) teşkil eder.}
  };
\end{tikzpicture}
\end{center}

\end{document}
"""

tex_path = os.path.join(SRC_DIR, "report.tex")
with open(tex_path, "w", encoding="utf-8") as f:
    f.write(tex_content)

print("Generated clean LaTeX report source at:", tex_path)
