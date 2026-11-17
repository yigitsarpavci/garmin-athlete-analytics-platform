/* Garmin Athlete IQ — Precision Modals, Debrief & AI Coach Flyout */
function closeActivityModal() {
  const modal = document.getElementById('activityDetailModal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
  }
}

function openActivityModal(act) {
  if (!act) return;
  const modal = document.getElementById('activityDetailModal');
  if (!modal) return;
  document.body.style.overflow = 'hidden';

  const spNames = {
    running: 'Koşu',
    sailing_v2: 'Yelken',
    strength_training: 'Kuvvet Antrenmanı',
    basketball: 'Basketbol',
    hiking: 'Doğa Yürüyüşü',
    rowing_v2: 'Kürek',
    walking: 'Yürüyüş'
  };
  const spIconNames = {
    running: 'footprints',
    sailing_v2: 'compass',
    strength_training: 'dumbbell',
    basketball: 'trophy',
    hiking: 'mountain',
    rowing_v2: 'waves',
    walking: 'footprints'
  };

  const iconEl = document.getElementById('modalSportIcon');
  if (iconEl) {
    iconEl.innerHTML = lucideSvg(spIconNames[act.sport] || 'activity', 'w-5 h-5 text-indigo-500 dark:text-indigo-400');
  }
  document.getElementById('modalActivityTitle').textContent = act.name || (spNames[act.sport] || 'Aktivite');
  document.getElementById('modalSportBadge').textContent = spNames[act.sport] || act.sport;
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

  const btnAi = document.getElementById('btnAskAiAboutAct');
  if (btnAi) {
    btnAi.onclick = () => {
      closeActivityModal();
      const flyout = document.getElementById('aiCoachFlyout');
      const launcher = document.getElementById('aiCoachLauncherBtn');
      if (flyout) flyout.classList.remove('hidden');
      if (launcher) launcher.classList.add('hidden');

      const input = document.getElementById('chatInputBox');
      if (input) {
        input.value = `${act.date} tarihindeki ${spNames[act.sport] || act.sport} antrenmanımı (${act.dur_m ? act.dur_m.toFixed(0) : 0} dk, ortalama ${act.avg_hr || 0} bpm nabız, ${act.load ? act.load.toFixed(1) : 0} yük) fizyolojik ve toparlanma açısından analiz eder misin?`;
        sendCoachMessage();
      }
    };
  }

  refreshIcons();
  modal.classList.remove('hidden');
}

// POST-WORKOUT DEBRIEF MODAL
let currentDebriefIdx = 0;

async function openDebriefModal(idx = 0) {
  currentDebriefIdx = idx;
  const modal = document.getElementById('postWorkoutDebriefModal');
  if (!modal) return;
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';

  const btnGym = document.getElementById('debriefBtnGym');
  const btnRun = document.getElementById('debriefBtnRun');
  const activeCls = "px-2.5 py-1 rounded-md font-semibold bg-white dark:bg-zinc-900 text-zinc-950 dark:text-zinc-50 border border-zinc-200/80 dark:border-zinc-700 transition-all duration-200 active:scale-[0.98] inline-flex items-center gap-1.5";
  const idleCls = "px-2.5 py-1 rounded-md font-medium text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all duration-200 active:scale-[0.98] inline-flex items-center gap-1.5";
  if (btnGym && btnRun) {
    btnGym.className = idx === 0 ? activeCls : idleCls;
    btnRun.className = idx === 0 ? idleCls : activeCls;
  }

  try {
    const res = await fetch('/api/post-workout-debrief?idx=' + idx);
    const d = await res.json();
    renderDebriefModalContent(d, idx);
  } catch (e) {
    console.error("Debrief yüklenemedi:", e);
  }
}

function closeDebriefModal() {
  const modal = document.getElementById('postWorkoutDebriefModal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
  }
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
    const ic = a.sport === 'strength_training' ? 'dumbbell' : (a.sport === 'running' ? 'footprints' : 'zap');
    iconEl.innerHTML = lucideSvg(ic, 'w-5 h-5 text-indigo-600 dark:text-indigo-400');
  }
  document.getElementById('debriefTitle').textContent = `${a.name} Seans Debrief Raporu`;
  document.getElementById('debriefBadge').textContent = a.sport === 'strength_training' ? (gym.workout_type || 'Kuvvet') : 'Koşu';
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
    hrBadge.className = "font-mono text-[10px] font-medium px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20";
  } else {
    hrBadge.textContent = `${diffSign} bpm YÜKSEK`;
    hrBadge.className = "font-mono text-[10px] font-medium px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20";
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
          <div class="bg-white dark:bg-zinc-900 p-3 rounded-lg border border-zinc-200/80 dark:border-zinc-800 space-y-1">
            <strong class="text-zinc-950 dark:text-zinc-50 text-xs font-semibold block truncate">${ex.name}</strong>
            <p class="font-mono text-[11px] text-indigo-600 dark:text-indigo-400 font-medium">${ex.sets ? ex.sets.length : 0} Set: <span class="text-zinc-600 dark:text-zinc-300">${setDetails}</span></p>
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
  div.className = "bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 p-3 rounded-xl rounded-tl-sm border border-zinc-200/80 dark:border-zinc-800 mr-6 flex items-center gap-2.5 text-[11px]";
  div.innerHTML = `
        <span class="flex gap-1">
          <span class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </span>
        <span class="font-medium text-zinc-600 dark:text-zinc-300">Garmin telemetrisi ve spor bilimi taranıyor...</span>
      `;
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
  return id;
}

function removeTypingIndicatorUI(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendMessageUI(sender, text, meta = null) {
  const c = document.getElementById('chatMessagesContainer');
  const div = document.createElement('div');
  if (sender === 'user') {
    div.className = "bg-indigo-600 text-white p-3 rounded-xl rounded-tr-sm self-end ml-6 leading-relaxed shadow-[inset_0_1px_0_0_rgba(255,255,255,0.15)]";
    div.textContent = text;
  } else {
    div.className = "bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 p-3.5 rounded-xl rounded-tl-sm border border-zinc-200/80 dark:border-zinc-800 mr-2 space-y-1.5 leading-relaxed";
    let formatted = text
      .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^• (.*?)$/gm, '<li class="ml-2.5 list-disc">$1</li>')
      .replace(/^- (.*?)$/gm, '<li class="ml-2.5 list-disc">$1</li>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');

    let metaHtml = '';
    if (meta) {
      const isReal = meta.is_real_ai;
      const badgeClass = isReal
        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'
        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700';
      const iconName = isReal ? 'zap' : 'cpu';
      metaHtml = `
<div class="pt-2 mt-2 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between font-mono text-[10px] text-zinc-400">
  <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border ${badgeClass} font-medium">
    ${lucideSvg(iconName, 'w-3 h-3')} ${meta.provider || 'Gerçek AI'}
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

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeDebriefModal();
    closeActivityModal();
    closePreferencesModal();
  }
});

['postWorkoutDebriefModal', 'activityDetailModal', 'preferencesModal'].forEach(id => {
  const modalEl = document.getElementById(id);
  if (modalEl) {
    modalEl.addEventListener('click', (e) => {
      if (e.target === modalEl) {
        if (id === 'postWorkoutDebriefModal') closeDebriefModal();
        else if (id === 'activityDetailModal') closeActivityModal();
        else if (id === 'preferencesModal') closePreferencesModal();
      }
    });
  }
});

window.addEventListener('DOMContentLoaded', initApp);
