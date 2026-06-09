import { useEffect } from "react";
import { Actions } from "./components/Actions";
import { BaselineCard } from "./components/BaselineCard";
import { Hero } from "./components/Hero";
import { LivePanel } from "./components/LivePanel";
import { Sparkles } from "./components/Sparkles";
import { TopBar } from "./components/TopBar";
import { useBackendState } from "./hooks/useBackendState";
import { useStageScale } from "./hooks/useStageScale";
import { visualOfDisplayState } from "./visual";

export default function App() {
  const { state, offline } = useBackendState();
  const { stageRef, wrapStyle, stageStyle } = useStageScale();

  // Tint the page glow to match the current stress state.
  useEffect(() => {
    if (!state) return;
    const { glow } = visualOfDisplayState(state.current.displayState);
    document.documentElement.style.setProperty("--glow", glow);
  }, [state]);

  if (!state) {
    return (
      <>
        <Sparkles />
        <div className="boot">연결 중…</div>
      </>
    );
  }

  return (
    <>
      <Sparkles />
      <div className="stage-wrap" style={wrapStyle}>
        <div className="stage" ref={stageRef} style={stageStyle}>
          <TopBar device={state.device} measurement={state.measurement} />

          <main className="main">
            <section className="left">
              <Hero current={state.current} />
              <div className="baselines">
                <BaselineCard
                  kind="normal"
                  title="평상시 기준값 (Normal)"
                  samples={state.baseline.normalSamples}
                  active={state.flags.collectingNormal}
                />
                <BaselineCard
                  kind="stress"
                  title="스트레스 기준값 (Stress)"
                  samples={state.baseline.stressSamples}
                  active={state.flags.collectingStress}
                />
              </div>
            </section>

            <section className="right">
              <LivePanel plots={state.plots} />
            </section>
          </main>

          <Actions ui={state.ui} flags={state.flags} disabled={offline} />
        </div>
      </div>

      {offline && <div className="offline-badge">오프라인 미리보기 (백엔드 미연결)</div>}
    </>
  );
}
