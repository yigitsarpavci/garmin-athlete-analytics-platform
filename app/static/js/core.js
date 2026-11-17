/* Garmin Athlete IQ — Core State, Theme, Navigation & Precision Helpers */
let globalOverview = null;
let globalSports = null;
let globalActivities = null;
let globalCharts = null;
let chartInstances = {};
let profilePresets = [];
let currentActiveProfile = {
  is_sarp: true,
  athlete_name: "Athlete",
  profile_badge: "Garmin Telemetrisi",
  description: "Haftalık 2 Koşu + 2 Gym (A/B 5x5)"
};

function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons({
      attrs: { 'stroke-width': '1.5', 'aria-hidden': 'true' }
    });
  }
}

function lucideSvg(name, cls = 'w-4 h-4') {
  return `<i data-lucide="${name}" class="${cls}" aria-hidden="true"></i>`;
}

// TEMA YÖNETİMİ (ZINC LIGHT / DARK ENGINE)

function initTheme() {
  const saved = localStorage.getItem('garmin_app_theme');
  const isDark = saved !== null ? (saved === 'dark') : false;
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
  if (icon) {
    icon.innerHTML = isDark
      ? lucideSvg('sun', 'w-3.5 h-3.5 text-zinc-300')
      : lucideSvg('moon', 'w-3.5 h-3.5 text-zinc-600');
  }
  if (text) text.textContent = isDark ? 'Aydınlık' : 'Koyu';
  localStorage.setItem('garmin_app_theme', isDark ? 'dark' : 'light');
  refreshIcons();
  if (typeof updateChartThemes === 'function') {
    updateChartThemes(isDark);
  }
}

function toggleTheme() {
  const isDarkNow = document.documentElement.classList.contains('dark');
  applyTheme(!isDarkNow);
}

initTheme();

// VERİ ÇEKME & NAVİGASYON

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

function setTab(tabId) {
  const tabs = ['overview', 'plan', 'calculator', 'sports', 'training_load', 'activities', 'health', 'analytics', 'settings'];
  tabs.forEach(t => {
    const sec = document.getElementById('section-' + t);
    const nav = document.getElementById('nav-' + t);
    if (t === tabId) {
      if (sec) sec.classList.remove('hidden');
      if (nav) {
        nav.classList.add('nav-tab-active');
        nav.setAttribute('aria-current', 'page');
      }
    } else {
      if (sec) sec.classList.add('hidden');
      if (nav) {
        nav.classList.remove('nav-tab-active');
        nav.removeAttribute('aria-current');
      }
    }
  });

  if (tabId === 'analytics') {
    renderCharts();
  }
}

function setSubTab(group, paneKey) {
  document.querySelectorAll(`[data-subpane-group="${group}"]`).forEach(el => {
    el.classList.toggle('hidden', el.dataset.subpane !== paneKey);
  });
  document.querySelectorAll(`[data-subtab-group="${group}"]`).forEach(btn => {
    const active = btn.dataset.subtab === paneKey;
    btn.className = active ? 'subtab-btn subtab-btn-active' : 'subtab-btn';
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  if (group === 'analytics' && paneKey === 'charts') {
    renderCharts();
  }
}

async function initApp() {
  try {
    initTheme();
    loadProfilePresets();

    globalOverview = await safeFetchJson('/api/overview');
    if (globalOverview) {
      applyAthleteBranding(globalOverview);
      renderOverview(globalOverview);
    }

    globalSports = await safeFetchJson('/api/sports');
    if (globalSports) renderSports(globalSports);

    const gymData = await safeFetchJson('/api/gym-history');
    if (gymData) renderGymHistory(gymData);

    const tlData = await safeFetchJson('/api/training-load');
    if (tlData) renderTrainingLoad(tlData);

    const seqData = await safeFetchJson('/api/same-day-sequence');
    if (seqData) renderSameDaySequence(seqData);

    globalActivities = await safeFetchJson('/api/activities');
    if (globalActivities) {
      renderActivities(globalActivities);
      renderWeeklyStreak(globalActivities);
      renderLatestActivitySummary(globalActivities);
    }

    const sleepData = await safeFetchJson('/api/sleep-analysis');
    if (sleepData) renderSleepAnalysis(sleepData);

    const corrData = await safeFetchJson('/api/correlations');
    if (corrData) renderCorrelations(corrData);

    const periodsData = await safeFetchJson('/api/periods-weeks');
    if (periodsData) renderPeriods(periodsData);

    const setData = await safeFetchJson('/api/garmin-settings');
    if (setData) renderSettingsAndZones(setData);

    const z2Data = await safeFetchJson('/api/z2-tracker');
    if (z2Data) renderZ2Tracker(z2Data);

    const morphData = await safeFetchJson('/api/physique-tracker');
    if (morphData) renderPhysiqueTracker(morphData);

    const healthScreenData = await safeFetchJson('/api/health-screening');
    if (healthScreenData) renderHealthScreening(healthScreenData);

    const fitAgeData = await safeFetchJson('/api/fitness-age');
    if (fitAgeData) renderFitnessAge(fitAgeData);

    const expData = await safeFetchJson('/api/garmin-expansion');
    if (expData) renderGarminExpansion(expData);

    const progData = await safeFetchJson('/api/progression');
    if (progData) renderProgressionAssessment(progData);

    const protocolsData = await safeFetchJson('/api/daily-protocols');
    if (protocolsData) renderDailyProtocols(protocolsData);

    runCalculator();
    refreshIcons();
  } catch (err) {
    console.error("Yükleme hatası:", err);
  }
}

async function syncGarminData() {
  const btn = document.getElementById('syncBtn');
  if (btn) {
    btn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 animate-spin text-indigo-500')}<span class="hidden xl:inline">Eşitleniyor...</span>`;
    refreshIcons();
  }
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
    if (btn) {
      btn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400')}<span class="hidden xl:inline">Eşitle</span>`;
      refreshIcons();
    }
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
        <button type="button" onclick="applyPresetToForm('${p.id}')" class="px-3 py-1.5 rounded-lg border border-zinc-200/80 dark:border-zinc-700/80 bg-white dark:bg-zinc-900 hover:border-indigo-500 dark:hover:border-indigo-500 text-zinc-900 dark:text-zinc-100 font-medium text-[11px] flex items-center gap-1.5 transition-all duration-200 active:scale-[0.98]">
          ${lucideSvg(p.is_current_athlete ? 'activity' : 'zap', 'w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400')}
          <span>${p.name}</span>
        </button>
      `).join('');
  refreshIcons();
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
    refreshIcons();
  }
}

function renderLatestActivitySummary(activities) {
  const row = document.getElementById('latestActivitySummaryRow');
  if (!row || !Array.isArray(activities) || !activities.length) return;
  const a = activities[0];
  const sp = (a.sport || '').toLowerCase();
  const iconName = sp.includes('run') ? 'footprints' : (sp.includes('sail') ? 'compass' : (sp.includes('basket') ? 'trophy' : 'dumbbell'));
  const dur = a.dur_m ? `${Math.round(a.dur_m)} dk` : '--';
  const hr = a.avg_hr ? `${a.avg_hr} bpm` : '--';
  row.innerHTML = `
    <span class="font-medium text-zinc-900 dark:text-zinc-100 truncate flex items-center gap-2">
      ${lucideSvg(iconName, 'w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0')}
      <span class="truncate">${a.name || a.sport || 'Antrenman'}</span>
      <span class="font-mono text-[10px] text-zinc-400 font-normal">(${a.date})</span>
    </span>
    <span class="font-mono text-[11px] text-zinc-600 dark:text-zinc-300 font-medium tabular-nums shrink-0 ml-2">${dur} · ${hr}</span>
  `;
  refreshIcons();
}

function renderWeeklyStreak(activities) {
  const strip = document.getElementById('weeklyStreakStrip');
  const badge = document.getElementById('weeklyStreakBadge');
  if (!strip || !Array.isArray(activities) || !activities.length) return;

  const dayNames = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];
  const order = [1, 2, 3, 4, 5, 6, 0];
  const latestStr = (activities[0].date || activities[0].startTimeLocal || '').slice(0, 10);
  const refDate = latestStr ? new Date(latestStr + 'T12:00:00') : new Date();
  const refDay = refDate.getDay();
  const diffToMon = (refDay === 0 ? -6 : 1 - refDay);
  const monday = new Date(refDate);
  monday.setDate(refDate.getDate() + diffToMon);

  const dayMap = {};
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const iso = d.toISOString().slice(0, 10);
    dayMap[iso] = null;
  }

  activities.forEach(a => {
    const d = (a.date || a.startTimeLocal || '').slice(0, 10);
    if (d in dayMap && !dayMap[d]) {
      const sp = (a.sport || '').toLowerCase();
      dayMap[d] = sp.includes('run') || sp.includes('koş') ? 'run' : (sp.includes('sail') || sp.includes('yelken') ? 'sail' : 'gym');
    }
  });

  const activeCount = Object.values(dayMap).filter(Boolean).length;
  if (badge) badge.textContent = `${activeCount}/7 Gün`;

  const keys = Object.keys(dayMap).sort();
  strip.innerHTML = keys.map((iso, idx) => {
    const kind = dayMap[iso];
    const lbl = dayNames[order[idx]];
    if (kind) {
      const ic = kind === 'run' ? 'footprints' : (kind === 'sail' ? 'compass' : 'dumbbell');
      const cls = kind === 'run'
        ? 'bg-indigo-600 text-white border border-indigo-500'
        : 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-950 border border-zinc-800 dark:border-zinc-200';
      return `<div class="flex flex-col items-center"><span class="font-mono text-[10px] text-zinc-500 font-medium mb-1.5">${lbl}</span><span class="w-7 h-7 rounded-lg ${cls} flex items-center justify-center">${lucideSvg(ic, 'w-3.5 h-3.5')}</span></div>`;
    }
    return `<div class="flex flex-col items-center"><span class="font-mono text-[10px] text-zinc-400 font-medium mb-1.5">${lbl}</span><span class="w-7 h-7 rounded-lg bg-zinc-100 dark:bg-zinc-800/70 border border-zinc-200/70 dark:border-zinc-800 text-zinc-400 font-mono text-xs flex items-center justify-center">·</span></div>`;
  }).join('');
  refreshIcons();
}

function applyAthleteBranding(overview) {
  const isDemo = Boolean(overview && overview.is_demo);
  const rawW = (overview && (overview.weight !== undefined ? overview.weight : overview.weight_kg)) || (isDemo ? 84.0 : 87.0);
  const w = String(rawW).replace('.', ',');
  const headerMeta = document.getElementById('headerAthleteMeta');
  const nameDisp = document.getElementById('profileNameDisplay');
  const badgeDisp = document.getElementById('profileBadgeDisplay');
  const descDisp = document.getElementById('profileDescDisplay');
  const avatarInit = document.getElementById('profileAvatarInitial');
  const btnRestoreLbl = document.getElementById('btnRestoreSarpLabel');
  const btnBannerRestore = document.getElementById('btnBannerRestore');
  const prefsSub = document.getElementById('prefsModalSubtitle');
  const coachGreet = document.getElementById('coachGreetingText');

  if (isDemo) {
    if (headerMeta) headerMeta.innerHTML = `Demo Athlete · Sentetik Profil · ${w} kg · Örnek Garmin Verisi`;
    if (avatarInit) avatarInit.textContent = 'D';
    if (nameDisp) nameDisp.textContent = 'Demo Athlete (Sentetik Telemetri)';
    if (badgeDisp) badgeDisp.textContent = 'Örnek Demo Verisi';
    if (descDisp) descDisp.textContent = `Haftalık 2 Koşu + 2 Gym (A/B 5x5) · ${w} kg → 78,0 kg Demo Hedefi`;
    if (btnRestoreLbl) btnRestoreLbl.textContent = 'Demo Telemetrisine Dön';
    if (btnBannerRestore) btnBannerRestore.textContent = 'Demo Profiline Geri Dön';
    if (prefsSub) prefsSub.textContent = 'Demo planı hazır; başka sporcular için tercihleri buradan';
    if (coachGreet) coachGreet.textContent = 'Merhaba! Ben sentetik Garmin Connect veritabanına bağlı yapay zeka spor koçunum. Bugünkü toparlanma';
  } else {
    if (headerMeta) headerMeta.innerHTML = `Sarp · 22 Yaş · 186 cm · ${w} kg (<span class="text-emerald-600 dark:text-emerald-400 font-medium">-8,0 kg</span>) · 93 Günlük Garmin Verisi`;
    if (avatarInit) avatarInit.textContent = 'S';
    if (nameDisp) nameDisp.textContent = 'Sarp (Özel Telemetri)';
    if (badgeDisp) badgeDisp.textContent = 'Orijinal Garmin Verisi';
    if (descDisp) descDisp.textContent = `Haftalık 2 Koşu + 2 Gym (A/B 5x5) · ${w} kg → 81,0 kg İdeal Hedef`;
    if (btnRestoreLbl) btnRestoreLbl.textContent = "Orijinal Telemetriye Dön";
    if (btnBannerRestore) btnBannerRestore.textContent = "Sarp'ın Profili'ne Geri Dön";
    if (prefsSub) prefsSub.textContent = "Varsayılan plan hazır; başkaları için tercihleri buradan";
    if (coachGreet) coachGreet.textContent = 'Merhaba Sarp! Ben 3 aylık Garmin Connect veritabanına bağlı kişisel spor koçunum. Bugünkü toparlanma';
  }
}

function applyCustomProfileToUI(plan) {
  currentActiveProfile = plan;
  const isSarp = plan.is_sarp;
  const isDemo = Boolean(globalOverview && globalOverview.is_demo);

  const nameDisp = document.getElementById('profileNameDisplay');
  const badgeDisp = document.getElementById('profileBadgeDisplay');
  const descDisp = document.getElementById('profileDescDisplay');
  const avatarInit = document.getElementById('profileAvatarInitial');
  const btnRestore = document.getElementById('btnRestoreSarp');
  const customBanner = document.getElementById('customProfileBanner');

  if (isSarp) {
    nameDisp.textContent = isDemo ? "Demo Athlete (Sentetik Telemetri)" : "Sarp (Özel Telemetri)";
    badgeDisp.textContent = isDemo ? "Örnek Demo Verisi" : "Orijinal Garmin Verisi";
    badgeDisp.className = "font-mono text-[10px] font-medium px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20";
    descDisp.textContent = isDemo
      ? "Haftalık 2 Koşu + 2 Gym (A/B 5x5) · 84,0 kg → 78,0 kg Demo Hedefi"
      : "Haftalık 2 Koşu + 2 Gym (A/B 5x5) · 87,0 kg → 81,0 kg İdeal Hedef";
    avatarInit.textContent = isDemo ? "D" : "S";
    avatarInit.className = "w-9 h-9 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-semibold text-sm shrink-0";
    if (btnRestore) btnRestore.classList.add('hidden');
    if (customBanner) customBanner.classList.add('hidden');
  } else {
    const m = plan.metrics || {};
    nameDisp.textContent = plan.athlete_name + " (Özel Tercihler)";
    badgeDisp.textContent = `${m.weekly_running_days || 0} Koşu + ${m.weekly_gym_days || 0} Gym`;
    badgeDisp.className = "font-mono text-[10px] font-medium px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-500/20";
    descDisp.textContent = `${m.current_weight_kg || 80} kg → ${m.target_weight_kg || 75} kg (${m.days_to_goal || 0} Gün, ${m.target_calories_kcal || 2400} kcal/gün)`;
    avatarInit.textContent = (plan.athlete_name || "M").charAt(0).toUpperCase();
    avatarInit.className = "w-9 h-9 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-950 flex items-center justify-center font-semibold text-sm shrink-0";
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
