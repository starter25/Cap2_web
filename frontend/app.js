// DESIGNER NOTE:
// - Layout/styling changes are best done in index.html and styles.css.
// - In this file, the API paths, JSON field names, and chart data bindings below are tied to the Python backend.
// - Do not rename ids, API routes, or backend data keys unless the Python code is updated together.

const normalBtn = document.getElementById("normal-btn");
const stressBtn = document.getElementById("stress-btn");
const exitBtn = document.getElementById("exit-btn");

const statusText = document.getElementById("status-text");
const fusionText = document.getElementById("fusion-text");
const eegFinalText = document.getElementById("eeg-final-text");
const ecgFinalText = document.getElementById("ecg-final-text");
const eegScoreText = document.getElementById("eeg-score");
const ecgScoreText = document.getElementById("ecg-score");
const heartRateText = document.getElementById("heart-rate");
const ecgRuleText = document.getElementById("ecg-rule");
const normalSamplesText = document.getElementById("normal-samples");
const stressSamplesText = document.getElementById("stress-samples");
const samplingRateText = document.getElementById("sampling-rate");
const deviceConnectedText = document.getElementById("device-connected");
const signalQualityText = document.getElementById("signal-quality");
const measurementStateText = document.getElementById("measurement-state");
const measurementTimeText = document.getElementById("measurement-time");
const hapticStatusText = document.getElementById("haptic-status");

// DO NOT MODIFY WITHOUT BACKEND CHANGES:
// These POST routes must stay aligned with web_viz/backend/app.py.
async function postAction(path) {
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) {
    throw new Error(`${path} failed`);
  }
  return response.json();
}

normalBtn.addEventListener("click", async () => {
  await postAction("/api/normal/toggle");
});

stressBtn.addEventListener("click", async () => {
  await postAction("/api/stress/toggle");
});

exitBtn.addEventListener("click", async () => {
  await postAction("/api/exit");
});

function safeText(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function formatElapsedTime(totalSec) {
  if (!Number.isFinite(totalSec) || totalSec < 0) {
    return "00:00";
  }
  const minutes = Math.floor(totalSec / 60);
  const seconds = Math.floor(totalSec % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function buildFiveSecondXAxis(length) {
  const maxIndex = Math.max((length || 1) - 1, 1);
  const tickvals = [0, 1, 2, 3, 4, 5].map((second) => (maxIndex * second) / 5);
  return {
    showgrid: false,
    tickmode: "array",
    tickvals,
    ticktext: ["0", "1", "2", "3", "4", "5"],
    title: "Time (s)",
    range: [0, maxIndex],
  };
}

function renderLineChart(targetId, title, values, color) {
  const xaxis = buildFiveSecondXAxis(values.length);
  Plotly.react(
    targetId,
    [{ x: values.map((_, index) => index), y: values, type: "scatter", mode: "lines", line: { color, width: 2 } }],
    {
      title,
      margin: { l: 40, r: 20, t: 40, b: 30 },
      paper_bgcolor: "#11172a",
      plot_bgcolor: "#11172a",
      font: { color: "#eef2ff" },
      xaxis,
      yaxis: { showgrid: true, gridcolor: "#28304f" },
    },
    { displayModeBar: false, responsive: true },
  );
}

// DO NOT MODIFY WITHOUT BACKEND CHANGES:
// The state.plots.* keys and threshold names come directly from /api/state.
function renderScoreChart(state) {
  const thresholds = state.plots.thresholds;
  const scoreLength = Math.max(state.plots.eegScore.length, state.plots.ecgScore.length);
  const xaxis = buildFiveSecondXAxis(scoreLength);
  Plotly.react(
    "chart-score",
    [
      { x: state.plots.eegScore.map((_, index) => index), y: state.plots.eegScore, type: "scatter", mode: "lines", name: "EEG Score", line: { color: "#22c55e", width: 3 } },
      { x: state.plots.ecgScore.map((_, index) => index), y: state.plots.ecgScore, type: "scatter", mode: "lines", name: "ECG Score", line: { color: "#a855f7", width: 3 } },
    ],
    {
      title: "EEG / ECG Stress Score",
      margin: { l: 40, r: 20, t: 40, b: 30 },
      paper_bgcolor: "#11172a",
      plot_bgcolor: "#11172a",
      font: { color: "#eef2ff" },
      xaxis,
      yaxis: { range: [0, 100], showgrid: true, gridcolor: "#28304f" },
      shapes: [
        { type: "line", x0: 0, x1: 1, xref: "paper", y0: thresholds.baseline, y1: thresholds.baseline, line: { color: "#bbbbbb", dash: "dot" } },
        { type: "line", x0: 0, x1: 1, xref: "paper", y0: thresholds.stress, y1: thresholds.stress, line: { color: "#ffbf00", dash: "dot" } },
        { type: "line", x0: 0, x1: 1, xref: "paper", y0: thresholds.reject, y1: thresholds.reject, line: { color: "#ef4444", dash: "dot" } },
      ],
      legend: { orientation: "h" },
    },
    { displayModeBar: false, responsive: true },
  );
}

// DO NOT MODIFY WITHOUT BACKEND CHANGES:
// The state.current.*, state.baseline.*, and state.ui.* field names are provided by the backend.
function updateUi(state) {
  statusText.textContent = state.status;
  fusionText.textContent = state.current.displayState || "idle";
  eegFinalText.textContent = `EEG: ${state.current.eegFinal}`;
  ecgFinalText.textContent = `ECG: ${state.current.ecgFinal}`;
  eegScoreText.textContent = safeText(state.current.eegSmoothedScore);
  ecgScoreText.textContent = safeText(state.current.ecgSmoothedScore);
  heartRateText.textContent = safeText(state.current.heartRate);
  ecgRuleText.textContent = state.current.ecgRule || "-";
  normalSamplesText.textContent = `Normal Samples: ${state.baseline.normalSamples}`;
  stressSamplesText.textContent = `Stress Samples: ${state.baseline.stressSamples}`;
  samplingRateText.textContent = `Sampling Rate: ${safeText(state.current.samplingRate, 2)} Hz`;
  normalBtn.textContent = state.ui.normalButtonLabel;
  stressBtn.textContent = state.ui.stressButtonLabel;
  normalBtn.disabled = !!state.ui.normalButtonDisabled;
  stressBtn.disabled = !!state.ui.stressButtonDisabled;
  deviceConnectedText.textContent = state.device.connected ? "연결됨" : "끊김";
  signalQualityText.textContent = state.device.signalQuality || "unknown";
  measurementStateText.textContent = state.measurement.stateLabel || "대기 중";
  measurementTimeText.textContent = formatElapsedTime(state.measurement.elapsedSec);
  hapticStatusText.textContent = state.device.hapticStatus || "-";

  renderLineChart("chart-eeg1", "EEG1 Raw", state.plots.rawEeg1, "#3b82f6");
  renderLineChart("chart-eeg2", "EEG2 Raw", state.plots.rawEeg2, "#f97316");
  renderLineChart("chart-ecg", "ECG Raw", state.plots.rawEcg, "#a855f7");
  renderScoreChart(state);
}

// DO NOT MODIFY WITHOUT BACKEND CHANGES:
// /api/state is the fixed polling endpoint exposed by the backend.
async function refreshState() {
  const response = await fetch("/api/state");
  if (!response.ok) {
    return;
  }
  const state = await response.json();
  updateUi(state);
}

setInterval(refreshState, 400);
refreshState();
