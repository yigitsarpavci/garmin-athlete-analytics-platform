/* Garmin Athlete IQ — Health, Sleep Architecture, 93d Biometrics, Morphology, Settings & Progression */

function renderSleepAnalysis(sData) {
  if (!sData) return;
  const totalNights = Array.isArray(sData.bedtime_groups)
    ? sData.bedtime_groups.reduce((acc, g) => acc + (g.count || 0), 0)
    : 0;
  const slpSub = document.getElementById('sleepBedtimeSubtitle');
  if (slpSub && totalNights > 0) {
    slpSub.textContent = `${totalNights} gecelik uyku kayıtlarının uykuya geçiş saatine göre 3 gruplu analizi:`;
  }
  const gBody = document.getElementById('bedtimeGroupsBody');
  if (gBody && Array.isArray(sData.bedtime_groups)) {
    gBody.innerHTML = '';
    sData.bedtime_groups.forEach(g => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
        <td class="py-3 px-4 font-semibold">${escapeHtml(g.group)}</td>
        <td class="py-3 px-4 font-mono text-[var(--text-secondary)]">${g.count} gece (%${g.pct})</td>
        <td class="py-3 px-4 font-mono font-semibold accent-text">${g.sleep_h} saat</td>
        <td class="py-3 px-4 font-mono">${g.deep_h} sa / <span class="font-semibold ochre-text">${g.rem_h} sa</span></td>
        <td class="py-3 px-4 font-mono font-semibold">${g.score}</td>
        <td class="py-3 px-4 font-mono font-semibold moss-text">${g.hrv} ms</td>
        <td class="py-3 px-4 font-mono text-[var(--text-secondary)]">${g.rhr} bpm</td>
        <td class="py-3 px-4 font-mono font-medium">${g.bb_wake} / ${g.readiness}</td>
      `;
      gBody.appendChild(tr);
    });
  }

  const nBody = document.getElementById('sleepNightsBody');
  if (nBody) {
    nBody.innerHTML = '';
    (sData.top_nights || []).forEach(n => {
      const tr = document.createElement('tr');
      tr.className = "bg-[var(--moss-soft)] hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
        <td class="py-2.5 px-3 font-semibold moss-text">En İyi ${escapeHtml(n.rank)}</td>
        <td class="py-2.5 px-3 font-mono font-medium">${escapeHtml(n.date)}</td>
        <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)]">${escapeHtml(n.bed_time)}</td>
        <td class="py-2.5 px-3 font-mono font-semibold moss-text">${n.score}</td>
        <td class="py-2.5 px-3 font-mono">${n.sleep_h} sa</td>
        <td class="py-2.5 px-3 font-mono">${escapeHtml(n.deep_rem)}</td>
        <td class="py-2.5 px-3 font-mono font-semibold">${escapeHtml(n.hrv_rhr)}</td>
        <td class="py-2.5 px-3 font-mono">${escapeHtml(n.bb_readiness)}</td>
      `;
      nBody.appendChild(tr);
    });
    (sData.worst_nights || []).forEach(n => {
      const tr = document.createElement('tr');
      tr.className = "bg-[var(--crimson-soft)] hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
        <td class="py-2.5 px-3 font-semibold crimson-text">En Düşük ${escapeHtml(n.rank)}</td>
        <td class="py-2.5 px-3 font-mono font-medium">${escapeHtml(n.date)}</td>
        <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)]">${escapeHtml(n.bed_time)}</td>
        <td class="py-2.5 px-3 font-mono font-semibold crimson-text">${n.score}</td>
        <td class="py-2.5 px-3 font-mono">${n.sleep_h} sa</td>
        <td class="py-2.5 px-3 font-mono">${escapeHtml(n.deep_rem)}</td>
        <td class="py-2.5 px-3 font-mono font-semibold">${escapeHtml(n.hrv_rhr)}</td>
        <td class="py-2.5 px-3 font-mono">${escapeHtml(n.bb_readiness)}</td>
      `;
      nBody.appendChild(tr);
    });
  }
}

function render93dBiometrics(rows) {
  const tbody = document.getElementById('healthMetrics93dBody');
  if (!tbody || !Array.isArray(rows) || !rows.length) return;
  tbody.innerHTML = rows.map(r => `
    <tr class="hover:bg-[var(--bg-subtle)] transition">
      <td class="py-2.5 px-4 font-medium">${escapeHtml(r.metric)}</td>
      <td class="py-2.5 px-4 font-mono font-semibold accent-text">${escapeHtml(r.avg_median)}</td>
      <td class="py-2.5 px-4 font-mono">${escapeHtml(r.min_max)}</td>
      <td class="py-2.5 px-4 font-mono">${escapeHtml(r.ideal_ref)}</td>
      <td class="py-2.5 px-4 text-[var(--text-secondary)]">${escapeHtml(r.status)}</td>
    </tr>
  `).join('');
}

function renderCorrelations(corrs) {
  const cBody = document.getElementById('correlationsBody');
  if (!cBody || !Array.isArray(corrs)) return;
  cBody.innerHTML = '';
  corrs.forEach(c => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-[var(--bg-subtle)] transition";
    tr.innerHTML = `
      <td class="py-3 px-4 font-semibold">${escapeHtml(c.pair)}</td>
      <td class="py-3 px-4 font-mono font-semibold ${c.r < 0 ? 'crimson-text' : 'accent-text'}">${Number(c.r).toFixed(3)}</td>
      <td class="py-3 px-4 font-mono text-[var(--text-secondary)]">${Number(c.t).toFixed(2)}</td>
      <td class="py-3 px-4 font-mono font-medium text-[var(--text-secondary)]">${escapeHtml(c.p)}</td>
      <td class="py-3 px-4 text-[var(--text-secondary)]">${escapeHtml(c.insight)}</td>
    `;
    cBody.appendChild(tr);
  });
}

function renderPeriods(pData) {
  const container = document.getElementById('periodsContainer');
  if (!container || !pData || !Array.isArray(pData.periods)) return;
  const titleEl = document.getElementById('analyticsPeriodsTitle');
  if (titleEl && Array.isArray(pData.weeks)) {
    titleEl.textContent = `Makro Dönemler ve ${pData.weeks.length} Haftalık Seyir`;
  }
  container.innerHTML = '';
  pData.periods.forEach((p, idx) => {
    const div = document.createElement('div');
    div.className = `surface-card p-5 space-y-2.5 ${idx === pData.periods.length - 1 ? 'md:col-span-2 border-l-[3px] border-l-[var(--accent)]' : ''}`;
    div.innerHTML = `
      <div class="flex items-center justify-between gap-2">
        <h4 class="font-editorial text-base font-medium tracking-tight">${escapeHtml(p.period)}</h4>
        <span class="stamp-tag stamp-accent">${escapeHtml(p.dates)}</span>
      </div>
      <p class="text-xs text-[var(--text-secondary)] leading-relaxed editorial-prose">${escapeHtml(p.summary)}</p>
      <div class="flex flex-wrap items-center gap-4 font-mono text-[11px] text-[var(--text-secondary)] pt-2 border-t border-[var(--border-subtle)]">
        <span>Ort. Yük: <strong class="text-[var(--text-primary)]">${p.avg_load}</strong></span>
        <span>Gece HRV: <strong class="text-[var(--text-primary)]">${p.avg_hrv} ms</strong></span>
        <span>Uyku: <strong class="text-[var(--text-primary)]">${escapeHtml(p.avg_sleep)}</strong></span>
      </div>
    `;
    container.appendChild(div);
  });

  const wBody = document.getElementById('periodsWeeksTableBody');
  if (wBody && Array.isArray(pData.weeks)) {
    wBody.innerHTML = pData.weeks.map(w => `
      <tr class="hover:bg-[var(--bg-subtle)] transition">
        <td class="py-2.5 px-3 font-mono font-semibold accent-text">${escapeHtml(w.week)}</td>
        <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)]">${escapeHtml(w.start_date)}</td>
        <td class="py-2.5 px-3 font-mono">${w.act_count} (${w.act_dur_m} dk)</td>
        <td class="py-2.5 px-3 font-mono">${Number(w.steps || 0).toLocaleString('tr-TR')} <span class="text-[var(--text-muted)]">(${escapeHtml(w.goal_hit)})</span></td>
        <td class="py-2.5 px-3 font-mono">${w.rhr ?? '--'} / <span class="moss-text">${w.hrv ?? '--'} ms</span></td>
        <td class="py-2.5 px-3 font-mono">${w.sleep_h ?? '--'} sa (${w.sleep_score ?? '--'})</td>
        <td class="py-2.5 px-3 font-mono">${w.bb_wake ?? '--'} / ${w.bb_low ?? '--'}</td>
        <td class="py-2.5 px-3 font-mono font-semibold">${w.max_load ?? 0}</td>
      </tr>
    `).join('');
  }
}

function renderSettingsAndZones(setData) {
  if (!setData) return;
  const sGrid = document.getElementById('settingsGrid');
  if (sGrid && Array.isArray(setData.settings)) {
    sGrid.innerHTML = '';
    let savedSettings = {};
    try {
      savedSettings = JSON.parse(localStorage.getItem('garmin_fixed_settings') || '{}');
    } catch (e) {
      savedSettings = {};
    }

    setData.settings.forEach(s => {
      const isChecked = !!savedSettings[s.num];
      const div = document.createElement('div');
      div.id = `setting-card-${s.num}`;
      div.className = isChecked
        ? "p-4 tint-moss-panel flex items-start gap-3 transition"
        : "surface-card p-4 flex items-start gap-3 transition";

      div.innerHTML = `
        <input type="checkbox" id="setting-cb-${s.num}" ${isChecked ? 'checked' : ''} class="mt-0.5 w-4 h-4 cursor-pointer">
        <div class="text-xs flex-1 cursor-pointer" onclick="document.getElementById('setting-cb-${s.num}').click()">
          <div class="flex items-center justify-between gap-2">
            <p class="font-semibold ${isChecked ? 'line-through text-[var(--text-muted)]' : ''}" id="setting-title-${s.num}">${s.num}. ${escapeHtml(s.name)}: <span class="font-mono font-semibold ${isChecked ? 'text-[var(--text-muted)]' : 'accent-text'}">${escapeHtml(s.recommended)}</span></p>
            ${isChecked ? '<span class="stamp-tag stamp-moss">UYGULANDI</span>' : ''}
          </div>
          <p class="text-[11px] text-[var(--text-secondary)] mt-1">Mevcut: <code class="font-mono bg-[var(--bg-surface-elevated)] px-1.5 py-0.5 rounded-[2px] text-[10px]">${escapeHtml(s.current)}</code></p>
          <p class="text-[11px] text-[var(--text-secondary)] mt-1 leading-relaxed">${escapeHtml(s.reason)}</p>
        </div>
      `;

      const cb = div.querySelector(`#setting-cb-${s.num}`);
      cb.onchange = (e) => {
        savedSettings[s.num] = e.target.checked;
        localStorage.setItem('garmin_fixed_settings', JSON.stringify(savedSettings));
        renderSettingsAndZones(setData);
      };

      sGrid.appendChild(div);
    });
  }

  const zChart = document.getElementById('hrZonesVisualChart');
  if (zChart && Array.isArray(setData.zones) && setData.zones.length) {
    const totalRunMin = setData.zones.reduce((s, z) => s + (Number(z.run_minutes) || 0), 0);
    const totalAllMin = setData.zones.reduce((s, z) => s + (Number(z.all_minutes) || 0), 0);
    const maxRunPct = Math.max(10, ...setData.zones.map(z => Number(z.run_pct) || 0));

    const stackBarHtml = `
      <div class="space-y-1.5">
        <div class="flex items-center justify-between text-[11px] font-mono">
          <span class="text-[var(--text-secondary)] uppercase tracking-wider">Koşu Z1–Z5 Dağılımı</span>
          <span class="text-[var(--text-primary)] font-semibold">${Math.round(totalRunMin)} dk Koşu · ${Math.round(totalAllMin)} dk Toplam</span>
        </div>
        <div class="flex h-3 w-full overflow-hidden rounded-[2px] bg-[var(--bg-surface-elevated)] gap-px">
          ${setData.zones.map(z => {
            const pct = Number(z.run_pct) || 0;
            if (pct <= 0) return '';
            return `<div style="width: ${pct}%; background-color: ${escapeHtml(z.color || 'var(--accent)')};" title="${escapeHtml(z.zone_short || '')} ${escapeHtml(z.rec_lthr)}: %${pct} (${z.run_minutes} dk)"></div>`;
          }).join('')}
        </div>
      </div>
    `;

    const rowsHtml = setData.zones.map(z => {
      const rPct = Number(z.run_pct) || 0;
      const aPct = Number(z.all_pct) || 0;
      const wPct = Math.max(4, Math.min(100, Math.round((rPct / maxRunPct) * 100)));
      const barCol = escapeHtml(z.color || 'var(--accent)');
      const lthrBpm = String(z.rec_lthr || '').split('(')[0].trim();
      const pwrRng = String(z.rec_pwr || '').split('(')[0].trim();
      return `
        <div class="tint-panel p-3.5 space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div class="flex items-center gap-2 min-w-0">
              <span class="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-[2px] text-[var(--bg-surface)] shrink-0" style="background-color: ${barCol};">${escapeHtml(z.zone_short || '')}</span>
              <span class="font-semibold truncate">${escapeHtml(z.zone)}</span>
            </div>
            <div class="font-mono text-[11px] shrink-0">
              <span class="accent-text font-semibold">${escapeHtml(lthrBpm)}</span>
              <span class="text-[var(--text-muted)]"> · ${escapeHtml(pwrRng)}</span>
            </div>
          </div>
          <div class="w-full h-2.5 bg-[var(--bg-surface-elevated)] rounded-[2px] overflow-hidden">
            <div class="h-full transition-all duration-500 rounded-[2px]" style="width: ${wPct}%; background-color: ${barCol};"></div>
          </div>
          <div class="flex items-center justify-between font-mono text-[10.5px] text-[var(--text-secondary)]">
            <span>Koşu: <strong class="text-[var(--text-primary)]">%${rPct.toFixed(1)}</strong> (${z.run_minutes} dk)</span>
            <span>Tüm Branşlar: %${aPct.toFixed(1)} (${z.all_minutes} dk)</span>
          </div>
        </div>
      `;
    }).join('');

    zChart.innerHTML = `${stackBarHtml}<div class="space-y-2.5">${rowsHtml}</div>`;
  }

  const zBody = document.getElementById('zonesTableBody');
  if (zBody && Array.isArray(setData.zones)) {
    zBody.innerHTML = '';
    setData.zones.forEach(z => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
        <td class="py-3 px-3 font-semibold">${escapeHtml(z.zone)}</td>
        <td class="py-3 px-3 font-mono text-[var(--text-secondary)]">${escapeHtml(z.current_hr)}</td>
        <td class="py-3 px-3 font-mono font-semibold accent-text">${escapeHtml(z.rec_lthr)}</td>
        <td class="py-3 px-3 font-mono font-medium moss-text">${escapeHtml(z.rec_hrr)}</td>
        <td class="py-3 px-3 font-mono font-semibold">${escapeHtml(z.rec_pwr)}</td>
      `;
      zBody.appendChild(tr);
    });
  }
}

function renderZ2Tracker(data) {
  if (!data) return;
  const wkBadge = document.getElementById('z2PlanWeeksLabel');
  if (wkBadge) {
    wkBadge.textContent = `2 Koşu + 2 Gym · ${data.plan_weeks_label || 'Aktif'}`;
  }
  const svgGoal = document.getElementById('svgPaceGoalZ2');
  const svgTargetLbl = document.getElementById('svgPaceTargetLabel');
  if (svgGoal && data.target_pace) svgGoal.textContent = `${data.target_pace} Z2`;
  if (svgTargetLbl && data.target_pace) svgTargetLbl.textContent = `Hedef: ${data.target_pace} /km (EF ${data.target_efficiency_factor || '1.38'})`;

  const kpi = document.getElementById('z2KpiGrid');
  if (kpi) {
    kpi.innerHTML = `
      <div class="tint-panel p-3.5">
        <p class="font-mono text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Mevcut 145 bpm</p>
        <p class="font-mono text-xl font-bold mt-1">${escapeHtml(data.current_pace)}</p>
        <p class="font-mono text-[10px] text-[var(--text-secondary)] mt-1">EF: ${data.current_efficiency_factor} m/atım</p>
      </div>
      <div class="tint-accent-panel p-3.5">
        <p class="font-mono text-[10px] accent-text uppercase tracking-wider">Hedef 145 bpm</p>
        <p class="font-mono text-xl font-bold accent-text mt-1">${escapeHtml(data.target_pace)}</p>
        <p class="font-mono text-[10px] text-[var(--text-secondary)] mt-1">EF: ${data.target_efficiency_factor}${data.goal_auto_advanced ? ' (Yeni Faz)' : ' (+%33)'}</p>
      </div>
      <div class="tint-panel p-3.5">
        <p class="font-mono text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Kalan Hız Farkı</p>
        <p class="font-mono text-xl font-bold mt-1">-${data.pace_gap_sec_per_km} sn/km</p>
        <p class="font-mono text-[10px] text-[var(--text-secondary)] mt-1">${escapeHtml(data.target_date)}</p>
      </div>
      <div class="tint-panel p-3.5">
        <p class="font-mono text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Kalan Gün</p>
        <p class="font-mono text-xl font-bold mt-1">~${data.remaining_days} Gün</p>
        <p class="font-mono text-[10px] moss-text mt-1">${escapeHtml(data.plan_weeks_label || 'Esnek Plan')}</p>
      </div>
      <div class="tint-panel p-3.5 col-span-2 md:col-span-1">
        <p class="font-mono text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Kalan Antrenman</p>
        <p class="font-mono text-xs font-semibold mt-1"><span class="accent-text">${data.workout_counts.remaining_zone2_sessions}</span> Z2 · <span class="moss-text">${data.workout_counts.remaining_interval_sessions}</span> İnt</p>
        <p class="font-mono text-[10px] text-[var(--text-secondary)] mt-1">${data.workout_counts.remaining_strength_sessions} A/B 5x5 Gym</p>
      </div>
    `;
  }

  const gr = document.getElementById('z2GoldenRulesContainer');
  if (gr && Array.isArray(data.golden_rules)) {
    gr.innerHTML = data.golden_rules.map(r => `
      <div class="surface-card p-3">
        <p class="font-semibold">${escapeHtml(r.rule)}</p>
        <p class="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-relaxed">${escapeHtml(r.why)}</p>
      </div>
    `).join('');
  }

  const ms = document.getElementById('z2MilestonesContainer');
  if (ms && Array.isArray(data.timeline_milestones)) {
    ms.innerHTML = data.timeline_milestones.map(m => `
      <div class="surface-card p-3 flex items-center justify-between gap-2">
        <div>
          <p class="font-semibold">${escapeHtml(m.period)}</p>
          <p class="text-[11px] text-[var(--text-secondary)]">${escapeHtml(m.status)}</p>
        </div>
        <div class="text-right shrink-0">
          <span class="stamp-tag stamp-moss">${escapeHtml(m.pace)}</span>
          <p class="font-mono text-[10px] text-[var(--text-secondary)] mt-1">${escapeHtml(m.weight)}</p>
        </div>
      </div>
    `).join('');
  }
}

function renderPhysiqueTracker(data) {
  if (!data || !Array.isArray(data.stages)) return;
  const c = document.getElementById('morphologyCardsContainer');
  if (!c) return;
  c.innerHTML = data.stages.map((s, idx) => `
    <div class="surface-card p-5 space-y-3 ${idx === 2 ? 'border-l-[3px] border-l-[var(--accent)]' : ''}">
      <div class="flex items-center justify-between gap-2">
        <span class="stamp-tag stamp-accent">Aşama ${s.stage_num}</span>
        <span class="stamp-tag stamp-moss">${s.days_remaining} Gün Kaldı</span>
      </div>
      <div>
        <h4 class="font-mono text-lg font-bold tracking-tight">${s.target_kg} kg <span class="text-xs text-[var(--text-secondary)] font-medium">(Yağ: ${escapeHtml(s.estimated_fat_pct)})</span></h4>
        <p class="font-mono text-[11px] accent-text font-medium mt-0.5">Hedef: ${escapeHtml(s.target_date)}</p>
      </div>
      <p class="text-xs text-[var(--text-secondary)] leading-relaxed"><strong class="text-[var(--text-primary)] font-semibold">Görsel Değişim:</strong> ${escapeHtml(s.visual_changes)}</p>
      <p class="text-xs moss-text tint-moss-panel p-2.5"><strong class="font-semibold">Performans Etkisi:</strong> ${escapeHtml(s.performance_impact)}</p>
    </div>
  `).join('');
}

function renderHealthScreening(data) {
  if (!data) return;
  const dv = document.getElementById('doctorVerdictTitle');
  const ds = document.getElementById('doctorSummaryText');
  if (dv) dv.textContent = data.doctor_verdict;
  if (ds) ds.textContent = data.summary;

  const pGrid = document.getElementById('healthPillarsGrid');
  if (pGrid && Array.isArray(data.pillars)) {
    pGrid.innerHTML = data.pillars.map((p, idx) => `
      <div class="tint-panel p-4 space-y-2 ${idx === 0 ? 'lg:col-span-2 border-l-[3px] border-l-[var(--accent)]' : ''}">
        <div class="flex items-center justify-between gap-2">
          <h5 class="text-xs font-semibold">${escapeHtml(p.name)}</h5>
          <span class="stamp-tag stamp-moss shrink-0">${escapeHtml(p.badge)}</span>
        </div>
        <p class="font-mono text-xs font-semibold accent-text">${escapeHtml(p.value)}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(p.clinical_notes)}</p>
      </div>
    `).join('');
  }
}

function renderFitnessAge(data) {
  if (!data) return;
  const valEl = document.getElementById('fitnessAgeValue');
  if (valEl) valEl.textContent = `${data.fitness_age} Yaş`;
  const advBadge = document.getElementById('fitnessAgeAdvantageBadge');
  if (advBadge && data.age_advantage_years !== undefined) {
    advBadge.textContent = `${data.age_advantage_years} Yaş Avantaj`;
  }
  const chronoEl = document.getElementById('fitnessAgeChronoText');
  if (chronoEl && data.chronological_age !== undefined) {
    chronoEl.textContent = `(Kronolojik: ${data.chronological_age})`;
  }
  const minEl = document.getElementById('fitnessAgeMinVal');
  if (minEl && data.achievable_minimum_age !== undefined) {
    minEl.textContent = `${Number(data.achievable_minimum_age).toFixed(1).replace('.', ',')} Yaş`;
  }
  const roadEl = document.getElementById('fitnessAgeRoadmapText');
  if (roadEl && data.roadmap_to_minimum && Array.isArray(data.roadmap_to_minimum.needed_actions)) {
    roadEl.textContent = data.roadmap_to_minimum.needed_actions[0] || '';
  }
}

function renderGarminExpansion(data) {
  if (!data || !Array.isArray(data.new_high_resolution_channels)) return;
  const c = document.getElementById('garminExpansionCardsContainer');
  if (c) {
    c.innerHTML = data.new_high_resolution_channels.map(ch => {
      const pills = Array.isArray(ch.live_metrics) ? ch.live_metrics : [];
      const pillsHtml = pills.length
        ? `<div class="flex flex-wrap gap-1.5 pt-1">
            ${pills.map(m => `<span class="font-mono text-[10px] px-2 py-0.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[2px] text-[var(--text-primary)]">${escapeHtml(m)}</span>`).join('')}
          </div>`
        : '';
      const statusBadge = ch.status
        ? `<span class="stamp-tag ${ch.status === 'AKTİF' || ch.status.includes('AKTİF') ? 'stamp-moss' : 'stamp-accent'} shrink-0">${escapeHtml(ch.status)}</span>`
        : '';
      return `
        <div class="tint-panel p-4 space-y-2.5 flex flex-col justify-between min-w-0">
          <div class="space-y-2">
            <div class="flex items-start justify-between gap-2">
              <h4 class="text-xs font-semibold flex items-center gap-2 leading-snug">
                ${lucideSvg('cpu', 'w-3.5 h-3.5 accent-text shrink-0')}
                <span>${escapeHtml(ch.channel)}</span>
              </h4>
              ${statusBadge}
            </div>
            <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(ch.detail)}</p>
            ${pillsHtml}
          </div>
          <p class="text-[11px] accent-text surface-card p-2.5 flex items-start gap-2">
            ${lucideSvg('sparkles', 'w-3.5 h-3.5 shrink-0 mt-0.5')}
            <span><strong class="font-semibold">Canlı Çıktı:</strong> ${escapeHtml(ch.benefit)}</span>
          </p>
        </div>
      `;
    }).join('');
  }

  const stepsList = document.getElementById('garminExpansionStepsList');
  const pipeBadge = document.getElementById('expansionPipelineBadge');
  const stepsDetail = Array.isArray(data.implementation_steps_detail) ? data.implementation_steps_detail : [];
  if (pipeBadge) {
    const activeCnt = stepsDetail.filter(s => s.status && (s.status.includes('AKTİF') || s.status.includes('DOĞRULANDI') || s.status.includes('HAZIR'))).length;
    pipeBadge.textContent = stepsDetail.length ? `${activeCnt}/${stepsDetail.length} Adım Hazır` : 'Aktif';
  }
  if (stepsList && stepsDetail.length) {
    stepsList.innerHTML = stepsDetail.map((st, idx) => `
      <div class="tint-panel p-3.5 space-y-1.5">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <span class="font-semibold text-[var(--text-primary)]">${idx + 1}. ${escapeHtml(st.step)}</span>
          <span class="stamp-tag ${st.status && (st.status.includes('AKTİF') || st.status.includes('DOĞRULANDI')) ? 'stamp-moss' : 'stamp-accent'}">${escapeHtml(st.status || 'Hazır')}</span>
        </div>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(st.detail || '')}</p>
      </div>
    `).join('');
  }

  const panel = document.getElementById('highResTelemetryPanel');
  if (panel) {
    const fit = data.fit_stream_summary || {};
    const hrv = data.hrv_5min_summary || {};
    const rd = data.running_dynamics_summary || {};
    const resp = data.respiration_thermal_summary || {};
    const firstFit = (Array.isArray(fit.parsed_files) && fit.parsed_files.length) ? fit.parsed_files[0] : null;
    const splits = fit.latest_run_splits || {};
    const rdLatest = rd.latest_run || {};
    const readings = Array.isArray(hrv.readings) ? hrv.readings : [];

    const maxHrvVal = readings.reduce((mx, r) => Math.max(mx, Number(r.value_ms) || 0), 1);
    const minHrvVal = readings.reduce((mn, r) => Math.min(mn, Number(r.value_ms) || 999), 999);
    const hrvBarsHtml = readings.length
      ? `<div class="flex items-end gap-1 h-16 pt-2">
          ${readings.map(r => {
            const val = Number(r.value_ms) || 0;
            const hPct = Math.max(18, Math.min(100, Math.round((val / maxHrvVal) * 100)));
            const isPeak = val >= maxHrvVal - 0.5;
            const cls = isPeak ? 'bg-[var(--moss)]' : 'bg-[var(--accent)] opacity-80';
            return `<div class="flex-1 ${cls} rounded-t-[1px] transition-all" style="height: ${hPct}%;" title="${escapeHtml(r.label)}: ${val} ms"></div>`;
          }).join('')}
        </div>
        <div class="flex justify-between font-mono text-[10px] text-[var(--text-muted)] pt-1">
          <span>${escapeHtml(readings[0].label)} (${readings[0].value_ms} ms)</span>
          <span>Min ${minHrvVal} / Peak ${hrv.peak_window ? `${hrv.peak_window.label}: ${hrv.peak_window.value_ms} ms` : `${maxHrvVal} ms`}</span>
          <span>${escapeHtml(readings[readings.length - 1].label)} (${readings[readings.length - 1].value_ms} ms)</span>
        </div>`
      : `<p class="text-[11px] text-[var(--text-secondary)]">HRV verisi bekleniyor.</p>`;

    const timeline = (firstFit && Array.isArray(firstFit.sampled_timeline)) ? firstFit.sampled_timeline : [];
    const maxSampleHr = timeline.reduce((mx, p) => Math.max(mx, Number(p.hr) || 0), 1);
    const fitSparkHtml = timeline.length
      ? `<div class="flex items-end gap-0.5 h-12 pt-1">
          ${timeline.map(p => {
            const hr = Number(p.hr) || 0;
            const hPct = Math.max(20, Math.min(100, Math.round((hr / maxSampleHr) * 100)));
            return `<div class="flex-1 bg-[var(--accent)] opacity-75 rounded-t-[1px]" style="height: ${hPct}%;" title="${p.t_min} dk · ${hr} bpm"></div>`;
          }).join('')}
        </div>
        <div class="flex justify-between font-mono text-[10px] text-[var(--text-muted)] pt-1">
          <span>0 dk (${timeline[0].hr} bpm)</span>
          <span>1. Yarı: ${firstFit.first_half_avg_hr ?? '--'} → 2. Yarı: ${firstFit.second_half_avg_hr ?? '--'} bpm</span>
          <span>${firstFit.duration_min ?? '--'} dk (${firstFit.max_hr ?? '--'} max)</span>
        </div>`
      : '';

    panel.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
        <div>
          <h4 class="font-editorial text-base font-medium tracking-tight">Canlı Yüksek Çözünürlük Telemetrisi (FIT + HRV + Running Dynamics)</h4>
          <p class="text-[11px] text-[var(--text-secondary)] mt-0.5">${escapeHtml(fit.note || '')}</p>
        </div>
        <div class="flex flex-wrap gap-1.5">
          <span class="stamp-tag stamp-moss">${escapeHtml(fit.status_badge || 'FIT AKTİF')}</span>
          <span class="stamp-tag stamp-accent">${escapeHtml(hrv.status_badge || 'HRV HAZIR')}</span>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="tint-panel p-4 space-y-2.5">
          <div class="flex items-center justify-between gap-2">
            <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">FIT İkili Akış Örneği</span>
            <span class="font-mono text-[10px] accent-text font-semibold">${escapeHtml(firstFit ? firstFit.file_name : 'download-fit')}</span>
          </div>
          <p class="text-xs font-medium">${escapeHtml(firstFit ? `${firstFit.activity_name} (${firstFit.date})` : 'Seans FIT Akışı')}</p>
          <p class="font-mono text-[11px] text-[var(--text-secondary)]">
            ${firstFit ? `${firstFit.sample_count} nokta · Ort HR ${firstFit.avg_hr} bpm · Drift ${firstFit.cardiac_drift_bpm >= 0 ? '+' : ''}${firstFit.cardiac_drift_bpm} bpm` : 'FIT dosyası bekleniyor'}
          </p>
          ${fitSparkHtml}
          ${splits.activity_name ? `<p class="font-mono text-[10px] text-[var(--text-secondary)] pt-1 border-t border-[var(--border-subtle)]">Son Koşu Splitleri (${escapeHtml(splits.date)}): En Hızlı 1K ${escapeHtml(splits.fastest_1k_pace)} · 5K Tempo ${escapeHtml(splits.fastest_5k_pace)}</p>` : ''}
        </div>

        <div class="tint-panel p-4 space-y-2.5">
          <div class="flex items-center justify-between gap-2">
            <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">${hrv.mode === '5min_rmssd' ? '5 Dakikalık Gece HRV (RMSSD)' : 'Son 14 Gece HRV Serisi (5dk Servis Hazır)'}</span>
            <span class="font-mono text-[10px] moss-text font-semibold">${hrv.overnight_avg_ms ?? '--'} ms (7G: ${hrv.baseline_7d_ms ?? '--'})</span>
          </div>
          ${hrvBarsHtml}
          <p class="text-[10.5px] text-[var(--text-secondary)] leading-relaxed pt-1 border-t border-[var(--border-subtle)]">${escapeHtml(hrv.note || '')}</p>
        </div>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div class="tint-panel p-3">
          <span class="font-mono text-[10px] text-[var(--text-muted)] block uppercase">Yerle Temas (GCT)</span>
          <strong class="font-mono text-sm font-bold accent-text">${rdLatest.gct_ms ?? '--'} ms</strong>
          <span class="font-mono text-[10px] text-[var(--text-secondary)] block">93G Ort: ${rd.avg_93d?.gct_ms ?? '--'} ms</span>
        </div>
        <div class="tint-panel p-3">
          <span class="font-mono text-[10px] text-[var(--text-muted)] block uppercase">Dikey Salınım / Oran</span>
          <strong class="font-mono text-sm font-bold">${rdLatest.vertical_oscillation_cm ?? '--'} cm</strong>
          <span class="font-mono text-[10px] text-[var(--text-secondary)] block">Oran: %${rdLatest.vertical_ratio_pct ?? '--'}</span>
        </div>
        <div class="tint-panel p-3">
          <span class="font-mono text-[10px] text-[var(--text-muted)] block uppercase">Solunum &amp; Cilt Isısı</span>
          <strong class="font-mono text-sm font-bold moss-text">${resp.sleep_respiration_latest ?? '--'} br/dk</strong>
          <span class="font-mono text-[10px] text-[var(--text-secondary)] block">Cilt: ${resp.skin_temp_c_latest ?? '--'} °C · SpO2 %${resp.spo2_daily_avg ?? resp.spo2_sleep_latest ?? '--'}</span>
        </div>
        <div class="tint-panel p-3">
          <span class="font-mono text-[10px] text-[var(--text-muted)] block uppercase">Koşu Gücü (NP / Maks)</span>
          <strong class="font-mono text-sm font-bold">${rdLatest.norm_power_w ?? '--'} W</strong>
          <span class="font-mono text-[10px] text-[var(--text-secondary)] block">Maks: ${rdLatest.max_power_w ?? '--'} W · Adım ${rdLatest.stride_length_cm ?? '--'} cm</span>
        </div>
      </div>
    `;
  }

  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderProgressionAssessment(data) {
  if (!data) return;
  const vp = data.volume_progression || {};
  const st = data.style_transition || {};
  const rp = data.running_progression || {};
  const fd = data.fatigue_and_deload || {};

  const tierBadge = document.getElementById('progressionTierBadge');
  if (tierBadge && data.current_tier_label) {
    tierBadge.textContent = data.current_tier_label;
  }

  const grid = document.getElementById('progressionCardsGrid');
  if (grid) {
    grid.innerHTML = `
      <div class="tint-panel p-4 space-y-2.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">1. Haftalık Gün Sayısı</span>
          <span class="stamp-tag ${vp.can_increase_days ? 'stamp-moss' : 'stamp-ochre'}">${escapeHtml(vp.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${escapeHtml(vp.current_days)} <span class="text-[var(--text-muted)]">→</span> <span class="${vp.can_increase_days ? 'moss-text' : 'ochre-text'}">${escapeHtml(vp.next_level_days)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(vp.advice || '')}</p>
      </div>

      <div class="tint-panel p-4 space-y-2.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">2. Kuvvet: Mevcut Ağırlıklar ve Hedef</span>
          <span class="stamp-tag stamp-accent">${escapeHtml(st.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">Mevcut: <span class="moss-text">${escapeHtml(st.current_style)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(st.advice || '')}</p>
      </div>

      <div class="tint-panel p-4 space-y-2.5 border-l-[3px] border-l-[var(--accent)]">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">3. Koşu: Mevcut Durum ve Hedef</span>
          <span class="stamp-tag stamp-moss">${escapeHtml(rp.verdict || '80/20 KOŞU PLANI')}</span>
        </div>
        <p class="font-mono text-[11px] font-semibold accent-text">${escapeHtml(rp.current_metrics || '')}</p>
        <p class="text-xs text-[var(--text-primary)] font-medium">${escapeHtml(rp.current_model || '')}</p>
        <p class="font-mono text-[10.5px] text-[var(--text-secondary)]">${escapeHtml(rp.load_balance || '')}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(rp.advice || st.running_style_advice || '')}</p>
        <p class="text-[10.5px] moss-text tint-moss-panel p-2"><strong class="font-semibold">Sıradaki Koşu Hedefleri:</strong> ${escapeHtml(rp.next_milestone || '')}</p>
      </div>

      <div class="tint-panel p-4 space-y-2.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">4. Yorgunluk ve Dinlenme</span>
          <span class="stamp-tag ${fd.needs_deload ? 'stamp-ochre' : 'stamp-moss'}">${escapeHtml(fd.status || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${fd.needs_deload ? 'Hacmi %40 Düşür' : 'Normal Yükte Devam'}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(fd.note || '')}</p>
        <p class="text-[10px] ochre-text tint-ochre-panel p-2"><strong class="font-semibold">Not:</strong> Yorgunluk yüksekse veya uyku düşükse antrenmanı hafif yürüyüşe çevirin.</p>
      </div>
    `;
  }

  const tiersGrid = document.getElementById('athleteTiersGrid');
  if (tiersGrid && data.athlete_levels) {
    const tiers = Object.values(data.athlete_levels);
    tiersGrid.innerHTML = tiers.map(t => `
      <div class="surface-card p-3.5 space-y-2">
        <p class="font-semibold accent-text text-xs">${escapeHtml(t.level_tr.split('(')[0])}</p>
        <p class="font-mono text-[10px] text-[var(--text-secondary)] font-medium">${escapeHtml(t.recommended_split)}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug"><strong class="text-[var(--text-primary)]">Koşu:</strong> ${escapeHtml(t.running_approach)}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug"><strong class="text-[var(--text-primary)]">Kuvvet:</strong> ${escapeHtml(t.strength_approach)}</p>
        <p class="text-[10px] moss-text tint-moss-panel p-2 mt-1"><strong class="font-semibold">Geçiş Eşiği:</strong> ${escapeHtml(t.progression_gate)}</p>
      </div>
    `).join('');
  }
}
