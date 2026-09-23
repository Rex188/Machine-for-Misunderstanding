/**
 * visualizer.js — A Machine for Misunderstanding · Exhibition Present Canvas
 * Generative Audio-Visual Topology on Warm Ivory / Xuan Paper Canvas (#f8f6f0)
 * Integrates:
 * 1. Real-time Live Audio Capture (Web Audio API: Time-Domain Oscilloscope & FFT Heatmap)
 * 2. Frequency-driven Brownian random-walk particle field & lattice filaments
 * 3. Central topological acoustic resonance organism
 */

let canvas;
let p5Instance;

// Smooth Lerp Parameters
let curTimbre = 1.25;
let curFreq = 1.41;
let curAmp = 7.5;
let curEnv = -0.7;
let curMode = -4.0;
let curChord = 3.0;
let curChordType = 0.0;
let curStep = 0;

let morphProgress = 1.0;
let lastStep = 0;

// Central Resonant Nodes
const NUM_NODES = 120;
let nodes = [];
let rotationAngle = 0;
let breathePhase = 0;

// Background Brownian / Random-Walk Particles (Governed by Frequency)
const MAX_PARTICLES = 360;
let bgParticles = [];

// ========================================================
// Real-Time Web Audio Engine (Oscilloscope & Spectral Heatmap)
// ========================================================
window.AUDIO_ENGINE = {
  active: false,
  audioCtx: null,
  analyser: null,
  stream: null,
  timeData: null,
  freqData: null,
  rms: 0.0,
  smoothedRms: 0.0,
  bassEnergy: 0.0,
  midEnergy: 0.0,
  highEnergy: 0.0,
  currentDeviceId: null,

  async toggle(deviceId) {
    if (this.active) {
      this.stop();
      return false;
    } else {
      return await this.start(deviceId);
    }
  },

  async start(deviceId) {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
      }
      const constraints = {
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
        video: false,
      };
      if (deviceId && deviceId !== 'default') {
        constraints.audio.deviceId = { exact: deviceId };
      }
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.currentDeviceId = deviceId || 'default';
      const source = this.audioCtx.createMediaStreamSource(this.stream);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 2048; // 1024 time-domain points & 1024 frequency bins
      this.analyser.smoothingTimeConstant = 0.8;
      source.connect(this.analyser);

      this.timeData = new Uint8Array(this.analyser.frequencyBinCount);
      this.freqData = new Uint8Array(this.analyser.frequencyBinCount);
      this.active = true;
      return true;
    } catch (err) {
      console.warn('Audio capture initialization error:', err);
      alert('Could not capture audio stream: ' + err.message + '\nPlease verify microphone/loopback permissions.');
      this.active = false;
      return false;
    }
  },

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    this.active = false;
    this.rms = 0.0;
    this.smoothedRms = 0.0;
  },

  update() {
    if (!this.active || !this.analyser) return;
    this.analyser.getByteTimeDomainData(this.timeData);
    this.analyser.getByteFrequencyData(this.freqData);

    // Compute RMS amplitude
    let sumSquares = 0;
    for (let i = 0; i < this.timeData.length; i++) {
      const norm = (this.timeData[i] - 128) / 128;
      sumSquares += norm * norm;
    }
    this.rms = Math.sqrt(sumSquares / this.timeData.length);
    this.smoothedRms = this.smoothedRms * 0.8 + this.rms * 0.2;

    // Compute band energies (Bass: 0-14, Mid: 15-120, High: 121-420)
    let bSum = 0, mSum = 0, hSum = 0;
    for (let i = 0; i < 14; i++) bSum += this.freqData[i];
    for (let i = 14; i < 120; i++) mSum += this.freqData[i];
    for (let i = 120; i < 420; i++) hSum += this.freqData[i];
    this.bassEnergy = bSum / (14 * 255);
    this.midEnergy = mSum / (106 * 255);
    this.highEnergy = hSum / (300 * 255);
  }
};

function initSketch() {
  const sketch = (p) => {
    p.setup = () => {
      const container = document.getElementById('canvasContainer');
      const w = (container && container.clientWidth > 0) ? container.clientWidth : p.windowWidth;
      const h = (container && container.clientHeight > 0) ? container.clientHeight : p.windowHeight;
      canvas = p.createCanvas(w, h);
      canvas.parent('canvasContainer');
      p.pixelDensity(p.displayDensity() > 1 ? 2 : 1);
      p.smooth();

      // Initialize Central Topology Nodes
      nodes = [];
      for (let i = 0; i < NUM_NODES; i++) {
        nodes.push({
          angle: (p.TWO_PI / NUM_NODES) * i,
          radius: p.random(120, 260),
          baseRadius: p.random(120, 260),
          speed: p.random(0.003, 0.012),
          phase: p.random(p.TWO_PI),
          wobbleFreq: p.random(2, 6),
          inkWeight: p.random(0.8, 2.4),
        });
      }

      // Initialize Background Particle Field
      bgParticles = [];
      for (let i = 0; i < MAX_PARTICLES; i++) {
        bgParticles.push({
          x: p.random(w),
          y: p.random(h),
          vx: p.random(-0.3, 0.3),
          vy: p.random(-0.3, 0.3),
          size: p.random(1.2, 2.8),
          phase: p.random(1000),
          baseAlpha: p.random(35, 95),
        });
      }

      p.background(248, 246, 240); // Warm Ivory / Raw Xuan Paper #f8f6f0
    };

    p.draw = () => {
      // 1. Update Live Audio Engine
      window.AUDIO_ENGINE.update();

      // 2. Fetch Real-time VCV Rack Voltages with Smooth Easing (Lerp)
      if (window.RACK_STATE && window.RACK_STATE.voltages) {
        const v = window.RACK_STATE.voltages;
        curTimbre = p.lerp(curTimbre, v.timbre_v !== undefined ? v.timbre_v : 1.25, 0.05);
        curFreq = p.lerp(curFreq, v.frequency_v !== undefined ? v.frequency_v : 1.41, 0.05);
        curAmp = p.lerp(curAmp, v.amplitude_v !== undefined ? v.amplitude_v : 7.5, 0.05);
        curEnv = p.lerp(curEnv, v.envelope_v !== undefined ? v.envelope_v : -0.7, 0.05);
        curMode = p.lerp(curMode, v.mode_v !== undefined ? v.mode_v : -4.0, 0.05);
        curChord = p.lerp(curChord, v.chord_v !== undefined ? v.chord_v : 3.0, 0.05);
        curChordType = p.lerp(curChordType, v.type_v !== undefined ? v.type_v : 0.0, 0.05);

        const currentServerStep = window.RACK_STATE.progression_step || 0;
        if (currentServerStep !== lastStep) {
          lastStep = currentServerStep;
          morphProgress = 0.0;
        }
      }

      morphProgress = p.min(1.0, morphProgress + 0.012);

      // 3. Mode Spectrum & Chromatic Tone Selection
      let primaryColor, accentColor, symmetryCount;
      if (curMode <= -3.5) {
        // Ionian (-4V): Rigid concentric array, disciplined slate gray
        primaryColor = p.color(32, 38, 46, 170);
        accentColor = p.color(105, 115, 125, 130);
        symmetryCount = 4;
      } else if (curMode <= -2.5) {
        // Dorian (-3V): Jazz suspension, deep celadon gray
        primaryColor = p.color(28, 38, 48, 175);
        accentColor = p.color(70, 115, 145, 155);
        symmetryCount = 3;
      } else if (curMode <= -1.5) {
        // Phrygian (-2V): Dark ink ground with breaking dawn amber gold
        primaryColor = p.color(18, 22, 28, 205);
        accentColor = p.color(195, 120, 5, 215);
        symmetryCount = 5;
      } else if (curMode <= -0.5) {
        // Lydian (-1V): Augmented 4th surreal levitation, lilac ink
        primaryColor = p.color(45, 40, 60, 165);
        accentColor = p.color(140, 100, 180, 165);
        symmetryCount = 7;
      } else if (curMode <= 0.5) {
        // Mixolydian (0V): Radiant warmth & free dynamic surge, terracotta
        primaryColor = p.color(38, 26, 22, 185);
        accentColor = p.color(185, 82, 32, 185);
        symmetryCount = 6;
      } else if (curMode <= 1.5) {
        // Aeolian (+1V): Pure solitary sorrow, indigo mist
        primaryColor = p.color(22, 26, 32, 170);
        accentColor = p.color(75, 85, 100, 140);
        symmetryCount = 2;
      } else {
        // Locrian (+2V): Structural collapse & severe dissonance, charred graphite
        primaryColor = p.color(20, 18, 22, 210);
        accentColor = p.color(160, 40, 40, 190);
        symmetryCount = 1;
      }

      // 4. Reverb Dissolution Trails (Envelope CV)
      const trailAlpha = p.map(curEnv, -5.0, 5.0, 48, 14);
      p.noStroke();
      p.fill(248, 246, 240, trailAlpha);
      p.rect(0, 0, p.width, p.height);

      // ========================================================
      // Layer 0: Spectral Energy Heatmap & Somatic Thermal Wash
      // ========================================================
      p.push();
      const hasLiveAudio = window.AUDIO_ENGINE.active;
      const bassPow = hasLiveAudio ? window.AUDIO_ENGINE.bassEnergy : p.map(curAmp, 2, 10, 0.1, 0.6);
      const midPow = hasLiveAudio ? window.AUDIO_ENGINE.midEnergy : p.map(curTimbre, 0, 2.5, 0.1, 0.7);
      const thermalRms = hasLiveAudio ? window.AUDIO_ENGINE.smoothedRms : p.map(curAmp, 2, 10, 0.05, 0.35);

      // Deep Sub-Bass Thermal Core (Lower Canvas)
      const heatRadius = p.map(bassPow, 0, 1, 140, 520);
      const heatAlpha = p.map(bassPow, 0, 1, 12, 55);
      p.noStroke();
      p.fill(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], heatAlpha);
      p.circle(p.width * 0.5, p.height * 0.70, heatRadius * 1.6);

      // Atmospheric Mid/High Thermal Contour Rings (Isobaric Sound Pressure)
      p.noFill();
      const numContours = 3;
      for (let c = 1; c <= numContours; c++) {
        const ringRad = (240 + c * 90) * (1.0 + thermalRms * 0.8);
        const ringAlpha = p.map(midPow, 0, 1, 8, 38) / c;
        p.stroke(accentColor.levels[0], accentColor.levels[1], accentColor.levels[2], ringAlpha);
        p.strokeWeight(0.8);
        p.circle(p.width * 0.5, p.height * 0.5, ringRad);
      }
      p.pop();

      // ========================================================
      // Layer 1: Background Brownian Random Walk Particle Field
      // ========================================================
      const activeCount = p.floor(p.map(curFreq, -3.0, 4.0, 45, MAX_PARTICLES, true));
      const chaos = p.map(curFreq, -3.0, 4.0, 0.25, 3.4, true) + thermalRms * 2.0;
      const stepSpeed = p.map(curFreq, -3.0, 4.0, 0.45, 4.2, true) + thermalRms * 3.0;
      const linkDist = p.map(curFreq, -3.0, 4.0, 26, 68, true);

      p.push();
      for (let i = 0; i < activeCount; i++) {
        const pt = bgParticles[i];

        const nAngle = p.noise(pt.x * 0.003, pt.y * 0.003, pt.phase + p.frameCount * 0.003 * chaos) * p.TWO_PI * 2.8;
        const flowX = p.cos(nAngle) * stepSpeed;
        const flowY = p.sin(nAngle) * stepSpeed;

        const jx = (p.random() - 0.5) * chaos * 2.6;
        const jy = (p.random() - 0.5) * chaos * 2.6;

        pt.vx = p.lerp(pt.vx, flowX + jx, 0.12);
        pt.vy = p.lerp(pt.vy, flowY + jy, 0.12);

        pt.x += pt.vx;
        pt.y += pt.vy;

        if (pt.x < -12) pt.x = p.width + 12;
        if (pt.x > p.width + 12) pt.x = -12;
        if (pt.y < -12) pt.y = p.height + 12;
        if (pt.y > p.height + 12) pt.y = -12;

        const dotAlpha = p.map(chaos, 0.25, 3.4, pt.baseAlpha * 0.7, pt.baseAlpha * 1.35);
        p.noStroke();
        p.fill(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], dotAlpha);
        p.circle(pt.x, pt.y, pt.size * (0.8 + 0.35 * (curAmp / 10.0)));
      }

      // Proximity Filaments
      if (curFreq > -1.5 || thermalRms > 0.15) {
        const lineAlphaBase = p.map(curFreq, -1.5, 4.0, 16, 68, true) + thermalRms * 40;
        for (let i = 0; i < activeCount; i += 2) {
          const p1 = bgParticles[i];
          for (let j = i + 1; j < activeCount; j += 2) {
            const p2 = bgParticles[j];
            const d = p.dist(p1.x, p1.y, p2.x, p2.y);
            if (d < linkDist) {
              const aLine = p.map(d, 0, linkDist, lineAlphaBase, 0);
              p.stroke(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], aLine);
              p.strokeWeight(0.5);
              p.line(p1.x, p1.y, p2.x, p2.y);
            }
          }
        }
      }
      p.pop();

      // ========================================================
      // Layer 2: Horizon Precision Vector Scope (Real Audio Waveform)
      // ========================================================
      p.push();
      const horizonY = p.height * 0.72;
      const scopeWidth = p.width - 96;
      const scopeStartX = 48;
      const scopeHeight = p.height * 0.16;

      // Subtle Zero-Crossing Reference Line
      p.stroke(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], 30);
      p.strokeWeight(0.6);
      p.line(scopeStartX, horizonY, scopeStartX + scopeWidth, horizonY);

      // Registration Labels
      p.noStroke();
      p.fill(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], 75);
      p.textFont('JetBrains Mono');
      p.textSize(8.5);
      p.text(hasLiveAudio ? 'SCOPE // 48kHz LIVE PCM (VCV RACK)' : 'SCOPE // STANDBY SYNTHESIS', scopeStartX, horizonY - 14);
      p.textAlign(p.RIGHT);
      p.text(hasLiveAudio ? `RMS: ${(window.AUDIO_ENGINE.rms * 100).toFixed(1)}%` : '0.00 V REF', scopeStartX + scopeWidth, horizonY - 14);
      p.textAlign(p.LEFT);

      // Draw Oscilloscope Traces
      const timeBuffer = (hasLiveAudio && window.AUDIO_ENGINE.timeData) ? window.AUDIO_ENGINE.timeData : null;
      const sampleSteps = 240;

      // 1. Ghost Persistence Trail (Phosphor / Ink Bleed)
      p.noFill();
      p.stroke(accentColor.levels[0], accentColor.levels[1], accentColor.levels[2], 40);
      p.strokeWeight(0.5);
      p.beginShape();
      for (let s = 0; s <= sampleSteps; s++) {
        const u = s / sampleSteps;
        const x = scopeStartX + u * scopeWidth;
        let yOffset = 0;
        if (timeBuffer) {
          const idx = p.floor(u * (timeBuffer.length - 1));
          yOffset = ((timeBuffer[idx] - 128) / 128.0) * scopeHeight;
        } else {
          // Mathematical standby carrier
          yOffset = p.sin(u * 22.0 + p.frameCount * 0.08) * (scopeHeight * 0.22) * (curAmp / 10.0);
        }
        p.curveVertex(x, horizonY + yOffset + 1.2);
      }
      p.endShape();

      // 2. Primary Hairline Vector Waveform
      p.stroke(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], 180);
      p.strokeWeight(1.0);
      p.beginShape();
      for (let s = 0; s <= sampleSteps; s++) {
        const u = s / sampleSteps;
        const x = scopeStartX + u * scopeWidth;
        let yOffset = 0;
        if (timeBuffer) {
          const idx = p.floor(u * (timeBuffer.length - 1));
          yOffset = ((timeBuffer[idx] - 128) / 128.0) * scopeHeight;
        } else {
          yOffset = p.sin(u * 22.0 + p.frameCount * 0.08) * (scopeHeight * 0.22) * (curAmp / 10.0);
        }
        p.curveVertex(x, horizonY + yOffset);
      }
      p.endShape();
      p.pop();

      // ========================================================
      // Layer 3: Central Resonant Organism (Topological Mesh)
      // ========================================================
      const bpm = 50 + 170 * ((curFreq + 3.0) / 7.0);
      const pulseSpeed = (bpm / 60.0) * 0.04;
      breathePhase += pulseSpeed;
      const audioPulse = hasLiveAudio ? window.AUDIO_ENGINE.smoothedRms * 0.25 : 0;
      const breatheScale = (1.0 + 0.07 * p.sin(breathePhase) * (curAmp / 10.0)) + audioPulse;
      rotationAngle += 0.002 * (curFreq + 4.0);

      const cx = p.width / 2;
      const cy = p.height / 2;

      p.push();
      p.translate(cx, cy);
      p.scale(breatheScale);
      p.rotate(rotationAngle);

      const chordDegreeFactor = p.floor(curChord) + 1;
      const chordTypeSpread = curChordType * 35;

      p.noFill();

      // Layer 3A: Topological Hairline Mesh (Casey Reas inspired)
      const lineAlpha = p.map(curAmp, 2.0, 10.0, 50, 185);
      p.stroke(primaryColor.levels[0], primaryColor.levels[1], primaryColor.levels[2], lineAlpha);
      p.strokeWeight(p.map(curAmp, 2.0, 10.0, 0.6, 1.8));

      p.beginShape();
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        n.phase += n.speed * (bpm / 100.0);

        let rOffset = 0;
        if (curTimbre >= 1.8) {
          rOffset = p.noise(p.cos(n.angle) * 3, p.sin(n.angle) * 3, p.frameCount * 0.05) * 140 - 70;
        } else if (curTimbre >= 0.9) {
          rOffset = p.sin(n.angle * chordDegreeFactor + n.phase) * (45 + chordTypeSpread)
                  + p.cos(n.angle * symmetryCount) * 20;
        } else if (curTimbre >= 0.3) {
          rOffset = (p.sin(n.angle * 18 + n.phase * 4) > 0 ? 18 : -18) * (curAmp / 8.0);
        } else {
          rOffset = p.sin(n.angle * 2 + n.phase) * 18;
        }

        const r = (n.baseRadius + rOffset) * (0.8 + 0.4 * morphProgress);
        const x = r * p.cos(n.angle);
        const y = r * p.sin(n.angle);

        p.curveVertex(x, y);

        if (i % 6 === 0) {
          p.push();
          p.stroke(accentColor.levels[0], accentColor.levels[1], accentColor.levels[2], 90);
          p.strokeWeight(0.5);
          p.line(0, 0, x, y);
          p.pop();
        }
      }
      p.endShape(p.CLOSE);

      // Layer 3B: Harmonic Orbital Rings (Zach Lieberman resonant standing waves)
      const numRings = p.floor(p.map(curChord, 0, 6, 3, 7));
      for (let k = 1; k <= numRings; k++) {
        p.push();
        p.stroke(accentColor.levels[0], accentColor.levels[1], accentColor.levels[2], p.map(k, 1, numRings, 120, 30));
        p.strokeWeight(p.map(k, 1, numRings, 1.2, 0.4));
        p.beginShape();
        const ringStep = p.TWO_PI / 64;
        for (let a = 0; a <= p.TWO_PI + ringStep; a += ringStep) {
          const lissajousMod = p.sin(a * k + breathePhase * 0.5) * (15 * (curTimbre + 0.5));
          const rad = (k * 42 + lissajousMod) * breatheScale;
          const rx = rad * p.cos(a);
          const ry = rad * p.sin(a);
          p.curveVertex(rx, ry);
        }
        p.endShape();
        p.pop();
      }

      // Layer 3C: Central Resonator Core (Morphing Stellar Focus)
      p.push();
      p.noStroke();
      const coreGlow = p.map(curAmp, 2, 10, 18, 48) * (1.0 + audioPulse * 1.5);
      p.fill(accentColor.levels[0], accentColor.levels[1], accentColor.levels[2], 30);
      p.circle(0, 0, coreGlow * 2.2);
      p.fill(accentColor.levels[0], accentColor.levels[1], accentColor.levels[2], 180);
      p.circle(0, 0, coreGlow * 0.5);
      p.pop();

      p.pop();

      // 7. Bauhaus Precision Corner Markings
      p.push();
      p.stroke(180, 175, 165, 80);
      p.strokeWeight(0.6);
      p.line(30, 30, 50, 30);
      p.line(30, 30, 30, 50);
      p.line(p.width - 30, 30, p.width - 50, 30);
      p.line(p.width - 30, 30, p.width - 30, 50);
      p.line(30, p.height - 30, 50, p.height - 30);
      p.line(30, p.height - 30, 30, p.height - 50);
      p.line(p.width - 30, p.height - 30, p.width - 50, p.height - 30);
      p.line(p.width - 30, p.height - 30, p.width - 30, p.height - 50);
      p.pop();
    };

    p.windowResized = () => {
      const container = document.getElementById('canvasContainer');
      const w = (container && container.clientWidth > 0) ? container.clientWidth : p.windowWidth;
      const h = (container && container.clientHeight > 0) ? container.clientHeight : p.windowHeight;
      p.resizeCanvas(w, h);
    };
  };

  p5Instance = new p5(sketch);
}

document.addEventListener('DOMContentLoaded', () => {
  initSketch();
});
