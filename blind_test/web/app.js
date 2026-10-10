/**
 * app.js — Master Application Coordinator
 *
 * Coordinates:
 * 1. Dual-blind interaction API client (REST + Long Polling)
 * 2. Session authentication, localStorage persistence and restoration
 * 3. Reactive UI view switching and DOM synchronization
 * 4. Sliders, dynamic form handling, and error handling
 * 5. Coords and Revelation delegation
 */

(function () {
  'use strict';

  // ── Application Configuration & State ───────────────────────────────────────
  // sessionStorage is intentionally used for the active browser tab. A and B
  // may use the same browser origin, but must never share each other's token.
  // sessionStorage survives refresh while remaining isolated per tab/window.
  const STORAGE_KEY = 'blind_test_client_session';
  // The UI is served by the static server on :8080 while the Blind Test API
  // runs on :7070 of the same host. Dynamically resolve API_BASE to the current
  // host's IP/domain on port 7070 so another laptop on the LAN can connect directly.
  const API_HOST = (typeof window !== 'undefined' && window.location && window.location.hostname)
    ? window.location.hostname
    : '127.0.0.1';
  const API_BASE = `http://${API_HOST}:7070`;

  const state = {
    sessionId: null,
    participantId: null,
    label: null,
    token: null,
    currentVersion: 0,
    role: 'OBSERVER',
    sessionStatus: 'DISCONNECTED',
    projection: null,
    isPolling: false,
    pollAbortController: null,
    hasVotedContinue: false,
  };

  // ── DOM References ──────────────────────────────────────────────────────────
  const dom = {
    // Top Bar
    valSessionId: document.getElementById('val-session-id'),
    valRoundIdx: document.getElementById('val-round-idx'),
    valRole: document.getElementById('val-role'),
    valStatus: document.getElementById('val-status'),
    valVersion: document.getElementById('val-version'),
    connIndicator: document.getElementById('conn-indicator'),
    connStatusText: document.getElementById('conn-status-text'),
    btnDisconnect: document.getElementById('btn-disconnect'),

    // Notifications
    notificationBanner: document.getElementById('notification-banner'),
    notificationMsg: document.getElementById('notification-msg'),
    btnBannerClose: document.getElementById('btn-banner-close'),

    // Panels
    panelJoin: document.getElementById('panel-join'),
    panelLobby: document.getElementById('panel-lobby'),
    panelRound: document.getElementById('panel-round'),
    panelSettlement: document.getElementById('panel-settlement'),
    panelError: document.getElementById('panel-error'),

    // Panel 1: Join Form
    formJoin: document.getElementById('form-join'),
    inputSessionId: document.getElementById('input-session-id'),
    inputClientToken: document.getElementById('input-client-token'),
    btnSubmitJoin: document.getElementById('btn-submit-join'),

    // Panel 2: Lobby
    lobbyParticipantsList: document.getElementById('lobby-participants-list'),
    lobbyAcousticVal: document.getElementById('lobby-acoustic-val'),
    btnLobbyReady: document.getElementById('btn-lobby-ready'),
    btnLobbyStart: document.getElementById('btn-lobby-start'),
    lobbyWaitingHint: document.getElementById('lobby-waiting-hint'),

    // Panel 3: Round Workspace
    roundRoleBanner: document.getElementById('round-role-banner'),
    roundAcousticStatus: document.getElementById('round-acoustic-status'),
    roundMarkerStatus: document.getElementById('round-marker-status'),
    senderView: document.getElementById('sender-view'),
    receiverView: document.getElementById('receiver-view'),
    roundCompleteView: document.getElementById('round-complete-view'),
    roundCompleteMsg: document.getElementById('round-complete-msg'),
    voteStatusBar: document.getElementById('vote-status-bar'),
    btnVoteContinue: document.getElementById('btn-vote-continue'),
    btnVoteEnd: document.getElementById('btn-vote-end'),
    activeCoordsCanvas: document.getElementById('active-coords-canvas'),

    // Panel 3: Sender Form & Sliders
    formSenderInput: document.getElementById('form-sender-input'),
    senderTextInput: document.getElementById('sender-text-input'),
    senderValV: document.getElementById('sender-val-v'),
    senderValA: document.getElementById('sender-val-a'),
    senderValD: document.getElementById('sender-val-d'),
    senderValC: document.getElementById('sender-val-c'),
    dispSenderV: document.getElementById('disp-sender-v'),
    dispSenderA: document.getElementById('disp-sender-a'),
    dispSenderD: document.getElementById('disp-sender-d'),
    dispSenderC: document.getElementById('disp-sender-c'),
    btnSubmitSender: document.getElementById('btn-submit-sender'),
    senderSubmittedSummary: document.getElementById('sender-submitted-summary'),
    senderSubmittedText: document.getElementById('sender-submitted-text'),
    senderSubmittedCoords: document.getElementById('sender-submitted-coords'),

    // Panel 3: Receiver Form & Sliders
    receiverWaitingMarker: document.getElementById('receiver-waiting-marker'),
    formReceiverInput: document.getElementById('form-receiver-input'),
    receiverShiftInput: document.getElementById('receiver-shift-input'),
    receiverValV: document.getElementById('receiver-val-v'),
    receiverValA: document.getElementById('receiver-val-a'),
    receiverValD: document.getElementById('receiver-val-d'),
    receiverValC: document.getElementById('receiver-val-c'),
    dispReceiverV: document.getElementById('disp-receiver-v'),
    dispReceiverA: document.getElementById('disp-receiver-a'),
    dispReceiverD: document.getElementById('disp-receiver-d'),
    dispReceiverC: document.getElementById('disp-receiver-c'),
    receiverConfirmedCheck: document.getElementById('receiver-confirmed-check'),
    btnSubmitReceiver: document.getElementById('btn-submit-receiver'),
    receiverSubmittedSummary: document.getElementById('receiver-submitted-summary'),

    // Panel 4: Settlement
    revelationCanvas: document.getElementById('revelation-canvas'),
    metricsStatGrid: document.getElementById('metrics-stat-grid'),
    roundsAuditList: document.getElementById('rounds-audit-list'),

    // Panel 5: Error
    errorTitle: document.getElementById('error-title'),
    errorDesc: document.getElementById('error-desc'),
    errorTraceText: document.getElementById('error-trace-text'),
    btnErrorReset: document.getElementById('btn-error-reset'),
  };

  // ── HTTP API Client ─────────────────────────────────────────────────────────

  /**
   * Unified fetch wrapper with session token injection and structured error handling.
   */
  async function apiRequest(endpoint, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    if (state.token) {
      headers['X-Session-Token'] = state.token;
    }
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    const config = Object.assign({}, options, { headers });

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, config);
      const text = await res.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : {};
      } catch (e) {
        data = { raw: text };
      }

      if (!res.ok) {
        const errorInfo = data.error || {
          code: `HTTP_${res.status}`,
          message: data.message || `Server returned status ${res.status}`,
        };
        const error = new Error(errorInfo.message);
        error.code = errorInfo.code;
        error.status = res.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      if (err.name === 'AbortError') {
        throw err; // Expected during long-poll resets
      }
      throw err;
    }
  }

  // ── Session Storage Persistence ─────────────────────────────────────────────

  function saveLocalSession() {
    if (!state.sessionId || !state.participantId || !state.token) {
      sessionStorage.removeItem(STORAGE_KEY);
      return;
    }
    const sessionData = {
      sessionId: state.sessionId,
      participantId: state.participantId,
      label: state.label,
      token: state.token,
      version: state.currentVersion,
    };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessionData));
  }

  function loadLocalSession() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
  }

  function restoreJoinForm() {
    if (state.sessionId) dom.inputSessionId.value = state.sessionId;
    if (state.token) dom.inputClientToken.value = state.token;
    if (state.label) {
      const radio = document.querySelector(`input[name="join-label"][value="${state.label}"]`);
      if (radio) radio.checked = true;
    }
  }

  function clearLocalSession() {
    stopPolling();
    state.sessionId = null;
    state.participantId = null;
    state.label = null;
    state.token = null;
    state.currentVersion = 0;
    state.role = 'OBSERVER';
    state.sessionStatus = 'DISCONNECTED';
    state.projection = null;
    state.hasVotedContinue = false;
    sessionStorage.removeItem(STORAGE_KEY);
    // Remove the legacy shared key from older frontend versions.
    localStorage.removeItem(STORAGE_KEY);
    updateTopBar();
    showPanel('join');
    setOnlineStatus(false, 'OFFLINE');
    dom.btnDisconnect.style.display = 'none';
  }

  // ── Notification Banner ─────────────────────────────────────────────────────

  function showNotification(msg, type = 'error') {
    dom.notificationMsg.textContent = msg;
    dom.notificationBanner.className = `notification-banner banner-${type}`;
    dom.notificationBanner.classList.remove('hidden');
  }

  function hideNotification() {
    dom.notificationBanner.classList.add('hidden');
  }

  // ── View Switching & Top Bar Sync ───────────────────────────────────────────

  function setOnlineStatus(online, text) {
    if (online) {
      dom.connIndicator.classList.add('online');
      dom.connStatusText.textContent = text || 'ONLINE';
    } else {
      dom.connIndicator.classList.remove('online');
      dom.connStatusText.textContent = text || 'OFFLINE';
    }
  }

  function updateTopBar() {
    dom.valSessionId.textContent = state.sessionId || '--';
    const currRound = (state.projection && typeof state.projection.current_round_index === 'number')
      ? state.projection.current_round_index
      : (state.projection && state.projection.session && typeof state.projection.session.current_round_index === 'number'
          ? state.projection.session.current_round_index
          : null);
    const maxRounds = (state.projection && typeof state.projection.max_rounds === 'number')
      ? state.projection.max_rounds
      : (state.projection && state.projection.session && typeof state.projection.session.max_rounds === 'number'
          ? state.projection.session.max_rounds
          : 3);

    dom.valRoundIdx.textContent = currRound !== null ? `${currRound + 1} / ${maxRounds}` : '--';
    dom.valRole.textContent = state.role || 'OBSERVER';
    dom.valStatus.textContent = state.sessionStatus || 'DISCONNECTED';
    dom.valVersion.textContent = state.currentVersion || '0';
    if (state.sessionId && state.token) {
      dom.btnDisconnect.style.display = 'inline-block';
    } else {
      dom.btnDisconnect.style.display = 'none';
    }
  }

  function showPanel(panelName) {
    const panels = [dom.panelJoin, dom.panelLobby, dom.panelRound, dom.panelSettlement, dom.panelError];
    panels.forEach(p => {
      p.classList.add('hidden');
      p.classList.remove('active');
    });

    let target = dom.panelJoin;
    if (panelName === 'lobby') target = dom.panelLobby;
    else if (panelName === 'round') target = dom.panelRound;
    else if (panelName === 'settlement') target = dom.panelSettlement;
    else if (panelName === 'error') target = dom.panelError;

    target.classList.remove('hidden');
    target.classList.add('active');
  }

  // ── Long Polling Loop ───────────────────────────────────────────────────────

  function startPolling() {
    if (state.isPolling) return;
    state.isPolling = true;
    pollState();
  }

  function stopPolling() {
    state.isPolling = false;
    if (state.pollAbortController) {
      state.pollAbortController.abort();
      state.pollAbortController = null;
    }
  }

  async function pollState() {
    if (!state.isPolling || !state.sessionId || !state.token) return;

    state.pollAbortController = new AbortController();

    try {
      const query = new URLSearchParams({
        session_id: state.sessionId,
        participant_id: state.participantId,
        version: state.currentVersion,
      });

      const projection = await apiRequest(`/api/blind/state?${query.toString()}`, {
        signal: state.pollAbortController.signal,
      });

      setOnlineStatus(true, 'LIVE');

      // Update state authoritatively from backend projection
      handleStateProjection(projection);

      // Re-trigger immediately for next event
      if (state.isPolling) {
        setTimeout(pollState, 100);
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        // Aborted cleanly
        return;
      }

      console.warn('Polling error:', err);
      setOnlineStatus(false, 'DISCONNECTED');

      if (err.status === 401) {
        // Preserve the saved identity. Clearing localStorage here makes a
        // browser refresh look like the experiment session disappeared.
        stopPolling();
        restoreJoinForm();
        showPanel('join');
        showNotification('The saved session could not be authenticated. Verify the token and reconnect; your local session information was preserved.', 'error');
        return;
      }

      // Exponential backoff for network/transient failures
      if (state.isPolling) {
        setTimeout(pollState, 3000);
      }
    }
  }

  // ── State Projection Handler ────────────────────────────────────────────────

  function handleStateProjection(proj) {
    if (!proj) return;
    state.projection = proj;

    // Normal state projections expose status/version at the top level.
    // The final receiver submission returns the full session export, where
    // those authoritative fields live under `session`.
    const authoritativeStatus = proj.status || (proj.session && proj.session.status);
    const authoritativeVersion = typeof proj.version === 'number'
      ? proj.version
      : (proj.session && typeof proj.session.version === 'number' ? proj.session.version : null);

    // Authoritative Version and Status
    if (typeof authoritativeVersion === 'number') {
      state.currentVersion = authoritativeVersion;
    }
    state.sessionStatus = authoritativeStatus || state.sessionStatus;
    if (state.sessionStatus === 'INPUT_OPEN') {
      // A new round has been created; the local vote belongs to the
      // previous round and must not keep the next round's UI locked.
      state.hasVotedContinue = false;
    }
    if (proj.role) {
      state.role = proj.role;
    }

    updateTopBar();
    saveLocalSession();

    // Route view based on authoritative session status
    const status = state.sessionStatus;

    if (status === 'LOBBY') {
      renderLobbyView(proj);
    } else if (status === 'READY') {
      renderLobbyView(proj);
    } else if (status === 'INPUT_OPEN' || status === 'RECEIVER_RESPONSE' || status === 'ROUND_COMPLETE' || status === 'ROUND_SETTLED' || status === 'NEXT_ROUND_PENDING') {
      renderRoundView(proj);
    } else if (status === 'SETTLEMENT') {
      renderSettlementView(proj);
    } else if (status === 'ABORTED') {
      renderAbortedView(proj);
    }
  }

  // ── View Renderers ──────────────────────────────────────────────────────────

  function renderLobbyView(proj) {
    showPanel('lobby');

    // Participants list
    const parts = proj.participants || [];
    let pListHtml = '';
    let allReady = parts.length >= 2;

    parts.forEach(p => {
      const isSelf = p.participant_id === state.participantId;
      const readyClass = p.ready ? 'ready' : 'waiting';
      const readyLabel = p.ready ? 'READY' : 'WAITING';
      pListHtml += `
        <li class="participant-item">
          <div class="part-meta">
            <strong>Participant ${p.label}</strong>
            ${isSelf ? '<span class="self-tag">(You)</span>' : ''}
          </div>
          <span class="part-status ${readyClass}">${readyLabel}</span>
        </li>
      `;
      if (!p.ready) allReady = false;
    });

    dom.lobbyParticipantsList.innerHTML = pListHtml || '<li class="status-note">No participants joined yet.</li>';
    dom.lobbyAcousticVal.textContent = proj.status === 'READY' ? 'READY (440Hz Standby)' : 'STANDBY';

    // Self ready status
    const selfPart = parts.find(p => p.participant_id === state.participantId);
    if (selfPart && selfPart.ready) {
      dom.btnLobbyReady.disabled = true;
      dom.btnLobbyReady.textContent = 'Readiness Confirmed ✓';
      dom.btnLobbyReady.classList.add('btn-disabled');
    } else {
      dom.btnLobbyReady.disabled = false;
      dom.btnLobbyReady.textContent = 'Mark Ready';
      dom.btnLobbyReady.classList.remove('btn-disabled');
    }

    // Start session button: available when both participants ready
    if (allReady && parts.length >= 2) {
      dom.btnLobbyStart.style.display = 'inline-block';
      dom.lobbyWaitingHint.textContent = 'Both participants are ready. Any participant may start session.';
    } else {
      dom.btnLobbyStart.style.display = 'none';
      dom.lobbyWaitingHint.textContent = `Awaiting participants readiness (${parts.filter(p => p.ready).length}/2 ready)...`;
    }
  }

  function renderRoundView(proj) {
    showPanel('round');

    const status = proj.status;
    const role = proj.role;
    const acousticStatus = proj.acoustic_status || 'WAITING';

    dom.roundRoleBanner.textContent = `${role} TURN (${status})`;
    dom.roundAcousticStatus.textContent = acousticStatus;
    dom.roundAcousticStatus.className = `strip-val ${acousticStatus === 'ACTIVE' ? 'highlight' : ''}`;
    dom.roundMarkerStatus.textContent = (acousticStatus === 'ACTIVE' || status === 'RECEIVER_RESPONSE' || status === 'ROUND_COMPLETE' || status === 'ROUND_SETTLED') ? 'COMMITTED' : 'PENDING';

    // Sub-views
    dom.senderView.classList.add('hidden');
    dom.receiverView.classList.add('hidden');
    dom.roundCompleteView.classList.add('hidden');

    if (status === 'ROUND_COMPLETE' || status === 'ROUND_SETTLED' || status === 'NEXT_ROUND_PENDING') {
      // Round Complete view & continuation voting
      dom.roundCompleteView.classList.remove('hidden');
      renderContinuationSection(proj);
    } else if (role === 'SENDER') {
      dom.senderView.classList.remove('hidden');
      renderSenderSection(proj);
    } else if (role === 'RECEIVER') {
      dom.receiverView.classList.remove('hidden');
      renderReceiverSection(proj);
    }

    // Render 2D Active Space Canvas (Authorized public coordinates only)
    if (window.CoordsView && window.CoordsView.renderActiveCoords) {
      window.CoordsView.renderActiveCoords(dom.activeCoordsCanvas, proj);
    }
  }

  function renderSenderSection(proj) {
    const hasSubmitted = Boolean(proj.own_input);

    if (hasSubmitted) {
      // Locked submitted state
      dom.formSenderInput.classList.add('hidden');
      dom.senderSubmittedSummary.classList.remove('hidden');
      dom.senderSubmittedText.textContent = `"${proj.own_input.text}"`;

      const v = proj.own_input.input_vadc;
      dom.senderSubmittedCoords.innerHTML = `
        <span class="coord-tag">Valence: ${v.valence.toFixed(2)}</span>
        <span class="coord-tag">Arousal: ${v.arousal.toFixed(2)}</span>
        <span class="coord-tag">Dominance: ${v.dominance.toFixed(2)}</span>
        <span class="coord-tag">Confidence: ${v.confidence.toFixed(2)}</span>
      `;
    } else {
      // Active input form
      dom.formSenderInput.classList.remove('hidden');
      dom.senderSubmittedSummary.classList.add('hidden');
    }
  }

  function renderReceiverSection(proj) {
    const canRespond = Boolean(proj.can_respond);

    if (canRespond) {
      dom.receiverWaitingMarker.classList.add('hidden');
      dom.formReceiverInput.classList.remove('hidden');
    } else {
      // Still waiting for Sender transmission and OSC marker commitment
      dom.receiverWaitingMarker.classList.remove('hidden');
      dom.formReceiverInput.classList.add('hidden');
    }
  }

  function renderContinuationSection(proj) {
    if (state.hasVotedContinue) {
      dom.btnVoteContinue.disabled = true;
      dom.btnVoteContinue.textContent = 'Continuation Vote Registered ✓';
      dom.voteStatusBar.innerHTML = '<span class="status-note">Waiting for peer to confirm continuation...</span>';
    } else {
      dom.btnVoteContinue.disabled = false;
      dom.btnVoteContinue.textContent = 'Vote: Continue to Next Round';
      dom.voteStatusBar.innerHTML = '<span class="status-note">Advance to next round (roles will automatically invert).</span>';
    }
  }

  async function renderSettlementView(proj) {
    showPanel('settlement');
    stopPolling(); // No further state progression

    try {
      // Fetch full unmasked summary with X-Session-Token
      const query = new URLSearchParams({
        session_id: state.sessionId,
        participant_id: state.participantId,
      });

      const summary = await apiRequest(`/api/blind/summary?${query.toString()}`);

      // Render Trajectory on Canvas
      if (window.RevelationView && window.RevelationView.renderRevelationTrajectory) {
        window.RevelationView.renderRevelationTrajectory(dom.revelationCanvas, summary);
      }

      // Render Metrics Stat Grid
      if (window.RevelationView && window.RevelationView.renderMetricsStatGrid) {
        window.RevelationView.renderMetricsStatGrid(dom.metricsStatGrid, summary);
      }

      // Render Round Audit List
      if (window.RevelationView && window.RevelationView.renderRoundAuditList) {
        window.RevelationView.renderRoundAuditList(dom.roundsAuditList, summary);
      }
    } catch (err) {
      console.error('Failed to load settlement summary:', err);
      showNotification(`Failed to load settlement audit: ${err.message}`, 'error');
    }
  }

  function renderAbortedView(proj) {
    showPanel('error');
    stopPolling();
    dom.errorTitle.textContent = 'EXPERIMENT ABORTED';
    dom.errorDesc.textContent = 'The experiment session was aborted prematurely.';
    dom.errorTraceText.textContent = JSON.stringify(proj, null, 2);
  }

  // ── Event Handlers & Form Submissions ───────────────────────────────────────

  function setupEventHandlers() {
    // Sliders value synchronization
    const syncSlider = (slider, disp) => {
      if (!slider || !disp) return;
      slider.addEventListener('input', () => {
        disp.textContent = Number(slider.value).toFixed(2);
      });
    };

    syncSlider(dom.senderValV, dom.dispSenderV);
    syncSlider(dom.senderValA, dom.dispSenderA);
    syncSlider(dom.senderValD, dom.dispSenderD);
    syncSlider(dom.senderValC, dom.dispSenderC);

    syncSlider(dom.receiverValV, dom.dispReceiverV);
    syncSlider(dom.receiverValA, dom.dispReceiverA);
    syncSlider(dom.receiverValD, dom.dispReceiverD);
    syncSlider(dom.receiverValC, dom.dispReceiverC);

    // Notification banner close
    dom.btnBannerClose.addEventListener('click', hideNotification);

    // Disconnect / Reset
    dom.btnDisconnect.addEventListener('click', () => {
      if (confirm('Disconnect from current experiment session?')) {
        clearLocalSession();
      }
    });

    dom.btnErrorReset.addEventListener('click', clearLocalSession);

    // Join Form Submit
    dom.formJoin.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideNotification();

      const sessionId = dom.inputSessionId.value.trim();
      const clientToken = dom.inputClientToken.value.trim();
      const labelRadio = document.querySelector('input[name="join-label"]:checked');
      const label = labelRadio ? labelRadio.value : 'A';

      if (!sessionId || !clientToken) {
        showNotification('Session ID and Security Token are required.', 'error');
        return;
      }

      dom.btnSubmitJoin.disabled = true;
      dom.btnSubmitJoin.textContent = 'Connecting...';

      try {
        const res = await apiRequest('/api/blind/join', {
          method: 'POST',
          body: {
            session_id: sessionId,
            label: label,
            client_token: clientToken,
          },
        });

        state.sessionId = sessionId;
        state.participantId = res.participant.participant_id;
        state.label = label;
        state.token = clientToken;
        saveLocalSession();

        updateTopBar();
        startPolling();
      } catch (err) {
        console.error('Join error:', err);
        // A refresh or an older frontend may have lost localStorage even
        // though the participant is already registered. In that case, verify
        // the supplied token against the existing participant and reconnect
        // without attempting a second JOIN.
        if (err.code === 'JOIN_REJECTED') {
          const existingParticipantId = `p_${sessionId}_${label}`;
          state.sessionId = sessionId;
          state.participantId = existingParticipantId;
          state.label = label;
          state.token = clientToken;
          state.currentVersion = 0;
          try {
            const proj = await apiRequest(
              `/api/blind/state?${new URLSearchParams({
                session_id: sessionId,
                participant_id: existingParticipantId,
                version: 0,
              }).toString()}`
            );
            saveLocalSession();
            handleStateProjection(proj);
            startPolling();
            showNotification('Existing participant verified. Session restored.', 'success');
            return;
          } catch (restoreErr) {
            state.sessionId = null;
            state.participantId = null;
            state.label = null;
            state.token = null;
            state.currentVersion = 0;
            showNotification(`Failed to reconnect existing participant: ${restoreErr.message}`, 'error');
          }
        } else {
          showNotification(`Failed to join session: ${err.message}`, 'error');
        }
      } finally {
        dom.btnSubmitJoin.disabled = false;
        dom.btnSubmitJoin.textContent = 'Connect to Session';
      }
    });

    // Lobby Ready
    dom.btnLobbyReady.addEventListener('click', async () => {
      hideNotification();
      dom.btnLobbyReady.disabled = true;
      try {
        const proj = await apiRequest('/api/blind/ready', {
          method: 'POST',
          body: {
            session_id: state.sessionId,
            participant_id: state.participantId,
          },
        });
        handleStateProjection(proj);
      } catch (err) {
        showNotification(`Failed to signal ready: ${err.message}`, 'error');
        dom.btnLobbyReady.disabled = false;
      }
    });

    // Lobby Start Session
    dom.btnLobbyStart.addEventListener('click', async () => {
      hideNotification();
      dom.btnLobbyStart.disabled = true;
      try {
        const proj = await apiRequest('/api/blind/start', {
          method: 'POST',
          body: {
            session_id: state.sessionId,
            participant_id: state.participantId,
          },
        });
        handleStateProjection(proj);
      } catch (err) {
        showNotification(`Failed to start session: ${err.message}`, 'error');
        dom.btnLobbyStart.disabled = false;
      }
    });

    // Sender Submit Input
    dom.formSenderInput.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideNotification();

      const text = dom.senderTextInput.value.trim();
      if (!text) {
        showNotification('Somatic phenomenological text description cannot be empty.', 'error');
        return;
      }

      const inputVadc = {
        valence: parseFloat(dom.senderValV.value),
        arousal: parseFloat(dom.senderValA.value),
        dominance: parseFloat(dom.senderValD.value),
        confidence: parseFloat(dom.senderValC.value),
      };

      const idempotencyKey = `sub-inp-${state.sessionId}-r${state.projection.current_round_index}-${Date.now()}`;

      dom.btnSubmitSender.disabled = true;
      dom.btnSubmitSender.textContent = 'Synthesizing & Transmitting...';

      try {
        const proj = await apiRequest('/api/blind/submit_input', {
          method: 'POST',
          body: {
            session_id: state.sessionId,
            participant_id: state.participantId,
            client_version: state.currentVersion,
            idempotency_key: idempotencyKey,
            payload: {
              text: text,
              input_vadc: inputVadc,
              client_submission_id: `cli_${Date.now()}`,
            },
          },
        });
        handleStateProjection(proj);
      } catch (err) {
        console.error('Submit input error:', err);
        if (err.code === 'STALE_VERSION') {
          showNotification('State version mismatch. Synchronizing state, please re-submit.', 'error');
        } else if (err.code === 'ROLE_MISMATCH') {
          showNotification('Role mismatch: It is not your turn to send.', 'error');
        } else {
          showNotification(`Submission rejected: ${err.message}`, 'error');
        }
      } finally {
        dom.btnSubmitSender.disabled = false;
        dom.btnSubmitSender.textContent = 'Transmit Somatic Inscription';
      }
    });

    // Receiver Submit Response
    dom.formReceiverInput.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideNotification();

      const shiftText = dom.receiverShiftInput.value.trim();
      const listeningConfirmed = dom.receiverConfirmedCheck.checked;

      const receiverVadc = {
        valence: parseFloat(dom.receiverValV.value),
        arousal: parseFloat(dom.receiverValA.value),
        dominance: parseFloat(dom.receiverValD.value),
        confidence: parseFloat(dom.receiverValC.value),
      };

      const idempotencyKey = `sub-rec-${state.sessionId}-r${state.projection.current_round_index}-${Date.now()}`;

      dom.btnSubmitReceiver.disabled = true;
      dom.btnSubmitReceiver.textContent = 'Submitting Evaluation...';

      try {
        const proj = await apiRequest('/api/blind/submit_receiver', {
          method: 'POST',
          body: {
            session_id: state.sessionId,
            participant_id: state.participantId,
            client_version: state.currentVersion,
            idempotency_key: idempotencyKey,
            payload: {
              receiver_vadc: receiverVadc,
              somatic_shift: shiftText,
              listening_confirmed: listeningConfirmed,
            },
          },
        });
        handleStateProjection(proj);
      } catch (err) {
        console.error('Submit receiver error:', err);
        if (err.code === 'STALE_VERSION') {
          showNotification('State version mismatch. Synchronizing state, please re-submit.', 'error');
        } else if (err.code === 'ROLE_MISMATCH') {
          showNotification('Role mismatch: It is not your turn to evaluate.', 'error');
        } else {
          showNotification(`Evaluation rejected: ${err.message}`, 'error');
        }
      } finally {
        dom.btnSubmitReceiver.disabled = false;
        dom.btnSubmitReceiver.textContent = 'Submit Evaluation & Complete Round';
      }
    });

    // Continuation Vote
    dom.btnVoteContinue.addEventListener('click', async () => {
      hideNotification();
      dom.btnVoteContinue.disabled = true;
      try {
        const proj = await apiRequest('/api/blind/continue', {
          method: 'POST',
          body: {
            session_id: state.sessionId,
            participant_id: state.participantId,
          },
        });
        state.hasVotedContinue = true;
        handleStateProjection(proj);
        if (proj.status === 'INPUT_OPEN') {
          showNotification('Both participants agreed. The next round is now open.', 'success');
        } else if (proj.status === 'NEXT_ROUND_PENDING') {
          showNotification('Continuation vote registered. Waiting for the other participant.', 'success');
        }
      } catch (err) {
        showNotification(`Failed to register continuation vote: ${err.message}`, 'error');
        dom.btnVoteContinue.disabled = false;
      }
    });

    // End Session Vote
    dom.btnVoteEnd.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to end dialogue and enter final settlement?')) return;
      hideNotification();
      dom.btnVoteEnd.disabled = true;
      try {
        const proj = await apiRequest('/api/blind/end', {
          method: 'POST',
          body: {
            session_id: state.sessionId,
            participant_id: state.participantId,
          },
        });
        handleStateProjection(proj);
      } catch (err) {
        showNotification(`Failed to end session: ${err.message}`, 'error');
        dom.btnVoteEnd.disabled = false;
      }
    });
  }

  // ── Initialization ──────────────────────────────────────────────────────────

  function init() {
    setupEventHandlers();

    // Try restoring saved session from localStorage
    const saved = loadLocalSession();
    if (saved && saved.sessionId && saved.participantId && saved.token) {
      state.sessionId = saved.sessionId;
      state.participantId = saved.participantId;
      state.label = saved.label;
      state.token = saved.token;
      state.currentVersion = saved.version || 0;

      restoreJoinForm();
      updateTopBar();
      startPolling();
    } else {
      showPanel('join');
    }
  }

  // Run when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
