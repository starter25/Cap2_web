from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import uvicorn

from stress_model.dual_eeg_baseline.ecg_support import CURATED_ECG_MODEL_PATH, CURATED_ECG_PROFILE_PATH
from stress_model.dual_eeg_baseline.offline_inference import DEFAULT_FEATURE_COLUMNS_PATH, DEFAULT_MODEL_PATH
from stress_model.runtime.config import DEFAULT_BAUDRATE
from web_viz.backend.controller import FusionWebController


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "web_viz" / "frontend"
# The React frontend is built (vite build) into frontend/dist; that is what we
# serve in production. Run `npm run build` in web_viz/frontend to (re)generate it.
DIST_DIR = FRONTEND_DIR / "dist"

app = FastAPI(title="Stress Detection Web Viz")

controller: FusionWebController | None = None


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "controllerReady": controller is not None, "startupError": None if controller is None else controller.startup_error}


@app.get("/api/state")
def get_state() -> dict:
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller not ready")
    return controller.get_state()


@app.post("/api/normal/toggle")
def toggle_normal() -> dict:
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller not ready")
    if controller.collecting_normal_baseline:
        controller.stop_normal_baseline_collection()
        message = "Stopped normal baseline and attempted build"
    else:
        controller.start_normal_baseline_collection()
        message = "Started normal baseline collection"
    return {"ok": True, "message": message, "state": controller.get_state()}


@app.post("/api/stress/toggle")
def toggle_stress() -> dict:
    if controller is None:
        raise HTTPException(status_code=503, detail="Controller not ready")
    if controller.collecting_stress_baseline:
        controller.stop_stress_baseline_collection()
        if controller.stress_baseline_ready:
            controller.start_detection()
        message = "Stopped stress baseline and attempted calibrate"
    else:
        controller.start_stress_baseline_collection()
        message = "Started stress baseline collection"
    return {"ok": True, "message": message, "state": controller.get_state()}


@app.post("/api/exit")
def exit_controller() -> dict:
    if controller is None:
        return {"ok": True, "message": "Controller already stopped"}
    controller.close()
    return {"ok": True, "message": "Controller stopped", "state": controller.get_state()}


# Serve the built React SPA last so it only handles routes not claimed by /api.
# html=True makes "/" return index.html and provides SPA-style fallback.
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="spa")
else:
    print(f"WARNING: frontend build not found at {DIST_DIR}. Run `npm run build` in web_viz/frontend. Serving API only.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stress detection web visualization server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5080)
    parser.add_argument("--serial-port", help="Serial COM port")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--sampling-rate", type=float, default=41.7)
    parser.add_argument("--decision-mode", choices=["raw", "smoothed"], default="smoothed")
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--ecg-threshold", type=float, default=0.50)
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--feature-columns-path", default=str(DEFAULT_FEATURE_COLUMNS_PATH))
    parser.add_argument("--ecg-model-path", default=str(CURATED_ECG_MODEL_PATH))
    parser.add_argument("--ecg-profile-path", default=str(CURATED_ECG_PROFILE_PATH))
    parser.add_argument("--unity-host", default="127.0.0.1")
    parser.add_argument("--unity-bio-port", type=int, default=50210)
    parser.add_argument("--disable-unity-bio", action="store_true")
    return parser.parse_args()


def main() -> None:
    global controller
    args = parse_args()
    controller = FusionWebController(
        port=args.serial_port,
        baudrate=args.baudrate,
        sampling_rate=args.sampling_rate,
        decision_mode=args.decision_mode,
        threshold=args.threshold,
        ecg_threshold=args.ecg_threshold,
        model_path=args.model_path,
        feature_columns_path=args.feature_columns_path,
        ecg_model_path=args.ecg_model_path,
        ecg_profile_path=args.ecg_profile_path,
        unity_host=args.unity_host,
        unity_bio_port=args.unity_bio_port,
        disable_unity_bio=args.disable_unity_bio,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
