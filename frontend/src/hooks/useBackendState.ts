import { useEffect, useRef, useState } from "react";
import { fetchState } from "../api";
import { nextMockState } from "../mock";
import type { AppState } from "../types";

const POLL_INTERVAL_MS = 400;

export interface BackendState {
  state: AppState | null;
  /** true while serving generated data because the backend is unreachable. */
  offline: boolean;
}

// Polls /api/state at the same cadence the legacy app.js used (400ms). If the
// backend is unreachable it transparently falls back to the offline mock so the
// UI keeps animating during designer preview.
export function useBackendState(): BackendState {
  const [state, setState] = useState<AppState | null>(null);
  const [offline, setOffline] = useState(false);
  const offlineRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const poll = async () => {
      try {
        const next = await fetchState(controller.signal);
        if (cancelled) return;
        setState(next);
        if (offlineRef.current) {
          offlineRef.current = false;
          setOffline(false);
        }
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        if (!offlineRef.current) {
          offlineRef.current = true;
          setOffline(true);
        }
        setState(nextMockState());
      }
    };

    void poll();
    const id = window.setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(id);
    };
  }, []);

  return { state, offline };
}
