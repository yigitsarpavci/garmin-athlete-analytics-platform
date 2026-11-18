/* Garmin Athlete IQ — Core State, Theme, Navigation & Precision Helpers */
let globalOverview = null;
let globalSports = null;
let globalActivities = null;
let globalCharts = null;
let chartInstances = {};
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

// TEMA YÖNETİMİ (KİLİT FULL DARK MODE)

function initTheme() {
  applyTheme(true);
}

function applyTheme() {
  document.documentElement.classList.add('dark');
  document.documentElement.classList.remove('light');
  localStorage.setItem('garmin_app_theme', 'dark');
  refreshIcons();
  if (typeof updateChartThemes === 'function') {
    updateChartThemes(true);
  }
}

function toggleTheme() {
  applyTheme(true);
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
  let targetTab = tabId;
  if (tabId === 'activities') {
    targetTab = 'training_load';
  } else if (tabId === 'analytics') {
    targetTab = 'health';
  }

  const tabs = ['overview', 'plan', 'sports', 'training_load', 'health', 'settings'];
  tabs.forEach(t => {
    const sec = document.getElementById('section-' + t);
    const nav = document.getElementById('nav-' + t);
    if (t === targetTab) {
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

  if (tabId === 'activities') {
    setSubTab('training_load', 'activities');
  } else if (tabId === 'analytics') {
    setSubTab('health', 'metrics');
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
  if (group === 'analytics' && paneKey === 'charts' && document.getElementById('chart-hrv')) {
    renderCharts();
  }
}

async function initApp() {
  try {
    initTheme();

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

    if (document.getElementById('sameDayTableBody')) {
      const seqData = await safeFetchJson('/api/same-day-sequence');
      if (seqData) renderSameDaySequence(seqData);
    }

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

    if (document.getElementById('periodsContainer')) {
      const periodsData = await safeFetchJson('/api/periods-weeks');
      if (periodsData) renderPeriods(periodsData);
    }

    const setData = await safeFetchJson('/api/garmin-settings');
    if (setData) renderSettingsAndZones(setData);

    if (document.getElementById('z2KpiGrid')) {
      const z2Data = await safeFetchJson('/api/z2-tracker');
      if (z2Data) renderZ2Tracker(z2Data);
    }

    if (document.getElementById('morphologyCardsContainer')) {
      const morphData = await safeFetchJson('/api/physique-tracker');
      if (morphData) renderPhysiqueTracker(morphData);
    }

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

    chartInstances = {};
    const analyticsSec = document.getElementById('section-analytics');
    if (analyticsSec && !analyticsSec.classList.contains('hidden') && document.getElementById('chart-hrv') && typeof renderCharts === 'function') {
      renderCharts(true);
    }

    if (document.getElementById('calcTargetInput')) runCalculator();
    startGarminSessionKeepAlive();
    refreshIcons();
  } catch (err) {
    console.error("Yükleme hatası:", err);
  }
}

function startGarminSessionKeepAlive() {
  if (window.__garminKeepAliveStarted) return;
  window.__garminKeepAliveStarted = true;

  const checkAndRefreshSession = async () => {
    try {
      const status = await safeFetchJson('/api/status');
      const sess = status && status.session;
      if (sess && sess.session_file_exists && typeof sess.jwt_remaining_sec === 'number' && sess.jwt_remaining_sec < 420) {
        await fetch('/api/session/keepalive', { method: 'POST' });
      }
    } catch (_) {
      // Arka plan oturum yenileme sessizce sürer
    }
  };

  window.__garminKeepAliveTimer = setInterval(checkAndRefreshSession, 240000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      checkAndRefreshSession();
    }
  });
}

async function syncGarminData() {
  const btn = document.getElementById('syncBtn');
  if (btn) {
    btn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 animate-spin accent-text')}<span class="hidden xl:inline">Eşitleniyor...</span>`;
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
      btn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 text-[var(--text-secondary)]')}<span class="hidden xl:inline">Eşitle</span>`;
      refreshIcons();
    }
  }
}

function getSportLucideIcon(sportStr) {
  const sp = (sportStr || '').toLowerCase();
  if (sp.includes('run') || sp.includes('koş')) return 'footprints';
  if (sp.includes('sail') || sp.includes('yelken')) return 'compass';
  if (sp.includes('basket')) return 'trophy';
  if (sp.includes('ski') || sp.includes('snow') || sp.includes('kayak')) return 'snowflake';
  if (sp.includes('hike') || sp.includes('doğa') || sp.includes('mount')) return 'mountain';
  if (sp.includes('swim') || sp.includes('row') || sp.includes('yüz') || sp.includes('kürek')) return 'waves';
  if (sp.includes('cycl') || sp.includes('bik') || sp.includes('bisik')) return 'bike';
  if (sp.includes('walk') || sp.includes('yürü')) return 'footprints';
  if (sp.includes('strength') || sp.includes('kuvvet') || sp.includes('gym')) return 'dumbbell';
  return 'activity';
}

function renderLatestActivitySummary(activities) {
  const row = document.getElementById('latestActivitySummaryRow');
  if (!row || !Array.isArray(activities) || !activities.length) return;
  const a = activities[0];
  const iconName = getSportLucideIcon(a.sport || a.sport_tr || a.name);
  const dur = a.dur_m ? `${Math.round(a.dur_m)} dk` : '--';
  const hr = a.avg_hr ? `${a.avg_hr} bpm` : '--';
  row.innerHTML = `
    <span class="font-medium truncate flex items-center gap-2">
      ${lucideSvg(iconName, 'w-3.5 h-3.5 accent-text shrink-0')}
      <span class="truncate">${a.name || a.sport_tr || a.sport || 'Antrenman'}</span>
      <span class="font-mono text-[10px] text-[var(--text-muted)] font-normal">(${a.date})</span>
    </span>
    <span class="font-mono text-[11px] text-[var(--text-secondary)] font-medium tabular-nums shrink-0 ml-2">${dur} · ${hr}</span>
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
      dayMap[d] = {
        isRun: sp.includes('run') || sp.includes('koş'),
        icon: getSportLucideIcon(a.sport || a.sport_tr || a.name)
      };
    }
  });

  const activeCount = Object.values(dayMap).filter(Boolean).length;
  if (badge) badge.textContent = `${activeCount}/7 Gün`;

  const keys = Object.keys(dayMap).sort();
  strip.innerHTML = keys.map((iso, idx) => {
    const info = dayMap[iso];
    const lbl = dayNames[order[idx]];
    if (info) {
      const cls = info.isRun
        ? 'accent-bg border border-[var(--accent)]'
        : 'bg-[var(--text-primary)] text-[var(--bg-surface)] border border-[var(--text-primary)]';
      return `<div class="flex flex-col items-center"><span class="font-mono text-[10px] text-[var(--text-secondary)] font-medium mb-1.5">${lbl}</span><span class="w-7 h-7 rounded-[2px] ${cls} flex items-center justify-center">${lucideSvg(info.icon, 'w-3.5 h-3.5')}</span></div>`;
    }
    return `<div class="flex flex-col items-center"><span class="font-mono text-[10px] text-[var(--text-muted)] font-medium mb-1.5">${lbl}</span><span class="w-7 h-7 rounded-[2px] bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)] font-mono text-xs flex items-center justify-center">·</span></div>`;
  }).join('');
  refreshIcons();
}

function applyAthleteBranding(overview) {
  const isDemo = Boolean(overview && overview.is_demo);
  const rawW = (overview && (overview.weight !== undefined ? overview.weight : overview.weight_kg)) || (isDemo ? 84.0 : 87.0);
  const lossKg = (overview && overview.total_loss_kg !== undefined) ? String(overview.total_loss_kg).replace('.', ',') : '8,0';
  const w = String(rawW).replace('.', ',');
  const headerMeta = document.getElementById('headerAthleteMeta');
  const coachGreet = document.getElementById('coachGreetingText');

  if (isDemo) {
    if (headerMeta) headerMeta.textContent = `Demo Athlete · Sentetik Profil · ${w} kg · Örnek Garmin Verisi`;
    if (coachGreet) coachGreet.textContent = 'Merhaba! Ben sentetik Garmin Connect veritabanına bağlı yapay zeka spor koçunum. Bugünkü toparlanma';
  } else {
    if (headerMeta) headerMeta.innerHTML = `Sarp · 22 Yaş · 186 cm · ${w} kg (<span class="moss-text font-medium">-${lossKg} kg</span>) · 93G Telemetri`;
    if (coachGreet) coachGreet.textContent = 'Merhaba Sarp! Ben 3 aylık Garmin Connect veritabanına bağlı kişisel spor koçunum. Bugünkü toparlanma';
  }
}
