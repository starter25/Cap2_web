import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { Plots } from "../types";

const DARK_BG = "#11172a";
const GRID = "#28304f";

// EEG/ECG stress-score chart with the baseline / stress / reject threshold
// guide lines, matching the legacy renderScoreChart().
export function ScoreChart({ plots }: { plots: Plots }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { thresholds } = plots;
    void Plotly.react(
      el,
      [
        {
          x: plots.eegScore.map((_, index) => index),
          y: plots.eegScore,
          type: "scatter",
          mode: "lines",
          name: "EEG Score",
          line: { color: "#22c55e", width: 3 },
        },
        {
          x: plots.ecgScore.map((_, index) => index),
          y: plots.ecgScore,
          type: "scatter",
          mode: "lines",
          name: "ECG Score",
          line: { color: "#a855f7", width: 3 },
        },
      ],
      {
        title: { text: "EEG / ECG Stress Score", font: { size: 13 } },
        margin: { l: 40, r: 20, t: 36, b: 30 },
        paper_bgcolor: DARK_BG,
        plot_bgcolor: DARK_BG,
        font: { color: "#eef2ff" },
        xaxis: { showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { range: [0, 100], showgrid: true, gridcolor: GRID },
        shapes: [
          { type: "line", x0: 0, x1: 1, xref: "paper", y0: thresholds.baseline, y1: thresholds.baseline, line: { color: "#bbbbbb", dash: "dot" } },
          { type: "line", x0: 0, x1: 1, xref: "paper", y0: thresholds.stress, y1: thresholds.stress, line: { color: "#ffbf00", dash: "dot" } },
          { type: "line", x0: 0, x1: 1, xref: "paper", y0: thresholds.reject, y1: thresholds.reject, line: { color: "#ef4444", dash: "dot" } },
        ],
        legend: { orientation: "h" },
      },
      { displayModeBar: false, responsive: true },
    );
  }, [plots]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) Plotly.purge(el);
    };
  }, []);

  return <div ref={ref} className="chart" />;
}
