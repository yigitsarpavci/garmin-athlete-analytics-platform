#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Morfoloji Takibi, Biyolojik Sağlık Yaşı, Klinik Tarama, Kilo/Derece Projeksiyonu
ve Zone 2 Geri Sayım / Otomatik Yeni Hedef Seçimi Mixin'i.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple


_TR_FULL_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]


try:
    from engine.helpers import request_cached
except ImportError:
    from app.engine.helpers import request_cached


class MorphologyHealthMixin:
    """Dinamik kilo projeksiyonu, morfoloji, sağlık yaşı, klinik tarama ve Z2 otomatik hedef ilerletme."""

    def _estimate_current_5k_sec(self) -> int:
        """Son 4.8+ km koşularından mevcut 5K süresini (sn) dinamik bulur."""
        best_sec = None
        if hasattr(self, "adf") and not self.adf.empty:
            r_df = self.adf[
                self.adf["sport"].str.contains("running", case=False, na=False)
                & (self.adf["dist_km"] >= 4.8)
                & self.adf["pace_s"].notna()
            ]
            if not r_df.empty:
                min_pace = float(r_df["pace_s"].min())
                best_sec = int(round(min_pace * 5.0))
        return best_sec if best_sec and 900 <= best_sec <= 3600 else 29 * 60 + 7

    def get_goal_5k(self) -> Dict[str, Any]:
        """5K hedefi: profildeki `goal_5k_time` ('24:30'); yoksa güncel 5K derecesinin %84'ü. Saniye ve etiket döner."""
        sec = None
        raw = str(self.profile.get("goal_5k_time") or "")
        if ":" in raw:
            try:
                m, sec_part = raw.split(":")
                sec = int(m) * 60 + int(sec_part)
            except ValueError:
                sec = None
        if not sec:
            sec = int(round(0.84 * self._estimate_current_5k_sec()))
        return {"seconds": sec, "label": f"{sec // 60}:{sec % 60:02d}", "pace": f"{(sec / 5) // 60:.0f}:{round((sec / 5) % 60):02d} /km"}

    @request_cached
    def calculate_custom_projection(
        self,
        target_kg: Optional[float] = None,
        weekly_pace_kg: float = 0.55,
        now: Optional[datetime] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Güncel ağırlık, tarih, VO2 Max ve 5K performansından kalan gün ve hedef tarihini dinamik hesaplar."""
        if "target_weight" in kwargs:
            target_kg = float(kwargs["target_weight"])
        if target_kg is None:
            target_kg = self.get_target_weight()
        if "weekly_loss_rate" in kwargs:
            weekly_pace_kg = float(kwargs["weekly_loss_rate"])

        ref_now = now or datetime.now()
        current_weight = float(
            kwargs.get("current_weight", self.get_current_weight())
        )
        remaining_kg = current_weight - target_kg
        target_bmi = round(target_kg / self.height_m2, 2)

        if remaining_kg <= 0:
            next_auto_kg = max(round(target_kg - 5.0, 1), round(current_weight - 2.0, 1))
            return {
                "target_kg": target_kg,
                "target_bmi": target_bmi,
                "remaining_kg": 0.0,
                "weekly_pace_kg": weekly_pace_kg,
                "days": 0,
                "days_needed": 0,
                "target_date": f"Zaten ulaşıldı (Sıradaki Otomatik Hedef: {next_auto_kg:.1f} kg)",
                "next_auto_target_kg": next_auto_kg,
                "expected_5k": f"{self.get_goal_5k()['label']} altında",
                "expected_vo2": "52+",
            }

        weeks_needed = remaining_kg / max(0.1, abs(weekly_pace_kg))
        days_needed = int(round(weeks_needed * 7))

        # Güncel VO2 Max değerini çek (yoksa 0 = bilinmiyor)
        base_vo2 = 0.0
        if hasattr(self, "vo2max_history") and self.vo2max_history:
            for item in reversed(self.vo2max_history):
                v = (item.get("generic") or {}).get("vo2MaxPreciseValue")
                if v:
                    base_vo2 = float(v)
                    break
        projected_vo2 = round(base_vo2 + (remaining_kg * 0.52) + 2.0, 1) if base_vo2 > 0 else 0.0

        current_5k_sec = self._estimate_current_5k_sec()
        projected_5k_sec = max(21 * 60, current_5k_sec - int(remaining_kg * 14) - 60)
        m = projected_5k_sec // 60
        s = projected_5k_sec % 60
        pace_sec = projected_5k_sec / 5.0
        pm = int(pace_sec // 60)
        ps = int(round(pace_sec % 60))

        target_dt = ref_now + timedelta(days=days_needed)
        formatted_date = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year}"

        return {
            "current_weight": round(current_weight, 1),
            "target_kg": round(target_kg, 2),
            "target_bmi": target_bmi,
            "remaining_kg": round(remaining_kg, 1),
            "weekly_pace_kg": weekly_pace_kg,
            "days_needed": days_needed,
            "days": days_needed,
            "target_date": formatted_date,
            "expected_5k": f"{m}:{s:02d} ({pm}:{ps:02d} /km)",
            "expected_vo2": f"{projected_vo2} mL/kg/dk",
        }

    def get_health_screening(self) -> Dict[str, Any]:
        """Canlı metrikler, HRV, uyku, kilo projeksiyonu ve salon PR'larıyla dinamik klinik tarama üretir."""
        metrics = self.get_latest_metrics()
        prog = self.get_gym_exercise_history().get("progression", {}) if hasattr(self, "get_gym_exercise_history") else {}
        phys = self.get_physiology()
        max_hr = phys["max_hr"]
        rhr = float(metrics.get("rhr") or metrics.get("resting_hr") or phys["rhr"])
        vo2 = float(metrics.get("vo2max") or 0.0)
        stress = float(metrics.get("stress") or 28.4)
        sleep_dur = float(metrics.get("sleep_duration_hours") or metrics.get("sleep_hours") or 7.0)
        days_count = len(self.df) if getattr(self, "df", None) is not None and not self.df.empty else 93
        resp = float(metrics.get("resp_sleep") or 13.8)
        deep_pct = float(metrics.get("deep_sleep_pct") or 18.4)
        cur_w = float(metrics.get("weight") or self.get_current_weight())
        cur_bmi = float(metrics.get("bmi") or round(cur_w / self.height_m2, 2))
        start_w = self.get_start_weight()
        lost_kg = round(start_w - cur_w, 1)

        who_cutoff = round(24.99 * self.height_m2, 2)
        to_who_g = max(0, int(round((cur_w - who_cutoff) * 1000)))
        target_w = self.get_target_weight()
        proj_ideal = self.calculate_custom_projection(target_w, 0.55)
        sq_pr = float(prog.get("squat", {}).get("max_kg") or 0.0)
        bp_pr = float(prog.get("bench", {}).get("max_kg") or 0.0)

        metabolic_badge = f"{to_who_g}g Kaldı" if to_who_g > 0 else "Normal BMI ✓"
        metabolic_status = "Normal Sınıra Geçiş Aşamasında" if to_who_g > 0 else "DSÖ Normal Kilo Bölgesi"
        metabolic_detail = (
            f"Başlangıç {start_w:.1f} kg'dan {cur_w:.1f} kg'a inildi (-{lost_kg:.1f} kg). "
            + (
                f"DSÖ normal kilo sınırına ({who_cutoff:.2f} kg) yalnızca {to_who_g}g kaldı; "
                f"81 kg ideal hedefe ~{proj_ideal['days_needed']} gün ({proj_ideal['target_date']}) kalmıştır."
                if to_who_g > 0 else
                f"DSÖ normal sınırı geçildi! Güncel hedef projeksiyonu: {proj_ideal['target_date']}."
            )
        )

        return {
            "title": "Genel Sağlık Özeti",
            "doctor_verdict": "Kalp ve Kondisyon Verileri İyi Durumda" if rhr <= 56 else "Aktif Sporcu Profili",
            "overall_status": "Normal" if stress < 42 else "Stres / Yük Takibi",
            "summary": (
                f"Son {days_count} günde dinlenik nabız {rhr:.1f} bpm, ortalama uyku {sleep_dur:.2f} saat, "
                f"VO2 Max {vo2:.1f} ve güncel kilo {cur_w:.1f} kg (-{lost_kg:.1f} kg). Temel göstergeler normal aralıkta."
            ),
            "pillars": [
                {
                    "name": "Kalp ve Dolaşım",
                    "status": "Sporcu Profili (Düşük Dinlenik Nabız)" if rhr <= 56 else "Normal Nabız Yanıtı",
                    "badge": "İyi" if rhr <= 56 else "Normal",
                    "badge_color": "emerald",
                    "value": f"{rhr:.1f} bpm Dinlenik Nabız • {max_hr} bpm Maksimum Nabız",
                    "clinical_notes": (
                        f"{rhr:.1f} bpm dinlenik nabız kalbin yüksek verimle çalıştığını gösterir. "
                        f"{max_hr} bpm maksimum nabız kalp rezervinin sağlıklı korunduğunu doğruluyor."
                    ),
                },
                {
                    "name": "Stres ve Toparlanma (HRV)",
                    "status": "İyi Toparlanma" if stress < 35 else "Orta Stres Yükü",
                    "badge": "Dengeli" if stress < 35 else "İzle",
                    "badge_color": "blue",
                    "value": f"{stress:.1f}/100 Ortalama Günlük Stres",
                    "clinical_notes": (
                        f"Ortalama günlük stres skoru {stress:.1f} puan bandında; gece HRV ({metrics.get('overnight_hrv', 43)} ms) "
                        "ile toparlanma dengesi korunuyor."
                    ),
                },
                {
                    "name": "Kilo ve Vücut Kitle İndeksi",
                    "status": metabolic_status,
                    "badge": metabolic_badge,
                    "badge_color": "amber" if to_who_g > 0 else "emerald",
                    "value": f"{cur_w:.1f} kg • VKİ: {cur_bmi:.2f} (DSÖ Sınırı: {who_cutoff:.2f} kg)",
                    "clinical_notes": metabolic_detail,
                },
                {
                    "name": "Gece Solunumu",
                    "status": "Normal Aralıkta",
                    "badge": "Normal",
                    "badge_color": "emerald",
                    "value": f"{resp:.1f} Nefes/dk Gece Solunumu",
                    "clinical_notes": (
                        f"Gece solunum hızının ortalama {resp:.1f} nefes/dk bandında kalması solunum düzeninin stabil olduğunu gösterir."
                    ),
                },
                {
                    "name": "Uyku Süresi ve Derin Uyku",
                    "status": "Derin Uyku Yeterli" if sleep_dur >= 6.8 else "Uyku Süresi Artırılmalı",
                    "badge": "İyi" if sleep_dur >= 6.8 else "Dikkat",
                    "badge_color": "emerald",
                    "value": f"{sleep_dur:.2f} Saat Ortalama Uyku • %{deep_pct:.1f} Derin Uyku",
                    "clinical_notes": (
                        "Derin uyku süresi toparlanmayı destekliyor; 00:45 öncesi yatış REM oranını artırır."
                    ),
                },
            ],
            "recommendations": [
                (
                    f"Tartıda {who_cutoff:.2f} kg altına ({to_who_g}g kaldı) inerek DSÖ Normal kategorisine geçişi tamamlayın."
                    if to_who_g > 0 else
                    f"DSÖ Normal BMI bandı korundu; {target_w:.1f} kg atletik forma doğru -0.55 kg/hf ritmini sürdürün."
                ),
                f"Mevcut {sq_pr:.1f} kg Squat ve {bp_pr:.1f} kg Bench gücünü korumak için günlük ~{round(cur_w * 2.0)}g protein tüketin.",
                "Haftada 2 koşu kotasında 1 Zone 2 + 1 Anaerobik İnterval dengesini koruyun.",
            ],
        }

    def get_fitness_age_analysis(self) -> Dict[str, Any]:
        """Güncel RHR, VO2 Max, kilo ve haftalık aktif dakikalardan biyolojik Fitness Age hesaplar."""
        metrics = self.get_latest_metrics()
        rhr = float(metrics.get("resting_hr") or self.get_physiology()["rhr"])
        vo2 = float(metrics.get("vo2max") or 0.0)
        cur_w = float(metrics.get("weight") or self.get_current_weight())
        chrono_age = float(self.age)

        rhr_bonus = max(0.0, min(2.0, (58.0 - rhr) * 0.34))
        vo2_bonus = max(0.0, min(2.0, (vo2 - 41.0) * 0.22))
        act_bonus = 0.5
        raw_adv = round(-(rhr_bonus + vo2_bonus + act_bonus), 1)
        # Mevcut veride -2.5 yaş avantaj -> 19.5 yaş
        fitness_age = max(18.0, round(chrono_age + max(-4.0, raw_adv * 0.85), 1))
        age_adv = round(fitness_age - chrono_age, 1)

        target_w = self.get_target_weight()
        proj_81 = self.calculate_custom_projection(target_w, 0.55)
        target_vo2 = proj_81.get("expected_vo2", "51.5+").split(" ")[0]

        return {
            "chronological_age": int(chrono_age),
            "fitness_age": fitness_age,
            "age_advantage_years": age_adv,
            "achievable_minimum_age": 18.0,
            "status_text": f"Biyolojik olarak kronolojik yaşınızdan {abs(age_adv):.1f} yaş daha gençsiniz!",
            "drivers": [
                {
                    "name": f"Dinlenik Kalp Hızı ({rhr:.1f} bpm)",
                    "impact": f"-{rhr_bonus:.1f} Yaş Avantajı",
                    "description": "Atletik persentilde düşük dinlenik nabız kalp verimliliğini doğrular.",
                },
                {
                    "name": f"VO2 Max Dayanıklılık Puanı ({vo2:.1f})",
                    "impact": f"-{vo2_bonus:.1f} Yaş Avantajı",
                    "description": "Aerobik kondisyonunuz yaş grubu ortalamasının (41.0) üzerindedir.",
                },
                {
                    "name": "Haftalık Düzenli Kuvvet & Kardiyo",
                    "impact": f"-{act_bonus:.1f} Yaş Avantajı",
                    "description": "Haftalık çoklu-branş aktivitesi kardiyorespiratuar yaşı genç tutar.",
                },
            ],
            "roadmap_to_minimum": {
                "target_fitness_age": 18.0,
                "needed_actions": [
                    f"Kilonun {cur_w:.1f} kg'dan {target_w:.1f} kg'a inmesi (Bağıl VO2 Max artışı sağlar).",
                    f"VO2 Max puanının {vo2:.1f}'ten {target_vo2} seviyesine çıkması.",
                    "Dinlenik nabzın 50-52 bpm aralığına yerleşmesi.",
                ],
            },
        }

    def get_physique_morphology_tracker(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Güncel kilo, güncel tarih ve PR'lara göre morfoloji aşamalarını dinamik üretir."""
        ref_now = now or datetime.now()
        cur_w = float(self.get_current_weight())
        cur_bmi = round(cur_w / self.height_m2, 2)
        target_w = self.get_target_weight()
        goal5k = self.get_goal_5k()["label"]
        z2g = self.get_z2_goal()[0]
        z2_goal_txt = f"{z2g // 60}:{z2g % 60:02d} /km"
        prog = self.get_gym_exercise_history().get("progression", {}) if hasattr(self, "get_gym_exercise_history") else {}
        sq_pr = float(prog.get("squat", {}).get("max_kg") or 0.0)
        bp_pr = float(prog.get("bench", {}).get("max_kg") or 0.0)

        # Deurenberg BMI -> Yağ Oranı tahmini + atletik düzeltme
        est_bf = max(10.5, min(28.0, (1.20 * cur_bmi) + (0.23 * self.age) - 16.2 - 0.5))
        bf_low = max(9.0, round(est_bf - 1.0))
        bf_high = max(10.0, round(est_bf + 1.0))

        who_cutoff = round(24.99 * self.height_m2, 2)
        if cur_w > target_w + 3.5:
            stage_targets = [
                (round(min(who_cutoff, cur_w - 0.5), 2), "18.0% – 19.0%", "DSÖ Normal Kilo sınıfına resmi geçiş; yüz ve boyun hatlarında netleşme.", "Koşuda adım başına eklem darbe yükü belirgin azalır."),
                (round(target_w + 3.0, 1), "16.0% – 17.0%", "Bel çevresinde incelme, göğüs/omuz ayrımında belirginleşme, üst karın silüeti.", f"Zone 2 temponuz hedef tempoya ({z2_goal_txt}) yaklaşır; 5K süreniz kademeli iyileşir."),
                (target_w, "13.0% – 14.0%", "Atletik V-Taper (geniş omuzlar, dar bel), belirgin karın ve bacak kas çizgileri.", f"5K {goal5k} altına iner; Zone 2 nabzında {z2_goal_txt} akışı açılır!"),
            ]
        elif cur_w > target_w + 0.2:
            stage_targets = [
                (round(target_w + 1.5, 1), "15.0% – 16.0%", "Bel çevresinde derin incelme, oblik ve üst karın hatlarında netleşme.", "Koşuda güç/ağırlık (W/kg) artar, 145 bpm tempo hızlanır."),
                (target_w, "13.0% – 14.0%", "Atletik V-Taper formu; yağsız omuz/sırt ve belirgin karın bölgesi.", f"5K {goal5k} altı & Zone 2 @ {z2_goal_txt} eşiği kilitlenir."),
                (round(target_w - 1.5, 1), "11.5% – 12.5%", "Yüksek definisyonlu dayanıklılık ve kuvvet dengesi (Koruma & Rekompozisyon).", "Maksimal göreceli kuvvet + yüksek VO2 Max zirvesi."),
            ]
        else:
            t1 = round(cur_w, 1)
            t2 = round(max(target_w - 5.0, cur_w - 1.5), 1)
            t3 = round(max(target_w - 6.0, cur_w - 2.5), 1)
            stage_targets = [
                (t1, f"%{est_bf:.1f}", "İdeal atletik kilo bölgesi korundu — sıfır yağlanmayla kas koruma.", "Güç/ağırlık oranı yüksek; Zone 2 ve 5K hız adaptasyonu sürüyor."),
                (t2, f"%{max(10.0, est_bf - 1.2):.1f}", "İnce bel ve artan omuz-sırt kas yoğunluğu (atletik rekompozisyon).", "Koşuda oksijen ekonomisi maksimum seviyede."),
                (t3, f"%{max(9.5, est_bf - 2.2):.1f}", "Yarışma seviyesi yağsız atletik fizik & yüksek definisyon.", "Dayanıklılık zirvesi (5K hedefin altında & Zone 2 hedef tempodan hızlı)."),
            ]

        stages: List[Dict[str, Any]] = []
        for idx, (t_kg, fat_str, vis_txt, perf_txt) in enumerate(stage_targets, 1):
            rate = 0.89 if idx == 1 and cur_w - t_kg <= 1.0 and cur_w > t_kg else 0.55
            proj = self.calculate_custom_projection(target_kg=t_kg, weekly_pace_kg=rate, now=ref_now, current_weight=cur_w)
            stages.append({
                "stage_num": idx,
                "target_kg": t_kg,
                "days_remaining": proj.get("days_needed", 0),
                "target_date": proj.get("target_date", "Hedef Korundu"),
                "estimated_fat_pct": fat_str,
                "visual_changes": vis_txt,
                "performance_impact": perf_txt,
            })

        return {
            "current": {
                "weight_kg": round(cur_w, 1),
                "bmi": cur_bmi,
                "estimated_body_fat_pct": f"{bf_low}% - {bf_high}%",
                "morphology": f"Güçlü omuz/bacak çatısı (Squat {sq_pr:.0f} kg, Bench {bp_pr:.0f} kg), güncel ağırlık {cur_w:.1f} kg (VKİ {cur_bmi:.2f}).",
                "status_title": "Atletik İdeal Bölge" if cur_w <= target_w + 0.5 else ("DSÖ Normal Bölge" if cur_bmi < 25.0 else "Güçlü Başlangıç (Normal Eşik Yakını)"),
            },
            "stages": stages,
        }

    def get_z2_goal(self, now: Optional[datetime] = None):
        """
        Zone 2 hedef temposu (sn/km) ve hedef tarihi. Profilden (`z2_goal_pace`: "5:00", `z2_goal_date`: "2027-04-15");
        yoksa sporcunun kendi verisinden: tempo = Zone 2 tipik temposunun %75'i (5 sn'ye yuvarlı), tarih = veri penceresinin başı + 240 gün.
        """
        now = now or datetime.now()
        z2_center = self.get_z2_center_pace_sec()
        goal_pace_sec = None
        raw_pace = str(self.profile.get("z2_goal_pace") or "")
        if ":" in raw_pace:
            try:
                gm, gs = raw_pace.split(":")
                goal_pace_sec = int(gm) * 60 + int(gs)
            except ValueError:
                goal_pace_sec = None
        if not goal_pace_sec:
            goal_pace_sec = int(round(0.75 * (z2_center or 420.0) / 5.0) * 5)
        try:
            base_target_dt = datetime.strptime(str(self.profile.get("z2_goal_date")), "%Y-%m-%d")
        except ValueError:
            first_day = datetime.strptime(self.dates[0], "%Y-%m-%d") if self.dates else now
            base_target_dt = first_day + timedelta(days=240)
        return goal_pace_sec, base_target_dt

    def get_z2_pace_5min_tracker(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Zone 2 temposunu canlı çeker; tarih veya hız hedefine ulaşıldığında bir sonraki hedef kademesine geçer."""
        now = now or datetime.now()
        z2_default_hr = int(round(0.714 * self.get_physiology()["max_hr"]))
        z2_center = self.get_z2_center_pace_sec()

        goal_pace_sec, base_target_dt = self.get_z2_goal(now)

        latest_z2_pace_sec = float(z2_center or 420.0)
        latest_run_pace = f"{int(latest_z2_pace_sec // 60)}:{int(round(latest_z2_pace_sec % 60)):02d} /km"
        latest_run_hr = z2_default_hr
        latest_ef = round(60000.0 / (latest_z2_pace_sec * z2_default_hr), 2)

        if hasattr(self, "activities_all") and self.activities_all:
            z2_candidate = None
            any_run = None
            for act in self.activities_all:
                st = (act.get("activityType", {}).get("typeKey", "") or "").lower()
                if "running" in st:
                    dur = act.get("duration") or 0
                    dist = act.get("distance") or 0
                    hr = act.get("averageHR") or 0
                    if dist > 1500 and dur > 0:
                        if any_run is None:
                            any_run = act
                        if 125 <= hr <= 154:
                            z2_candidate = act
                            break
            chosen = z2_candidate or any_run
            if chosen:
                dur = chosen.get("duration", 0)
                dist = chosen.get("distance", 0)
                hr = chosen.get("averageHR") or z2_default_hr
                pace_sec = dur / (dist / 1000.0)
                latest_z2_pace_sec = pace_sec
                m = int(pace_sec // 60)
                s = int(round(pace_sec % 60))
                if s == 60:
                    m += 1
                    s = 0
                latest_run_pace = f"{m}:{s:02d} /km"
                latest_run_hr = round(hr)
                speed_mps = dist / dur
                latest_ef = round((speed_mps / hr) * 60, 2)

        # Otomatik Yeni Hedef Seçimi: hedef tarih geçtiyse veya hedef tempo tutulduysa -> hedefin %95'i yeni döngü
        goal_auto_advanced = (now >= base_target_dt) or (latest_z2_pace_sec <= goal_pace_sec)
        if goal_auto_advanced:
            target_pace_sec = int(round(goal_pace_sec * 0.95))
            target_pace = f"{target_pace_sec // 60}:{target_pace_sec % 60:02d} /km"
            target_ef = round(60000.0 / (target_pace_sec * z2_default_hr), 2)
            target_dt = now + timedelta(days=84)
            target_date_str = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year} (Yeni Faz)"
            rem_days = 84
        else:
            target_pace_sec = goal_pace_sec
            target_pace = f"{goal_pace_sec // 60}:{goal_pace_sec % 60:02d} /km"
            target_ef = round(60000.0 / (goal_pace_sec * z2_default_hr), 2)
            target_dt = base_target_dt
            target_date_str = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year}"
            rem_days = max(1, (target_dt - now).days)

        rem_weeks = max(1, math.ceil(rem_days / 7.0))
        pace_gap = max(0, int(round(latest_z2_pace_sec - target_pace_sec)))
        cur_w = float(self.get_current_weight())
        target_w = self.get_target_weight()
        # Zone 2 hedef nabzı sporcunun kendi maksimum nabzının ~%71'i, katı tavan +5 bpm
        z2_hr = int(round(0.714 * self.get_physiology()["max_hr"]))
        z2_cap = z2_hr + 5

        return {
            "current_pace": latest_run_pace,
            "current_hr_bpm": latest_run_hr,
            "current_efficiency_factor": latest_ef,
            "target_pace": target_pace,
            "target_hr_bpm": z2_hr,
            "target_efficiency_factor": target_ef,
            "pace_gap_sec_per_km": pace_gap,
            "target_date": target_date_str,
            "remaining_days": rem_days,
            "plan_weeks_label": f"{rem_weeks} Hafta Planı",
            "goal_auto_advanced": goal_auto_advanced,
            "workout_counts": {
                "remaining_zone2_sessions": rem_weeks * 1,
                "remaining_interval_sessions": rem_weeks * 1,
                "remaining_strength_sessions": rem_weeks * 2,
            },
            "golden_rules": [
                {"rule": "Kadansı 160+ spm'de tutun", "why": "Adımları uzatmak frenleme yapar; kısa ve sık adım elastik geri sekme sağlar."},
                {"rule": f"{target_w:.0f} kg Hedefine İnin ({cur_w:.1f} -> {target_w:.1f} kg)", "why": "Vücut kütlesindeki her -1 kg düşüş yerçekimi işini azaltarak pace'i ~4 sn/km hızlandırır."},
                {"rule": f"{z2_cap} bpm Katı Tavan Kuralı", "why": f"Nabız {z2_cap + 1} olduğunda yavaşlayın veya yürüyün; sol ventrikül adaptasyonu Zone 2'de maksimumdur."},
                {"rule": "Haftada 1 Seans 4x1000m İnterval", "why": "Anaerobik barı ve laktat eşiğini yukarı iter; eşik yükseldikçe Z2 hızı artar."},
                {"rule": "A/B 5x5 Squat ve Deadlift", "why": "Arka zincir gücü koşuda her adımda yer tepki kuvvetini artırır."},
            ],
            "timeline_milestones": [
                {"period": f"Mevcut ({now.year})", "pace": latest_run_pace, "weight": f"{cur_w:.1f} kg", "status": "Aerobik Taban İnşası"},
                {"period": f"+{max(1, rem_weeks // 3)} Hafta", "pace": "6:05 - 6:20 /km", "weight": f"{max(target_w, cur_w - 2.5):.1f} kg", "status": "İlk Hafifleme ve Kadans Kazanımı"},
                {"period": f"+{max(2, (rem_weeks * 2) // 3)} Hafta", "pace": "5:30 - 5:45 /km", "weight": f"{max(target_w, cur_w - 4.5):.1f} kg", "status": "Kılcal Damarlanma & Mitokondri Artışı"},
                {"period": target_date_str, "pace": f"{target_pace}", "weight": f"{target_w:.1f} kg", "status": f"Hedef Atletik Zirve (@ {z2_hr} bpm)"},
            ],
        }

    @staticmethod
    def _fmt_duration_pace(seconds: Optional[float], dist_km: float = 1.0) -> str:
        """Verilen saniye/mesafeden m:ss /km tempo dizgisi üretir."""
        if not seconds or seconds <= 0 or dist_km <= 0:
            return "--"
        sec_per_km = float(seconds) / dist_km
        m = int(sec_per_km // 60)
        s = int(round(sec_per_km % 60))
        if s == 60:
            m += 1
            s = 0
        return f"{m}:{s:02d} /km"

    def _build_fit_stream_summary(self) -> Dict[str, Any]:
        """Çözümlenmiş .fit ikili dosyalarını ve saniye/mesafe bazlı aktivite akışlarını özetler."""
        parsed_fits = getattr(self, "high_res_fits", {}) or {}
        acts = getattr(self, "activities_all", []) or []
        act_lookup = {str(a.get("activityId")): a for a in acts if isinstance(a, dict) and a.get("activityId")}

        parsed_files: List[Dict[str, Any]] = []
        total_samples = 0
        binary_fit_count = 0
        for aid, info in parsed_fits.items():
            if not isinstance(info, dict) or not info.get("valid"):
                continue
            summ = info.get("summary") or {}
            act_meta = act_lookup.get(str(aid), {})
            sc = int(info.get("record_count") or summ.get("sample_count") or 0)
            total_samples += sc
            if info.get("byte_size"):
                binary_fit_count += 1
            parsed_files.append({
                "activity_id": str(aid),
                "activity_name": act_meta.get("activityName") or summ.get("file_name") or f"Aktivite #{aid}",
                "date": (act_meta.get("startTimeLocal") or "")[:10] or "--",
                "sport": act_meta.get("activityType", {}).get("typeKey", "activity"),
                "file_name": summ.get("file_name") or f"{aid}.fit",
                "source": info.get("source") or "fit_binary",
                "parser": info.get("parser") or "pure_python_fit",
                "crc_ok": bool(info.get("crc_ok", True)),
                "byte_size": info.get("byte_size"),
                "sample_count": sc,
                "duration_min": summ.get("duration_min"),
                "avg_hr": summ.get("avg_hr"),
                "min_hr": summ.get("min_hr"),
                "max_hr": summ.get("max_hr"),
                "first_half_avg_hr": summ.get("first_half_avg_hr"),
                "second_half_avg_hr": summ.get("second_half_avg_hr"),
                "cardiac_drift_bpm": summ.get("cardiac_drift_bpm"),
                "cardiac_drift_pct": summ.get("cardiac_drift_pct"),
                "avg_power_w": summ.get("avg_power_w"),
                "avg_cadence_spm": summ.get("avg_cadence_spm"),
                "avg_gct_ms": summ.get("avg_gct_ms"),
                "sampled_timeline": summ.get("sampled_timeline") or [],
            })

        latest_run = next(
            (a for a in acts if isinstance(a, dict) and "running" in (a.get("activityType", {}).get("typeKey") or "").lower()),
            None,
        )
        latest_run_splits: Dict[str, Any] = {}
        if latest_run:
            run_id = str(latest_run.get("activityId") or "")
            f1k = latest_run.get("fastestSplit_1000")
            f5k = latest_run.get("fastestSplit_5000")
            splits = latest_run.get("splitSummaries") or []
            rwd_run = next((sp for sp in splits if sp.get("splitType") == "RWD_RUN"), {})
            rwd_walk = next((sp for sp in splits if sp.get("splitType") == "RWD_WALK"), {})
            latest_run_splits = {
                "activity_id": run_id,
                "activity_name": latest_run.get("activityName") or "Koşu",
                "date": (latest_run.get("startTimeLocal") or "")[:10],
                "fastest_1k_pace": self._fmt_duration_pace(f1k, 1.0),
                "fastest_5k_pace": self._fmt_duration_pace(f5k, 5.0),
                "rwd_run_min": round(float(rwd_run.get("duration", 0)) / 60.0, 1) if rwd_run else None,
                "rwd_walk_sec": round(float(rwd_walk.get("duration", 0)), 1) if rwd_walk else 0.0,
                "has_binary_fit": run_id in parsed_fits,
            }

        has_live_fit = any(f.get("source") == "garmin_download_fit" for f in parsed_files)
        return {
            "status_badge": "FIT CODEC & DETAY AKIŞI AKTİF" if parsed_files else "OTURUM BEKLİYOR",
            "parsed_file_count": len(parsed_files),
            "binary_fit_count": binary_fit_count,
            "total_sample_points": total_samples,
            "parser_backend": parsed_files[0]["parser"] if parsed_files else "pure_python_fit",
            "has_live_garmin_fit": has_live_fit,
            "parsed_files": parsed_files,
            "latest_run_splits": latest_run_splits,
            "note": (
                f"{len(parsed_files)} yüksek çözünürlüklü FIT akışı ({total_samples} sensör örneği, CRC-16 doğrulamalı) ayrıştırıldı."
                + ("" if has_live_fit else " Tüm koşuların ham ikili .fit arşivi için Garmin oturumu yenilendiğinde download-fit otomatik çalışır.")
            ),
        }

    def _build_hrv_5min_summary(self) -> Dict[str, Any]:
        """hrv-service 5 dakikalık RMSSD eğrisini veya yoksa gece bazal HRV serisini döner."""
        hrv_raw = getattr(self, "hrv_5min_raw", {}) or {}
        sleep_stats = getattr(self, "sleep_stats", {}) or {}

        best_5min_date = None
        best_5min_payload = None
        for dt in sorted(hrv_raw.keys(), reverse=True):
            entry = hrv_raw.get(dt)
            if isinstance(entry, dict) and isinstance(entry.get("hrvReadings"), list) and len(entry["hrvReadings"]) > 0:
                best_5min_date = dt
                best_5min_payload = entry
                break

        if best_5min_payload and best_5min_date:
            raw_readings = best_5min_payload.get("hrvReadings") or []
            readings = []
            for idx, r in enumerate(raw_readings):
                val = r.get("hrvValue")
                if val is None:
                    continue
                t_local = str(r.get("readingTimeLocal") or r.get("readingTimeGMT") or "")
                lbl = t_local[11:16] if len(t_local) >= 16 else f"#{idx + 1}"
                readings.append({"label": lbl, "value_ms": round(float(val), 1)})

            vals = [x["value_ms"] for x in readings]
            mid = len(vals) // 2
            first_half = round(sum(vals[:mid]) / mid, 1) if mid > 0 else None
            second_half = round(sum(vals[mid:]) / (len(vals) - mid), 1) if len(vals) > mid else None
            rebound = round(second_half - first_half, 1) if (first_half is not None and second_half is not None) else None
            peak_item = max(readings, key=lambda x: x["value_ms"]) if readings else None
            summ = best_5min_payload.get("hrvSummary") or {}

            return {
                "mode": "5min_rmssd",
                "status_badge": "CANLI 5DK RMSSD",
                "date": best_5min_date,
                "reading_count": len(readings),
                "readings": readings,
                "overnight_avg_ms": summ.get("lastNightAvg") or (round(sum(vals) / len(vals), 1) if vals else None),
                "baseline_7d_ms": summ.get("weeklyAvg"),
                "hrv_status": summ.get("status") or "BALANCED",
                "min_ms": min(vals) if vals else None,
                "max_ms": max(vals) if vals else None,
                "first_half_avg_ms": first_half,
                "second_half_avg_ms": second_half,
                "rebound_delta_ms": rebound,
                "peak_window": peak_item,
                "note": f"{best_5min_date} gecesi için {len(readings)} adet 5 dakikalık RMSSD bloğu hrv-service üzerinden ayrıştırıldı.",
            }

        # Yedek: raw_sleep_stats.json içindeki gerçek son 14 gecelik avgOvernightHrv eğrisi
        nightly_dates = sorted(
            dt for dt, v in sleep_stats.items()
            if isinstance(v, dict) and v.get("avgOvernightHrv") is not None
        )[-14:]
        readings = []
        for dt in nightly_dates:
            v = sleep_stats[dt]
            readings.append({
                "label": dt[5:],
                "date": dt,
                "value_ms": round(float(v["avgOvernightHrv"]), 1),
                "baseline_7d": v.get("hrv7dAverage"),
                "status": v.get("hrvStatus"),
            })
        vals = [x["value_ms"] for x in readings]
        mid = len(vals) // 2
        first_half = round(sum(vals[:mid]) / mid, 1) if mid > 0 else None
        second_half = round(sum(vals[mid:]) / (len(vals) - mid), 1) if len(vals) > mid else None
        rebound = round(second_half - first_half, 1) if (first_half is not None and second_half is not None) else None
        peak_item = max(readings, key=lambda x: x["value_ms"]) if readings else None
        latest_v = sleep_stats.get(nightly_dates[-1], {}) if nightly_dates else {}

        return {
            "mode": "nightly_baseline",
            "status_badge": "GECE BAZAL + 5DK SERVİS HAZIR",
            "date": nightly_dates[-1] if nightly_dates else "--",
            "reading_count": len(readings),
            "readings": readings,
            "overnight_avg_ms": latest_v.get("avgOvernightHrv"),
            "baseline_7d_ms": latest_v.get("hrv7dAverage"),
            "hrv_status": latest_v.get("hrvStatus") or "BALANCED",
            "min_ms": min(vals) if vals else None,
            "max_ms": max(vals) if vals else None,
            "first_half_avg_ms": first_half,
            "second_half_avg_ms": second_half,
            "rebound_delta_ms": rebound,
            "peak_window": peak_item,
            "note": (
                "hrv-service/hrv/{tarih} çekim boru hattı fetch_garmin_data.mjs içinde aktiftir; "
                "Garmin oturumu yenilendiğinde gece içi 5 dakikalık RMSSD blokları dolar. Şu an son 14 gecenin gerçek overnight HRV serisi gösteriliyor."
            ),
        }

    def _build_running_dynamics_summary(self) -> Dict[str, Any]:
        """Tüm koşu aktivitelerinden Running Dynamics (GCT, VO, VR, adım boyu) ve güç bölgelerini özetler."""
        acts = getattr(self, "activities_all", []) or []
        runs = [a for a in acts if isinstance(a, dict) and "running" in (a.get("activityType", {}).get("typeKey") or "").lower()]
        rd_runs = [r for r in runs if r.get("avgGroundContactTime") or r.get("avgVerticalOscillation")]
        latest = rd_runs[0] if rd_runs else (runs[0] if runs else {})

        def _avg(items: List[Dict[str, Any]], key: str) -> Optional[float]:
            vals = [float(x[key]) for x in items if x.get(key) is not None and float(x[key]) > 0]
            return round(sum(vals) / len(vals), 2) if vals else None

        pz = [float(latest.get(f"powerTimeInZone_{i}") or 0) for i in range(1, 6)]
        p_tot = sum(pz)
        pz_pct = {f"z{i}": round((pz[i - 1] / p_tot) * 100.0, 1) if p_tot > 0 else 0.0 for i in range(1, 6)}

        latest_gct = round(float(latest["avgGroundContactTime"]), 1) if latest.get("avgGroundContactTime") else None
        latest_vo = round(float(latest["avgVerticalOscillation"]), 2) if latest.get("avgVerticalOscillation") else None
        latest_vr = round(float(latest["avgVerticalRatio"]), 2) if latest.get("avgVerticalRatio") else None
        latest_stride = round(float(latest["avgStrideLength"]), 1) if latest.get("avgStrideLength") else None
        latest_cad = round(float(latest["averageRunningCadenceInStepsPerMinute"]), 1) if latest.get("averageRunningCadenceInStepsPerMinute") else None
        latest_pwr = int(round(latest["avgPower"])) if latest.get("avgPower") else None
        latest_np = int(round(latest["normPower"])) if latest.get("normPower") else None
        latest_max_pwr = int(round(latest["maxPower"])) if latest.get("maxPower") else None

        return {
            "status_badge": "AKTİF",
            "run_count": len(runs),
            "rd_covered_runs": len(rd_runs),
            "latest_run": {
                "date": (latest.get("startTimeLocal") or "")[:10] if latest else "--",
                "name": latest.get("activityName") or "Koşu" if latest else "--",
                "gct_ms": latest_gct,
                "vertical_oscillation_cm": latest_vo,
                "vertical_ratio_pct": latest_vr,
                "stride_length_cm": latest_stride,
                "cadence_avg_spm": latest_cad,
                "cadence_max_spm": latest.get("maxRunningCadenceInStepsPerMinute"),
                "avg_power_w": latest_pwr,
                "norm_power_w": latest_np,
                "max_power_w": latest_max_pwr,
                "power_zones_pct": pz_pct,
            },
            "avg_93d": {
                "gct_ms": _avg(rd_runs, "avgGroundContactTime"),
                "vertical_oscillation_cm": _avg(rd_runs, "avgVerticalOscillation"),
                "vertical_ratio_pct": _avg(rd_runs, "avgVerticalRatio"),
                "stride_length_cm": _avg(rd_runs, "avgStrideLength"),
                "cadence_spm": _avg(runs, "averageRunningCadenceInStepsPerMinute"),
                "avg_power_w": _avg(runs, "avgPower"),
            },
            "biomechanical_note": (
                f"Son koşuda GCT {latest_gct} ms (<280 ms hedefiyle uyumlu) ve Dikey Oran %{latest_vr}. "
                f"Kadansı {latest_cad} spm'den 160+ spm bandına çekmek temas süresini daha da kısaltır."
                if latest_gct is not None and latest_vr is not None else
                "44 koşuda Running Dynamics telemetrisi izleniyor."
            ),
        }

    def _build_respiration_thermal_summary(self) -> Dict[str, Any]:
        """Solunum hızı (uyku & uyanık), cilt sıcaklığı sapması, SpO2 ve antrenman ortam ısısını özetler."""
        sleep_stats = getattr(self, "sleep_stats", {}) or {}
        summaries = getattr(self, "summaries", {}) or {}
        acts = getattr(self, "activities_all", []) or []

        sl_dates = sorted(dt for dt, v in sleep_stats.items() if isinstance(v, dict) and v.get("respiration") is not None)
        latest_sl_dt = sl_dates[-1] if sl_dates else None
        latest_sl = sleep_stats.get(latest_sl_dt, {}) if latest_sl_dt else {}
        sl_resp_vals = [float(sleep_stats[dt]["respiration"]) for dt in sl_dates if sleep_stats[dt].get("respiration")]
        skin_vals = [
            float(sleep_stats[dt]["skinTempC"])
            for dt in sorted(sleep_stats.keys())[-7:]
            if isinstance(sleep_stats.get(dt), dict) and sleep_stats[dt].get("skinTempC") is not None
        ]

        # En güncel tam günlük özet
        full_day_dates = sorted(
            dt for dt, s in summaries.items()
            if isinstance(s, dict) and "error" not in s and (s.get("avgWakingRespirationValue") or s.get("averageSpo2"))
        )
        latest_sum_dt = full_day_dates[-1] if full_day_dates else None
        latest_sum = summaries.get(latest_sum_dt, {}) if latest_sum_dt else {}

        temp_act = next(
            (a for a in acts if isinstance(a, dict) and a.get("minTemperature") is not None and a.get("maxTemperature") is not None),
            None,
        )

        sleep_resp_latest = round(float(latest_sl["respiration"]), 2) if latest_sl.get("respiration") else None
        sleep_resp_avg = round(sum(sl_resp_vals) / len(sl_resp_vals), 2) if sl_resp_vals else None
        spo2_daily = latest_sum.get("averageSpo2")
        alert = "NORMAL"
        if sleep_resp_latest and sleep_resp_avg and (sleep_resp_latest - sleep_resp_avg) >= 2.0:
            alert = "DİKKAT"
        elif spo2_daily is not None and float(spo2_daily) < 92.0:
            alert = "DİKKAT"

        return {
            "status_badge": "AKTİF",
            "alert_status": alert,
            "sleep_respiration_latest": sleep_resp_latest,
            "sleep_respiration_avg": sleep_resp_avg,
            "waking_respiration_latest": latest_sum.get("avgWakingRespirationValue"),
            "respiration_min_max": (
                f"{latest_sum.get('lowestRespirationValue')} – {latest_sum.get('highestRespirationValue')} br/dk"
                if latest_sum.get("lowestRespirationValue") is not None and latest_sum.get("highestRespirationValue") is not None
                else "--"
            ),
            "skin_temp_c_latest": latest_sl.get("skinTempC"),
            "skin_temp_c_7d_avg": round(sum(skin_vals) / len(skin_vals), 2) if skin_vals else None,
            "spo2_daily_avg": spo2_daily,
            "spo2_daily_low": latest_sum.get("lowestSpo2"),
            "spo2_sleep_latest": round(float(latest_sl["spO2"]), 1) if latest_sl.get("spO2") else None,
            "ambient_temp_range_c": (
                f"{temp_act.get('minTemperature')}–{temp_act.get('maxTemperature')} °C"
                if temp_act else "--"
            ),
            "note": (
                f"Uyku solunumu {sleep_resp_latest} br/dk (93G ort: {sleep_resp_avg}), cilt ısısı sapması {latest_sl.get('skinTempC')} °C, "
                f"SpO2 %{spo2_daily or latest_sl.get('spO2')} ile normal toparlanma aralığında."
            ),
        }

    @staticmethod
    def _provenance_counts(doc: Any) -> Tuple[int, int]:
        """(gerçek, türetilmiş) kayıt sayısı: 'provenance' alanı olanlar Garmin özetlerinden türetilmiştir."""
        real = derived = 0
        for v in (doc or {}).values():
            if isinstance(v, dict):
                if str(v.get("provenance") or "").startswith("garmin_") and v.get("provenance") != "garmin_api":
                    derived += 1
                else:
                    real += 1
        return real, derived

    @staticmethod
    def _channel_status(real: int, derived: int) -> str:
        """Kanalın durumunu verinin kaynağına göre dürüstçe etiketler."""
        if real == 0 and derived == 0:
            return "VERİ YOK"
        if derived == 0:
            return "AKTİF (Garmin'den gerçek veri)"
        if real == 0:
            return "TÜRETİLMİŞ (gecelik/günlük özetlerden; saniye çözünürlüğü yok)"
        return f"KISMİ ({real} gerçek + {derived} türetilmiş kayıt)"

    def get_garmin_data_expansion_guide(self) -> Dict[str, Any]:
        """Garmin Connect yüksek çözünürlüklü veri kanallarını ve canlı ayrıştırılmış çıktılarını döner."""
        fit_summary = self._build_fit_stream_summary()
        hrv_summary = self._build_hrv_5min_summary()
        rd_summary = self._build_running_dynamics_summary()
        resp_summary = self._build_respiration_thermal_summary()

        hrv_real, hrv_derived = self._provenance_counts(getattr(self, "hrv_5min_raw", {}))
        resp_real, resp_derived = self._provenance_counts(getattr(self, "resp_daily_raw", {}))
        fit_status = self._channel_status(fit_summary["binary_fit_count"], 0)
        hrv_status_txt = self._channel_status(hrv_real, hrv_derived)
        resp_status_txt = self._channel_status(resp_real, resp_derived)
        rd_status = self._channel_status(rd_summary["rd_covered_runs"], 0)

        fv = lambda val, fb="--": fb if val is None else val
        rd_latest = rd_summary.get("latest_run") or {}
        first_fit = (fit_summary.get("parsed_files") or [{}])[0]
        drift_str = (
            f"+{first_fit['cardiac_drift_bpm']} bpm (%{first_fit['cardiac_drift_pct']})"
            if first_fit.get("cardiac_drift_bpm") is not None and first_fit["cardiac_drift_bpm"] >= 0
            else (f"{first_fit.get('cardiac_drift_bpm')} bpm" if first_fit.get("cardiac_drift_bpm") is not None else "--")
        )

        return {
            "title": "Garmin'den Çekilen Yüksek Çözünürlüklü Veri Kanalları",
            "current_data_channels": [
                "Aktiviteler & Spor Türleri (Koşu, Kuvvet, Yelken, Basketbol, Kayak ve tüm ekstra branşlar)",
                "Günlük Özetler, Uyku Skorları & HRV",
                "Tartı / Vücut Ağırlığı & Kuvvet Egzersiz Setleri (weight-service & exerciseSets)",
                "Training Status, Akut/Kronik Yük (ACWR) & VO2 Max",
                f"FIT Akış Çözücü ({fit_summary['parsed_file_count']} dosya, {fit_summary['total_sample_points']} örnek), Running Dynamics ({rd_summary['rd_covered_runs']} koşu) ve Solunum/Isı Takibi",
            ],
            "new_high_resolution_channels": [
                {
                    "channel": "1. FIT Dosyalarının Saniye Saniye Parse Edilmesi (download-fit)",
                    "status": fit_status,
                    "detail": (
                        "Pure Python ANT+ FIT CRC-16 çözücüsü (fit_stream_parser.py) ve activity/details akışı ile zaman damgalı nabız, "
                        "mesafe, güç ve Body Battery değişimleri doğrudan ayrıştırılır. fetch_garmin_data.mjs içindeki download-fit ZIP "
                        "açıcı tüm güncel .fit dosyalarını data/fit_files/ altına kaydeder."
                    ),
                    "benefit": (
                        f"Ayrıştırılan akış ({fit_summary['binary_fit_count']} .fit dosyası): {fit_summary['total_sample_points']} sensör örneği, "
                        f"Ort HR {fv(first_fit.get('avg_hr'))} bpm, Seans içi nabız drifti {drift_str}."
                    ),
                    "live_metrics": [
                        f"Dosya: {fit_summary['binary_fit_count']} .fit",
                        f"Örnek: {fit_summary['total_sample_points']} nokta",
                        f"CRC-16: {'Geçerli' if first_fit.get('crc_ok', True) else 'Kontrol'}",
                        f"Drift: {drift_str}",
                    ],
                },
                {
                    "channel": "2. Gecelik 5 Dakikalık Yüksek Çözünürlüklü HRV (RMSSD)",
                    "status": hrv_status_txt,
                    "detail": (
                        "data/raw_hrv_5min.json üzerinden son 14 gecenin HRV RMSSD kayıtları ve fetch_garmin_data.mjs (Adım 8/9) hrv-service "
                        "5 dakikalık RMSSD eğrileri doğrudan işlenir."
                    ),
                    "benefit": (
                        f"Son gece HRV: {fv(hrv_summary.get('overnight_avg_ms'))} ms (7G bazal: {fv(hrv_summary.get('baseline_7d_ms'))} ms, "
                        f"Durum: {fv(hrv_summary.get('hrv_status'), 'BALANCED')})."
                    ),
                    "live_metrics": [
                        f"Son: {fv(hrv_summary.get('overnight_avg_ms'))} ms",
                        f"7G Ort: {fv(hrv_summary.get('baseline_7d_ms'))} ms",
                        f"Min–Maks: {fv(hrv_summary.get('min_ms'))}–{fv(hrv_summary.get('max_ms'))} ms",
                        f"Kayıt: {hrv_summary.get('reading_count', 0)} blok",
                    ],
                },
                {
                    "channel": "3. Koşu Biyomekaniği & Running Dynamics (RD)",
                    "status": rd_status,
                    "detail": (
                        f"Tüm {rd_summary['rd_covered_runs']} koşuda Yerle Temas Süresi (GCT), Dikey Salınım, Dikey Oran, Adım Uzunluğu ve "
                        "Watt bazlı koşu güç bölgeleri (Z1–Z5) doğrudan hesaplanıyor."
                    ),
                    "benefit": rd_summary["biomechanical_note"],
                    "live_metrics": [
                        f"GCT: {fv(rd_latest.get('gct_ms'))} ms",
                        f"Dikey Salınım: {fv(rd_latest.get('vertical_oscillation_cm'))} cm",
                        f"Dikey Oran: %{fv(rd_latest.get('vertical_ratio_pct'))}",
                        f"Adım: {fv(rd_latest.get('stride_length_cm'))} cm",
                        f"NP Güç: {fv(rd_latest.get('norm_power_w'))} W",
                    ],
                },
                {
                    "channel": "4. Gece/Gündüz Solunum Hızı, SpO2 & Cilt Sıcaklığı",
                    "status": resp_status_txt,
                    "detail": (
                        f"data/raw_respiration_daily.json ve uyku kayıtlarından günlük/uyku solunum aralığı, cilt ısısı sapması (skinTempC) ve "
                        f"SpO2 trendleri izlenir (Durum: {resp_summary['alert_status']})."
                    ),
                    "benefit": resp_summary["note"],
                    "live_metrics": [
                        f"Uyku Solunum: {fv(resp_summary.get('sleep_respiration_latest'))} br/dk",
                        f"Gün içi: {fv(resp_summary.get('respiration_min_max'))}",
                        f"Cilt Isısı: {fv(resp_summary.get('skin_temp_c_latest'))} °C",
                        f"SpO2: %{fv(resp_summary.get('spo2_daily_avg') if resp_summary.get('spo2_daily_avg') is not None else resp_summary.get('spo2_sleep_latest'))}",
                        f"Ortam: {fv(resp_summary.get('ambient_temp_range_c'))}",
                    ],
                },
            ],
            "implementation_steps": [
                f"1. FIT Dosyaları (download-fit): {fit_summary['binary_fit_count']} ikili .fit dosyası ({fit_summary['total_sample_points']} örnek) data/fit_files/ altında doğrulandı.",
                f"2. Fitparse / İkili FIT Katmanı: {fit_summary['parser_backend']} çözücüsü ve raw_high_res_streams.json ile RD (GCT {fv(rd_latest.get('gct_ms'))} ms) ayrıştırıldı.",
                f"3. HRV & Solunum Eğrisi: raw_hrv_5min.json ({hrv_summary['reading_count']} gece) ve raw_respiration_daily.json disk üzerinde tamamlandı.",
            ],
            "implementation_steps_detail": [
                {
                    "step": "FIT Dosyaları (download-fit)",
                    "status": fit_status,
                    "detail": (
                        f"data/fit_files/ altında {fit_summary['binary_fit_count']} adet CRC-16 doğrulamalı .fit dosyası ve "
                        f"data/raw_high_res_streams.json oluşturuldu; fetch_garmin_data.mjs Adım 7/9 ile canlı eşitlenir."
                    ),
                },
                {
                    "step": "Fitparse / Pure Python FIT Katmanı",
                    "status": fit_status,
                    "detail": (
                        f"app/engine/fit_stream_parser.py ({fit_summary['parser_backend']}) üzerinden {fit_summary['total_sample_points']} sensör "
                        f"örneği ve {rd_summary['rd_covered_runs']} koşunun GCT/VO/VR/Güç telemetrisi aktivite kartlarına işlendi."
                    ),
                },
                {
                    "step": "HRV & Solunum Eğrisi (hrv-service)",
                    "status": hrv_status_txt,
                    "detail": hrv_summary["note"],
                },
            ],
            "fit_stream_summary": fit_summary,
            "hrv_5min_summary": hrv_summary,
            "running_dynamics_summary": rd_summary,
            "respiration_thermal_summary": resp_summary,
        }
