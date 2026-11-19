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
      <td class="py-1.5 px-3 font-medium">${escapeHtml(r.metric)}</td>
      <td class="py-1.5 px-3 font-mono font-semibold accent-text">${escapeHtml(r.avg_median)}</td>
      <td class="py-1.5 px-3 font-mono">${escapeHtml(r.min_max)}</td>
      <td class="py-1.5 px-3 font-mono">${escapeHtml(r.ideal_ref)}</td>
      <td class="py-1.5 px-3 text-[var(--text-secondary)]">${escapeHtml(r.status)}</td>
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
      <td class="py-1.5 px-3 font-semibold">${escapeHtml(c.pair)}</td>
      <td class="py-1.5 px-3 font-mono font-semibold ${c.r < 0 ? 'crimson-text' : 'accent-text'}">${Number(c.r).toFixed(3)}</td>
      <td class="py-1.5 px-3 font-mono text-[var(--text-secondary)]">${Number(c.t).toFixed(2)}</td>
      <td class="py-1.5 px-3 font-mono font-medium text-[var(--text-secondary)]">${escapeHtml(c.p)}</td>
      <td class="py-1.5 px-3 text-[var(--text-secondary)]">${escapeHtml(c.insight)}</td>
    `;
    cBody.appendChild(tr);
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
        <div class="tint-panel p-2.5 space-y-1">
          <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div class="flex items-center gap-2 min-w-0">
              <span class="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-[2px] text-[var(--bg-surface)] shrink-0" style="background-color: ${barCol};">${escapeHtml(z.zone_short || '')}</span>
              <span class="font-semibold truncate">${escapeHtml(z.zone)}</span>
            </div>
            <div class="font-mono text-[10.5px] shrink-0">
              <span class="accent-text font-semibold">${escapeHtml(lthrBpm)}</span>
              <span class="text-[var(--text-muted)]"> · ${escapeHtml(pwrRng)}</span>
            </div>
          </div>
          <div class="w-full h-2 bg-[var(--bg-surface-elevated)] rounded-[2px] overflow-hidden">
            <div class="h-full transition-all duration-500 rounded-[2px]" style="width: ${wPct}%; background-color: ${barCol};"></div>
          </div>
          <div class="flex items-center justify-between font-mono text-[10px] text-[var(--text-secondary)]">
            <span>Koşu: <strong class="text-[var(--text-primary)]">%${rPct.toFixed(1)}</strong> (${z.run_minutes} dk)</span>
            <span>Tüm Branşlar: %${aPct.toFixed(1)} (${z.all_minutes} dk)</span>
          </div>
        </div>
      `;
    }).join('');

    zChart.innerHTML = `${stackBarHtml}<div class="space-y-1.5">${rowsHtml}</div>`;
  }

  const zBody = document.getElementById('zonesTableBody');
  if (zBody && Array.isArray(setData.zones)) {
    zBody.innerHTML = '';
    setData.zones.forEach(z => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
        <td class="py-1.5 px-2 text-[10.5px] font-semibold leading-tight">${escapeHtml(String(z.zone || '').replace('Zone ', 'Z'))}</td>
        <td class="py-1.5 px-2 text-[10.5px] font-mono text-[var(--text-secondary)] leading-tight">${escapeHtml(z.current_hr)}</td>
        <td class="py-1.5 px-2 text-[10.5px] font-mono font-semibold accent-text leading-tight">${escapeHtml(z.rec_lthr)}</td>
        <td class="py-1.5 px-2 text-[10.5px] font-mono font-medium moss-text leading-tight">${escapeHtml(z.rec_hrr)}</td>
        <td class="py-1.5 px-2 text-[10.5px] font-mono font-semibold leading-tight">${escapeHtml(z.rec_pwr)}</td>
      `;
      zBody.appendChild(tr);
    });
  }
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
      <div class="tint-panel p-3 space-y-1.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">1. Haftalık Gün Sayısı</span>
          <span class="stamp-tag ${vp.can_increase_days ? 'stamp-moss' : 'stamp-ochre'}">${escapeHtml(vp.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${escapeHtml(vp.current_days)} <span class="text-[var(--text-muted)]">→</span> <span class="${vp.can_increase_days ? 'moss-text' : 'ochre-text'}">${escapeHtml(vp.next_level_days)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(vp.advice || '')}</p>
      </div>

      <div class="tint-panel p-3 space-y-1.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">2. Kuvvet: Mevcut Ağırlıklar ve Hedef</span>
          <span class="stamp-tag stamp-accent">${escapeHtml(st.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">Mevcut: <span class="moss-text">${escapeHtml(st.current_style)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(st.advice || '')}</p>
      </div>

      <div class="tint-panel p-3 space-y-1.5 border-l-[3px] border-l-[var(--accent)]">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">3. Koşu: Mevcut Durum ve Hedef</span>
          <span class="stamp-tag stamp-moss">${escapeHtml(rp.verdict || '80/20 KOŞU PLANI')}</span>
        </div>
        <p class="font-mono text-[11px] font-semibold accent-text">${escapeHtml(rp.current_metrics || '')}</p>
        <p class="text-xs text-[var(--text-primary)] font-medium leading-snug">${escapeHtml(rp.current_model || '')}</p>
        <p class="font-mono text-[10.5px] text-[var(--text-secondary)]">${escapeHtml(rp.load_balance || '')}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(rp.advice || st.running_style_advice || '')}</p>
        <p class="text-[10.5px] moss-text tint-moss-panel p-1.5 leading-snug"><strong class="font-semibold">Sıradaki Koşu Hedefleri:</strong> ${escapeHtml(rp.next_milestone || '')}</p>
      </div>

      <div class="tint-panel p-3 space-y-1.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">4. Yorgunluk ve Dinlenme</span>
          <span class="stamp-tag ${fd.needs_deload ? 'stamp-ochre' : 'stamp-moss'}">${escapeHtml(fd.status || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${fd.needs_deload ? 'Hacmi %40 Düşür' : 'Normal Yükte Devam'}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(fd.note || '')}</p>
        <p class="text-[10px] ochre-text tint-ochre-panel p-1.5 leading-snug"><strong class="font-semibold">Not:</strong> Yorgunluk yüksekse veya uyku düşükse antrenmanı hafif yürüyüşe çevirin.</p>
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
