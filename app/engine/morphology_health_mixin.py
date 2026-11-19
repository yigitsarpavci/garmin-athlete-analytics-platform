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


try:
    from engine.helpers import fnum, request_cached
except ImportError:
    from app.engine.helpers import fnum, request_cached


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
                    f"Dinlenik nabzın {max(35, round(rhr) - 4)}-{max(36, round(rhr) - 2)} bpm aralığına yerleşmesi.",
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

    @staticmethod
    def _pace_band(sec: float) -> str:
        """Saniye/km değerinin ±7 sn bandını "m:ss - m:ss /km" olarak yazar."""
        lo, hi = int(round(sec - 7)), int(round(sec + 7))
        return f"{lo // 60}:{lo % 60:02d} - {hi // 60}:{hi % 60:02d} /km"

    def get_z2_pace_5min_tracker(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Zone 2 temposunu canlı çeker; tarih veya hız hedefine ulaşıldığında bir sonraki hedef kademesine geçer."""
        now = now or datetime.now()
        z2_default_hr = int(round(0.714 * self.get_physiology()["max_hr"]))
        z2_center = self.get_z2_center_pace_sec()

        goal_pace_sec, base_target_dt = self.get_z2_goal(now)

        latest_z2_pace_sec = fnum(z2_center, 420.0)
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
                        if 0.62 * self.get_physiology()["max_hr"] <= hr <= 0.77 * self.get_physiology()["max_hr"]:
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
                {"period": f"+{max(1, rem_weeks // 3)} Hafta", "pace": self._pace_band(latest_z2_pace_sec - (latest_z2_pace_sec - target_pace_sec) / 3.0), "weight": f"{max(target_w, cur_w - 2.5):.1f} kg", "status": "İlk Hafifleme ve Kadans Kazanımı"},
                {"period": f"+{max(2, (rem_weeks * 2) // 3)} Hafta", "pace": self._pace_band(latest_z2_pace_sec - 2.0 * (latest_z2_pace_sec - target_pace_sec) / 3.0), "weight": f"{max(target_w, cur_w - 4.5):.1f} kg", "status": "Kılcal Damarlanma & Mitokondri Artışı"},
                {"period": target_date_str, "pace": f"{target_pace}", "weight": f"{target_w:.1f} kg", "status": f"Hedef Atletik Zirve (@ {z2_hr} bpm)"},
            ],
        }
