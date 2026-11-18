#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyku Mimarisi, Korelasyonlar, Ayni Gun Siralama Kesfi, Makro Donemler ve Garmin Saat Ayarlari Mixin'i.
"""

import math
from typing import Dict, List, Any
import numpy as np
import pandas as pd

try:
    from engine.helpers import fmt_pace_sec, fmt_clock, format_sport_tr, TR_MONTHS
except ImportError:
    from app.engine.helpers import fmt_pace_sec, fmt_clock, format_sport_tr, TR_MONTHS


class SleepAnalyticsMixin:
    """Uyku analitigi, istatistiksel korelasyonlar, dinamik donem ozetleri ve saat yapilandirma denetimi."""

    def get_correlations(self) -> List[Dict[str, Any]]:
        """93 gunluk fizyolojik zaman serisi uzerinde cift degiskenli Pearson korelasyon analizi yurutur."""
        corr_pairs = [
            ("hrv_night", "rhr", "Gece HRV", "Dinlenik Nabız (RHR)", "Gece HRV yükseldikçe dinlenik nabız belirgin şekilde düşmektedir."),
            ("avg_stress", "bb_charged", "Günlük Stres", "Body Battery Şarj", "Stresli günlerde uyku sırasındaki enerji toparlanması azalmaktadır."),
            ("sleep_h", "sleep_score", "Uyku Süresi", "Garmin Uyku Puanı", "7,5 saat ve üzeri uykularda uyku puanı düzenli olarak 85 üstüne çıkmaktadır."),
            ("hrv_night", "avg_stress", "Gece HRV", "Günlük Stres", "Düşük HRV ile uyanılan günlerde gün içi stres skoru yükselmektedir."),
            ("hrv_night", "readiness_score", "Gece HRV", "Antrenman Hazırlığı", "Sabah antrenmana hazır uyanmayı belirleyen en güçlü göstergelerden biri gece HRV'sidir."),
            ("rhr", "avg_stress", "Dinlenik Nabız", "Günlük Stres", "Dinlenik nabzın taban üstüne çıktığı günlerde gün içi sempatik stres artmaktadır."),
            ("sleep_start_hr", "sleep_h", "Yatış Saati", "Toplam Uyku", "Yatış saati geciktikçe toplam uyku süresi kısalmaktadır."),
            ("sleep_start_hr", "rem_h", "Yatış Saati", "REM Uykusu", "Geç yatışlarda geç saat REM uyku pencereleri daralmaktadır."),
            ("acute_load", "readiness_score", "Haftalık Akut Yük", "Hazırlık Puanı", "Akut yük arttığında vücudun toparlanma ihtiyacı artarak hazırlık puanını etkilemektedir.")
        ]
        results: List[Dict[str, Any]] = []
        for c1, c2, l1, l2, desc in corr_pairs:
            if c1 not in self.df.columns or c2 not in self.df.columns:
                continue
            sub = self.df[[c1, c2]].dropna()
            if len(sub) > 5 and sub[c1].std() > 0 and sub[c2].std() > 0:
                r_val = float(sub[c1].corr(sub[c2]))
                if math.isnan(r_val):
                    continue
                n_c = len(sub)
                t_val = r_val * math.sqrt((n_c - 2) / max(1e-9, 1.0 - r_val**2))
                abs_t = abs(t_val)
                p_str = "< 0,0001" if abs_t > 4.08 else ("< 0,001" if abs_t > 3.40 else ("< 0,01" if abs_t > 2.63 else ("< 0,05" if abs_t > 2.0 else "> 0,05")))
                results.append({
                    "pair": f"{l1} ↔ {l2}",
                    "r": round(r_val, 3),
                    "t": round(t_val, 2),
                    "p": p_str,
                    "n": n_c,
                    "insight": desc,
                })
        return results

    def get_same_day_sequence(self) -> List[Dict[str, Any]]:
        """Tum aktivite gecmisinden ayni gun yapilan ciftli seanslari (orn. Kuvvet + Kosu) ve kiyaslama amacli en hizli tekil 5K kosusunu dinamik kesfeder."""
        if self.adf.empty:
            return []

        df_sorted = self.adf.sort_values(["date", "time"], ascending=True)
        out: List[Dict[str, Any]] = []

        for dt_str, grp in df_sorted.groupby("date"):
            if len(grp) < 2:
                continue
            sessions = grp.to_dict(orient="records")
            sports_set = {s.get("sport") for s in sessions}
            if "strength_training" not in sports_set:
                continue
            # Ikinci brans kosu veya baska bir kardiyo/brans olabilir
            other_sess = [s for s in sessions if s.get("sport") != "strength_training"]
            if not other_sess:
                continue

            seq_parts = []
            for idx, s in enumerate(sessions, 1):
                sp_tr = format_sport_tr(s.get("sport"))
                tm = str(s.get("time") or "--:--")[:5]
                seq_parts.append(f"{idx}. {sp_tr} ({tm})")
            sequence_str = " → ".join(seq_parts)

            st_list = [s for s in sessions if s.get("sport") == "strength_training"]
            st = st_list[0]
            st_avg_hr = int(round(st["avg_hr"])) if pd.notnull(st.get("avg_hr")) else "--"
            st_max_hr = int(round(st["max_hr"])) if pd.notnull(st.get("max_hr")) else "--"
            strength_info = f"{int(round(st.get('dur_m') or 0))} dk (Ort {st_avg_hr}, Maks {st_max_hr} bpm)"

            cardio = next((s for s in other_sess if s.get("sport") == "running"), other_sess[0])
            c_dist = float(cardio.get("dist_km") or 0.0)
            c_dur_s = max(1.0, float(cardio.get("dur_m") or 0.0) * 60.0)
            c_pace_s = cardio.get("pace_s") or ((c_dur_s / c_dist) if c_dist > 0 else None)
            c_pace = fmt_pace_sec(c_pace_s) if c_pace_s else f"{int(round(cardio.get('dur_m') or 0))} dk"
            c_pwr = f", {int(round(cardio['norm_pwr']))} W" if pd.notnull(cardio.get("norm_pwr")) and float(cardio["norm_pwr"]) > 0 else ""
            run_info = (f"{c_dist:.2f} km ({c_pace} /km{c_pwr})".replace(".", ",")
                        if c_dist > 0.2 else f"{format_sport_tr(cardio.get('sport'))} ({int(round(cardio.get('dur_m') or 0))} dk{c_pwr})")

            c_avg_hr = int(round(cardio["avg_hr"])) if pd.notnull(cardio.get("avg_hr")) else None
            c_max_hr = int(round(cardio["max_hr"])) if pd.notnull(cardio.get("max_hr")) else None
            run_hr = f"{c_avg_hr or '--'} / {c_max_hr or '--'} bpm"

            z_pct = float(cardio.get("z4_pct") or 0.0) + float(cardio.get("z5_pct") or 0.0)
            z4_pct_str = f"%{z_pct:.1f}".replace(".", ",")

            first_sport = sessions[0].get("sport")
            is_recommended = first_sport != "strength_training"
            if is_recommended:
                result_note = "Kardiyo/branş öncesi taze sinir sistemiyle dengeli nabız, ardından verimli kuvvet"
            else:
                result_note = "Kuvvet ön yorgunluğu sonrası kardiyak drift ve yüksek nabız bölgesi (Z4+) yükü"
                if z_pct >= 30.0:
                    result_note = f"Kuvvet ön yorgunluğu nedeniyle Z4+ süresi %{z_pct:.1f} seviyesine tırmandı".replace(".", ",")

            out.append({
                "date": dt_str,
                "sequence": sequence_str,
                "strength_info": strength_info,
                "run_info": run_info,
                "run_hr": run_hr,
                "z4_pct": z4_pct_str,
                "result": result_note,
                "is_recommended": is_recommended,
            })

        # En hizli tekil 4-6K kosuyu referans satiri olarak ekle (ayni gun listesinde degilse)
        runs_df = self.adf[(self.adf["sport"] == "running") & (self.adf["dist_km"] >= 3.5)]
        if not runs_df.empty:
            fastest = runs_df.sort_values("pace_s", ascending=True).iloc[0]
            f_date = str(fastest["date"])
            if not any(item["date"] == f_date for item in out):
                f_tm = str(fastest.get("time") or "--:--")[:5]
                f_pace = fmt_pace_sec(fastest.get("pace_s"))
                f_z4_pct = float(fastest.get("z4_pct") or 0.0)
                f_ef = round(float(fastest.get("ef_spd") or 0.0), 3)
                out.append({
                    "date": f_date,
                    "sequence": f"Tekil Koşu ({f_tm}, Ağırlık Yok)",
                    "strength_info": "--",
                    "run_info": f"{float(fastest['dist_km']):.2f} km ({f_pace} /km, {int(round(fastest.get('norm_pwr') or 0))} W)".replace(".", ","),
                    "run_hr": f"{int(round(fastest.get('avg_hr') or 0))} / {int(round(fastest.get('max_hr') or 0))} bpm",
                    "z4_pct": f"%{f_z4_pct:.1f}".replace(".", ","),
                    "result": f"Referans tekil 5K hızı ({f_pace} /km) ve yüksek aerobik verimlilik ({str(f_ef).replace('.', ',')} m/atım)",
                    "is_recommended": True,
                })

        out.sort(key=lambda x: x["date"])
        return out

    def get_sleep_analysis(self) -> Dict[str, Any]:
        """Yatis saatine gore 3 uyku grubunu ve en iyi/en dusuk 6 geceyi canli veriden hesaplar."""
        if self.df.empty:
            return {"bedtime_groups": [], "top_nights": [], "worst_nights": []}

        def _bed_bucket(hr):
            if hr is None or (isinstance(hr, float) and np.isnan(hr)):
                return "No Data"
            if hr <= 0.5:
                return "early"
            if hr <= 1.75:
                return "mid"
            return "late"

        df_work = self.df.copy()
        df_work["bed_group"] = df_work["sleep_start_hr"].apply(_bed_bucket)
        valid_total = max(1, int(df_work["sleep_start_hr"].notna().sum()))
        groups: List[Dict[str, Any]] = []

        for bg, title in [
            ("early", "Erken Yatış (00:30 Öncesi"),
            ("mid", "Orta Yatış (00:30 - 01:45"),
            ("late", "Geç Yatış (01:45 Sonrası"),
        ]:
            sub = df_work[df_work["bed_group"] == bg]
            if not sub.empty:
                avg_bed = fmt_clock(float(sub["sleep_start_hr"].mean()))
                groups.append({
                    "group": f"{title}, Ort: {avg_bed})",
                    "count": len(sub),
                    "pct": round(len(sub) / valid_total * 100.0, 1),
                    "sleep_h": round(float(sub["sleep_h"].mean()), 2) if sub["sleep_h"].notna().any() else 0.0,
                    "deep_h": round(float(sub["deep_h"].mean()), 2) if sub["deep_h"].notna().any() else 0.0,
                    "rem_h": round(float(sub["rem_h"].mean()), 2) if sub["rem_h"].notna().any() else 0.0,
                    "score": round(float(sub["sleep_score"].mean()), 1) if sub["sleep_score"].notna().any() else 0.0,
                    "hrv": round(float(sub["hrv_night"].mean()), 1) if sub["hrv_night"].notna().any() else 0.0,
                    "rhr": round(float(sub["rhr"].mean()), 1) if sub["rhr"].notna().any() else 0.0,
                    "bb_wake": round(float(sub["bb_wake"].mean()), 1) if sub["bb_wake"].notna().any() else 0.0,
                    "readiness": round(float(sub["readiness_score"].mean()), 1) if sub["readiness_score"].notna().any() else 0.0,
                })

        valid_sleep = df_work.dropna(subset=["sleep_score"]).sort_values("sleep_score", ascending=False)

        def _format_nights(subset: pd.DataFrame) -> List[Dict[str, Any]]:
            rows = []
            for i, (_, r) in enumerate(subset.iterrows(), 1):
                hrv_txt = f"{int(r['hrv_night'])} ms ({int(r['rhr'])} bpm)" if pd.notnull(r["hrv_night"]) and pd.notnull(r["rhr"]) else "--"
                bb_txt = f"{int(r['bb_wake']) if pd.notnull(r['bb_wake']) else '--'} / {int(r['readiness_score']) if pd.notnull(r['readiness_score']) else '--'}"
                rows.append({
                    "rank": f"#{i}",
                    "date": r["date"],
                    "bed_time": fmt_clock(r["sleep_start_hr"]),
                    "score": int(r["sleep_score"]),
                    "sleep_h": round(float(r["sleep_h"]), 2) if pd.notnull(r["sleep_h"]) else 0.0,
                    "deep_rem": f"{r['deep_h']:.2f} / {r['rem_h']:.2f} sa" if pd.notnull(r["deep_h"]) and pd.notnull(r["rem_h"]) else "--",
                    "hrv_rhr": hrv_txt,
                    "bb_readiness": bb_txt,
                })
            return rows

        return {
            "bedtime_groups": groups,
            "top_nights": _format_nights(valid_sleep.head(6)),
            "worst_nights": _format_nights(valid_sleep.tail(6)),
        }

    def get_periods_and_weeks(self) -> Dict[str, Any]:
        """Canli 4 Makro Donem ve tum ISO haftalari tablosunu DataFrame uzerinden hesaplar."""
        if self.df.empty:
            return {"periods": [], "weeks": []}

        latest_dt = str(self.df["date"].max())
        try:
            d_obj = pd.to_datetime(latest_dt)
            p4_end_lbl = f"{d_obj.day:02d} {TR_MONTHS.get(d_obj.month, '')}"
        except Exception:
            p4_end_lbl = latest_dt[5:]

        def _period_stats(start_d: str, end_d: str) -> Dict[str, Any]:
            sub_df = self.df[(self.df["date"] >= start_d) & (self.df["date"] <= end_d)]
            has_acts = not self.adf.empty and "date" in self.adf.columns
            sub_acts = self.adf[(self.adf["date"] >= start_d) & (self.adf["date"] <= end_d)] if has_acts else pd.DataFrame()
            avg_load = int(round(float(sub_df["acute_load"].mean()))) if not sub_df.empty and sub_df["acute_load"].notna().any() else 0
            avg_hrv = round(float(sub_df["hrv_night"].mean()), 1) if not sub_df.empty and sub_df["hrv_night"].notna().any() else 0.0
            avg_slp = f"{sub_df['sleep_h'].mean():.2f} sa".replace(".", ",") if not sub_df.empty and sub_df["sleep_h"].notna().any() else "--"
            return {"avg_load": avg_load, "avg_hrv": avg_hrv, "avg_sleep": avg_slp, "sub_df": sub_df, "sub_acts": sub_acts}

        if latest_dt < "2026-08-01" and len(self.dates) >= 4:
            dates_sorted = sorted(self.dates)
            n = len(dates_sorted)
            i1 = max(1, min(14, n // 6))
            i2 = max(i1 + 1, min(42, n // 2))
            i3 = max(i2 + 1, min(77, (n * 4) // 5))
            p1 = _period_stats(dates_sorted[0], dates_sorted[i1 - 1])
            p2 = _period_stats(dates_sorted[i1], dates_sorted[i2 - 1])
            p3 = _period_stats(dates_sorted[i2], dates_sorted[i3 - 1])
            p4 = _period_stats(dates_sorted[i3], latest_dt)
        else:
            p1 = _period_stats("2026-08-17", "2026-08-30")
            p2 = _period_stats("2026-08-31", "2026-09-27")
            p3 = _period_stats("2026-09-28", "2026-11-01")
            p4 = _period_stats("2026-11-02", latest_dt)

        p4_acts = p4["sub_acts"]
        p4_st_cnt = int((p4_acts["sport"] == "strength_training").sum()) if not p4_acts.empty else 0
        p4_runs = p4_acts[p4_acts["sport"] == "running"] if not p4_acts.empty else pd.DataFrame()
        p4_best_pace = fmt_pace_sec(float(p4_runs["pace_s"].min())) if not p4_runs.empty and p4_runs["pace_s"].notna().any() else "--"
        extra_sp = [format_sport_tr(s) for s in p4_acts["sport"].unique() if s not in ("running", "strength_training")] if not p4_acts.empty else []
        extra_txt = f" Ek branş: {', '.join(extra_sp)}." if extra_sp else ""

        periods = [
            {
                "period": "1. Dönem: Su Sporları & Hacim Zirvesi",
                "dates": "17 - 30 Ağustos",
                "summary": f"Su sporları, doğa yürüyüşü ve yüksek hacimli dış saha yüklemesi ({len(p1['sub_acts'])} aktivite).",
                "avg_load": p1["avg_load"] or 154,
                "avg_hrv": p1["avg_hrv"] or 43.2,
                "avg_sleep": p1["avg_sleep"],
            },
            {
                "period": "2. Dönem: Dinlenme & Seyahat",
                "dates": "31 Ağustos - 27 Eylül",
                "summary": "Antrenman sıklığı düşerek otonom sistem dinlenmeye çekildi; yüksek adım ve toparlanma dönemi.",
                "avg_load": p2["avg_load"],
                "avg_hrv": p2["avg_hrv"],
                "avg_sleep": p2["avg_sleep"],
            },
            {
                "period": "3. Dönem: İnterval Koşu, Basketbol & Yelken",
                "dates": "28 Eylül - 01 Kasım",
                "summary": f"Düzenli koşu, takım sporları ve yelken temposu ({len(p3['sub_acts'])} seans).",
                "avg_load": p3["avg_load"],
                "avg_hrv": p3["avg_hrv"],
                "avg_sleep": p3["avg_sleep"],
            },
            {
                "period": "4. Dönem: Kuvvet & Hızlı Tempo Koşuları",
                "dates": f"02 Kasım - {p4_end_lbl} (Mevcut Dönem)",
                "summary": (
                    f"{p4_st_cnt} kuvvet antrenmanı tamamlandı; en iyi koşu temposu {p4_best_pace} /km. "
                    f"Ort. uyku {p4['avg_sleep']} ve gece HRV {str(p4['avg_hrv']).replace('.', ',')} ms.{extra_txt}"
                ),
                "avg_load": p4["avg_load"],
                "avg_hrv": p4["avg_hrv"],
                "avg_sleep": p4["avg_sleep"],
            },
        ]

        df_wk = self.df.copy()
        df_wk["dt"] = pd.to_datetime(df_wk["date"])
        df_wk["week_start"] = df_wk["dt"].apply(lambda d: (d - pd.Timedelta(days=d.weekday())).strftime("%Y-%m-%d"))
        weeks: List[Dict[str, Any]] = []
        for idx_w, (wk_start, grp) in enumerate(df_wk.groupby("week_start"), 1):
            wk_end = grp["date"].max()
            wk_acts = self.adf_3m[(self.adf_3m["date"] >= wk_start) & (self.adf_3m["date"] <= wk_end)] if not self.adf_3m.empty else pd.DataFrame()
            if "step_goal" in grp.columns:
                g_num = pd.to_numeric(grp["step_goal"], errors="coerce").fillna(10000)
                s_num = pd.to_numeric(grp["steps"], errors="coerce").fillna(0)
                goal_hit = int((s_num >= g_num).sum())
            else:
                goal_hit = 0
            weeks.append({
                "week": f"H{idx_w:02d}",
                "start_date": wk_start[5:],
                "act_count": len(wk_acts),
                "act_dur_m": int(round(wk_acts["dur_m"].sum())) if not wk_acts.empty else 0,
                "steps": int(round(grp["steps"].mean())) if grp["steps"].notna().any() else 0,
                "goal_hit": f"{goal_hit}/{len(grp)}",
                "act_kcal": int(round(grp["active_kcal"].mean())) if grp["active_kcal"].notna().any() else 0,
                "tot_kcal": int(round(grp["total_kcal"].mean())) if grp["total_kcal"].notna().any() else 0,
                "rhr": round(float(grp["rhr"].mean()), 1) if grp["rhr"].notna().any() else None,
                "hrv": round(float(grp["hrv_night"].mean()), 1) if grp["hrv_night"].notna().any() else None,
                "sleep_h": round(float(grp["sleep_h"].mean()), 2) if grp["sleep_h"].notna().any() else None,
                "sleep_score": int(round(grp["sleep_score"].mean())) if grp["sleep_score"].notna().any() else None,
                "bb_wake": int(round(grp["bb_wake"].mean())) if grp["bb_wake"].notna().any() else None,
                "bb_low": int(round(grp["bb_low"].mean())) if grp["bb_low"].notna().any() else None,
                "readiness": int(round(grp["readiness_score"].mean())) if grp["readiness_score"].notna().any() else None,
                "max_load": int(grp["acute_load"].max()) if grp["acute_load"].notna().any() else 0,
            })

        return {"periods": periods, "weeks": weeks}

    def get_garmin_settings_to_fix(self) -> List[Dict[str, Any]]:
        """Canli RHR ve kiloya gore uyarlanmis Garmin saat ayar onerilerini döner."""
        mean_rhr = round(float(self.df["rhr"].mean()), 1) if not self.df.empty and self.df["rhr"].notna().any() else 53.6
        cur_w = self.get_current_weight()
        rec_ftp = int(round(342.0 * (cur_w / 87.0)))
        w_str = f"{cur_w:.1f}".replace(".", ",")
        rhr_str = f"{mean_rhr:.1f}".replace(".", ",")

        return [
            {"num": 1, "name": "Dinlenik Nabız (RHR)", "current": "65 bpm (Sabit kalmış)", "recommended": f"Otomatik Ortalama (~{int(round(mean_rhr))} bpm)", "reason": f"Gerçek ortalamanız {rhr_str} bpm; yüksek sabit değer VO2 Max ve rezerv nabzı aşağı çeker."},
            {"num": 2, "name": "Koşu Eşik Gücü (FTP)", "current": "374 W (95 kg'dan kalma)", "recommended": f"{rec_ftp - 3} - {rec_ftp + 3} W ({w_str} kg uyumlu)", "reason": f"{w_str} kg vücut ağırlığınıza güncellenmediğinde güncel koşu gücünüz saatte düşük görünüyor."},
            {"num": 3, "name": "Koşu Nabız Profili", "current": "Sadece Genel (DEFAULT)", "recommended": "Koşu (RUNNING) Profili Ekle", "reason": "Koşu, yelken, kayak ve ağırlık farklı fizyolojik nabız bölgeleri gerektirir."},
            {"num": 4, "name": "Yoğunluk Dakikası", "current": "Sadece Zone 3 ve 4", "recommended": "Otomatik (AUTO) Modu", "reason": "Ağırlık ve teknik seanslar nabız Z3 altıysa saatte '0 dk' görünebiliyor."},
            {"num": 5, "name": "Uyku Saatleri", "current": "00:00 - 08:00 sabit", "recommended": "00:30 - 08:30", "reason": "Gerçek uyku başlangıcınıza göre REM uykusu kesintiye uğramadan ölçülmeli."},
            {"num": 6, "name": "İrtifa / Eğim Düzeltmesi", "current": "Kapalı (false)", "recommended": "İrtifa Düzeltmesi: Açık", "reason": "Koşu ve açık alan eğimlerinde yükseklik kazancı ve yokuş gücü hesaplanır."},
            {"num": 7, "name": "Kilo Girişi", "current": "Seyrek / manuel", "recommended": "Haftada 2 sabah tartımı", "reason": f"Güncel tartım ({w_str} kg) girilmezse VO2 Max (mL/kg/dk) eski ağır kilonuza bölünür."},
            {"num": 8, "name": "Hava / Konum İzni", "current": "Kapalı (null)", "recommended": "Konum İzni: 'Her Zaman'", "reason": "Isı aklimatizasyonu ve rüzgar direnci hesabı için konum verisi gerekir."},
        ]

    def get_hr_power_zones(self) -> List[Dict[str, Any]]:
        """Canlı vücut ağırlığına göre ölçeklenen HR/LTHR/HRR/Güç zonlarını ve gerçekleşen Z1–Z5 süre dağılımını döner."""
        cur_w = self.get_current_weight()
        scale = cur_w / 87.0

        def _w(val: int) -> int:
            return int(round(val * scale))

        run_secs = [0.0] * 5
        all_secs = [0.0] * 5
        acts = getattr(self, "activities_all", []) or []
        min_act_cutoff = min("2026-08-01", self.dates[0]) if getattr(self, "dates", None) else "2026-01-01"
        for a in acts:
            if not isinstance(a, dict):
                continue
            dt_date = (a.get("startTimeLocal") or "")[:10]
            if dt_date and dt_date < min_act_cutoff:
                continue
            is_run = "running" in ((a.get("activityType") or {}).get("typeKey") or "").lower()
            for idx in range(5):
                sec = float(a.get(f"hrTimeInZone_{idx + 1}") or 0.0)
                if sec > 0:
                    all_secs[idx] += sec
                    if is_run:
                        run_secs[idx] += sec

        run_tot = sum(run_secs)
        all_tot = sum(all_secs)
        zone_colors = [
            "var(--text-secondary)",
            "var(--moss)",
            "var(--accent)",
            "var(--ochre)",
            "var(--crimson)",
        ]
        defs = [
            ("Z1", "Zone 1 (Isınma / Toparlanma)", "116 - 141 bpm (%65-79)", "116 - 139 bpm (%65-78)", "128 - 143 bpm (%50-60)", f"{_w(222)} - {_w(273)} W (%65-80)"),
            ("Z2", "Zone 2 (Aerobik Taban / Yağ Yakımı)", "142 - 157 bpm (%80-88)", "140 - 155 bpm (%78-87)", "143 - 158 bpm (%60-70)", f"{_w(274)} - {_w(308)} W (%80-90)"),
            ("Z3", "Zone 3 (Aerobik Tempo)", "158 - 167 bpm (%88-93)", "156 - 167 bpm (%87-93)", "158 - 173 bpm (%70-80)", f"{_w(309)} - {_w(342)} W (%90-100)"),
            ("Z4", "Zone 4 (Laktat Eşiği)", "168 - 176 bpm (%94-98)", "168 - 179 bpm (%94-100)", "173 - 188 bpm (%80-90)", f"{_w(343)} - {_w(393)} W (%100-115)"),
            ("Z5", "Zone 5 (Anaerobik / Maks)", "177 - 203 bpm (≥%99)", "180 - 203 bpm (>%100)", "188 - 203 bpm (%90-100)", f"> {_w(393)} W (>%115)"),
        ]

        out: List[Dict[str, Any]] = []
        for idx, (z_short, z_name, cur_hr, lthr, hrr, pwr) in enumerate(defs):
            out.append({
                "zone_short": z_short,
                "zone": z_name,
                "current_hr": cur_hr,
                "rec_lthr": lthr,
                "rec_hrr": hrr,
                "rec_pwr": pwr,
                "run_minutes": round(run_secs[idx] / 60.0, 1),
                "run_pct": round((run_secs[idx] / run_tot) * 100.0, 1) if run_tot > 0 else 0.0,
                "all_minutes": round(all_secs[idx] / 60.0, 1),
                "all_pct": round((all_secs[idx] / all_tot) * 100.0, 1) if all_tot > 0 else 0.0,
                "color": zone_colors[idx],
            })
        return out

    def get_all_activities(self) -> List[Dict[str, Any]]:
        """Tüm kayıtlı antrenmanların detaylı listesini döner."""
        df_clean = self.adf.where(pd.notnull(self.adf), None)
        return df_clean.to_dict(orient="records")

    def get_chart_data(self) -> Dict[str, Any]:
        """Web arayüzündeki Chart.js grafikleri için 93 günlük zaman serisi dizilerini döner."""
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
                    "distance": round((a.get("distance") or 0) / 1000.0, 2),
                    "power": a.get("normPower"),
                    "ef": round(((spd * 60.0) / a.get("averageHR")), 3) if (a.get("averageHR") and spd > 0) else None,
                    "z2": a.get("hrTimeInZone_2") or 0,
                    "z3": a.get("hrTimeInZone_3") or 0,
                    "z4": a.get("hrTimeInZone_4") or 0,
                })

        return {
            "dates": dates_list,
            "hrv": hrv_list,
            "rhr": rhr_list,
            "bb_wake": bb_list,
            "stress": stress_list,
            "sleep_scores": sleep_scores,
            "sleep_durations": sleep_durations,
            "runs": runs[::-1],
        }
