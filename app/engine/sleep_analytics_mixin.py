#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyku Mimarisi, Korelasyonlar, Ayni Gun Siralama Kesfi, Makro Donemler ve Garmin Saat Ayarlari Mixin'i.
"""

import logging
import math
from typing import Dict, List, Any
import pandas as pd

try:
    from engine.helpers import fmt_pace_sec, fmt_clock, format_sport_tr
except ImportError:
    from app.engine.helpers import fmt_pace_sec, fmt_clock, format_sport_tr


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
                insight = f"{neg_txt if r_val < 0 else pos_txt}"
            else:
                insight = "Anlamlı bir ilişki saptanmadı."
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

    def get_all_activities(self) -> List[Dict[str, Any]]:
        """Tüm kayıtlı antrenmanların detaylı listesini döner."""
        df_clean = self.adf.where(pd.notnull(self.adf), None)
        return df_clean.to_dict(orient="records")
