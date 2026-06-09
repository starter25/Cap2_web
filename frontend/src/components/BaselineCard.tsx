import { baselineProgress } from "../visual";

interface BaselineCardProps {
  kind: "normal" | "stress";
  title: string;
  samples: number;
  /** highlighted while this baseline is actively being collected. */
  active: boolean;
}

const LEAF = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
    <path d="M20 4S8 3 5 11c-1.6 4.3 1 7.5 1 7.5S4.5 12 9 9c-2 3-2 6-2 6s9 1 12-7c.7-1.9 1-4 1-4z" />
  </svg>
);
const BOLT = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
    <path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" />
  </svg>
);

export function BaselineCard({ kind, title, samples, active }: BaselineCardProps) {
  const { pct, done, sub } = baselineProgress(samples);
  const className = ["baseline-card", kind, done ? "done" : "", active ? "active" : ""].filter(Boolean).join(" ");
  const iconColor = kind === "normal" ? "var(--normal-green)" : "var(--stress-orange)";

  return (
    <div className={className}>
      <div className="baseline-head">
        <span className="b-icon" style={{ color: iconColor }}>{kind === "normal" ? LEAF : BOLT}</span>
        <span className="baseline-title">{title}</span>
        <span className="check" aria-hidden>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12.5l4.5 4.5L19 7" />
          </svg>
        </span>
      </div>
      <div className="baseline-sub">{active ? "측정 중…" : sub}</div>
      <div className="progress"><span style={{ width: `${pct}%` }} /></div>
      <div className="progress-label">{pct} %</div>
    </div>
  );
}
