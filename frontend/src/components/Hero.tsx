import { useCountUp } from "../hooks/useCountUp";
import type { CurrentState } from "../types";
import { headlineScore, visualOfDisplayState } from "../visual";

// Mascot + status pill + big animated stress index.
export function Hero({ current }: { current: CurrentState }) {
  const visual = visualOfDisplayState(current.displayState);
  const headline = headlineScore(current.eegSmoothedScore, current.ecgSmoothedScore);
  const animated = useCountUp(headline);

  const glowVars = {
    ["--glow" as string]: visual.glow,
    ["--ring" as string]: visual.ring,
  };

  return (
    <div className="hero">
      <div className={`mascot-wrap ${visual.mood}`} style={glowVars}>
        <div className="mascot">
          <span className="eye left" />
          <span className="eye right" />
          <span className="cheek left" />
          <span className="cheek right" />
          <span className="mouth" />
        </div>
      </div>

      <div className="state-pill">{visual.label}</div>
      <div className="score-big" style={glowVars}>
        <span>{animated == null ? "--" : Math.round(animated)}</span>
        <span className="pct">%</span>
      </div>
      <div className="score-caption">스트레스 지수</div>
    </div>
  );
}
