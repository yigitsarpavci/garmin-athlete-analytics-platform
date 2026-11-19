/* Garmin Athlete IQ — Native Top-Layer <dialog> Modals, Debrief & Coach Flyout */
let chatHistory = [];

function openDialogNative(dialogEl) {
  if (!dialogEl) return;
  if (!dialogEl.open) {
    if (typeof dialogEl.showModal === 'function') {
      dialogEl.showModal();
    } else {
      dialogEl.setAttribute('open', '');
    }
  }
}

function closeDialogNative(dialogEl) {
  if (!dialogEl) return;
  if (dialogEl.open) {
    if (typeof dialogEl.close === 'function') {
      dialogEl.close();
    } else {
      dialogEl.removeAttribute('open');
    }
  }
}

function closeActivityModal() {
  closeDialogNative(document.getElementById('activityDetailModal'));
}

function openActivityModal(act) {
  if (!act) return;
  const modal = document.getElementById('activityDetailModal');
  if (!modal) return;

  const spNames = {
    running: 'Koşu',
    sailing_v2: 'Yelken',
    strength_training: 'Kuvvet Antrenmanı',
    basketball: 'Basketbol',
    hiking: 'Doğa Yürüyüşü',
    rowing_v2: 'Kürek',
    walking: 'Yürüyüş',
    resort_skiing: 'Kayak',
    skiing: 'Kayak',
    swimming: 'Yüzme',
    cycling: 'Bisiklet',
    tennis: 'Tenis'
  };
  const spIconNames = {
    running: 'footprints',
    sailing_v2: 'compass',
    strength_training: 'dumbbell',
    basketball: 'trophy',
    hiking: 'mountain',
    rowing_v2: 'waves',
    walking: 'footprints',
    resort_skiing: 'snowflake',
    skiing: 'snowflake',
    swimming: 'waves',
    cycling: 'bike'
  };

  const sportLabel = act.sport_tr || spNames[act.sport] || String(act.sport || 'Aktivite').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const iconEl = document.getElementById('modalSportIcon');
  if (iconEl) {
    iconEl.innerHTML = lucideSvg(spIconNames[act.sport] || 'activity', 'w-5 h-5 accent-text');
  }
  document.getElementById('modalActivityTitle').textContent = act.name || sportLabel;
  document.getElementById('modalSportBadge').textContent = sportLabel;
  document.getElementById('modalActivitySub').textContent = `${act.date || ''} · ${act.time || ''}`;

  document.getElementById('modalDuration').textContent = act.dur_m ? `${act.dur_m.toFixed(0)} dk` : '--';
  document.getElementById('modalDistance').textContent = act.dist_km > 0 ? `${act.dist_km.toFixed(2)} km` : '--';
  document.getElementById('modalPace').textContent = act.pace_str || '--';
  document.getElementById('modalCalories').textContent = act.cal ? `${act.cal} kcal` : '--';

  document.getElementById('modalAvgHr').textContent = act.avg_hr ? `${act.avg_hr} bpm` : '--';
  document.getElementById('modalMaxHr').textContent = act.max_hr ? `${act.max_hr} bpm` : '--';

  let efText = '--';
  if (act.dist_km > 0 && act.dur_m > 0 && act.avg_hr > 0) {
    const speedMs = (act.dist_km * 1000) / (act.dur_m * 60);
    const ef = (speedMs / act.avg_hr) * 60;
    efText = `${ef.toFixed(2)} m/atım`;
  }
  document.getElementById('modalEf').textContent = efText;
  document.getElementById('modalHydration').textContent = act.water_ml ? `${(act.water_ml).toFixed(0)} mL (${(act.water_ml / 1000).toFixed(1)} L)` : 'Normal (~400 mL)';

  document.getElementById('modalLoad').textContent = act.load ? act.load.toFixed(1) : '0';
  document.getElementById('modalAeroTe').textContent = act.aTE ? `${act.aTE.toFixed(1)} / 5.0` : '--';
  document.getElementById('modalAnaeroTe').textContent = act.anTE !== undefined && act.anTE !== null ? `${act.anTE.toFixed(1)} / 5.0` : '0.0';

  const pwr = act.norm_pwr ? `${act.norm_pwr} W` : (act.avg_pwr ? `${act.avg_pwr} W` : '--');
  const cad = act.cadence ? `${act.cadence.toFixed(0)} spm` : '--';
  document.getElementById('modalPowerCadence').textContent = `${pwr} · ${cad}`;

  const rdRow = document.getElementById('modalRunningDynamicsRow');
  const rdEl = document.getElementById('modalRunningDynamics');
  if (rdRow && rdEl) {
    const rdParts = [];
    if (act.gct_ms) rdParts.push(`GCT ${Number(act.gct_ms).toFixed(1)} ms`);
    if (act.vert_osc_cm) rdParts.push(`VO ${Number(act.vert_osc_cm).toFixed(1)} cm`);
    if (act.vert_ratio) rdParts.push(`VR %${Number(act.vert_ratio).toFixed(1)}`);
    if (act.stride_cm) rdParts.push(`Adım ${Number(act.stride_cm).toFixed(0)} cm`);
    if (rdParts.length) {
      rdEl.textContent = rdParts.join(' · ');
      rdRow.classList.remove('hidden');
    } else {
      rdEl.textContent = '--';
      rdRow.classList.add('hidden');
    }
  }

  refreshIcons();
  openDialogNative(modal);
}

// POST-WORKOUT DEBRIEF MODAL
let currentDebriefIdx = 0;

function renderDebriefSwitchButtons(activeIdx) {
  const bar = document.getElementById('debriefSwitchBar');
  if (!bar) return;
  const acts = (typeof globalActivities !== 'undefined' && Array.isArray(globalActivities))
    ? globalActivities
    : (Array.isArray(window.globalActivities) ? window.globalActivities : []);

  const gymIdx = acts.findIndex(a => String(a.sport || '').toLowerCase() === 'strength_training');
  const runIdx = acts.findIndex(a => String(a.sport || '').toLowerCase() === 'running');
  const otherIdx = acts.findIndex(a => {
    const sp = String(a.sport || '').toLowerCase();
    return sp && sp !== 'strength_training' && sp !== 'running';
  });

  const tabs = [];
  if (gymIdx >= 0) tabs.push({ idx: gymIdx, label: 'Son Gym' });
  if (runIdx >= 0) tabs.push({ idx: runIdx, label: 'Son Koşu' });
  if (otherIdx >= 0) tabs.push({ idx: otherIdx, label: 'Son Diğer Spor' });
  if (!tabs.length) tabs.push({ idx: 0, label: 'Son Gym' });

  bar.innerHTML = tabs.map(t => {
    const cls = t.idx === activeIdx ? 'subtab-btn subtab-btn-active whitespace-nowrap' : 'subtab-btn whitespace-nowrap';
    return `<button type="button" onclick="openDebriefModal(${t.idx})" class="${cls}">${escapeHtml(t.label)}</button>`;
  }).join('');
}

async function openDebriefModal(idx = 0) {
  currentDebriefIdx = idx;
  const modal = document.getElementById('postWorkoutDebriefModal');
  if (!modal) return;
  openDialogNative(modal);
  renderDebriefSwitchButtons(idx);

  try {
    const res = await fetch('/api/post-workout-debrief?idx=' + idx);
    const d = await res.json();
    renderDebriefModalContent(d, idx);
  } catch (e) {
    console.error("Debrief yüklenemedi:", e);
  }
}

function closeDebriefModal() {
  closeDialogNative(document.getElementById('postWorkoutDebriefModal'));
}

function renderDebriefModalContent(d, idx) {
  if (!d || !d.activity) return;
  const a = d.activity;
  const tl = d.training_load || {};
  const pe = d.productive_evaluation || {};
  const bio = d.daily_biometrics_24h || {};
  const hrComp = d.hr_comparison_with_prev_same_sport || {};
  const gym = d.gym_volume_progression || {};
  const coach = d.executive_coaching_verdict || {};

  const iconEl = document.getElementById('debriefIcon');
  if (iconEl) {
    const ic = a.sport === 'strength_training' ? 'dumbbell' : (a.sport === 'running' ? 'footprints' : (String(a.sport || '').includes('ski') ? 'snowflake' : 'zap'));
    iconEl.innerHTML = lucideSvg(ic, 'w-5 h-5 accent-text');
  }
  document.getElementById('debriefTitle').textContent = `${a.name} Seans Debrief Raporu`;
  document.getElementById('debriefBadge').textContent = a.sport === 'strength_training' ? (gym.workout_type || 'Kuvvet') : (a.workout_type || a.sport_tr || (a.sport === 'running' ? 'Koşu' : 'Branş'));
  document.getElementById('debriefSub').textContent = `${a.date} · ${a.time || ''} · ${a.duration_min} dk Seans · ${a.calories} kcal`;

  document.getElementById('debriefSessionLoad').textContent = tl.session_epoc_load || a.load;
  document.getElementById('debriefAcuteChronic').textContent = `${tl.acute_load} / ${tl.chronic_load}`;
  document.getElementById('debriefAcwrRatio').textContent = tl.acwr ? tl.acwr.toFixed(2) : '1.00';
  document.getElementById('debriefAcwrBadge').textContent = tl.in_sweet_spot ? 'SWEET SPOT' : tl.acwr_status;
  document.getElementById('debriefLoadDesc').textContent = tl.interpretation || '';

  document.getElementById('debriefProductiveStatusBadge').textContent = pe.status_tr || pe.status_code;
  document.getElementById('debriefProductiveReason').textContent = pe.status_reason || '';
  document.getElementById('debriefHowToProductive').textContent = pe.how_to_reach_productive || '';

  document.getElementById('debriefWeight').textContent = `${bio.weight_kg} kg`;
  document.getElementById('debriefRhr').textContent = `${bio.resting_hr_bpm} bpm`;
  document.getElementById('debriefHrv').textContent = `${bio.overnight_hrv_ms} ms`;
  document.getElementById('debriefSleep').textContent = `${bio.sleep_score} / 100`;
  document.getElementById('debriefSleepTime').textContent = `${bio.sleep_hours} sa (${bio.sleep_stages || ''})`;
  document.getElementById('debriefBb').textContent = `${bio.body_battery_wake} / ${bio.body_battery_current}`;
  document.getElementById('debriefStress').textContent = `${bio.stress_score} Puan`;

  const avgDiff = hrComp.avg_hr_diff !== undefined ? hrComp.avg_hr_diff : 0;
  const diffSign = avgDiff > 0 ? `+${avgDiff}` : `${avgDiff}`;
  const hrBadge = document.getElementById('debriefHrDiffBadge');
  if (avgDiff <= 0) {
    hrBadge.textContent = `${diffSign} bpm TASARRUF`;
    hrBadge.className = "stamp-tag stamp-moss";
  } else {
    hrBadge.textContent = `${diffSign} bpm YÜKSEK`;
    hrBadge.className = "stamp-tag stamp-crimson";
  }

  document.getElementById('debriefCurHr').textContent = `${a.avg_hr} / ${a.max_hr} bpm`;
  document.getElementById('debriefCurDur').textContent = `${a.duration_min} dk seans`;
  document.getElementById('debriefPrevHrDate').textContent = `Önceki Seans (${hrComp.previous_date || 'Geçmiş'})`;
  document.getElementById('debriefPrevHr').textContent = `${hrComp.previous_avg_hr || '--'} / ${hrComp.previous_max_hr || '--'} bpm`;
  document.getElementById('debriefPrevDur').textContent = `${hrComp.previous_dur_m || '--'} dk seans`;
  document.getElementById('debriefHrInsight').textContent = hrComp.insight || '';

  const gymSec = document.getElementById('debriefGymSection');
  const exGrid = document.getElementById('debriefExerciseGrid');
  if (a.sport === 'strength_training' && gym && gym.current_volume_kg) {
    gymSec.classList.remove('hidden');
    document.getElementById('debriefVolumeTonnage').textContent = `${gym.current_tonnage} Ton (${gym.current_volume_kg.toLocaleString('tr-TR')} kg)`;
    const dSign = (gym.same_type_volume_delta_kg || 0) >= 0 ? `+${gym.same_type_volume_delta_kg}` : `${gym.same_type_volume_delta_kg}`;
    document.getElementById('debriefVolumeDelta').textContent = `${dSign} kg vs önceki A`;

    if (exGrid && gym.exercises) {
      exGrid.innerHTML = gym.exercises.map(ex => {
        const setDetails = (ex.sets || []).map(s => `${s.reps}x${s.weight_kg}kg`).join(', ');
        return `
          <div class="surface-card p-3 space-y-1">
            <strong class="text-xs font-semibold block truncate">${ex.name}</strong>
            <p class="font-mono text-[11px] accent-text font-medium">${ex.sets ? ex.sets.length : 0} Set: <span class="text-[var(--text-secondary)]">${setDetails}</span></p>
          </div>
        `;
      }).join('');
    }
  } else {
    if (gymSec) gymSec.classList.add('hidden');
  }

  if (coach) {
    document.getElementById('debriefVerdict').textContent = coach.verdict || '';
    document.getElementById('debriefNutritionAction').textContent = coach.nutrition_action || '';
    if (coach.next_session) {
      document.getElementById('debriefNextAction').textContent = `${coach.next_session.day}: ${coach.next_session.title} (${coach.next_session.target_hr}). ${coach.next_session.purpose}`;
    }
  }

  refreshIcons();
}

function toggleAICoach() {
  const flyout = document.getElementById('aiCoachFlyout');
  const launcher = document.getElementById('aiCoachLauncherBtn');
  if (flyout) {
    flyout.classList.toggle('hidden');
    if (launcher) {
      if (flyout.classList.contains('hidden')) {
        launcher.classList.remove('hidden');
      } else {
        launcher.classList.add('hidden');
      }
    }
  }
}

async function sendCoachMessage() {
  const input = document.getElementById('chatInputBox');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  const modelSelect = document.getElementById('aiModelSelect');
  const selectedModel = modelSelect ? modelSelect.value : 'gemini-3.8-flash-low';

  appendMessageUI('user', text);
  chatHistory.push({ role: 'user', content: text });

  const typingId = appendTypingIndicatorUI();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: text,
        model: selectedModel,
        history: chatHistory,
        custom_profile: (!currentActiveProfile.is_sarp) ? currentActiveProfile : null
      })
    });
    const data = await res.json();
    removeTypingIndicatorUI(typingId);

    chatHistory.push({ role: 'assistant', content: data.answer });
    appendMessageUI('coach', data.answer, data);
  } catch (e) {
    removeTypingIndicatorUI(typingId);
    appendMessageUI('coach', 'Bağlantıda bir hata oluştu, lütfen tekrar deneyin.');
  }
}

function askCoachPrompt(prompt) {
  const flyout = document.getElementById('aiCoachFlyout');
  if (flyout) flyout.classList.remove('hidden');
  document.getElementById('chatInputBox').value = prompt;
  sendCoachMessage();
}

function appendTypingIndicatorUI() {
  const c = document.getElementById('chatMessagesContainer');
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.id = id;
  div.className = "surface-card p-3 mr-6 flex items-center gap-2.5 text-[11px] text-[var(--text-secondary)]";
  div.innerHTML = `
        <span class="flex gap-1">
          <span class="w-1.5 h-1.5 accent-bg rounded-sm animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-1.5 h-1.5 accent-bg rounded-sm animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-1.5 h-1.5 accent-bg rounded-sm animate-bounce" style="animation-delay: 300ms"></span>
        </span>
        <span class="font-medium text-[var(--text-primary)]">Garmin telemetrisi ve spor bilimi taranıyor...</span>
      `;
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
  return id;
}

function removeTypingIndicatorUI(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function formatCoachMarkdown(rawText) {
  const esc = String(rawText ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  const applyInline = (s) => s
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^\*])\*([^*]+?)\*(?!\*)/g, '$1<em>$2</em>');

  const lines = esc.split(/\r?\n/);
  const blocks = [];
  let inList = false;
  let paraLines = [];

  const flushPara = () => {
    if (paraLines.length) {
      blocks.push(`<p>${paraLines.map(applyInline).join('<br>')}</p>`);
      paraLines = [];
    }
  };
  const closeList = () => {
    if (inList) {
      blocks.push('</ul>');
      inList = false;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const listMatch = trimmed.match(/^(?:•|-|\*|\d+\.)\s+(.*)$/);
    if (!trimmed) {
      flushPara();
      closeList();
    } else if (listMatch) {
      flushPara();
      if (!inList) {
        blocks.push('<ul>');
        inList = true;
      }
      blocks.push(`<li>${applyInline(listMatch[1])}</li>`);
    } else {
      closeList();
      paraLines.push(trimmed);
    }
  }
  flushPara();
  closeList();
  return blocks.join('');
}

function appendMessageUI(sender, text, meta = null) {
  const c = document.getElementById('chatMessagesContainer');
  const div = document.createElement('div');
  if (sender === 'user') {
    div.className = "accent-bg chat-message-bubble p-3 rounded-[3px] self-end ml-6";
    div.textContent = text;
  } else {
    div.className = "surface-card chat-message-bubble p-3.5 mr-2 space-y-2";
    const formatted = formatCoachMarkdown(text);

    let metaHtml = '';
    if (meta) {
      const isReal = meta.is_real_ai;
      const badgeClass = isReal ? 'stamp-tag stamp-moss' : 'stamp-tag';
      const iconName = isReal ? 'zap' : 'cpu';
      metaHtml = `
<div class="pt-2 mt-2 border-t border-[var(--border-subtle)] flex items-center justify-between font-mono text-[10px] text-[var(--text-muted)]">
  <span class="${badgeClass}">
    ${lucideSvg(iconName, 'w-3 h-3')} ${escapeHtml(meta.provider || 'Gerçek AI')}
  </span>
  <span>${meta.response_time_sec ? meta.response_time_sec + ' sn' : ''}</span>
</div>
      `;
    }

    div.innerHTML = formatted + metaHtml;
  }
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
  refreshIcons();
}

/* Fallback light dismiss for dialog[closedby="any"] in browsers lacking HTMLDialogElement.prototype.closedBy */
if (!('closedBy' in HTMLDialogElement.prototype)) {
  const outside = (e, dialog) => {
    const r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };
  for (const dialog of document.querySelectorAll('dialog[closedby="any"]')) {
    let pressedOutside = false;
    dialog.addEventListener('pointerdown', (e) => { pressedOutside = outside(e, dialog); });
    dialog.addEventListener('pointerup', (e) => { if (pressedOutside && outside(e, dialog)) dialog.close(); });
  }
}

window.addEventListener('DOMContentLoaded', initApp);
