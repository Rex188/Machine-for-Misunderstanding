/**
 * revelation.js — Final Settlement & Multi-Round Unmasked Trajectory Visualizer
 *
 * Exclusively active when session enters SETTLEMENT (or ABORTED) status.
 * Visualizes:
 * 1. Multi-Round Affective Trajectory Canvas (Input -> Model -> Receiver per round)
 * 2. Cumulative Misunderstanding Metrics Stat Grid
 * 3. Exhaustive Round-by-Round Audit Cards with unmasked text, model VAD, receiver response, and voltage telemetry.
 */

(function () {
  'use strict';

  /**
   * Render Multi-Round Trajectory on the settlement canvas.
   * Connects Sender Input (cyan) -> Model (purple) -> Receiver (amber)
   * for each round with arrows/lines and labeled round markers.
   *
   * @param {HTMLCanvasElement} canvas
   * @param {Object} fullSummary - Full session dump from /api/blind/summary
   */
  function renderRevelationTrajectory(canvas, fullSummary) {
    if (!canvas || !fullSummary) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const displayWidth = canvas.clientWidth || 560;
    const displayHeight = canvas.clientHeight || 340;

    if (canvas.width !== displayWidth * dpr || canvas.height !== displayHeight * dpr) {
      canvas.width = displayWidth * dpr;
      canvas.height = displayHeight * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);

    const width = displayWidth;
    const height = displayHeight;

    // Background
    ctx.fillStyle = '#090a0f';
    ctx.fillRect(0, 0, width, height);

    // Margins
    const padX = 45;
    const padY = 35;
    const plotW = width - padX * 2;
    const plotH = height - padY * 2;

    function mapX(v) {
      return padX + Math.max(0, Math.min(1, v)) * plotW;
    }
    function mapY(a) {
      return padY + (1 - Math.max(0, Math.min(1, a))) * plotH;
    }

    // Grid Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    [0.25, 0.75].forEach(val => {
      ctx.beginPath();
      ctx.moveTo(mapX(val), padY);
      ctx.lineTo(mapX(val), padY + plotH);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(padX, mapY(val));
      ctx.lineTo(padX + plotW, mapY(val));
      ctx.stroke();
    });

    // Crosshairs
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(mapX(0.5), padY);
    ctx.lineTo(mapX(0.5), padY + plotH);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(padX, mapY(0.5));
    ctx.lineTo(padX + plotW, mapY(0.5));
    ctx.stroke();
    ctx.setLineDash([]);

    // Plot Border
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.strokeRect(padX, padY, plotW, plotH);

    // Labels
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.textAlign = 'center';
    ctx.fillText('0.0 Aversion', mapX(0.0), height - 10);
    ctx.fillText('0.5 Neutral', mapX(0.5), height - 10);
    ctx.fillText('1.0 Pleasure', mapX(1.0), height - 10);
    ctx.fillText('VALENCE →', mapX(0.5), padY - 14);

    ctx.textAlign = 'right';
    ctx.fillText('1.0 Hyperactive', padX - 8, mapY(1.0) + 3);
    ctx.fillText('0.5', padX - 8, mapY(0.5) + 3);
    ctx.fillText('0.0 Lethargic', padX - 8, mapY(0.0) + 3);

    // Extract rounds from summary
    const rounds = fullSummary.rounds || [];
    const inputEvents = fullSummary.input_events || [];
    const modelInferences = fullSummary.model_runs || fullSummary.model_inferences || [];
    const receiverResponses = fullSummary.receiver_responses || [];

    // Color definitions
    const COLOR_INPUT = '#00f2fe';
    const COLOR_MODEL = '#a855f7';
    const COLOR_RECEIVER = '#f59e0b';

    // Round stroke styles
    const roundStrokeStyles = [
      'rgba(0, 242, 254, 0.7)',
      'rgba(244, 114, 182, 0.7)',
      'rgba(52, 211, 153, 0.7)',
    ];

    rounds.forEach((rnd, idx) => {
      const inp = inputEvents.find(e =>
        (rnd.input_event_id && (e.event_id === rnd.input_event_id || e.input_event_id === rnd.input_event_id)) ||
        (e.round_id && e.round_id === rnd.round_id)
      );
      const mod = modelInferences.find(m =>
        (rnd.model_run_id && m.model_run_id === rnd.model_run_id) ||
        (rnd.model_inference_id && m.inference_id === rnd.model_inference_id) ||
        (m.round_id && m.round_id === rnd.round_id)
      );
      const rec = receiverResponses.find(r =>
        (rnd.receiver_response_id && (r.receiver_response_id === rnd.receiver_response_id || r.response_id === rnd.receiver_response_id)) ||
        (r.round_id && r.round_id === rnd.round_id)
      );

      const pInput = (inp && inp.input_vadc) ? inp.input_vadc : null;
      const pModel = (mod && (mod.output || mod.model_vadc)) ? (mod.output || mod.model_vadc) : null;
      const pRec = (rec && rec.receiver_vadc) ? rec.receiver_vadc : null;

      const strokeColor = roundStrokeStyles[idx % roundStrokeStyles.length];

      // Draw Path Input -> Model -> Receiver
      const points = [];
      if (pInput) points.push({ x: mapX(pInput.valence), y: mapY(pInput.arousal), type: 'input', data: pInput });
      if (pModel) points.push({ x: mapX(pModel.valence), y: mapY(pModel.arousal), type: 'model', data: pModel });
      if (pRec) points.push({ x: mapX(pRec.valence), y: mapY(pRec.arousal), type: 'receiver', data: pRec });

      if (points.length > 1) {
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
          ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Draw Nodes
      points.forEach(pt => {
        let color = COLOR_INPUT;
        let label = 'I';
        if (pt.type === 'model') {
          color = COLOR_MODEL;
          label = 'M';
        } else if (pt.type === 'receiver') {
          color = COLOR_RECEIVER;
          label = 'R';
        }

        // Glow
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = color.replace(')', ', 0.25)').replace('rgb', 'rgba').replace('#00f2fe', 'rgba(0, 242, 254, 0.25)').replace('#a855f7', 'rgba(168, 85, 247, 0.25)').replace('#f59e0b', 'rgba(245, 158, 11, 0.25)');
        ctx.fill();

        // Node Circle
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Node Tag
        ctx.font = '8px "JetBrains Mono", monospace';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        ctx.fillText(`R${rnd.round_index + 1}:${label}`, pt.x + 8, pt.y - 4);
      });
    });

    ctx.restore();
  }

  /**
   * Render Cumulative Metrics Stat Grid.
   * Displays primary scientific indicators of affective misunderstanding.
   *
   * @param {HTMLElement} container
   * @param {Object} fullSummary
   */
  function renderMetricsStatGrid(container, fullSummary) {
    if (!container || !fullSummary) return;

    const metricsList = fullSummary.metrics || [];
    if (metricsList.length === 0) {
      container.innerHTML = '<div class="stat-card"><span class="stat-title">NO METRICS</span><span class="stat-num">--</span></div>';
      return;
    }

    // Compute averages across rounds
    let sumRawTotal = 0;
    let sumConfAdjusted = 0;
    let sumModelDist = 0;
    let sumMediumDist = 0;
    let count = 0;
    let lastDrift = null;

    metricsList.forEach(m => {
      const raw = m.raw_distance || {};
      const adjusted = m.confidence_adjusted_distance || {};
      const rawTotal = typeof m.raw_total_distance === 'number' ? m.raw_total_distance : raw.total;
      const adjustedTotal = typeof m.confidence_adjusted_total_distance === 'number'
        ? m.confidence_adjusted_total_distance : adjusted.total;
      const modelDist = typeof m.raw_model_distance === 'number' ? m.raw_model_distance : raw.model;
      const mediumDist = typeof m.raw_medium_distance === 'number' ? m.raw_medium_distance : raw.medium;

      if (typeof rawTotal === 'number') {
        sumRawTotal += rawTotal;
        sumConfAdjusted += (typeof adjustedTotal === 'number' ? adjustedTotal : rawTotal);
        sumModelDist += (typeof modelDist === 'number' ? modelDist : 0);
        sumMediumDist += (typeof mediumDist === 'number' ? mediumDist : 0);
        count++;
      }
      if (typeof m.inter_round_drift === 'number') {
        lastDrift = m.inter_round_drift;
      }
    });

    const avgRawTotal = count > 0 ? (sumRawTotal / count) : 0;
    const avgConf = count > 0 ? (sumConfAdjusted / count) : 0;
    const avgModel = count > 0 ? (sumModelDist / count) : 0;
    const avgMedium = count > 0 ? (sumMediumDist / count) : 0;

    container.innerHTML = `
      <div class="stat-card">
        <span class="stat-title">MEAN MISUNDERSTANDING (TOTAL)</span>
        <span class="stat-num">${avgRawTotal.toFixed(3)}</span>
        <span class="stat-desc">Euclidean unit cube distance (Input ↔ Receiver)</span>
      </div>
      <div class="stat-card">
        <span class="stat-title">CONFIDENCE ADJUSTED MISUNDERSTANDING</span>
        <span class="stat-num highlight">${avgConf.toFixed(3)}</span>
        <span class="stat-desc">Modulated by Sender/Receiver certainty factor</span>
      </div>
      <div class="stat-card">
        <span class="stat-title">MODEL TRANSLATION GAP (MACHINE)</span>
        <span class="stat-num">${avgModel.toFixed(3)}</span>
        <span class="stat-desc">Input intent vs LLM acoustic parameterization</span>
      </div>
      <div class="stat-card">
        <span class="stat-title">ACOUSTIC MEDIUM GAP (PERCEPTION)</span>
        <span class="stat-num">${avgMedium.toFixed(3)}</span>
        <span class="stat-desc">LLM parameterization vs Listener somatic intake</span>
      </div>
      <div class="stat-card">
        <span class="stat-title">INTER-ROUND SOMATIC DRIFT</span>
        <span class="stat-num">${lastDrift !== null ? lastDrift.toFixed(3) : 'N/A'}</span>
        <span class="stat-desc">Drift across conversational conversational handoffs</span>
      </div>
      <div class="stat-card">
        <span class="stat-title">TOTAL COMPLETED ROUNDS</span>
        <span class="stat-num">${count} / ${fullSummary.session ? fullSummary.session.max_rounds : 3}</span>
        <span class="stat-desc">Frozen deterministic evaluation cycles</span>
      </div>
    `;
  }

  /**
   * Render Unmasked Round-by-Round Audit Cards.
   * Completely reveals sender text, model output, receiver assessment, and metrics.
   *
   * @param {HTMLElement} container
   * @param {Object} fullSummary
   */
  function renderRoundAuditList(container, fullSummary) {
    if (!container || !fullSummary) return;

    const rounds = fullSummary.rounds || [];
    const inputEvents = fullSummary.input_events || [];
    const modelInferences = fullSummary.model_runs || fullSummary.model_inferences || [];
    const acousticMarkers = fullSummary.markers || fullSummary.acoustic_markers || [];
    const receiverResponses = fullSummary.receiver_responses || [];
    const metricsList = fullSummary.metrics || [];
    const participants = fullSummary.participants || [];

    if (rounds.length === 0) {
      container.innerHTML = '<p class="status-note">No round interactions recorded.</p>';
      return;
    }

    let html = '';

    rounds.forEach((rnd, idx) => {
      const inp = inputEvents.find(e =>
        (rnd.input_event_id && (e.event_id === rnd.input_event_id || e.input_event_id === rnd.input_event_id)) ||
        (e.round_id && e.round_id === rnd.round_id)
      );
      const mod = modelInferences.find(m =>
        (rnd.model_run_id && m.model_run_id === rnd.model_run_id) ||
        (rnd.model_inference_id && m.inference_id === rnd.model_inference_id) ||
        (m.round_id && m.round_id === rnd.round_id)
      );
      const mark = acousticMarkers.find(m =>
        (rnd.marker_id && m.marker_id === rnd.marker_id) ||
        (m.round_id && m.round_id === rnd.round_id)
      );
      const rec = receiverResponses.find(r =>
        (rnd.receiver_response_id && (r.receiver_response_id === rnd.receiver_response_id || r.response_id === rnd.receiver_response_id)) ||
        (r.round_id && r.round_id === rnd.round_id)
      );
      const met = metricsList.find(m => m.round_id === rnd.round_id);

      const senderPart = participants.find(p => p.participant_id === rnd.sender_id);
      const receiverPart = participants.find(p => p.participant_id === rnd.receiver_id);

      const senderLabel = senderPart ? `Participant ${senderPart.label}` : rnd.sender_id;
      const receiverLabel = receiverPart ? `Participant ${receiverPart.label}` : rnd.receiver_id;

      const inpVadc = inp && inp.input_vadc ? inp.input_vadc : { valence: 0, arousal: 0, dominance: 0, confidence: 0 };
      const modVadc = mod && (mod.output || mod.model_vadc) ? (mod.output || mod.model_vadc) : { valence: 0, arousal: 0, dominance: 0, confidence: 0 };
      const recVadc = rec && rec.receiver_vadc ? rec.receiver_vadc : { valence: 0, arousal: 0, dominance: 0, confidence: 0 };

      html += `
        <article class="audit-card">
          <div class="audit-card-header">
            <h4>Round ${rnd.round_index + 1} Audit</h4>
            <div class="audit-roles">
              <span class="role-badge sender-badge">Sender: ${senderLabel}</span>
              <span class="role-badge-arrow">→</span>
              <span class="role-badge receiver-badge">Receiver: ${receiverLabel}</span>
            </div>
          </div>

          <div class="audit-body-grid">
            <!-- Col 1: Sender Inscription -->
            <div class="audit-section">
              <h5>1. Sender Somatic Inscription</h5>
              <blockquote class="audit-quote">"${inp ? escapeHtml(inp.text) : 'N/A'}"</blockquote>
              <div class="audit-vadc-tags">
                <span class="vadc-pill">V: ${inpVadc.valence.toFixed(2)}</span>
                <span class="vadc-pill">A: ${inpVadc.arousal.toFixed(2)}</span>
                <span class="vadc-pill">D: ${inpVadc.dominance.toFixed(2)}</span>
                <span class="vadc-pill">C: ${inpVadc.confidence.toFixed(2)}</span>
              </div>
            </div>

            <!-- Col 2: Machine Interpretation & Synthesis -->
            <div class="audit-section">
              <h5>2. Model Interpretation (Unmasked)</h5>
              <div class="audit-vadc-tags">
                <span class="vadc-pill model-pill">V: ${modVadc.valence.toFixed(2)}</span>
                <span class="vadc-pill model-pill">A: ${modVadc.arousal.toFixed(2)}</span>
                <span class="vadc-pill model-pill">D: ${modVadc.dominance.toFixed(2)}</span>
                <span class="vadc-pill model-pill">C: ${modVadc.confidence.toFixed(2)}</span>
              </div>
              ${mod && mod.raw_output ? `
                <details class="audit-raw-details">
                  <summary>Raw Model Generation & Reasoning</summary>
                  <pre class="audit-raw-text">${escapeHtml(mod.raw_output)}</pre>
                </details>
              ` : ''}
              ${(() => {
                const vMap = (mark && mark.acoustic_state && mark.acoustic_state.voltages) || (mark && mark.voltages);
                if (!vMap) return '';
                return `
                <div class="voltage-strip">
                  <span class="strip-label">8-CH OSC Voltages:</span>
                  <code>${Object.entries(vMap).map(([k, v]) => `${k}:${Number(v).toFixed(2)}V`).join(' | ')}</code>
                </div>
                `;
              })()}
            </div>

            <!-- Col 3: Receiver Intake -->
            <div class="audit-section">
              <h5>3. Receiver Somatic Intake</h5>
              <blockquote class="audit-quote">"${rec ? escapeHtml(rec.somatic_shift || '(No somatic text)') : 'N/A'}"</blockquote>
              <div class="audit-vadc-tags">
                <span class="vadc-pill receiver-pill">V: ${recVadc.valence.toFixed(2)}</span>
                <span class="vadc-pill receiver-pill">A: ${recVadc.arousal.toFixed(2)}</span>
                <span class="vadc-pill receiver-pill">D: ${recVadc.dominance.toFixed(2)}</span>
                <span class="vadc-pill receiver-pill">C: ${recVadc.confidence.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <!-- Audit Metrics Footer -->
          ${met ? `
            ${(() => {
              const raw = met.raw_distance || {};
              const adjusted = met.confidence_adjusted_distance || {};
              const total = typeof met.raw_total_distance === 'number' ? met.raw_total_distance : raw.total;
              const confTotal = typeof met.confidence_adjusted_total_distance === 'number' ? met.confidence_adjusted_total_distance : adjusted.total;
              const model = typeof met.raw_model_distance === 'number' ? met.raw_model_distance : raw.model;
              const medium = typeof met.raw_medium_distance === 'number' ? met.raw_medium_distance : raw.medium;
              return `
            <div class="audit-footer">
              <span class="metric-tag">Total Dist: <strong>${Number(total || 0).toFixed(3)}</strong></span>
              <span class="metric-tag">Conf Adjusted: <strong>${Number(confTotal || 0).toFixed(3)}</strong></span>
              <span class="metric-tag">Model Dist: <strong>${Number(model || 0).toFixed(3)}</strong></span>
              <span class="metric-tag">Medium Dist: <strong>${Number(medium || 0).toFixed(3)}</strong></span>
              ${typeof met.inter_round_drift === 'number' ? `<span class="metric-tag">Inter-Round Drift: <strong>${Number(met.inter_round_drift).toFixed(3)}</strong></span>` : ''}
            </div>
              `;
            })()}
          ` : ''}
        </article>
      `;
    });

    container.innerHTML = html;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Export to global scope
  window.RevelationView = {
    renderRevelationTrajectory: renderRevelationTrajectory,
    renderMetricsStatGrid: renderMetricsStatGrid,
    renderRoundAuditList: renderRoundAuditList,
  };
})();
