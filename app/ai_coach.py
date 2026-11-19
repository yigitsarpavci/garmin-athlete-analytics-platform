#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerçek AI Entegrasyonlu Sporcu ve Garmin Danışman Motoru (Real AI Coach)
Kullanıcının antrenman, uyku, beslenme, kilo hedefleri ve biyometrik verileri hakkındaki
tüm sorularını Google DeepMind Gemini / OpenAI / Anthropic gerçek yapay zeka modellerine
sporcu telemetrisi ve bağlamıyla aktararak gerçek yanıtlar üretir.
"""

import logging
import contextlib
import os
import sys
import shutil
import subprocess
import time
from typing import List, Dict, Any, Optional, Tuple

try:
    from google import genai
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


logger = logging.getLogger(__name__)


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

    AGY_CLI_MODELS = [
        {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Hızlı - Önerilen)", "recommended": True},
        {"id": "gemini-4-hydrogen-high", "name": "Gemini 4 Hydrogen (Derin Analiz)", "recommended": False},
        {"id": "claude-sonnet-5-5-medium", "name": "Claude Sonnet 5.5 (Alternatif)", "recommended": False},
    ]

    def _engine_scope(self):
        """Motorun istek kapsamını (kilit + tek seferlik hesaplama) döner; motor desteklemiyorsa boş bağlam."""
        scope = getattr(self.engine, "request_scope", None)
        return scope() if callable(scope) else contextlib.nullcontext()

    def describe_providers(self) -> Dict[str, Any]:
        """Bu makinede gerçekten kullanılabilir AI sağlayıcılarını (öncelik sırasıyla) raporlar."""
        providers = []
        if HAS_GOOGLE_GENAI and os.environ.get("GEMINI_API_KEY"):
            providers.append({"id": "google_genai", "model": "gemini-2.5-flash"})
        if HAS_OPENAI and os.environ.get("OPENAI_API_KEY"):
            providers.append({"id": "openai", "model": "gpt-4o-mini"})
        has_agy = bool(self.agy_path) and os.path.exists(self.agy_path)
        if has_agy:
            providers.append({"id": "agy_cli", "model": self.default_model})
        return {
            "active_provider": providers[0]["id"] if providers else "fallback_rules",
            "providers": providers,
            "default_model": self.default_model,
            "is_real_ai_available": bool(providers),
            # Model seçimi yalnızca Antigravity CLI sağlayıcısında etkilidir
            "available_models": self.AGY_CLI_MODELS if has_agy else [],
        }

    def _get_weekly_quota_snapshot(self) -> Dict[str, Any]:
        """
        Motorun haftalık esnek kota özetini (`get_weekly_quota_summary`) güvenli şekilde çeker.
        Metot mevcut değilse veya hata verirse sabit gün dayatmayan güvenli bir özet döner.
        """
        if hasattr(self.engine, "get_weekly_quota_summary"):
            try:
                quota = self.engine.get_weekly_quota_summary()
                if isinstance(quota, dict) and ("running" in quota or "strength" in quota):
                    return quota
            except Exception as e:
                sys.stderr.write(f"get_weekly_quota_summary çağrısı hatası: {e}\n")

        # Güvenli fallback: schedule veya guidance üzerinden özet çıkar
        runs_done, gyms_done = 0, 0
        if hasattr(self.engine, "get_weekly_schedule"):
            try:
                sched = self.engine.get_weekly_schedule() or []
                for row in sched:
                    sec = (row.get("secondary") or "")
                    pri = (row.get("primary") or "")
                    if "TAMAMLANDI" in sec:
                        if "Koşu" in pri:
                            runs_done += 1
                        if "Kuvvet" in pri:
                            gyms_done += 1
            except Exception:
                logger.warning("_get_weekly_quota_snapshot: yedek davranış uygulandı", exc_info=True)

        rem_runs = max(0, 2 - runs_done)
        rem_gyms = max(0, 2 - gyms_done)
        run_items = []
        if rem_runs >= 2:
            run_items = [
                {"category": "running", "type": "Zone 2 Koşu", "title": "Koşu #1 · Zone 2 Rahat Taban", "target_hr": "[[Z2_HR]]", "target_pace": "[[Z2_PACE]]", "duration": "45-50 dk"},
                {"category": "running", "type": "Hız İntervali", "title": "Koşu #2 · 5K Hız İntervali (4x1.000m)", "target_hr": "[[INT_HR]]", "target_pace": "[[INT_PACE]]", "duration": "45 dk"},
            ]
        elif rem_runs == 1:
            run_items = [
                {"category": "running", "type": "Zone 2 Koşu", "title": "Koşu #2 · Zone 2 Rahat Taban", "target_hr": "[[Z2_HR]]", "target_pace": "[[Z2_PACE]]", "duration": "45-50 dk"},
            ]

        gym_items = []
        if rem_gyms >= 2:
            gym_items = [
                {"category": "strength", "type": "Workout A", "title": "Kuvvet #1 · Workout A (5x5)", "exercises_summary": "Squat (5x5) · Bench Press (5x5) · Barbell Row (5x5) · Lateral Raise (3x12) · Shrug (3x12)", "duration": "55 dk"},
                {"category": "strength", "type": "Workout B", "title": "Kuvvet #2 · Workout B (5x5)", "exercises_summary": "Squat (5x5) · OHP (5x5) · Deadlift (1x5) · Lat Pulldown (4x12) · Lateral Raise (3x12) · Shrug (3x12)", "duration": "55 dk"},
            ]
        elif rem_gyms == 1:
            gym_items = [
                {"category": "strength", "type": "Workout B", "title": "Kuvvet #2 · Workout B (5x5)", "exercises_summary": "Squat (5x5) · OHP (5x5) · Deadlift (1x5) · Lat Pulldown (4x12) · Lateral Raise (3x12) · Shrug (3x12)", "duration": "55 dk"},
            ]

        return self.engine.fill_zone_tokens({
            "week_range": "Bu Hafta (Esnek Kota)",
            "headline": f"Bu hafta {runs_done} Koşu + {gyms_done} Kuvvet tamamladın · Geriye {rem_runs} Koşu + {rem_gyms} Kuvvet kaldı",
            "flexibility_note": "Sabit gün zorunluluğu yok — kalan seansları toparlanmana ve programına göre haftanın herhangi bir uygun gününe yerleştirebilirsin.",
            "total": {"target": 4, "completed": runs_done + gyms_done, "remaining": rem_runs + rem_gyms},
            "running": {
                "target": 2, "completed": runs_done, "remaining": rem_runs,
                "completed_labels": [], "remaining_items": run_items,
                "status_text": f"{runs_done}/2 Tamamlandı · Geriye {rem_runs} koşu kaldı",
            },
            "strength": {
                "target": 2, "completed": gyms_done, "remaining": rem_gyms,
                "completed_labels": [], "remaining_items": gym_items,
                "status_text": f"{gyms_done}/2 Tamamlandı · Geriye {rem_gyms} kuvvet seansı kaldı",
            },
            "remaining_items": run_items + gym_items,
            "spontaneous": {"count": 0, "labels": [], "status_text": "Spontane branşlar yapıldıkça takip edilir"},
        })

    @staticmethod
    def _format_remaining_item_line(item: Dict[str, Any]) -> str:
        """Kalan bir kota seansını okunabilir tek satır özete dönüştürür."""
        title = item.get("title") or item.get("type") or "Seans"
        kind = item.get("type") or ""
        prefix = f"{title} ({kind})" if kind and kind not in title else title
        parts: List[str] = []
        if item.get("duration"):
            parts.append(item["duration"])
        if item.get("target_hr"):
            parts.append(item["target_hr"])
        if item.get("target_pace"):
            parts.append(item["target_pace"])
        if item.get("exercises_summary"):
            parts.append(item["exercises_summary"])
        detail = " · ".join(parts)
        return f"{prefix}: {detail}" if detail else prefix

    def build_system_context(self) -> str:
        """
        Sporcunun güncel Garmin sensör verilerini, biyometrik ölçümlerini,
        antrenman yükünü, esnek haftalık kota özetini, gym geçmişini ve ilkelerini
        gerçek AI modeline enjekte edilmek üzere kapsamlı bir sistem bağlamı olarak hazırlar.
        """
        metrics = self.engine.get_latest_metrics()
        gym = self.engine.get_gym_exercise_history()
        tl = self.engine.get_training_load_analytics()
        quota = self._get_weekly_quota_snapshot()

        load_foc = tl.get("load_focus", {}) if isinstance(tl, dict) else {}
        cur_status = tl.get("current_status", {}) if isinstance(tl, dict) else {}
        acute_load = cur_status.get("acute_load", tl.get("acute_load", 0))
        chronic_load = cur_status.get("chronic_load", tl.get("chronic_load", 0))
        acwr_ratio = cur_status.get("acwr", 1.00)
        acwr_status = cur_status.get("acwr_status", "Kusursuz Sweet Spot - Sakatlık riski minimum")

        cur_w = float(metrics.get("weight") or self.engine.get_current_weight())
        cur_bmi = float(metrics.get("bmi") or round(cur_w / self.engine.height_m2, 2))
        start_w = float(metrics.get("start_weight") or self.engine.get_start_weight())
        age = self.engine.age
        height_cm = self.engine.height_cm
        target_w = self.engine.get_target_weight()
        lost_kg = round(start_w - cur_w, 1)
        vo2_val = float(metrics.get("vo2max", tl.get("vo2max_current", 0.0)))
        stress_val = float(metrics.get("stress", 28.4))
        proj_81 = self.engine.calculate_custom_projection(target_w, 0.55)
        morph = self.engine.get_physique_morphology_tracker() if hasattr(self.engine, "get_physique_morphology_tracker") else {}
        z2_tr = self.engine.get_z2_pace_5min_tracker() if hasattr(self.engine, "get_z2_pace_5min_tracker") else {}
        fit_age = self.engine.get_fitness_age_analysis() if hasattr(self.engine, "get_fitness_age_analysis") else {}
        prog_map = gym.get("progression", {}) if isinstance(gym, dict) else {}

        recent_sessions = (gym.get("sessions") or gym.get("recent_sessions") or []) if isinstance(gym, dict) else []
        last_session_summary = "Henüz seans yok"
        if recent_sessions:
            last_s = recent_sessions[0]
            vol = last_s.get("total_volume_kg") or last_s.get("total_tonnage_kg") or 0
            ex_names = ", ".join([e.get("name") or e.get("exercise_name") or "" for e in last_s.get("exercises", []) if (e.get("name") or e.get("exercise_name"))])
            last_session_summary = (
                f"{last_s.get('date')} ({last_s.get('workout_type') or last_s.get('day_name') or 'Kuvvet'}) - "
                f"Toplam Hacim: {vol:,.0f} kg"
                + (f", Hareketler: {ex_names}" if ex_names else "")
            )

        q_week = quota.get("week_range", "Bu Hafta")
        q_headline = quota.get("headline", "")
        q_flex = quota.get("flexibility_note", "Sabit gün zorunluluğu yok — kalan seansları programına ve toparlanmana göre haftanın herhangi bir uygun gününe yerleştirebilirsin.")
        q_adapt = (quota.get("last_week_adaptation") or {}).get("adaptation_note", "")
        q_total = quota.get("total", {})
        q_run = quota.get("running", {})
        q_str = quota.get("strength", {})
        q_spont = quota.get("spontaneous", {})

        run_done_labels = q_run.get("completed_labels") or []
        str_done_labels = q_str.get("completed_labels") or []
        run_rem_items = q_run.get("remaining_items") or []
        str_rem_items = q_str.get("remaining_items") or []

        run_done_txt = "; ".join(run_done_labels) if run_done_labels else "Henüz tamamlanan koşu yok"
        str_done_txt = "; ".join(str_done_labels) if str_done_labels else "Henüz tamamlanan kuvvet seansı yok"
        run_rem_lines = (
            "\n".join(f"    * {self._format_remaining_item_line(item)}" for item in run_rem_items)
            if run_rem_items
            else "    * Bu haftanın koşu kotası tamamlandı (0 kalan)."
        )
        str_rem_lines = (
            "\n".join(f"    * {self._format_remaining_item_line(item)}" for item in str_rem_items)
            if str_rem_items
            else "    * Bu haftanın kuvvet kotası tamamlandı (0 kalan)."
        )
        spont_labels = q_spont.get("labels") or []
        spont_txt = q_spont.get("status_text") or (
            f"{q_spont.get('count', 0)} seans ({', '.join(spont_labels)})" if spont_labels else "Kayıt yok"
        )

        sq_p = prog_map.get("squat", {})
        bp_p = prog_map.get("bench", {})
        rw_p = prog_map.get("row", {})
        ohp_p = prog_map.get("ohp", {})
        dl_p = prog_map.get("deadlift", {})
        focus_rec = load_foc.get("recommended_workout", "Anaerobik barı %62 seviyesinde olduğu için haftalık 4x1000m hız intervali önceliklidir.")

        context = f"""Sen, {age} yaşında elit çoklu-branş sporcusuna (Koşu, Ağırlık/Kuvvet, Yelken, Basketbol, Kayak ve tüm Garmin branşları) 7/24 kişisel danışmanlık yapan spor bilimci ve GERÇEK bir AI Koçsun.
Aşağıda sporcunun Garmin saatinden ve canlı sensör telemetrisinden çekilen BİREBİR GÜNCEL veriler yer almaktadır:

=================== SPORCU BİYOMETRİK VE FİZYOLOJİK PROFİLİ ===================
• Yaş / Boy: {age} Yaşında, {height_cm:.0f} cm boy
• Kilo Seyri: {start_w:.1f} kg -> {cur_w:.1f} kg (-{lost_kg:.1f} kg verildi, VKİ: {cur_bmi:.2f})
• HEDEF İDEAL ATLETİK KİLO: {target_w:.1f} kg (Kalan: {max(0.0, cur_w - target_w):.1f} kg) -> ~{proj_81.get('days_needed', 0)} Gün ({proj_81.get('target_date', '--')})
• Günlük Protein Hedefi: ~{round(cur_w * 2.0)} g (2.0 g/kg yağsız kas koruması)

=================== BU HAFTANIN ESNEK ANTRENMAN KOTASI ({q_week}) ===================
• Genel Kota Özeti: {q_headline}
• Geçen Hafta Adaptasyonu: {q_adapt}
• Toplam Haftalık Kota İlerlemesi: {q_total.get('completed', 0)} / {q_total.get('target', 4)} Seans Tamamlandı (Kalan: {q_total.get('remaining', 4)})
• Koşu Kotası: {q_run.get('completed', 0)} / {q_run.get('target', 2)} · Tamamlananlar: {run_done_txt}
  - Bu Hafta Kalan Koşu Türleri:
{run_rem_lines}
• Kuvvet (Gym) Kotası: {q_str.get('completed', 0)} / {q_str.get('target', 2)} · Tamamlananlar: {str_done_txt}
  - Bu Hafta Kalan Kuvvet Türleri:
{str_rem_lines}
• Spontane & Yeni Branşlar (Yelken / Basketbol / Kayak vb.): {spont_txt}
• ESNEK KOTA PRENSİBİ:
  - {q_flex}
  - ASLA sabit takvim günü veya haftanın belirli bir gününü dikte etme ("şu gün X yap" YASAK!). Pazartesi daima 0/2 sıfırlanır; geçen haftadan eksik kalan türler öne çekilir.

=================== CANLI GARMIN KUVVET (GYM) TELEMETRİSİ (A/B 5x5) ===================
• Son Gym Kaydı: {last_session_summary}
• Güncel Zirveler & Sıradaki Hedefler:
  - Back Squat: {sq_p.get('max_kg', 0.0)} kg -> Sıradaki Hedef: {sq_p.get('next_target', '--')}
  - Bench Press: {bp_p.get('max_kg', 0.0)} kg -> Sıradaki Hedef: {bp_p.get('next_target', '--')}
  - Barbell Row: {rw_p.get('max_kg', 0.0)} kg -> Sıradaki Hedef: {rw_p.get('next_target', '--')}
  - Overhead Press (OHP): {ohp_p.get('max_kg', 0.0)} kg -> Sıradaki Hedef: {ohp_p.get('next_target', '--')}
  - Barbell Deadlift: {dl_p.get('max_kg', 0.0)} kg -> Sıradaki Hedef: {dl_p.get('next_target', '--')}

=================== FIRSTBEAT ANTRENMAN YÜKÜ VE ENERJİ ODAĞI ===================
• Akut Yük (7G ATL): {acute_load} birim | Kronik Yük (28G CTL): {chronic_load} birim | ACWR: {acwr_ratio:.2f} ({acwr_status})
• Güncel Toparlanma: Dinlenme süresi {metrics.get('recovery_time_h', 0.0)} saat, Uyku skoru {metrics.get('sleep_score', 82)}/100, Gece HRV {metrics.get('overnight_hrv', 43)} ms
• Load Focus (Gerçek Bar Dolulukları):
  - Düşük Aerobik (Zone 1-2): {load_foc.get('aerobic_low', {}).get('actual', 0.0):.1f} / {load_foc.get('aerobic_low', {}).get('target_max', 0)} birim (%{load_foc.get('aerobic_low', {}).get('pct_of_target', 92.3)})
  - Yüksek Aerobik (Zone 3-4): {load_foc.get('aerobic_high', {}).get('actual', 0.0):.1f} / {load_foc.get('aerobic_high', {}).get('target_max', 0)} birim (%{load_foc.get('aerobic_high', {}).get('pct_of_target', 91.5)})
  - Anaerobik (Zone 5 / Sprint): {load_foc.get('anaerobic', {}).get('actual', 0.0):.1f} / {load_foc.get('anaerobic', {}).get('target_max', 0)} birim (%{load_foc.get('anaerobic', {}).get('pct_of_target', 61.9)})
• ÖNCELİKLİ ODAK KURALI: {focus_rec}

=================== SAĞLIK YAŞI, MORFOLOJİ VE ZONE 2 GERİ SAYIM ===================
• VO2 Max: {vo2_val} mL/kg/dk | Dinlenik Nabız (RHR): {metrics.get('resting_hr') or self.engine.get_physiology()['rhr']} bpm | Ort. Stres: {stress_val}/100 | Sağlık Yaşı: {fit_age.get('fitness_age', 19.5)} yaş
• Zone 2 Hedefi: Mevcut {z2_tr.get('current_pace', '--')} -> Hedef {z2_tr.get('target_pace', '--')} ({z2_tr.get('remaining_days', 0)} gün, {z2_tr.get('target_date', '--')})
• Morfoloji Durumu: {(morph.get('current') or {}).get('status_title', '')} — {(morph.get('current') or {}).get('morphology', '')}

=================== PROGRAM POLİTİKASI & ÇAPRAZ BRANŞLAR ===================
• Aynı Gün Sıralama Kanunu: ÖNCE KOŞU, SONRA KUVVET (veya ≥6 saat ara).
• Preset dışı sporlar (ör. Kayak, Yüzme, Bisiklet) Garmin'den yüklendiğinde otomatik olarak spontane branşlar + ACWR yüküne işlenir.
• İLETİŞİM: Net, pratik, Türkçe yanıt ver; asla sabit takvim günü emri verme."""
        extra_analytics = self._build_sport_stress_summary()
        if extra_analytics:
            context = f"{context}\n\n{extra_analytics}"
        return context

    def _build_sport_stress_summary(self) -> str:
        """Spor branşlarına göre aynı gün günlük stres / gece HRV ortalamalarını ve en güçlü veri korelasyonlarını özetler."""
        lines: List[str] = []
        df = getattr(self.engine, "df", None)
        acts = getattr(self.engine, "activities_all", None) or []
        if df is not None and not getattr(df, "empty", True) and "date" in df.columns:
            try:
                from engine.helpers import format_sport_tr
            except ImportError:
                from app.engine.helpers import format_sport_tr
            by_date: Dict[str, Dict[str, Any]] = {}
            for _, row in df.iterrows():
                d_str = str(row.get("date") or "")[:10]
                if not d_str:
                    continue
                st_val = row.get("avg_stress")
                hrv_val = row.get("hrv_night")
                by_date[d_str] = {
                    "stress": float(st_val) if st_val is not None and st_val == st_val else None,
                    "hrv": float(hrv_val) if hrv_val is not None and hrv_val == hrv_val else None,
                }

            sport_dates: Dict[str, set] = {}
            active_dates: set = set()
            for a in acts:
                d_str = (a.get("startTimeLocal") or "")[:10]
                if d_str not in by_date:
                    continue
                active_dates.add(d_str)
                sp_key = a.get("sport") or (a.get("activityType") or {}).get("typeKey") or "other"
                sp_tr = format_sport_tr(sp_key, a.get("activityName") or "")
                sport_dates.setdefault(sp_tr, set()).add(d_str)

            rest_dates = set(by_date.keys()) - active_dates
            groups: List[Tuple[str, set]] = [("Dinlenme Günü (Aktivite Yok)", rest_dates)] + sorted(
                sport_dates.items(), key=lambda kv: len(kv[1]), reverse=True
            )
            sport_lines: List[str] = []
            for label, d_set in groups[:10]:
                st_vals = [by_date[d]["stress"] for d in d_set if by_date[d]["stress"] is not None]
                hrv_vals = [by_date[d]["hrv"] for d in d_set if by_date[d]["hrv"] is not None]
                if not st_vals and not hrv_vals:
                    continue
                st_txt = f"Ort. Stres {sum(st_vals) / len(st_vals):.1f}" if st_vals else "Stres --"
                hrv_txt = f"Gece HRV {sum(hrv_vals) / len(hrv_vals):.1f} ms" if hrv_vals else "HRV --"
                sport_lines.append(f"  - {label} ({len(d_set)} gün): {st_txt}, {hrv_txt}")
            if sport_lines:
                lines.append("=================== BRANŞ × AYNI GÜN STRES & HRV İLİŞKİSİ (93G) ===================")
                lines.extend(sport_lines)

        if hasattr(self.engine, "get_correlations"):
            try:
                corrs = self.engine.get_correlations() or []
                if corrs:
                    lines.append("=================== EN GÜÇLÜ VERİ KORELASYONLARI ===================")
                    for c in corrs[:6]:
                        lines.append(f"  - {c.get('pair', '')}: r={c.get('r', '')} ({c.get('desc', '')})")
            except Exception:
                logger.warning("_build_sport_stress_summary correlations fallback", exc_info=True)

        return "\n".join(lines)

    def answer_query(self, user_question: str, model: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None, custom_profile: Optional[dict] = None) -> dict:
        """
        Kullanıcı sorusunu gerçek AI motoruna iletir ve yanıtı döner.
        Eğer custom_profile verilmişse (başka bir sporcu için), yanıtı o sporcunun tercihlerine göre uyarlar.
        """
        selected_model = model or self.default_model
        # Motor verisi yalnızca bağlam kurulurken kilitlenir; LLM çağrıları kilit dışında yapılır.
        with self._engine_scope():
            system_context = self.build_system_context()

        # Başka bir sporcu için soruluyorsa sistem bağlamına sporcu profilini ekle
        profile_instruction = ""
        if custom_profile and not custom_profile.get("is_current_athlete", False):
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
            c_quota = custom_profile.get("quota_summary") or custom_profile.get("weekly_quota") or {}
            c_rem_items = c_quota.get("remaining_items") or []
            c_rem_txt = (
                "\n".join(f"  * {self._format_remaining_item_line(item)}" for item in c_rem_items)
                if c_rem_items else f"  * {c_r} Koşu + {c_g} Kuvvet (Esnek hafta içi/sonu dağılımı)"
            )
            profile_instruction = (
                f"\n=================== DİKKAT: AKTİF SPORCU PROFİLİ ({c_name}) ===================\n"
                f"Kullanıcı şu an Garmin hesabının sahibi olan ana sporcu için DEĞİL, kendi belirlediği tercihlere sahip {c_name} isimli bir sporcu için soru sormaktadır:\n"
                f"• Biyometri: {c_age} yaş, {c_w} kg (Hedef: {c_tw} kg)\n"
                f"• Haftalık Esnek Antrenman Kotası: {c_r} Koşu + {c_g} Kuvvet (Sabit gün dayatması yok!)\n"
                f"• Planlanan Kota Seansları:\n{c_rem_txt}\n"
                f"• Program Tercihi: Salon Rutini: {c_routine}, Koşu Tarzı: {c_style}\n"
                f"• Beslenme Hedefi: Günlük {c_kcal} kcal, {c_p}g protein\n"
                f"Tüm antrenman, tempo, set/tekrar ve gelişim tavsiyelerini doğrudan {c_name}'in bu esnek kotasına ve tercihlerine göre ver; asla sabit takvim günü dikte etme!\n"
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
            f"AI Koç Yanıtı (Sporcu dilinde, esnek kota odaklı, net ve eyleme yönelik):"
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
                sys_msg = f"{system_context}\n{profile_instruction}".strip()
                usr_msg = f"{conversation_context}\n{user_question}".strip()
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": usr_msg}
                    ]
                )
                if response.choices:
                    reply_text = response.choices[0].message.content.strip()
                    provider_used = "OpenAI SDK (gpt-4o-mini)"
            except Exception as e:
                sys.stderr.write(f"OpenAI SDK hatası: {e}\n")

        # 3. YÖNTEM: Antigravity / Gemini CLI Runtime (Kullanıcının lokal DeepMind Gemini motoru - API Keysiz & Doğrudan)
        if not reply_text and self.agy_path and os.path.exists(self.agy_path):
            cli_model = selected_model if selected_model in ["gemini-3.8-flash-low", "gemini-3.8-flash-medium", "gemini-4-hydrogen-high", "claude-sonnet-5-5-medium"] else "gemini-3.8-flash-low"
            attempts = [(cli_model, 110 if cli_model in ("gemini-4-hydrogen-high", "claude-sonnet-5-5-medium") else 60)]
            if cli_model != "gemini-3.8-flash-low":
                attempts.append(("gemini-3.8-flash-low", 45))
            for idx, (m_id, t_sec) in enumerate(attempts):
                try:
                    cmd = [
                        self.agy_path,
                        "--model", m_id,
                        "-p", full_prompt
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=t_sec)
                    if res.returncode == 0 and res.stdout.strip():
                        reply_text = res.stdout.strip()
                        suffix = " · hızlı yedek" if idx > 0 else ""
                        provider_used = f"Antigravity DeepMind Gemini Runtime ({m_id}{suffix})"
                        break
                    else:
                        sys.stderr.write(f"AGY CLI ({m_id}) stdout: {res.stdout}, stderr: {res.stderr}\n")
                except subprocess.TimeoutExpired:
                    sys.stderr.write(f"AGY CLI ({m_id}) zaman aşımına uğradı ({t_sec}s).\n")
                except Exception as e:
                    sys.stderr.write(f"AGY CLI ({m_id}) çalıştırma hatası: {e}\n")

        # 4. YÖNTEM: Eğer hiçbir AI servisi yanıt vermezse acil durum akıllı spor bilimi motoru
        if not reply_text:
            with self._engine_scope():
                reply_text = self._fallback_response(user_question, custom_profile=custom_profile)
            provider_used = "Kişiselleştirilmiş Garmin Kural Motoru (Fallback)"

        elapsed = time.time() - start_time

        return {
            "answer": reply_text,
            "provider": provider_used,
            "model": selected_model,
            "response_time_sec": round(elapsed, 2),
            "is_real_ai": "Kural Motoru" not in provider_used
        }

    def _fallback_response(self, user_question: str, custom_profile: Optional[dict] = None) -> str:
        """
        Dış AI API'larına veya LLM servislerine ulaşılamadığında çalışan deterministik spor bilimi yanıtlayıcısı.
        Sabit takvim günü dayatmadan haftalık kota ilerlemesini (completed/target) ve kalan seans türlerini sunar.

        Args:
            user_question (str): Kullanıcının ilettiği soru metni.
            custom_profile (Optional[dict]): Varsa özel sporcu profili.

        Returns:
            str: Esnek haftalık kota ve sporcu telemetrisine dayalı rehberlik yanıtı.
        """
        q = (user_question or "").lower()

        is_custom = bool(
            custom_profile
            and not custom_profile.get("is_current_athlete", False)
        )
        if is_custom:
            quota = custom_profile.get("quota_summary") or custom_profile.get("weekly_quota") or {}
            athlete_label = custom_profile.get("athlete_name") or custom_profile.get("name") or "Misafir Sporcu"
            metrics = custom_profile.get("metrics") or {}
            kcal_txt = f"{metrics.get('target_calories_kcal', 2400)} kcal"
            prot_txt = f"{metrics.get('protein_g', 160)}g protein"
            z2_cur = "--"
            z2_tgt = "--"
            z2_date = "Hedef Tarih"
            gym_prog = {}
        else:
            quota = self._get_weekly_quota_snapshot()
            athlete_label = self.engine.profile.get("name") or "Sporcu"
            latest_m = self.engine.get_latest_metrics() if hasattr(self.engine, "get_latest_metrics") else {}
            cur_w = float(latest_m.get("weight") or self.engine.get_current_weight())
            kcal_txt = f"{round(cur_w * 28)} kcal (~500 kcal açık)"
            prot_txt = f"~{round(cur_w * 2.0)}g protein"
            z2_tr = self.engine.get_z2_pace_5min_tracker() if hasattr(self.engine, "get_z2_pace_5min_tracker") else {}
            z2_cur = z2_tr.get("current_pace", "--")
            z2_tgt = z2_tr.get("target_pace", "--")
            z2_date = z2_tr.get("target_date", "--")
            gym_hist = self.engine.get_gym_exercise_history() if hasattr(self.engine, "get_gym_exercise_history") else {}
            gym_prog = gym_hist.get("progression", {}) if isinstance(gym_hist, dict) else {}

        q_run = quota.get("running", {})
        q_str = quota.get("strength", {})
        r_done, r_target, r_rem = q_run.get("completed", 0), q_run.get("target", 2), q_run.get("remaining", 0)
        g_done, g_target, g_rem = q_str.get("completed", 0), q_str.get("target", 2), q_str.get("remaining", 0)
        r_rem_items = q_run.get("remaining_items") or []
        g_rem_items = q_str.get("remaining_items") or []
        all_rem_items = quota.get("remaining_items") or (r_rem_items + g_rem_items)
        week_range = quota.get("week_range", "Bu Hafta")

        tl = self.engine.get_training_load_analytics() if hasattr(self.engine, "get_training_load_analytics") else {}
        cur_status = tl.get("current_status", {}) if isinstance(tl, dict) else {}
        acute_load = cur_status.get("acute_load", 0)
        acwr_ratio = cur_status.get("acwr", 1.00)

        rem_runs_txt = (
            " | ".join(self._format_remaining_item_line(it) for it in r_rem_items)
            if r_rem_items else "Bu haftanın koşu kotası tamamlandı (0 kalan)."
        )
        rem_gyms_txt = (
            " | ".join(self._format_remaining_item_line(it) for it in g_rem_items)
            if g_rem_items else "Bu haftanın kuvvet kotası tamamlandı (0 kalan)."
        )

        if "z2" in q or "zone 2" in q or "pace" in q:
            return (
                "🎯 **Zone 2 Temposu & Esnek Haftalık Koşu Kotası:**\n"
                f"Şu anki {self.engine.get_training_zones()['[[Z2_HR_MID]]']} bpm Zone 2 temponuz {z2_cur}'dir. {self.engine.get_target_weight():.0f} kg hedef kilonuza inerken "
                f"80/20 polarize modelle ({z2_date} hedefinde) {self.engine.get_training_zones()['[[Z2_HR_MID]]']} bpm nabızda {z2_tgt} temposuna ilerliyorsunuz.\n"
                f"• **Bu Haftaki Koşu Kotası ({week_range}):** {r_done}/{r_target} koşu tamamlandı, geriye {r_rem} koşu kaldı.\n"
                f"• **Kalan Koşu Türü:** {rem_runs_txt}\n"
                "• **Esnek Planlama:** Sabit bir güne bağlı kalmadan bacaklarınız taze olduğunda haftanın herhangi bir uygun gününde uygulayabilirsiniz."
            )
        elif any(k in q for k in ("ağırlık", "squat", "bench", "gym", "kuvvet", "workout", "deadlift", "ohp")):
            sq = gym_prog.get("squat", {})
            bp = gym_prog.get("bench", {})
            rw = gym_prog.get("row", {})
            return (
                "🏋️ **Kuvvet Progresyonu & Esnek Haftalık Gym Kotası:**\n"
                f"Son kayıtta Squat {sq.get('max_kg', 0.0)} kg ({sq.get('next_target', '--')}), "
                f"Bench Press {bp.get('max_kg', 0.0)} kg ({bp.get('next_target', '--')}) ve "
                f"Barbell Row {rw.get('max_kg', 0.0)} kg ({rw.get('next_target', '--')}) takip edilmektedir.\n"
                f"• **Bu Haftaki Kuvvet Kotası ({week_range}):** {g_done}/{g_target} kuvvet seansı tamamlandı, geriye {g_rem} seans kaldı.\n"
                f"• **Kalan Kuvvet Seansı:** {rem_gyms_txt}\n"
                "• **Esnek Planlama:** Sabit gün zorunluluğu yoktur; merkezi sinir sistemi ve bacaklarınız toparlandığında haftanın uygun bir gününe yerleştirebilirsiniz."
            )
        else:
            if all_rem_items:
                rem_bullets = "\n".join(f"  - {self._format_remaining_item_line(it)}" for it in all_rem_items)
            else:
                rem_bullets = "  - Bu haftanın planlı kotası eksiksiz tamamlandı! İsteğe bağlı hafif yürüyüş / mobilite veya dinlenme uygulayabilirsiniz."

            return (
                f"💪 **Esnek Haftalık Kota & Garmin Koç Özeti ({athlete_label} · {week_range}):**\n"
                f"Antrenman yükünüz {acute_load} birim ve ACWR oranınız {acwr_ratio:.2f} ile Sweet Spot dengesindedir.\n"
                f"• **Tamamlananlar:** Koşu {r_done}/{r_target} · Kuvvet {g_done}/{g_target}\n"
                f"• **Bu Haftadan Kalanlar ({r_rem} Koşu + {g_rem} Kuvvet):**\n{rem_bullets}\n"
                "• **Esnek Uygulama Kuralı:** Sabit bir takvim günü dayatması yoktur; kalan seansları programınıza ve toparlanma hissinize göre haftanın uygun günlerine yerleştirebilirsiniz "
                "(aynı gün çift seans yapılırsa önce koşu, sonra kuvvet veya araya ≥6 saat koyun). "
                f"Beslenmede {prot_txt} ve {kcal_txt} bandını koruyun."
            )
