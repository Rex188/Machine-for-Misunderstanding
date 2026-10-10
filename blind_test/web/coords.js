/**
 * coords.js — Active Affective Space Coordinate Visualizer
 *
 * Visualizes the 2D Valence-Arousal (V-A) affective space on the active canvas.
 * Strict Privacy Constraint: ONLY renders coordinates authorized for public display
 * by the backend projection. Never speculates or renders uncommitted/masked data.
 */

(function () {
  'use strict';

  /**
   * Render the 2D V-A space canvas.
   * @param {HTMLCanvasElement} canvas
   * @param {Object} projection - Privacy-sanitized projection from /api/blind/state
   */
  function renderActiveCoords(canvas, projection) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Support HiDPI rendering
    const dpr = window.devicePixelRatio || 1;
    const displayWidth = canvas.clientWidth || 400;
    const displayHeight = canvas.clientHeight || 260;

    if (canvas.width !== displayWidth * dpr || canvas.height !== displayHeight * dpr) {
      canvas.width = displayWidth * dpr;
      canvas.height = displayHeight * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);

    const width = displayWidth;
    const height = displayHeight;

    // Clear background
    ctx.fillStyle = '#090a0f';
    ctx.fillRect(0, 0, width, height);

    // Coordinate Area Margins
    const padX = 40;
    const padY = 30;
    const plotW = width - padX * 2;
    const plotH = height - padY * 2;

    // Helper: Map VAD [0, 1] to Canvas (x: 0->1, y: 1->0 inverted so high arousal is top)
    function mapX(v) {
      return padX + Math.max(0, Math.min(1, v)) * plotW;
    }
    function mapY(a) {
      return padY + (1 - Math.max(0, Math.min(1, a))) * plotH;
    }

    // Draw Grid Background
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;

    // Sub-grid lines (0.25, 0.75)
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

    // Center Crosshair (Neutral: V=0.5, A=0.5)
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

    ctx.setLineDash([]); // Reset line dash

    // Outer Border
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.strokeRect(padX, padY, plotW, plotH);

    // Axis Labels & Scale Indicators
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';

    // X-Axis (Valence)
    ctx.textAlign = 'center';
    ctx.fillText('0.0 (Aversion)', mapX(0.0), height - 10);
    ctx.fillText('0.5 (Neutral)', mapX(0.5), height - 10);
    ctx.fillText('1.0 (Pleasure)', mapX(1.0), height - 10);
    ctx.fillText('VALENCE →', mapX(0.5), padY - 12);

    // Y-Axis (Arousal)
    ctx.textAlign = 'right';
    ctx.fillText('1.0', padX - 8, mapY(1.0) + 3);
    ctx.fillText('0.5', padX - 8, mapY(0.5) + 3);
    ctx.fillText('0.0', padX - 8, mapY(0.0) + 3);

    ctx.save();
    ctx.translate(14, padY + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('AROUSAL ↑', 0, 0);
    ctx.restore();

    // Check what authorized coordinates are available
    // Privacy Rules:
    // 1. If role is SENDER and projection.own_input exists, render SENDER input coordinate.
    // 2. If role is RECEIVER, receiver CANNOT see sender input or model coordinates.
    // 3. Status watermark indicates carrier/waiting state.

    let hasPoint = false;

    if (projection && projection.role === 'SENDER' && projection.own_input && projection.own_input.input_vadc) {
      const vadc = projection.own_input.input_vadc;
      const vx = mapX(vadc.valence);
      const vy = mapY(vadc.arousal);
      const conf = typeof vadc.confidence === 'number' ? vadc.confidence : 0.8;
      const radius = 6 + conf * 4;

      // Glow halo
      ctx.beginPath();
      ctx.arc(vx, vy, radius + 4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 242, 254, 0.2)';
      ctx.fill();

      // Solid marker
      ctx.beginPath();
      ctx.arc(vx, vy, radius, 0, Math.PI * 2);
      ctx.fillStyle = '#00f2fe';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Coordinate Tag
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#00f2fe';
      ctx.textAlign = 'left';
      ctx.fillText(`Own Inscription (V:${vadc.valence.toFixed(2)}, A:${vadc.arousal.toFixed(2)})`, vx + radius + 6, vy - 2);

      hasPoint = true;
    }

    if (!hasPoint) {
      // Receiver view or standby: Watermark notice
      ctx.font = '11px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
      ctx.textAlign = 'center';

      if (projection && projection.role === 'RECEIVER') {
        const text = projection.status === 'RECEIVER_RESPONSE'
          ? 'ACOUSTIC CARRIER DISPATCHED · RECORD FELT SHIFT'
          : 'AWAITING SENDER TRANSMISSION · CARRIER MUTED';
        ctx.fillText(text, padX + plotW / 2, padY + plotH / 2);
      } else {
        ctx.fillText('AWAITING TRANSMISSION', padX + plotW / 2, padY + plotH / 2);
      }
    }

    ctx.restore();
  }

  // Export to global scope
  window.CoordsView = {
    renderActiveCoords: renderActiveCoords,
  };
})();
