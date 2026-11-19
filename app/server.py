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

Uç Noktalar (Endpoints) — yalnızca arayüzün kullandıkları:
-----------------------------------------------------------
- GET  /api/overview            : Güncel metrikler, ACWR, haftalık kota ve yük özeti.
- GET  /api/training-load       : Firstbeat ATL, CTL, ACWR ve yük dağılımı (Düşük/Yüksek/Anaerobik).
- GET  /api/gym-history         : Salon setleri (sayfalı: ?limit=&offset=), ağırlıklar ve 5x5 progresyonu.
- GET  /api/activities          : Kayıtlı tüm Garmin antrenmanları (spor filtresi destekli).
- GET  /api/correlations        : Pearson korelasyon matrisi ve p anlamlılık değerleri.
- GET  /api/progression         : Haftalık gün modeli (2 kuvvet + 2-3 koşu), seviye ve deload analizi.
- GET  /api/daily-protocols     : Derin egzersiz, set, tekrar, ağırlık ve beslenme reçetesi.
- GET  /api/post-workout-debrief: Antrenman sonrası 5 maddelik debrief (?idx=).
- GET  /api/status              : Sunucu durumu, oturum ve veri sürümü (data_version).
- GET  /api/session/keepalive   : Oturum özeti (POST ile Garmin oturumu yenilenir).
- POST /api/chat                : İnteraktif AI koç sohbeti.
- POST /api/sync                : Garmin Connect ile veri senkronizasyonu tetikleme.
"""

import base64
import os
import signal
import sys
import json
import math
import time
import hashlib
import logging
import threading
import subprocess
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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

logger = logging.getLogger("garmin.server")

engine = GarminAthleteEngine()
coach = AthleteAICoach(engine)

# Otomatik eşitleme aralığı (sn). Varsayılan 15 dk; artımlı çekme sayesinde her eşitleme birkaç istektir.
AUTO_SYNC_INTERVAL_SEC = max(300, int(os.environ.get("GARMIN_SYNC_INTERVAL_SEC", "900")))
# Garmin Connect'te veri eksik/boş döndüyse (saat henüz eşitlenmedi) tam aralığı beklemeden kısa aralıkla yeniden dene
QUICK_RETRY_SEC = 300
QUICK_RETRY_MAX = 8

SYNC_STATE: Dict[str, Any] = {
    "last_sync_at": None,
    "session_valid": True,
    "last_error": None,
    "auto_sync_interval_sec": AUTO_SYNC_INTERVAL_SEC,
    "keepalive_active": True,
    "keepalive_interval_sec": 240,
    "last_keepalive_at": None,
    "jwt_expires_at": None,
    "jwt_remaining_sec": None,
}
_SYNC_LOCK = threading.Lock()
_SESSION_FILE_PATH = os.path.join(os.path.expanduser("~"), ".garmin-connect-mcp", "session.json")


def _inspect_session_jwt() -> Dict[str, Any]:
    """
    ~/.garmin-connect-mcp/session.json içindeki JWT_WEB çerezinin gerçek bitiş zamanını çözer.
    Süre bilinmiyorsa uydurulmaz: jwt_expires_at / jwt_remaining_sec None döner.
    Not: Garmin JWT_WEB kısa ömürlüdür; oturumun gerçek geçerliliği son sync/keep-alive
    sonucundan (SYNC_STATE["session_valid"]) okunmalıdır.
    """
    now_ts = int(time.time())
    info: Dict[str, Any] = {
        "session_file_exists": os.path.exists(_SESSION_FILE_PATH),
        "jwt_expires_at": None,
        "jwt_remaining_sec": None,
        "last_keepalive_at": SYNC_STATE.get("last_keepalive_at"),
    }
    if not info["session_file_exists"]:
        return info
    try:
        with open(_SESSION_FILE_PATH, "r", encoding="utf-8") as f:
            sess = json.load(f) or {}
        if sess.get("last_keepalive_at"):
            info["last_keepalive_at"] = sess.get("last_keepalive_at")
        for c in sess.get("cookies") or []:
            if isinstance(c, dict) and c.get("name") == "JWT_WEB":
                parts = (c.get("value") or "").split(".")
                if len(parts) == 3:
                    b64 = parts[1] + "=" * (-len(parts[1]) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(b64).decode("utf-8"))
                    if isinstance(payload.get("exp"), (int, float)):
                        info["jwt_expires_at"] = int(payload["exp"])
                        info["jwt_remaining_sec"] = max(0, int(payload["exp"]) - now_ts)
                break
    except (OSError, ValueError, TypeError):
        logger.debug("_inspect_session_jwt: yedek davranış uygulandı", exc_info=True)
    return info


# Keep-alive, son başarılı Garmin temasından bu yana bu süre geçmeden Playwright başlatmaz.
# Otomatik sync oturum çerezlerini zaten tazelediği için keep-alive yalnızca sync aksarsa devreye girer.
KEEPALIVE_MIN_GAP_SEC = max(840, AUTO_SYNC_INTERVAL_SEC - 600)
_LAST_GARMIN_CONTACT_TS: Optional[float] = None


def _mark_garmin_contact() -> None:
    """Başarılı sync/keep-alive anını kaydeder (gereksiz keep-alive süreçlerini önlemek için)."""
    global _LAST_GARMIN_CONTACT_TS
    _LAST_GARMIN_CONTACT_TS = time.time()


_RELOAD_LOCK = threading.RLock()


def _data_signature() -> str:
    """Ham telemetri dosyalarının (raw_*.json, athlete_profile.json) ad+değişim zamanı+boyut özeti; dışarıdan (make fetch) yapılan güncellemeyi yakalar."""
    d = engine.data_dir
    parts = []
    try:
        for name in sorted(os.listdir(d)):
            if (name.startswith("raw_") and name.endswith(".json")) or name == "athlete_profile.json":
                st = os.stat(os.path.join(d, name))
                parts.append(f"{name}:{st.st_mtime_ns}:{st.st_size}")
    except OSError:
        return "unavailable"
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]


DATA_SIGNATURE: Optional[str] = _data_signature()


def _reload_engine() -> None:
    """Yeni telemetriyi kilit altında yükler."""
    global DATA_SIGNATURE
    with _RELOAD_LOCK:
        with engine.lock:
            engine.load_data()
        DATA_SIGNATURE = _data_signature()


def refresh_if_data_changed() -> None:
    """Diskteki veri, bellekteki motordan farklıysa (ör. elle `make fetch` veya başka süreç) motoru otomatik yeniler."""
    if IS_DEMO_MODE:
        return
    if _data_signature() != DATA_SIGNATURE:
        with _RELOAD_LOCK:
            if _data_signature() != DATA_SIGNATURE:
                logger.info("Diskte yeni Garmin verisi algılandı; motor yeniden yükleniyor.")
                _reload_engine()


def _sync_is_complete() -> bool:
    """Eşitleme sonrası veri tam mı? Garmin bugünün antrenman durumunu henüz üretmediyse (saat eşitlenmedi) False."""
    return not bool(getattr(engine, "training_status_is_fallback", False)) and bool(getattr(engine, "training_status_latest", None))


def sync_garmin_live() -> Dict[str, Any]:
    """Garmin Connect verilerini canlı çeker ve motoru tazeler; 401 durumunda yerel telemetri ve oturum kirasını korur."""
    fetch_script = os.path.join(BASE_DIR, "scripts", "fetch_garmin_data.mjs")
    # Demo modunda gerçek Garmin hesabına bağlanılmaz ve data/ klasörüne yazılmaz
    if IS_DEMO_MODE or not os.path.exists(fetch_script):
        _reload_engine()
        SYNC_STATE["last_sync_at"] = datetime.now().isoformat(timespec="seconds")
        SYNC_STATE["session_valid"] = True
        SYNC_STATE["last_error"] = None
        return {
            "success": True,
            "session_expired": False,
            "last_sync_at": SYNC_STATE["last_sync_at"],
            "message": "Yerel Garmin telemetrisi tazelendi ve oturum korundu.",
        }

    with _SYNC_LOCK:
        try:
            res = subprocess.run(["node", fetch_script], capture_output=True, text=True, timeout=420)
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            _reload_engine()
            now_iso = datetime.now().isoformat(timespec="seconds")
            jwt_info = _inspect_session_jwt()
            SYNC_STATE["last_keepalive_at"] = jwt_info.get("last_keepalive_at") or now_iso
            SYNC_STATE["jwt_expires_at"] = jwt_info.get("jwt_expires_at")
            SYNC_STATE["jwt_remaining_sec"] = jwt_info.get("jwt_remaining_sec")
            is_expired = (
                res.returncode == 2
                or '"session_expired":true' in output
                or '"remote_401":true' in output
            )
            if is_expired:
                SYNC_STATE["session_valid"] = False
                SYNC_STATE["last_error"] = "Garmin Connect oturum süresi doldu (401). Yeniden giriş gerekli."
                return {
                    "success": False,
                    "session_expired": True,
                    "last_sync_at": SYNC_STATE["last_sync_at"],
                    "message": SYNC_STATE["last_error"],
                }
            if res.returncode == 3 or '"already_running":true' in output:
                return {
                    "success": True,
                    "session_expired": False,
                    "last_sync_at": SYNC_STATE["last_sync_at"],
                    "message": "Başka bir senkronizasyon zaten çalışıyor; bittiğinde veri otomatik yüklenir.",
                }
            if res.returncode != 0:
                SYNC_STATE["session_valid"] = True
                SYNC_STATE["last_error"] = (res.stderr or res.stdout or "Senkronizasyon hatası").strip()[:300]
                return {
                    "success": False,
                    "session_expired": False,
                    "last_sync_at": SYNC_STATE["last_sync_at"],
                    "message": f"Garmin senkronizasyonu başarısız: {SYNC_STATE['last_error']}",
                }
            SYNC_STATE["last_sync_at"] = now_iso
            _mark_garmin_contact()
            SYNC_STATE["session_valid"] = True
            SYNC_STATE["last_error"] = None
            return {
                "success": True,
                "session_expired": False,
                "last_sync_at": SYNC_STATE["last_sync_at"],
                "message": "Garmin verileri başarıyla senkronize edildi ve güncellendi!",
            }
        except Exception as exc:
            _reload_engine()
            SYNC_STATE["last_error"] = str(exc)
            return {
                "success": False,
                "session_expired": False,
                "last_sync_at": SYNC_STATE["last_sync_at"],
                "message": f"Garmin senkronizasyon hatası: {exc}",
            }


def keepalive_garmin_session() -> Dict[str, Any]:
    """Garmin Connect oturumunu hafif --keepalive nabız atışı ile canlı tutar ve yeni çerezleri kaydeder."""
    jwt_info = _inspect_session_jwt()
    if IS_DEMO_MODE or not jwt_info["session_file_exists"]:
        SYNC_STATE["session_valid"] = True
        SYNC_STATE["last_error"] = None
        SYNC_STATE["jwt_expires_at"] = jwt_info.get("jwt_expires_at")
        SYNC_STATE["jwt_remaining_sec"] = jwt_info.get("jwt_remaining_sec")
        return {
            "success": True,
            "session_expired": False,
            "session_valid": True,
            "message": "Oturum yuvarlanan kira ile aktif tutuldu.",
            **jwt_info,
        }

    fetch_script = os.path.join(BASE_DIR, "scripts", "fetch_garmin_data.mjs")
    if not os.path.exists(fetch_script):
        SYNC_STATE["session_valid"] = True
        SYNC_STATE["last_error"] = None
        return {
            "success": True,
            "session_expired": False,
            "session_valid": True,
            "message": "Oturum yuvarlanan kira ile aktif tutuldu.",
            **jwt_info,
        }

    with _SYNC_LOCK:
        try:
            proc = subprocess.run(
                ["node", fetch_script, "--keepalive"],
                capture_output=True,
                text=True,
                timeout=45,
            )
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            updated_info = _inspect_session_jwt()
            now_iso = datetime.now().isoformat(timespec="seconds")
            SYNC_STATE["jwt_expires_at"] = updated_info.get("jwt_expires_at")
            SYNC_STATE["jwt_remaining_sec"] = updated_info.get("jwt_remaining_sec")
            SYNC_STATE["last_keepalive_at"] = updated_info.get("last_keepalive_at") or now_iso
            is_expired = (
                proc.returncode == 2
                or '"session_expired":true' in output
                or '"remote_401":true' in output
            )
            if is_expired:
                SYNC_STATE["session_valid"] = False
                SYNC_STATE["last_error"] = "Garmin Connect oturum süresi doldu (401)."
                return {
                    "success": False,
                    "session_expired": True,
                    "session_valid": False,
                    "last_keepalive_at": SYNC_STATE["last_keepalive_at"],
                    "message": SYNC_STATE["last_error"],
                    **updated_info,
                }
            SYNC_STATE["session_valid"] = True
            SYNC_STATE["last_error"] = None
            _mark_garmin_contact()
            return {
                "success": True,
                "session_expired": False,
                "session_valid": True,
                "last_keepalive_at": SYNC_STATE["last_keepalive_at"],
                "message": "Garmin oturumu canlı tutuldu ve tazelendi.",
                **updated_info,
            }
        except Exception as exc:
            updated_info = _inspect_session_jwt()
            now_iso = datetime.now().isoformat(timespec="seconds")
            SYNC_STATE["jwt_expires_at"] = updated_info.get("jwt_expires_at")
            SYNC_STATE["jwt_remaining_sec"] = updated_info.get("jwt_remaining_sec")
            SYNC_STATE["last_keepalive_at"] = updated_info.get("last_keepalive_at") or now_iso
            SYNC_STATE["session_valid"] = False
            SYNC_STATE["last_error"] = str(exc)
            return {
                "success": False,
                "session_expired": False,
                "session_valid": False,
                "last_keepalive_at": SYNC_STATE["last_keepalive_at"],
                "message": f"Garmin keepalive hatası: {exc}",
                **updated_info,
            }


def _session_keepalive_loop(base_interval_sec: int = 240) -> None:
    """Uygulama çalıştığı sürece Garmin Connect oturumunu adaptif aralıklarla yeniler."""
    if IS_DEMO_MODE:
        return  # Demo modu gerçek Garmin hesabına dokunmaz
    while True:
        info = _inspect_session_jwt()
        SYNC_STATE["jwt_expires_at"] = info.get("jwt_expires_at")
        SYNC_STATE["jwt_remaining_sec"] = info.get("jwt_remaining_sec")
        if info.get("last_keepalive_at"):
            SYNC_STATE["last_keepalive_at"] = info.get("last_keepalive_at")

        recently_contacted = (
            _LAST_GARMIN_CONTACT_TS is not None
            and (time.time() - _LAST_GARMIN_CONTACT_TS) < KEEPALIVE_MIN_GAP_SEC
        )
        if info.get("session_file_exists") and not recently_contacted:
            res = keepalive_garmin_session()
            rem = res.get("jwt_remaining_sec")
        else:
            rem = info.get("jwt_remaining_sec") if info.get("session_file_exists") else None

        if isinstance(rem, int) and 0 < rem < 600:
            sleep_sec = max(60, min(base_interval_sec, rem // 2))
        else:
            sleep_sec = base_interval_sec
        time.sleep(sleep_sec)


def _auto_sync_loop(interval_sec: int = 3600) -> None:
    """Sunucu çalışırken belirli aralıklarla Garmin telemetrisini otomatik yeniler."""
    if IS_DEMO_MODE:
        return
    daily_file = os.path.join(BASE_DIR, "data", "raw_daily_93d.json")
    try:
        age_sec = time.time() - os.path.getmtime(daily_file) if os.path.exists(daily_file) else interval_sec + 1
        if age_sec > interval_sec:
            sync_garmin_live()
    except Exception:
        logger.warning("_auto_sync_loop: yedek davranış uygulandı", exc_info=True)
    retries = 0
    while True:
        # Veri eksikse (Garmin bugünün durumunu henüz üretmedi) kısa aralıkla tekrar dene; tamamsa normal aralık
        if not _sync_is_complete() and retries < QUICK_RETRY_MAX:
            retries += 1
            wait = min(QUICK_RETRY_SEC, interval_sec)
        else:
            retries = 0
            wait = interval_sec
        time.sleep(wait)
        try:
            sync_garmin_live()
        except Exception:
            logger.warning("_auto_sync_loop: eşitleme istisnası", exc_info=True)


class AthleteAppHandler(SimpleHTTPRequestHandler):
    """Garmin Sporcu Platformu HTTP İstek İşleyicisi."""

    def __init__(self, *args, **kwargs) -> None:
        """Statik dosya dizinini bağlayarak işleyiciyi ilklendirir."""
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    # Motoru kullanmayan veya uzun süren ağ çağrısı yapan uç noktalar kilit dışında çalışır.
    # /api/chat: motor bağlamı AI koçun içinde kısa süreliğine kilitlenir; LLM çağrısı (35 sn'ye kadar) kilit dışındadır.
    _UNSCOPED_PATHS = {"/api/status", "/api/session/keepalive", "/api/sync", "/api/ai-models", "/api/chat"}
    # Yalnızca yerel istemciler: DNS rebinding ve başka sitelerden gelen istekleri engeller.
    _ALLOWED_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
    MAX_BODY_BYTES = 1_000_000
    CSP = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )

    def _reject(self, code: int, message: str) -> bool:
        """Yasaklı isteği JSON hata gövdesiyle reddeder (CORS başlığı eklenmez)."""
        self.send_json(code, {"error": message})
        return False

    def _guard(self) -> bool:
        """
        Host, Origin ve Sec-Fetch-Site başlıklarını doğrular.
        - Host yalnızca localhost / 127.0.0.1 / ::1 olabilir (DNS rebinding savunması).
        - Origin varsa Host ile aynı olmalı (başka bir web sitesi API'yi çağıramaz).
        - Sec-Fetch-Site 'cross-site' / 'same-site' ise reddedilir (<img>, <form> gibi Origin'siz çağrılar dahil).
        """
        host = self.headers.get("Host") or ""
        try:
            hostname = urllib.parse.urlsplit("//" + host).hostname
        except ValueError:
            hostname = None
        if hostname not in self._ALLOWED_HOSTNAMES:
            return self._reject(403, "Geçersiz Host başlığı")
        origin = self.headers.get("Origin")
        if origin is not None and urllib.parse.urlsplit(origin).netloc != host:
            return self._reject(403, "Farklı kaynaktan (cross-origin) istek reddedildi")
        if (self.headers.get("Sec-Fetch-Site") or "same-origin") not in ("same-origin", "none"):
            return self._reject(403, "Farklı kaynaktan (cross-site) istek reddedildi")
        return True

    def _in_engine_scope(self, path: str) -> bool:
        return path.startswith("/api/") and path not in self._UNSCOPED_PATHS

    def do_GET(self) -> None:
        """GET isteklerini motor istek kapsamında (kilit + tek seferlik hesaplama) yönlendirir."""
        if not self._guard():
            return
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/"):
            try:
                refresh_if_data_changed()
            except Exception:
                logger.warning("refresh_if_data_changed başarısız", exc_info=True)
        if self._in_engine_scope(path):
            with engine.request_scope():
                return self._route_get()
        return self._route_get()

    def do_POST(self) -> None:
        """POST isteklerini motor istek kapsamında yönlendirir (sync/keep-alive hariç)."""
        if not self._guard():
            return
        path = urllib.parse.urlparse(self.path).path
        if self._in_engine_scope(path):
            with engine.request_scope():
                return self._route_post()
        return self._route_post()

    def _route_get(self) -> None:
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
        if path == "/api/overview":
            self.send_json(200, {
                **engine.get_latest_metrics(),
                "is_demo": IS_DEMO_MODE,
                "athlete": {
                    "name": engine.profile.get("name"),
                    "profile_complete": engine.profile.get("is_complete"),
                    "profile_missing": engine.profile.get("missing"),
                    "target_weight_kg": engine.get_target_weight(),
                },
                "weekly_quota": engine.get_weekly_quota_summary(),
                "training_load": engine.get_training_load_analytics()
            })
        # 2. Antrenman Yükü & ACWR (Firstbeat)
        elif path == "/api/training-load":
            self.send_json(200, engine.get_training_load_analytics())
        # 3.1. Kuvvet & Spor Salonu Hareket/Set/Ağırlık Geçmişi
        elif path == "/api/gym-history":
            # Progresyon/plato TÜM seanslardan hesaplanır; yalnızca tablo için seans listesi sayfalanır (varsayılan en yeni 50)
            gh = engine.get_gym_exercise_history()
            all_sessions = gh.get("sessions") or []
            try:
                limit = max(1, min(500, int(query.get("limit", ["50"])[0])))
                offset = max(0, int(query.get("offset", ["0"])[0]))
            except (ValueError, TypeError):
                limit, offset = 50, 0
            self.send_json(200, {
                **gh,
                "sessions": all_sessions[offset:offset + limit],
                "sessions_total": len(all_sessions),
                "sessions_offset": offset,
                "sessions_limit": limit,
            })
        # 3. Tüm Aktiviteler (Filtreli)
        elif path == "/api/activities":
            acts = engine.get_all_activities()
            sport_filter = query.get("sport", [None])[0]
            if sport_filter and sport_filter != "all":
                acts = [a for a in acts if a.get("sport") == sport_filter]
            self.send_json(200, acts)
        # 5. İstatistiksel Korelasyonlar
        elif path == "/api/correlations":
            self.send_json(200, engine.get_correlations())
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
        elif path == "/api/status":
            sess_info = {**SYNC_STATE, **_inspect_session_jwt()}
            self.send_json(200, {
                "status": "ok",
                "profile_id": None,  # Kişisel Garmin profil kimliği repoya gömülmez
                "version": "2.0.0",
                "is_demo": IS_DEMO_MODE,
                "session": sess_info,
                "data_version": DATA_SIGNATURE,
                "training_status_is_fallback": bool(getattr(engine, "training_status_is_fallback", False)),
            })
        elif path == "/api/session/keepalive":
            # GET yan etkisizdir (Garmin'e bağlanmaz); yenileme yalnızca POST ile tetiklenir.
            self.send_json(200, {**_inspect_session_jwt(), "session_valid": SYNC_STATE.get("session_valid")})
        elif path == "/" or path == "":
            self.path = "/index.html"
            return super().do_GET()
        else:
            return super().do_GET()

    def _route_post(self) -> None:
        """Hesaplayıcı, özel profil, veri eşitleme ve interaktif AI koçu POST isteklerini işler."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self.send_json(400, {"error": "Geçersiz Content-Length"})
        if length < 0 or length > self.MAX_BODY_BYTES:
            return self.send_json(413, {"error": "İstek gövdesi çok büyük"})
        raw_body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (UnicodeDecodeError, ValueError):
            body = {}
        if not isinstance(body, dict):
            body = {}

        # 1. AI Koç Sohbeti
        if path == "/api/chat":
            question = body.get("question", "")
            model = body.get("model", "gemini-3.8-flash-low")
            history = body.get("history", [])
            response = coach.answer_query(question, model=model, history=history)
            self.send_json(200, response)
        # 3. Garmin Veri Senkronizasyonu
        elif path == "/api/sync":
            res = sync_garmin_live()
            status_code = 200 if res.get("success") else (401 if res.get("session_expired") else 500)
            self.send_json(status_code, res)
        elif path == "/api/session/keepalive":
            self.send_json(200, keepalive_garmin_session())
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

        try:
            data = engine.fill_zone_tokens(data)
        except Exception:
            logger.debug("fill_zone_tokens başarısız", exc_info=True)
        sanitized_data = _sanitize(data)
        payload = json.dumps(sanitized_data, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def end_headers(self) -> None:
        """Uygulama dosyaları önbelleksiz; sürümü adında sabitlenmiş /vendor/ dosyaları uzun süre önbellekli sunulur."""
        # Sıkı güvenlik başlıkları: yalnızca kendi kaynaklarından script/font/veri; satır içi script yok (olaylar data-* ile)
        self.send_header("Content-Security-Policy", self.CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if self.path.startswith("/vendor/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Standart HTTP günlük mesajlarını zaman damgasıyla stderr akışına yazar."""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

def run(port: int = 8085) -> None:
    """
    Yerel HTTP sunucusunu belirtilen port üzerinden başlatır, arka plan otomatik
    Garmin senkronizasyonunu (varsayılan 60 dk aralıkla, artımlı) ve oturum keep-alive nabzını (4 dk)
    devreye alır ve istekleri dinler.

    Args:
        port (int): Sunucunun bağlanacağı TCP portu (varsayılan: 8085).
    """
    logging.basicConfig(
        level=os.environ.get("GARMIN_LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    threading.Thread(target=_session_keepalive_loop, args=(240,), daemon=True).start()
    threading.Thread(target=_auto_sync_loop, args=(AUTO_SYNC_INTERVAL_SEC,), daemon=True).start()
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, AthleteAppHandler)
    print("\n=======================================================")
    print("🚀 Garmin Sporcu Asistanı & Gösterge Paneli Başlatıldı")
    if IS_DEMO_MODE:
        print("🧪 Mod: DEMO / MOCK VERİ (sample_data) — Canlı senkronizasyon devre dışı")
    else:
        print(f"🔄 Otomatik Garmin Canlı Senkronizasyon: Aktif ({AUTO_SYNC_INTERVAL_SEC // 60} dk, artımlı)")
    print("🔐 Garmin Oturum Keep-Alive: Aktif (4 dk adaptif)")
    print(f"👉 Tarayıcıda açın: http://localhost:{port}")
    print("=======================================================\n")
    try:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        print("\nSunucu kapatıldı.")
        httpd.server_close()

if __name__ == "__main__":
    pos_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    port = int(pos_args[0]) if pos_args else 8085
    run(port)
