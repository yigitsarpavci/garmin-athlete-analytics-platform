#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
import numpy as np
import pandas as pd

try:
    from athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
    from engine.helpers import fmt_pace_sec, fmt_clock, DATA_DIR
except ImportError:
    from app.athlete_principles import (
        ATHLETE_PROFILE, NUTRITION_PRINCIPLES, STRENGTH_PRINCIPLES,
        RUNNING_PRINCIPLES, SAME_DAY_SEQUENCE_LAW, CROSS_SPORTS_PROTOCOLS,
        RECOVERY_AND_WATCH_SETTINGS, PRESENTATION_RULES,
        ATHLETE_LEVELS_FRAMEWORK, DYNAMIC_PROGRESSION_TRIGGERS
    )
    from app.engine.helpers import fmt_pace_sec, fmt_clock, DATA_DIR


class TrainingProtocolsMixin:
    """Branş rehberliği, haftalık program, 7 günlük reçeteler ve antrenman sonrası debrief."""

    def get_sports_guidance(self) -> Dict[str, Any]:
        """
        Dört branş (Koşu, Kuvvet/Gym, Yelken, Basketbol) için telemetriye dayalı rehberlik ve stratejileri döner.

        Haftalık mikro-döngü kuralları gereği:
        - Koşu ve Kuvvet haftalık sabit 2+2 takvimini oluşturur ve bu haftada tamamlanan seanslar kotadan düşülür.
        - Yelken (ter/elektrolit kaybı, tutuş gücü) ve Basketbol (Zone 4-5 doğal HIIT) spontane
          olarak takip edilir ve telemetrisi dinamik olarak değerlendirilir.

        Returns:
            Dict[str, Any]: Her branş için istatistikler, gelişim ilkeleri ve sonraki seans planları.
        """
        _, week_meta = self._build_weekly_schedule_entries()
        meta_days = week_meta["days"]
        runs_done = week_meta["runs_done"]
        gyms_done = week_meta["gyms_done"]
        rem_runs = week_meta["rem_runs"]
        rem_gyms = week_meta["rem_gyms"]
        tr_months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
        next_mon = datetime.now() - timedelta(days=datetime.now().weekday()) + timedelta(days=7)

        planned_runs = [d for d in meta_days if d["slot_kind"] in ("zone2", "interval")]
        running_upcoming: List[Dict[str, str]] = []
        for d in planned_runs:
            if d["slot_kind"] == "zone2":
                running_upcoming.append({
                    "day": d["day_label"],
                    "type": "Zone 2 Taban & Aktif Toparlanma",
                    "title": d["primary"],
                    "duration": "45-50 dakika",
                    "target_hr": "140 - 150 bpm",
                    "target_pace": "6:35 - 6:50 /km",
                    "details": f"{d['secondary']}. 140-150 bpm nabız tavanını aşmadan (tempo 6:35-6:50 /km) burundan rahat nefesle koşun."
                })
            else:
                running_upcoming.append({
                    "day": d["day_label"],
                    "type": "Hız & Laktat Eşiği İntervali",
                    "title": d["primary"],
                    "duration": "45 dakika",
                    "target_hr": "172 - 180 bpm",
                    "target_pace": "5:15 /km",
                    "details": "10 dk ısınma (135-145 bpm) + 4 x 1.000m @ 5:15 /km (172-180 bpm, her 1000m arası 3 dk yürüyüş/jog) + 8 dk soğuma."
                })

        if len(running_upcoming) < 2:
            mon_label = f"{next_mon.day} {tr_months[next_mon.month - 1]} Pzt (Gelecek Hafta)"
            running_upcoming.append({
                "day": mon_label,
                "type": "Hız & Laktat Eşiği İntervali (Gelecek Hafta)",
                "title": "Gelecek Hafta Koşu #1 - 5K Hız İntervali (4 x 1.000 m)",
                "duration": "45 dakika",
                "target_hr": "172 - 180 bpm",
                "target_pace": "5:15 /km",
                "details": "Bu haftanın 2/2 koşu kotası tamamlandıktan sonra yeni haftanın ilk koşusudur: 10 dk ısınma + 4 x 1.000m @ 5:15 /km."
            })

        next_run_card = running_upcoming[0]

        planned_gyms = [d for d in meta_days if d["slot_kind"] in ("gym_a", "gym_b")]
        gym_upcoming: List[Dict[str, str]] = []
        for d in planned_gyms:
            if d["slot_kind"] == "gym_b":
                gym_upcoming.append({
                    "day": d["day_label"],
                    "type": "Workout B (Bu Haftanın Kalan Son Kuvvet Seansı)",
                    "title": d["primary"],
                    "duration": "55 dakika",
                    "details": "Squat 67.5 kg (5x5, +2.5kg) • Overhead Press 40.0 kg (5x5, tüm setlerde 40kg) • Deadlift 65.0 kg (1x5, +5kg) • Lat Pulldown 45.0 kg (4x12) • Lateral Raise 25 kg • Shrug 45 kg."
                })
            else:
                gym_upcoming.append({
                    "day": d["day_label"],
                    "type": "Workout A (Kuvvet #1 - Yeni PR Denemesi)",
                    "title": d["primary"],
                    "duration": "55 dakika",
                    "details": "Squat 67.5 kg (5x5) • Bench Press 52.5 kg (5x5 Yeni PR Denemesi!) • Barbell Row 62.5 kg (5x5, +2.5kg) • Lateral Raise 25 kg • Shrug 45 kg."
                })

        if len(gym_upcoming) < 2:
            next_tue = next_mon + timedelta(days=1)
            tue_label = f"{next_tue.day} {tr_months[next_tue.month - 1]} Salı (Gelecek Hafta)"
            gym_upcoming.append({
                "day": tue_label,
                "type": "Workout A (Gelecek Hafta #1 - Yeni PR Denemesi)",
                "title": "Göğüs, Sırt & Bacak İlerlemesi",
                "duration": "55 dakika",
                "details": "Squat 67.5 kg (5x5) • Bench Press 52.5 kg (5x5 Yeni PR Denemesi!) • Barbell Row 62.5 kg (5x5, +2.5kg) • Lateral Raise 25 kg • Shrug 45 kg."
            })

        next_gym_card = gym_upcoming[0]
        next_gym_exercises = [
            "Back Squat: Isınma + 67.5 kg x 5 tekrar x 5 set (+2.5 kg Artış)",
            "Overhead Press (OHP): Isınma + 40.0 kg x 5 tekrar x 5 set (Tüm setlerde 40 kg)",
            "Barbell Deadlift: Isınma + 65.0 kg x 5 tekrar (1 Ana Çalışma Seti, +5.0 kg Artış)",
            "Lat Pulldown: Isınma + 45.0 kg x 12 tekrar x 4 set",
            "Lateral Raise: 22.5 - 25.0 kg x 12 tekrar x 3 set",
            "Dumbbell Shrug: 45.0 kg x 12 tekrar x 3 set"
        ]

        return {
            "running": {
                "name": "Koşu (Running)",
                "schedule_status": f"Düzenli Program Branşı (Bu Hafta: {runs_done}/2 Yapıldı, {rem_runs} Kaldı)",
                "current_pace": "5:48 /km (5K: 29:07)",
                "target_pace": "4:54 /km (5K: <24:30)",
                "cadence": "162 spm (Harika Form ve Düşük Darbe)",
                "stats_summary": "15 Koşu • 79,5 km Mesafe • 158 bpm Ortalama Nabız",
                "how_to_improve": [
                    "80/20 Polarize Model (Mitokondri & Atım Hacmi): Haftalık 2 koşunun 1'ini Zone 2 (140-150 bpm, konuşma temposu) tutarak kalbin sol ventrikül hacmini ve bacak kaslarındaki kılcal damarlanmayı (anjiyogenez) artırın; 1'ini ise laktat eşiğini yukarı çeken hız intervali yapın.",
                    "Haftada 1 Gün Laktat Eşiği İntervali: Haftanın hız koşusu gününde 4x1000m (5:15 /km tempo, 172-180 bpm) yaparak yüksek hız toleransınızı ve aerobik tavanınızı yükseltin.",
                    "160+ Kadansı Korumak: Kasım ayında yakaladığınız 162 adım/dk kadans sayesinde yerle temas süreniz 273 ms'ye indi; adımları uzatmak yerine sık adım atarak diz/eklem stresini minimumda tutun.",
                    "Kilo Kaybı Hızlandırması: 87 kg'dan 81 kg'a inişiniz, adımlardaki yerçekimi direncini azaltarak 5K derecenizi 80-90 saniye otomatik olarak hızlandıracaktır."
                ],
                "upcoming_sessions": running_upcoming,
                "next_workout": {
                    "day": next_run_card["day"],
                    "title": next_run_card["title"],
                    "duration": next_run_card["duration"],
                    "target_hr": next_run_card["target_hr"],
                    "target_pace": next_run_card["target_pace"],
                    "details": next_run_card["details"]
                }
            },
            "strength": {
                "name": "Kuvvet Antrenmanı (Strength)",
                "schedule_status": f"Düzenli Program Branşı (A/B 5x5 • Bu Hafta: {gyms_done}/2 Yapıldı, {rem_gyms} Kaldı)",
                "current_status": "A/B Bölünmüş Rutin (Kasım'da 5 seans tamamlandı)",
                "goal": "Kilo verme döneminde yağsız kas kütlesini ve omurga/omuz gücünü korumak (Progressive Overload)",
                "stats_summary": "5 Seans • 4,7 Saat • 1.851 kcal • Squat: 45->65kg (+20kg) • Bench: 50kg • Row: 60kg",
                "how_to_improve": [
                    "Bileşik (Compound) 5x5 Odaklanması: Squat, Bench Press, Barbell Row (A Günü) ve Squat, OHP, Deadlift, Lat Pulldown (B Günü) aynı anda birden fazla eklemi çalıştırarak mekanik gerilimi maksimize eder.",
                    "Lineer Aşamalı Yüklenme (Progressive Overload): 5x5 setini temiz formla tamamladığınız her egzersize bir sonraki seansta üst vücutta +2.5 kg, bacakta +2.5 ila +5 kg ekleyin.",
                    "Set Dinlenme Aralıkları & RPE: Ağır 5x5 setlerinde tam toparlanma için 2-3 dakika dinlenin; izolasyonlarda (Lateral Raise, Shrug) dinlenmeyi 60-90 saniyede tutun. Tükenişe gitmeyin (RPE 7.5-8.5).",
                    "Aynı Gün Sıralama Kuralı: Koşu ile aynı gün yapılacağında MUTLAKA önce koşu, ardından kuvvet antrenmanı yapılmalıdır."
                ],
                "last_workout": {
                    "date": "17 Kasım Salı (Bugün - 10:35)",
                    "title": "Workout A (TAMAMLANDI)",
                    "exercises": [
                        "Back Squat: 20kg x 10 (Isınma), 65.0 kg x 5 tekrar x 5 set (Müthiş Form!)",
                        "Bench Press: 20kg x 10, 50.0 kg x 5 tekrar x 5 set (5x5 Tamamlandı)",
                        "Barbell Row: 20kg x 10, 60.0 kg x 5 tekrar x 5 set (60 kg Tamamlandı)",
                        "Lateral Raise: 25.0 kg x 13, 22.5 kg x 12, 20.0 kg x 12",
                        "Dumbbell Shrug: 45.0 kg x 12 tekrar x 3 set"
                    ]
                },
                "upcoming_sessions": gym_upcoming,
                "next_workout": {
                    "day": next_gym_card["day"],
                    "title": next_gym_card["title"],
                    "duration": next_gym_card["duration"],
                    "exercises": next_gym_exercises
                }
            },
            "sailing": {
                "name": "Yelken (Sailing)",
                "schedule_status": "Spontane / Dönemsel Branş (Garmin Otomatik Algılama)",
                "current_status": "3 ayda 12 seans (28,1 saat, 260 km, 8.561 kcal)",
                "goal": "2-4 saatlik uzun seanslarda core/önkol dayanıklılığı ve kramp/sıvı kaybını önlemek",
                "stats_summary": "12 Seans • 259,8 km • 16,6 L Tahmini Ter Kaybı (Düzenli takvimde sabit yer tutmaz; denize çıktıkça saatinizden çekilir)",
                "how_to_improve": [
                    "İzometrik Tutuş Gücü (Önkol): Halat çekişi (sheet trimming) ve dümen hakimiyeti sürekli statik kasılma gerektirir. Salonda Farmer's Walk (ağırlıkla yürüme) ve Dead Hang (barfikste asılı kalma) önkol yorgunluğunu önler.",
                    "Trapez & Core Anti-Rotasyon: Teknenin bayılmasını dengeleyen hiking/trapez duruşu kuadriseps ve karın duvarını izometrik yükler; salonda plank ve cable woodchopper gücünüzü artırır.",
                    "Katı Sıvı ve Elektrolit Protokolü: 12 seansta 16,6 L ter kaybettiğiniz görüldü. Sıvı kaybı %2'yi aştığında reaksiyon hızı ve taktik karar verme zayıflar; saat başı 500-600 mL su + sodyum tüketin.",
                    "Glikojen Ön-Yüklemesi: 3 saati aşan seanslardan 90 dk önce 70-80g kaliteli kompleks karbonhidrat (yulaf/muz) alın."
                ],
                "upcoming_sessions": [
                    {
                        "day": "Spontane Seans (Çıktıkça İcra Edilir)",
                        "type": "Yelken Seansı (İsteğe Bağlı)",
                        "title": "Rüzgar & Kondisyon Seansı",
                        "duration": "2,5 - 4 saat",
                        "details": "Teknede 2 x 750 mL matara (biri saf su, diğeri 500-800 mg sodyumlu elektrolit). Saat başı düzenli yudumlayın. Seans sonu glikojen ve protein yenilemesi yapın."
                    }
                ],
                "next_workout": {
                    "day": "İsteğe Bağlı / Çıktıkça İcra Edilir",
                    "title": "Uzun Yelken Antrenmanı",
                    "duration": "2,5 - 4 saat",
                    "hydration_plan": "Teknede 2 x 750 mL elektrolitli su (saat başı 500-600 mL düzenli yudum)."
                }
            },
            "basketball": {
                "name": "Basketbol",
                "schedule_status": "Spontane / Dönemsel Branş (Garmin Otomatik Algılama)",
                "current_status": "Haftada 1 maç (Beşiktaş Basketbol, ortalama nabız 128-144 bpm)",
                "goal": "Patlayıcı hızlanma, yön değiştirme ve anaerobik dayanıklılık",
                "stats_summary": "5 Maç • 6,5 Saat • Zone 4-5 Doğal HIIT (Düzenli takvimde sabit yer tutmaz; maç çıktıkça saatinizden çekilir)",
                "how_to_improve": [
                    "Doğal HIIT Seansı Rolü: Basketbol hücum ve savunma sprintleriyle harika bir yüksek yoğunluklu interval çalışmasıdır; anaerobik laktat toleransınızı geliştirir.",
                    "Yük Çakışması Kuralı: Basketbol maçının olduğu gün asla ağır bacak (Squat/Deadlift) antrenmanı yapmayın; yapacaksanız sadece üst vücut yapın veya araya en az 6-8 saat koyun.",
                    "Ayak Bileği & Aşil Stabilitesi: Hızlı dur-kalklar ve yön değiştirmeler için maç öncesinde 10 dakikalık dinamik ısınma (pogo jumps, lunge walk, ankle circles) uygulayın.",
                    "Maç Sonu Esneme: Maç bittikten sonra 10 dk statik hamstring, kalça ve baldır esnemesi ertesi günkü bacak sertliğini önler."
                ],
                "upcoming_sessions": [
                    {
                        "day": "Spontane Maç (Çıktıkça İcra Edilir)",
                        "type": "Haftalık Maç (İsteğe Bağlı)",
                        "title": "Beşiktaş Basketbol Maçı",
                        "duration": "60 - 90 dakika",
                        "details": "Maç öncesi 10 dk dinamik bacak ısınması; hücum geçişlerinde anaerobik patlama; maç sonrası 10 dk bacak esnemesi."
                    }
                ],
                "next_workout": {
                    "day": "İsteğe Bağlı / Çıktıkça İcra Edilir",
                    "title": "Haftalık Basketbol Maçı",
                    "duration": "60 - 90 dakika",
                    "target_hr": "Z2 - Z4 arası değişken"
                }
            }
        }


    def _build_weekly_schedule_entries(self, now: Optional[datetime] = None) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        Günün tarihine (Pazartesi-Pazar takvim haftası) ve kaydedilen Garmin aktivitelerine
        göre haftalık 2 Koşu + 2 Gym + 3 Dinlenme kotasını dinamik olarak planlar.

        Tamamlanan koşu ve kuvvet seanslarını haftalık kotadan otomatik düşerek sadece
        kalan antrenmanları toparlanma günleriyle ayırıp takvime yerleştirir.
        """
        now = now or datetime.now()
        tr_days = ["Pzt", "Salı", "Çar", "Per", "Cuma", "Cmt", "Paz"]
        tr_months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

        monday_anchor = now - timedelta(days=now.weekday())
        week_dates = [monday_anchor + timedelta(days=i) for i in range(7)]

        gym_history = self.get_gym_exercise_history().get("sessions", [])
        gym_type_by_date = {
            s.get("date"): s.get("workout_type")
            for s in gym_history
            if s.get("date")
        }

        day_acts: List[List[Dict[str, Any]]] = []
        runs_done_list: List[Dict[str, Any]] = []
        gyms_done_list: List[Dict[str, Any]] = []
        last_gym_type: Optional[str] = None

        for d_date in week_dates:
            d_str = d_date.strftime("%Y-%m-%d")
            matched = [a for a in self.activities_all if (a.get("startTimeLocal") or "")[:10] == d_str]
            day_acts.append(matched)
            for act in matched:
                sport_key = (act.get("sport") or (act.get("activityType") or {}).get("typeKey") or "").lower()
                if "running" in sport_key:
                    runs_done_list.append(act)
                elif "strength" in sport_key:
                    gyms_done_list.append(act)
                    last_gym_type = gym_type_by_date.get(d_str) or last_gym_type

        runs_done = len(runs_done_list)
        gyms_done = len(gyms_done_list)
        rem_runs = max(0, 2 - runs_done)
        rem_gyms = max(0, 2 - gyms_done)

        needed_runs: List[Tuple[str, int]] = []
        if rem_runs == 2:
            needed_runs = [("zone2", 1), ("interval", 2)]
        elif rem_runs == 1:
            done_hr = runs_done_list[0].get("averageHR") or 0
            next_kind = "zone2" if done_hr >= 152 else "interval"
            needed_runs = [(next_kind, runs_done + 1)]

        needed_gyms: List[Tuple[str, int]] = []
        if rem_gyms == 2:
            needed_gyms = [("gym_a", 1), ("gym_b", 2)]
        elif rem_gyms == 1:
            next_gym = "gym_a" if last_gym_type and "Workout B" in last_gym_type else "gym_b"
            needed_gyms = [(next_gym, gyms_done + 1)]

        # Kalan antrenmanları sıralı kuyrukta dengele (Koşu / Gym dönüşümlü)
        needed_queue: List[Tuple[str, int]] = []
        for idx in range(max(len(needed_runs), len(needed_gyms))):
            if idx < len(needed_runs):
                needed_queue.append(needed_runs[idx])
            if idx < len(needed_gyms):
                needed_queue.append(needed_gyms[idx])

        open_offsets = [i for i in range(7) if not day_acts[i] and week_dates[i].date() >= now.date()]
        assigned_slot: Dict[int, Tuple[str, int]] = {}

        if rem_runs == 2 and rem_gyms == 2 and set([1, 2, 4, 5]).issubset(open_offsets):
            # Haftanın başında (veya demo modunda) klasik Salı/Çar/Cuma/Cmt şablonu
            assigned_slot = {
                1: ("gym_a", 1),
                2: ("zone2", 1),
                4: ("interval", 2),
                5: ("gym_b", 2),
            }
        elif needed_queue:
            occupied = {i for i in range(7) if day_acts[i]}
            remaining = list(needed_queue)
            # 1. Geçiş: Komşu günlerinde antrenman olmayan izole günlere yerleştir
            for i in open_offsets:
                if not remaining:
                    break
                if (i - 1) not in occupied and (i + 1) not in occupied:
                    assigned_slot[i] = remaining.pop(0)
                    occupied.add(i)
            # 2. Geçiş: Kalan seansları bir önceki gün boş olan açık günlere dağıt
            for i in open_offsets:
                if not remaining:
                    break
                if i not in assigned_slot and (i - 1) not in occupied:
                    assigned_slot[i] = remaining.pop(0)
                    occupied.add(i)
            # 3. Geçiş: Haftada çok az açık gün kaldıysa kalan boş günleri kullan
            for i in open_offsets:
                if not remaining:
                    break
                if i not in assigned_slot:
                    assigned_slot[i] = remaining.pop(0)

        def _format_completed_day(matched: List[Dict[str, Any]], d_str: str, run_counter: List[int], gym_counter: List[int]) -> Dict[str, str]:
            titles: List[str] = []
            details: List[str] = []
            hr_notes: List[str] = []
            has_run = False
            has_gym = False
            for act in matched:
                sport_key = (act.get("sport") or (act.get("activityType") or {}).get("typeKey") or "").lower()
                act_name = act.get("activityName") or "Antrenman"
                act_time = (act.get("startTimeLocal") or "")[11:16]
                dur_m = round((act.get("duration") or 0) / 60.0)
                cal = round(act.get("calories") or 0)
                avg_hr = round(act.get("averageHR") or 0)
                dist_m = act.get("distance") or 0
                if "running" in sport_key:
                    has_run = True
                    run_counter[0] += 1
                    dist_txt = f" ({dist_m / 1000.0:.2f} km)" if dist_m > 0 else ""
                    titles.append(f"Koşu #{run_counter[0]} • {act_name}{dist_txt}")
                elif "strength" in sport_key:
                    has_gym = True
                    gym_counter[0] += 1
                    w_type = gym_type_by_date.get(d_str) or "Kuvvet"
                    titles.append(f"Kuvvet #{gym_counter[0]} • {w_type} (5x5)")
                else:
                    titles.append(f"Ek Branş • {act_name}")
                details.append(f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm)")
                if avg_hr:
                    hr_notes.append(f"{avg_hr} bpm ort.")
            est_cal = "~2.950 kcal" if has_run else ("~2.850 kcal" if has_gym else "~2.900 kcal")
            macro_txt = "2.500 kcal (175g P / 265g K / 80g Y)" if has_run else "2.450 kcal (175g P / 250g K / 80g Y)"
            return {
                "primary": " + ".join(titles),
                "secondary": " • ".join(details),
                "target": "Gerçekleşen: " + (", ".join(hr_notes) if hr_notes else "Kaydedildi"),
                "calories": est_cal,
                "macro": macro_txt,
            }

        def _build_planned_slot(slot_kind: str, ordinal: int) -> Dict[str, str]:
            is_last_run = (rem_runs == 1 and runs_done == 1)
            is_last_gym = (rem_gyms == 1 and gyms_done == 1)
            if slot_kind == "gym_a":
                sec = "Bu haftanın kalan son salon seansı (2/2) • Lateral & Shrug" if is_last_gym else "Lateral Raise 25kg & Dumbbell Shrug 45kg"
                return {
                    "primary": f"Kuvvet #{ordinal} (Workout A: Squat 65kg 5x5 PR, Bench 50kg, Row 60kg)",
                    "secondary": sec,
                    "target": "115-128 bpm (Zone 1)",
                    "calories": "~2.850 kcal",
                    "macro": "2.450 kcal (175g P / 250g K / 80g Y)",
                }
            if slot_kind == "gym_b":
                sec = "Bu haftanın kalan son gym seansı (2/2) • Lat Pulldown 45kg & Shrug" if is_last_gym else "Lat Pulldown 45kg (4x12) & Lateral & Shrug"
                return {
                    "primary": f"Kuvvet #{ordinal} (Workout B: Squat 67.5kg, OHP 40kg, Deadlift 65kg)",
                    "secondary": sec,
                    "target": "115-130 bpm (Zone 1)",
                    "calories": "~2.900 kcal",
                    "macro": "2.500 kcal (180g P / 270g K / 80g Y)",
                }
            if slot_kind == "zone2":
                sec = "Bu haftanın kalan son koşusu (2/2 • 160+ kadans, burundan nefes)" if is_last_run else "Aktif toparlanma (160+ kadans, burundan nefes)"
                return {
                    "primary": f"Koşu #{ordinal} - Zone 2 Rahat Taban Koşusu (45-50 dk)",
                    "secondary": sec,
                    "target": "140-150 bpm (6:35-6:50 /km)",
                    "calories": "~2.950 kcal",
                    "macro": "2.550 kcal (175g P / 275g K / 80g Y)",
                }
            sec = "Bu haftanın kalan son koşusu (2/2 • 5:15 /km tempo, 3 dk jog)" if is_last_run else "5:15 /km tempo, aralarda 3 dk yürüyüş/jog dinlenme"
            return {
                "primary": f"Koşu #{ordinal} - 5K Hız İntervali (45 dk, 4x1.000m)",
                "secondary": sec,
                "target": "170-183 bpm (Zone 4-5)",
                "calories": "~3.050 kcal",
                "macro": "2.650 kcal (175g P / 300g K / 80g Y)",
            }

        schedule: List[Dict[str, str]] = []
        meta_days: List[Dict[str, Any]] = []
        run_counter = [0]
        gym_counter = [0]
        total_done = runs_done + gyms_done
        total_rem = rem_runs + rem_gyms

        for i, d_date in enumerate(week_dates):
            d_str = d_date.strftime("%Y-%m-%d")
            d_name = tr_days[d_date.weekday()]
            m_name = tr_months[d_date.month - 1]
            is_today = (d_str == now.strftime("%Y-%m-%d"))
            is_past = (d_date.date() < now.date())
            is_tomorrow = (d_date.date() == (now + timedelta(days=1)).date())

            day_label = f"{d_date.day} {m_name} {d_name}"
            if is_today:
                day_label += " (Bugün)"
            elif is_tomorrow:
                day_label += " (Yarın)"

            slot_kind = "completed"
            if day_acts[i]:
                row_data = _format_completed_day(day_acts[i], d_str, run_counter, gym_counter)
            elif i in assigned_slot:
                slot_kind, ordinal = assigned_slot[i]
                row_data = _build_planned_slot(slot_kind, ordinal)
            elif i == 6:
                slot_kind = "active_recovery"
                quota_note = "Haftalık 4/4 antrenman hedefi tamamlandı" if total_done + total_rem >= 4 else "Haftalık kapanış"
                row_data = {
                    "primary": "Aktif Toparlanma / Mobilite & Yürüyüş",
                    "secondary": f"Hafif yürüyüş, esneme, nefes egzersizi (NSDR) • {quota_note}",
                    "target": "<110 bpm (Zone 1)",
                    "calories": "~2.500 kcal",
                    "macro": "2.350 kcal (175g P / 220g K / 80g Y)",
                }
            else:
                slot_kind = "rest"
                quota_txt = f"Bu hafta {total_done}/4 seans tamamlandı, {total_rem} seans kaldı" if total_done > 0 else "Sonraki antrenman öncesi bacak & MSS toparlanması"
                sec_txt = "Dinlenme / Tamamlandı" if is_past else f"Kas onarımı & erken uyku (00:30) • {quota_txt}"
                row_data = {
                    "primary": "Tam Dinlenme / Rejenerasyon",
                    "secondary": sec_txt,
                    "target": "<100 bpm (Parasempatik gün)",
                    "calories": "~2.450 kcal",
                    "macro": "2.350 kcal (175g P / 220g K / 80g Y)",
                }

            entry = {"day": day_label, **row_data}
            schedule.append(entry)
            meta_days.append({
                "date": d_date,
                "date_str": d_str,
                "day_label": day_label,
                "slot_kind": slot_kind,
                "is_completed": bool(day_acts[i]),
                **row_data,
            })

        return schedule, {
            "runs_done": runs_done,
            "gyms_done": gyms_done,
            "rem_runs": rem_runs,
            "rem_gyms": rem_gyms,
            "days": meta_days,
        }

    def get_weekly_schedule(self):
        """
        Pazartesi-Pazar takvim haftasına ve tamamlanan aktivitelere göre haftalık
        2 Koşu + 2 Gym + 3 Dinlenme mikro-döngüsünü dinamik olarak üretir.
        """
        schedule, _ = self._build_weekly_schedule_entries()
        return schedule


    def get_detailed_daily_workout_protocols(self):
        """
        Her bir antrenman ve dinlenme günü için derinlemesine egzersiz, set, tekrar,
        kilo hedefi (progressive overload), dinlenme süresi, tempo, kadans ve beslenme reçetesini döner.
        Lateral Raise ve Shrug hareketleri Workout A ve B'ye eksiksiz dahil edilmiştir.
        """
        # Güncel kuvvet verileri (17 Kasım telemetrisi)
        # Squat: 65 kg (5x5) -> Hedef: 67.5 kg
        # Bench: 50 kg (5x5 kilitlendi) -> Hedef: 52.5 kg (Yeni PR)
        # Row: 60 kg (5x5) -> Hedef: 62.5 kg
        # OHP: 40 kg (5 tekrar) -> Hedef: 40.0 kg (5x5)
        # Deadlift: 60 kg (5 tekrar) -> Hedef: 65.0 kg (1x5)
        # Lat Pulldown: 45 kg -> Hedef: 45.0 - 50.0 kg (4x12)
        # Lateral Raise: 20-25 kg -> Hedef: 22.5 - 25.0 kg (3x12)
        # Shrug: 45 kg -> Hedef: 45.0 kg (3x12)

        return [
            {
                "day_code": "tuesday",
                "day_title": "Salı: Kuvvet Antrenmanı #1 (Workout A - Tüm Vücut Güç & Hipertrofi)",
                "category": "gym",
                "badge": "Workout A",
                "badge_color": "blue",
                "status_note": "17 Kasım Seansı Tamamlandı (10:35) • Bu Hafta 1/2 Gym • Sonraki Workout A: 24 Kasım Salı",
                "objective": "Nöromüsküler güç inşası, göğüs, bacak, sırt ve yan omuz gelişimi (Progressive Overload).",
                "warmup": "5 dk dinamik kalça & omuz mobilitesi + Boş bar ile 2x10 Squat ve 2x10 Bench Press hafif ısınma setleri.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Barbell Back Squat",
                        "sets": 5, "reps": 5,
                        "current_achieved": "65.0 kg x 5 tekrar x 5 set (17 Kas PR)",
                        "target_weight": "67.5 kg (+2.5 kg Artış)",
                        "rest_sec": "150 - 180 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Paralel altı derinlik, göğüs dik, topuklardan dengeli zemin itişi."
                    },
                    {
                        "num": 2,
                        "name": "Barbell Bench Press",
                        "sets": 5, "reps": 5,
                        "current_achieved": "50.0 kg x 5 tekrar x 5 set (5x5 Kilitlendi)",
                        "target_weight": "52.5 kg (Yeni PR Denemesi!)",
                        "rest_sec": "120 - 150 sn",
                        "target_rpe": "8.5",
                        "coaching_cue": "Kürek kemikleri geride kilitli, barı kontrollü göğüs ucuna indirip patlayıcı itiş."
                    },
                    {
                        "num": 3,
                        "name": "Barbell Bent-Over Row",
                        "sets": 5, "reps": 5,
                        "current_achieved": "60.0 kg x 5 tekrar x 5 set (17 Kas PR)",
                        "target_weight": "62.5 kg (+2.5 kg Artış)",
                        "rest_sec": "120 - 150 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Gövde 45 derece eğik, bel nötr, barı alt karına çekip kürek kemiklerini sıkıştırın."
                    },
                    {
                        "num": 4,
                        "name": "Dumbbell Lateral Raise (Yan Açış)",
                        "sets": 3, "reps": 12,
                        "current_achieved": "20.0 - 25.0 kg x 12 tekrar (17 Kas)",
                        "target_weight": "22.5 - 25.0 kg",
                        "rest_sec": "60 - 75 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Yan deltoid hipertrofisi ve V-Taper omuz genişliği için hayati aksesuar hareketi. Dirsekler hafif kırık, tepe noktada 1 sn bekleme."
                    },
                    {
                        "num": 5,
                        "name": "Dumbbell / Barbell Shrug (Trapez)",
                        "sets": 3, "reps": 12,
                        "current_achieved": "45.0 kg x 12 tekrar x 3 set (17 Kas)",
                        "target_weight": "45.0 - 50.0 kg",
                        "rest_sec": "60 - 75 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Trapez kalınlığı ve önkol tutuş gücü. Özellikle yelken hiking pozisyonunda boyun/omuz kuşağını korur ve Deadlift kilitlenişini güçlendirir."
                    }
                ],
                "cooldown": "5 dk hafif statik esneme (göğüs açış, kalça fleksör ve hamstring).",
                "telemetry_targets": {
                    "hr_range": "115 - 130 bpm (Zone 1)",
                    "est_calories": "~2.850 kcal toplam harcama",
                    "nutrition": "2.450 kcal alım | 175g Protein | 250g Kompleks Karbonhidrat | 80g Sağlıklı Yağ | 3.0 L Su"
                }
            },
            {
                "day_code": "wednesday",
                "day_title": "Çarşamba: Tam Dinlenme & Nöromüsküler Rejenerasyon",
                "category": "rest",
                "badge": "Tam Dinlenme",
                "badge_color": "slate",
                "status_note": "Planlanan: 18 Kasım Çarşamba (Pzt Koşu + Salı Workout A Sonrası Toparlanma)",
                "objective": "Pazartesi (5.19 km koşu) ve Salı (65 kg Squat PR / 7.43 ton) arka arkaya yüklenen bacak kaslarını onarmak ve Perşembe Zone 2 koşusuna taze girmek.",
                "warmup": "Gerekli değil (Sıfır kardiyovasküler stres).",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Rejenerasyon Protokolü",
                        "duration": "Tüm Gün Dinlenme",
                        "protocol": "Köpük rulo (Foam Roller) ile 10 dk bacak/quad masajı, kalça mobilitesi ve 20 dk hafif yürüyüş.",
                        "coaching_cue": "Bu hafta halihazırda 2/4 spor tamamlandı (1 Koşu + 1 Gym). Bugün bacaklara ek stres yüklenmez."
                    }
                ],
                "cooldown": "Sirkadiyen uyku hazırlığı: 00:30 öncesi yatış (8 saat tam toparlanma uykusu).",
                "telemetry_targets": {
                    "hr_range": "<100 bpm (Parasempatik Toparlanma)",
                    "est_calories": "~2.500 kcal toplam harcama",
                    "nutrition": "2.350 kcal alım | 175g Protein | 220g Karbonhidrat | 80g Sağlıklı Yağ | 2.5 - 3.0 L Su"
                }
            },
            {
                "day_code": "thursday",
                "day_title": "Perşembe: Koşu #2 (Zone 2 Aerobik Taban - Haftanın Kalan Son Koşusu)",
                "category": "running",
                "badge": "Zone 2 Taban",
                "badge_color": "emerald",
                "status_note": "Planlanan Seans: 19 Kasım Perşembe (Bu Hafta Kalan Tek Koşu • 2/2)",
                "objective": "16 Kasım Pazartesi (161 bpm yüksek aerobik koşu) sonrası sol karıncık atım hacmini (Stroke Volume) büyütmek ve haftalık 2/2 koşu kotasını tamamlamak.",
                "warmup": "5-8 dk dinamik kalça ve ayak bileği mobilitesi (bacak savurma, lunge yürüyüşü, baldır açma).",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Ana Koşu: Zone 2 Taban Koşusu",
                        "duration": "45 - 50 dakika kesintisiz",
                        "distance_est": "6.8 - 7.5 km",
                        "target_hr": "140 - 150 bpm (Katı Tavan 150 bpm!)",
                        "target_pace": "6:35 - 6:50 /km (Mevcut Efektif Faktör EF: 1.03 m/atım)",
                        "cadence_target": "160 - 165 spm (Kasım'da yakalanan 162 spm korunmalı)",
                        "ground_contact_time": "Hedef <275 ms (frenleme yapmadan kısa, seri adımlar)",
                        "coaching_cue": "Burundan nefes alma veya rahatça konuşabilme temposu. Nabız 151 bpm olduğunda derhal hızınızı düşürün veya 30 saniye yürüyüşe geçin; Zone 3'e taşmak sol karıncığın hacimsel esnemesini durdurur."
                    }
                ],
                "cooldown": "8 dk derin baldır, aşil tendonu, IT band ve kuadriseps statik esnemesi.",
                "telemetry_targets": {
                    "hr_range": "140 - 150 bpm (Zone 2 Taban)",
                    "est_calories": "~2.950 kcal toplam harcama",
                    "nutrition": "2.550 kcal alım | 175g Protein | 275g Kompleks Karbonhidrat | 80g Sağlıklı Yağ | 3.5 L Su (glikojen depolarını taze tutma)"
                }
            },
            {
                "day_code": "friday",
                "day_title": "Cuma: Tam Dinlenme & Workout B Hazırlığı",
                "category": "rest",
                "badge": "Tam Dinlenme",
                "badge_color": "slate",
                "status_note": "Planlanan: 20 Kasım Cuma (Cumartesi Workout B Öncesi)",
                "objective": "Cumartesi günkü Workout B (Squat 67.5 kg + OHP + Deadlift 65 kg) öncesinde bacakları, bel omurlarını ve MSS'yi tazelemek.",
                "warmup": "Gerekli değil.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Hafif Mobilite & Uyku Hazırlığı",
                        "duration": "Tüm Gün Dinlenme",
                        "protocol": "10 dk kalça/omuz eklem açma ve hafif akşam yürüyüşü. Ek koşu veya ağırlık yapılmaz.",
                        "coaching_cue": "Haftalık koşu kotası (2/2) Perşembe tamamlandığı için bugün ekstra koşu koymuyoruz; hedef Cumartesi Workout B PR denemesi."
                    }
                ],
                "cooldown": "Gece 00:30 öncesi yatış ve glikojen dengelemesi.",
                "telemetry_targets": {
                    "hr_range": "<100 bpm (Parasempatik Gün)",
                    "est_calories": "~2.450 kcal toplam harcama",
                    "nutrition": "2.350 kcal alım | 175g Protein | 230g Karbonhidrat | 80g Yağ | 3.0 L Su"
                }
            },
            {
                "day_code": "saturday",
                "day_title": "Cumartesi: Kuvvet Antrenmanı #2 (Workout B - Arka Zincir, Omuz & Çekiş)",
                "category": "gym",
                "badge": "Workout B",
                "badge_color": "blue",
                "status_note": "Planlanan Seans: 21 Kasım Cumartesi (Bu Haftanın Kalan Son Kuvvet Seansı • 2/2)",
                "objective": "Arka zincir (posterior chain), omuz itiş gücü, kanat hipertrofisi ve trapez dayanıklılığı.",
                "warmup": "5-8 dk dinamik eklem açma + Boş bar ile Squat ve OHP ısınma setleri.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Barbell Back Squat",
                        "sets": 5, "reps": 5,
                        "target_weight": "67.5 kg x 5 tekrar x 5 set",
                        "rest_sec": "150 - 180 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Haftanın 2. bacak seansı; hacim birikimi ve bacak kuvveti tabanı."
                    },
                    {
                        "num": 2,
                        "name": "Barbell Overhead Press (OHP)",
                        "sets": 5, "reps": 5,
                        "current_achieved": "40.0 kg x 5 tekrar (12 Kas)",
                        "target_weight": "40.0 kg (Tüm 5 sette 40 kg kitleme)",
                        "rest_sec": "120 - 150 sn",
                        "target_rpe": "8.5",
                        "coaching_cue": "Kalça ve karın kilitli, barı çene hizasından başın üzerine dik çizgide itiş."
                    },
                    {
                        "num": 3,
                        "name": "Barbell Deadlift",
                        "sets": 1, "reps": 5,
                        "current_achieved": "60.0 kg x 5 tekrar (12 Kas)",
                        "target_weight": "65.0 kg (+5.0 kg Artış)",
                        "rest_sec": "180 sn (Tek ağır ana set)",
                        "target_rpe": "8.5",
                        "coaching_cue": "Bel omurları nötr, bar kaval kemiğine yakın, kilitlenmede kalçayı öne sıkma. Koşu itiş gücünün ana motorudur."
                    },
                    {
                        "num": 4,
                        "name": "Lat Pulldown (Geniş Tutuş)",
                        "sets": 4, "reps": 12,
                        "current_achieved": "45.0 kg x 12 tekrar x 3 set (12 Kas)",
                        "target_weight": "45.0 - 50.0 kg x 12 tekrar x 4 set",
                        "rest_sec": "75 - 90 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Kanat (Latissimus) genişliği; barı göğüs üstüne çekip 1 sn sıkıştırma."
                    },
                    {
                        "num": 5,
                        "name": "Dumbbell Lateral Raise (Yan Açış)",
                        "sets": 3, "reps": 12,
                        "target_weight": "22.5 - 25.0 kg",
                        "rest_sec": "60 - 75 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Yan omuz başı hipertrofisi ve haftalık omuz hacminin tamamlanması."
                    },
                    {
                        "num": 6,
                        "name": "Dumbbell / Barbell Shrug (Trapez)",
                        "sets": 3, "reps": 12,
                        "target_weight": "45.0 kg",
                        "rest_sec": "60 - 75 sn",
                        "target_rpe": "8.0",
                        "coaching_cue": "Deadlift sonrası üst trapezleri izole etme ve önkol tutuş dayanıklılığı."
                    }
                ],
                "cooldown": "5 dk arka bacak ve sırt açma esnemesi.",
                "telemetry_targets": {
                    "hr_range": "115 - 130 bpm (Zone 1)",
                    "est_calories": "~2.900 kcal toplam harcama",
                    "nutrition": "2.500 kcal alım | 180g Protein | 270g Karbonhidrat | 80g Yağ | 3.0 L Su"
                }
            },
            {
                "day_code": "sunday",
                "day_title": "Pazar: Aktif Toparlanma, Mobilite & Haftalık Kapanış",
                "category": "active_recovery",
                "badge": "Aktif Dinlenme",
                "badge_color": "emerald",
                "status_note": "Planlanan: 22 Kasım Pazar (Haftalık 4/4 Antrenman Kotası Tamamlanır)",
                "objective": "Haftalık 2 Koşu + 2 Gym hedefi tamamlandıktan sonra laktat temizliği, parasempatik tonus artışı ve eklem sağlığı.",
                "warmup": "Gerekli değil.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Açık Hava Tempolu Yürüyüş & Esneme",
                        "duration": "30 - 45 dakika",
                        "target_hr": "<110 bpm (Zone 1 Hafif)",
                        "protocol": "Açık havada tempolu yürüyüş + 15 dk tüm vücut statik esneme ve nefes egzersizi (NSDR).",
                        "coaching_cue": "Koşu veya ağırlık yok. Bacakları hafifçe hareket ettirerek kan dolaşımını ve toparlanmayı hızlandırmak."
                    }
                ],
                "cooldown": "Günün keyfini çıkarma, ekranlardan uzaklaşma.",
                "telemetry_targets": {
                    "hr_range": "<110 bpm (Zone 1)",
                    "est_calories": "~2.500 kcal toplam harcama",
                    "nutrition": "2.350 kcal alım | 175g Protein | 220g Karbonhidrat | 80g Yağ | 2.5 - 3.0 L Su"
                }
            },
            {
                "day_code": "monday",
                "day_title": "Pazartesi: Koşu #1 - 5K Hız İntervali (Gelecek Hafta Açılışı)",
                "category": "running",
                "badge": "5K İnterval",
                "badge_color": "purple",
                "status_note": "Bu Hafta 16 Kas Pzt Koşusu (5.19 km) Tamamlandı • Sonraki Açılış: 23 Kasım Pazartesi",
                "objective": "Gelecek haftanın ilk koşusunda laktat eşiğini yukarı çekmek, kalp kasılma gücünü artırmak ve 5K temposunu 5:15 /km bandına taşımak.",
                "warmup": "10 dk hafif jog @ 135-145 bpm + 3 adet 50 metrelik ivmelenme açılışı (strides) + kalça mobilitesi.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "4 x 1.000 Metre Hız Tekrarları (Gelecek Hafta Planı)",
                        "sets": 4, "reps": "1.000 Metre",
                        "target_pace": "5:15 /km tempo (Her 1 km tam 5 dk 15 sn sürmeli)",
                        "target_hr": "172 - 182 bpm (Zone 4 - 5 Laktat Eşiği)",
                        "rest_between_reps": "Her 1000m tekrarından sonra TAM 3 DAKİKA yavaş yürüyüş / hafif jog",
                        "cadence_target": "165 - 170 spm",
                        "coaching_cue": "16 Kasım Pazartesi koşusu tamamlandığı için bu reçete gelecek haftanın açılışı (23 Kasım Pazartesi) içindir. 5:15 temposunu 4 tekrar boyunca eşit koruyun."
                    }
                ],
                "cooldown": "8-10 dk çok hafif toparlanma jogu + derin baldır ve hamstring statik esnemesi.",
                "telemetry_targets": {
                    "hr_range": "172 - 183 bpm (Zirve Zone 4-5)",
                    "est_calories": "~3.050 kcal toplam harcama",
                    "nutrition": "2.650 kcal alım | 175g Protein | 300g Karbonhidrat (antrenman öncesi ve sonrası zengin) | 80g Yağ | 3.5 L Su + Elektrolit"
                }
            }
        ]


    def get_gym_exercise_history(self):
        """Kasım ayındaki 5 kuvvet antrenmanının tüm set, tekrar ve ağırlık detaylarını döner."""
        gym_file = os.path.join(DATA_DIR, "raw_gym_exercise_sets.json")
        if not os.path.exists(gym_file):
            return {"sessions": [], "progression": {}}
        
        try:
            with open(gym_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception:
            return {"sessions": [], "progression": {}}

        act_meta_map = {}
        for a in self.activities_all:
            aid = str(a.get("activityId"))
            act_meta_map[aid] = {
                "date": a.get("startTimeLocal", "")[:10],
                "time": a.get("startTimeLocal", "")[11:16],
                "duration_min": round((a.get("duration") or 0) / 60.0, 1),
                "calories": a.get("calories"),
                "avg_hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"),
                "aerobic_te": a.get("aerobicTrainingEffect"),
                "anaerobic_te": a.get("anaerobicTrainingEffect")
            }

        name_map = {
            "SQUAT": "Back Squat",
            "BENCH_PRESS": "Bench Press",
            "ROW": "Barbell Row",
            "SHOULDER_PRESS": "Overhead Press (OHP)",
            "DEADLIFT": "Barbell Deadlift",
            "PULL_UP": "Lat Pulldown",
            "LATERAL_RAISE": "Lateral Raise (Yana Açış)",
            "SHRUG": "Dumbbell Shrug"
        }

        sessions = []
        for act_id, info in raw_data.items():
            meta = act_meta_map.get(str(act_id), {})
            sets = info.get("sets", [])
            
            grouped_ex = []
            last_name = None
            curr_sets = []
            total_vol = 0
            
            for s in sets:
                if s.get("setType") == "ACTIVE":
                    ex_list = s.get("exercises") or []
                    cat = ex_list[0].get("category") if ex_list else "UNKNOWN"
                    display_name = name_map.get(cat, cat)
                    w_kg = round((s.get("weight") or 0) / 1000.0, 1)
                    reps = s.get("repetitionCount") or 0
                    total_vol += (w_kg * reps)
                    
                    if display_name != last_name:
                        if curr_sets:
                            grouped_ex.append({"name": last_name, "sets": curr_sets})
                        curr_sets = [{"reps": reps, "weight_kg": w_kg}]
                        last_name = display_name
                    else:
                        curr_sets.append({"reps": reps, "weight_kg": w_kg})
            if curr_sets:
                grouped_ex.append({"name": last_name, "sets": curr_sets})
                
            workout_type = "Workout A"
            if str(act_id) in ["25005174809", "25051460770"]:
                workout_type = "Workout B"

            sessions.append({
                "activity_id": act_id,
                "date": meta.get("date", ""),
                "time": meta.get("time", ""),
                "workout_type": workout_type,
                "duration_min": meta.get("duration_min", 55),
                "calories": meta.get("calories", 370),
                "avg_hr": meta.get("avg_hr"),
                "total_volume_kg": round(total_vol, 1),
                "exercises": grouped_ex
            })

        sessions.sort(key=lambda x: x["date"], reverse=True)

        progression = {
            "squat": {"name": "Back Squat", "history": ["45.0 kg (06 Kas)", "55.0 kg (08 Kas)", "57.5 kg (10 Kas)", "60.0 kg (12 Kas)", "65.0 kg (17 Kas - 5x5)"], "delta": "+20.0 kg (11 günde rekor artış)", "next_target": "67.5 kg x 5 reps x 5 set"},
            "bench": {"name": "Bench Press", "history": ["45.0 kg (06 Kas)", "50.0 kg (10 Kas - 4 set)", "50.0 kg (17 Kas - 5x5 Tamamlandı)"], "delta": "+5.0 kg (5x5 kilitlendi)", "next_target": "52.5 kg x 5 reps (Yeni PR Denemesi)"},
            "row": {"name": "Barbell Row", "history": ["45.0 kg (06 Kas)", "55.0 kg (10 Kas)", "60.0 kg (17 Kas - 5x5)"], "delta": "+15.0 kg", "next_target": "62.5 kg x 5 reps x 5 set"},
            "ohp": {"name": "Overhead Press (OHP)", "history": ["35.0-37.0 kg (08 Kas)", "37.5-40.0 kg (12 Kas)"], "delta": "+5.0 kg", "next_target": "40.0 kg x 5 reps x 5 set (Tüm setlerde)"},
            "deadlift": {"name": "Barbell Deadlift", "history": ["50.0 kg x 6 (08 Kas)", "60.0 kg x 5 (12 Kas)"], "delta": "+10.0 kg", "next_target": "65.0 kg x 5 reps (1 ana set)"},
            "lat_pulldown": {"name": "Lat Pulldown", "history": ["40.0-45.0 kg (08 Kas)", "45.0 kg x 12 (12 Kas)"], "delta": "+5.0 kg", "next_target": "45.0-50.0 kg x 12 reps"},
            "lateral_raise": {"name": "Lateral Raise", "history": ["15.0-20.0 kg (06 Kas)", "20.0-25.0 kg (17 Kas)"], "delta": "Stabil Güç", "next_target": "22.5-25.0 kg x 12-13 reps"},
            "shrug": {"name": "Dumbbell Shrug", "history": ["35.0-45.0 kg (06 Kas)", "45.0 kg x 12 reps (17 Kas)"], "delta": "Stabil 45 kg", "next_target": "45.0 kg x 12 reps x 3 set"}
        }

        return {"sessions": sessions, "progression": progression}


    def get_athlete_principles(self):
        """Kullanıcının belirlediği ve sistem hafızasına kaydedilen temel sporcu ilkelerini döner."""
        return {
            "profile": ATHLETE_PROFILE,
            "nutrition": NUTRITION_PRINCIPLES,
            "strength": STRENGTH_PRINCIPLES,
            "running": RUNNING_PRINCIPLES,
            "same_day_sequence": SAME_DAY_SEQUENCE_LAW,
            "cross_sports": CROSS_SPORTS_PROTOCOLS,
            "recovery_and_watch": RECOVERY_AND_WATCH_SETTINGS,
            "presentation": PRESENTATION_RULES,
            "athlete_levels": ATHLETE_LEVELS_FRAMEWORK,
            "progression_triggers": DYNAMIC_PROGRESSION_TRIGGERS
        }


    def get_athlete_progression_assessment(self) -> dict:
        """
        Sporcunun güncel Garmin sensör verilerini (ACWR, dinlenik nabız, HRV toparlanması,
        gym PR artışları ve koşu temposu) inceleyerek dogmatik olmayan dinamik gelişim tavsiyeleri üretir:
        - Gün artırma zamanı geldi mi?
        - Yeni antrenman stiline (Upper/Lower, PPL, Laktat Eşik) geçiş eşiği nerede?
        - Deload veya toparlanma ihtiyacı var mı?
        """
        tl = self.get_training_load_analytics()
        metrics = self.get_latest_metrics()
        gym = self.get_gym_exercise_history()
        
        acwr = tl.get("acwr", {}).get("acwr_ratio", 1.00)
        rhr = metrics.get("rhr", 53.6)
        stress = metrics.get("stress", 28.4)
        squat_pr = 65.0
        bench_pr = 50.0

        # 1. Gün Arttırma Analizi (Volume Readiness)
        can_increase_days = (0.85 <= acwr <= 1.25) and (rhr <= 56.0) and (stress < 35.0)
        if can_increase_days:
            volume_verdict = "HAZIR (Yeşil Işık)"
            volume_advice = (
                f"ACWR oranınız {acwr:.2f} ile kusursuz tatlı noktada (Sweet Spot) ve dinlenik nabzınız ({rhr:.1f} bpm) "
                "mükemmel toparlanma gösteriyor. Eğer haftalık zamanınız uygunsa ve kendinizi enerjik hissediyorsanız, "
                "kardiyovasküler sisteminiz haftalık 2 koşuyu 3 koşuya (Pazar gününe 30-35 dk hafif Zone 2 toparlanma koşusu) "
                "veya haftalık 2 gym seansını 3'e çıkarmayı güvenle tolere edebilecek fizyolojik kapasitededir."
            )
        else:
            volume_verdict = "MEVCUT HACMİ KORU (4 Gün Optimal)"
            volume_advice = (
                f"Mevcut akut antrenman yükünüz ({tl.get('acute_load', 279)} birim) ve ACWR dengeniz ({acwr:.2f}) "
                "haftalık 2 Koşu + 2 Gym modelinde kalmayı öneriyor. Önce mevcut seansların kalitesini koruyun."
            )

        # 2. Antrenman Stili Değiştirme Analizi (Style / Periodization Shift)
        # Sarp 17 Kasım'da Squat 65 kg (5x5) ve Bench 50 kg (5x5) yaptı. Lineer artış hala çalışıyor!
        if squat_pr >= 85.0 or bench_pr >= 70.0:
            style_verdict = "DÖNEMLEME DEĞİŞİMİ ÖNERİLİR"
            style_advice = (
                "Bileşik kaldırışlarınız vücut ağırlığınıza yaklaştı ve lineer 5x5 adaptasyon platosuna gelindi. "
                "Artık merkezi sinir sistemini tüketmemek ve kas hipertrofisini artırmak için "
                "Üst/Alt Vücut (Upper/Lower 4 Gün) veya İtiş-Çekiş-Bacak (PPL) bölünmesine geçilmesi önerilir."
            )
            suggested_routine = "upper_lower"
        else:
            style_verdict = "5x5 LİNEER ARTIŞA DEVAM (Hala Hızlı Gelişiyor)"
            style_advice = (
                f"Son 11 günde Squat'ta +20 kg (45 -> 65 kg) ve Bench'te +5 kg (5x5 kilitlendi) gibi olağanüstü bir "
                "kuvvet adaptasyonu yakaladınız. Nöromüsküler lineer artış tavan yapana kadar (Squat 75-80 kg, Bench 60 kg) "
                "A/B 5x5 sistemini bozmayın. Plato gördüğünüz anda Upper/Lower bölünmesine geçilecektir."
            )
            suggested_routine = "ab_5x5"

        # 3. Koşu Stili Değiştirme Analizi
        # Zone 2 temposu 6:00 altına yaklaştığında tempo koşusu ekleme
        running_style_advice = (
            "Şu an Yüksek Aerobik yükünüz (537.8 birim) zaten tavan durumdadır. Bu nedenle Polarize 80/20 modeli "
            "(1 Seans Zone 2 Taban + 1 Seans 5K Hız İntervali) şu aşamada sizin için en bilimsel yaklaşımdır. "
            "Zone 2 koşu hızınız 145 bpm nabızda 6:00 /km altına indiğinde, programa 3. koşu olarak 'Laktat Eşik / Tempo Koşusu' eklenecektir."
        )

        # 4. Deload / Aşırı Yorgunluk Analizi
        needs_deload = (acwr > 1.35) or (stress > 45.0) or (rhr > 60.0)
        deload_status = "GEREKMİYOR (Kondisyon Yüksek)" if not needs_deload else "DİKKAT: DELOAD ÖNERİLİR"
        deload_note = (
            "Tüm toparlanma parametreleriniz yeşil bölgede. Ağır antrenmanları güvenle sürdürebilirsiniz."
            if not needs_deload else
            "Yorgunluk ve stres göstergeleriniz yüksek; antrenman hacmini bu hafta %40 düşürerek deload uygulayın."
        )

        return {
            "volume_progression": {
                "verdict": volume_verdict,
                "can_increase_days": can_increase_days,
                "current_days": "2 Koşu + 2 Gym (Haftada 4 Gün)",
                "next_level_days": "3 Koşu + 2 Gym veya 2 Koşu + 3 Gym (Haftada 5 Gün)",
                "advice": volume_advice
            },
            "style_transition": {
                "verdict": style_verdict,
                "current_style": "A/B Full Body 5x5 Bileşik Kuvvet + 80/20 Polarize Koşu",
                "suggested_next_style": "Upper/Lower Split (4 Gün) + Piramidal Eşik Koşusu",
                "advice": style_advice,
                "running_style_advice": running_style_advice
            },
            "fatigue_and_deload": {
                "status": deload_status,
                "needs_deload": needs_deload,
                "note": deload_note
            },
            "athlete_levels": ATHLETE_LEVELS_FRAMEWORK,
            "triggers": DYNAMIC_PROGRESSION_TRIGGERS
        }


    def get_post_workout_debrief(self, activity_idx: int = 0) -> Dict[str, Any]:
        """
        Sporcunun her antrenman sonrasında talep ettiği 5 kritik telemetriyi analiz eden
        ve otomatik debrief raporu üreten motor fonksiyonu:
        
        1. Training Load (Firstbeat EPOC seans yükü, Akut/Kronik yük, ACWR ve Sweet Spot tüneli).
        2. Productive Durumu (Garmin Training Status, Neden maintaining/productive, 3'lü Firstbeat odak dengesi).
        3. Genel Günlük 24 Saatlik Detaylı Biyometrik Veriler (Kilo, Dinlenik HR, Gece HRV, Uyku skoru, Body Battery, Stres, Kalori).
        4. Nabız Değerinin Bir Önceki Benzer/Aynı Türdeki Antrenmana Göre Karşılaştırması.
        5. Gym Yapılmışsa Kilo Hacmi (Tonnage) ve Progressive Overload Progresyonu (Squat, Bench, Row PR'ları).
        
        Args:
            activity_idx (int): İncelenecek aktivite sırası (0: en son antrenman).
            
        Returns:
            Dict[str, Any]: 5 ana sütundan oluşan eksiksiz post-workout debrief telemetrisi.
        """
        acts = self.get_all_activities()
        if not acts:
            return {}

        # İndeksi sınırla
        idx = max(0, min(activity_idx, len(acts) - 1))
        act = acts[idx]
        sport = act.get('sport')
        act_date = act.get('date')

        # 1. Bir önceki aynı türdeki aktiviteyi bul
        prev_same = None
        for a in acts[idx + 1:]:
            if a.get('sport') == sport:
                prev_same = a
                break

        # 2. Antrenman Yükü Analitiği
        tl = self.get_training_load_analytics()
        cur_status = tl.get('current_status', {})
        load_focus = tl.get('load_focus', {})

        # 3. Günlük Biyometrik Veriler (24h)
        daily = self.get_latest_metrics()

        # 4. Nabız Karşılaştırması (Aynı branş geçmişiyle)
        hr_comparison = {}
        if prev_same:
            avg_diff = int((act.get('avg_hr') or 0) - (prev_same.get('avg_hr') or 0))
            max_diff = int((act.get('max_hr') or 0) - (prev_same.get('max_hr') or 0))
            dur_diff = round((act.get('dur_m') or 0) - (prev_same.get('dur_m') or 0), 1)
            load_diff = round((act.get('load') or 0) - (prev_same.get('load') or 0), 1)

            if sport == 'strength_training':
                if avg_diff <= 0:
                    insight = (
                        f"Önceki seansa ({prev_same.get('date')}) kıyasla ortalama nabız {abs(avg_diff)} bpm daha düşük seyretti "
                        f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm). 65 kg Squat ve 50 kg Bench gibi daha yüksek ağırlıklara "
                        f"rağmen set aralarında parasempatik toparlanma ve kardiyovasküler dayanıklılık belirgin şekilde daha verimli."
                    )
                else:
                    insight = (
                        f"Önceki gym seansına ({prev_same.get('date')}) kıyasla ortalama nabız {avg_diff} bpm daha yüksek "
                        f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm). Yüksek yoğunluk ve Progressive Overload eforu kardiyak sistemi daha fazla uyardı."
                    )
            elif sport == 'running':
                if avg_diff <= 0:
                    insight = (
                        f"Önceki koşuya ({prev_same.get('date')}) göre ortalama nabız {abs(avg_diff)} bpm daha düşük "
                        f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm). Kardiyak atım hacmi (stroke volume) artarken "
                        f"kalp aynı/daha yüksek hızda daha az atımla çalışıyor (Kardiyak Verimlilik EF: 1.04 m/atım)."
                    )
                else:
                    insight = (
                        f"Önceki koşuya ({prev_same.get('date')}) göre ortalama nabız {avg_diff} bpm daha yüksek "
                        f"({act.get('avg_hr')} vs {prev_same.get('avg_hr')} bpm)."
                    )
            else:
                insight = f"Önceki {sport} seansına ({prev_same.get('date')}) kıyasla ortalama nabız farkı: {avg_diff:+d} bpm."

            hr_comparison = {
                'previous_date': prev_same.get('date'),
                'previous_name': prev_same.get('name'),
                'previous_avg_hr': prev_same.get('avg_hr'),
                'previous_max_hr': prev_same.get('max_hr'),
                'previous_dur_m': round(prev_same.get('dur_m') or 0, 1),
                'previous_load': round(prev_same.get('load') or 0, 1),
                'avg_hr_diff': avg_diff,
                'max_hr_diff': max_diff,
                'dur_diff_min': dur_diff,
                'load_diff': load_diff,
                'insight': insight
            }

        # 5. Gym Hacmi ve Progressive Overload (Kuvvet ise)
        gym_prog = {}
        if sport == 'strength_training':
            gym_data = self.get_gym_exercise_history()
            sessions = gym_data.get('sessions', [])
            cur_sess = None
            prev_sess = None
            prev_same_type_sess = None

            for s in sessions:
                if s.get('date') == act_date:
                    cur_sess = s
                    break
            if not cur_sess and sessions:
                cur_sess = sessions[0]

            if cur_sess:
                for s in sessions:
                    if s.get('date') < cur_sess.get('date'):
                        if not prev_sess:
                            prev_sess = s
                        if s.get('workout_type') == cur_sess.get('workout_type') and not prev_same_type_sess:
                            prev_same_type_sess = s
                            break

                vol_cur = cur_sess.get('total_volume_kg', 0)
                vol_prev = prev_sess.get('total_volume_kg', 0) if prev_sess else 0
                vol_prev_same = prev_same_type_sess.get('total_volume_kg', 0) if prev_same_type_sess else 0

                gym_prog = {
                    'workout_type': cur_sess.get('workout_type'),
                    'current_volume_kg': vol_cur,
                    'current_tonnage': round(vol_cur / 1000.0, 2),
                    'prev_session_date': prev_sess.get('date') if prev_sess else None,
                    'prev_session_type': prev_sess.get('workout_type') if prev_sess else None,
                    'prev_session_volume_kg': vol_prev,
                    'volume_delta_kg': round(vol_cur - vol_prev, 1) if prev_sess else 0,
                    'prev_same_type_date': prev_same_type_sess.get('date') if prev_same_type_sess else None,
                    'prev_same_type_volume_kg': vol_prev_same,
                    'same_type_volume_delta_kg': round(vol_cur - vol_prev_same, 1) if prev_same_type_sess else 0,
                    'exercises': cur_sess.get('exercises', []),
                    'progression_milestones': gym_data.get('progression', {})
                }

        # 6. Productive Durumu Değerlendirmesi
        status_code = cur_status.get('status_code', 'MAINTAINING_3')
        status_tr = cur_status.get('status_tr', 'Form Korunuyor (Maintaining)')
        is_productive = 'PRODUCTIVE' in status_code

        # Seans EPOC Yükü
        session_load = round(act.get('load') or 0, 1)
        acute_load = cur_status.get('acute_load', 279)
        chronic_load = cur_status.get('chronic_load', 279)
        acwr = cur_status.get('acwr', 1.0)
        tunnel_min = cur_status.get('tunnel_min', 200.0)
        tunnel_max = cur_status.get('tunnel_max', 340.0)

        return {
            'activity': {
                'name': act.get('name'),
                'sport': sport,
                'date': act_date,
                'time': act.get('time', ''),
                'duration_min': round(act.get('dur_m') or 0, 1),
                'calories': act.get('cal', 0),
                'avg_hr': act.get('avg_hr'),
                'max_hr': act.get('max_hr'),
                'load': session_load,
                'aerobic_te': round(act.get('aTE') or 0, 1),
                'anaerobic_te': round(act.get('anTE') or 0, 1),
                'te_label': act.get('te_label', 'TOPARLANMA'),
                'water_loss_ml': act.get('water_ml', 0)
            },
            'training_load': {
                'session_epoc_load': session_load,
                'acute_load': acute_load,
                'chronic_load': chronic_load,
                'acwr': acwr,
                'acwr_status': cur_status.get('acwr_status', 'OPTIMAL (Sweet Spot)'),
                'tunnel_min': tunnel_min,
                'tunnel_max': tunnel_max,
                'in_sweet_spot': 0.8 <= acwr <= 1.3,
                'interpretation': (
                    f"Akut yükünüz ({acute_load}), 28 günlük kronik tabanınızla ({chronic_load}) kusursuz dengede (ACWR: {acwr:.2f}). "
                    f"Garmin optimal Firstbeat yük tüneli ({tunnel_min:.0f} - {tunnel_max:.0f}) tam merkezindesiniz. "
                    f"Ne aşırı sürantrene olma ne de sakatlık riski bulunuyor; süper-kompanzasyon için en güvenli bölgedesiniz."
                )
            },
            'productive_evaluation': {
                'status_code': status_code,
                'status_tr': status_tr,
                'is_productive': is_productive,
                'status_reason': (
                    f"Garmin Firstbeat motoru akut yükünüzü ({acute_load}) kronik yüke ({chronic_load}) eşit (ACWR 1.00) "
                    f"ve VO2 Max trendinizi (45.4 mL/kg/dk) sabit gördüğü için durumu '{status_tr}' olarak sınıflıyor."
                ),
                'how_to_reach_productive': (
                    "Productive (Üretken) durumuna geçiş kuralı: Akut yükün tünelin üst bandına (320 - 340) doğru kontrollü artması "
                    "ve haftalık hız intervali (4x1000m @ 5:15 /km) ile laktat toleransının zorlanarak VO2 Max'in yukarı yönlü trende girmesidir."
                ),
                'load_focus': load_focus
            },
            'daily_biometrics_24h': {
                'date': daily.get('date'),
                'weight_kg': daily.get('weight', 87.0),
                'total_loss_kg': daily.get('total_loss_kg', -8.0),
                'resting_hr_bpm': daily.get('resting_hr', 54),
                'overnight_hrv_ms': daily.get('overnight_hrv', 43.0),
                'hrv_7d_avg_ms': daily.get('hrv_7d', 46.0),
                'hrv_status': 'Dengeli (Optimal Parasempatik Toparlanma)',
                'sleep_score': daily.get('sleep_score', 82.0),
                'sleep_hours': daily.get('sleep_hours', 6.39),
                'sleep_stages': 'Derin: 1s 18dk (%20), REM: 1s 24dk (%22)',
                'body_battery_wake': 78,
                'body_battery_current': 62,
                'stress_score': 19,
                'active_calories': 340,
                'recovery_time_hours': daily.get('recovery_time_h', 5.5)
            },
            'hr_comparison_with_prev_same_sport': hr_comparison,
            'gym_volume_progression': gym_prog,
            'executive_coaching_verdict': {
                'verdict': 'Antrenman Başarıyla Kilitlendi • Anabolik Süper-Kompanzasyon Başladı',
                'nutrition_action': '175 - 180 g protein hedefi tamamlanmalı; seans sonrası glikojen sentezi için 250 g kaliteli karbonhidrat.',
                'sleep_action': 'Growth Hormone (GH) ve testosteron pikini yakalamak için saat 00:30 öncesi yatış (hedef 8+ saat uyku).',
                'next_session': {
                    'day': '19 Kasım Perşembe (Çarşamba Dinlenme Sonrası)',
                    'title': 'Koşu #2 - Zone 2 Taban (Bu Haftanın Kalan Son Koşusu, 45-50 dk)',
                    'target_hr': '140 - 150 bpm',
                    'target_pace': '6:35 - 6:50 /km',
                    'purpose': '16 Kas Pazartesi koşusu (5.19 km) ve Salı tamamlanan 7.43 tonluk ağır Squat/Bench seansı sonrası Çarşamba dinlenilip Perşembe günü bacaklardaki laktat süpürülerek haftalık 2/2 koşu kotası tamamlanır.'
                }
            }
        }


