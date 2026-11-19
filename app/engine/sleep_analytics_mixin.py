#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyku Mimarisi, Korelasyonlar, Ayni Gun Siralama Kesfi, Makro Donemler ve Garmin Saat Ayarlari Mixin'i.
"""

import logging
import math
from typing import Dict, List, Any, Tuple
import pandas as pd

try:
    from engine.helpers import fmt_pace_sec, fmt_clock, format_sport_tr, TR_MONTHS
except ImportError:
    from app.engine.helpers import fmt_pace_sec, fmt_clock, format_sport_tr, TR_MONTHS


logger = logging.getLogger(__name__)


class SleepAnalyticsMixin:
    """Uyku analitigi, istatistiksel korelasyonlar, dinamik donem ozetleri ve saat yapilandirma denetimi."""

    # (sütun1, sütun2, etiket1, etiket2, negatif ilişki yorumu, pozitif ilişki yorumu)
    _CORR_PAIRS = [
        ("hrv_night", "rhr", "Gece HRV", "Dinlenik Nabız (RHR)",
         "Gece HRV yükseldikçe dinlenik nabız düşüyor (beklenen toparlanma ilişkisi).",
         "Gece HRV ile dinlenik nabız birlikte artıyor (beklenenin tersi; ölçüm veya hastalık etkisi olabilir)."),
        ("avg_stress", "bb_charged", "Günlük Stres", "Body Battery Şarj",
         "Stresli günlerde uyku sırasındaki enerji toparlanması azalıyor.",
         "Stres arttıkça Body Battery şarjı da artıyor (beklenenin tersi)."),
        ("sleep_h", "sleep_score", "Uyku Süresi", "Garmin Uyku Puanı",
         "Uyku süresi arttıkça Garmin uyku puanı düşüyor (beklenenin tersi).",
         "Uyku süresi arttıkça Garmin uyku puanı yükseliyor."),
        ("hrv_night", "avg_stress", "Gece HRV", "Günlük Stres",
         "Düşük HRV ile uyanılan günlerde gün içi stres skoru yüksek.",
         "HRV yükseldikçe gün içi stres de yükseliyor (beklenenin tersi)."),
        ("hrv_night", "readiness_score", "Gece HRV", "Antrenman Hazırlığı",
         "Gece HRV yükseldikçe hazırlık puanı düşüyor (beklenenin tersi).",
         "Gece HRV yükseldikçe sabah antrenman hazırlığı da yükseliyor."),
        ("rhr", "avg_stress", "Dinlenik Nabız", "Günlük Stres",
         "Dinlenik nabız arttıkça gün içi stres azalıyor (beklenenin tersi).",
         "Dinlenik nabız taban üstüne çıktığında gün içi sempatik stres artıyor."),
        ("sleep_start_hr", "sleep_h", "Yatış Saati", "Toplam Uyku",
         "Yatış saati geciktikçe toplam uyku süresi kısalıyor.",
         "Yatış saati geciktikçe toplam uyku süresi uzuyor (beklenenin tersi)."),
        ("sleep_start_hr", "rem_h", "Yatış Saati", "REM Uykusu",
         "Yatış saati geciktikçe REM uykusu azalıyor.",
         "Yatış saati geciktikçe REM uykusu artıyor (beklenenin tersi)."),
        ("acute_load", "readiness_score", "Haftalık Akut Yük", "Hazırlık Puanı",
         "Akut yük arttıkça hazırlık puanı düşüyor (toparlanma ihtiyacı artıyor).",
         "Akut yük arttıkça hazırlık puanı da yükseliyor (beklenenin tersi)."),
    ]

    @staticmethod
    def _student_t_p_two_sided(t_val: float, dof: int) -> float:
        """Student t dağılımı için çift yönlü p-değeri (düzenlenmiş eksik beta fonksiyonu ile; ek bağımlılık yok)."""
        if dof <= 0:
            return 1.0
        x = dof / (dof + t_val * t_val)

        def _betacf(a: float, b: float, xx: float) -> float:
            tiny, qab, qap, qam = 1e-30, a + b, a + 1.0, a - 1.0
            c, d = 1.0, 1.0 - qab * xx / qap
            d = 1.0 / (d if abs(d) > tiny else tiny)
            h = d
            for m in range(1, 200):
                m2 = 2 * m
                aa = m * (b - m) * xx / ((qam + m2) * (a + m2))
                d = 1.0 + aa * d
                d = 1.0 / (d if abs(d) > tiny else tiny)
                c = 1.0 + aa / c
                c = c if abs(c) > tiny else tiny
                h *= d * c
                aa = -(a + m) * (qab + m) * xx / ((a + m2) * (qap + m2))
                d = 1.0 + aa * d
                d = 1.0 / (d if abs(d) > tiny else tiny)
                c = 1.0 + aa / c
                c = c if abs(c) > tiny else tiny
                delta = d * c
                h *= delta
                if abs(delta - 1.0) < 3e-12:
                    break
            return h

        a, b = dof / 2.0, 0.5
        ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x) if 0 < x < 1 else 0.0
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        bt = math.exp(ln_beta)
        if x < (a + 1.0) / (a + b + 2.0):
            ib = bt * _betacf(a, b, x) / a
        else:
            ib = 1.0 - bt * _betacf(b, a, 1.0 - x) / b
        return max(0.0, min(1.0, ib))

    @staticmethod
    def _corr_strength(r: float) -> str:
        a = abs(r)
        return "çok zayıf" if a < 0.2 else "zayıf" if a < 0.4 else "orta" if a < 0.6 else "güçlü" if a < 0.8 else "çok güçlü"

    def get_correlations(self) -> List[Dict[str, Any]]:
        """
        Günlük fizyolojik zaman serilerinde çift değişkenli Pearson korelasyonu: r, t, gerçek Student-t p-değeri, güç ve yön.
        Yorum metni hesaplanan r'ın işaretinden ve gücünden üretilir (hazır cümle değildir). Ardışık günler tam bağımsız
        olmadığı için p-değerleri iyimser kabul edilmelidir; bu yüzden anlamlılık için p < 0,01 ve |r| ≥ 0,3 aranır.
        """
        results: List[Dict[str, Any]] = []
        for c1, c2, l1, l2, neg_txt, pos_txt in self._CORR_PAIRS:
            if c1 not in self.df.columns or c2 not in self.df.columns:
                continue
            sub = self.df[[c1, c2]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(sub) <= 5 or sub[c1].std() <= 0 or sub[c2].std() <= 0:
                continue
            r_val = float(sub[c1].corr(sub[c2]))
            if math.isnan(r_val):
                continue
            n_c = len(sub)
            t_val = r_val * math.sqrt((n_c - 2) / max(1e-9, 1.0 - r_val ** 2))
            p_val = self._student_t_p_two_sided(t_val, n_c - 2)
            significant = p_val < 0.01 and abs(r_val) >= 0.3
            strength = self._corr_strength(r_val)
            p_str = "< 0,0001" if p_val < 0.0001 else f"{p_val:.4f}".replace(".", ",")
            if significant:
                insight = f"{neg_txt if r_val < 0 else pos_txt} (r = {r_val:.2f}, {strength}, n = {n_c})"
            else:
                insight = f"Anlamlı bir ilişki saptanmadı (r = {r_val:.2f}, {strength}, n = {n_c})."
            results.append({
                "pair": f"{l1} ↔ {l2}",
                "r": round(r_val, 3),
                "t": round(t_val, 2),
                "p": p_str,
                "p_value": round(p_val, 6),
                "n": n_c,
                "strength": strength,
                "direction": "negatif" if r_val < 0 else "pozitif",
                "significant": significant,
                "insight": insight,
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
        """En iyi/en dusuk 6 uyku gecesini canli veriden hesaplar."""
        if self.df.empty:
            return {"top_nights": [], "worst_nights": []}

        valid_sleep = self.df.dropna(subset=["sleep_score"]).sort_values("sleep_score", ascending=False)

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
            "top_nights": _format_nights(valid_sleep.head(6)),
            "worst_nights": _format_nights(valid_sleep.tail(6)),
        }

    def get_periods_and_weeks(self) -> Dict[str, Any]:
        """Canli 4 Makro Donem ve tum ISO haftalari tablosunu DataFrame uzerinden hesaplar."""
        if self.df.empty:
            return {"periods": [], "weeks": []}

        def _date_lbl(d: str) -> str:
            try:
                d_obj = pd.to_datetime(d)
                return f"{d_obj.day:02d} {TR_MONTHS[d_obj.month - 1]}"
            except (ValueError, TypeError):
                logger.debug("get_periods_and_weeks: tarih etiketi üretilemedi", exc_info=True)
                return d[5:]

        def _period_stats(start_d: str, end_d: str) -> Dict[str, Any]:
            sub_df = self.df[(self.df["date"] >= start_d) & (self.df["date"] <= end_d)]
            has_acts = not self.adf.empty and "date" in self.adf.columns
            sub_acts = self.adf[(self.adf["date"] >= start_d) & (self.adf["date"] <= end_d)] if has_acts else pd.DataFrame()
            avg_load = int(round(float(sub_df["acute_load"].mean()))) if not sub_df.empty and sub_df["acute_load"].notna().any() else 0
            avg_hrv = round(float(sub_df["hrv_night"].mean()), 1) if not sub_df.empty and sub_df["hrv_night"].notna().any() else 0.0
            avg_slp = f"{sub_df['sleep_h'].mean():.2f} sa".replace(".", ",") if not sub_df.empty and sub_df["sleep_h"].notna().any() else "--"
            return {"start": start_d, "end": end_d, "avg_load": avg_load, "avg_hrv": avg_hrv, "avg_sleep": avg_slp,
                    "sub_df": sub_df, "sub_acts": sub_acts}

        # 4 ardışık makro dönem sporcunun KENDİ veri aralığından kurulur (gün sayısına göre 14 / 28 / 35 / kalan düzeni)
        dates_sorted = sorted(self.dates)
        latest_dt = dates_sorted[-1]
        n = len(dates_sorted)
        if n < 4:
            return {"periods": [], "weeks": self._build_weekly_rows()}
        i1 = max(1, min(14, n // 6))
        i2 = max(i1 + 1, min(42, n // 2))
        i3 = max(i2 + 1, min(77, n - 16))
        stats = [
            _period_stats(dates_sorted[0], dates_sorted[i1 - 1]),
            _period_stats(dates_sorted[i1], dates_sorted[i2 - 1]),
            _period_stats(dates_sorted[i2], dates_sorted[i3 - 1]),
            _period_stats(dates_sorted[i3], latest_dt),
        ]
        loads = [st["avg_load"] for st in stats]
        mean_load = (sum(loads) / len(loads)) if any(loads) else 0.0
        counts = [len(st["sub_acts"]) for st in stats]
        mean_cnt = sum(counts) / len(counts)

        def _describe(idx: int, st: Dict[str, Any]) -> Tuple[str, str]:
            """Dönemin adını ve özetini sporcunun kendi aktivite/yük verisinden üretir."""
            acts = st["sub_acts"]
            cnt = len(acts)
            top = []
            if not acts.empty:
                top = [format_sport_tr(sp) for sp in acts["sport"].value_counts().head(2).index]
            sports_txt = " & ".join(top) if top else "Aktivite Yok"
            if mean_cnt and cnt <= 0.5 * mean_cnt:
                flag = "Dinlenme & Toparlanma"
            elif mean_load and st["avg_load"] >= 1.15 * mean_load:
                flag = "Yüksek Yük"
            else:
                flag = "Dengeli Yük"
            title = f"{idx + 1}. Dönem: {flag}" + (f" ({sports_txt})" if top else "")
            summary = (
                f"{cnt} aktivite ({sports_txt}); ort. yük {st['avg_load']}, gece HRV "
                f"{str(st['avg_hrv']).replace('.', ',')} ms, uyku {st['avg_sleep']}."
            )
            if idx == 3 and not acts.empty:
                st_cnt = int(acts["bucket"].eq("strength").sum())
                runs = acts[acts["bucket"] == "running"]
                best = fmt_pace_sec(float(runs["pace_s"].min())) if not runs.empty and runs["pace_s"].notna().any() else "--"
                summary += f" {st_cnt} kuvvet antrenmanı; en iyi koşu temposu {best} /km."
            return title, summary

        periods = []
        for idx, st in enumerate(stats):
            title, summary = _describe(idx, st)
            end_lbl = _date_lbl(st["end"]) + (" (Mevcut Dönem)" if idx == 3 else "")
            periods.append({
                "period": title,
                "dates": f"{_date_lbl(st['start'])} - {end_lbl}",
                "summary": summary,
                "avg_load": st["avg_load"],
                "avg_hrv": st["avg_hrv"],
                "avg_sleep": st["avg_sleep"],
            })

        return {"periods": periods, "weeks": self._build_weekly_rows()}

    def _build_weekly_rows(self) -> List[Dict[str, Any]]:
        """Veri aralığındaki tüm ISO haftalarının özet satırlarını üretir."""
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

        return weeks

    def get_garmin_settings_to_fix(self) -> List[Dict[str, Any]]:
        """Canlı RHR, kilo, tahmini eşik gücü ve uyku düzenine göre kişiselleştirilmiş Garmin saat ayar önerilerini döner."""
        phys = self.get_physiology()
        mean_rhr = phys["rhr"]
        cur_w = self.get_current_weight()
        ftp = phys["ftp_w"]
        w_str = f"{cur_w:.1f}".replace(".", ",")
        rhr_str = f"{mean_rhr:.1f}".replace(".", ",")
        ftp_rec = f"{ftp - 3} - {ftp + 3} W (koşu verilerinden tahmin, {w_str} kg ile)" if ftp else "Koşu gücü verisi yok (güç sensörlü koşu kaydedin)"

        sleep_win = "Gerçek uyku düzeninizi kaydedin"
        if not self.df.empty and self.df["sleep_start_hr"].notna().any() and self.df["sleep_end_hr"].notna().any():
            sleep_win = f"{fmt_clock(float(self.df['sleep_start_hr'].mean()))} - {fmt_clock(float(self.df['sleep_end_hr'].mean()))} (ortalama gerçek uykunuz)"

        check = "Saatinizdeki mevcut değeri kontrol edin"
        return [
            {"num": 1, "name": "Dinlenik Nabız (RHR)", "current": check, "recommended": f"Otomatik Ortalama (~{int(round(mean_rhr))} bpm)", "reason": f"Gerçek ortalamanız {rhr_str} bpm; yüksek sabit değer VO2 Max ve rezerv nabzı aşağı çeker."},
            {"num": 2, "name": "Koşu Eşik Gücü (FTP)", "current": check, "recommended": ftp_rec, "reason": f"{w_str} kg vücut ağırlığınıza güncellenmediğinde güncel koşu gücünüz saatte düşük görünebilir."},
            {"num": 3, "name": "Koşu Nabız Profili", "current": check, "recommended": "Koşu (RUNNING) Profili Ekle", "reason": "Koşu, yelken, kayak ve ağırlık farklı fizyolojik nabız bölgeleri gerektirir."},
            {"num": 4, "name": "Yoğunluk Dakikası", "current": check, "recommended": "Otomatik (AUTO) Modu", "reason": "Ağırlık ve teknik seanslar nabız Z3 altıysa saatte '0 dk' görünebiliyor."},
            {"num": 5, "name": "Uyku Saatleri", "current": check, "recommended": sleep_win, "reason": "Gerçek uyku başlangıcınıza göre REM uykusu kesintiye uğramadan ölçülmeli."},
            {"num": 6, "name": "İrtifa / Eğim Düzeltmesi", "current": check, "recommended": "İrtifa Düzeltmesi: Açık", "reason": "Koşu ve açık alan eğimlerinde yükseklik kazancı ve yokuş gücü hesaplanır."},
            {"num": 7, "name": "Kilo Girişi", "current": check, "recommended": "Haftada 2 sabah tartımı", "reason": f"Güncel tartım ({w_str} kg) girilmezse VO2 Max (mL/kg/dk) eski kilonuza bölünür."},
            {"num": 8, "name": "Hava / Konum İzni", "current": check, "recommended": "Konum İzni: 'Her Zaman'", "reason": "Isı aklimatizasyonu ve rüzgar direnci hesabı için konum verisi gerekir."},
        ]

    def get_hr_power_zones(self) -> List[Dict[str, Any]]:
        """Canlı vücut ağırlığına göre ölçeklenen HR/LTHR/HRR/Güç zonlarını ve gerçekleşen Z1–Z5 süre dağılımını döner."""
        phys = self.get_physiology()
        max_hr, lthr, rhr, ftp = phys["max_hr"], phys["lthr"], phys["rhr"], phys["ftp_w"]

        run_secs = [0.0] * 5
        all_secs = [0.0] * 5
        acts = getattr(self, "activities_all", []) or []
        min_act_cutoff = self._activity_cutoff()
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
        names = [
            ("Z1", "Zone 1 (Isınma / Toparlanma)"),
            ("Z2", "Zone 2 (Aerobik Taban / Yağ Yakımı)"),
            ("Z3", "Zone 3 (Aerobik Tempo)"),
            ("Z4", "Zone 4 (Laktat Eşiği)"),
            ("Z5", "Zone 5 (Anaerobik / Maks)"),
        ]
        # Yüzde bantları (alt, üst); son bandın üstü maksimum nabızdır. bpm değerleri sporcunun kendi eşiklerinden hesaplanır.
        lthr_now = [(65, 79), (80, 88), (88, 93), (94, 98), (99, None)]
        lthr_rec = [(65, 78), (78, 87), (87, 93), (94, 100), (100, None)]
        hrr_bands = [(50, 60), (60, 70), (70, 80), (80, 90), (90, 100)]
        pwr_bands = [(65, 80), (80, 90), (90, 100), (100, 115), (115, None)]

        def _bpm_range(bands, idx, base, offset=0, ref_max=None):
            lo, hi = bands[idx]
            lo_bpm = int(round(offset + base * lo / 100.0))
            hi_bpm = max_hr if hi is None else int(round(offset + base * hi / 100.0))
            label = f"%{lo}-{hi}" if hi is not None else (f"≥%{lo}" if ref_max == "ge" else f">%{lo}")
            return f"{lo_bpm} - {hi_bpm} bpm ({label})"

        def _power(idx):
            if not ftp:
                return "Güç verisi yok"
            lo, hi = pwr_bands[idx]
            lo_w = int(round(ftp * lo / 100.0))
            if hi is None:
                return f"> {lo_w} W (>%{lo})"
            return f"{lo_w} - {int(round(ftp * hi / 100.0))} W (%{lo}-{hi})"

        hrr = max_hr - rhr
        defs = [
            (
                names[i][0], names[i][1],
                _bpm_range(lthr_now, i, lthr, ref_max="ge"),
                _bpm_range(lthr_rec, i, lthr),
                _bpm_range(hrr_bands, i, hrr, offset=rhr),
                _power(i),
            )
            for i in range(5)
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
