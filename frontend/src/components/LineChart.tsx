import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

const DARK_BG = "#11172a";
const GRID = "#28304f";

interface LineChartProps {
  title: string;
  values: number[];
  color: string;
}

// Single raw-signal trace. Mirrors the Plotly styling used by the legacy app.js
// so the dark charts blend into the live panel.
export function LineChart({ title, values, color }: LineChartProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    void Plotly.react(
      el,
      [
        {
          x: values.map((_, index) => index),
          y: values,
          type: "scatter",
          mode: "lines",
          name: title,
          line: { color, width: 2 },
        },
      ],
      {
        title: { text: title, font: { size: 13 } },
        margin: { l: 36, r: 16, t: 30, b: 24 },
        paper_bgcolor: DARK_BG,
        plot_bgcolor: DARK_BG,
        font: { color: "#eef2ff" },
        xaxis: { showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { showgrid: true, gridcolor: GRID, zeroline: false },
      },
      { displayModeBar: false, responsive: true },
    );
  }, [title, values, color]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) Plotly.purge(el);
    };
  }, []);

  return <div ref={ref} className="chart" />;
}
