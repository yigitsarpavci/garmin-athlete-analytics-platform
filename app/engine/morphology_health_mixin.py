#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Morfoloji Takibi, Biyolojik Sağlık Yaşı, Klinik Tarama, Kilo/Derece Projeksiyonu
ve Zone 2 Geri Sayım / Otomatik Yeni Hedef Seçimi Mixin'i.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


_TR_FULL_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]


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

    def calculate_custom_projection(
        self,
        target_kg: float = 81.0,
        weekly_pace_kg: float = 0.55,
        now: Optional[datetime] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Güncel ağırlık, tarih, VO2 Max ve 5K performansından kalan gün ve hedef tarihini dinamik hesaplar."""
        if "target_weight" in kwargs:
            target_kg = float(kwargs["target_weight"])
        if "weekly_loss_rate" in kwargs:
            weekly_pace_kg = float(kwargs["weekly_loss_rate"])

        ref_now = now or datetime.now()
        current_weight = float(
            kwargs.get("current_weight", self.get_current_weight() if hasattr(self, "get_current_weight") else 87.0)
        )
        remaining_kg = current_weight - target_kg
        target_bmi = round(target_kg / self.height_m2, 2)

        if remaining_kg <= 0:
            next_auto_kg = max(76.0, round(current_weight - 2.0, 1))
            return {
                "target_kg": target_kg,
                "target_bmi": target_bmi,
                "remaining_kg": 0.0,
                "weekly_pace_kg": weekly_pace_kg,
                "days": 0,
                "days_needed": 0,
                "target_date": f"Zaten ulaşıldı (Sıradaki Otomatik Hedef: {next_auto_kg:.1f} kg)",
                "next_auto_target_kg": next_auto_kg,
                "expected_5k": "24:30 altında",
                "expected_vo2": "52+",
            }

        weeks_needed = remaining_kg / max(0.1, abs(weekly_pace_kg))
        days_needed = int(round(weeks_needed * 7))

        # Güncel VO2 Max değerini çek (yoksa 45.4)
        base_vo2 = 45.4
        if hasattr(self, "vo2max_history") and self.vo2max_history:
            for item in reversed(self.vo2max_history):
                v = (item.get("generic") or {}).get("vo2MaxPreciseValue")
                if v:
                    base_vo2 = float(v)
                    break
        projected_vo2 = round(base_vo2 + (remaining_kg * 0.52) + 2.0, 1)

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
        rhr = float(metrics.get("resting_hr") or metrics.get("rhr") or 53.6)
        vo2 = float(metrics.get("vo2max") or 45.4)
        stress = float(metrics.get("stress") or 28.4)
        sleep_dur = float(metrics.get("sleep_hours") or metrics.get("sleep_duration_hours") or 7.0)
        resp = float(metrics.get("resp_sleep") or 13.8)
        deep_pct = float(metrics.get("deep_sleep_pct") or 18.4)
        cur_w = float(metrics.get("weight") or 87.0)
        cur_bmi = float(metrics.get("bmi") or round(cur_w / self.height_m2, 2))
        start_w = self.get_start_weight() if hasattr(self, "get_start_weight") else 95.0
        lost_kg = round(start_w - cur_w, 1)

        who_cutoff = round(24.99 * self.height_m2, 2)
        to_who_g = max(0, int(round((cur_w - who_cutoff) * 1000)))
        proj_ideal = self.calculate_custom_projection(81.0, 0.55)
        sq_pr = float(prog.get("squat", {}).get("max_kg") or 65.0)
        bp_pr = float(prog.get("bench", {}).get("max_kg") or 50.0)

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
            "title": "Klinik Egzersiz Fizyolojisi & Genel Sağlık Taraması",
            "doctor_verdict": "A-1 Sınıfı Üstün Atletik Kardiyovasküler Rezerv" if rhr <= 56 else "B-1 Aktif Sporcu Kardiyovasküler Profili",
            "overall_status": "MÜKEMMEL (Risk Faktörü Bulunmamaktadır)" if stress < 42 else "DİKKAT (Stres / Yük İzlemi)",
            "summary": (
                f"Güncel 93 günlük sensör telemetrisinde dinlenik nabız {rhr:.1f} bpm, ortalama uyku {sleep_dur:.2f} saat, "
                f"VO2 Max {vo2:.1f} ve kilo {cur_w:.1f} kg (-{lost_kg:.1f} kg) olarak kaydedildi. Metabolik ve otonom profil optimal bantta."
            ),
            "pillars": [
                {
                    "name": "Kardiyovasküler Kapasite & Kalp Sağlığı",
                    "status": "Sporcu Kalbi (Fizyolojik Bradikardi)" if rhr <= 56 else "Sağlıklı Kardiyak Yanıt",
                    "badge": "Mükemmel" if rhr <= 56 else "İyi",
                    "badge_color": "emerald",
                    "value": f"{rhr:.1f} bpm Dinlenik Nabız • 203 bpm Maksimum Nabız",
                    "clinical_notes": (
                        f"{rhr:.1f} bpm dinlenik nabız güçlü sol ventrikül atım hacmini gösterir. "
                        "203 bpm tavanı sempatik kalp rezervinin sağlıklı korunduğunu doğrular."
                    ),
                },
                {
                    "name": "Otonom Sinir Sistemi (HRV & Parasempatik Denge)",
                    "status": "Yüksek Vagal Tonus" if stress < 35 else "Orta Sempatik Yük",
                    "badge": "Dengeli" if stress < 35 else "İzle",
                    "badge_color": "blue",
                    "value": f"{stress:.1f}/100 Ortalama Günlük Stres",
                    "clinical_notes": (
                        f"Ortalama günlük stres skoru {stress:.1f} puan bandında; gece HRV ({metrics.get('overnight_hrv', 43)} ms) "
                        "ile parasempatik toparlanma dengesi korunuyor."
                    ),
                },
                {
                    "name": "Metabolik Sağlık & Vücut Kompozisyonu",
                    "status": metabolic_status,
                    "badge": metabolic_badge,
                    "badge_color": "amber" if to_who_g > 0 else "emerald",
                    "value": f"{cur_w:.1f} kg • VKİ: {cur_bmi:.2f} (DSÖ Eşiği: {who_cutoff:.2f} kg)",
                    "clinical_notes": metabolic_detail,
                },
                {
                    "name": "Pulmoner Fonksiyon & Gece Oksijenasyonu",
                    "status": "Optimal Gaz Değişimi",
                    "badge": "Optimal",
                    "badge_color": "emerald",
                    "value": f"{resp:.1f} Nefes/dk Gece Solunumu",
                    "clinical_notes": (
                        f"Gece solunum hızının ortalama {resp:.1f} nefes/dk bandında kalması stabil gaz değişimini gösterir."
                    ),
                },
                {
                    "name": "Nörolojik Rejenerasyon & Uyku Mimarisi",
                    "status": "Derin Fazlar Korunmuş" if sleep_dur >= 6.8 else "Uyku Süresi Artırılmalı",
                    "badge": "İyi" if sleep_dur >= 6.8 else "Dikkat",
                    "badge_color": "emerald",
                    "value": f"{sleep_dur:.2f} Saat Ortalama Uyku • %{deep_pct:.1f} Derin Uyku",
                    "clinical_notes": (
                        "Derin uyku oranı kas dokusu tamirini destekliyor; 00:45 öncesi yatış REM mimarisini maksimize eder."
                    ),
                },
            ],
            "recommendations": [
                (
                    f"Tartıda {who_cutoff:.2f} kg altına ({to_who_g}g kaldı) inerek DSÖ Normal kategorisine geçişi tamamlayın."
                    if to_who_g > 0 else
                    "DSÖ Normal BMI bandı korundu; 81.0 kg atletik forma doğru -0.55 kg/hf ritmini sürdürün."
                ),
                f"Mevcut {sq_pr:.1f} kg Squat ve {bp_pr:.1f} kg Bench gücünü korumak için günlük ~{round(cur_w * 2.0)}g protein tüketin.",
                "Haftada 2 koşu kotasında 1 Zone 2 + 1 Anaerobik İnterval dengesini koruyun.",
            ],
        }

    def get_fitness_age_analysis(self) -> Dict[str, Any]:
        """Güncel RHR, VO2 Max, kilo ve haftalık aktif dakikalardan biyolojik Fitness Age hesaplar."""
        metrics = self.get_latest_metrics()
        rhr = float(metrics.get("resting_hr") or 53.6)
        vo2 = float(metrics.get("vo2max") or 45.4)
        cur_w = float(metrics.get("weight") or 87.0)
        chrono_age = float(self.age if hasattr(self, "age") else 22)

        rhr_bonus = max(0.0, min(2.0, (58.0 - rhr) * 0.34))
        vo2_bonus = max(0.0, min(2.0, (vo2 - 41.0) * 0.22))
        act_bonus = 0.5
        raw_adv = round(-(rhr_bonus + vo2_bonus + act_bonus), 1)
        # Mevcut veride -2.5 yaş avantaj -> 19.5 yaş
        fitness_age = max(18.0, round(chrono_age + max(-4.0, raw_adv * 0.85), 1))
        age_adv = round(fitness_age - chrono_age, 1)

        proj_81 = self.calculate_custom_projection(81.0, 0.55)
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
                    f"Kilonun {cur_w:.1f} kg'dan 81.0 kg'a inmesi (Bağıl VO2 Max artışı sağlar).",
                    f"VO2 Max puanının {vo2:.1f}'ten {target_vo2} seviyesine çıkması.",
                    "Dinlenik nabzın 50-52 bpm aralığına yerleşmesi.",
                ],
            },
        }

    def get_physique_morphology_tracker(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Güncel kilo, güncel tarih ve PR'lara göre morfoloji aşamalarını dinamik üretir."""
        ref_now = now or datetime.now()
        cur_w = float(self.get_current_weight() if hasattr(self, "get_current_weight") else 87.0)
        cur_bmi = round(cur_w / self.height_m2, 2)
        prog = self.get_gym_exercise_history().get("progression", {}) if hasattr(self, "get_gym_exercise_history") else {}
        sq_pr = float(prog.get("squat", {}).get("max_kg") or 65.0)
        bp_pr = float(prog.get("bench", {}).get("max_kg") or 50.0)

        # Deurenberg BMI -> Yağ Oranı tahmini + atletik düzeltme
        est_bf = max(10.5, min(28.0, (1.20 * cur_bmi) + (0.23 * self.age) - 16.2 - 0.5))
        bf_low = max(9.0, round(est_bf - 1.0))
        bf_high = max(10.0, round(est_bf + 1.0))

        who_cutoff = round(24.99 * self.height_m2, 2)
        if cur_w > 84.5:
            stage_targets = [
                (round(min(who_cutoff, cur_w - 0.5), 2), "18.0% – 19.0%", "DSÖ Normal Kilo sınıfına resmi geçiş; yüz ve boyun hatlarında netleşme.", "Koşuda adım başına eklem darbe yükü belirgin azalır."),
                (84.0, "16.0% – 17.0%", "Bel çevresinde incelme, göğüs/omuz ayrımında belirginleşme, üst karın silüeti.", "Zone 2 pace ~6:15 /km bandına yaklaşır, 5K süresi 27 dk altına iner."),
                (81.0, "13.0% – 14.0%", "Atletik V-Taper (geniş omuzlar, dar bel), belirgin karın ve bacak kas çizgileri.", "5K 24:30 altına iner; 145 bpm nabızda 5:00-5:15 /km akışı açılır!"),
            ]
        elif cur_w > 81.2:
            stage_targets = [
                (82.5, "15.0% – 16.0%", "Bel çevresinde derin incelme, oblik ve üst karın hatlarında netleşme.", "Koşuda güç/ağırlık (W/kg) artar, 145 bpm tempo hızlanır."),
                (81.0, "13.0% – 14.0%", "Atletik V-Taper formu; yağsız omuz/sırt ve belirgin karın bölgesi.", "5K 24:30 altı & Zone 2 @ 5:00 /km eşiği kilitlenir."),
                (79.5, "11.5% – 12.5%", "Yüksek definisyonlu dayanıklılık ve kuvvet dengesi (Koruma & Rekompozisyon).", "Maksimal göreceli kuvvet + yüksek VO2 Max zirvesi."),
            ]
        else:
            t1 = round(cur_w, 1)
            t2 = round(max(76.0, cur_w - 1.5), 1)
            t3 = round(max(75.0, cur_w - 2.5), 1)
            stage_targets = [
                (t1, f"%{est_bf:.1f}", "İdeal atletik kilo bölgesi korundu — sıfır yağlanmayla kas koruma.", "Güç/ağırlık oranı yüksek; Zone 2 ve 5K hız adaptasyonu sürüyor."),
                (t2, f"%{max(10.0, est_bf - 1.2):.1f}", "İnce bel ve artan omuz-sırt kas yoğunluğu (atletik rekompozisyon).", "Koşuda oksijen ekonomisi maksimum seviyede."),
                (t3, f"%{max(9.5, est_bf - 2.2):.1f}", "Yarışma seviyesi yağsız atletik fizik & yüksek definisyon.", "Dayanıklılık zirvesi (5K <24:00 & sub-5:00 /km Z2)."),
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
                "status_title": "Atletik İdeal Bölge" if cur_w <= 81.5 else ("DSÖ Normal Bölge" if cur_bmi < 25.0 else "Güçlü Başlangıç (Normal Eşik Yakını)"),
            },
            "stages": stages,
        }

    def get_z2_pace_5min_tracker(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Zone 2 temposunu canlı çeker; tarih veya hız hedefine ulaşıldığında bir sonraki hedef kademesine geçer."""
        now = now or datetime.now()
        base_target_dt = datetime(2027, 4, 15)

        latest_z2_pace_sec = 400.0
        latest_run_pace = "6:40 /km"
        latest_run_hr = 145
        latest_ef = 1.03

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
                hr = chosen.get("averageHR") or 145
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

        # Otomatik Yeni Hedef Seçimi: Tarih sıfırlandıysa veya 5:00/km tutulduysa -> 4:45/km yeni döngüsü
        goal_auto_advanced = (now >= base_target_dt) or (latest_z2_pace_sec <= 300.0)
        if goal_auto_advanced:
            target_pace_sec = 285
            target_pace = "4:45 /km"
            target_ef = 1.45
            target_dt = now + timedelta(days=84)
            target_date_str = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year} (Yeni Faz)"
            rem_days = 84
        else:
            target_pace_sec = 300
            target_pace = "5:00 /km"
            target_ef = 1.38
            target_dt = base_target_dt
            target_date_str = f"{target_dt.day} {_TR_FULL_MONTHS[target_dt.month - 1]} {target_dt.year}"
            rem_days = max(1, (target_dt - now).days)

        rem_weeks = max(1, math.ceil(rem_days / 7.0))
        pace_gap = max(0, int(round(latest_z2_pace_sec - target_pace_sec)))
        cur_w = float(self.get_current_weight() if hasattr(self, "get_current_weight") else 87.0)

        return {
            "current_pace": latest_run_pace,
            "current_hr_bpm": latest_run_hr,
            "current_efficiency_factor": latest_ef,
            "target_pace": target_pace,
            "target_hr_bpm": 145,
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
                {"rule": "Kadansı 162+ spm'de tutun", "why": "Adımları uzatmak frenleme yapar; kısa ve sık adım elastik geri sekme sağlar."},
                {"rule": f"81 kg Hedefine İnin ({cur_w:.1f} -> 81.0 kg)", "why": "Vücut kütlesindeki her -1 kg düşüş yerçekimi işini azaltarak pace'i ~4 sn/km hızlandırır."},
                {"rule": "150 bpm Katı Tavan Kuralı", "why": "Nabız 151 olduğunda yavaşlayın veya yürüyün; sol ventrikül adaptasyonu Zone 2'de maksimumdur."},
                {"rule": "Haftada 1 Seans 4x1000m İnterval", "why": "Anaerobik barı ve laktat eşiğini yukarı iter; eşik yükseldikçe Z2 hızı artar."},
                {"rule": "A/B 5x5 Squat ve Deadlift", "why": "Arka zincir gücü koşuda her adımda yer tepki kuvvetini artırır."},
            ],
            "timeline_milestones": [
                {"period": f"Mevcut ({now.year})", "pace": latest_run_pace, "weight": f"{cur_w:.1f} kg", "status": "Aerobik Taban İnşası"},
                {"period": f"+{max(1, rem_weeks // 3)} Hafta", "pace": "6:05 - 6:20 /km", "weight": f"{max(81.0, cur_w - 2.5):.1f} kg", "status": "İlk Hafifleme ve Kadans Kazanımı"},
                {"period": f"+{max(2, (rem_weeks * 2) // 3)} Hafta", "pace": "5:30 - 5:45 /km", "weight": f"{max(81.0, cur_w - 4.5):.1f} kg", "status": "Kılcal Damarlanma & Mitokondri Artışı"},
                {"period": target_date_str, "pace": f"{target_pace}", "weight": "81.0 kg", "status": "Hedef Atletik Zirve (@ 145 bpm)"},
            ],
        }

    def get_garmin_data_expansion_guide(self) -> Dict[str, Any]:
        """Garmin Connect veri derinliğini artırma rehberini döner."""
        return {
            "title": "Garmin'den Çektiğimiz Verileri Nasıl Daha Fazla Artırabiliriz?",
            "current_data_channels": [
                "Aktiviteler & Spor Türleri (Koşu, Kuvvet, Yelken, Basketbol, Kayak ve tüm ekstra branşlar)",
                "Günlük Özetler, Uyku Skorları & HRV",
                "Tartı / Vücut Ağırlığı & Kuvvet Egzersiz Setleri (weight-service & exerciseSets)",
                "Training Status, Akut/Kronik Yük (ACWR) & VO2 Max",
            ],
            "new_high_resolution_channels": [
                {
                    "channel": "1. FIT Dosyalarının Saniye Saniye Parse Edilmesi (download-fit)",
                    "detail": "Her koşu ve kuvvet seansının .fit ikili dosyası indirilerek saniye saniye nabız, hız, irtifa ve kadans haritalandırılır.",
                    "benefit": "Koşunun hangi kilometresinde nabız sıçraması (cardiac drift) oluştuğu milisaniye hassasiyetinde görülür.",
                },
                {
                    "channel": "2. Gecelik 5 Dakikalık Yüksek Çözünürlüklü HRV (RMSSD)",
                    "detail": "Garmin hrv-service üzerinden gece boyu 5 dakikalık RMSSD dalgalanması çekilebilir.",
                    "benefit": "Merkezi sinir sisteminin hangi saatlerde derin rejenerasyona girdiği saptanır.",
                },
                {
                    "channel": "3. Koşu Biyomekaniği & Running Dynamics (RD)",
                    "detail": "Dikey Salınım, Dikey Oran ve Sol/Sağ Yerle Temas Denge Oranı takibi.",
                    "benefit": "Bacak asimetrisi erken yakalanarak sakatlık önlenir.",
                },
                {
                    "channel": "4. Gece/Gündüz Solunum Hızı & Isı Aklimatizasyonu",
                    "detail": "Respiration service ile enfeksiyon/aşırı yüklenme sinyallerinin 48 saat önce yakalanması.",
                    "benefit": "Deload kararlarını hastalık oluşmadan tetikler.",
                },
            ],
            "implementation_steps": [
                "fetch_garmin_data.mjs ile weight-service ve exerciseSets canlı akışı tamamlandı.",
                "İleri aşamada download-fit ve hrv-service uçları eklenerek fitparse entegrasyonu yapılabilir.",
            ],
        }
