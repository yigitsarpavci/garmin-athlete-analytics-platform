/* Garmin Athlete IQ — Health, Sleep Architecture, 93d Biometrics, Morphology, Settings & Progression */

function render93dBiometrics(rows) {
  const tbody = document.getElementById('healthMetrics93dBody');
  if (!tbody || !Array.isArray(rows) || !rows.length) return;
  tbody.innerHTML = rows.map(r => {
    const stLower = String(r.status || '').toLowerCase();
    const stCls = (stLower.includes('iyi') || stLower.includes('optimal') || stLower.includes('normal') || stLower.includes('sağlıklı'))
      ? 'moss-text font-medium'
      : ((stLower.includes('artır') || stLower.includes('dikkat') || stLower.includes('orta') || stLower.includes('sınır'))
        ? 'ochre-text font-medium'
        : 'text-[var(--text-secondary)]');
    return `
      <tr class="hover:bg-[var(--bg-subtle)] transition">
        <td class="py-1.5 px-3 font-medium">${escapeHtml(r.metric)}</td>
        <td class="py-1.5 px-3 font-mono font-semibold sky-text">${escapeHtml(r.avg_median)}</td>
        <td class="py-1.5 px-3 font-mono text-[var(--text-secondary)]">${escapeHtml(r.min_max)}</td>
        <td class="py-1.5 px-3 font-mono violet-text">${escapeHtml(r.ideal_ref)}</td>
        <td class="py-1.5 px-3 ${stCls}">${escapeHtml(r.status)}</td>
      </tr>
    `;
  }).join('');
}

function renderCorrelations(corrs) {
  const cBody = document.getElementById('correlationsBody');
  if (!cBody || !Array.isArray(corrs)) return;
  cBody.innerHTML = '';
  if (!corrs.length) {
    cBody.innerHTML = '<tr><td colspan="4" class="py-3 px-3 text-[var(--text-secondary)]">Korelasyon için yeterli günlük veri yok (en az 6 gün gerekir).</td></tr>';
    return;
  }
  corrs.forEach(c => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-[var(--bg-subtle)] transition";
    const pairCls = c.significant ? (Number(c.r) < 0 ? 'ochre-text' : 'sky-text') : 'text-[var(--text-muted)]';
    const rTxt = Number(c.r).toFixed(2).replace('.', ',');
    tr.innerHTML = `
      <td class="py-1.5 px-3 font-semibold ${pairCls}">${escapeHtml(c.pair)}</td>
      <td class="py-1.5 px-3 font-mono whitespace-nowrap">${escapeHtml(rTxt)} <span class="text-[var(--text-muted)]">(${escapeHtml(c.strength || '')})</span></td>
      <td class="py-1.5 px-3 font-mono whitespace-nowrap text-[var(--text-secondary)]">${escapeHtml(String(c.p))}</td>
      <td class="py-1.5 px-3 text-[var(--text-secondary)]">${escapeHtml(c.insight)}</td>
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
