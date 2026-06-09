import type { DeviceState, MeasurementState } from "../types";
import { formatElapsed } from "../visual";

const SIGNAL_QUALITY_LABEL: Record<string, string> = {
  good: "좋음",
  fair: "보통",
  poor: "나쁨",
  unknown: "확인 중",
};

interface TopBarProps {
  device: DeviceState;
  measurement: MeasurementState;
}

export function TopBar({ device, measurement }: TopBarProps) {
  const liveClass = /측정\s*중/.test(measurement.stateLabel) ? "value is-live" : "value";
  return (
    <header className="topbar glass">
      <div className="status-item">
        <span className="icon sensor" aria-hidden>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12.5a10 10 0 0 1 14 0" />
            <path d="M8.5 16a5 5 0 0 1 7 0" />
            <circle cx="12" cy="19" r="0.6" fill="currentColor" stroke="none" />
          </svg>
        </span>
        <div>
          <div className="label">센서 연결</div>
          <div className="value">{device.connected ? "연결됨" : "끊김"}</div>
        </div>
      </div>

      <div className="status-item">
        <span className="icon signal" aria-hidden>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12h3l2.5-6 4 13 2.5-7H21" />
          </svg>
        </span>
        <div>
          <div className="label">신호 품질</div>
          <div className="value">{SIGNAL_QUALITY_LABEL[device.signalQuality] ?? device.signalQuality}</div>
        </div>
      </div>

      <div className="status-item">
        <span className="icon state" aria-hidden>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="8.5" />
            <path d="M12 7.5V12l3 2" />
          </svg>
        </span>
        <div>
          <div className="label">측정 상태</div>
          <div className={liveClass}>{measurement.stateLabel || "대기 중"}</div>
        </div>
      </div>

      <div className="spacer" />

      <div className="clock">
        <div className="label">측정 시간</div>
        <div className="value">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7v5l3.5 2" />
          </svg>
          <span>{formatElapsed(measurement.elapsedSec)}</span>
        </div>
      </div>
    </header>
  );
}
