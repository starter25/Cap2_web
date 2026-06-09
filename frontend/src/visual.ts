import type { DisplayState } from "./types";

// Maps the backend displayState onto the mascot expression, status-pill label
// and glow colors. Ported from the legacy in-page sync script.
export type MascotMood = "idle" | "calm" | "normal" | "warn" | "danger";

export interface Visual {
  mood: MascotMood;
  label: string;
  glow: string;
  ring: string;
}

export function visualOfDisplayState(displayState: DisplayState | undefined): Visual {
  switch ((displayState ?? "").toLowerCase()) {
    case "normal":
      return { mood: "calm", label: "정상", glow: "rgba(79,209,122,0.7)", ring: "rgba(79,209,122,0.6)" };
    case "caution":
      return { mood: "normal", label: "주의", glow: "rgba(255,200,120,0.75)", ring: "rgba(255,198,120,0.6)" };
    case "stress":
      return { mood: "warn", label: "스트레스", glow: "rgba(245,128,62,0.7)", ring: "rgba(245,128,62,0.6)" };
    case "danger":
      return { mood: "danger", label: "위험", glow: "rgba(239,84,102,0.7)", ring: "rgba(239,84,102,0.65)" };
    default:
      return { mood: "idle", label: "대기", glow: "rgba(180,180,210,0.6)", ring: "rgba(200,200,225,0.6)" };
  }
}

// Number of baseline samples that fills a progress bar (visual reference only).
export const BASELINE_TARGET = 2000;

export function baselineProgress(samples: number): { pct: number; done: boolean; sub: string } {
  const done = samples >= BASELINE_TARGET;
  const pct = done ? 100 : Math.max(0, Math.min(100, Math.round((samples / BASELINE_TARGET) * 100)));
  const sub = done ? "측정 완료" : samples > 0 ? "측정 중…" : "대기 중";
  return { pct, done, sub };
}

// Headline stress index = mean of the smoothed EEG/ECG scores the backend emits.
export function headlineScore(eeg: number | null, ecg: number | null): number | null {
  if (eeg != null && ecg != null) return 0.5 * eeg + 0.5 * ecg;
  if (eeg != null) return eeg;
  if (ecg != null) return ecg;
  return null;
}

export function formatElapsed(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}
