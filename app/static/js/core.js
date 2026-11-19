/* Garmin Athlete IQ — Core State, Theme, Navigation & Precision Helpers */
let globalOverview = null;
let globalSports = null;
let globalActivities = null;
let globalCharts = null;
let currentActiveProfile = {
  is_current_athlete: true,
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
  }
}

function closeAllNavDropdowns() {
  document.querySelectorAll('.nav-dropdown.is-open').forEach(el => {
    el.classList.remove('is-open');
  });
  document.querySelectorAll('.nav-dropdown > .nav-tab[aria-haspopup]').forEach(btn => btn.setAttribute('aria-expanded', 'false'));
}

function toggleNavDropdown(tabId, ev) {
  if (ev) ev.stopPropagation();
  const wrap = document.querySelector(`.nav-dropdown[data-nav-dropdown="${tabId}"]`);
  const wasOpen = wrap ? wrap.classList.contains('is-open') : false;
  closeAllNavDropdowns();
  setTab(tabId);
  if (wrap && !wasOpen) {
    wrap.classList.add('is-open');
    const trigger = wrap.querySelector(':scope > .nav-tab');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
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
  if (e.key !== 'Escape') return;
  closeAllNavDropdowns();
  // Açık <dialog> varsa tarayıcı Esc'i kendisi işler; yoksa AI koç paneli kapatılır ve odak tetikleyiciye döner
  const flyout = document.getElementById('aiCoachFlyout');
  if (flyout && !flyout.classList.contains('hidden') && !document.querySelector('dialog[open]')) toggleAICoach();
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

/* Boş / hatalı durumlar için kullanıcıya ne yapacağını söyleyen şerit */
function renderStatusBanner(overview) {
  const el = document.getElementById('statusBanner');
  if (!el) return;
  const msgs = [];
  if (!overview) {
    msgs.push('Sunucuya ulaşılamadı. Uygulamanın çalıştığından emin olun (<code>make run</code>) ve sayfayı yenileyin.');
  } else if (overview.weight === undefined || overview.weight === null) {
    msgs.push('Henüz Garmin verisi yok. <code>make fetch</code> ile verilerinizi indirin veya <code>python3 app/server.py --demo</code> ile demo verisini deneyin.');
  } else if (overview.data_is_stale) {
    const hh = String(overview.data_as_of).slice(11, 16);
    msgs.push('Garmin verileri ' + escapeHtml(hh) + ' itibarıyla (' + Math.round(overview.data_age_min / 60) + ' sa önce). Adım ve kalori, saatiniz telefondaki Garmin Connect ile eşitlendiğinde güncellenir: saati eşitleyin, sonra üstteki "Eşitle"ye basın.');
  } else if (overview.athlete && Array.isArray(overview.athlete.profile_missing) && overview.athlete.profile_missing.length) {
    msgs.push('Profiliniz eksik (' + overview.athlete.profile_missing.map(escapeHtml).join(', ') + '). <code>data/athlete_profile.json</code> dosyasını <code>athlete_profile.example.json</code> örneğine göre doldurun; yoksa tahmini varsayılanlar kullanılır.');
  }
  el.innerHTML = msgs.join(' ');
  el.classList.toggle('hidden', msgs.length === 0);
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
      corrData,
      progData,
      protocolsData
    ] = await Promise.all([
      safeFetchJson('/api/overview'),
      safeFetchJson('/api/sports'),
      safeFetchJson('/api/gym-history'),
      safeFetchJson('/api/training-load'),
      safeFetchJson('/api/activities'),
      safeFetchJson('/api/correlations'),
      safeFetchJson('/api/progression'),
      safeFetchJson('/api/daily-protocols')
    ]);

    renderStatusBanner(overview);
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
    if (corrData) renderCorrelations(corrData);
    if (progData) renderProgressionAssessment(progData);
    if (protocolsData) renderDailyProtocols(protocolsData);

    // Garmin oturum keep-alive'ı sunucudaki arka plan döngüsü yönetir (server.py:_session_keepalive_loop).
    refreshIcons();
  } catch (err) {
    console.error("Yükleme hatası:", err);
  }
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
      <span class="font-mono text-[11px] text-[var(--text-muted)] font-normal">(${a.date})</span>
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
  const todayIso = (typeof globalOverview !== 'undefined' && globalOverview && globalOverview.date)
    ? String(globalOverview.date).slice(0, 10)
    : new Date().toISOString().slice(0, 10);
  const refStr = todayIso || latestStr;
  const refDate = refStr ? new Date(refStr + 'T12:00:00') : new Date();
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
        isGym: sp.includes('strength') || sp.includes('kuvvet') || sp.includes('gym'),
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
    badge.innerHTML = `${thisSessionCount} Seans <span class="text-[11px] font-normal text-[var(--text-secondary)] ml-1.5">· Geçen Hafta: ${prevSessionCount} Seans</span>`;
  }

  const keys = Object.keys(dayMap).sort();
  strip.innerHTML = keys.map((iso, idx) => {
    const items = dayMap[iso] || [];
    const lbl = dayNames[order[idx]];
    if (items.length > 1) {
      const tip = items.map(i => i.title).join(' · ').replace(/"/g, '&quot;');
      return `<div class="flex flex-col items-center"><span class="font-mono text-[11px] text-[#AB86D4] font-medium mb-1.5">${lbl}</span><span title="${tip}" class="w-7 h-7 rounded-[2px] bg-[rgba(140,98,184,0.18)] text-[#AB86D4] border border-[rgba(140,98,184,0.45)] font-mono text-xs font-bold flex items-center justify-center tabular-nums">${items.length}</span></div>`;
    }
    if (items.length === 1) {
      const info = items[0];
      const lblCls = info.isRun ? 'moss-text' : (info.isGym ? 'ochre-text' : 'text-[#AB86D4]');
      const boxCls = info.isRun
        ? 'accent-bg border border-[var(--accent)]'
        : (info.isGym
          ? 'bg-[rgba(201,154,73,0.16)] text-[#C99A49] border border-[rgba(201,154,73,0.45)]'
          : 'bg-[rgba(140,98,184,0.18)] text-[#AB86D4] border border-[rgba(140,98,184,0.45)]');
      return `<div class="flex flex-col items-center"><span class="font-mono text-[11px] ${lblCls} font-medium mb-1.5">${lbl}</span><span title="${String(info.title).replace(/"/g, '&quot;')}" class="w-7 h-7 rounded-[2px] ${boxCls} flex items-center justify-center">${lucideSvg(info.icon, 'w-3.5 h-3.5')}</span></div>`;
    }
    if (iso < todayIso) {
      return `<div class="flex flex-col items-center"><span class="font-mono text-[11px] text-[#6BA7D6] font-medium mb-1.5">${lbl}</span><span title="Dinlenme Günü" class="w-7 h-7 rounded-[2px] bg-[rgba(75,142,194,0.14)] text-[#6BA7D6] border border-[rgba(75,142,194,0.35)] flex items-center justify-center">${lucideSvg('bed', 'w-3.5 h-3.5')}</span></div>`;
    }
    return `<div class="flex flex-col items-center"><span class="font-mono text-[11px] text-[var(--text-muted)] font-medium mb-1.5">${lbl}</span><span class="w-7 h-7 rounded-[2px] bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)] font-mono text-xs flex items-center justify-center">·</span></div>`;
  }).join('');
  refreshIcons();
}

function applyAthleteBranding(overview) {
  const isDemo = Boolean(overview && overview.is_demo);
  const coachGreet = document.getElementById('coachGreetingText');

  if (isDemo) {
    if (coachGreet) coachGreet.textContent = 'Merhaba! Ben sentetik Garmin Connect veritabanına bağlı yapay zeka spor koçunum. Bugünkü toparlanma';
  } else {
    if (coachGreet) coachGreet.textContent = (overview && overview.athlete && overview.athlete.name ? 'Merhaba ' + overview.athlete.name + '! ' : 'Merhaba! ') + 'Ben 3 aylık Garmin Connect veritabanına bağlı kişisel spor koçunum. Bugünkü toparlanma';
  }
}


// ---------------------------------------------------------------------------
// Olay yönlendirici: satır içi onclick/oninput/onkeydown yerine data-* öznitelikleri
//   data-calls='[["setTab","plan"],["fn", "@event"]]'  -> sırayla window[fn](...args) çağrılır ("@event" = tarayıcı olayı)
//   data-input-call="fn"                                -> input olayında fn(value)
//   data-enter-call="fn"                                -> Enter tuşunda fn()
// Böylece sıkı bir Content-Security-Policy (script-src 'self') kullanılabilir.
// ---------------------------------------------------------------------------
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-calls]');
  if (!el) return;
  let calls;
  try { calls = JSON.parse(el.dataset.calls); } catch (_) { return; }
  calls.forEach(([name, ...args]) => {
    const fn = window[name];
    if (typeof fn === 'function') fn(...args.map(a => (a === '@event' ? e : a)));
  });
});
document.addEventListener('input', (e) => {
  const name = e.target && e.target.dataset && e.target.dataset.inputCall;
  if (name && typeof window[name] === 'function') window[name](e.target.value);
});
document.addEventListener('keydown', (e) => {
  const name = e.target && e.target.dataset && e.target.dataset.enterCall;
  if (name && e.key === 'Enter' && typeof window[name] === 'function') window[name]();
});

function openLatestActivityOrDebrief() {
  if (window.globalActivities && globalActivities.length) openActivityModal(globalActivities[0]);
  else openDebriefModal(0);
}
