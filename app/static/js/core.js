/* Garmin Athlete OS - Core State, Theme & Navigation */
let globalOverview = null;
let globalSports = null;
let globalActivities = null;
let globalCharts = null;
let chartInstances = {};
let profilePresets = [];
let currentActiveProfile = {
  is_sarp: true,
  athlete_name: "Sarp",
  profile_badge: "Orijinal Telemetri",
  description: "Haftalık 2 Koşu + 2 Gym (A/B 5x5) • 87,0 kg → 81,0 kg İdeal Hedef"
};

// TEMA YÖNETİMİ (PRO ATHLETIC DARK / DAYLIGHT ENGINE)

function initTheme() {
  const saved = localStorage.getItem('garmin_app_theme');
  const isDark = saved !== null ? (saved === 'dark') : true; // Pro athletic dark varsayılan
  applyTheme(isDark);
}


function applyTheme(isDark) {
  if (isDark) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  const icon = document.getElementById('themeToggleIcon');
  const text = document.getElementById('themeToggleText');
  if (icon) icon.textContent = isDark ? '☀️' : '🌙';
  if (text) text.textContent = isDark ? 'Aydınlık' : 'Koyu';
  localStorage.setItem('garmin_app_theme', isDark ? 'dark' : 'light');
  if (typeof updateChartThemes === 'function') {
    updateChartThemes(isDark);
  }
}


function toggleTheme() {
  const isDarkNow = document.documentElement.classList.contains('dark');
  applyTheme(!isDarkNow);
}

// Sayfa render olmadan önce flicker'ı engellemek için temayı anında başlat
initTheme();

// PROFİL VE TERCİH SİHİRBAZI YÖNETİMİ

async function safeFetchJson(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn(`Veri çekme uyarısı (${url}):`, e);
    return null;
  }
}

// SAYFA İLK YÜKLEME

function setTab(tabId) {
  const tabs = ['overview', 'calculator', 'sports', 'training_load', 'activities', 'health', 'analytics', 'settings'];
  tabs.forEach(t => {
    const sec = document.getElementById('section-' + t);
    const nav = document.getElementById('nav-' + t);
    const mnav = document.getElementById('mnav-' + t);
    if (t === tabId) {
      if (sec) sec.classList.remove('hidden');
      if (nav) nav.className = "px-3 py-1.5 rounded-lg active-nav transition";
      if (mnav) mnav.className = "whitespace-nowrap px-3 py-1 rounded-lg text-neutral-900 dark:text-neutral-950 font-bold bg-white shadow-xs";
    } else {
      if (sec) sec.classList.add('hidden');
      if (nav) nav.className = "px-3 py-1.5 rounded-lg text-neutral-400 hover:text-white transition";
      if (mnav) mnav.className = "whitespace-nowrap px-3 py-1 rounded-lg text-neutral-400 hover:text-neutral-200";
    }
  });

  if (tabId === 'analytics') {
    renderCharts();
  }
}


async function initApp() {
  try {
    initTheme();
    loadProfilePresets();

    // 1. Overview Metrikleri
    globalOverview = await safeFetchJson('/api/overview');
    if (globalOverview) renderOverview(globalOverview);

    // 2. Branşlar
    globalSports = await safeFetchJson('/api/sports');
    if (globalSports) renderSports(globalSports);

    // 2.1 Gym Geçmişi ve Ağırlıklar
    const gymData = await safeFetchJson('/api/gym-history');
    if (gymData) renderGymHistory(gymData);

    // 3. Antrenman Yükü ve ACWR
    const tlData = await safeFetchJson('/api/training-load');
    if (tlData) renderTrainingLoad(tlData);

    // 4. Aynı Gün Sıralaması
    const seqData = await safeFetchJson('/api/same-day-sequence');
    if (seqData) renderSameDaySequence(seqData);

    // 4. Aktiviteler
    globalActivities = await safeFetchJson('/api/activities');
    if (globalActivities) renderActivities(globalActivities);

    // 5. Uyku Analizi
    const sleepData = await safeFetchJson('/api/sleep-analysis');
    if (sleepData) renderSleepAnalysis(sleepData);

    // 6. Korelasyonlar
    const corrData = await safeFetchJson('/api/correlations');
    if (corrData) renderCorrelations(corrData);

    // 7. Dönemler
    const periodsData = await safeFetchJson('/api/periods-weeks');
    if (periodsData) renderPeriods(periodsData);

    // 8. Ayarlar & Bölgeler
    const setData = await safeFetchJson('/api/garmin-settings');
    if (setData) renderSettingsAndZones(setData);

    // 9. Zone 2 @ 5:00 Pace Geri Sayım
    const z2Data = await safeFetchJson('/api/z2-tracker');
    if (z2Data) renderZ2Tracker(z2Data);

    // 10. Fiziksel Morfoloji Takibi
    const morphData = await safeFetchJson('/api/physique-tracker');
    if (morphData) renderPhysiqueTracker(morphData);

    // 11. Klinik Sağlık Taraması & Doktor Özeti
    const healthScreenData = await safeFetchJson('/api/health-screening');
    if (healthScreenData) renderHealthScreening(healthScreenData);

    // 12. Sağlık Yaşı (Fitness Age)
    const fitAgeData = await safeFetchJson('/api/fitness-age');
    if (fitAgeData) renderFitnessAge(fitAgeData);

    // 13. Garmin Veri Derinliğini Artırma
    const expData = await safeFetchJson('/api/garmin-expansion');
    if (expData) renderGarminExpansion(expData);

    // 14. Dogmatik Olmayan Gelişim & Seviye Atlama Analizi
    const progData = await safeFetchJson('/api/progression');
    if (progData) renderProgressionAssessment(progData);

    // 15. Detaylı Günlük Antrenman Protokolleri
    const protocolsData = await safeFetchJson('/api/daily-protocols');
    if (protocolsData) renderDailyProtocols(protocolsData);

    // Başlangıç Hesaplayıcısı
    runCalculator();

  } catch (err) {
    console.error("Yükleme hatası:", err);
  }
}

// 1. GENEL BAKIŞ RENDER

async function syncGarminData() {
  const btn = document.getElementById('syncBtn');
  btn.innerHTML = `<span class="animate-spin inline-block mr-1">↻</span> Çekiliyor...`;
  try {
    const res = await fetch('/api/sync', { method: 'POST' });
    const resData = await res.json();
    if (!res.ok || !resData.success) {
      alert(resData.message || "Garmin oturumu yenilenemedi. Lütfen Garmin Connect girişi yapın.");
    } else {
      alert(resData.message || "Garmin verileri güncellendi!");
      initApp();
    }
  } catch (e) {
    alert("Senkronizasyon hatası: " + e);
  } finally {
    btn.innerHTML = `<svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg><span class="hidden xl:inline">Eşitle</span>`;
  }
}


async function loadProfilePresets() {
  try {
    const res = await fetch('/api/custom-profile/presets');
    profilePresets = await res.json();
    renderPresetBadges();
  } catch (e) {
    console.error("Presets yüklenemedi:", e);
  }
}


function renderPresetBadges() {
  const c = document.getElementById('presetBadgesContainer');
  if (!c || !profilePresets.length) return;
  c.innerHTML = profilePresets.map(p => `
        <button type="button" onclick="applyPresetToForm('${p.id}')" class="px-3 py-1.5 rounded-xl border border-indigo-200 bg-white hover:bg-indigo-100 text-indigo-950 font-bold text-[11px] flex items-center space-x-1.5 transition shadow-xs">
          <span>${p.is_current_athlete ? '🏃‍♂️' : '⚡'}</span>
          <span>${p.name}</span>
        </button>
      `).join('');
}


function openPreferencesModal() {
  const modal = document.getElementById('preferencesModal');
  if (modal) {
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
}


function closePreferencesModal() {
  const modal = document.getElementById('preferencesModal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
  }
}


function applyPresetToForm(presetId) {
  const preset = profilePresets.find(p => p.id === presetId);
  if (!preset || !preset.prefs) return;
  const p = preset.prefs;
  document.getElementById('prefName').value = p.name || '';
  document.getElementById('prefAge').value = p.age || 25;
  document.getElementById('prefGender').value = p.gender || 'male';
  document.getElementById('prefHeight').value = p.height_cm || 180;
  document.getElementById('prefWeight').value = p.current_weight_kg || 80;
  document.getElementById('prefTargetWeight').value = p.target_weight_kg || 75;
  document.getElementById('prefLossRate').value = p.weekly_weight_loss_rate || 0.50;
  document.getElementById('prefRunDays').value = p.running_days !== undefined ? p.running_days : 2;
  document.getElementById('prefRunStyle').value = p.running_style || 'polarize';
  document.getElementById('prefGymDays').value = p.gym_days !== undefined ? p.gym_days : 2;
  document.getElementById('prefGymRoutine').value = p.gym_routine || 'ab_5x5';
  if (p.primary_goal) document.getElementById('prefGoal').value = p.primary_goal;

  const secSports = p.secondary_sports || [];
  document.querySelectorAll('input[name="secSport"]').forEach(cb => {
    cb.checked = secSports.includes(cb.value);
  });
}


async function submitCustomPlanForm(e) {
  if (e) e.preventDefault();
  const btn = document.getElementById('btnSubmitCustomPlan');
  const oldText = btn.innerHTML;
  btn.innerHTML = `<span>Hesaplanıyor...</span>`;
  btn.disabled = true;

  const payload = {
    name: document.getElementById('prefName').value.trim() || 'Misafir Sporcu',
    age: parseInt(document.getElementById('prefAge').value) || 25,
    gender: document.getElementById('prefGender').value,
    height_cm: parseFloat(document.getElementById('prefHeight').value) || 178,
    current_weight_kg: parseFloat(document.getElementById('prefWeight').value) || 80,
    target_weight_kg: parseFloat(document.getElementById('prefTargetWeight').value) || 75,
    weekly_weight_loss_rate: parseFloat(document.getElementById('prefLossRate').value) || 0.5,
    running_days: parseInt(document.getElementById('prefRunDays').value),
    running_style: document.getElementById('prefRunStyle').value,
    gym_days: parseInt(document.getElementById('prefGymDays').value),
    gym_routine: document.getElementById('prefGymRoutine').value,
    primary_goal: document.getElementById('prefGoal').value,
    secondary_sports: Array.from(document.querySelectorAll('input[name="secSport"]:checked')).map(cb => cb.value)
  };

  try {
    const res = await fetch('/api/custom-profile/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const plan = await res.json();
    applyCustomProfileToUI(plan);
    closePreferencesModal();
  } catch (err) {
    alert("Plan oluşturulurken hata meydana geldi: " + err);
  } finally {
    btn.innerHTML = oldText;
    btn.disabled = false;
  }
}


function applyCustomProfileToUI(plan) {
  currentActiveProfile = plan;
  const isSarp = plan.is_sarp;

  const nameDisp = document.getElementById('profileNameDisplay');
  const badgeDisp = document.getElementById('profileBadgeDisplay');
  const descDisp = document.getElementById('profileDescDisplay');
  const avatarInit = document.getElementById('profileAvatarInitial');
  const btnRestore = document.getElementById('btnRestoreSarp');
  const customBanner = document.getElementById('customProfileBanner');

  if (isSarp) {
    nameDisp.textContent = "Sarp (Özel Telemetri)";
    badgeDisp.textContent = "Orijinal Garmin Verisi";
    badgeDisp.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
    descDisp.textContent = "Haftalık 2 Koşu + 2 Gym (A/B 5x5) • 87,0 kg → 81,0 kg İdeal Hedef";
    avatarInit.textContent = "S";
    avatarInit.className = "w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-black text-white text-base shadow-sm ring-2 ring-white/10";
    if (btnRestore) btnRestore.classList.add('hidden');
    if (customBanner) customBanner.classList.add('hidden');
  } else {
    const m = plan.metrics || {};
    nameDisp.textContent = plan.athlete_name + " (Özel Tercihler)";
    badgeDisp.textContent = `${m.weekly_running_days || 0} Koşu + ${m.weekly_gym_days || 0} Gym`;
    badgeDisp.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30";
    descDisp.textContent = `${m.current_weight_kg || 80} kg → ${m.target_weight_kg || 75} kg (${m.days_to_goal || 0} Gün, ${m.target_calories_kcal || 2400} kcal/gün)`;
    avatarInit.textContent = (plan.athlete_name || "M").charAt(0).toUpperCase();
    avatarInit.className = "w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-600 to-orange-500 flex items-center justify-center font-black text-white text-base shadow-sm ring-2 ring-white/10";
    if (btnRestore) btnRestore.classList.remove('hidden');
    if (customBanner) {
      customBanner.classList.remove('hidden');
      document.getElementById('customBannerTitle').textContent = `${plan.athlete_name.toUpperCase()} İÇİN ÖZEL PLAN AKTİF`;
      document.getElementById('customBannerText').textContent = `Haftalık mikro-döngü, ${m.weekly_running_days} gün koşu ve ${m.weekly_gym_days} gün salon tercihine göre güncellenmiştir. Günlük hedef: ${m.target_calories_kcal} kcal (${m.protein_g}g Protein).`;
    }
  }

  renderWeeklyScheduleTable(plan.schedule);
}


async function restoreSarpProfile() {
  try {
    const res = await fetch('/api/custom-profile/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: 'sarp_default' })
    });
    const plan = await res.json();
    applyCustomProfileToUI(plan);
  } catch (e) {
    if (globalOverview && globalOverview.schedule) {
      renderWeeklyScheduleTable(globalOverview.schedule);
    }
  }
}


