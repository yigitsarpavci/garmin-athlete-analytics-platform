/* Garmin Athlete IQ — Core State, Theme, Navigation & Precision Helpers */
let globalOverview = null;
let globalActivities = null;
let globalGymTypeByDate = {};

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

function restoreSavedNavigation() {
  try {
    const savedTab = localStorage.getItem(STORAGE_TAB_KEY);
    if (savedTab && document.getElementById('section-' + savedTab)) {
      setTab(savedTab, false);
    }
  } catch (_) {}
}

/* TEK EKRAN KURALI: hiçbir sayfa kaydırma gerektirmez. İçerik pencere yüksekliğini aşarsa, görünür sayfanın içeriği otomatik küçültülür (zoom).
   Tablolar kendi içinde kaydırılır; çok küçülmesi gerekirse (<0.7) o sayfa kaydırmaya döner. Mobilde (<640px) uygulanmaz. */
const FIT_MIN_ZOOM = 0.7;
let _fitBusy = false;
function _fitContainer(c) {
  const kids = [...c.children].filter(k => k.offsetParent !== null || k.tagName === 'SECTION');
  kids.forEach(k => { k.style.zoom = ''; });
  c.style.overflowY = '';
  if (window.innerWidth < 640 || !c.clientHeight) return;
  let z = 1;
  while (z > FIT_MIN_ZOOM && c.scrollHeight > c.clientHeight + 1) {
    z = Math.max(FIT_MIN_ZOOM, +(z - 0.03).toFixed(2));
    kids.forEach(k => { k.style.zoom = String(z); });
  }
  c.style.overflowY = c.scrollHeight > c.clientHeight + 1 ? 'auto' : 'hidden';
}
function fitVisibleToScreen() {
  if (_fitBusy) return;
  _fitBusy = true;
  try {
    document.querySelectorAll('#section-overview, #section-health, .single-screen-pane').forEach(c => {
      if (c.offsetParent !== null && !c.matches('[data-subpane-group="overview"]')) _fitContainer(c);
    });
  } finally {
    _fitBusy = false;
  }
}
let _fitTimer = null;
function scheduleOverviewFit() {
  clearTimeout(_fitTimer);
  _fitTimer = setTimeout(fitVisibleToScreen, 60);
}
window.addEventListener('resize', scheduleOverviewFit);
window.addEventListener('DOMContentLoaded', scheduleOverviewFit);

function setTab(tabId, persist = true) {
  let targetTab = tabId;
  if (tabId === 'activities') {
    targetTab = 'history';
  } else if (tabId === 'settings' || tabId === 'training_load' || tabId === 'analytics') {
    targetTab = 'health';
  }

  const tabs = ['overview', 'sports', 'history', 'health'];
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
  scheduleOverviewFit();

}

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  // Açık <dialog> varsa tarayıcı Esc'i kendisi işler; yoksa AI koç paneli kapatılır ve odak tetikleyiciye döner
  const flyout = document.getElementById('aiCoachFlyout');
  if (flyout && !flyout.classList.contains('hidden') && !document.querySelector('dialog[open]')) toggleAICoach();
});
/* Boş / hatalı durumlar için kullanıcıya ne yapacağını söyleyen şerit */
function renderStatusBanner(overview) {
  const el = document.getElementById('statusBanner');
  if (!el) return;
  const msgs = [];
  if (!overview) {
    msgs.push('Sunucuya ulaşılamadı. Uygulamanın çalıştığından emin olun (<code>make run</code>) ve sayfayı yenileyin.');
  } else if (overview.weight === undefined || overview.weight === null) {
    msgs.push('Henüz Garmin verisi yok. <code>make fetch</code> ile verilerinizi indirin veya <code>python3 app/server.py --demo</code> ile demo verisini deneyin.');
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
      gymData,
      activities,
      corrData,
      progData,
      protocolsData
    ] = await Promise.all([
      safeFetchJson('/api/overview'),
      safeFetchJson('/api/gym-history'),
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
    if (gymData) {
      globalGymTypeByDate = {};
      (gymData.sessions || []).forEach(s => {
        if (s && s.date && s.workout_type) globalGymTypeByDate[String(s.date).slice(0, 10)] = s.workout_type;
      });
      renderGymHistory(gymData);
    }
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
    scheduleOverviewFit();
  } catch (err) {
    console.error("Yükleme hatası:", err);
  }
}

/* Veri izleyici: sunucu diskte yeni Garmin verisi görünce (otomatik sync veya elle make fetch) data_version değişir; sayfa kendiliğinden yenilenir */
let _lastDataVersion = null;
let _dataWatchBusy = false;
async function checkDataVersion() {
  if (_dataWatchBusy || document.hidden) return;
  _dataWatchBusy = true;
  try {
    const res = await fetch('/api/status', { cache: 'no-store' });
    if (!res.ok) return;
    const st = await res.json();
    const ver = st && st.data_version;
    if (!ver) return;
    if (_lastDataVersion !== null && ver !== _lastDataVersion) {
      _lastDataVersion = ver;
      await initApp();
    } else {
      _lastDataVersion = ver;
    }
  } catch (_) {
    /* sunucuya geçici ulaşılamadı: bir sonraki turda tekrar denenir */
  } finally {
    _dataWatchBusy = false;
  }
}
window.addEventListener('DOMContentLoaded', () => {
  checkDataVersion();
  setInterval(checkDataVersion, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) checkDataVersion(); });
});

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

function _classifyRunLogoKind(a) {
  const te = String(a.te_label || '').toUpperCase();
  const anTe = Number(a.anTE || 0);
  const nm = String(a.name || '').toLowerCase();
  if (anTe >= 1.5 || te.includes('ANAEROBIC') || te.includes('SPEED') || te.includes('VO2') || nm.includes('interval')) {
    return 'interval';
  }
  if (te.includes('TEMPO') || te.includes('THRESHOLD') || nm.includes('tempo') || Number(a.avg_hr || 0) >= 156) {
    return 'tempo';
  }
  return 'zone2';
}

function _getRunKindLogo(kind) {
  if (kind === 'interval') {
    return {
      label: 'İnterval',
      lblCls: 'text-[#B994E8]',
      boxCls: 'bg-[rgba(140,98,184,0.2)] text-[#B994E8] border border-[rgba(140,98,184,0.5)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 18h2v-6H3v6zm5 0h2V6H8v12zm5 0h2v-8h-2v8zm5 0h2V4h-2v14z" fill="currentColor" stroke="none"/><path d="M13 2l-2 5h3l-2 5" stroke="currentColor" stroke-width="1.6"/></svg>`
    };
  }
  if (kind === 'tempo') {
    return {
      label: 'Tempo',
      lblCls: 'ochre-text',
      boxCls: 'bg-[rgba(201,154,73,0.18)] text-[#E2B05B] border border-[rgba(201,154,73,0.5)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 16c3 0 4-6 8-6h7"/><path d="M15 6l4 4-4 4"/><line x1="4" y1="20" x2="20" y2="20" stroke-opacity="0.55"/></svg>`
    };
  }
  return {
    label: 'Zone 2',
    lblCls: 'moss-text',
    boxCls: 'bg-[rgba(122,168,125,0.16)] text-[#8BC38E] border border-[rgba(122,168,125,0.48)]',
    svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 13c2.5-3.5 5-3.5 7.5 0s5 3.5 7.5 0 3.5-2.5 5 0"/><circle cx="12" cy="7" r="1.5" fill="currentColor" stroke="none"/></svg>`
  };
}

function _classifyGymLogoKind(a) {
  const dStr = String(a.date || a.startTimeLocal || '').slice(0, 10);
  const wType = String(a.workout_type || (dStr ? globalGymTypeByDate[dStr] : '') || a.name || '').toLowerCase();
  if (wType.includes('push') || wType.includes('itme')) return 'push';
  if (wType.includes('pull') || wType.includes('çekme')) return 'pull';
  if (wType.includes('upper') || wType.includes('üst')) return 'upper';
  if (wType.includes('lower') || wType.includes('alt vücut')) return 'lower';
  if (wType.includes('leg') || wType.includes('bacak')) return 'legs';
  if (wType.includes('workout b') || /\bb\b/.test(wType)) return 'workout_b';
  if (wType.includes('workout a') || /\ba\b/.test(wType)) return 'workout_a';
  return null;
}

function _getGymKindLogo(kind) {
  const map = {
    workout_a: {
      label: 'Workout A',
      lblCls: 'text-[#4FBFB3]',
      boxCls: 'bg-[rgba(79,191,179,0.16)] text-[#4FBFB3] border border-[rgba(79,191,179,0.5)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8.5 14.5L12 5l3.5 9.5M9.7 11.5h4.6"/><line x1="4" y1="19" x2="20" y2="19"/><line x1="6" y1="17" x2="6" y2="21"/><line x1="18" y1="17" x2="18" y2="21"/></svg>`
    },
    workout_b: {
      label: 'Workout B',
      lblCls: 'text-[#E08575]',
      boxCls: 'bg-[rgba(201,106,91,0.16)] text-[#E08575] border border-[rgba(201,106,91,0.48)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5v9.5h4.2a2.3 2.3 0 0 0 0-4.6H9m0 0h3.8a2.1 2.1 0 0 0 0-4.9H9"/><line x1="4" y1="19" x2="20" y2="19"/><line x1="6" y1="17" x2="6" y2="21"/><line x1="18" y1="17" x2="18" y2="21"/></svg>`
    },
    push: {
      label: 'Push',
      lblCls: 'text-[#D98FB5]',
      boxCls: 'bg-[rgba(217,143,181,0.16)] text-[#D98FB5] border border-[rgba(217,143,181,0.5)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4M8 8l4-4 4 4"/><line x1="4" y1="20" x2="20" y2="20"/><line x1="6" y1="18" x2="6" y2="22"/><line x1="18" y1="18" x2="18" y2="22"/></svg>`
    },
    pull: {
      label: 'Pull',
      lblCls: 'text-[#6BA7D6]',
      boxCls: 'bg-[rgba(75,142,194,0.16)] text-[#6BA7D6] border border-[rgba(75,142,194,0.48)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="4" x2="20" y2="4"/><path d="M12 8v12M8 16l4 4 4-4"/></svg>`
    },
    upper: {
      label: 'Upper',
      lblCls: 'text-[#D98FB5]',
      boxCls: 'bg-[rgba(217,143,181,0.16)] text-[#D98FB5] border border-[rgba(217,143,181,0.5)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 11l8-6 8 6"/><rect x="7" y="13" width="10" height="6" rx="1"/></svg>`
    },
    lower: {
      label: 'Lower',
      lblCls: 'moss-text',
      boxCls: 'bg-[rgba(122,168,125,0.16)] text-[#8BC38E] border border-[rgba(122,168,125,0.48)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="5" x2="19" y2="5"/><path d="M7 9l5 10 5-10"/></svg>`
    },
    legs: {
      label: 'Legs',
      lblCls: 'moss-text',
      boxCls: 'bg-[rgba(122,168,125,0.16)] text-[#8BC38E] border border-[rgba(122,168,125,0.48)]',
      svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="5" x2="19" y2="5"/><path d="M8 9v5l-2 5M16 9v5l2 5"/></svg>`
    }
  };
  return map[kind] || null;
}

function _buildStreakActivityEntry(a) {
  const sp = (a.sport || '').toLowerCase();
  const isRun = sp.includes('run') || sp.includes('koş');
  const isGym = sp.includes('strength') || sp.includes('kuvvet') || sp.includes('gym');
  const runKind = isRun ? _classifyRunLogoKind(a) : null;
  const runLogo = runKind ? _getRunKindLogo(runKind) : null;
  const gymKind = isGym ? _classifyGymLogoKind(a) : null;
  const gymLogo = gymKind ? _getGymKindLogo(gymKind) : null;
  const prefix = runLogo ? `${runLogo.label} · ` : (gymLogo ? `${gymLogo.label} · ` : '');
  return {
    isRun,
    runLogo,
    isGym,
    gymLogo,
    icon: getSportLucideIcon(a.sport || a.sport_tr || a.name),
    title: `${prefix}${a.name || a.sport_tr || a.sport || 'Antrenman'}${a.dur_m ? ` (${Math.round(a.dur_m)} dk)` : ''}`
  };
}

function _renderStreakDayCell(lbl, items, iso, todayIso, showLabel = true) {
  const mkLbl = (cls) => showLabel
    ? `<span class="font-mono text-[11px] ${cls} font-medium mb-1.5">${lbl}</span>`
    : '';
  if (items.length > 1) {
    const tip = items.map(i => i.title).join(' · ').replace(/"/g, '&quot;');
    return `<div class="flex flex-col items-center">${mkLbl('text-[#C9D3CC]')}<span title="${tip}" class="w-7 h-7 rounded-md bg-[rgba(201,211,204,0.12)] text-[#E3EAE5] border border-[rgba(201,211,204,0.4)] font-mono text-xs font-bold flex items-center justify-center tabular-nums">${items.length}</span></div>`;
  }
  if (items.length === 1) {
    const info = items[0];
    if (info.isRun && info.runLogo) {
      return `<div class="flex flex-col items-center">${mkLbl(info.runLogo.lblCls)}<span title="${String(info.title).replace(/"/g, '&quot;')}" class="w-7 h-7 rounded-md ${info.runLogo.boxCls} flex items-center justify-center">${info.runLogo.svg}</span></div>`;
    }
    if (info.isGym && info.gymLogo) {
      return `<div class="flex flex-col items-center">${mkLbl(info.gymLogo.lblCls)}<span title="${String(info.title).replace(/"/g, '&quot;')}" class="w-7 h-7 rounded-md ${info.gymLogo.boxCls} flex items-center justify-center">${info.gymLogo.svg}</span></div>`;
    }
    const lblCls = info.isGym ? 'text-[#D98FB5]' : 'text-[#C9D3CC]';
    const boxCls = info.isGym
      ? 'bg-[rgba(217,143,181,0.16)] text-[#D98FB5] border border-[rgba(217,143,181,0.45)]'
      : 'bg-[rgba(201,211,204,0.12)] text-[#E3EAE5] border border-[rgba(201,211,204,0.4)]';
    return `<div class="flex flex-col items-center">${mkLbl(lblCls)}<span title="${String(info.title).replace(/"/g, '&quot;')}" class="w-7 h-7 rounded-md ${boxCls} flex items-center justify-center">${lucideSvg(info.icon, 'w-3.5 h-3.5')}</span></div>`;
  }
  if (iso < todayIso) {
    return `<div class="flex flex-col items-center">${mkLbl('text-[#6BA7D6]')}<span title="Dinlenme Günü" class="w-7 h-7 rounded-md bg-[rgba(75,142,194,0.14)] text-[#6BA7D6] border border-[rgba(75,142,194,0.35)] flex items-center justify-center">${lucideSvg('bed', 'w-3.5 h-3.5')}</span></div>`;
  }
  return `<div class="flex flex-col items-center">${mkLbl('text-[var(--text-muted)]')}<span class="w-7 h-7 rounded-md bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)] font-mono text-xs flex items-center justify-center">·</span></div>`;
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
    dayMap[d.toISOString().slice(0, 10)] = [];
  }

  const prevDayMap = {};
  for (let i = -7; i < 0; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    prevDayMap[d.toISOString().slice(0, 10)] = [];
  }
  let thisSessionCount = 0;
  let prevSessionCount = 0;
  activities.forEach(a => {
    const d = (a.date || a.startTimeLocal || '').slice(0, 10);
    if (d in dayMap) {
      dayMap[d].push(_buildStreakActivityEntry(a));
      thisSessionCount += 1;
    }
    if (d in prevDayMap) {
      prevDayMap[d].push(_buildStreakActivityEntry(a));
      prevSessionCount += 1;
    }
  });

  if (badge) {
    badge.innerHTML = '';
  }

  const keys = Object.keys(dayMap).sort();
  const prevKeys = Object.keys(prevDayMap).sort();
  const thisWeekRow = keys.map((iso, idx) => _renderStreakDayCell(dayNames[order[idx]], dayMap[iso] || [], iso, todayIso, true)).join('');
  const prevDivider = `<div style="grid-column: 1 / -1;" class="flex items-center justify-between pt-1.5 mt-0.5 border-t border-[var(--border-subtle)]"><span class="font-mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Geçen Hafta</span></div>`;
  const prevWeekRow = prevKeys.map((iso, idx) => _renderStreakDayCell(dayNames[order[idx]], prevDayMap[iso] || [], iso, todayIso, false)).join('');
  strip.innerHTML = `${thisWeekRow}${prevDivider}${prevWeekRow}`;
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
