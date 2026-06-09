import { useState } from "react";
import { exitController, toggleNormal, toggleStress } from "../api";
import type { Flags, UiState } from "../types";

interface ActionsProps {
  ui: UiState;
  flags: Flags;
  disabled: boolean;
}

// Bottom action bar. POSTs to the toggle/exit endpoints; the next /api/state
// poll reflects the resulting state, so we only guard against double-clicks.
export function Actions({ ui, flags, disabled }: ActionsProps) {
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    try {
      await action();
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  const normalActive = flags.collectingNormal;
  const stressActive = flags.collectingStress;

  return (
    <footer className="actions">
      <button
        className={`btn${normalActive ? " active-normal" : ""}`}
        disabled={disabled || busy || ui.normalButtonDisabled}
        onClick={() => void run(toggleNormal)}
      >
        {ui.normalButtonLabel}
      </button>
      <button
        className={`btn${stressActive ? " active-stress" : ""}`}
        disabled={disabled || busy || ui.stressButtonDisabled}
        onClick={() => void run(toggleStress)}
      >
        {ui.stressButtonLabel}
      </button>
      <button
        className="btn danger"
        disabled={disabled || busy}
        onClick={() => void run(exitController)}
      >
        종료
      </button>
    </footer>
  );
}
