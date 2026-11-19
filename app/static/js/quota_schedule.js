/* Garmin Athlete IQ — Flexible Weekly Quota Ledger, Adaptive Carryover & Daily Protocols */

function escapeHtml(val) {
  return String(val ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function resolveProtocolIndex(slotKind, dayCode, fallbackText = '', fallbackIdx = 0) {
  if (typeof cachedDailyProtocols === 'undefined' || !Array.isArray(cachedDailyProtocols) || !cachedDailyProtocols.length) {
    return fallbackIdx;
  }
  if (dayCode) {
    const byCode = cachedDailyProtocols.findIndex(p => p.day_code === dayCode);
    if (byCode >= 0) return byCode;
  }
  const kindToCode = {
    gym_a: 'tuesday',
    gym: 'tuesday',
    gym_b: 'saturday',
    zone2: 'thursday',
    run: 'thursday',
    interval: 'monday',
    tempo: 'monday',
    active_recovery: 'sunday',
    rest: 'wednesday'
  };
  if (slotKind && kindToCode[slotKind]) {
    const mapped = cachedDailyProtocols.findIndex(p => p.day_code === kindToCode[slotKind]);
    if (mapped >= 0) return mapped;
  }
  const lower = (fallbackText || '').toLowerCase();
  if (lower.includes('workout b')) {
    const bIdx = cachedDailyProtocols.findIndex(p => p.day_code === 'saturday');
    if (bIdx >= 0) return bIdx;
  }
  if (lower.includes('workout a')) {
    const aIdx = cachedDailyProtocols.findIndex(p => p.day_code === 'tuesday');
    if (aIdx >= 0) return aIdx;
  }
  if (lower.includes('zone 2')) {
    const zIdx = cachedDailyProtocols.findIndex(p => p.day_code === 'thursday');
    if (zIdx >= 0) return zIdx;
  }
  if (lower.includes('interval') || lower.includes('interva') || lower.includes('hız')) {
    const iIdx = cachedDailyProtocols.findIndex(p => p.day_code === 'monday');
    if (iIdx >= 0) return iIdx;
  }
  const dayMap = [
    ['pzt', 'monday'], ['sal', 'tuesday'], ['çar', 'wednesday'],
    ['per', 'thursday'], ['cum', 'friday'], ['cmt', 'saturday'], ['paz', 'sunday']
  ];
  const matched = dayMap.find(([trCode]) => lower.includes(trCode));
  if (matched) {
    const found = cachedDailyProtocols.findIndex(p => p.day_code === matched[1]);
    if (found >= 0) return found;
  }
  return fallbackIdx;
}

function openQuotaItemRecipe(slotKind, dayCode) {
  if (typeof setTab === 'function') setTab('plan');
  if (typeof setSubTab === 'function') setSubTab('plan', 'protocols');
  const targetIdx = resolveProtocolIndex(slotKind, dayCode, '', 0);
  if (typeof selectProtocolDay === 'function') selectProtocolDay(targetIdx);
}

function buildQuotaBucketCard(label, iconName, bucket, barColorClass, extraHtml = '') {
  const target = bucket.target ?? 0;
  const completed = bucket.completed ?? 0;
  const remaining = bucket.remaining ?? 0;
  const pct = Math.max(0, Math.min(100, bucket.progress_pct ?? (target > 0 ? Math.round((Math.min(completed, target) / target) * 100) : 0)));
  const isDone = target > 0 && remaining === 0;
  const completedLabels = Array.isArray(bucket.completed_labels) ? bucket.completed_labels : [];
  const remItems = Array.isArray(bucket.remaining_items) ? bucket.remaining_items : [];
  const remTypesText = remItems.map(i => i.short_label || i.type || i.badge).filter(Boolean).join(' + ');
  const planSummary = bucket.plan_summary || '';

  const doneHtml = completedLabels.length
    ? `<div class="space-y-1 pt-1">
        ${completedLabels.map(lbl => `<p class="text-[11px] moss-text font-medium flex items-start gap-1.5 break-words"><span class="shrink-0">✓</span><span>${escapeHtml(lbl)}</span></p>`).join('')}
      </div>`
    : '';

  const remHtml = remaining > 0 && remItems.length
    ? `<div class="space-y-1.5 pt-1">
        <p class="font-mono text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">
          Kalan: <strong class="text-[var(--text-primary)]">${remaining}</strong>${remTypesText ? ` (${escapeHtml(remTypesText)})` : ''}
        </p>
        <div class="space-y-1.5">
          ${remItems.map(item => {
            const meta = item.target_pace || item.duration || '';
            const dayCode = escapeHtml(item.protocol_day_code || '');
            const slotKind = escapeHtml(item.slot_kind || '');
            const detail = item.target_hr || item.exercises_summary || item.coaching_note || '';
            const prioBadge = item.prioritized_from_last_week
              ? `<span class="stamp-tag stamp-ochre">GEÇEN HAFTADAN ÖNCELİKLİ</span>`
              : '';
            return `<div class="w-full text-left tint-panel px-2 py-1.5">
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="stamp-tag stamp-accent">${escapeHtml(item.short_label || item.badge || item.type || 'Kalan')}</span>
                  ${prioBadge}
                  ${meta ? `<span class="font-mono text-[11px] text-[var(--text-secondary)]">${escapeHtml(meta)}</span>` : ''}
                </div>
                ${detail ? `<p class="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-snug whitespace-normal break-words">${escapeHtml(detail)}</p>` : ''}
              </div>
            </div>`;
          }).join('')}
        </div>
      </div>`
    : `<p class="text-[11px] ${isDone ? 'moss-text font-medium' : 'text-[var(--text-secondary)]'} pt-0.5">
        ${isDone
          ? (completed > target ? `✓ Bu haftanın kotası tamamlandı (+${completed - target} ekstra seans).` : '✓ Bu haftanın kotası tamamlandı.')
          : escapeHtml(bucket.status_text || 'Kota tanımlanmadı.')}
      </p>`;

  return `
    <div class="tint-panel p-2.5 space-y-1.5 flex flex-col justify-between min-w-0">
      <div class="space-y-1.5">
        <div class="flex items-center justify-between gap-1.5 flex-wrap">
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
            ${lucideSvg(iconName, 'w-3.5 h-3.5 accent-text shrink-0')}
            <span>${escapeHtml(label)}</span>
          </span>
          <span class="stamp-tag ${isDone ? 'stamp-moss' : 'stamp-accent'} tabular-nums">${completed} / ${target}</span>
        </div>
        <div class="w-full bg-[var(--bg-surface-elevated)] h-1.5 overflow-hidden rounded-[1px]">
          <div class="${isDone ? 'bg-[var(--moss)]' : barColorClass} h-1.5 transition-all duration-500" style="width: ${pct}%"></div>
        </div>
        ${planSummary ? `<p class="font-mono text-[10.5px] text-[var(--text-secondary)] leading-tight">${escapeHtml(planSummary)}</p>` : ''}
        ${doneHtml}
      </div>
      ${remHtml}
      ${extraHtml}
    </div>
  `;
}

function buildSpontaneousCard(spont, restCount = 0) {
  const count = spont.count ?? 0;
  const items = Array.isArray(spont.items) ? spont.items : [];
  const labels = Array.isArray(spont.labels) ? spont.labels : [];
  const sportTrLookup = {
    sailing: 'Yelken', basketball: 'Basketbol', swimming: 'Yüzme',
    cycling: 'Bisiklet', tennis: 'Tenis', pilates: 'Pilates / Mobilite',
    resort_skiing: 'Kayak', hiking: 'Doğa Yürüyüşü', walking: 'Yürüyüş'
  };

  let bodyHtml = `<p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(spont.status_text || 'Bu hafta henüz spontane branş kaydı yok.')}</p>`;
  if (items.length > 0) {
    bodyHtml = `
      <div class="space-y-1.5">
        ${items.map(it => `
          <div class="surface-card p-2.5 text-[11px] space-y-0.5">
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold text-[var(--text-primary)] truncate">${escapeHtml(it.sport_tr || sportTrLookup[it.sport] || 'Ek Branş')} · ${escapeHtml(it.title || '')}</span>
              <span class="font-mono text-[11px] moss-text shrink-0">${escapeHtml(it.day_label || it.date || '')}</span>
            </div>
            <p class="font-mono text-[11px] text-[var(--text-secondary)]">${it.duration_min ? `${it.duration_min} dk` : ''}${it.avg_hr ? ` · ${it.avg_hr} bpm` : ''}${it.calories ? ` · ${it.calories} kcal` : ''}</p>
          </div>
        `).join('')}
      </div>
    `;
  } else if (labels.length > 0) {
    bodyHtml = `
      <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(spont.status_text || '')}</p>
      <div class="flex flex-wrap gap-1.5 pt-1">
        ${labels.map(l => `<span class="stamp-tag">${escapeHtml(sportTrLookup[l] || l)}</span>`).join('')}
      </div>
    `;
  }

  return `
    <div class="tint-panel p-2.5 space-y-1.5 flex flex-col justify-between min-w-0">
      <div class="space-y-1.5">
        <div class="flex items-center justify-between gap-1.5 flex-wrap">
          <span class="font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
            ${lucideSvg('compass', 'w-3.5 h-3.5 violet-text shrink-0')}
            <span>Spontane Branşlar</span>
          </span>
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="font-mono text-[10.5px] text-[var(--text-muted)] tabular-nums inline-flex items-center gap-1" title="Bu hafta gerçekleşen dinlenme günü">${lucideSvg('moon', 'w-3 h-3 sky-text shrink-0')}${restCount}g dinlenme</span>
            <span class="stamp-tag stamp-violet tabular-nums">${count} Seans</span>
          </div>
        </div>
        ${bodyHtml}
      </div>
      <p class="font-mono text-[11px] text-[var(--text-muted)] pt-1 border-t border-[var(--border-subtle)] leading-tight">Yelken, Basketbol, Kayak vb. sabit kota kaplamaz.</p>
    </div>
  `;
}

function buildQuotaLedgerHtml(quota) {
  const total = quota.total || { target: 4, completed: 0, remaining: 4, progress_pct: 0, is_complete: false };
  const run = quota.running || { target: 2, completed: 0, remaining: 2, progress_pct: 0, completed_labels: [], remaining_items: [] };
  const str = quota.strength || { target: 2, completed: 0, remaining: 2, progress_pct: 0, completed_labels: [], remaining_items: [] };
  const spont = quota.spontaneous || { count: 0, items: [], labels: [] };
  const weekRange = quota.week_range || 'Bu Hafta';
  const totalBadgeCls = total.is_complete ? 'stamp-moss' : 'stamp-accent';
  const adapt = quota.last_week_adaptation || null;
  const hasMissedCarry = adapt && Array.isArray(adapt.missed_sessions) && adapt.missed_sessions.length > 0;
  const deviations = Array.isArray(quota.plan_deviations) ? quota.plan_deviations : [];

  const deviationHtml = deviations.length
    ? deviations.map(d => `
      <div class="tint-ochre-panel px-2.5 py-1.5 text-[12px] space-y-1 min-w-0">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[11px] uppercase tracking-wider ochre-text font-semibold flex items-center gap-1">
            ${lucideSvg('alert-triangle', 'w-3 h-3 shrink-0 ochre-text')}
            <span>Kota Uyarlaması</span>
          </span>
          <span class="stamp-tag stamp-ochre">${escapeHtml(d.badge || 'Güncellendi')}</span>
        </div>
        <p class="ochre-text leading-snug">${escapeHtml(d.note || '')}</p>
      </div>
    `).join('')
    : '';

  const adaptHtml = adapt && adapt.adaptation_note
    ? `<div class="${hasMissedCarry ? 'tint-ochre-panel' : 'tint-moss-panel'} px-2.5 py-1.5 text-[12px] space-y-1 min-w-0">
        <div class="flex flex-wrap items-center justify-between gap-1.5">
          <span class="font-mono text-[11px] uppercase tracking-wider ${hasMissedCarry ? 'ochre-text' : 'moss-text'} font-semibold flex items-center gap-1">
            ${lucideSvg(hasMissedCarry ? 'refresh-cw' : 'check', `w-3 h-3 shrink-0 ${hasMissedCarry ? 'ochre-text' : 'moss-text'}`)}
            <span>Haftalık Kota Geçişi</span>
          </span>
          ${adapt.monday_reset_enforced ? `<span class="font-mono text-[11px] text-[var(--text-secondary)] shrink-0">Pzt 0/${escapeHtml(run.target ?? 2)}</span>` : ''}
        </div>
        <p class="${hasMissedCarry ? 'ochre-text' : 'moss-text'} leading-snug">${escapeHtml(adapt.adaptation_note)}</p>
      </div>`
    : '';

  const bannerRowHtml = (deviationHtml || adaptHtml)
    ? `<div class="grid grid-cols-1 lg:grid-cols-2 gap-1.5">${deviationHtml}${adaptHtml}</div>`
    : '';

  const restCount = Number((quota.rest_days || {}).count ?? ((quota.rest_days || {}).days || []).length ?? 0);
  const predSteps = Array.isArray((quota.next_4_runs_prediction || {}).steps) ? quota.next_4_runs_prediction.steps : [];
  const runShortMap = { interval: 'İnterval', zone2: 'Zone 2', tempo: 'Tempo', gym_overflow: 'Kuvvet' };
  const runProjectionHtml = predSteps.length
    ? `<div class="pt-1.5 border-t border-[var(--border-subtle)] space-y-1">
        <p class="font-mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Sıradaki ${predSteps.length} Koşu Projeksiyonu (Yük Barı)</p>
        <div class="flex flex-wrap gap-1">
          ${predSteps.map((s, idx) => {
            const inWeek = idx < (run.target ?? 2);
            const lbl = runShortMap[s.kind] || s.short_label || s.kind || 'Koşu';
            const cls = inWeek ? 'stamp-accent' : 'bg-[var(--bg-surface-elevated)] text-[var(--text-muted)] border border-[var(--border-subtle)]';
            return `<span class="font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] ${cls}" title="${escapeHtml(s.reason || '')}">${idx + 1}. ${escapeHtml(lbl)}</span>`;
          }).join('')}
        </div>
      </div>`
    : '';

  return `
    ${bannerRowHtml}

    <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
      ${buildQuotaBucketCard('Koşu Kotası', 'footprints', run, 'bg-[#4B8EC2]', runProjectionHtml)}
      ${buildQuotaBucketCard('Kuvvet Kotası', 'dumbbell', str, 'bg-[var(--moss)]')}
      ${buildSpontaneousCard(spont, restCount)}
    </div>

  `;
}

function renderWeeklyQuotaPanels(quota) {
  if (!quota || !quota.total) return;

  const html = buildQuotaLedgerHtml(quota);
  const overviewPanel = document.getElementById('weeklyQuotaPanel');
  if (overviewPanel) overviewPanel.innerHTML = html;

  const planPanel = document.getElementById('planQuotaSummary');
  if (planPanel) planPanel.innerHTML = html;

  if (typeof refreshIcons === 'function') refreshIcons();
}

let cachedDailyProtocols = [];
let selectedProtocolMode = 0;

function selectProtocolDay(mode) {
  selectedProtocolMode = mode;
  try {
    const p = Array.isArray(cachedDailyProtocols) ? cachedDailyProtocols[mode] : null;
    if (p && p.day_code) localStorage.setItem('garmin_active_protocol_code', p.day_code);
  } catch (_) {}
  renderDailyProtocols(cachedDailyProtocols);
}

function getProtocolTabLabel(p) {
  if (p && p.category === 'gym' && p.slot_label && p.slot_label !== 'Workout A' && p.slot_label !== 'Workout B') {
    return p.slot_label;
  }
  const byCode = {
    tuesday: 'Gym A',
    wednesday: 'Dinlenme',
    thursday: 'Zone 2',
    tempo: 'Tempo',
    friday: 'Hazırlık',
    saturday: 'Gym B',
    sunday: 'Toparlanma',
    monday: 'İnterval'
  };
  if (p.day_code && byCode[p.day_code]) return byCode[p.day_code];
  return p.slot_label || p.badge || 'Reçete';
}

function getQuotaStatusStamp(quotaStatus) {
  if (quotaStatus === 'remaining') return '<span class="stamp-tag stamp-accent">KALAN KOTA</span>';
  if (quotaStatus === 'completed') return '<span class="stamp-tag stamp-moss">TAMAMLANDI</span>';
  return '<span class="stamp-tag">ESNEK ŞABLON</span>';
}

function renderDailyProtocols(protocols) {
  const container = document.getElementById('dailyProtocolsContainer');
  const tabsEl = document.getElementById('protocolDayTabs');
  if (!container || !protocols || !Array.isArray(protocols) || !protocols.length) return;
  cachedDailyProtocols = protocols;

  const orderMap = { tuesday: 0, saturday: 1, thursday: 2, tempo: 3, monday: 4 };
  const sortedIndices = protocols
    .map((_, idx) => idx)
    .filter(idx => Object.prototype.hasOwnProperty.call(orderMap, protocols[idx]?.day_code))
    .sort((a, b) => orderMap[protocols[a].day_code] - orderMap[protocols[b].day_code]);

  let savedIdx = -1;
  try {
    const savedCode = localStorage.getItem('garmin_active_protocol_code');
    if (savedCode && Object.prototype.hasOwnProperty.call(orderMap, savedCode)) {
      savedIdx = protocols.findIndex(p => p.day_code === savedCode);
    }
  } catch (_) {}

  let activeIdx = (typeof selectedProtocolMode === 'number' && sortedIndices.includes(selectedProtocolMode))
    ? selectedProtocolMode
    : (sortedIndices.includes(savedIdx)
      ? savedIdx
      : (sortedIndices.find(idx => protocols[idx]?.quota_status === 'remaining') ?? sortedIndices[0] ?? 0));
  if (!sortedIndices.includes(activeIdx)) activeIdx = sortedIndices[0] ?? 0;
  selectedProtocolMode = activeIdx;

  if (tabsEl) {
    const activeCls = 'subtab-btn subtab-btn-active';
    const idleCls = 'subtab-btn';
    tabsEl.innerHTML = `<div class="subtab-bar">${sortedIndices.map((idx) => {
      const p = protocols[idx];
      const remDot = p.quota_status === 'remaining' ? ' <span class="accent-text">●</span>' : '';
      return `<button type="button" data-calls="[[&quot;selectProtocolDay&quot;, ${idx}]]" class="${activeIdx === idx ? activeCls : idleCls}">${escapeHtml(getProtocolTabLabel(p))}${remDot}</button>`;
    }).join('')}</div>`;
  }

  const p = protocols[activeIdx];
  let exerciseHtml = '';
  if (p.category === 'gym') {
    exerciseHtml = `
<div tabindex="0" role="region" aria-label="${escapeHtml(p.day_title)} egzersiz tablosu" class="table-scroll-region mt-1">
  <table class="w-full text-left text-[11px]">
    <thead>
      <tr>
        <th class="py-1 px-1.5">#</th>
        <th class="py-1 px-1.5">Egzersiz</th>
        <th class="py-1 px-1.5">Set x Tekrar</th>
        <th class="py-1 px-1.5">Mevcut &amp; Hedef Ağırlık</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-[var(--border-subtle)]">
      ${(p.exercises || []).map(ex => `
        <tr class="hover:bg-[var(--bg-subtle)]">
          <td class="py-1 px-1.5 font-mono font-semibold text-[var(--text-muted)]">${ex.num}</td>
          <td class="py-1 px-1.5 font-semibold">${escapeHtml(ex.name)}</td>
          <td class="py-1 px-1.5 font-mono font-semibold accent-text whitespace-nowrap">${ex.sets} x ${ex.reps}</td>
          <td class="py-1 px-1.5">
            <span class="stamp-tag stamp-moss">${escapeHtml(ex.target_weight)}</span>
            ${ex.current_achieved ? `<span class="font-mono text-[11px] text-[var(--text-muted)] ml-1">Son: ${escapeHtml(ex.current_achieved)}</span>` : ''}
          </td>
        </tr>
      `).join('')}
    </tbody>
  </table>
</div>
    `;
  } else if (p.category === 'running') {
    const runEx = (p.exercises || [])[0] || {};
    exerciseHtml = `
<div class="tint-panel p-3.5 space-y-2.5 mt-1.5">
  <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
    <div>
      <p class="font-mono text-[11px] text-[var(--text-secondary)] uppercase">Süre / Mesafe</p>
      <p class="font-mono font-bold text-sm mt-0.5">${escapeHtml(runEx.duration || (runEx.sets + ' x ' + runEx.reps))}</p>
      ${runEx.distance_est ? `<p class="font-mono text-[11px] text-[var(--text-muted)]">${escapeHtml(runEx.distance_est)}</p>` : ''}
    </div>
    <div>
      <p class="font-mono text-[11px] text-[var(--text-secondary)] uppercase">Hedef Nabız</p>
      <p class="font-mono font-bold moss-text text-sm mt-0.5">${escapeHtml(runEx.target_hr)}</p>
    </div>
    <div>
      <p class="font-mono text-[11px] text-[var(--text-secondary)] uppercase">Hedef Kadans</p>
      <p class="font-mono font-bold text-sm mt-0.5">${escapeHtml(runEx.cadence_target)}</p>
    </div>
  </div>
  <p class="text-xs text-[var(--text-secondary)] pt-2 border-t border-[var(--border-subtle)]"><strong class="text-[var(--text-primary)] font-semibold">Koçluk Talimatı:</strong> ${escapeHtml(runEx.coaching_cue)}</p>
</div>
    `;
  } else {
    const restEx = (p.exercises || [])[0] || {};
    exerciseHtml = `
<div class="tint-panel p-3.5 space-y-1 mt-1.5 text-xs">
  <p class="font-semibold">${escapeHtml(restEx.protocol)}</p>
  <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(restEx.coaching_cue)}</p>
</div>
    `;
  }

  container.innerHTML = `
    <div class="surface-card p-2.5 space-y-1 h-full flex flex-col justify-between overflow-hidden">
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-1.5 shrink-0">
        <div class="flex flex-wrap items-center gap-2">
          <span class="stamp-tag stamp-accent">${escapeHtml(p.badge)}</span>
          ${getQuotaStatusStamp(p.quota_status)}
          <h4 class="font-editorial text-sm sm:text-base font-medium tracking-tight">${escapeHtml(p.day_title)}</h4>
        </div>
        <span class="font-mono text-[12px] text-[var(--text-secondary)]">${escapeHtml(p.status_note)}</span>
      </div>

      ${exerciseHtml}
    </div>
  `;
  if (typeof refreshIcons === 'function') refreshIcons();
}
