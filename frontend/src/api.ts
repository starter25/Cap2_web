import type { ActionResult, AppState } from "./types";

// Fixed endpoints exposed by web_viz.backend.app. These must stay aligned with
// the FastAPI route definitions.
export async function fetchState(signal?: AbortSignal): Promise<AppState> {
  const response = await fetch("/api/state", { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(`/api/state failed: ${response.status}`);
  }
  return (await response.json()) as AppState;
}

async function postAction(path: string): Promise<ActionResult> {
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`);
  }
  return (await response.json()) as ActionResult;
}

export const toggleNormal = () => postAction("/api/normal/toggle");
export const toggleStress = () => postAction("/api/stress/toggle");
export const exitController = () => postAction("/api/exit");
