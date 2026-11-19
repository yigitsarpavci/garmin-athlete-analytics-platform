#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garmin Veri ve Performans Hesaplama Motoru (Ana Orkestratör).
Ham Garmin Connect telemetrisini (günlük özetler, uyku, HRV, tartı/kilo, egzersiz setleri
ve tüm çoklu branş aktiviteleri) yükler ve modüler Mixin sınıflarıyla analitiğe sunar.
"""

import contextlib
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    from athlete_profile import load_athlete_profile
    from engine.helpers import fmt_pace_sec, DATA_DIR, IS_DEMO_MODE, format_sport_tr, classify_sport_bucket
    from engine.fit_stream_parser import load_and_parse_high_res_streams
    from engine.telemetry_mixin import TelemetryMixin
    from engine.sleep_analytics_mixin import SleepAnalyticsMixin
    from engine.training_protocols_mixin import TrainingProtocolsMixin
    from engine.simulation_health_mixin import SimulationHealthMixin
except ImportError:
    from app.athlete_profile import load_athlete_profile
    from app.engine.helpers import fmt_pace_sec, DATA_DIR, IS_DEMO_MODE, format_sport_tr, classify_sport_bucket
    from app.engine.fit_stream_parser import load_and_parse_high_res_streams
    from app.engine.telemetry_mixin import TelemetryMixin
    from app.engine.sleep_analytics_mixin import SleepAnalyticsMixin
    from app.engine.training_protocols_mixin import TrainingProtocolsMixin
    from app.engine.simulation_health_mixin import SimulationHealthMixin


logger = logging.getLogger(__name__)


def _read_json(path: str, default: Any) -> Any:
    """JSON dosyasını güvenle okur (dosya tutamacı kapatılır); yoksa veya bozuksa varsayılanı döner."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


class GarminAthleteEngine(TelemetryMixin, SleepAnalyticsMixin, TrainingProtocolsMixin, SimulationHealthMixin):
    """Garmin Çoklu Spor Biyometrik ve Telemetri Hesaplama Motoru."""

    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self.data_dir = data_dir
        self._apply_profile()
        # Arka plan senkronizasyonu (load_data) ile istek işleme arasındaki yarışları önler.
        self.lock = threading.RLock()
        # None: önbellek kapalı; dict: aktif istek kapsamı (bkz. helpers.request_cached).
        self._req_cache: Optional[Dict[Any, Any]] = None
        self.load_data()

    def _apply_profile(self) -> None:
        """Sporcu profilini (yaş, boy, hedef kilo...) data_dir'den yükler; kodda kişisel değer yoktur."""
        self.profile = load_athlete_profile(self.data_dir)
        self.height_cm = float(self.profile["height_cm"])
        self.height_m2 = (self.height_cm / 100.0) ** 2
        self.age = int(self.profile["age"])

    @contextlib.contextmanager
    def request_scope(self):
        """Tek bir API isteği boyunca motoru kilitler ve ağır hesaplamaları bir kez yapar."""
        with self.lock:
            outer = self._req_cache
            if outer is None:
                self._req_cache = {}
            try:
                yield self
            finally:
                if outer is None:
                    self._req_cache = None

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

    def _summary_weights(self) -> List[Dict[str, Any]]:
        """Günlük özetlerdeki bodyWeightInGrams kayıtlarını tarih sıralı döner."""
        out: List[Dict[str, Any]] = []
        for dt in (self.dates if hasattr(self, "dates") else []):
            s = self.summaries.get(dt, {}) if isinstance(self.summaries.get(dt), dict) else {}
            w_g = s.get("bodyWeightInGrams") or s.get("weight")
            if w_g and float(w_g) > 0:
                out.append({"date": dt, "weight_kg": round(float(w_g) / 1000.0 if float(w_g) > 300 else float(w_g), 2)})
        return out

    def _fallback_weight(self) -> float:
        """Hiçbir tartı verisi yoksa: Garmin profil kilosu, o da yoksa boya göre VKİ 22 ağırlığı (kişisel sabit yok)."""
        w = self.profile.get("weight_kg")
        return float(w) if w else round(22.0 * self.height_m2, 1)

    def get_start_weight(self) -> float:
        """Başlangıç kilosu: tartı geçmişinin ilk kaydı, yoksa günlük özetlerin ilki, yoksa güncel kilo."""
        hist = self.get_weight_history()
        if hist:
            return hist[0]["weight_kg"]
        summ = self._summary_weights()
        if summ:
            return summ[0]["weight_kg"]
        return self.get_current_weight()

    def get_target_weight(self) -> float:
        """Hedef kilo: profildeki `target_weight_kg`; yoksa boya göre VKİ 22,5 ağırlığı."""
        t = self.profile.get("target_weight_kg")
        return round(float(t), 1) if t else round(22.5 * self.height_m2, 1)

    def get_current_weight(self, date_str: Optional[str] = None) -> float:
        """Güncel (veya `date_str` tarihindeki) kilo: tartı geçmişi, günlük özetler, profil yedeği sırasıyla."""
        hist = self.get_weight_history()
        if hist:
            if date_str:
                eligible = [e for e in hist if e["date"] <= date_str]
                if eligible:
                    return eligible[-1]["weight_kg"]
            return hist[-1]["weight_kg"]

        summ = self._summary_weights()
        if date_str:
            summ = [e for e in summ if e["date"] <= date_str] or summ[:1]
        if summ:
            return summ[-1]["weight_kg"] if date_str else summ[-1]["weight_kg"]
        return self._fallback_weight()

    ZONE_TOKENS = ("[[Z2_HR]]", "[[Z2_HR_CAP]]", "[[Z2_PACE]]", "[[INT_HR]]", "[[INT_PACE]]", "[[Z45_HR]]", "[[WARM_HR]]", "[[Z2_HR_MID]]")

    @staticmethod
    def _fmt_pace(sec: float) -> str:
        sec = int(round(sec))
        return f"{sec // 60}:{sec % 60:02d}"

    def get_training_zones(self) -> Dict[str, str]:
        """
        Antrenman reçetelerindeki nabız ve tempo değerlerini sporcunun KENDİ verisinden türetir:
        nabız bantları maksimum nabzın yüzdesidir (Z2 %69-74, interval %85-89, Z4-5 %84-90, ısınma %66.5-71.4);
        Zone 2 temposu, Z2 nabzındaki kardiyak verimlilikten (EF = m/dk / bpm); interval temposu güncel 5K temposunun %90'ıdır.
        Veri yoksa tempo '--' döner.
        """
        cached = getattr(self, "_zones_cache", None)
        if cached is not None and cached[0] is self.df:
            return cached[1]
        mx = self.get_physiology()["max_hr"]
        z2_lo, z2_hi = int(round(0.69 * mx)), int(round(0.74 * mx))
        z2_mid = int(round(0.714 * mx))
        pace_z2 = "--"
        pace_int = "--"
        self._z2_center_sec = None
        try:
            runs = self.adf[self.adf["sport"].str.contains("running", case=False, na=False)] if not self.adf.empty else self.adf
            ef_all = runs[(runs["ef_spd"].notna()) & (runs["dist_km"] >= 2.0)] if not runs.empty else runs
            if not ef_all.empty:
                band = ef_all[(ef_all["avg_hr"] >= 0.62 * mx) & (ef_all["avg_hr"] <= 0.76 * mx)]
                ef = float((band if not band.empty else ef_all)["ef_spd"].median())
                center = 60000.0 / (ef * z2_mid)
                self._z2_center_sec = center
                pace_z2 = f"{self._fmt_pace(center - 8)} - {self._fmt_pace(center + 8)} /km"
            best5k = self._estimate_current_5k_sec() if hasattr(self, "_estimate_current_5k_sec") else None
            if best5k and not runs.empty:
                pace_int = f"{self._fmt_pace(0.9 * best5k / 5.0)} /km"
        except (KeyError, ValueError, ZeroDivisionError):
            logger.debug("get_training_zones: tempo türetilemedi", exc_info=True)
        zones = {
            "[[Z2_HR]]": f"{z2_lo} - {z2_hi} bpm",
            "[[Z2_HR_CAP]]": str(z2_hi),
            "[[Z2_HR_MID]]": str(z2_mid),
            "[[Z2_PACE]]": pace_z2,
            "[[INT_HR]]": f"{int(round(0.847 * mx))} - {int(round(0.887 * mx))} bpm",
            "[[INT_PACE]]": pace_int,
            "[[Z45_HR]]": f"{int(round(0.837 * mx))} - {int(round(0.90 * mx))} bpm",
            "[[WARM_HR]]": f"{int(round(0.665 * mx))}-{int(round(0.714 * mx))} bpm",
        }
        self._zones_cache = (self.df, zones)
        return zones

    def get_z2_center_pace_sec(self) -> Optional[float]:
        """Zone 2 nabzındaki tipik tempo (sn/km); veri yoksa None."""
        self.get_training_zones()
        return getattr(self, "_z2_center_sec", None)

    def fill_zone_tokens(self, obj: Any) -> Any:
        """Şablon metinlerindeki [[Z2_HR]] gibi belirteçleri sporcunun kendi bölgeleriyle doldurur (iç içe yapılarda)."""
        zones = self.get_training_zones()

        def _fill(o: Any) -> Any:
            if isinstance(o, str):
                if "[[" not in o:
                    return o
                for token, value in zones.items():
                    o = o.replace(token, value)
                return o
            if isinstance(o, list):
                return [_fill(x) for x in o]
            if isinstance(o, tuple):
                return tuple(_fill(x) for x in o)
            if isinstance(o, dict):
                return {k: _fill(v) for k, v in o.items()}
            return o

        return _fill(obj)

    def get_personal_baseline(self, column: str, days: int = 28, min_points: int = 10) -> Dict[str, Any]:
        """
        Sporcunun KENDİ son `days` günlük taban çizgisi (ortalama, std, çeyreklikler). Son gün hariç tutulur ki bugünkü
        değer kendi tabanını çarpıtmasın. `min_points` altında güvenilir değildir (reliable=False) ve çağıran sabit bantlara düşer.
        """
        if self.df.empty or column not in self.df.columns:
            return {"mean": None, "std": None, "p25": None, "p75": None, "n": 0, "reliable": False}
        ser = pd.to_numeric(self.df[column], errors="coerce").dropna().iloc[:-1].tail(days)
        n = int(len(ser))
        if n == 0:
            return {"mean": None, "std": None, "p25": None, "p75": None, "n": 0, "reliable": False}
        return {
            "mean": float(ser.mean()), "std": float(ser.std(ddof=0)),
            "p25": float(ser.quantile(0.25)), "p75": float(ser.quantile(0.75)),
            "n": n, "reliable": n >= min_points,
        }

    def get_hrv_baseline(self) -> Optional[Dict[str, Any]]:
        """
        Gece HRV "dengeli" aralığı. Öncelik Garmin'in kendi hesabı (hrv-service baseline.balancedLow/balancedUpper, en yeni gün);
        yoksa sporcunun kendi 28 günlük çeyreklikleri (p25–p75). Hiçbiri yoksa None (sabit değer döndürülmez).
        """
        raw = getattr(self, "hrv_5min_raw", None) or {}
        for day in sorted(raw, reverse=True):
            base = ((raw.get(day) or {}).get("hrvSummary") or {}).get("baseline") or {}
            lo, hi = base.get("balancedLow"), base.get("balancedUpper")
            if lo is not None and hi is not None and float(hi) > float(lo) > 0:
                return {"low": float(lo), "high": float(hi), "source": "garmin"}
        pb = self.get_personal_baseline("hrv_night")
        if pb.get("reliable") and pb["p75"] > pb["p25"]:
            return {"low": round(pb["p25"], 1), "high": round(pb["p75"], 1), "source": "personal"}
        return None

    _NUTRITION_DAY_FACTOR = {"rest": 0.88, "gym": 0.98, "run": 1.02, "tempo": 1.04, "interval": 1.05}

    def get_day_nutrition(self, kind: str) -> Optional[Dict[str, int]]:
        """
        Gün tipine göre kişisel enerji/makro hedefi. Harcama tabanı sporcunun KENDİ son 28 günlük ortalama toplam harcaması (Garmin),
        açık sadece hedef kilonun üstündeyse (~500 kcal); protein 2,0 g/kg, yağ 0,9 g/kg, kalan karbonhidrat. Veri yoksa None.
        """
        if self.df.empty or "total_kcal" not in self.df.columns:
            return None
        ser = pd.to_numeric(self.df["total_kcal"], errors="coerce")
        ser = ser[ser > 0].iloc[:-1].tail(28)
        if ser.empty:
            return None
        weight = float(self.get_current_weight() or 0)
        if weight <= 0:
            return None
        spend = float(ser.mean()) * self._NUTRITION_DAY_FACTOR.get(kind, 1.0)
        deficit = 500.0 if weight > float(self.get_target_weight()) + 0.5 else 0.0
        bmr = pd.to_numeric(self.df.get("bmr_kcal"), errors="coerce").dropna()
        floor = float(bmr.mean()) if not bmr.empty else 0.0
        intake = max(spend - deficit, floor)
        protein = round(weight * 2.0)
        fat = round(weight * 0.9)
        carbs = max(0, round((intake - 4 * protein - 9 * fat) / 4 / 5) * 5)
        return {"spend": int(round(spend / 50) * 50), "intake": int(round(intake / 50) * 50),
                "protein": int(protein), "carbs": int(carbs), "fat": int(fat)}

    def nutrition_texts(self, kind: str) -> Dict[str, str]:
        """Takvim satırı için kişisel 'calories' / 'macro' metinleri; veri yoksa '--'."""
        n = self.get_day_nutrition(kind)
        if not n:
            return {"calories": "--", "macro": "--", "line": "--"}
        f = lambda v: f"{v:,}".replace(",", ".")
        return {
            "calories": f"~{f(n['spend'])} kcal",
            "macro": f"{f(n['intake'])} kcal ({n['protein']}g P / {n['carbs']}g K / {n['fat']}g Y)",
            "line": f"{f(n['intake'])} kcal alım | {n['protein']}g Protein | {n['carbs']}g Karbonhidrat | {n['fat']}g Yağ",
            "spend_line": f"~{f(n['spend'])} kcal toplam harcama",
        }

    def get_physiology(self) -> Dict[str, Any]:
        """
        Sporcunun fizyolojik eşiklerini Garmin verisinden türetir (kişisel sabit yok):
        max nabız (profilde verilmişse o; yoksa gözlenen en yüksek, o da yoksa 220-yaş), laktat eşiği nabzı (Garmin/profil, yoksa %88 maks),
        dinlenik nabız (ortalama) ve tahmini koşu eşik gücü (en iyi 3 uzun koşunun NP ortalamasının %97'si).
        """
        peaks: List[float] = []
        if not self.df.empty and "max_hr" in self.df.columns:
            peaks += [float(v) for v in pd.to_numeric(self.df["max_hr"], errors="coerce").dropna() if v > 0]
        peaks += [float(a.get("maxHR")) for a in self.activities_all if a.get("maxHR")]
        max_hr = int(self.profile.get("max_hr") or (round(max(peaks)) if peaks else 220 - self.age))
        lthr = int(self.profile.get("lactate_threshold_hr") or round(0.88 * max_hr))
        rhr = (
            round(float(self.df["rhr"].dropna().mean()), 1)
            if not self.df.empty and "rhr" in self.df.columns and self.df["rhr"].notna().any() else 60.0
        )
        np_runs = sorted(
            float(a["normPower"]) for a in self.activities_all
            if a.get("normPower") and (a.get("duration") or 0) > 1200
            and "running" in ((a.get("activityType") or {}).get("typeKey") or "").lower()
        )
        ftp = int(round(0.97 * sum(np_runs[-3:]) / len(np_runs[-3:]))) if np_runs else None
        return {"max_hr": max_hr, "lthr": lthr, "rhr": rhr, "ftp_w": ftp, "ftp_reference_weight_kg": self.get_current_weight()}

    def load_data(self) -> None:
        """Ham telemetri dosyalarını (günlük, uyku, aktivite, yük, VO2, tartı) yükler."""
        with self.lock:
            self._load_data_locked()
            if self._req_cache is not None:
                self._req_cache.clear()

    def _repair_empty_training_status(self) -> None:
        """Garmin gün başında (veya saat eşitlenmeden önce) 'bugün' için boş (null) Training Status döndürebilir.
        Boş kayıtlar yük analizini 0'a düşürmesin diye en son dolu haftalık kayıt kullanılır."""
        def _has_data(obj: Any) -> bool:
            return isinstance(obj, dict) and bool(obj.get("mostRecentTrainingStatus") or obj.get("mostRecentTrainingLoadBalance"))

        weekly = self.training_status_weekly if isinstance(self.training_status_weekly, dict) else {}
        self.training_status_weekly = {k: v for k, v in weekly.items() if _has_data(v)}
        self.training_status_as_of = None
        self.training_status_is_fallback = False
        if not _has_data(self.training_status_latest) and self.training_status_weekly:
            self.training_status_as_of = max(self.training_status_weekly)
            self.training_status_is_fallback = True
            self.training_status_latest = self.training_status_weekly[self.training_status_as_of]

    def _load_data_locked(self) -> None:
        self._apply_profile()
        daily_path = os.path.join(self.data_dir, "raw_daily_93d.json")
        sleep_path = os.path.join(self.data_dir, "raw_sleep_stats.json")
        acts_path = os.path.join(self.data_dir, "raw_activities.json")
        ts_latest_path = os.path.join(self.data_dir, "raw_training_status_latest.json")
        ts_weekly_path = os.path.join(self.data_dir, "raw_training_status_weekly.json")
        vo2_path = os.path.join(self.data_dir, "raw_vo2max_history.json")
        weight_path = os.path.join(self.data_dir, "raw_weight.json")

        self.daily_raw = _read_json(daily_path, {"summaries": {}, "readiness": {}})
        self.sleep_stats = _read_json(sleep_path, {})
        self.activities_all = _read_json(acts_path, [])
        self.training_status_latest = _read_json(ts_latest_path, {})
        self.training_status_weekly = _read_json(ts_weekly_path, {})
        self._repair_empty_training_status()
        self.vo2max_history = _read_json(vo2_path, [])
        self.weight_raw = _read_json(weight_path, {})

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

        self._build_daily_frame()

        self._build_activity_frame()

    def _activity_cutoff(self) -> str:
        """Aktivite penceresinin başlangıcı: günlük veri aralığının başlangıcından 18 gün önce (ısınma/geçiş seansları dahil)."""
        if not self.dates:
            return "1970-01-01"
        return (datetime.strptime(self.dates[0], "%Y-%m-%d") - timedelta(days=18)).strftime("%Y-%m-%d")

    def _build_daily_frame(self):
        """Günlük özet, uyku ve hazırlık verilerinden günlük biyometri DataFrame'ini (df) üretir."""
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


    def _build_activity_frame(self):
        """Ham aktivitelerden (koşu dinamikleri, TE, nabız zonları, EF dahil) aktivite DataFrame'lerini (adf, adf_3m) üretir."""
        act_rows = []
        min_act_cutoff = self._activity_cutoff()
        for a in self.activities_all:
            dt_local = a.get("startTimeLocal", "")
            dt_date = dt_local[:10]
            if dt_date < min_act_cutoff:
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

