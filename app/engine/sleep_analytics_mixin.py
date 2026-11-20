#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uyku Mimarisi, Korelasyonlar, Ayni Gun Siralama Kesfi, Makro Donemler ve Garmin Saat Ayarlari Mixin'i.
"""

import logging
import math
from typing import Dict, List, Any
import pandas as pd


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

    def get_all_activities(self) -> List[Dict[str, Any]]:
        """Tüm kayıtlı antrenmanların detaylı listesini döner."""
        df_clean = self.adf.where(pd.notnull(self.adf), None)
        return df_clean.to_dict(orient="records")
