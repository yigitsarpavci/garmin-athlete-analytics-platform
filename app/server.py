#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Garmin Sporcu Asistanı Web Sunucusu ve REST API Katmanı
================================================================================

Bu modül, hafif ve harici web çatısı gerektirmeyen (Pure Python 3 standard library
http.server) bir HTTP sunucusudur. Sporcu telemetrisini, Firstbeat antrenman yükü
analitiklerini, makro projeksiyonlarını ve interaktif AI koçunu REST API uç
noktaları üzerinden sunar.

Uç Noktalar (Endpoints):
-----------------------
- GET  /api/overview            : Güncel metrikler, ACWR, haftalık mikro-döngü ve öneriler.
- GET  /api/training-load       : Firstbeat ATL, CTL, ACWR ve yük dağılımı (Düşük/Yüksek/Anaerobik).
- GET  /api/sports              : Branş bazında (Koşu, Gym, Yelken, Basketbol) telemetri ve rehberlik.
- GET  /api/gym-history         : Salon setleri, tekrarlar, ağırlıklar (raw_gym_exercise_sets.json).
- GET  /api/activities          : Kayıtlı tüm Garmin antrenmanları (spor filtresi destekli).
- GET  /api/sleep-analysis      : 88 gecelik uyku evreleri, sirkadiyen ritim ve yatış saati etkisi.
- GET  /api/correlations        : Parametrik Pearson korelasyon matrisi ve p anlamlılık değerleri.
- GET  /api/periods-weeks       : 4 Makro dönem ve 14 ISO haftası analizi.
- GET  /api/same-day-sequence   : Aynı gün kuvvet + koşu sıralamasının nabız ve zon etkisi.
- GET  /api/garmin-settings     : Saatte düzeltilmesi gereken 8 ayar ve nabız/güç zonları.
- GET  /api/principles          : Sporcu ilkeleri ve sistem hafızası (SSOT).
- GET  /api/health-screening    : Spor hekimi klinik sağlık taraması ve kardiyak risk analizi.
- GET  /api/fitness-age         : Garmin Sağlık Yaşı (Fitness Age) ve gençleşme potansiyeli.
- GET  /api/physique-tracker    : Fiziksel değişim, yağ oranı projeksiyonu ve estetik morfoloji.
- GET  /api/z2-tracker          : Zone 2 5:00 /km temposuna kalan seans/gün dinamik sayacı.
- GET  /api/garmin-expansion    : Garmin veri derinliğini artırma mimarisi ve rehberi.
- GET  /api/custom-profile/presets: Sarp ve diğer sporcu seviyeleri için hazır profil şablonları.
- GET  /api/progression         : Dogmatik olmayan seviye atlama, gün artırma ve deload analizi.
- GET  /api/daily-protocols     : 7 günlük derin egzersiz, set, tekrar, ağırlık ve beslenme reçetesi.
- GET  /api/charts              : Web arayüzü grafikleri için 93 günlük zaman serisi verileri.
- GET  /api/status              : Sunucu sağlık durumu ve profil kimliği.
- POST /api/chat                : Gerçek LLM sağlayıcılı interaktif sporcu koçluğu sohbeti.
- POST /api/calculator          : Hedef kilo ve haftalık hıza göre gün/tarih projeksiyonu.
- POST /api/custom-profile/plan : Özel sporcu tercihleri için dinamik 7 günlük antrenman üretimi.
- POST /api/sync                : Garmin Connect ile veri senkronizasyonu tetikleme.
"""

import os
import sys
import json
import math
import time
import threading
import subprocess
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from typing import Any, Dict, Optional, Tuple

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
BASE_DIR = os.path.dirname(APP_DIR)

sys.path.insert(0, APP_DIR)
from garmin_engine import GarminAthleteEngine
from ai_coach import AthleteAICoach
try:
    from engine.helpers import IS_DEMO_MODE
except ImportError:
    from app.engine.helpers import IS_DEMO_MODE

engine = GarminAthleteEngine()
coach = AthleteAICoach(engine)

SYNC_STATE: Dict[str, Any] = {
    "last_sync_at": None,
    "session_valid": True,
    "last_error": None,
    "auto_sync_interval_sec": 900,
}
_SYNC_LOCK = threading.Lock()


def sync_garmin_live() -> Dict[str, Any]:
    """Garmin Connect verilerini canlı çeker ve motoru tazeler."""
    fetch_script = os.path.join(BASE_DIR, "src", "fetch_garmin_data.mjs")
    if not os.path.exists(fetch_script):
        SYNC_STATE["last_error"] = "fetch_garmin_data.mjs bulunamadı."
        return {"success": False, "session_expired": False, "message": SYNC_STATE["last_error"]}

    with _SYNC_LOCK:
        try:
            res = subprocess.run(["node", fetch_script], capture_output=True, text=True, timeout=90)
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            if res.returncode != 0:
                expired = "401" in output or "Session invalid" in output or "expired" in output.lower()
                SYNC_STATE["session_valid"] = not expired
                SYNC_STATE["last_error"] = (
                    "Garmin Connect oturum çerezleri (401) süresi dolmuş. Lütfen yeniden giriş yapın."
                    if expired else f"Senkronizasyon hatası (kod {res.returncode})"
                )
                return {
                    "success": False,
                    "session_expired": expired,
                    "message": SYNC_STATE["last_error"],
                }

            engine.load_data()
            SYNC_STATE["last_sync_at"] = datetime.now().isoformat(timespec="seconds")
            SYNC_STATE["session_valid"] = True
            SYNC_STATE["last_error"] = None
            return {
                "success": True,
                "session_expired": False,
                "last_sync_at": SYNC_STATE["last_sync_at"],
                "message": "Garmin verileri başarıyla senkronize edildi ve güncellendi!",
            }
        except Exception as e:
            SYNC_STATE["last_error"] = str(e)
            return {"success": False, "session_expired": False, "message": f"Senkronizasyon hatası: {str(e)}"}


def _auto_sync_loop(interval_sec: int = 900) -> None:
    """Sunucu çalışırken belirli aralıklarla Garmin telemetrisini otomatik yeniler."""
    daily_file = os.path.join(BASE_DIR, "data", "raw_daily_93d.json")
    try:
        age_sec = time.time() - os.path.getmtime(daily_file) if os.path.exists(daily_file) else interval_sec + 1
        if age_sec > interval_sec:
            sync_garmin_live()
    except Exception:
        pass
    while True:
        time.sleep(interval_sec)
        sync_garmin_live()

class AthleteAppHandler(SimpleHTTPRequestHandler):
    """Garmin Sporcu Platformu HTTP İstek İşleyicisi."""

    def __init__(self, *args, **kwargs) -> None:
        """Statik dosya dizinini bağlayarak işleyiciyi ilklendirir."""
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self) -> None:
        """Tüm analitik GET isteklerini yönlendirir veya statik HTML dosyalarını sunar."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 0. Favicon sessiz yanıtı (Console 404 önleme)
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 1. Genel Bakış & Metrikler
        if path == "/api/overview" or path == "/api/metrics":
            self.send_json(200, {
                **engine.get_latest_metrics(),
                "is_demo": IS_DEMO_MODE,
                "schedule": engine.get_weekly_schedule(),
                "settings": engine.get_garmin_settings_to_fix(),
                "guidance": engine.get_sports_guidance(),
                "training_load": engine.get_training_load_analytics()
            })
        # 2. Antrenman Yükü & ACWR (Firstbeat)
        elif path == "/api/training-load":
            self.send_json(200, engine.get_training_load_analytics())
        # 3. Branşlar ve Gelişim
        elif path == "/api/sports":
            self.send_json(200, engine.get_sports_guidance())
        # 3.1. Kuvvet & Spor Salonu Hareket/Set/Ağırlık Geçmişi
        elif path == "/api/gym-history":
            self.send_json(200, engine.get_gym_exercise_history())
        # 3. Tüm Aktiviteler (Filtreli)
        elif path == "/api/activities":
            acts = engine.get_all_activities()
            sport_filter = query.get("sport", [None])[0]
            if sport_filter and sport_filter != "all":
                acts = [a for a in acts if a.get("sport") == sport_filter]
            self.send_json(200, acts)
        # 4. Uyku ve Yatış Saati Analizi
        elif path == "/api/sleep-analysis":
            self.send_json(200, engine.get_sleep_analysis())
        # 5. İstatistiksel Korelasyonlar
        elif path == "/api/correlations":
            self.send_json(200, engine.get_correlations())
        # 6. Dönemler ve 14 Hafta
        elif path == "/api/periods-weeks":
            self.send_json(200, engine.get_periods_and_weeks())
        # 7. Aynı Gün Kuvvet ve Koşu Sıralaması
        elif path == "/api/same-day-sequence":
            self.send_json(200, engine.get_same_day_sequence())
        # 8. Garmin Ayarları ve Nabız Zonları
        elif path == "/api/garmin-settings":
            self.send_json(200, {
                "settings": engine.get_garmin_settings_to_fix(),
                "zones": engine.get_hr_power_zones()
            })
        # 8.1. Temel Sporcu İlkeleri ve Sistem Hafızası
        elif path == "/api/principles":
            self.send_json(200, engine.get_athlete_principles())
        # 8.2. Klinik Genel Sağlık Taraması & Doktor Özeti
        elif path == "/api/health-screening":
            self.send_json(200, engine.get_health_screening())
        # 8.3. Sağlık Yaşı (Fitness Age) Analizi
        elif path == "/api/fitness-age":
            self.send_json(200, engine.get_fitness_age_analysis())
        # 8.4. Fiziksel Değişim, Yağ Oranı ve Morfoloji Takibi
        elif path == "/api/physique-tracker":
            self.send_json(200, engine.get_physique_morphology_tracker())
        # 8.5. Zone 2 @ 5:00 /km Pace Geri Sayım ve Antrenman Sayacı
        elif path == "/api/z2-tracker":
            self.send_json(200, engine.get_z2_pace_5min_tracker())
        # 8.6. Garmin Veri Derinliğini Artırma Rehberi
        elif path == "/api/garmin-expansion":
            self.send_json(200, engine.get_garmin_data_expansion_guide())
        # 8.7. Başkaları ve Sarp İçin Hazır Profil Şablonları (Presets)
        elif path == "/api/custom-profile/presets":
            self.send_json(200, engine.get_profile_presets())
        # 8.8. Dogmatik Olmayan Gelişim & Seviye Atlama / Gün Artırma Analizi
        elif path == "/api/progression":
            self.send_json(200, engine.get_athlete_progression_assessment())
        # 8.9. Detaylı Günlük Egzersiz, Set, Tekrar ve Ağırlık Protokolleri
        elif path == "/api/daily-protocols":
            self.send_json(200, engine.get_detailed_daily_workout_protocols())
        # 8.10. Antrenman Sonrası 5 Maddelik Telemetri ve Debrief Raporu
        elif path == "/api/post-workout-debrief" or path.startswith("/api/post-workout-debrief"):
            idx = 0
            if "?" in self.path:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "idx" in q:
                    try:
                        idx = int(q["idx"][0])
                    except (ValueError, TypeError):
                        idx = 0
            self.send_json(200, engine.get_post_workout_debrief(activity_idx=idx))
        elif path == "/api/ai-models":
            self.send_json(200, {
                "active_provider": "Antigravity Google DeepMind Gemini Runtime",
                "default_model": "gemini-3.8-flash-low",
                "is_real_ai_available": True,
                "available_models": [
                    {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Hızlı & Keskin - Önerilen)", "recommended": True},
                    {"id": "gemini-4-hydrogen-high", "name": "Gemini 4 Hydrogen (Derin Analiz & Muhakeme)", "recommended": False},
                    {"id": "claude-sonnet-5-5-medium", "name": "Claude Sonnet 5.5 (Alternatif Model)", "recommended": False}
                ]
            })
        # 9. Zaman Serisi Grafikleri
        elif path == "/api/charts":
            self.send_json(200, engine.get_chart_data())
        elif path == "/api/status":
            self.send_json(200, {"status": "ok", "profile_id": null, "version": "2.0.0"})
        elif path == "/" or path == "":
            self.path = "/index.html"
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self) -> None:
        """Hesaplayıcı, özel profil, veri eşitleme ve interaktif AI koçu POST isteklerini işler."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            body = {}

        # 1. AI Koç Sohbeti
        if path == "/api/chat":
            question = body.get("question", "")
            model = body.get("model", "gemini-3.8-flash-low")
            history = body.get("history", [])
            custom_profile = body.get("custom_profile")
            response = coach.answer_query(question, model=model, history=history, custom_profile=custom_profile)
            self.send_json(200, response)
        # 1.1. Kişiselleştirilmiş Antrenman ve Profil Planı Üretici
        elif path == "/api/custom-profile/plan":
            res = engine.generate_custom_plan(body)
            self.send_json(200, res)
        # 2. Özel Forma Girme Hesaplayıcısı
        elif path == "/api/calculator":
            target_kg = float(body.get("target_kg", 81.0))
            weekly_pace_kg = float(body.get("weekly_pace_kg", 0.55))
            res = engine.calculate_custom_projection(target_kg, weekly_pace_kg)
            self.send_json(200, res)
        # 3. Garmin Veri Senkronizasyonu
        elif path == "/api/sync":
            res = sync_garmin_live()
            status_code = 200 if res.get("success") else (401 if res.get("session_expired") else 500)
            self.send_json(status_code, res)
        else:
            self.send_json(404, {"error": "Not found"})

    def send_json(self, status_code: int, data: Any) -> None:
        """
        Veriyi JSON formatında serileştirir ve standart CORS başlıkları ile istemciye yazar.
        Tüm NaN ve sonsuz (inf) kayan noktalı sayıları RFC 8259 uyumlu olarak None (null)
        değerine dönüştürerek tarayıcı JSON.parse istisnalarını önler.

        Args:
            status_code (int): HTTP durum kodu (200, 400, 404, 500 vb.).
            data (Any): JSON serileştirilebilir veri yapısı (dict, list, int, str vb.).
        """
        def _sanitize(val: Any) -> Any:
            if isinstance(val, dict):
                return {k: _sanitize(v) for k, v in val.items()}
            elif isinstance(val, (list, tuple, set)):
                return [_sanitize(v) for v in val]
            elif isinstance(val, float):
                if math.isnan(val) or math.isinf(val):
                    return None
                return val
            return val

        def _json_default(obj: Any) -> Any:
            if hasattr(obj, 'item'):
                return obj.item()
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return str(obj)

        sanitized_data = _sanitize(data)
        payload = json.dumps(sanitized_data, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        """Standart HTTP günlük mesajlarını zaman damgasıyla stderr akışına yazar."""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

def run(port: int = 8085) -> None:
    """
    Yerel HTTP sunucusunu belirtilen port üzerinden başlatır, arka plan otomatik
    Garmin senkronizasyonunu (15 dk aralıkla) devreye alır ve istekleri dinler.

    Args:
        port (int): Sunucunun bağlanacağı TCP portu (varsayılan: 8085).
    """
    threading.Thread(target=_auto_sync_loop, args=(900,), daemon=True).start()
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, AthleteAppHandler)
    print(f"\n=======================================================")
    print(f"🚀 Garmin Sporcu Asistanı & Gösterge Paneli Başlatıldı")
    print(f"🔄 Otomatik Garmin Canlı Senkronizasyon: Aktif (15 dk)")
    print(f"👉 Tarayıcıda açın: http://localhost:{port}")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatıldı.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8085
    run(port)
