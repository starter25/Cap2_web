import type { Plots } from "../types";
import { LineChart } from "./LineChart";
import { ScoreChart } from "./ScoreChart";

export function LivePanel({ plots }: { plots: Plots }) {
  return (
    <div className="live-panel glass">
      <div className="live-head"><span className="live-dot" /> LIVE</div>
      <div className="charts">
        <div className="chart-block signal">
          <div className="c-title">EEG (뇌파 1)</div>
          <div className="chart-card"><LineChart title="EEG1 Raw" values={plots.rawEeg1} color="#3b82f6" /></div>
        </div>
        <div className="chart-block signal">
          <div className="c-title">EEG (뇌파 2)</div>
          <div className="chart-card"><LineChart title="EEG2 Raw" values={plots.rawEeg2} color="#f97316" /></div>
        </div>
        <div className="chart-block signal">
          <div className="c-title">ECG (심전도)</div>
          <div className="chart-card"><LineChart title="ECG Raw" values={plots.rawEcg} color="#a855f7" /></div>
        </div>
        <div className="chart-block score">
          <div className="c-title">EEG / ECG Stress Score</div>
          <div className="chart-card"><ScoreChart plots={plots} /></div>
        </div>
      </div>
      <div className="live-foot">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <circle cx="12" cy="12" r="9.5" />
          <path d="M12 11v5" strokeLinecap="round" />
          <circle cx="12" cy="7.6" r="0.4" fill="currentColor" />
        </svg>
        안정된 자세를 유지하면 더 정확한 측정이 가능합니다.
      </div>
    </div>
  );
}
