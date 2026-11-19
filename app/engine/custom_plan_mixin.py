#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hazır Sporcu Şablonları ve Kişiselleştirilmiş Esnek Kota Planlayıcı Mixin'i.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

try:
    from engine.helpers import format_sport_tr
except ImportError:
    from app.engine.helpers import format_sport_tr


logger = logging.getLogger(__name__)


class CustomPlanMixin:
    """Özel profil sihirbazı, preset şablonlar ve dinamik esnek döngü üreticisi."""

    def get_profile_presets(self) -> List[Dict[str, Any]]:
        """Hazır antrenman profili şablonlarını canlı metriklerle döner."""
        cur_w = round(float(self.get_current_weight()), 1)
        me = self.profile.get("name") or "Sporcu"
        tw = self.get_target_weight()
        prog = self.get_gym_exercise_history().get("progression", {}) if hasattr(self, "get_gym_exercise_history") else {}
        sq = prog.get("squat", {}).get("max_kg", 0.0)
        bp = prog.get("bench", {}).get("max_kg", 0.0)
        return [
            {
                "id": "athlete_default",
                "name": f"{me} (Özel Sensör Profili - 2 Koşu + 2 Gym)",
                "description": f"Gerçek Garmin sensör verileri, Squat {sq:.0f}kg / Bench {bp:.0f}kg PR, {cur_w} kg -> {tw} kg ve polarize koşu.",
                "is_current_athlete": True,
                "badge": "Orijinal Telemetri",
                "prefs": {
                    "name": me, "age": self.age, "gender": self.profile.get("gender", "male"), "height_cm": self.height_cm,
                    "current_weight_kg": cur_w, "target_weight_kg": tw,
                    "weekly_weight_loss_rate": 0.55, "running_days": 2, "running_style": "polarize",
                    "gym_days": 2, "gym_routine": "ab_5x5", "secondary_sports": ["sailing", "basketball"],
                    "primary_goal": "fat_loss_and_speed",
                },
            },
            {
                "id": "fat_loss_hybrid",
                "name": "Agresif Yağ Yakımı & Hibrit Kondisyon (3 Koşu + 2 Gym)",
                "description": "3 Zone 2 koşusu ve 2 Tüm Vücut kuvvet seansı içeren esnek yağ yakım modeli.",
                "is_current_athlete": False,
                "badge": "Yağ Yakımı",
                "prefs": {
                    "name": "Misafir Sporcu", "age": 26, "gender": "male", "height_cm": 180.0,
                    "current_weight_kg": 85.0, "target_weight_kg": 77.0,
                    "weekly_weight_loss_rate": 0.65, "running_days": 3, "running_style": "pure_z2",
                    "gym_days": 2, "gym_routine": "ab_5x5", "secondary_sports": ["cycling"], "primary_goal": "fat_loss",
                },
            },
            {
                "id": "marathon_runner",
                "name": "Yarı Maraton & Maratoncu Modeli (4 Koşu + 1 Gym)",
                "description": "Yüksek koşu hacmi ve sakatlık önleyici 1 kuvvet seansı içeren model.",
                "is_current_athlete": False,
                "badge": "Koşu & Hacim",
                "prefs": {
                    "name": "Koşucu", "age": 28, "gender": "male", "height_cm": 178.0,
                    "current_weight_kg": 74.0, "target_weight_kg": 70.0,
                    "weekly_weight_loss_rate": 0.40, "running_days": 4, "running_style": "polarize",
                    "gym_days": 1, "gym_routine": "fullbody_accessories", "secondary_sports": [], "primary_goal": "running_speed",
                },
            },
            {
                "id": "hypertrophy_ppl",
                "name": "Kas Hipertrofisi & Güç (4 Gym PPL + 1 Koşu)",
                "description": "İtiş-Çekiş-Bacak bölünmesi ve 1 gün Zone 2 kardiyovasküler koruma.",
                "is_current_athlete": False,
                "badge": "Kas & Güç",
                "prefs": {
                    "name": "Vücut Geliştirme", "age": 24, "gender": "male", "height_cm": 182.0,
                    "current_weight_kg": 82.0, "target_weight_kg": 85.0,
                    "weekly_weight_loss_rate": -0.25, "running_days": 1, "running_style": "pure_z2",
                    "gym_days": 4, "gym_routine": "ppl", "secondary_sports": ["swimming"], "primary_goal": "muscle_hypertrophy",
                },
            },
            {
                "id": "beginner_fit",
                "name": "Yeni Başlayan / Sağlıklı Yaşam (2 Koşu/Yürüyüş + 1 Gym)",
                "description": "Eklemleri yormadan sürdürülebilir alışkanlık kazandıran başlangıç programı.",
                "is_current_athlete": False,
                "badge": "Başlangıç & Sağlık",
                "prefs": {
                    "name": "Yeni Başlayan", "age": 30, "gender": "female", "height_cm": 168.0,
                    "current_weight_kg": 68.0, "target_weight_kg": 62.0,
                    "weekly_weight_loss_rate": 0.45, "running_days": 2, "running_style": "pure_z2",
                    "gym_days": 1, "gym_routine": "bodyweight", "secondary_sports": ["pilates"], "primary_goal": "general_health",
                },
            },
        ]

    def _safe_get_weekly_quota(self) -> Dict[str, Any]:
        """Haftalık kota özetini güvenli biçimde çeker; yoksa standart esnek şablona düşer."""
        if hasattr(self, "get_weekly_quota_summary"):
            try:
                quota = self.get_weekly_quota_summary()
                if isinstance(quota, dict) and quota:
                    out = dict(quota)
                    out.setdefault("is_custom", False)
                    out.setdefault("running_target", (out.get("running") or {}).get("target", 2))
                    out.setdefault("gym_target", (out.get("strength") or {}).get("target", 2))
                    return out
            except Exception:
                logger.warning("_safe_get_weekly_quota: yedek davranış uygulandı", exc_info=True)
        return {
            "is_custom": False,
            "week_range": "Esnek Haftalık Döngü",
            "headline": "Haftalık Hedef: 2 Koşu + 2 Kuvvet · Esnek Takvim",
            "flexibility_note": "Sabit gün zorunluluğu yok — kalan seansları uygun günlere yerleştirebilirsiniz.",
            "running_target": 2,
            "gym_target": 2,
            "total": {"target": 4, "completed": 0, "remaining": 4, "progress_pct": 0, "is_complete": False},
            "running": {"target": 2, "completed": 0, "remaining": 2, "progress_pct": 0, "completed_labels": [], "completed_items": [], "remaining_items": [], "status_text": "0/2 Tamamlandı"},
            "strength": {"target": 2, "completed": 0, "remaining": 2, "progress_pct": 0, "completed_labels": [], "completed_items": [], "remaining_items": [], "status_text": "0/2 Tamamlandı"},
            "remaining_items": [],
            "spontaneous": {"count": 0, "items": [], "labels": [], "status_text": "Spontane branşlar yapıldıkça takip edilir"},
        }

    # Şablonlardaki nabız bantları nominal 200 bpm maksimum için tasarlanmıştır; her sporcunun kendi
    # (220 - yaş) tahmini maksimum nabzına göre ölçeklenir. Böylece hiçbir şablon belirli bir kişiye bağlı değildir.
    TEMPLATE_REFERENCE_MAX_HR = 200

    def _scale_hr_text(self, text: str, max_hr: int) -> str:
        """'135-148 bpm' gibi nabız aralıklarını sporcunun maksimum nabzına göre ölçekler."""
        import re
        k = max_hr / float(self.TEMPLATE_REFERENCE_MAX_HR)
        return re.sub(r"(\d{2,3})-(\d{2,3}) bpm", lambda m: f"{round(int(m.group(1)) * k)}-{round(int(m.group(2)) * k)} bpm", text)

    def _get_custom_session_pools(self, r_style: str, g_routine: str, age: Optional[int] = None) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """Özel sporcu tercihi için koşu ve kuvvet seans şablon havuzlarını (nabız bantları yaşa göre ölçeklenmiş) döner."""
        runs, gyms = self._raw_session_pools(r_style, g_routine)
        max_hr = 220 - int(age if age is not None else self.age)
        for item in runs + gyms:
            if "target" in item:
                item["target"] = self._scale_hr_text(item["target"], max_hr)
        return runs, gyms

    def _raw_session_pools(self, r_style: str, g_routine: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """Şablon havuzları (nominal 200 bpm maksimum nabız referansıyla)."""
        if r_style == "pure_z2":
            runs = [
                {"slot_kind": "zone2", "type": "Zone 2 Taban", "badge": "Zone 2", "title_suffix": "Zone 2 Taban Koşusu (40-45 dk)", "secondary": "Düşük nabız, burundan nefes, mitokondri inşası", "target": "135-148 bpm (Zone 2)", "target_pace": "Konuşma temposu", "duration": "40-45 dk"},
                {"slot_kind": "zone2", "type": "Zone 2 Taban", "badge": "Zone 2", "title_suffix": "Zone 2 Taban Koşusu (45-50 dk)", "secondary": "Aerobik taban ve yağ oksidasyonu", "target": "135-148 bpm (Zone 2)", "target_pace": "Konuşma temposu", "duration": "45-50 dk"},
                {"slot_kind": "zone2", "type": "Zone 2 Uzun", "badge": "Zone 2 Uzun", "title_suffix": "Zone 2 Uzun Taban (50-60 dk)", "secondary": "Haftalık uzun koşu, konuşma temposu", "target": "138-150 bpm (Zone 2)", "target_pace": "Konuşma temposu", "duration": "50-60 dk"},
                {"slot_kind": "zone2", "type": "Toparlanma Koşusu", "badge": "Toparlanma", "title_suffix": "Zone 2 Rahat Akış (35-40 dk)", "secondary": "Toparlanma amaçlı hafif tempolu koşu", "target": "130-142 bpm (Zone 1-2)", "target_pace": "Çok rahat tempo", "duration": "35-40 dk"},
            ]
        else:
            runs = [
                {"slot_kind": "zone2", "type": "Zone 2 Koşu", "badge": "Zone 2 Taban", "title_suffix": "Zone 2 Rahat Taban (45 dk)", "secondary": "Konuşma temposu, aerobik kılcal damarlanma", "target": "138-150 bpm (Zone 2)", "target_pace": "Konuşma temposu", "duration": "45 dk"},
                {"slot_kind": "interval", "type": "Hız İntervali", "badge": "İnterval", "title_suffix": "Hız & Laktat İntervali (40 dk)", "secondary": "Isınma + 4x800m veya 4x1000m hızlı tempo (aralarda 3 dk jog)", "target": "170-182 bpm (Zone 4-5)", "target_pace": "5K hızı / yüksek tempo", "duration": "40 dk"},
                {"slot_kind": "zone2", "type": "Zone 2 Uzun", "badge": "Zone 2 Uzun", "title_suffix": "Zone 2 Uzun Taban (50-55 dk)", "secondary": "Düz parkurda kesintisiz taban koşusu", "target": "140-152 bpm (Zone 2)", "target_pace": "Konuşma temposu", "duration": "50-55 dk"},
                {"slot_kind": "tempo", "type": "Tempo / Eşik", "badge": "Eşik Tempo", "title_suffix": "Tempo / Eşik Koşusu (35 dk)", "secondary": "Isınma + 20 dk sürdürülebilir eşik temposu", "target": "162-172 bpm (Zone 3-4)", "target_pace": "Laktat eşiği temposu", "duration": "35 dk"},
            ]

        if g_routine == "ppl":
            gyms = [
                {"slot_kind": "gym", "type": "İtiş (Push)", "badge": "Push", "title_suffix": "İtiş / Push (Göğüs, Omuz, Triceps)", "secondary": "Bench Press, Incline DB Press, OHP, Lateral Raise, Triceps Pushdown", "target": "115-130 bpm (Zone 1)", "duration": "55 dk"},
                {"slot_kind": "gym", "type": "Çekiş (Pull)", "badge": "Pull", "title_suffix": "Çekiş / Pull (Sırt, Arka Omuz, Biceps)", "secondary": "Lat Pulldown, Barbell Row, Seated Cable Row, Face Pull, Curl", "target": "115-130 bpm (Zone 1)", "duration": "55 dk"},
                {"slot_kind": "gym", "type": "Bacak (Legs)", "badge": "Legs", "title_suffix": "Bacak / Legs (Kuadriseps & Arka Zincir)", "secondary": "Back Squat, Romanian Deadlift, Leg Press, Leg Curl, Baldır", "target": "125-140 bpm (Zone 1-2)", "duration": "55 dk"},
                {"slot_kind": "gym", "type": "Üst Vücut & Core", "badge": "Üst + Core", "title_suffix": "Üst Vücut & Core Hipertrofisi", "secondary": "Dumbbell Press, Barfiks, Lateral Raise, Cable Core", "target": "115-130 bpm (Zone 1)", "duration": "50 dk"},
            ]
        elif g_routine == "upper_lower":
            gyms = [
                {"slot_kind": "gym", "type": "Üst Vücut Güç", "badge": "Üst Güç", "title_suffix": "Üst Vücut Güç & Hipertrofi", "secondary": "Bench Press, Barbell Row, OHP, Lat Pulldown, Yan Açış", "target": "115-130 bpm (Zone 1)", "duration": "55 dk"},
                {"slot_kind": "gym", "type": "Alt Vücut Güç", "badge": "Alt Güç", "title_suffix": "Alt Vücut & Core Güç", "secondary": "Squat, Deadlift, Lunge, Hanging Leg Raise, Plank", "target": "125-140 bpm (Zone 1-2)", "duration": "55 dk"},
                {"slot_kind": "gym", "type": "Üst Vücut Hacim", "badge": "Üst Hacim", "title_suffix": "Üst Vücut Aksesuar & Hacim", "secondary": "Incline DB Press, Cable Row, Dips, Barfiks", "target": "115-130 bpm (Zone 1)", "duration": "50 dk"},
                {"slot_kind": "gym", "type": "Alt Vücut Fonksiyonel", "badge": "Alt Fonk.", "title_suffix": "Alt Vücut & Fonksiyonel", "secondary": "Front Squat / Goblet Squat, Hip Thrust, Baldır, Core", "target": "120-135 bpm (Zone 1)", "duration": "50 dk"},
            ]
        elif g_routine == "bodyweight":
            gyms = [
                {"slot_kind": "gym", "type": "Vücut Ağırlığı", "badge": "Bodyweight", "title_suffix": "Fonksiyonel Vücut Ağırlığı & Core", "secondary": "Şınav, Barfiks/Inverted Row, Bodyweight Squat, Lunge, Plank", "target": "120-140 bpm (Zone 1-2)", "duration": "40 dk"},
                {"slot_kind": "gym", "type": "Mobilite & Güç", "badge": "Mobilite", "title_suffix": "Mobilite, Denge & Güç", "secondary": "Pike Pushup, Dips, Step-Up, Side Plank", "target": "115-135 bpm (Zone 1)", "duration": "40 dk"},
            ]
        else:
            gyms = [
                {"slot_kind": "gym_a", "type": "Workout A (5x5)", "badge": "Workout A", "title_suffix": "Workout A (Squat, Bench Press, Barbell Row 5x5)", "secondary": "Bileşik güç (5x5) + Lateral Raise (3x12) & Shrug (3x12)", "target": "115-130 bpm (Zone 1)", "duration": "55 dk"},
                {"slot_kind": "gym_b", "type": "Workout B (5x5)", "badge": "Workout B", "title_suffix": "Workout B (Squat, OHP, Deadlift, Lat Pulldown)", "secondary": "Arka zincir & omuz gücü + Lat Pulldown (4x12), Lateral Raise & Shrug", "target": "115-130 bpm (Zone 1)", "duration": "55 dk"},
                {"slot_kind": "gym_a", "type": "Workout A Ek", "badge": "Workout A+", "title_suffix": "Workout A Tekrarı veya Aksesuar", "secondary": "Squat 5x5, Bench Press 5x5, Lateral Raise & Core", "target": "115-130 bpm (Zone 1)", "duration": "50 dk"},
            ]
        return runs, gyms

    def _build_custom_quota_summary(self, name: str, r_days: int, r_style: str, g_days: int, g_routine: str, sec_sports: List[str], age: Optional[int] = None) -> Dict[str, Any]:
        """Özel sporcu profili için esnek haftalık kota özetini üretir."""
        run_pool, gym_pool = self._get_custom_session_pools(r_style, g_routine, age)
        run_items = [
            {
                "category": "running", "slot_kind": run_pool[idx % len(run_pool)]["slot_kind"],
                "ordinal": idx + 1, "type": run_pool[idx % len(run_pool)]["type"],
                "short_label": run_pool[idx % len(run_pool)]["type"],
                "title": f"Koşu #{idx + 1} · {run_pool[idx % len(run_pool)]['title_suffix']}",
                "target_hr": run_pool[idx % len(run_pool)]["target"],
                "target_pace": run_pool[idx % len(run_pool)]["target_pace"],
                "duration": run_pool[idx % len(run_pool)]["duration"],
                "badge": run_pool[idx % len(run_pool)]["badge"],
                "coaching_note": run_pool[idx % len(run_pool)]["secondary"],
            }
            for idx in range(r_days)
        ]
        gym_items = [
            {
                "category": "strength", "slot_kind": gym_pool[idx % len(gym_pool)]["slot_kind"],
                "ordinal": idx + 1, "type": gym_pool[idx % len(gym_pool)]["type"],
                "short_label": gym_pool[idx % len(gym_pool)]["type"],
                "title": f"Kuvvet #{idx + 1} · {gym_pool[idx % len(gym_pool)]['title_suffix']}",
                "exercises_summary": gym_pool[idx % len(gym_pool)]["secondary"],
                "duration": gym_pool[idx % len(gym_pool)]["duration"],
                "badge": gym_pool[idx % len(gym_pool)]["badge"],
                "coaching_note": gym_pool[idx % len(gym_pool)]["secondary"],
            }
            for idx in range(g_days)
        ]
        sec_tr = [format_sport_tr(s, s) for s in sec_sports]
        total_target = r_days + g_days
        return {
            "is_custom": True,
            "athlete_name": name,
            "week_range": "Esnek 7 Günlük Döngü",
            "headline": f"Haftalık Hedef: {r_days} Koşu + {g_days} Kuvvet · Esnek Takvim",
            "flexibility_note": f"Sabit gün zorunluluğu yok — {name} için haftalık {r_days} koşu ve {g_days} kuvvet uygun günlere esnekçe yerleştirilir.",
            "running_target": r_days,
            "gym_target": g_days,
            "total": {"target": total_target, "completed": 0, "remaining": total_target, "progress_pct": 0, "is_complete": total_target == 0},
            "running": {"target": r_days, "completed": 0, "remaining": r_days, "progress_pct": 0, "completed_labels": [], "completed_items": [], "remaining_items": run_items, "status_text": f"0/{r_days} Tamamlandı"},
            "strength": {"target": g_days, "completed": 0, "remaining": g_days, "progress_pct": 0, "completed_labels": [], "completed_items": [], "remaining_items": gym_items, "status_text": f"0/{g_days} Tamamlandı"},
            "remaining_items": run_items + gym_items,
            "spontaneous": {"count": 0, "items": [], "labels": sec_tr, "status_text": f"Ek branşlar ({', '.join(sec_tr)}) isteğe bağlı takip edilir" if sec_tr else "Spontane ek branş tanımlanmadı"},
        }

    def generate_custom_plan(self, prefs: dict) -> dict:
        """Ana sporcu (Garmin hesabı sahibi) veya özel sporcu profili için dinamik mikro-döngü, kota özeti ve makro planı üretir."""
        my_name = str(self.profile.get("name") or "").strip().lower()
        if prefs.get("id") == "athlete_default" or prefs.get("is_current_athlete") or (my_name and prefs.get("name", "").strip().lower() == my_name):
            my_quota = self._safe_get_weekly_quota()
            cur_w = float(self.get_current_weight())
            tw = self.get_target_weight()
            cur_bmi = round(cur_w / self.height_m2, 2)
            tar_bmi = round(tw / self.height_m2, 2)
            bmr = round(10 * cur_w + 6.25 * self.height_cm - 5 * self.age + 5)
            tdee = round(bmr * 1.50)
            target_kcal = max(1800, tdee - 450)
            prot_g = round(cur_w * 2.0)
            fat_g = round(cur_w * 0.88)
            carbs_g = max(90, round((target_kcal - prot_g * 4 - fat_g * 9) / 4))
            proj = self.calculate_custom_projection(target_kg=tw, weekly_pace_kg=0.55)
            me = self.profile.get("name") or "Sporcu"
            return {
                "is_current_athlete": True,
                "athlete_name": me,
                "profile_badge": f"{me} (Özel Telemetri - 2 Koşu + 2 Gym)",
                "description": f"Gerçek Garmin sensör verileri, {cur_w:.1f} kg -> {tw:.1f} kg ve esnek 2+2 kota aktif.",
                "metrics": {
                    "age": self.age, "gender": "Kadın" if self.profile.get("gender") == "female" else "Erkek", "height_cm": self.height_cm,
                    "current_weight_kg": cur_w, "target_weight_kg": tw,
                    "current_bmi": cur_bmi, "target_bmi": tar_bmi,
                    "bmr_kcal": bmr, "tdee_kcal": tdee, "target_calories_kcal": target_kcal,
                    "protein_g": prot_g, "carbs_g": carbs_g, "fat_g": fat_g,
                    "days_to_goal": proj.get("days_needed", 0), "target_date": proj.get("target_date", "--"),
                    "weekly_running_days": 2, "weekly_gym_days": 2, "weekly_weight_loss_rate": 0.55,
                },
                "schedule": self.get_weekly_schedule(),
                "weekly_quota": my_quota,
                "quota_summary": my_quota,
                "coaching_tips": [
                    "Aynı Gün Sıralama Kanunu: Asla ağırlıktan hemen sonra koşma; önce koşu, sonra ağırlık yap (veya araya ≥6 saat koy).",
                    "Esnek Pazartesi Kotası: Pazartesi 0/2 açılır; geçen haftadan eksik kalan tür ilk sıraya önceliklendirilir.",
                    "Firstbeat Load Focus: Düşük/Yüksek aerobik yüksekken Anaerobik odak için 4x1000m hız intervali koruyun.",
                    "Progressive Overload: 5x5 temiz tamamlandığında üst vücuda +2.5 kg, bacaklara +2.5–5.0 kg ekleyin.",
                ],
            }

        name = prefs.get("name", "Misafir Sporcu")
        age = int(prefs.get("age", 25))
        gender = prefs.get("gender", "male")
        height = float(prefs.get("height_cm", 178))
        weight = float(prefs.get("current_weight_kg", 80.0))
        target_weight = float(prefs.get("target_weight_kg", 75.0))
        loss_rate = float(prefs.get("weekly_weight_loss_rate", 0.50))
        r_days = max(0, int(prefs.get("running_days", 2)))
        r_style = prefs.get("running_style", "polarize")
        g_days = max(0, int(prefs.get("gym_days", 2)))
        g_routine = prefs.get("gym_routine", "ab_5x5")
        goal = prefs.get("primary_goal", "fat_loss")
        sec_sports = prefs.get("secondary_sports", [])
        if isinstance(sec_sports, str):
            sec_sports = [s.strip() for s in sec_sports.split(",") if s.strip()]

        bmr = round(10 * weight + 6.25 * height - 5 * age - (161 if gender == "female" else -5))
        tot_active = r_days + g_days
        mult = 1.25 if tot_active <= 1 else (1.35 if tot_active == 2 else (1.45 if tot_active == 3 else (1.55 if tot_active == 4 else (1.65 if tot_active == 5 else 1.75))))
        tdee = round(bmr * mult)

        weight_diff = weight - target_weight
        if weight_diff > 0:
            deficit = min(round((loss_rate * 7700) / 7), 650)
            target_kcal = max(tdee - deficit, 1300)
            days_to_goal = max(round(weight_diff / (loss_rate / 7.0 if loss_rate > 0 else 0.07)), 7)
        elif weight_diff < 0:
            target_kcal = tdee + 300
            days_to_goal = max(round(abs(weight_diff) / (0.25 / 7)), 14)
        else:
            target_kcal = tdee
            days_to_goal = 0

        target_dt = datetime.fromtimestamp(datetime.now().timestamp() + days_to_goal * 86400)
        tr_m = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        target_date_str = f"{target_dt.day} {tr_m[target_dt.month - 1]} {target_dt.year}"

        protein_g = round(weight * (2.0 if g_days >= 2 or goal in ("fat_loss", "muscle_hypertrophy") else 1.6))
        fat_g = round(weight * 0.85)
        carbs_g = max(round((target_kcal - (protein_g * 4 + fat_g * 9)) / 4), 90)
        h_m = height / 100.0
        cur_bmi = round(weight / (h_m * h_m), 2)
        tar_bmi = round(target_weight / (h_m * h_m), 2)

        schedule = self._build_dynamic_schedule(name, weight, r_days, r_style, g_days, g_routine, target_kcal, protein_g, carbs_g, fat_g, tdee, sec_sports, age)
        quota_summary = self._build_custom_quota_summary(name, r_days, r_style, g_days, g_routine, sec_sports, age)

        tot_days = r_days + g_days
        if tot_days <= 3:
            athlete_tier = "Başlangıç Seviyesi (Temel Adaptasyon & Fonksiyonellik)"
            progression_next = "Kesintisiz 35 dk Zone 2 ve vücut ağırlığı temel hareketleri oturduğunda kota 4 seansa çıkarılır."
        elif tot_days == 4:
            athlete_tier = "Orta Seviye (Gelişim, Güç & Aerobik Taban)"
            progression_next = "Lineer artış platosunda Upper/Lower bölünmesine ve ek tempo koşusuna geçilir."
        elif tot_days == 5:
            athlete_tier = "İleri Seviye (Hacim & Bölünmüş Rutinler)"
            progression_next = "Dalgalı periyodizasyon ve laktat eşiği blokları uygulanır."
        else:
            athlete_tier = "Elit / Yüksek Performans Seviyesi"
            progression_next = "Blok periyodizasyonu ve yarış zirveleme haftaları uygulanır."

        return {
            "is_current_athlete": False,
            "athlete_name": name,
            "athlete_tier": athlete_tier,
            "profile_badge": f"{name} ({r_days} Koşu + {g_days} Gym • {athlete_tier.split(' ')[0]})",
            "description": f"{name} için kişiselleştirilmiş haftalık {r_days} koşu, {g_days} kuvvet esnek kota ve beslenme planı.",
            "metrics": {
                "age": age, "gender": "Kadın" if gender == "female" else "Erkek", "height_cm": height,
                "current_weight_kg": weight, "target_weight_kg": target_weight, "current_bmi": cur_bmi, "target_bmi": tar_bmi,
                "bmr_kcal": bmr, "tdee_kcal": tdee, "target_calories_kcal": target_kcal,
                "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g,
                "days_to_goal": days_to_goal, "target_date": target_date_str,
                "weekly_running_days": r_days, "weekly_gym_days": g_days, "weekly_weight_loss_rate": loss_rate,
            },
            "schedule": schedule,
            "quota_summary": quota_summary,
            "weekly_quota": quota_summary,
            "coaching_tips": [
                f"Seviye Sınıflandırması: {athlete_tier}",
                f"Esnek Haftalık Kota: {name} için {r_days} koşu + {g_days} kuvvet kotasıyla {target_weight:.1f} kg hedefi ~{days_to_goal} günde ({target_date_str}) öngörülüyor.",
                f"Beslenme: {target_kcal} kcal, {protein_g}g protein, {carbs_g}g karbonhidrat.",
                f"Gelişim: {progression_next}",
            ],
            "progression_readiness": {"current_tier": athlete_tier, "next_milestone": progression_next},
        }

    def _build_dynamic_schedule(
        self, name: str, weight: float, r_days: int, r_style: str, g_days: int, g_routine: str,
        target_kcal: int, protein_g: int, carbs_g: int, fat_g: int, tdee: int, sec_sports: List[str], age: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """7 esnek kota slotu döner (sabit takvim günü/tarihi dayatmaz)."""
        slots = ["rest"] * 7
        if r_days == 2 and g_days == 2:
            slots = ["gym", "run", "rest", "run", "gym", "active_recovery", "rest"]
        elif r_days == 3 and g_days == 2:
            slots = ["gym", "run", "rest", "run", "gym", "run", "rest"]
        elif r_days == 4 and g_days == 1:
            slots = ["run", "gym", "run", "rest", "run", "run", "rest"]
        elif r_days == 1 and g_days == 4:
            slots = ["gym", "gym", "rest", "run", "gym", "gym", "rest"]
        else:
            g_rem, r_rem = g_days, r_days
            for d in [0, 3, 1, 4, 5, 2, 6]:
                if g_rem > 0 and slots[d] == "rest":
                    slots[d] = "gym"
                    g_rem -= 1
                elif r_rem > 0 and slots[d] == "rest":
                    slots[d] = "run"
                    r_rem -= 1
            if slots[5] == "rest" and (r_days + g_days) < 7:
                slots[5] = "active_recovery"

        run_pool, gym_pool = self._get_custom_session_pools(r_style, g_routine, age)
        run_idx, gym_idx, sched_rows = 0, 0, []
        for i in range(7):
            slot = slots[i]
            slot_num = i + 1
            if slot == "gym":
                tmpl = gym_pool[gym_idx % len(gym_pool)]
                gym_idx += 1
                sched_rows.append({
                    "day": f"Kota Slotu {slot_num} · Kuvvet #{gym_idx} (Esnek Gün)",
                    "primary": f"Kuvvet #{gym_idx} · {tmpl['title_suffix']}",
                    "secondary": tmpl["secondary"], "target": tmpl["target"],
                    "calories": f"~{tdee + 300} kcal",
                    "macro": f"{target_kcal} kcal ({protein_g}g P / {carbs_g}g K / {fat_g}g Y)",
                    "slot_kind": tmpl["slot_kind"], "is_completed": False, "is_flexible": True,
                })
            elif slot == "run":
                tmpl = run_pool[run_idx % len(run_pool)]
                run_idx += 1
                sched_rows.append({
                    "day": f"Kota Slotu {slot_num} · Koşu #{run_idx} (Esnek Gün)",
                    "primary": f"Koşu #{run_idx} · {tmpl['title_suffix']}",
                    "secondary": tmpl["secondary"], "target": tmpl["target"],
                    "calories": f"~{tdee + 400} kcal",
                    "macro": f"{target_kcal + 100} kcal ({protein_g}g P / {carbs_g + 25}g K / {fat_g}g Y)",
                    "slot_kind": tmpl["slot_kind"], "is_completed": False, "is_flexible": True,
                })
            elif slot == "active_recovery":
                sched_rows.append({
                    "day": f"Kota Slotu {slot_num} · Aktif Toparlanma (Esnek Gün)",
                    "primary": "Aktif Toparlanma / Yürüyüş & Mobilite",
                    "secondary": "30-40 dk hafif yürüyüş, esneme ve nefes egzersizi",
                    "target": "<110 bpm (Zone 1)",
                    "calories": f"~{tdee - 150} kcal",
                    "macro": f"{target_kcal - 100} kcal ({protein_g}g P / {max(60, carbs_g - 20)}g K / {fat_g}g Y)",
                    "slot_kind": "active_recovery", "is_completed": False, "is_flexible": True,
                })
            else:
                sched_rows.append({
                    "day": f"Kota Slotu {slot_num} · Dinlenme Tamponu (Esnek Gün)",
                    "primary": "Tam Dinlenme / Rejenerasyon",
                    "secondary": "Sinir sistemi ve kas toparlanması, erken uyku",
                    "target": "<100 bpm (Parasempatik gün)",
                    "calories": f"~{tdee - 250} kcal",
                    "macro": f"{target_kcal - 150} kcal ({protein_g}g P / {max(60, carbs_g - 35)}g K / {fat_g}g Y)",
                    "slot_kind": "rest", "is_completed": False, "is_flexible": True,
                })
        return sched_rows
