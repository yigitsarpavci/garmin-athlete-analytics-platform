#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerçek AI Entegrasyonlu Sporcu ve Garmin Danışman Motoru (Real AI Coach)
Kullanıcının antrenman, uyku, beslenme, kilo hedefleri ve biyometrik verileri hakkındaki
tüm sorularını Google DeepMind Gemini / OpenAI / Anthropic gerçek yapay zeka modellerine
sporcu telemetrisi ve bağlamıyla aktararak gerçek yanıtlar üretir.
"""

import os
import sys
import json
import shutil
import subprocess
import time
from typing import List, Dict, Any, Optional

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class AthleteAICoach:
    """
    Gerçek Yapay Zeka Tabanlı Çoklu Sporcu Koçluk ve Telemetri Danışmanı.

    Bu sınıf; sporcunun güncel Garmin sensör verilerini, biyometrik ölçümlerini,
    Firstbeat yük durumunu ve antrenman hafızasını sistem promptuna enjekte eder.
    Google GenAI SDK, OpenAI SDK veya Antigravity Runtime CLI üzerinden gerçek zamanlı
    muhakeme yürüterek sporcuya kanıta dayalı ve kişiselleştirilmiş yanıtlar üretir.
    """

    def __init__(self, engine: Any) -> None:
        """
        AI Koçunu Garmin veri motoru referansı ve varsayılan model parametreleri ile ilklendirir.

        Args:
            engine (GarminAthleteEngine): Telemetri ve analitik veri motoru örneği.
        """
        self.engine = engine
        self.agy_path = os.environ.get("ANTIGRAVITY_AGENTAPI_EXE") or shutil.which("agy") or os.path.expanduser("~/.gemini/bin/agy")
        self.default_model = "gemini-3.8-flash-low"
        self.active_provider = "gemini_cli" # gemini_cli | google_genai | openai

    def build_system_context(self) -> str:
        """
        Sporcunun güncel Garmin sensör verilerini, biyometrik ölçümlerini,
        antrenman yükünü, gym geçmişini ve prensiplerini gerçek AI modeline
        enjekte edilmek üzere kapsamlı bir sistem bağlamı olarak hazırlar.
        """
        principles = self.engine.get_athlete_principles()
        metrics = self.engine.get_latest_metrics()
        gym = self.engine.get_gym_exercise_history()
        tl = self.engine.get_training_load_analytics()
        guidance = self.engine.get_sports_guidance()

        # Profil & Kilo
        prof = principles.get("athlete_profile", {})
        nutr = principles.get("nutrition", {})
        load_foc = tl.get("load_focus", {})
        acwr = tl.get("acwr", {})
        gym_prog = gym.get("progression", {})
        recent_sessions = gym.get("recent_sessions", [])

        # Son gym seans özeti
        last_session_summary = "Henüz seans yok"
        if recent_sessions:
            last_s = recent_sessions[0]
            last_session_summary = (
                f"{last_s.get('date')} ({last_s.get('day_name')}) - "
                f"Toplam Tonaj: {last_s.get('total_tonnage_kg', 0):,.0f} kg, "
                f"Set Sayısı: {last_s.get('set_count', 0)}, "
                f"Hareketler: {', '.join([e.get('exercise_name', '') for e in last_s.get('exercises', [])])}"
            )

        context = f"""Sen, 22 yaşında elit çoklu-branş sporcusuna (Koşu, Ağırlık/Kuvvet, Yelken, Basketbol) 7/24 kişisel danışmanlık yapan yüksek lisanslı spor bilimci ve GERÇEK bir AI Koçsun.
Aşağıda sporcunun Garmin saatinden, sensör telemetrisinden ve sağlık kayıtlarından çekilen BİREBİR GERÇEK veriler yer almaktadır:

=================== SPORCU BİYOMETRİK VE FİZYOLOJİK PROFİLİ ===================
• Yaş / Boy: 22 Yaşında, 186 cm boy
• Kilo Seyri: 95.0 kg -> 87.0 kg (-8.0 kg verildi, son 63 günde haftalık -0.89 kg/hf)
• Vücut Kitle İndeksi (VKİ): 25.15 (DSÖ Normal Sınırı: 86.45 kg -> Normale kalan: Yalnızca -550 gram!)
• HEDEF İDEAL ATLETİK KİLO: 81.0 kg (80.0 - 83.0 kg optimal aralık, VKİ: 23.41). Kalan: -6.0 kg.
• İdeal Kiloya Varış Takvimi: Kas ve kuvveti koruyan sürdürülebilir hızda (-0.55 kg/hf) tam 76 Gün -> 1 Şubat 2027.
• Günlük Enerji & Beslenme: TDEE: 2.850 - 3.100 kcal. Hedef Günlük Alım: 2.400 - 2.500 kcal (~500 kcal koruyucu açık).
• Protein Hedefi: 175 - 180 g (2.0 - 2.1 g/kg yağsız kas koruması).

=================== GERÇEK GARMIN KUVVET (GYM) TELEMETRİSİ (A/B 5x5) ===================
Sporcu klasik Starting Strength / StrongLifts tarzı A/B Full Body rutini uygulamaktadır:
• Son Yapılan Seans (Bugün / 17 Kasım Salı):
  - Back Squat: 20 kg x 10, 65.0 kg x 5 tekrar x 5 set (5x5 PR REKORU! 06 Kasım'daki 45 kg'dan +20 kg artış!)
  - Bench Press: 20 kg x 10, 50.0 kg x 5 tekrar x 5 set (5x5 kilitlendi! 06 Kasım'daki 45 kg'dan +5 kg artış)
  - Barbell Row: 20 kg x 10, 60.0 kg x 5 tekrar x 5 set (5x5 PR! 06 Kasım'daki 45 kg'dan +15 kg artış)
• Diğer Ana Hareketler Telemetrisi:
  - Overhead Press (OHP): 12 Kasım'da 40.0 kg x 5 tekrar (ve 37.5 kg x 5 x 3 set)
  - Barbell Deadlift: 12 Kasım'da 60.0 kg x 5 tekrar (+10 kg)
  - Lat Pulldown: 12 Kasım'da 45.0 kg x 12 tekrar x 3 set
  - Lateral Raise & Shrug: 20-25 kg yana açış, 45 kg x 12 x 3 shrug.
• Sonraki Kuvvet Hedefleri (Progressive Overload):
  - 21 Kasım Cumartesi (Workout B): Squat 67.5 kg (5x5, +2.5 kg), OHP 40.0 kg (5x5), Deadlift 65.0 kg (1x5, +5 kg), Lat Pulldown 45 kg (4x12).
  - 24 Kasım Salı (Workout A): Squat 67.5 kg (5x5), Bench Press 52.5 kg (5x5 Yeni PR!), Row 62.5 kg (5x5, +2.5 kg).

=================== FIRSTBEAT ANTRENMAN YÜKÜ VE ENERJİ SİSTEMLERİ ===================
• Akut Yük (ATL, 7 günlük yorgunluk): {tl.get('acute_load', 279)} birim
• Kronik Yük (CTL, 28 günlük kondisyon temeli): {tl.get('chronic_load', 279)} birim
• ACWR (Sakatlık Riski Oranı): {acwr.get('acwr_ratio', 1.00):.2f} ({acwr.get('status', 'Kusursuz Sweet Spot - Sakatlık riski minimum')})
• Load Focus (Yük Dağılımı):
  - Yüksek Aerobik (High Aerobic - Zone 3 & 4): {load_foc.get('aerobic_high', {}).get('actual', 537.8):.1f} birim (BALANCED, hedef 325-588 içinde ZİRVEDE!).
  - Düşük Aerobik (Low Aerobic - Zone 1 & 2): {load_foc.get('aerobic_low', {}).get('actual', 385.9):.1f} birim.
  - Anaerobik (Anaerobic - Zone 5): {load_foc.get('anaerobic', {}).get('actual', 162.3):.1f} birim.
• 80/20 Polarize Koşu Modeli (Haftada 2 Gün Koşu): High Aerobic yük zaten tavan olduğundan haftada 1 kez Zone 2 (140-150 bpm, 6:35-6:50 /km, 45-50 dk) koşulmalı; haftada 1 kez ise 4x1000m (5:15 /km, 172-180 bpm) hız intervali yapılmalıdır.
• Zone 2 Hızlanma Takvimi: 81 kg'a iniş ve kardiyak verimlilikle (EF 1.03 -> 1.38 m/atım) Mart-Nisan 2027'de 145 bpm nabızda 5:00 /km hızına ulaşılacaktır.

=================== KLİNİK DOKTOR CHECK-UP VE SAĞLIK YAŞI (FITNESS AGE) ===================
• Doktor Tanısı: A-1 Sınıfı Üstün Atletik Kardiyovasküler Rezerv (Klinik risk faktörü yoktur).
• Dinlenik Nabız (RHR): 53.6 bpm (Fizyolojik sporcu kalbi bradikardisi, kardiyovasküler mortalite riski %40 daha düşük).
• Sağlık Yaşı (Fitness Age): 19.5 Yaş (Kronolojik yaş olan 22'den tam 2.5 yaş daha genç!). Ulaşılabilecek en düşük biyolojik sınır: 18.0 Yaş.
• Otonom Sinir Sistemi & Stres: 28.4/100 ortalama stres, %58 günlük dinlenme/parasempatik toparlanma oranı.
• Pulmoner Durum: 13.8 nefes/dk gece solunumu (kesintisiz gaz değişimi, sıfır apne/hipoksi riski).

=================== FİZİKSEL MORFOLOJİ VE ZONE 2 @ 5:00 /KM GERİ SAYIM SAYACI ===================
• Mevcut Fizik: 87.0 kg, %19-21 tahmini yağ oranı, güçlü omuz ve bacak çatısı.
• Aşama 1 (86.45 kg, 5 Gün Sonra): DSÖ Normal Kilo sınıfına resmi geçiş.
• Aşama 2 (84.0 kg, 34 Gün Sonra): Bel çevresinde net incelme, üst karın çizgileri, 6:15 Z2 pace.
• Aşama 3 (81.0 kg, 76 Gün Sonra - 1 Şubat 2027): %13-14 yağ oranı, klasik V-Taper atletik form!
• Zone 2 @ 5:00 /km Hedefi:
  - Kalan Süre: ~140 Gün (Nisan 2027) • Kalan Hız Farkı: 100 sn/km (6:40 -> 5:00 /km)
  - Kalan Antrenman Sayacı (Haftalık 2 Koşu + 2 Gym Modeli): 20 Seans Zone 2 + 20 Seans İnterval + 40 Seans A/B 5x5 Kuvvet! Toplam 80 seans.
  - 5 Altın Kural: 162+ kadans, 81 kg'a iniş, 150 bpm katı tavan, haftalık 1x 4x1000m, ağır Squat/Deadlift.

=================== PROGRAM POLİTİKASI VE DOGMATİK OLMAMA İLKESİ (DİNAMİK GELİŞİM) ===================
• Sarp'ın mevcut temel mikro-döngüsü haftalık 2 GÜN KOŞU + 2 GÜN GYM (A/B 5x5) ve 3 dinlenme günüdür. Yelken ve Basketbol takvime sabit yazılmaz; spontane çıktıkça dinamik analiz edilir.
• ASLA DOGMATİK OLMA! Bir antrenman programı taşa kazınmış sabit bir kalıp DEĞİLDİR. Sporcunun seviyesine, form grafiğine ve günlük telemetri geri bildirimlerine göre dinamik olarak evrilmelidir.
• HER SEVİYE SPORCUYA AYRI VE BİLİMSEL ANTRENMAN YAKLAŞIMI:
  1. Başlangıç (Beginner): Koş-Yürü (Run/Walk) veya Saf Zone 1-2 konuşma temposu. Asla yüksek şiddetli interval verilmez. Kuvvet için vücut ağırlığı ve dambıl temel kalıplar (Squat, Hinge, Push, Pull). 2-3 gün/hf.
  2. Orta (Intermediate - Sarp'ın Mevcut Seviyesi): Polarize 80/20 koşu (1 Zone 2 + 1 Hız İntervali). Kuvvet için A/B Full Body 5x5. 4 gün/hf (2 Koşu + 2 Gym).
  3. İleri (Advanced): Piramidal veya laktat eşik dönemlemesi (2 Zone 2 + 1 Eşik/Tempo + 1 İnterval). Kuvvet için 5x5'ten Üst/Alt Vücut (Upper/Lower) veya İtiş-Çekiş-Bacak (PPL) bölünmesine geçiş; RPE/RIR tabanlı ağırlık yönetimi. 5 gün/hf.
  4. Elit (Elite): Blok periyodizasyonu, haftalık 5-6 koşu, çift seanslar, patlayıcı pliometri ve yarış zirvelemesi (Peaking).
• ANLIK YORUMLARDAN GÜN ARTTIRMA VE STİL DEĞİŞTİRME TAVSİYELERİ ÇIKARMA:
  - Gün Arttırma Tavsiyesi: Eğer sporcunun ACWR oranı 0.90-1.20 arasında dengeliyse, HRV toparlanması yüksekse ve seans sonrası kas ağrısı (DOMS) hızlı toparlanıyorsa; "Kardiyak tabanın ve kasların hazır, haftalık programa 3. bir koşu (hafif 30 dk toparlanma koşusu) veya 3. bir gym günü ekleyebiliriz" tavsiyesinde bulun.
  - Antrenman Stili Değiştirme Tavsiyesi: Eğer 5x5 lineer artışında aynı ağırlıkta deload yapılmasına rağmen takılma yaşandıysa veya hipertrofi hedefleniyorsa, 5x5'ten Üst/Alt Vücut veya PPL rutinine geçiş öner. Zone 2 temposu 6:00 /km altına indiğinde ise haftalık programa 1 gün 'Laktat Eşik / Tempo Koşusu' bloğu entegre et.
  - Deload / Geri Adım: Yorgunluk, düşük HRV, yüksek dinlenik nabız veya yüksek stres sinyallerinde asla dogmatik davranıp antrenmanı zorlama; "Bugün vücudun sinyal veriyor, antrenmanı hafif yürüyüş ve esnemeye çeviriyoruz veya hacmi %50 kısıyoruz" de.

=================== ÇAPRAZ BRANŞLAR VE KRİTİK KURALLAR ===================
• Aynı Gün Sıralama Kanunu: ASLA ağırlıktan hemen sonra koşma (nabız +7 bpm fırlar, Zone 4 %26'dan %50'ye katlanır). Aynı gün yapılacaksa ÖNCE KOŞU, SONRA AĞIRLIK (veya en az 6 saat ara).
• Yelken Protokolü: 12 seansta 16.6 L ter kaybı. Saat başı 500-600 mL su + 500-800 mg sodyum elektrolit. Seans öncesi 70g kompleks karb. Önkol dayanıklılığı için Farmer's Walk ve Dead Hang.
• Basketbol Protokolü: Doğal anaerobik HIIT seansı. Maç günü ağır bacak (Squat/Deadlift) ASLA yapılmaz. Maç öncesi 10 dk dinamik ayak bileği/kalça mobilitesi.
• Uyku & Sirkadiyen: Sabah 08:30 uyanış için yatış saati mutlaka 00:45 öncesi olmalıdır (>01:45 yatışta REM uykusu -%32 düşmekte ve Body Battery -20 ceza almaktadır).

=================== İLETİŞİM VE CEVAPLAMA TALİMATLARI ===================
1. Sen kurgusal veya kalıp mesajlar veren bir bot DEĞİLSİN. Gerçek bir yapay zekasın; sporcunun sorusunu derin spor bilimi ve yukarıdaki gerçek biyometrik verileriyle analiz et.
2. Üslubun motive edici, net, atletik ve doğrudan eyleme dönük olmalıdır.
3. Karmaşık formüllerle sporcuyu boğma; net sonucu ve "Bugün/Yarın sahada ve salonda tam olarak ne yapmalısın?" maddelerini sporcu diliyle yaz.
4. Sporcuya hitap ederken Türkçe konuş, gerekirse maddeler ve emojilerle son derece okunabilir formatta yanıt ver.
"""
        return context

    def answer_query(self, user_question: str, model: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None, custom_profile: Optional[dict] = None) -> dict:
        """
        Kullanıcı sorusunu gerçek AI motoruna iletir ve yanıtı döner.
        Eğer custom_profile verilmişse (başka bir sporcu için), yanıtı o sporcunun tercihlerine göre uyarlar.
        """
        selected_model = model or self.default_model
        system_context = self.build_system_context()

        # Başka bir sporcu için soruluyorsa sistem bağlamına sporcu profilini ekle
        profile_instruction = ""
        if custom_profile and not custom_profile.get("is_current_athlete", False) and not custom_profile.get("is_sarp", False):
            c_name = custom_profile.get("athlete_name") or custom_profile.get("name") or "Misafir Sporcu"
            metrics = custom_profile.get("metrics", {})
            c_age = metrics.get("age") or custom_profile.get("age", 25)
            c_w = metrics.get("current_weight_kg") or custom_profile.get("current_weight_kg", 80)
            c_tw = metrics.get("target_weight_kg") or custom_profile.get("target_weight_kg", 75)
            c_r = metrics.get("weekly_running_days") or custom_profile.get("running_days", 2)
            c_g = metrics.get("weekly_gym_days") or custom_profile.get("gym_days", 2)
            c_routine = custom_profile.get("gym_routine", "Tüm Vücut")
            c_style = custom_profile.get("running_style", "Polarize")
            c_kcal = metrics.get("target_calories_kcal", 2400)
            c_p = metrics.get("protein_g", 160)
            profile_instruction = (
                f"\n=================== DİKKAT: AKTİF SPORCU PROFİLİ ({c_name}) ===================\n"
                f"Kullanıcı şu an Sarp için DEĞİL, kendi belirlediği tercihlere sahip {c_name} isimli bir sporcu için soru sormaktadır:\n"
                f"• Biyometri: {c_age} yaş, {c_w} kg (Hedef: {c_tw} kg)\n"
                f"• Tercih Edilen Antrenman: Haftada {c_r} Koşu + {c_g} Gym\n"
                f"• Program Tercihi: Salon Rutini: {c_routine}, Koşu Tarzı: {c_style}\n"
                f"• Beslenme Hedefi: Günlük {c_kcal} kcal, {c_p}g protein\n"
                f"Tüm antrenman, tempo, set/tekrar ve gelişim tavsiyelerini doğrudan {c_name}'in bu tercihlerine göre ver!\n"
            )

        # Önceki sohbet geçmişi varsa ekle
        conversation_context = ""
        if history and isinstance(history, list):
            recent_hist = history[-6:] # son 3 soru-cevap çifti
            conversation_context = "\n--- Önceki Sohbet Geçmişi ---\n"
            for h in recent_hist:
                role = "Sporcu" if h.get("role") == "user" else "AI Koç"
                conversation_context += f"{role}: {h.get('content', '')}\n"

        full_prompt = (
            f"{system_context}\n\n"
            f"{profile_instruction}\n\n"
            f"{conversation_context}\n"
            f"Sporcunun Yeni Sorusu: {user_question}\n\n"
            f"AI Koç Yanıtı (Sporcu dilinde, net ve eyleme yönelik):"
        )

        start_time = time.time()
        reply_text = None
        provider_used = None

        # 1. YÖNTEM: Google GenAI SDK (Eğer GEMINI_API_KEY varsa)
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if HAS_GOOGLE_GENAI and gemini_api_key and not reply_text:
            try:
                client = genai.Client(api_key=gemini_api_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=full_prompt,
                )
                if response and response.text:
                    reply_text = response.text.strip()
                    provider_used = "Google GenAI SDK (gemini-2.5-flash)"
            except Exception as e:
                sys.stderr.write(f"Google GenAI SDK hatası: {e}\n")

        # 2. YÖNTEM: OpenAI SDK (Eğer OPENAI_API_KEY varsa)
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if HAS_OPENAI and openai_api_key and not reply_text:
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": user_question}
                    ]
                )
                if response.choices:
                    reply_text = response.choices[0].message.content.strip()
                    provider_used = "OpenAI SDK (gpt-4o-mini)"
            except Exception as e:
                sys.stderr.write(f"OpenAI SDK hatası: {e}\n")

        # 3. YÖNTEM: Antigravity / Gemini CLI Runtime (Kullanıcının lokal DeepMind Gemini motoru - API Keysiz & Doğrudan)
        if not reply_text and os.path.exists(self.agy_path):
            try:
                cli_model = selected_model if selected_model in ["gemini-3.8-flash-low", "gemini-3.8-flash-medium", "gemini-4-hydrogen-high", "claude-sonnet-5-5-medium"] else "gemini-3.8-flash-low"
                cmd = [
                    self.agy_path,
                    "--model", cli_model,
                    "-p", full_prompt
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
                if res.returncode == 0 and res.stdout.strip():
                    reply_text = res.stdout.strip()
                    provider_used = f"Antigravity DeepMind Gemini Runtime ({cli_model})"
                else:
                    sys.stderr.write(f"AGY CLI stdout: {res.stdout}, stderr: {res.stderr}\n")
            except subprocess.TimeoutExpired:
                sys.stderr.write("AGY CLI zaman aşımına uğradı (35s).\n")
            except Exception as e:
                sys.stderr.write(f"AGY CLI çalıştırma hatası: {e}\n")

        # 4. YÖNTEM: Eğer hiçbir AI servisi yanıt vermezse acil durum akıllı spor bilimi motoru
        if not reply_text:
            reply_text = self._fallback_response(user_question)
            provider_used = "Kişiselleştirilmiş Garmin Kural Motoru (Fallback)"

        elapsed = time.time() - start_time

        return {
            "answer": reply_text,
            "provider": provider_used,
            "model": selected_model,
            "response_time_sec": round(elapsed, 2),
            "is_real_ai": "Kural Motoru" not in provider_used
        }

    def _fallback_response(self, user_question: str) -> str:
        """
        Dış AI API'larına veya LLM servislerine ulaşılamadığında çalışan deterministik spor bilimi yanıtlayıcısı.

        Args:
            user_question (str): Kullanıcının ilettiği soru metni.

        Returns:
            str: Sporcu telemetrisine ve ilkelerine dayalı kural tabanlı rehberlik yanıtı.
        """
        q = user_question.lower()
        if "z2" in q or "zone 2" in q or "pace" in q:
            return (
                "🎯 **Zone 2 Temposu ve Gelişim Takvimi:**\n"
                "Şu anki 145 bpm temponuz 6:35-6:50 /km'dir. 81 kg hedef kilonuza ulaştığınızda (-6 kg) "
                "ve haftalık 2 Zone 2 koşusuyla mitokondri yoğunluğunuz arttığında, Mart-Nisan 2027 civarında "
                "145 bpm nabızda 5:00 /km temposuna rahatlıkla ulaşacaksınız."
            )
        elif "ağırlık" in q or "squat" in q or "bench" in q:
            return (
                "🏋️ **Kuvvet ve Progresyon:**\n"
                "Bugün 17 Kasım Salı günü 65 kg Squat 5x5 PR'ınızı ve 50 kg Bench Press 5x5'inizi kilitlediniz. "
                "Perşembe günkü Workout B seansında Squat 67.5 kg (+2.5 kg), OHP 40 kg ve Deadlift 65 kg (+5 kg) hedeflenmektedir."
            )
        else:
            return (
                "💪 **Spor Bilimi & Garmin Koç Tavsiyesi:**\n"
                "Antrenman yükünüz şu an 279 birimle kusursuz Sweet Spot (ACWR 1.00) seviyesindedir. "
                "Yarın (Çarşamba) bacakları dinlendirmek için 45 dk Zone 2 (140-150 bpm) koşusu yapmalı, "
                "beslenmenizde 175-180g protein ve 2.500 kcal bandını korumalısınız."
            )
