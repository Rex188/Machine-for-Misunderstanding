/**
 * app.js — A Machine for Misunderstanding · Web UI Controller
 * Dual-mode controller: PRESENT (generative art installation) vs ADMIN (engineering telemetry).
 * Completely English interface: text interpretation, 4D VADC slider debounce,
 * 7 modal scales, and autonomous chord progression sequencer.
 */

document.addEventListener('DOMContentLoaded', () => {
  // View Containers & Mode Switcher
  const presentView = document.getElementById('presentView');
  const adminView = document.getElementById('adminView');
  const switchBtns = document.querySelectorAll('.switch-btn');

  // Present Mode DOM
  const presentTextInput = document.getElementById('presentTextInput');
  const presentTransmuteBtn = document.getElementById('presentTransmuteBtn');
  const presentStatusHint = document.getElementById('presentStatusHint');
  const presentPresets = document.getElementById('presentPresets');

  // Admin Mode DOM
  const bodyTextInput = document.getElementById('bodyTextInput');
  const charCount = document.getElementById('charCount');
  const interpretBtn = document.getElementById('interpretBtn');
  const interpReasoning = document.getElementById('interpReasoning');
  const interpLatency = document.getElementById('interpLatency');
  const presetButtons = document.getElementById('presetButtons');
  
  // Header Indicators
  const headerBpm = document.getElementById('headerBpm');
  const headerMode = document.getElementById('headerMode');

  // VADC Sliders & Numeric Readouts
  const sliderValence = document.getElementById('sliderValence');
  const sliderArousal = document.getElementById('sliderArousal');
  const sliderDominance = document.getElementById('sliderDominance');
  const sliderConfidence = document.getElementById('sliderConfidence');

  const valValence = document.getElementById('valValence');
  const valArousal = document.getElementById('valArousal');
  const valDominance = document.getElementById('valDominance');
  const valConfidence = document.getElementById('valConfidence');

  // Eurorack 8 Channels Display & Sliders
  const cvValTimbre = document.getElementById('cvValTimbre');
  const cvDescTimbre = document.getElementById('cvDescTimbre');
  const sliderCvTimbre = document.getElementById('sliderCvTimbre');

  const cvValFrequency = document.getElementById('cvValFrequency');
  const cvDescFrequency = document.getElementById('cvDescFrequency');
  const sliderCvFrequency = document.getElementById('sliderCvFrequency');

  const cvValAmplitude = document.getElementById('cvValAmplitude');
  const sliderCvAmplitude = document.getElementById('sliderCvAmplitude');

  const cvValEnvelope = document.getElementById('cvValEnvelope');
  const sliderCvEnvelope = document.getElementById('sliderCvEnvelope');

  const cvValMode = document.getElementById('cvValMode');
  const cvDescMode = document.getElementById('cvDescMode');
  const modePills = document.querySelectorAll('.mode-pill');

  const cvValChord = document.getElementById('cvValChord');
  const cvDescChord = document.getElementById('cvDescChord');
  const selectChordDegree = document.getElementById('selectChordDegree');
  const selectChordType = document.getElementById('selectChordType');

  // Progression Sequencer DOM
  const toggleProgressionBtn = document.getElementById('toggleProgressionBtn');
  const progSpeedSelect = document.getElementById('progSpeedSelect');
  const progressionTrack = document.getElementById('progressionTrack');

  const cvValNoise = document.getElementById('cvValNoise');
  const sliderCvNoise = document.getElementById('sliderCvNoise');

  const historyList = document.getElementById('historyList');

  // Live Audio Capture Controls & Device Selectors
  const presentAudioBtn = document.getElementById('presentAudioBtn');
  const adminAudioBtn = document.getElementById('adminAudioBtn');
  const presentAudioDeviceSelect = document.getElementById('presentAudioDeviceSelect');
  const adminAudioDeviceSelect = document.getElementById('adminAudioDeviceSelect');

  async function populateAudioDevices() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter(d => d.kind === 'audioinput');
      if (audioInputs.length === 0) return;

      [presentAudioDeviceSelect, adminAudioDeviceSelect].forEach(select => {
        if (!select) return;
        const curVal = select.value;
        select.innerHTML = '';
        audioInputs.forEach((d, idx) => {
          const opt = document.createElement('option');
          opt.value = d.deviceId;
          opt.textContent = d.label || `Audio Input ${idx + 1}`;
          select.appendChild(opt);
        });
        if (curVal && Array.from(select.options).some(o => o.value === curVal)) {
          select.value = curVal;
        }
      });
    } catch (e) {
      console.warn('Could not enumerate audio devices:', e);
    }
  }

  async function handleAudioToggle() {
    if (window.AUDIO_ENGINE) {
      const select = presentView.classList.contains('active') ? presentAudioDeviceSelect : adminAudioDeviceSelect;
      const deviceId = select ? select.value : 'default';
      const active = await window.AUDIO_ENGINE.toggle(deviceId);
      updateAudioButtons(active);
      if (active) {
        await populateAudioDevices();
      }
    }
  }

  function updateAudioButtons(active) {
    [presentAudioBtn, adminAudioBtn].forEach(btn => {
      if (btn) {
        btn.classList.toggle('active', active);
        const label = btn.querySelector('.audio-label');
        if (label) {
          label.textContent = active ? 'LIVE AUDIO: ON' : 'LIVE AUDIO: OFF';
        }
      }
    });
  }

  if (presentAudioBtn) presentAudioBtn.addEventListener('click', handleAudioToggle);
  if (adminAudioBtn) adminAudioBtn.addEventListener('click', handleAudioToggle);

  [presentAudioDeviceSelect, adminAudioDeviceSelect].forEach(sel => {
    if (sel) {
      sel.addEventListener('change', async (e) => {
        const newId = e.target.value;
        [presentAudioDeviceSelect, adminAudioDeviceSelect].forEach(s => {
          if (s && s !== e.target) s.value = newId;
        });
        if (window.AUDIO_ENGINE && window.AUDIO_ENGINE.active) {
          window.AUDIO_ENGINE.stop();
          const active = await window.AUDIO_ENGINE.start(newId);
          updateAudioButtons(active);
        }
      });
    }
  });

  // Try populating device labels on startup
  populateAudioDevices();

  let presetsCache = {};
  let debounceVadcTimer = null;
  let currentProgressionEnabled = true;

  // ========================================================
  // 1. Dual-Mode Switching (PRESENT ↔ ADMIN)
  // ========================================================
  switchBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target; // 'present' or 'admin'
      if (target === 'present') {
        presentView.classList.add('active');
        adminView.classList.remove('active');
        setTimeout(() => {
          window.dispatchEvent(new Event('resize'));
        }, 50);
      } else {
        adminView.classList.add('active');
        presentView.classList.remove('active');
      }
      switchBtns.forEach(b => {
        b.classList.toggle('active', b.dataset.target === target);
      });
    });
  });

  // ========================================================
  // 2. Initialization & Preset Synchronization
  // ========================================================
  async function loadPresets() {
    try {
      const res = await fetch('/api/presets');
      const data = await res.json();
      if (data.presets) {
        data.presets.forEach(p => {
          presetsCache[p.id] = p;
        });
        selectPreset('1');
      }
    } catch (e) {
      console.warn('Failed to load presets:', e);
    }
  }

  function selectPreset(id) {
    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.id === id);
    });
    document.querySelectorAll('.present-preset-chip').forEach(chip => {
      chip.classList.toggle('active', chip.dataset.id === id);
    });

    if (id === 'custom') {
      bodyTextInput.value = '';
      if (presentTextInput) {
        presentTextInput.value = '';
        presentTextInput.focus();
      }
    } else if (presetsCache[id]) {
      const txt = presetsCache[id].text;
      bodyTextInput.value = txt;
      if (presentTextInput) presentTextInput.value = txt;
    }
    updateCharCount();
  }

  presetButtons.addEventListener('click', (e) => {
    const btn = e.target.closest('.preset-btn');
    if (btn) selectPreset(btn.dataset.id);
  });

  if (presentPresets) {
    presentPresets.addEventListener('click', (e) => {
      const chip = e.target.closest('.present-preset-chip');
      if (chip) selectPreset(chip.dataset.id);
    });
  }

  function updateCharCount() {
    charCount.textContent = `${bodyTextInput.value.length} chars`;
  }

  bodyTextInput.addEventListener('input', () => {
    if (presentTextInput) presentTextInput.value = bodyTextInput.value;
    updateCharCount();
  });
  if (presentTextInput) {
    presentTextInput.addEventListener('input', () => {
      bodyTextInput.value = presentTextInput.value;
      updateCharCount();
    });
  }

  // Floating Side Dock Minimize / Restore Handlers
  const presentDock = document.getElementById('presentDock');
  const dockMinimizeBtn = document.getElementById('dockMinimizeBtn');
  const dockRestoreBtn = document.getElementById('dockRestoreBtn');

  if (dockMinimizeBtn && presentDock && dockRestoreBtn) {
    dockMinimizeBtn.addEventListener('click', () => {
      presentDock.classList.add('minimized');
      dockRestoreBtn.style.display = 'flex';
    });

    dockRestoreBtn.addEventListener('click', () => {
      presentDock.classList.remove('minimized');
      dockRestoreBtn.style.display = 'none';
      if (presentTextInput) presentTextInput.focus();
    });
  }

  // ========================================================
  // 3. Unified Transmute Pipeline
  // ========================================================
  async function executeInterpretation() {
    const text = (presentTextInput && presentView.classList.contains('active'))
      ? presentTextInput.value.trim()
      : bodyTextInput.value.trim();

    if (!text) {
      alert('Please enter a somatic description or choose a literature excerpt!');
      return;
    }

    const activeBtn = document.querySelector('.preset-btn.active') || document.querySelector('.present-preset-chip.active');
    const title = activeBtn && activeBtn.dataset.id !== 'custom' 
      ? activeBtn.textContent.trim() 
      : 'Custom Somatic Perception';

    interpretBtn.classList.add('loading');
    interpretBtn.querySelector('.btn-text').textContent = 'Translating via Blackbox...';
    if (presentTransmuteBtn) {
      presentTransmuteBtn.classList.add('loading');
      presentTransmuteBtn.querySelector('.btn-primary-text').textContent = 'TRANSMUTING...';
      presentTransmuteBtn.querySelector('.btn-sub-text').textContent = 'RESONATING';
    }
    if (presentStatusHint) {
      presentStatusHint.textContent = 'Blackbox analyzing · Mapping somatic physiology to 4D VADC space...';
    }

    const startTime = performance.now();

    try {
      const res = await fetch('/api/interpret', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, title }),
      });
      const data = await res.json();

      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      interpLatency.textContent = `Latency: ${elapsed}s`;

      if (data.status === 'success') {
        applyState(data.vadc, data.voltages, data);
        loadHistory();
        if (presentStatusHint) {
          const modeName = data.voltages && data.voltages.mode_desc ? data.voltages.mode_desc.split('(')[0].trim() : 'Modal';
          presentStatusHint.textContent = `Acoustic topology reconstructed · Mode: ${modeName} · 10s progression active`;
        }
      } else {
        alert('Translation failed: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      alert('Network request error: ' + e.message);
    } finally {
      interpretBtn.classList.remove('loading');
      interpretBtn.querySelector('.btn-text').textContent = 'Translate & Drive VCV Rack';
      if (presentTransmuteBtn) {
        presentTransmuteBtn.classList.remove('loading');
        presentTransmuteBtn.querySelector('.btn-primary-text').textContent = 'TRANSMUTE';
        presentTransmuteBtn.querySelector('.btn-sub-text').textContent = 'RESONATE';
      }
    }
  }

  interpretBtn.addEventListener('click', executeInterpretation);
  if (presentTransmuteBtn) {
    presentTransmuteBtn.addEventListener('click', executeInterpretation);
  }

  // ========================================================
  // 4. State Application & Real-time Canvas Sync (applyState)
  // ========================================================
  function applyState(vadc, voltages, serverState) {
    if (!vadc || !voltages) return;

    window.RACK_STATE = Object.assign({}, serverState || {}, { vadc, voltages });

    if (vadc.reasoning) {
      interpReasoning.textContent = vadc.reasoning;
    }

    // VADC Sliders
    sliderValence.value = vadc.valence;
    valValence.textContent = Number(vadc.valence).toFixed(2);

    sliderArousal.value = vadc.arousal;
    valArousal.textContent = Number(vadc.arousal).toFixed(2);

    sliderDominance.value = vadc.dominance;
    valDominance.textContent = Number(vadc.dominance).toFixed(2);

    sliderConfidence.value = vadc.confidence;
    valConfidence.textContent = Number(vadc.confidence).toFixed(2);

    // CH 1: Timbre
    cvValTimbre.textContent = `${Number(voltages.timbre_v).toFixed(2)} V`;
    sliderCvTimbre.value = voltages.timbre_v;
    if (voltages.timbre_v >= 2.0) {
      cvDescTimbre.textContent = 'Model 6 (Extreme Harsh Chord Aggression)';
    } else if (voltages.timbre_v >= 1.0) {
      cvDescTimbre.textContent = 'Model 4 (Harmonic Additive Warm Pad)';
    } else if (voltages.timbre_v >= 0.5) {
      cvDescTimbre.textContent = 'Model 2 (FM Metallic Shiver)';
    } else {
      cvDescTimbre.textContent = 'Model 0 (Pure Sine Baseline)';
    }

    // CH 2: Frequency
    cvValFrequency.textContent = `${voltages.frequency_v >= 0 ? '+' : ''}${Number(voltages.frequency_v).toFixed(2)} V`;
    sliderCvFrequency.value = voltages.frequency_v;
    const bpm = voltages.bpm_estimated || Math.round(50 + 170 * ((voltages.frequency_v + 3) / 7));
    cvDescFrequency.textContent = `${bpm} BPM (Dense Rhythmic Pulse)`;
    headerBpm.textContent = bpm;

    // CH 3: Amplitude
    cvValAmplitude.textContent = `${Number(voltages.amplitude_v).toFixed(2)} V`;
    sliderCvAmplitude.value = voltages.amplitude_v;

    // CH 4: Envelope
    cvValEnvelope.textContent = `${voltages.envelope_v >= 0 ? '+' : ''}${Number(voltages.envelope_v).toFixed(2)} V`;
    sliderCvEnvelope.value = voltages.envelope_v;

    // CH 5: Mode (7 Modal Scales)
    cvValMode.textContent = `${voltages.mode_v >= 0 ? '+' : ''}${Number(voltages.mode_v).toFixed(2)} V`;
    cvDescMode.textContent = voltages.mode_desc || 'Current Mode';
    headerMode.textContent = voltages.mode_desc ? voltages.mode_desc.split('(')[0] : 'Ionian';
    modePills.forEach(pill => {
      pill.classList.toggle('active', Number(pill.dataset.v) === Number(voltages.mode_v));
    });

    // CH 6 & 7: Chord & Type
    selectChordDegree.value = Math.round(voltages.chord_v);
    selectChordType.value = Math.round(voltages.type_v);
    const chordDescStr = `${voltages.chord_desc || 'Chord'} · ${voltages.type_desc || 'Type'}`;
    cvValChord.textContent = chordDescStr.split('·')[0];
    cvDescChord.textContent = chordDescStr;

    // Render 4-step Autonomous Progression Track
    const progression = voltages.progression || [];
    const activeStep = serverState ? (serverState.progression_step || 0) : 0;
    if (serverState && typeof serverState.progression_enabled === 'boolean') {
      currentProgressionEnabled = serverState.progression_enabled;
      toggleProgressionBtn.classList.toggle('active', currentProgressionEnabled);
      toggleProgressionBtn.textContent = currentProgressionEnabled ? '⏸ Auto-Progressing' : '▶ Progression Paused';
    }
    if (serverState && serverState.progression_interval) {
      progSpeedSelect.value = String(serverState.progression_interval);
    }

    if (progressionTrack && progression.length > 0) {
      progressionTrack.innerHTML = '';
      progression.forEach((ch, idx) => {
        const capsule = document.createElement('div');
        capsule.className = `prog-step-capsule ${idx === activeStep ? 'active' : ''}`;
        capsule.dataset.step = idx;
        capsule.innerHTML = `
          <span class="step-idx">STEP ${idx + 1}</span>
          <span class="step-name">${ch.name.split('·')[0]}</span>
        `;
        progressionTrack.appendChild(capsule);
      });
    }

    // CH 8: Noise
    cvValNoise.textContent = `${Number(voltages.noise_v).toFixed(2)} V`;
    sliderCvNoise.value = voltages.noise_v;
  }

  // 4D VADC Slider Modulation (Debounced)
  function handleVadcSliderChange() {
    valValence.textContent = Number(sliderValence.value).toFixed(2);
    valArousal.textContent = Number(sliderArousal.value).toFixed(2);
    valDominance.textContent = Number(sliderDominance.value).toFixed(2);
    valConfidence.textContent = Number(sliderConfidence.value).toFixed(2);

    clearTimeout(debounceVadcTimer);
    debounceVadcTimer = setTimeout(async () => {
      const vadc = {
        valence: parseFloat(sliderValence.value),
        arousal: parseFloat(sliderArousal.value),
        dominance: parseFloat(sliderDominance.value),
        confidence: parseFloat(sliderConfidence.value),
        reasoning: 'Manual real-time parameter modulation.',
      };
      try {
        const res = await fetch('/api/send_vadc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vadc }),
        });
        const data = await res.json();
        if (data.status === 'success') {
          applyState(data.vadc, data.voltages, data);
        }
      } catch (e) {
        console.error('Failed to sync VADC:', e);
      }
    }, 40);
  }

  [sliderValence, sliderArousal, sliderDominance, sliderConfidence].forEach(s => {
    s.addEventListener('input', handleVadcSliderChange);
  });

  // Direct Channel Control
  async function sendDirectCv(param, value) {
    try {
      await fetch('/api/send_cv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ param, value }),
      });
    } catch (e) {
      console.error('Failed to send direct CV:', e);
    }
  }

  sliderCvTimbre.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    cvValTimbre.textContent = `${val.toFixed(2)} V`;
    if (window.RACK_STATE && window.RACK_STATE.voltages) {
      window.RACK_STATE.voltages.timbre_v = val;
    }
    sendDirectCv('/param/timbre', val);
  });

  sliderCvFrequency.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    cvValFrequency.textContent = `${val >= 0 ? '+' : ''}${val.toFixed(2)} V`;
    const bpm = Math.round(50 + 170 * ((val + 3) / 7));
    cvDescFrequency.textContent = `${bpm} BPM (Dense Rhythmic Pulse)`;
    headerBpm.textContent = bpm;
    if (window.RACK_STATE && window.RACK_STATE.voltages) {
      window.RACK_STATE.voltages.frequency_v = val;
    }
    sendDirectCv('/param/frequency', val);
  });

  sliderCvAmplitude.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    cvValAmplitude.textContent = `${val.toFixed(2)} V`;
    if (window.RACK_STATE && window.RACK_STATE.voltages) {
      window.RACK_STATE.voltages.amplitude_v = val;
    }
    sendDirectCv('/param/amplitude', val);
  });

  sliderCvEnvelope.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    cvValEnvelope.textContent = `${val >= 0 ? '+' : ''}${val.toFixed(2)} V`;
    if (window.RACK_STATE && window.RACK_STATE.voltages) {
      window.RACK_STATE.voltages.envelope_v = val;
    }
    sendDirectCv('/param/envelope', val);
  });

  // Mode Selection
  modePills.forEach(pill => {
    pill.addEventListener('click', async (e) => {
      const mode_v = parseFloat(e.currentTarget.dataset.v);
      modePills.forEach(p => p.classList.remove('active'));
      e.currentTarget.classList.add('active');
      try {
        const res = await fetch('/api/set_mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode_v }),
        });
        const data = await res.json();
        if (data.status === 'success' && data.state) {
          applyState(data.state.vadc, data.state.voltages, data.state);
        }
      } catch (err) {
        console.error('Failed to set mode:', err);
      }
    });
  });

  // Progression Controls
  toggleProgressionBtn.addEventListener('click', async () => {
    currentProgressionEnabled = !currentProgressionEnabled;
    toggleProgressionBtn.classList.toggle('active', currentProgressionEnabled);
    toggleProgressionBtn.textContent = currentProgressionEnabled ? '⏸ Auto-Progressing' : '▶ Progression Paused';
    try {
      await fetch('/api/set_progression', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: currentProgressionEnabled }),
      });
    } catch (e) {
      console.error('Failed to toggle progression:', e);
    }
  });

  progSpeedSelect.addEventListener('change', async (e) => {
    const interval = parseFloat(e.target.value);
    try {
      await fetch('/api/set_progression', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval }),
      });
    } catch (e) {
      console.error('Failed to change progression speed:', e);
    }
  });

  progressionTrack.addEventListener('click', async (e) => {
    const capsule = e.target.closest('.prog-step-capsule');
    if (capsule) {
      const step = parseInt(capsule.dataset.step);
      try {
        const res = await fetch('/api/set_progression', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ step }),
        });
        const data = await res.json();
        if (data.status === 'success' && data.state) {
          applyState(data.state.vadc, data.state.voltages, data.state);
        }
      } catch (err) {
        console.error('Failed to jump to chord step:', err);
      }
    }
  });

  selectChordDegree.addEventListener('change', (e) => {
    const val = parseFloat(e.target.value);
    sendDirectCv('/param/chord', val);
  });

  selectChordType.addEventListener('change', (e) => {
    const val = parseFloat(e.target.value);
    sendDirectCv('/param/type', val);
  });

  sliderCvNoise.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    cvValNoise.textContent = `${val.toFixed(2)} V`;
    sendDirectCv('/param/noise', val);
  });

  // History Log
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      if (data.history && data.history.length > 0) {
        historyList.innerHTML = '';
        data.history.forEach(item => {
          const div = document.createElement('div');
          div.className = 'history-item';
          const timeStr = item.timestamp ? item.timestamp.split('T')[1].split('.')[0] : '';
          const vad = item.vad || {};
          const v = item.voltages || {};
          div.innerHTML = `
            <div class="history-item-head">
              <span class="history-title">${item.title || 'Custom Input'}</span>
              <span class="history-time">${timeStr}</span>
            </div>
            <div class="history-snippet">${item.text || ''}</div>
            <div class="history-meta">
              <span>V:${vad.valence || '-'} A:${vad.arousal || '-'} D:${vad.dominance || '-'}</span>
              <span>Mode: ${v.mode_desc ? v.mode_desc.split('(')[0] : '-'}</span>
              <span>Chord: ${v.chord_desc ? v.chord_desc.split('(')[0] : '-'}</span>
            </div>
          `;
          historyList.appendChild(div);
        });
      } else {
        historyList.innerHTML = '<div class="history-loading">No translation history recorded yet.</div>';
      }
    } catch (e) {
      console.warn('Failed to load history:', e);
    }
  }

  async function syncServerState() {
    try {
      const res = await fetch('/api/state');
      const data = await res.json();
      applyState(data.vadc, data.voltages, data);
    } catch (e) {
      // Ignore transient network hiccups
    }
  }

  loadPresets();
  syncServerState();
  loadHistory();

  setInterval(syncServerState, 1000);
});
