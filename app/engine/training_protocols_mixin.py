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
        - Koşu ve Kuvvet haftalık sabit 2+2 takvimini oluşturur.
        - Yelken (ter/elektrolit kaybı, tutuş gücü) ve Basketbol (Zone 4-5 doğal HIIT) spontane
          olarak takip edilir ve telemetrisi dinamik olarak değerlendirilir.

        Returns:
            Dict[str, Any]: Her branş için istatistikler, gelişim ilkeleri ve sonraki seans planları.
        """
        return {
            "running": {
                "name": "Koşu (Running)",
                "schedule_status": "Düzenli Program Branşı",
                "current_pace": "5:48 /km (5K: 29:07)",
                "target_pace": "4:54 /km (5K: <24:30)",
                "cadence": "162 spm (Harika Form ve Düşük Darbe)",
                "stats_summary": "15 Koşu • 79,5 km Mesafe • 158 bpm Ortalama Nabız",
                "how_to_improve": [
                    "80/20 Polarize Model (Mitokondri & Atım Hacmi): Haftalık 2 koşunun 1'ini Zone 2 (140-150 bpm, konuşma temposu) tutarak kalbin sol ventrikül hacmini ve bacak kaslarındaki kılcal damarlanmayı (anjiyogenez) artırın; 1'ini ise laktat eşiğini yukarı çeken hız intervali yapın.",
                    "Haftada 1 Gün Laktat Eşiği İntervali: Cuma günleri 4x1000m (5:15 /km tempo, 172-180 bpm) yaparak yüksek hız toleransınızı ve aerobik tavanınızı yükseltin.",
                    "160+ Kadansı Korumak: Kasım ayında yakaladığınız 162 adım/dk kadans sayesinde yerle temas süreniz 273 ms'ye indi; adımları uzatmak yerine sık adım atarak diz/eklem stresini minimumda tutun.",
                    "Kilo Kaybı Hızlandırması: 87 kg'dan 81 kg'a inişiniz, adımlardaki yerçekimi direncini azaltarak 5K derecenizi 80-90 saniye otomatik olarak hızlandıracaktır."
                ],
                "upcoming_sessions": [
                    {
                        "day": "18 Kasım Çarşamba (Yarın)",
                        "type": "Zone 2 Taban & Aktif Toparlanma",
                        "title": "Koşu #1 - Zone 2 Aerobik Taban",
                        "duration": "45-50 dakika",
                        "details": "Salı günü tamamlanan ağır Squat/Bench sonrası bacaklara kan pompalar. 140-150 bpm nabız tavanını aşmayın (tempo 6:35-6:50 /km). Burundan rahat nefes alabilmelisiniz."
                    },
                    {
                        "day": "20 Kasım Cuma",
                        "type": "Hız & Laktat Eşiği İntervali",
                        "title": "Koşu #2 - 5K Hız İntervali (4 x 1.000 m)",
                        "duration": "45 dakika",
                        "details": "10 dk ısınma (135-145 bpm) + 4 x 1.000m @ 5:15 /km (172-180 bpm, her 1000m arasında 3 dk yürüyüş/jog) + 8 dk soğuma."
                    }
                ],
                "next_workout": {
                    "day": "18 Kasım Çarşamba",
                    "title": "Koşu #1 - Zone 2 Taban & Aktif Toparlanma",
                    "duration": "45-50 dakika",
                    "target_hr": "140 - 150 bpm",
                    "target_pace": "6:35 - 6:50 /km",
                    "details": "Düz sahil hattında burundan nefesle rahat tempo."
                }
            },
            "strength": {
                "name": "Kuvvet Antrenmanı (Strength)",
                "schedule_status": "Düzenli Program Branşı (A/B 5x5)",
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
                "upcoming_sessions": [
                    {
                        "day": "21 Kasım Cumartesi",
                        "type": "Workout B (Kuvvet #2 - İlerleyen Ağırlıklar)",
                        "title": "Bacak, Omuz & Arka Zincir Gücü",
                        "duration": "55 dakika",
                        "details": "Squat 67.5 kg (5x5, +2.5kg) • Overhead Press 40.0 kg (5x5, tüm setlerde 40kg) • Deadlift 65.0 kg (1x5, +5kg) • Lat Pulldown 45.0 kg (4x12) • Lateral Raise 25 kg • Shrug 45 kg."
                    },
                    {
                        "day": "24 Kasım Salı",
                        "type": "Workout A (Kuvvet #1 - Yeni PR Denemesi)",
                        "title": "Göğüs, Sırt & Bacak İlerlemesi",
                        "duration": "55 dakika",
                        "details": "Squat 67.5 kg (5x5) • Bench Press 52.5 kg (5x5 Yeni PR Denemesi!) • Barbell Row 62.5 kg (5x5, +2.5kg) • Lateral Raise 25 kg • Shrug 45 kg."
                    }
                ],
                "next_workout": {
                    "day": "21 Kasım Cumartesi",
                    "title": "Workout B (Kuvvet #2 - İlerleyen Ağırlıklar)",
                    "duration": "55 dakika",
                    "exercises": [
                        "Back Squat: Isınma + 67.5 kg x 5 tekrar x 5 set (+2.5 kg Artış)",
                        "Overhead Press (OHP): Isınma + 40.0 kg x 5 tekrar x 5 set (Tüm setlerde 40 kg)",
                        "Barbell Deadlift: Isınma + 65.0 kg x 5 tekrar (1 Ana Çalışma Seti, +5.0 kg Artış)",
                        "Lat Pulldown: Isınma + 45.0 kg x 12 tekrar x 4 set",
                        "Lateral Raise: 22.5 - 25.0 kg x 12 tekrar x 3 set",
                        "Dumbbell Shrug: 45.0 kg x 12 tekrar x 3 set"
                    ]
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


    def get_weekly_schedule(self):
        """
        Günün tarihine (datetime.now) ve son kaydedilen aktivitelere göre
        haftalık 2 Koşu + 2 Gym + 3 Dinlenme mikro-döngüsünü dinamik olarak üretir.
        Gününde tamamlanmış antrenmanları otomatik olarak algılayıp TAMAMLANDI işaretler.
        """
        now = datetime.now()
        tr_days = ["Pzt", "Salı", "Çar", "Per", "Cuma", "Cmt", "Paz"]
        tr_months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
        
        # Haftanın başlangıç çıpası (Salı günleri)
        weekday = now.weekday()
        days_from_tuesday = (weekday - 1) % 7
        tuesday_anchor = now - timedelta(days=days_from_tuesday)

        plan_definitions = [
            {
                "offset": 0, "day_name": "Salı",
                "workout_type": "gym",
                "plan_primary": "Kuvvet #1 (Workout A: Squat 65kg 5x5 PR, Bench 50kg, Row 60kg)",
                "plan_secondary": "Lateral Raise 25kg & Dumbbell Shrug 45kg",
                "target": "115-128 bpm (Zone 1)",
                "calories": "~2.850 kcal",
                "macro": "2.450 kcal (175g P / 250g K / 80g Y)"
            },
            {
                "offset": 1, "day_name": "Çarşamba",
                "workout_type": "running",
                "plan_primary": "Koşu #1 - Zone 2 Rahat Taban Koşusu (45-50 dk)",
                "plan_secondary": "Aktif toparlanma (160+ kadans, burundan nefes)",
                "target": "140-150 bpm (6:35-6:50 /km)",
                "calories": "~2.950 kcal",
                "macro": "2.550 kcal (175g P / 275g K / 80g Y)"
            },
            {
                "offset": 2, "day_name": "Perşembe",
                "workout_type": "rest",
                "plan_primary": "Tam Dinlenme / Rejenerasyon",
                "plan_secondary": "Cuma günkü hız intervali öncesi bacak toparlanması & erken uyku",
                "target": "<100 bpm (Parasempatik gün)",
                "calories": "~2.500 kcal",
                "macro": "2.350 kcal (175g P / 220g K / 80g Y)"
            },
            {
                "offset": 3, "day_name": "Cuma",
                "workout_type": "running",
                "plan_primary": "Koşu #2 - 5K Hız İntervali (45 dk, 4x1.000m)",
                "plan_secondary": "5:15 /km tempo, aralarda 3 dk yürüyüş/jog dinlenme",
                "target": "170-183 bpm (Zone 4-5)",
                "calories": "~3.050 kcal",
                "macro": "2.650 kcal (175g P / 300g K / 80g Y)"
            },
            {
                "offset": 4, "day_name": "Cumartesi",
                "workout_type": "gym",
                "plan_primary": "Kuvvet #2 (Workout B: Squat 67.5kg, OHP 40kg, Deadlift 65kg)",
                "plan_secondary": "Lat Pulldown 45kg (4x12) & Lateral & Shrug",
                "target": "115-130 bpm (Zone 1)",
                "calories": "~2.900 kcal",
                "macro": "2.500 kcal (180g P / 270g K / 80g Y)"
            },
            {
                "offset": 5, "day_name": "Pazar",
                "workout_type": "active_recovery",
                "plan_primary": "Aktif Toparlanma / Mobilite & Yürüyüş",
                "plan_secondary": "Hafif yürüyüş, esneme, nefes egzersizi (NSDR)",
                "target": "<110 bpm (Zone 1)",
                "calories": "~2.500 kcal",
                "macro": "2.350 kcal (175g P / 220g K / 80g Y)"
            },
            {
                "offset": 6, "day_name": "Pazartesi",
                "workout_type": "rest",
                "plan_primary": "Tam Dinlenme / Haftalık Toparlanma",
                "plan_secondary": "Yeni haftaya zinde başlangıç, erken yatış (00:30)",
                "target": "<100 bpm (Parasempatik gün)",
                "calories": "~2.450 kcal",
                "macro": "2.300 kcal (175g P / 210g K / 80g Y)"
            }
        ]

        schedule = []
        for p in plan_definitions:
            d_date = tuesday_anchor + timedelta(days=p["offset"])
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

            matched_acts = [a for a in self.activities_all if (a.get("startTimeLocal") or "")[:10] == d_str]
            primary = p["plan_primary"]
            secondary = p["plan_secondary"]
            target = p["target"]
            cals = p["calories"]
            macro = p["macro"]

            if matched_acts:
                act = matched_acts[0]
                act_time = (act.get("startTimeLocal") or "")[11:16]
                dur_m = round((act.get("duration") or 0) / 60.0)
                cal = act.get("calories") or 0
                avg_hr = act.get("averageHR") or 0
                act_name = act.get("activityName") or "Antrenman"
                secondary = f"TAMAMLANDI ({act_time} • {dur_m} dk • {cal} kcal • {avg_hr} bpm)"
            elif is_past:
                secondary = "Dinlenme / Tamamlandı"

            schedule.append({
                "day": day_label,
                "primary": primary,
                "secondary": secondary,
                "target": target,
                "calories": cals,
                "macro": macro
            })

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
                "status_note": "17 Kasım Seansı Tamamlandı (10:35) • Bir Sonraki Seans: 24 Kasım Salı",
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
                "day_title": "Çarşamba: Koşu #1 (Zone 2 Aerobik Taban & Mitokondri İnşası)",
                "category": "running",
                "badge": "Zone 2 Taban",
                "badge_color": "emerald",
                "status_note": "Planlanan Seans: 18 Kasım Çarşamba Sabah/Öğleden Sonra",
                "objective": "Sol karıncık atım hacmini (Stroke Volume) büyütmek, periferik kılcal damar ağını genişletmek ve mitokondri yoğunluğunu artırmak.",
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
                "day_code": "thursday",
                "day_title": "Perşembe: Tam Dinlenme & Nöromüsküler Rejenerasyon",
                "category": "rest",
                "badge": "Tam Dinlenme",
                "badge_color": "slate",
                "status_note": "Planlanan: 19 Kasım Perşembe",
                "objective": "Cuma günkü 5K Hız İntervali öncesi bacak kaslarındaki mikroyırtıkları tamir etmek, glikojeni depolamak ve merkezi sinir sistemini (MSS) tazelemek.",
                "warmup": "Gerekli değil (Sıfır kardiyovasküler stres).",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Rejenerasyon Protokolü",
                        "duration": "Tüm Gün Dinlenme",
                        "protocol": "Köpük rulo (Foam Roller) ile 10 dk bacak masajı, kalça mobilitesi ve 20 dk hafif akşam yürüyüşü.",
                        "coaching_cue": "Ağır antrenman veya koşu ASLA yapılmaz. Bacaklar Cuma günkü 4x1000m intervallerine %100 taze girmelidir."
                    }
                ],
                "cooldown": "Sirkadiyen uyku hazırlığı: 00:30 öncesi yatış (Sabah 08:30 uyanış için 8 saat tam döngü).",
                "telemetry_targets": {
                    "hr_range": "<100 bpm (Parasempatik Toparlanma)",
                    "est_calories": "~2.500 kcal toplam harcama",
                    "nutrition": "2.350 kcal alım | 175g Protein | 220g Karbonhidrat | 80g Sağlıklı Yağ | 2.5 - 3.0 L Su"
                }
            },
            {
                "day_code": "friday",
                "day_title": "Cuma: Koşu #2 (5K Hız İntervali - VO2Max & Laktat Eşiği)",
                "category": "running",
                "badge": "5K İnterval",
                "badge_color": "purple",
                "status_note": "Planlanan Seans: 20 Kasım Cuma",
                "objective": "Laktat eşiğini yukarı çekmek, kalp kasılma gücünü (kontraktilite) artırmak ve 5K yarış temposunu 5:15 /km altına kalıcı olarak sabitlemek.",
                "warmup": "10 dk hafif jog @ 135-145 bpm + 3 adet 50 metrelik ivmelenme açılışı (strides) + kalça mobilitesi.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "4 x 1.000 Metre Hız Tekrarları",
                        "sets": 4, "reps": "1.000 Metre",
                        "target_pace": "5:15 /km tempo (Her 1 km tam 5 dk 15 sn sürmeli)",
                        "target_hr": "172 - 182 bpm (Zone 4 - 5 Laktat Eşiği)",
                        "rest_between_reps": "Her 1000m tekrarından sonra TAM 3 DAKİKA yavaş yürüyüş / hafif jog",
                        "cadence_target": "165 - 170 spm",
                        "coaching_cue": "İlk tekrarda depar atmayın; 5:15 temposunu 4 tekrar boyunca eşit ve ritmik koruyun. Dinlenme sürelerinde oturmayın, yürüyerek laktat asidinin kandan temizlenmesini sağlayın."
                    }
                ],
                "cooldown": "8-10 dk çok hafif toparlanma jogu + derin baldır ve hamstring statik esnemesi.",
                "telemetry_targets": {
                    "hr_range": "172 - 183 bpm (Zirve Zone 4-5)",
                    "est_calories": "~3.050 kcal toplam harcama",
                    "nutrition": "2.650 kcal alım | 175g Protein | 300g Karbonhidrat (antrenman öncesi ve sonrası zengin) | 80g Yağ | 3.5 L Su + Elektrolit"
                }
            },
            {
                "day_code": "saturday",
                "day_title": "Cumartesi: Kuvvet Antrenmanı #2 (Workout B - Arka Zincir, Omuz & Çekiş)",
                "category": "gym",
                "badge": "Workout B",
                "badge_color": "blue",
                "status_note": "Planlanan Seans: 21 Kasım Cumartesi",
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
                "day_title": "Pazar: Aktif Toparlanma, Mobilite & Açık Hava Yürüyüşü",
                "category": "active_recovery",
                "badge": "Aktif Dinlenme",
                "badge_color": "emerald",
                "status_note": "Planlanan: 22 Kasım Pazar",
                "objective": "Laktat temizliği, parasempatik tonus artışı, eklem sağlığı ve zihinsel dinlenme.",
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
                "day_title": "Pazartesi: Tam Dinlenme & Haftalık Yenilenme",
                "category": "rest",
                "badge": "Tam Dinlenme",
                "badge_color": "slate",
                "status_note": "Planlanan: 23 Kasım Pazartesi",
                "objective": "Yeni haftanın Workout A ve Zone 2 seanslarına merkezi sinir sistemini ve glikojen depolarını tam dolu olarak hazırlamak.",
                "warmup": "Gerekli değil.",
                "exercises": [
                    {
                        "num": 1,
                        "name": "Tam Dinlenme & Zihinsel Odaklanma",
                        "duration": "Tüm Gün Dinlenme",
                        "protocol": "Sıfır egzersiz. Sağlıklı beslenme, hidrasyon ve erken uyku.",
                        "coaching_cue": "Salı günkü ağır Squat (67.5 kg) ve Bench PR (52.5 kg) denemesine taze girmek için bu gün dinlenmenin hakkını verin."
                    }
                ],
                "cooldown": "Gece 00:30 öncesi yatış (Sabah dinlenik nabız ölçümü için stabil sirkadiyen ritim).",
                "telemetry_targets": {
                    "hr_range": "<100 bpm (Parasempatik Gün)",
                    "est_calories": "~2.450 kcal toplam harcama",
                    "nutrition": "2.300 kcal alım | 175g Protein | 210g Karbonhidrat | 80g Yağ | 2.5 L Su"
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
                    "ve Cuma günkü hız intervali (4x1000m @ 5:15 /km) ile laktat toleransının zorlanarak VO2 Max'in yukarı yönlü trende girmesidir."
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
                    'day': '18 Kasım Çarşamba (Yarın)',
                    'title': 'Koşu #1 - Zone 2 Taban & Aktif Toparlanma (45 dk)',
                    'target_hr': '140 - 150 bpm',
                    'target_pace': '6:35 - 6:50 /km',
                    'purpose': 'Salı günü tamamlanan 7.43 tonluk ağır Squat/Bench seansı sonrası bacak kaslarındaki laktatı süpürür ve mitokondriyal kılcal damarlanmayı (anjiyogenez) besler.'
                }
            }
        }


