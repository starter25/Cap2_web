import { useEffect, useRef, useState } from "react";

// Smoothly animates a displayed number toward `target` using an exponential
// ease, so the big stress index glides instead of snapping on every poll.
export function useCountUp(target: number | null, speed = 0.18): number | null {
  const [value, setValue] = useState<number | null>(target);
  const frame = useRef<number>(0);
  const current = useRef<number | null>(target);

  useEffect(() => {
    if (target == null) {
      current.current = null;
      setValue(null);
      return;
    }
    const step = () => {
      const from = current.current;
      if (from == null) {
        current.current = target;
        setValue(target);
        return;
      }
      const delta = target - from;
      if (Math.abs(delta) < 0.1) {
        current.current = target;
        setValue(target);
        return;
      }
      const next = from + delta * speed;
      current.current = next;
      setValue(next);
      frame.current = requestAnimationFrame(step);
    };
    frame.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame.current);
  }, [target, speed]);

  return value;
}
