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
        <span class="violet-text shrink-0">${r.ideal_source === 'personal' ? 'Kişisel' : 'İdeal'}: ${escapeHtml(r.ideal_ref)}</span>
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
  const list = document.getElementById('correlationsList');
  if (!list || !Array.isArray(corrs)) return;
  if (!corrs.length) {
    list.innerHTML = '<p class="py-3 px-3 text-[11px] text-[var(--text-secondary)]">Korelasyon için yeterli günlük veri yok (en az 6 gün gerekir).</p>';
    return;
  }
  // Her satır eşit yükseklikte esner: liste, sağdaki 93G tablosunun yüksekliğini tam doldurur. Çubuk r değerini (−1…+1) merkezden gösterir.
  list.innerHTML = corrs.map(c => {
    const r = Number(c.r);
    const neg = r < 0;
    const pct = Math.min(100, Math.abs(r) * 100) / 2;
    const col = c.significant ? (neg ? 'var(--ochre, #C99A49)' : 'var(--accent, #6BA7D6)') : 'var(--text-muted)';
    const titleCls = c.significant ? (neg ? 'ochre-text' : 'sky-text') : 'text-[var(--text-muted)]';
    const fill = neg ? `right:50%;width:${pct.toFixed(1)}%` : `left:50%;width:${pct.toFixed(1)}%`;
    const rTxt = (Number.isFinite(r) ? r.toFixed(2) : '--').replace('.', ',');
    return `
      <div role="listitem" class="tint-panel px-2.5 py-1 grid grid-cols-[1fr_auto] gap-x-3 items-center" style="flex:1 1 0;min-height:0">
        <div class="min-w-0">
          <p class="text-[11px] font-semibold leading-tight ${titleCls}">${escapeHtml(c.pair)}</p>
          <p class="text-[10.5px] text-[var(--text-secondary)] leading-snug">${escapeHtml(c.insight)}</p>
        </div>
        <div class="w-44 shrink-0 text-right" title="${escapeHtml(`${c.strength || ''} ${c.direction || ''} · n=${c.n ?? '--'} · p ${c.p || ''}`)}">
          <div class="relative h-2 bg-[var(--bg-surface-elevated)] rounded-[1px]">
            <span class="absolute top-[-2px] bottom-[-2px] w-px bg-[var(--border-medium)]" style="left:50%"></span>
            <span class="absolute top-0 bottom-0 rounded-[1px]" style="${fill};background:${col}"></span>
          </div>
          <span class="font-mono text-[10px] tabular-nums" style="color:${col}">r ${rTxt}</span>
          <span class="font-mono text-[10px] text-[var(--text-muted)]"> · ${escapeHtml(c.strength || '')}</span>
        </div>
      </div>`;
  }).join('');
}

function renderProgressionAssessment(data) {
  if (!data) return;
  const vp = data.volume_progression || {};
  const st = data.style_transition || {};
  const rp = data.running_progression || {};

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

      <div class="tint-panel p-3 space-y-1.5 border-l-[3px] border-l-[var(--accent)] md:col-span-2">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">3. Koşu: Mevcut Durum ve Hedef</span>
          <span class="stamp-tag stamp-moss">${escapeHtml(rp.verdict || 'EN EKSİK BAR')}</span>
        </div>
        <p class="font-mono text-[11px] font-semibold accent-text">${escapeHtml(rp.current_metrics || '')}</p>
        <p class="text-xs text-[var(--text-primary)] font-medium leading-snug">${escapeHtml(rp.current_model || '')}</p>
        <p class="font-mono text-[12px] text-[var(--text-secondary)]">${escapeHtml(rp.load_balance || '')}</p>
        <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(rp.advice || st.running_style_advice || '')}</p>
        <p class="text-[12px] moss-text tint-moss-panel p-1.5 leading-snug"><strong class="font-semibold">Sıradaki Koşu Hedefleri:</strong> ${escapeHtml(rp.next_milestone || '')}</p>
      </div>
    `;
  }
}
