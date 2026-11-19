/* Garmin Athlete IQ — Health, Sleep Architecture, 93d Biometrics, Morphology, Settings & Progression */

function _build93dRowGauge(r) {
  const avg = Number(r.avg_val);
  const lo = Number(r.min_val);
  const hi = Number(r.max_val);
  const idLo = Number(r.ideal_low);
  const idHi = Number(r.ideal_high);
  if ([avg, lo, hi, idLo, idHi].some(Number.isNaN) || hi <= lo) {
    return `<span class="font-mono sky-text">${escapeHtml(r.avg_median)}</span>`;
  }
  const scaleLo = Math.min(lo, idLo);
  const scaleHi = Math.max(hi, idHi);
  const segs = r.polarity === 'lower_better'
    ? [{ cls: 'seg-blue', flex: 1 }, { cls: 'seg-green', flex: 1.4 }, { cls: 'seg-amber', flex: 1.1 }]
    : (r.polarity === 'range'
      ? [{ cls: 'seg-amber', flex: 1 }, { cls: 'seg-green', flex: 1.4 }, { cls: 'seg-amber', flex: 1 }]
      : [{ cls: 'seg-amber', flex: 1.1 }, { cls: 'seg-green', flex: 1.4 }, { cls: 'seg-blue', flex: 1 }]);
  const breaks = [scaleLo, idLo, idHi, scaleHi];
  const activeIdx = avg < idLo ? 0 : (avg <= idHi ? 1 : 2);
  const rawPct = typeof _piecewiseGaugePct === 'function'
    ? _piecewiseGaugePct(avg, breaks, segs)
    : ((avg - scaleLo) / Math.max(0.01, scaleHi - scaleLo)) * 100;
  const clamped = Math.max(4, Math.min(96, rawPct));
  const minMaxParts = String(r.min_max || '').split('–').map(s => s.trim());
  const minLbl = minMaxParts[0] || String(r.min_val);
  const maxLbl = minMaxParts[1] || String(r.max_val);
  const avgTxt = String(r.avg_median || '');
  const avgMatch = avgTxt.match(/^([^\(]+)\(([^\)]+)\)(.*)$/);
  const avgDisplay = avgMatch
    ? `Ort: ${avgMatch[1].trim()}${avgMatch[3] || ''}`
    : `Ort: ${avgTxt}`;

  return `
    <div class="space-y-0.5 w-full">
      <div class="flex items-baseline justify-between gap-2 font-mono text-[10px]">
        <span class="font-semibold sky-text">${escapeHtml(avgDisplay)}</span>
        <span class="violet-text shrink-0">İdeal: ${escapeHtml(r.ideal_ref)}</span>
      </div>
      <div class="garmin-gauge">
        <div class="garmin-gauge-track">
          ${segs.map((s, idx) => `<div class="garmin-seg ${s.cls} ${idx === activeIdx ? 'active' : ''}" style="flex:${s.flex}"></div>`).join('')}
          <span class="garmin-gauge-pin" style="left:${clamped.toFixed(1)}%" title="${escapeHtml(avgDisplay)}"></span>
        </div>
        <div class="garmin-gauge-scale">
          <span>Min: ${escapeHtml(minLbl)}</span>
          <span>Maks: ${escapeHtml(maxLbl)}</span>
        </div>
      </div>
    </div>
  `;
}

function render93dBiometrics(rows) {
  const tbody = document.getElementById('healthMetrics93dBody');
  if (!tbody || !Array.isArray(rows) || !rows.length) return;
  tbody.innerHTML = rows.map(r => `
      <tr class="hover:bg-[var(--bg-subtle)] transition">
        <td class="py-1 px-2 font-medium whitespace-nowrap w-px pr-3">${escapeHtml(r.metric)}</td>
        <td class="py-1 px-2 w-full">${_build93dRowGauge(r)}</td>
      </tr>
    `).join('');
}

function renderCorrelations(corrs) {
  const cBody = document.getElementById('correlationsBody');
  if (!cBody || !Array.isArray(corrs)) return;
  cBody.innerHTML = '';
  if (!corrs.length) {
    cBody.innerHTML = '<tr><td colspan="2" class="py-3 px-3 text-[var(--text-secondary)]">Korelasyon için yeterli günlük veri yok (en az 6 gün gerekir).</td></tr>';
    return;
  }
  corrs.forEach(c => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-[var(--bg-subtle)] transition";
    const pairCls = c.significant ? (Number(c.r) < 0 ? 'ochre-text' : 'sky-text') : 'text-[var(--text-muted)]';
    tr.innerHTML = `
      <td class="py-1 px-2 font-semibold ${pairCls}">${escapeHtml(c.pair)}</td>
      <td class="py-1 px-2 text-[var(--text-secondary)]">${escapeHtml(c.insight)}</td>
    `;
    cBody.appendChild(tr);
  });
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
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">1. Haftalık Gün Sayısı</span>
          <span class="stamp-tag ${vp.can_increase_days ? 'stamp-moss' : 'stamp-ochre'}">${escapeHtml(vp.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${escapeHtml(vp.current_days)} <span class="text-[var(--text-muted)]">→</span> <span class="${vp.can_increase_days ? 'moss-text' : 'ochre-text'}">${escapeHtml(vp.next_level_days)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(vp.advice || '')}</p>
      </div>

      <div class="tint-panel p-3 space-y-1.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">2. Kuvvet: Mevcut Ağırlıklar ve Hedef</span>
          <span class="stamp-tag stamp-accent">${escapeHtml(st.verdict || '--')}</span>
        </div>
        <p class="text-xs font-semibold">Mevcut: <span class="moss-text">${escapeHtml(st.current_style)}</span></p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(st.advice || '')}</p>
      </div>

      <div class="tint-panel p-3 space-y-1.5 border-l-[3px] border-l-[var(--accent)]">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">3. Koşu: Mevcut Durum ve Hedef</span>
          <span class="stamp-tag stamp-moss">${escapeHtml(rp.verdict || '80/20 KOŞU PLANI')}</span>
        </div>
        <p class="font-mono text-[11px] font-semibold accent-text">${escapeHtml(rp.current_metrics || '')}</p>
        <p class="text-xs text-[var(--text-primary)] font-medium leading-snug">${escapeHtml(rp.current_model || '')}</p>
        <p class="font-mono text-[12px] text-[var(--text-secondary)]">${escapeHtml(rp.load_balance || '')}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(rp.advice || st.running_style_advice || '')}</p>
        <p class="text-[12px] moss-text tint-moss-panel p-1.5 leading-snug"><strong class="font-semibold">Sıradaki Koşu Hedefleri:</strong> ${escapeHtml(rp.next_milestone || '')}</p>
      </div>

      <div class="tint-panel p-3 space-y-1.5">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">4. Yorgunluk ve Dinlenme</span>
          <span class="stamp-tag ${fd.needs_deload ? 'stamp-ochre' : 'stamp-moss'}">${escapeHtml(fd.status || '--')}</span>
        </div>
        <p class="text-xs font-semibold">${fd.needs_deload ? 'Hacmi %40 Düşür' : 'Normal Yükte Devam'}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(fd.note || '')}</p>
        <p class="text-[11px] ochre-text tint-ochre-panel p-1.5 leading-snug"><strong class="font-semibold">Not:</strong> Yorgunluk yüksekse veya uyku düşükse antrenmanı hafif yürüyüşe çevirin.</p>
      </div>
    `;
  }

  const tiersGrid = document.getElementById('athleteTiersGrid');
  if (tiersGrid && data.athlete_levels) {
    const tiers = Object.values(data.athlete_levels);
    tiersGrid.innerHTML = tiers.map(t => `
      <div class="surface-card p-3.5 space-y-2">
        <p class="font-semibold accent-text text-xs">${escapeHtml(t.level_tr.split('(')[0])}</p>
        <p class="font-mono text-[11px] text-[var(--text-secondary)] font-medium">${escapeHtml(t.recommended_split)}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug"><strong class="text-[var(--text-primary)]">Koşu:</strong> ${escapeHtml(t.running_approach)}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug"><strong class="text-[var(--text-primary)]">Kuvvet:</strong> ${escapeHtml(t.strength_approach)}</p>
        <p class="text-[11px] moss-text tint-moss-panel p-2 mt-1"><strong class="font-semibold">Geçiş Eşiği:</strong> ${escapeHtml(t.progression_gate)}</p>
      </div>
    `).join('');
  }
}
