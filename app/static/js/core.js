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

  if (tabId === 'analytics' && document.getElementById('chart-hrv')) {
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
  if (group === 'analytics' && paneKey === 'charts' && document.getElementById('chart-hrv')) {
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

    chartInstances = {};
    const analyticsSec = document.getElementById('section-analytics');
    if (analyticsSec && !analyticsSec.classList.contains('hidden') && document.getElementById('chart-hrv') && typeof renderCharts === 'function') {
      renderCharts(true);
    }

    runCalculator();
    refreshIcons();
  } catch (err) {
    console.error("Yükleme hatası:", err);
  }
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
        <button type="button" onclick="applyPresetToForm('${p.id}')" class="btn-secondary text-[11px] px-2.5 py-1.5">
          ${lucideSvg(p.is_current_athlete ? 'activity' : 'zap', 'w-3.5 h-3.5 accent-text')}
          <span>${p.name}</span>
        </button>
      `).join('');
  refreshIcons();
}

function openPreferencesModal() {
  const modal = document.getElementById('preferencesModal');
  if (modal && !modal.open) {
    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.setAttribute('open', '');
    }
  }
}

function closePreferencesModal() {
  const modal = document.getElementById('preferencesModal');
  if (modal && modal.open) {
    if (typeof modal.close === 'function') {
      modal.close();
    } else {
      modal.removeAttribute('open');
    }
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
  const targetW = (overview && overview.target_weight !== undefined) ? String(overview.target_weight).replace('.', ',') : (isDemo ? '78,0' : '81,0');
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
    if (headerMeta) headerMeta.textContent = `Demo Athlete · Sentetik Profil · ${w} kg · Örnek Garmin Verisi`;
    if (avatarInit) avatarInit.textContent = 'D';
    if (nameDisp) nameDisp.textContent = 'Demo Athlete (Sentetik Telemetri)';
    if (badgeDisp) badgeDisp.textContent = 'Örnek Demo Verisi';
    if (descDisp) descDisp.textContent = `Haftalık 2 Koşu + 2 Kuvvet (Esnek Gün · A/B 5x5) · ${w} kg → ${targetW} kg Hedefi`;
    if (btnRestoreLbl) btnRestoreLbl.textContent = 'Demo Telemetrisine Dön';
    if (btnBannerRestore) btnBannerRestore.textContent = 'Demo Profiline Geri Dön';
    if (prefsSub) prefsSub.textContent = 'Demo planı hazır; başka sporcular için tercihleri buradan';
    if (coachGreet) coachGreet.textContent = 'Merhaba! Ben sentetik Garmin Connect veritabanına bağlı yapay zeka spor koçunum. Bugünkü toparlanma';
  } else {
    if (headerMeta) headerMeta.innerHTML = `Sarp · 22 Yaş · 186 cm · ${w} kg (<span class="moss-text font-medium">-${lossKg} kg</span>) · 93G Telemetri`;
    if (avatarInit) avatarInit.textContent = 'S';
    if (nameDisp) nameDisp.textContent = 'Sarp (Kişisel Telemetri)';
    if (badgeDisp) badgeDisp.textContent = 'Garmin Connect Verisi';
    if (descDisp) descDisp.textContent = `Haftalık 2 Koşu + 2 Kuvvet (Esnek Gün · A/B 5x5) · ${w} kg → ${targetW} kg İdeal Hedef`;
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
  const kpiTarget = document.getElementById('kpi-weight-target');
  const svgTarget = document.getElementById('svgPaceTargetWeight');
  const svgCur = document.getElementById('svgPaceCurWeight');

  if (isSarp) {
    if (globalOverview) applyAthleteBranding(globalOverview);
    if (badgeDisp) badgeDisp.className = "stamp-tag stamp-moss";
    if (avatarInit) avatarInit.className = "w-9 h-9 rounded-[3px] accent-bg flex items-center justify-center font-mono font-semibold text-sm shrink-0";
    if (btnRestore) btnRestore.classList.add('hidden');
    if (customBanner) customBanner.classList.add('hidden');
    if (globalOverview && typeof renderOverview === 'function') renderOverview(globalOverview);
  } else {
    const m = plan.metrics || {};
    if (nameDisp) nameDisp.textContent = plan.athlete_name + " (Özel Tercihler)";
    if (badgeDisp) {
      badgeDisp.textContent = `${m.weekly_running_days || 0} Koşu + ${m.weekly_gym_days || 0} Gym`;
      badgeDisp.className = "stamp-tag stamp-accent";
    }
    if (descDisp) descDisp.textContent = `${m.current_weight_kg || 80} kg → ${m.target_weight_kg || 75} kg (${m.days_to_goal || 0} Gün, ${m.target_calories_kcal || 2400} kcal/gün)`;
    if (avatarInit) {
      avatarInit.textContent = (plan.athlete_name || "M").charAt(0).toUpperCase();
      avatarInit.className = "w-9 h-9 rounded-[3px] bg-[var(--text-primary)] text-[var(--bg-surface)] flex items-center justify-center font-mono font-semibold text-sm shrink-0";
    }
    if (btnRestore) btnRestore.classList.remove('hidden');
    if (customBanner) {
      customBanner.classList.remove('hidden');
      const bannerTitle = document.getElementById('customBannerTitle');
      const bannerText = document.getElementById('customBannerText');
      if (bannerTitle) bannerTitle.textContent = `${(plan.athlete_name || '').toUpperCase()} İÇİN ÖZEL PLAN AKTİF`;
      if (bannerText) bannerText.textContent = `Haftalık esnek kota, ${m.weekly_running_days} koşu ve ${m.weekly_gym_days} kuvvet seansı tercihine göre güncellenmiştir. Günlük hedef: ${m.target_calories_kcal} kcal (${m.protein_g}g Protein).`;
    }
    if (kpiTarget && m.target_weight_kg) kpiTarget.textContent = `Hedef: ${m.target_weight_kg} kg`;
    if (svgTarget && m.target_weight_kg) svgTarget.textContent = `${m.target_weight_kg} kg Hedef`;
    if (svgCur && m.current_weight_kg) svgCur.textContent = `${m.current_weight_kg} kg Mevcut`;
  }

  renderWeeklyScheduleTable(plan.schedule);
  const quotaPayload = plan.quota_summary || plan.weekly_quota || (globalOverview && globalOverview.weekly_quota);
  if (quotaPayload && typeof renderWeeklyQuotaPanels === 'function') {
    renderWeeklyQuotaPanels(quotaPayload);
  }
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
    if (globalOverview && globalOverview.weekly_quota && typeof renderWeeklyQuotaPanels === 'function') {
      renderWeeklyQuotaPanels(globalOverview.weekly_quota);
    }
  }
}
