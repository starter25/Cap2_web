// Mirror of the JSON returned by web_viz.backend.controller.FusionWebController.get_state().
// Keep these field names in lockstep with controller.py:get_state(); the backend is the
// source of truth. Numeric fields that the backend emits as NaN are serialized as null.

export type DisplayState = "idle" | "normal" | "caution" | "stress" | "danger" | string;

export interface DeviceState {
  connected: boolean;
  signalQuality: string;
  eegQuality: string;
  ecgQuality: string;
  hapticStatus: string;
}

export interface MeasurementState {
  stateLabel: string;
  elapsedSec: number;
}

export interface Flags {
  collectingNormal: boolean;
  collectingStress: boolean;
  detecting: boolean;
  normalReady: boolean;
  stressReady: boolean;
}

export interface UiState {
  normalButtonLabel: string;
  stressButtonLabel: string;
  stressButtonDisabled: boolean;
  normalButtonDisabled: boolean;
}

export interface CurrentState {
  eegFinal: string;
  ecgFinal: string;
  fusionFinal: string;
  displayState: DisplayState;
  eegProbability: number | null;
  eegSmoothedProbability: number | null;
  eegScore: number | null;
  eegSmoothedScore: number | null;
  ecgProbability: number | null;
  ecgSmoothedProbability: number | null;
  ecgScore: number | null;
  ecgSmoothedScore: number | null;
  ecgRule: string;
  heartRate: number | null;
  rmssd: number | null;
  samplingRate: number;
}

export interface BaselineState {
  normalSamples: number;
  stressSamples: number;
  eegNormalMean: number | null;
  eegStressMean: number | null;
  ecgNormalMean: number | null;
  ecgStressMean: number | null;
}

export interface Thresholds {
  baseline: number;
  stress: number;
  reject: number;
}

export interface Plots {
  rawEeg1: number[];
  rawEeg2: number[];
  rawEcg: number[];
  eegScore: (number | null)[];
  ecgScore: (number | null)[];
  thresholds: Thresholds;
}

export interface AppState {
  status: string;
  device: DeviceState;
  measurement: MeasurementState;
  flags: Flags;
  ui: UiState;
  current: CurrentState;
  baseline: BaselineState;
  plots: Plots;
}

export interface ActionResult {
  ok: boolean;
  message: string;
  state?: AppState;
}
