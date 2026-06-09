import { useLayoutEffect, useRef, useState } from "react";

const BASE_WIDTH = 1200;

// Scales the fixed 1200px stage down to fit the viewport width (never up),
// and reports the scaled height so the wrapper reserves the right space and the
// page scrolls naturally when content overflows. Replaces the legacy fitStage.
export function useStageScale() {
  const stageRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [wrapHeight, setWrapHeight] = useState(0);

  useLayoutEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;

    const fit = () => {
      const s = Math.min(window.innerWidth / BASE_WIDTH, 1);
      setScale(s);
      setWrapHeight(stage.offsetHeight * s);
    };

    fit();
    window.addEventListener("resize", fit);
    const observer = new ResizeObserver(fit);
    observer.observe(stage);
    if (document.fonts?.ready) void document.fonts.ready.then(fit);

    return () => {
      window.removeEventListener("resize", fit);
      observer.disconnect();
    };
  }, []);

  return {
    stageRef,
    wrapStyle: { width: `${BASE_WIDTH * scale}px`, height: `${wrapHeight}px` },
    stageStyle: { transform: `scale(${scale})` },
  };
}
