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

const STORAGE_TAB_KEY = 'garmin_active_tab';
const STORAGE_SUBTABS_KEY = 'garmin_active_subtabs';

function saveActiveSubTab(group, paneKey) {
  try {
    const raw = localStorage.getItem(STORAGE_SUBTABS_KEY);
    const map = raw ? JSON.parse(raw) : {};
    map[group] = paneKey;
    localStorage.setItem(STORAGE_SUBTABS_KEY, JSON.stringify(map));
  } catch (_) {}
}

function restoreSavedNavigation() {
  try {
    const savedTab = localStorage.getItem(STORAGE_TAB_KEY);
    const rawSubs = localStorage.getItem(STORAGE_SUBTABS_KEY);
    const subMap = rawSubs ? JSON.parse(rawSubs) : {};

    if (subMap && typeof subMap === 'object') {
      Object.entries(subMap).forEach(([group, paneKey]) => {
        if (document.querySelector(`[data-subpane-group="${group}"][data-subpane="${paneKey}"]`)) {
          setSubTab(group, paneKey, false);
        }
      });
    }
    if (savedTab && document.getElementById('section-' + savedTab)) {
      setTab(savedTab, false);
    }
  } catch (_) {}
}

function setTab(tabId, persist = true) {
  let targetTab = tabId;
  if (tabId === 'activities' || tabId === 'settings') {
    targetTab = 'training_load';
  } else if (tabId === 'analytics') {
    targetTab = 'health';
  }

  const tabs = ['overview', 'plan', 'sports', 'training_load', 'health'];
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

  if (persist) {
    try { localStorage.setItem(STORAGE_TAB_KEY, targetTab); } catch (_) {}
  }

  if (tabId === 'activities') {
    setSubTab('training_load', 'activities', persist);
  } else if (tabId === 'analytics') {
    setSubTab('health', 'metrics', persist);
  }
}

function closeAllNavDropdowns() {
  document.querySelectorAll('.nav-dropdown.is-open').forEach(el => {
    el.classList.remove('is-open');
  });
}

function toggleNavDropdown(tabId, ev) {
  if (ev) ev.stopPropagation();
  const wrap = document.querySelector(`.nav-dropdown[data-nav-dropdown="${tabId}"]`);
  const wasOpen = wrap ? wrap.classList.contains('is-open') : false;
  closeAllNavDropdowns();
  setTab(tabId);
  if (wrap && !wasOpen) {
    wrap.classList.add('is-open');
  }
}

function selectNavSubTab(tabId, subTabId, ev) {
  if (ev) ev.stopPropagation();
  setTab(tabId);
  setSubTab(tabId, subTabId);
  closeAllNavDropdowns();
  if (document.activeElement && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.nav-dropdown')) {
    closeAllNavDropdowns();
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeAllNavDropdowns();
});
document.querySelectorAll('.nav-dropdown').forEach(wrap => {
  wrap.addEventListener('mouseenter', () => {
    document.querySelectorAll('.nav-dropdown.is-open').forEach(openEl => {
      if (openEl !== wrap) openEl.classList.remove('is-open');
    });
    const active = document.activeElement;
    if (active && active.closest('.nav-dropdown') && active.closest('.nav-dropdown') !== wrap && typeof active.blur === 'function') {
      active.blur();
    }
  });
});

function setSubTab(group, paneKey, persist = true) {
  document.querySelectorAll(`[data-subpane-group="${group}"]`).forEach(el => {
    el.classList.toggle('hidden', el.dataset.subpane !== paneKey);
  });
  document.querySelectorAll(`[data-subtab-group="${group}"]`).forEach(btn => {
    const active = btn.dataset.subtab === paneKey;
    if (btn.classList.contains('nav-dropdown-item')) {
      btn.className = active ? 'nav-dropdown-item nav-dropdown-item-active' : 'nav-dropdown-item';
    } else {
      btn.className = active ? 'subtab-btn subtab-btn-active' : 'subtab-btn';
    }
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  if (persist) saveActiveSubTab(group, paneKey);
}

async function initApp() {
  try {
    initTheme();
    restoreSavedNavigation();

    const [
      overview,
      sports,
      gymData,
      tlData,
      activities,
      sleepData,
      corrData,
      progData,
      protocolsData
    ] = await Promise.all([
      safeFetchJson('/api/overview'),
      safeFetchJson('/api/sports'),
      safeFetchJson('/api/gym-history'),
      safeFetchJson('/api/training-load'),
      safeFetchJson('/api/activities'),
      safeFetchJson('/api/sleep-analysis'),
      safeFetchJson('/api/correlations'),
      safeFetchJson('/api/progression'),
      safeFetchJson('/api/daily-protocols')
    ]);

    if (overview) {
      globalOverview = overview;
      applyAthleteBranding(globalOverview);
      renderOverview(globalOverview);
    }
    if (sports) {
      globalSports = sports;
      renderSports(globalSports);
    }
    if (gymData) renderGymHistory(gymData);
    if (tlData) renderTrainingLoad(tlData);
    if (activities) {
      globalActivities = activities;
      renderActivities(globalActivities);
      renderWeeklyStreak(globalActivities);
      renderLatestActivitySummary(globalActivities);
    }
    if (sleepData) renderSleepAnalysis(sleepData);
    if (corrData) renderCorrelations(corrData);
    if (progData) renderProgressionAssessment(progData);
    if (protocolsData) renderDailyProtocols(protocolsData);

    chartInstances = {};
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
  let syncedOk = false;
  let sessionExpired = false;
  let errMsg = '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 animate-spin accent-text')}<span class="hidden sm:inline">Eşitleniyor...</span>`;
    refreshIcons();
  }
  try {
    const res = await fetch('/api/sync', { method: 'POST' });
    const resData = await res.json().catch(() => ({}));
    await initApp();
    if (res.ok && resData.success !== false) {
      syncedOk = true;
    } else {
      sessionExpired = Boolean(resData.session_expired || res.status === 401);
      errMsg = resData.message || (sessionExpired ? 'Garmin oturum süresi doldu.' : 'Senkronizasyon başarısız.');
    }
  } catch (e) {
    errMsg = e?.message || 'Bağlantı hatası';
    console.warn('Senkronizasyon uyarısı:', e);
  } finally {
    if (btn) {
      btn.disabled = false;
      if (syncedOk) {
        btn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 text-emerald-400')}<span class="hidden sm:inline text-emerald-400">✓ Eşitlendi</span>`;
        refreshIcons();
        setTimeout(() => {
          const currentBtn = document.getElementById('syncBtn');
          if (currentBtn) {
            currentBtn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 text-[var(--text-secondary)]')}<span class="hidden sm:inline">Eşitle</span>`;
            refreshIcons();
          }
        }, 2500);
      } else {
        const label = sessionExpired ? 'Oturum Doldu' : 'Eşitleme Hatası';
        btn.title = errMsg;
        btn.innerHTML = `${lucideSvg('alert-triangle', 'w-3.5 h-3.5 text-amber-400')}<span class="hidden sm:inline text-amber-400">${label}</span>`;
        refreshIcons();
        setTimeout(() => {
          const currentBtn = document.getElementById('syncBtn');
          if (currentBtn) {
            currentBtn.innerHTML = `${lucideSvg('refresh-cw', 'w-3.5 h-3.5 text-[var(--text-secondary)]')}<span class="hidden sm:inline">Eşitle</span>`;
            refreshIcons();
          }
        }, 4500);
      }
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
  const cal = a.cal ? `${Math.round(a.cal)} kcal` : '--';
  row.innerHTML = `
    <span class="font-medium truncate flex items-center gap-2">
      ${lucideSvg(iconName, 'w-3.5 h-3.5 accent-text shrink-0')}
      <span class="truncate">${a.name || a.sport_tr || a.sport || 'Antrenman'}</span>
      <span class="font-mono text-[10px] text-[var(--text-muted)] font-normal">(${a.date})</span>
    </span>
    <span class="font-mono text-[11px] text-[var(--text-secondary)] font-medium tabular-nums shrink-0 ml-2">${dur} · ${hr} · ${cal}</span>
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
    dayMap[iso] = [];
  }

  const prevDays = new Set();
  for (let i = -7; i < 0; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    prevDays.add(d.toISOString().slice(0, 10));
  }
  let thisSessionCount = 0;
  let prevSessionCount = 0;
  activities.forEach(a => {
    const d = (a.date || a.startTimeLocal || '').slice(0, 10);
    if (d in dayMap) {
      const sp = (a.sport || '').toLowerCase();
      dayMap[d].push({
        isRun: sp.includes('run') || sp.includes('koş'),
        icon: getSportLucideIcon(a.sport || a.sport_tr || a.name),
        title: `${a.name || a.sport_tr || a.sport || 'Antrenman'}${a.dur_m ? ` (${Math.round(a.dur_m)} dk)` : ''}`
      });
      thisSessionCount += 1;
    }
    if (prevDays.has(d)) {
      prevSessionCount += 1;
    }
  });

  if (badge) {
    badge.innerHTML = `${thisSessionCount} Seans <span class="text-[10px] font-normal text-[var(--text-secondary)] ml-1.5">· Geçen Hafta: ${prevSessionCount} Seans</span>`;
  }

  const keys = Object.keys(dayMap).sort();
  strip.innerHTML = keys.map((iso, idx) => {
    const items = dayMap[iso] || [];
    const lbl = dayNames[order[idx]];
    if (items.length) {
      const boxCls = items.length > 1 ? 'w-6 h-7' : 'w-7 h-7';
      const iconsHtml = items.map(info => {
        const cls = info.isRun
          ? 'accent-bg border border-[var(--accent)]'
          : 'bg-[var(--text-primary)] text-[var(--bg-surface)] border border-[var(--text-primary)]';
        return `<span title="${String(info.title).replace(/"/g, '&quot;')}" class="${boxCls} rounded-[2px] ${cls} flex items-center justify-center shrink-0">${lucideSvg(info.icon, 'w-3.5 h-3.5')}</span>`;
      }).join('');
      return `<div class="flex flex-col items-center"><span class="font-mono text-[10px] text-[var(--text-secondary)] font-medium mb-1.5">${lbl}</span><div class="inline-flex items-center justify-center gap-0.5">${iconsHtml}</div></div>`;
    }
    return `<div class="flex flex-col items-center"><span class="font-mono text-[10px] text-[var(--text-muted)] font-medium mb-1.5">${lbl}</span><span class="w-7 h-7 rounded-[2px] bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)] font-mono text-xs flex items-center justify-center">·</span></div>`;
  }).join('');
  refreshIcons();
}

function applyAthleteBranding(overview) {
  const isDemo = Boolean(overview && overview.is_demo);
  const coachGreet = document.getElementById('coachGreetingText');

  if (isDemo) {
    if (coachGreet) coachGreet.textContent = 'Merhaba! Ben sentetik Garmin Connect veritabanına bağlı yapay zeka spor koçunum. Bugünkü toparlanma';
  } else {
    if (coachGreet) coachGreet.textContent = 'Merhaba Sarp! Ben 3 aylık Garmin Connect veritabanına bağlı kişisel spor koçunum. Bugünkü toparlanma';
  }
}
