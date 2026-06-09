import { useMemo } from "react";

interface Spark {
  size: number;
  left: number;
  top: number;
  dur: number;
  delay: number;
}

// Decorative twinkling background layer.
export function Sparkles({ count = 16 }: { count?: number }) {
  const sparks = useMemo<Spark[]>(
    () =>
      Array.from({ length: count }, () => ({
        size: 6 + Math.random() * 12,
        left: Math.random() * 100,
        top: Math.random() * 100,
        dur: 2.6 + Math.random() * 2.6,
        delay: -Math.random() * 4,
      })),
    [count],
  );

  return (
    <div id="sparkles" aria-hidden>
      {sparks.map((s, i) => (
        <div
          key={i}
          className="sparkle"
          style={{
            width: `${s.size}px`,
            height: `${s.size}px`,
            left: `${s.left}vw`,
            top: `${s.top}vh`,
            ["--dur" as string]: `${s.dur}s`,
            ["--delay" as string]: `${s.delay}s`,
          }}
        />
      ))}
    </div>
  );
}
