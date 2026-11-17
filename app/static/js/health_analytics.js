/* Garmin Athlete IQ — Health, Sleep Architecture, 93d Biometrics, Morphology, Settings & Progression */

function renderSleepAnalysis(sData) {
  if (!sData) return;
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

  const zBody = document.getElementById('zonesTableBody');
  if (zBody && Array.isArray(setData.zones)) {
    zBody.innerHTML = '';
    setData.zones.forEach(z => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
        <td class="py-3 px-4 font-semibold">${escapeHtml(z.zone)}</td>
        <td class="py-3 px-4 font-mono text-[var(--text-secondary)]">${escapeHtml(z.current_hr)}</td>
        <td class="py-3 px-4 font-mono font-semibold accent-text">${escapeHtml(z.rec_lthr)}</td>
        <td class="py-3 px-4 font-mono font-medium moss-text">${escapeHtml(z.rec_hrr)}</td>
        <td class="py-3 px-4 font-mono font-semibold">${escapeHtml(z.rec_pwr)}</td>
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
  if (!c) return;
  c.innerHTML = data.new_high_resolution_channels.map((ch, idx) => `
    <div class="tint-panel p-4 space-y-2.5 ${idx === 0 ? 'md:col-span-2' : ''}">
      <h4 class="text-xs font-semibold flex items-center gap-2">
        ${lucideSvg('cpu', 'w-3.5 h-3.5 accent-text')}
        <span>${escapeHtml(ch.channel)}</span>
      </h4>
      <p class="text-xs text-[var(--text-secondary)] leading-relaxed">${escapeHtml(ch.detail)}</p>
      <p class="text-[11px] accent-text surface-card p-2.5 flex items-start gap-2">
        ${lucideSvg('sparkles', 'w-3.5 h-3.5 shrink-0 mt-0.5')}
        <span><strong class="font-semibold">Faydası:</strong> ${escapeHtml(ch.benefit)}</span>
      </p>
    </div>
  `).join('');
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderProgressionAssessment(data) {
  if (!data) return;
  const vp = data.volume_progression || {};
  const st = data.style_transition || {};
  const fd = data.fatigue_and_deload || {};

  const grid = document.getElementById('progressionCardsGrid');
  if (grid) {
    grid.innerHTML = `
      <div class="tint-panel p-4 space-y-2.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Hacim &amp; Gün Artırma</span>
          <span class="stamp-tag ${vp.can_increase_days ? 'stamp-moss' : 'stamp-accent'}">${escapeHtml(vp.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${escapeHtml(vp.current_days)} → <span class="accent-text">${escapeHtml(vp.next_level_days)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(vp.advice || '')}</p>
      </div>

      <div class="tint-panel p-4 space-y-2.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Stil &amp; Rutin Değişimi</span>
          <span class="stamp-tag stamp-accent">${escapeHtml(st.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">Mevcut: <span class="moss-text">${escapeHtml(st.current_style)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(st.advice || '')}</p>
        <p class="text-[10px] text-[var(--text-secondary)] surface-card p-2">${escapeHtml(st.running_style_advice || '')}</p>
      </div>

      <div class="tint-panel p-4 space-y-2.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Deload &amp; Esneklik</span>
          <span class="stamp-tag ${fd.needs_deload ? 'stamp-ochre' : 'stamp-moss'}">${escapeHtml(fd.status || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${fd.needs_deload ? 'Hacmi %40 Düşür' : 'Tam Güç &amp; Kondisyon Aktif'}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(fd.note || '')}</p>
        <p class="text-[10px] ochre-text tint-ochre-panel p-2"><strong class="font-semibold">Dogmatik Olmama Kuralı:</strong> Yorgunluk/düşük HRV durumunda seans yürüyüş veya esnemeye çevrilir.</p>
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
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug"><strong class="text-[var(--text-primary)]">Koşu:</strong> ${escapeHtml(t.running_approach.split('.')[0])}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug"><strong class="text-[var(--text-primary)]">Kuvvet:</strong> ${escapeHtml(t.strength_approach.split('.')[0])}</p>
        <p class="text-[10px] moss-text tint-moss-panel p-2 mt-1"><strong class="font-semibold">Geçiş Eşiği:</strong> ${escapeHtml(t.progression_gate)}</p>
      </div>
    `).join('');
  }
}
