import type { AppState } from "./types";

// Offline preview generator. When /api/state is unreachable (designer preview,
// no device connected) the polling hook falls back to this so the whole UI —
// charts, score, mascot, baselines — stays alive. Ported from the standalone
// shim that used to live in the legacy index.html.

const RAW_LEN = 220;
const SCORE_LEN = 170;
const TARGET = 2600;
const THRESHOLDS = { baseline: 33, stress: 60, reject: 82 };

const clamp = (v: number) => Math.max(0, Math.min(100, v));
const eeg1 = (t: number) =>
  Math.sin(t * 1.7) * 0.6 + Math.sin(t * 4.3 + 1.1) * 0.35 + Math.sin(t * 9.1) * 0.18 + (Math.random() - 0.5) * 0.5;
const eeg2 = (t: number) =>
  Math.sin(t * 6.2) * 0.5 + Math.sin(t * 13.7 + 0.5) * 0.3 + (Math.random() - 0.5) * 0.9;

interface MockMemory {
  t: number;
  ecgPhase: number;
  eeg: number;
  ecg: number;
  startedAt: number;
  rawEeg1: number[];
  rawEeg2: number[];
  rawEcg: number[];
  eegSeries: number[];
  ecgSeries: number[];
}

function ecg(m: MockMemory): number {
  m.ecgPhase += 0.085;
  const b = m.ecgPhase % (Math.PI * 2);
  let v = Math.sin(b * 0.5) * 0.08;
  v += Math.exp(-Math.pow((b - 0.6) * 6, 2)) - Math.exp(-Math.pow((b - 1) * 7, 2)) * 0.28 + (Math.random() - 0.5) * 0.05;
  return v;
}

function createMemory(): MockMemory {
  const m: MockMemory = {
    t: 0,
    ecgPhase: 0,
    eeg: 68,
    ecg: 48,
    startedAt: Date.now() - 156 * 1000,
    rawEeg1: [],
    rawEeg2: [],
    rawEcg: [],
    eegSeries: [],
    ecgSeries: [],
  };
  for (let i = 0; i < RAW_LEN; i++) {
    m.t += 0.18;
    m.rawEeg1.push(eeg1(m.t));
    m.rawEeg2.push(eeg2(m.t));
    m.rawEcg.push(ecg(m));
  }
  for (let j = 0; j < SCORE_LEN; j++) {
    const k = j / (SCORE_LEN - 1);
    m.eegSeries.push(clamp(m.eeg - (1 - k) * 22 + (Math.random() - 0.5) * 2.5));
    m.ecgSeries.push(clamp(m.ecg - (1 - k) * 16 + (Math.random() - 0.5) * 2.5));
  }
  return m;
}

let memory: MockMemory | null = null;

function tick(m: MockMemory): void {
  for (let i = 0; i < 3; i++) {
    m.t += 0.18;
    m.rawEeg1.push(eeg1(m.t));
    m.rawEeg2.push(eeg2(m.t));
    m.rawEcg.push(ecg(m));
    if (m.rawEeg1.length > RAW_LEN) m.rawEeg1.shift();
    if (m.rawEeg2.length > RAW_LEN) m.rawEeg2.shift();
    if (m.rawEcg.length > RAW_LEN) m.rawEcg.shift();
  }
  if (Math.random() < 0.01) m.eeg += (clamp(m.eeg + (Math.random() - 0.5) * 24) - m.eeg) * 0.04;
  m.eeg = clamp(m.eeg + (Math.random() - 0.5) * 1.2);
  m.ecg = clamp(m.ecg + (Math.random() - 0.5) * 1.2);
  m.eegSeries.push(clamp(m.eeg));
  m.ecgSeries.push(clamp(m.ecg));
  if (m.eegSeries.length > SCORE_LEN) m.eegSeries.shift();
  if (m.ecgSeries.length > SCORE_LEN) m.ecgSeries.shift();
}

export function nextMockState(): AppState {
  if (memory === null) memory = createMemory();
  const m = memory;
  tick(m);
  const elapsed = Math.max(0, Math.floor((Date.now() - m.startedAt) / 1000));
  return {
    status: "MOCK",
    device: {
      connected: true,
      signalQuality: "good",
      eegQuality: "good",
      ecgQuality: "good",
      hapticStatus: "HAPTIC_IDLE",
    },
    measurement: { stateLabel: "실시간 측정 중", elapsedSec: elapsed },
    flags: {
      collectingNormal: false,
      collectingStress: false,
      detecting: true,
      normalReady: true,
      stressReady: true,
    },
    ui: {
      normalButtonLabel: "평상시 기준값 측정",
      stressButtonLabel: "스트레스 기준값 측정",
      normalButtonDisabled: false,
      stressButtonDisabled: false,
    },
    current: {
      eegFinal: "NORMAL",
      ecgFinal: "NORMAL",
      fusionFinal: "NORMAL",
      displayState: "normal",
      eegProbability: m.eeg / 100,
      eegSmoothedProbability: m.eeg / 100,
      eegScore: m.eeg,
      eegSmoothedScore: m.eeg,
      ecgProbability: m.ecg / 100,
      ecgSmoothedProbability: m.ecg / 100,
      ecgScore: m.ecg,
      ecgSmoothedScore: m.ecg,
      ecgRule: "mock",
      heartRate: 72 + Math.round(Math.sin(m.t * 0.1) * 4),
      rmssd: 42,
      samplingRate: 41.7,
    },
    baseline: {
      normalSamples: TARGET,
      stressSamples: TARGET,
      eegNormalMean: 0.3,
      eegStressMean: 0.7,
      ecgNormalMean: 0.35,
      ecgStressMean: 0.65,
    },
    plots: {
      rawEeg1: m.rawEeg1.slice(),
      rawEeg2: m.rawEeg2.slice(),
      rawEcg: m.rawEcg.slice(),
      eegScore: m.eegSeries.slice(),
      ecgScore: m.ecgSeries.slice(),
      thresholds: THRESHOLDS,
    },
  };
}
