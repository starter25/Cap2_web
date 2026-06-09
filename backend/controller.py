from __future__ import annotations

import csv
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import RLock, Thread
from typing import Any
import time

import numpy as np
import pandas as pd
import serial

from stress_model.dual_eeg_baseline.build_dataset import DEFAULT_SAMPLING_RATE, build_baseline_stats, transform_relative_features
from stress_model.dual_eeg_baseline.ecg_support import (
    CURATED_ECG_MODEL_PATH,
    CURATED_ECG_PROFILE_PATH,
    align_ecg_feature_frame,
    attach_ecg_delta_features,
    build_ecg_stress_profile,
    build_normal_baseline_feature_stats,
    evaluate_ecg_rule,
    load_ecg_stress_profile,
)
from stress_model.dual_eeg_baseline.haptic_logic import HapticFeedbackController
from stress_model.dual_eeg_baseline.offline_inference import (
    DEFAULT_FEATURE_COLUMNS_PATH,
    DEFAULT_MODEL_PATH,
    align_feature_frame,
    extract_probability,
    load_feature_column_config,
    load_model_artifact,
)
from stress_model.dual_eeg_baseline.realtime_gui_predictor_fusion import (
    DEFAULT_LOG_DIR,
    ECG_WINDOW_SEC,
    EEG_WINDOW_SEC,
    PLOT_POINTS,
    SCORE_BASELINE,
    SCORE_REJECT_THRESHOLD,
    SCORE_STRESS_THRESHOLD,
    SMOOTH_HISTORY,
    STRIDE_SEC,
    build_ecg_window_row,
    build_eeg_window_row,
    map_ecg_probability_to_display_score,
    map_probability_to_display_score,
    resolve_display_state,
)
from stress_model.runtime.config import DEFAULT_BAUDRATE
from stress_model.runtime.serial_utils import auto_detect_port, estimate_sampling_rate, make_output_path, parse_serial_line, prepare_serial_stream, write_capture_header
from stress_model.training.ecg_tabular_model import load_serial_ecg_model_artifact
from web_viz.backend.unity_sender import UnityBioSender


SERIAL_MAX_LINES_PER_TICK = 32
SERIAL_TEXT_BUFFER_MAX_CHARS = 8192
UNITY_SEND_INTERVAL_SEC = 1.0
UNITY_STRESS_NORMAL = 20
UNITY_STRESS_CAUTION = 40
UNITY_STRESS_STRESS = 60
UNITY_STRESS_DANGER = 80
OUTPUT_FLUSH_INTERVAL_ROWS = 100
# Live inference only ever reads the most recent window of signal, so the
# signal_eeg1/2/ecg buffers are kept bounded to avoid unbounded memory growth
# over long sessions. We keep at least this many windows of headroom and trim in
# batches (down to SIGNAL_BUFFER_KEEP_WINDOWS once SIGNAL_BUFFER_TRIM_WINDOWS is
# exceeded) so trimming is amortized O(1) per sample and never cuts into the
# active window.
SIGNAL_BUFFER_KEEP_WINDOWS = 4
SIGNAL_BUFFER_TRIM_WINDOWS = 8


class FusionWebController:
    def __init__(
        self,
        *,
        port: str | None,
        baudrate: int,
        sampling_rate: float,
        decision_mode: str,
        threshold: float,
        ecg_threshold: float,
        model_path: str,
        feature_columns_path: str,
        ecg_model_path: str,
        ecg_profile_path: str,
        unity_host: str,
        unity_bio_port: int,
        disable_unity_bio: bool,
    ) -> None:
        self.lock = RLock()
        self.running = True
        self.worker: Thread | None = None
        self.unity_worker: Thread | None = None
        self.startup_error: str | None = None

        self.args: dict[str, Any] = {
            "decision_mode": str(decision_mode),
            "threshold": float(threshold),
            "ecg_threshold": float(ecg_threshold),
        }
        self.serial_port_name: str | None = None
        self.serial_connection: serial.Serial | None = None
        self.serial_text_buffer = ""
        self.capture_path: Path | None = None
        self.capture_file = None
        self.capture_writer = None
        self.fusion_log_path: Path | None = None
        self.fusion_log_file = None
        self.fusion_log_writer = None
        self.capture_row_count = 0
        self.unity_sender: UnityBioSender | None = None
        self.unity_enabled = not bool(disable_unity_bio)
        self.last_valid_heart_rate = 0.0
        self.last_sample_received_at: float | None = None
        self.detection_started_at: float | None = None
        self.haptic_controller = HapticFeedbackController(hold_sec=5.0, cooldown_sec=10.0, command="V")
        self.haptic_status = "HAPTIC_IDLE"
        self.current_sampling_rate = float(sampling_rate)
        self.eeg_window_size = 0
        self.ecg_window_size = 0
        self.stride_samples = 0
        self._update_sampling_rate_dependent_sizes(self.current_sampling_rate)
        self.device_millis_history: deque[int] = deque(maxlen=160)

        self.collecting_normal_baseline = False
        self.collecting_stress_baseline = False
        self.detection_running = False
        self.normal_baseline_ready = False
        self.stress_baseline_ready = False

        self.signal_eeg1: list[float] = []
        self.signal_eeg2: list[float] = []
        self.signal_ecg: list[float] = []
        self.normal_baseline_eeg1: list[float] = []
        self.normal_baseline_eeg2: list[float] = []
        self.normal_baseline_ecg: list[float] = []
        self.stress_baseline_eeg1: list[float] = []
        self.stress_baseline_eeg2: list[float] = []
        self.stress_baseline_ecg: list[float] = []

        self.normal_baseline_stats_map: dict[str, dict[str, float]] = {}
        self.normal_ecg_feature_stats: dict[str, float] = {}
        self.personal_ecg_stress_profile: dict[str, Any] | None = None
        self.eeg_normal_scores: list[float] = []
        self.eeg_stress_scores: list[float] = []
        self.ecg_normal_scores: list[float] = []
        self.ecg_stress_scores: list[float] = []
        self.eeg_personalized_threshold = float(threshold)
        self.ecg_personalized_threshold = float(ecg_threshold)
        self.eeg_normal_score_mean = np.nan
        self.eeg_stress_score_mean = np.nan
        self.ecg_normal_score_mean = np.nan
        self.ecg_stress_score_mean = np.nan
        self.normal_hr_mean = np.nan
        self.stress_hr_mean = np.nan
        self.normal_rmssd_mean = np.nan
        self.stress_rmssd_mean = np.nan
        self.eeg_prob_history: deque[float] = deque(maxlen=SMOOTH_HISTORY)
        self.ecg_prob_history: deque[float] = deque(maxlen=SMOOTH_HISTORY)

        self.raw_plot_eeg1: deque[float] = deque(maxlen=PLOT_POINTS)
        self.raw_plot_eeg2: deque[float] = deque(maxlen=PLOT_POINTS)
        self.raw_plot_ecg: deque[float] = deque(maxlen=PLOT_POINTS)
        self.eeg_score_plot_smooth: deque[float] = deque(maxlen=PLOT_POINTS)
        self.ecg_score_plot_smooth: deque[float] = deque(maxlen=PLOT_POINTS)

        self.current_state_text = "READY"
        self.current_eeg_quality = "-"
        self.current_ecg_quality = "-"
        self.current_eeg_probability = np.nan
        self.current_eeg_smoothed_probability = np.nan
        self.current_eeg_score = np.nan
        self.current_eeg_smoothed_score = np.nan
        self.current_ecg_probability = np.nan
        self.current_ecg_smoothed_probability = np.nan
        self.current_ecg_score = np.nan
        self.current_ecg_smoothed_score = np.nan
        self.current_eeg_final = "IDLE"
        self.current_ecg_final = "IDLE"
        self.current_fusion_final = "IDLE"
        self.current_display_state = "IDLE"
        self.current_ecg_rule_text = "-"
        self.current_ecg_rule_status = "IDLE"
        self.current_eeg1 = np.nan
        self.current_eeg2 = np.nan
        self.current_ecg = np.nan
        self.current_hr_bpm = np.nan
        self.current_rmssd_ms = np.nan
        self.last_infer_cursor = 0

        artifact = load_model_artifact(Path(model_path).resolve())
        feature_config = load_feature_column_config(Path(feature_columns_path).resolve())
        self.eeg_model = artifact["model"]
        self.base_feature_columns = feature_config.get("base_feature_columns", artifact.get("base_feature_columns", []))
        if not self.base_feature_columns:
            raise ValueError("No base EEG feature columns were found in feature_columns.json or model artifact")

        ecg_artifact = load_serial_ecg_model_artifact(Path(ecg_model_path).resolve())
        self.ecg_model = ecg_artifact["model"]
        self.ecg_feature_columns = list(ecg_artifact["feature_columns"])
        ecg_classes = getattr(self.ecg_model, "classes_", np.asarray([0, 1]))
        self.ecg_positive_class_index = list(ecg_classes).index(1)
        self.ecg_stress_profile = load_ecg_stress_profile(Path(ecg_profile_path).resolve())

        try:
            self.serial_port_name = port or auto_detect_port()
            self.serial_connection = serial.Serial(self.serial_port_name, baudrate, timeout=0)
            prepare_serial_stream(self.serial_connection)
            self.current_state_text = f"SERIAL_READY {self.serial_port_name}"
        except Exception as exc:
            self.startup_error = str(exc)
            self.current_state_text = f"SERIAL_ERROR {exc}"
            self.running = False
            return

        try:
            self._open_output_logs()
        except Exception as exc:
            self.startup_error = str(exc)
            self.current_state_text = f"OUTPUT_ERROR {exc}"
            self.running = False
            try:
                if self.serial_connection is not None and self.serial_connection.is_open:
                    self.serial_connection.close()
            except Exception:
                pass
            return

        if self.unity_enabled:
            try:
                self.unity_sender = UnityBioSender(unity_host, unity_bio_port)
            except Exception as exc:
                self.startup_error = str(exc) if self.startup_error is None else f"{self.startup_error} | unity={exc}"
                self.unity_enabled = False

        self.worker = Thread(target=self._run_loop, daemon=True)
        self.worker.start()
        if self.unity_enabled and self.unity_sender is not None:
            self.unity_worker = Thread(target=self._run_unity_loop, daemon=True)
            self.unity_worker.start()

    def _open_output_logs(self) -> None:
        self.capture_path = make_output_path(None)
        self.capture_path.parent.mkdir(parents=True, exist_ok=True)
        self.capture_file = self.capture_path.open("w", newline="", encoding="utf-8")
        self.capture_writer = csv.writer(self.capture_file)
        write_capture_header(self.capture_writer)
        self.capture_file.flush()

        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.fusion_log_path = DEFAULT_LOG_DIR / f"realtime_fusion_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.fusion_log_file = self.fusion_log_path.open("w", newline="", encoding="utf-8")
        self.fusion_log_writer = csv.writer(self.fusion_log_file)
        self.fusion_log_writer.writerow([
            "timestamp",
            "eeg1",
            "eeg2",
            "ecg",
            "eeg_quality",
            "eeg_probability",
            "eeg_smoothed_probability",
            "eeg_final",
            "ecg_quality",
            "ecg_probability",
            "ecg_smoothed_probability",
            "ecg_final",
            "fusion_final",
        ])
        self.fusion_log_file.flush()

        print(f"Saving raw capture CSV: {self.capture_path}")
        print(f"Saving fusion log CSV: {self.fusion_log_path}")

    def _write_raw_capture_row(
        self,
        *,
        received_at: str,
        device_millis: int | None,
        ecg_value: int,
        eeg_value: int,
        eeg1_value: int,
        eeg2_value: int,
    ) -> None:
        if self.capture_writer is None:
            return
        self.capture_writer.writerow([
            received_at,
            self.capture_row_count,
            device_millis,
            ecg_value,
            eeg_value,
            eeg1_value,
            eeg2_value,
        ])
        self.capture_row_count += 1

    def _write_fusion_log_row(self, timestamp: str) -> None:
        if self.fusion_log_writer is None:
            return
        self.fusion_log_writer.writerow([
            timestamp,
            self.current_eeg1,
            self.current_eeg2,
            self.current_ecg,
            self.current_eeg_quality,
            "" if not np.isfinite(self.current_eeg_probability) else f"{self.current_eeg_probability:.6f}",
            "" if not np.isfinite(self.current_eeg_smoothed_probability) else f"{self.current_eeg_smoothed_probability:.6f}",
            self.current_eeg_final,
            self.current_ecg_quality,
            "" if not np.isfinite(self.current_ecg_probability) else f"{self.current_ecg_probability:.6f}",
            "" if not np.isfinite(self.current_ecg_smoothed_probability) else f"{self.current_ecg_smoothed_probability:.6f}",
            self.current_ecg_final,
            self.current_fusion_final,
        ])

    def _flush_output_logs_if_needed(self) -> None:
        if self.capture_row_count == 0 or (self.capture_row_count % OUTPUT_FLUSH_INTERVAL_ROWS) != 0:
            return
        if self.capture_file is not None:
            self.capture_file.flush()
        if self.fusion_log_file is not None:
            self.fusion_log_file.flush()

    def _close_output_logs(self) -> None:
        try:
            if self.capture_file is not None:
                self.capture_file.flush()
                self.capture_file.close()
        except Exception:
            pass
        finally:
            self.capture_file = None
            self.capture_writer = None

        try:
            if self.fusion_log_file is not None:
                self.fusion_log_file.flush()
                self.fusion_log_file.close()
        except Exception:
            pass
        finally:
            self.fusion_log_file = None
            self.fusion_log_writer = None

    def _update_sampling_rate_dependent_sizes(self, new_sampling_rate: float) -> None:
        self.current_sampling_rate = float(new_sampling_rate)
        self.eeg_window_size = max(1, int(round(EEG_WINDOW_SEC * self.current_sampling_rate)))
        self.ecg_window_size = max(1, int(round(ECG_WINDOW_SEC * self.current_sampling_rate)))
        self.stride_samples = max(1, int(round(STRIDE_SEC * self.current_sampling_rate)))

    def _predict_probabilities_for_eeg_df(self, absolute_df: pd.DataFrame) -> np.ndarray:
        relative_df = transform_relative_features(absolute_df, self.normal_baseline_stats_map)
        X = align_feature_frame(relative_df, self.base_feature_columns)
        return extract_probability(self.eeg_model, X)

    def _predict_probabilities_for_ecg_df(self, ecg_df: pd.DataFrame) -> np.ndarray:
        X = align_ecg_feature_frame(ecg_df, self.ecg_feature_columns, self.normal_ecg_feature_stats)
        probabilities = self.ecg_model.predict_proba(X)
        return probabilities[:, self.ecg_positive_class_index]

    def _build_eeg_rows_from_buffers(self, eeg1_buffer: list[float], eeg2_buffer: list[float]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for start in range(0, len(eeg1_buffer) - self.eeg_window_size + 1, self.stride_samples):
            end = start + self.eeg_window_size
            rows.append(
                build_eeg_window_row(
                    raw_eeg1_window=np.asarray(eeg1_buffer[start:end], dtype=np.float64),
                    raw_eeg2_window=np.asarray(eeg2_buffer[start:end], dtype=np.float64),
                    sampling_rate=self.current_sampling_rate,
                    source_path=Path("serial_live.csv"),
                    window_start_sec=start / self.current_sampling_rate,
                    window_end_sec=end / self.current_sampling_rate,
                )
            )
        return pd.DataFrame(rows)

    def _build_ecg_rows_from_buffer(self, ecg_buffer: list[float]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for start in range(0, len(ecg_buffer) - self.ecg_window_size + 1, self.stride_samples):
            end = start + self.ecg_window_size
            rows.append(
                build_ecg_window_row(
                    raw_ecg_window=np.asarray(ecg_buffer[start:end], dtype=np.float64),
                    sampling_rate=self.current_sampling_rate,
                    window_start_sec=start / self.current_sampling_rate,
                    window_end_sec=end / self.current_sampling_rate,
                )
            )
        return pd.DataFrame(rows)

    def _recompute_eeg_personalized_threshold(self) -> None:
        if len(self.eeg_normal_scores) == 0 or len(self.eeg_stress_scores) == 0:
            self.eeg_personalized_threshold = float(self.args["threshold"])
            return
        normal_scores = np.asarray(self.eeg_normal_scores, dtype=np.float64)
        stress_scores = np.asarray(self.eeg_stress_scores, dtype=np.float64)
        normal_p90 = float(np.percentile(normal_scores, 90.0))
        stress_p25 = float(np.percentile(stress_scores, 25.0))
        self.eeg_personalized_threshold = float(max(0.0, min(1.0, (normal_p90 + stress_p25) * 0.5)))
        self.eeg_normal_score_mean = float(np.mean(normal_scores))
        self.eeg_stress_score_mean = float(np.mean(stress_scores))

    def _recompute_ecg_personalized_threshold(self) -> None:
        if len(self.ecg_normal_scores) == 0 or len(self.ecg_stress_scores) == 0:
            self.ecg_personalized_threshold = float(self.args["ecg_threshold"])
            return
        normal_scores = np.asarray(self.ecg_normal_scores, dtype=np.float64)
        stress_scores = np.asarray(self.ecg_stress_scores, dtype=np.float64)
        normal_p90 = float(np.percentile(normal_scores, 90.0))
        stress_p25 = float(np.percentile(stress_scores, 25.0))
        self.ecg_personalized_threshold = float(max(0.0, min(1.0, (normal_p90 + stress_p25) * 0.5)))
        self.ecg_normal_score_mean = float(np.mean(normal_scores))
        self.ecg_stress_score_mean = float(np.mean(stress_scores))

    def _reset_probabilities(self) -> None:
        self.eeg_prob_history.clear()
        self.ecg_prob_history.clear()
        self.current_eeg_probability = np.nan
        self.current_eeg_smoothed_probability = np.nan
        self.current_eeg_score = np.nan
        self.current_eeg_smoothed_score = np.nan
        self.current_ecg_probability = np.nan
        self.current_ecg_smoothed_probability = np.nan
        self.current_ecg_score = np.nan
        self.current_ecg_smoothed_score = np.nan
        self.current_eeg_final = "IDLE"
        self.current_ecg_final = "IDLE"
        self.current_fusion_final = "IDLE"
        self.current_eeg_quality = "-"
        self.current_ecg_quality = "-"
        self.current_ecg_rule_text = "-"
        self.current_ecg_rule_status = "IDLE"
        self.current_hr_bpm = np.nan
        self.current_rmssd_ms = np.nan

    def start_normal_baseline_collection(self) -> None:
        with self.lock:
            self.haptic_controller.reset("HAPTIC_IDLE")
            self.haptic_status = self.haptic_controller.status
            self.collecting_normal_baseline = True
            self.collecting_stress_baseline = False
            self.detection_running = False
            self.normal_baseline_ready = False
            self.stress_baseline_ready = False
            self.normal_baseline_stats_map = {}
            self.eeg_normal_scores = []
            self.eeg_stress_scores = []
            self.ecg_normal_scores = []
            self.ecg_stress_scores = []
            self.eeg_personalized_threshold = float(self.args["threshold"])
            self.ecg_personalized_threshold = float(self.args["ecg_threshold"])
            self.normal_ecg_feature_stats = {}
            self.personal_ecg_stress_profile = None
            self.eeg_normal_score_mean = np.nan
            self.eeg_stress_score_mean = np.nan
            self.ecg_normal_score_mean = np.nan
            self.ecg_stress_score_mean = np.nan
            self.normal_hr_mean = np.nan
            self.stress_hr_mean = np.nan
            self.normal_rmssd_mean = np.nan
            self.stress_rmssd_mean = np.nan
            self.normal_baseline_eeg1.clear()
            self.normal_baseline_eeg2.clear()
            self.normal_baseline_ecg.clear()
            self._reset_probabilities()
            self.current_state_text = "COLLECTING_NORMAL_BASELINE"

    def stop_normal_baseline_collection(self) -> None:
        with self.lock:
            self.collecting_normal_baseline = False
            if len(self.normal_baseline_eeg1) < self.eeg_window_size or len(self.normal_baseline_eeg2) < self.eeg_window_size or len(self.normal_baseline_ecg) < self.ecg_window_size:
                self.current_state_text = "NORMAL_BASELINE_TOO_SHORT"
                self.current_fusion_final = "IDLE"
                return
            eeg_baseline_df = self._build_eeg_rows_from_buffers(self.normal_baseline_eeg1, self.normal_baseline_eeg2)
            usable_eeg_df = eeg_baseline_df[eeg_baseline_df["quality_bucket"].isin(["good", "warning"])].copy()
            if usable_eeg_df.empty:
                self.current_state_text = "NORMAL_EEG_BASELINE_BAD_QUALITY"
                self.current_fusion_final = "IDLE"
                return
            ecg_baseline_df = self._build_ecg_rows_from_buffer(self.normal_baseline_ecg)
            usable_ecg_df = ecg_baseline_df[ecg_baseline_df["quality_bucket"].isin(["good", "warning"])].copy()
            if usable_ecg_df.empty:
                self.current_state_text = "NORMAL_ECG_BASELINE_BAD_QUALITY"
                self.current_fusion_final = "IDLE"
                return
            self.normal_ecg_feature_stats = build_normal_baseline_feature_stats(usable_ecg_df)
            if not self.normal_ecg_feature_stats:
                self.current_state_text = "NORMAL_ECG_BASELINE_NO_FEATURES"
                self.current_fusion_final = "IDLE"
                return
            self.normal_baseline_stats_map, _ = build_baseline_stats(usable_eeg_df)
            self.eeg_normal_scores = [float(value) for value in self._predict_probabilities_for_eeg_df(usable_eeg_df) if np.isfinite(value)]
            self.ecg_normal_scores = [float(value) for value in self._predict_probabilities_for_ecg_df(usable_ecg_df) if np.isfinite(value)]
            if not self.eeg_normal_scores or not self.ecg_normal_scores:
                self.current_state_text = "NORMAL_BASELINE_NO_SCORES"
                self.current_fusion_final = "IDLE"
                return
            self.normal_baseline_ready = True
            self.eeg_normal_score_mean = float(np.mean(np.asarray(self.eeg_normal_scores, dtype=np.float64)))
            self.ecg_normal_score_mean = float(np.mean(np.asarray(self.ecg_normal_scores, dtype=np.float64)))
            self.normal_hr_mean = float(pd.to_numeric(usable_ecg_df["ecg_heart_rate_bpm"], errors="coerce").dropna().mean()) if usable_ecg_df["ecg_heart_rate_bpm"].notna().any() else np.nan
            self.normal_rmssd_mean = float(pd.to_numeric(usable_ecg_df["ecg_rmssd_ms"], errors="coerce").dropna().mean()) if usable_ecg_df["ecg_rmssd_ms"].notna().any() else np.nan
            self.current_eeg_final = "NORMAL"
            self.current_ecg_final = "NORMAL"
            self.current_fusion_final = "NORMAL"
            self.current_state_text = "NORMAL_BASELINE_READY"

    def start_stress_baseline_collection(self) -> None:
        with self.lock:
            self.haptic_controller.reset("HAPTIC_IDLE")
            self.haptic_status = self.haptic_controller.status
            if not self.normal_baseline_ready:
                self.current_state_text = "NO_NORMAL_BASELINE"
                self.current_fusion_final = "IDLE"
                return
            self.collecting_stress_baseline = True
            self.collecting_normal_baseline = False
            self.detection_running = False
            self.stress_baseline_ready = False
            self.eeg_stress_scores = []
            self.ecg_stress_scores = []
            self.stress_baseline_eeg1.clear()
            self.stress_baseline_eeg2.clear()
            self.stress_baseline_ecg.clear()
            self._reset_probabilities()
            self.current_state_text = "COLLECTING_STRESS_BASELINE"

    def stop_stress_baseline_collection(self) -> None:
        with self.lock:
            self.collecting_stress_baseline = False
            if not self.normal_baseline_ready:
                self.current_state_text = "NO_NORMAL_BASELINE"
                self.current_fusion_final = "IDLE"
                return
            if len(self.stress_baseline_eeg1) < self.eeg_window_size or len(self.stress_baseline_eeg2) < self.eeg_window_size or len(self.stress_baseline_ecg) < self.ecg_window_size:
                self.current_state_text = "STRESS_BASELINE_TOO_SHORT"
                self.current_fusion_final = "IDLE"
                return
            eeg_stress_df = self._build_eeg_rows_from_buffers(self.stress_baseline_eeg1, self.stress_baseline_eeg2)
            usable_eeg_df = eeg_stress_df[eeg_stress_df["quality_bucket"].isin(["good", "warning"])].copy()
            if usable_eeg_df.empty:
                self.current_state_text = "STRESS_EEG_BASELINE_BAD_QUALITY"
                self.current_fusion_final = "IDLE"
                return
            ecg_stress_df = self._build_ecg_rows_from_buffer(self.stress_baseline_ecg)
            usable_ecg_df = ecg_stress_df[ecg_stress_df["quality_bucket"].isin(["good", "warning"])].copy()
            if usable_ecg_df.empty:
                self.current_state_text = "STRESS_ECG_BASELINE_BAD_QUALITY"
                self.current_fusion_final = "IDLE"
                return
            self.eeg_stress_scores = [float(value) for value in self._predict_probabilities_for_eeg_df(usable_eeg_df) if np.isfinite(value)]
            self.ecg_stress_scores = [float(value) for value in self._predict_probabilities_for_ecg_df(usable_ecg_df) if np.isfinite(value)]
            if not self.eeg_stress_scores or not self.ecg_stress_scores:
                self.current_state_text = "STRESS_BASELINE_NO_SCORES"
                self.current_fusion_final = "IDLE"
                return
            personal_stress_df = attach_ecg_delta_features(usable_ecg_df, self.normal_ecg_feature_stats)
            self.personal_ecg_stress_profile = build_ecg_stress_profile(
                personal_stress_df,
                lower_quantile=float(self.ecg_stress_profile.get("lower_quantile", 0.01)),
                upper_quantile=float(self.ecg_stress_profile.get("upper_quantile", 0.99)),
                direction_min_votes=int(self.ecg_stress_profile.get("direction_min_votes", 2)),
                range_min_votes=int(self.ecg_stress_profile.get("range_min_votes", 2)),
                included_sessions=["live_personal_stress_baseline"],
                excluded_sessions=[],
            )
            self.personal_ecg_stress_profile["baseline_stats_by_subject"] = {"live": dict(self.normal_ecg_feature_stats)}
            self.stress_baseline_ready = True
            self._recompute_eeg_personalized_threshold()
            self._recompute_ecg_personalized_threshold()
            self.stress_hr_mean = float(pd.to_numeric(usable_ecg_df["ecg_heart_rate_bpm"], errors="coerce").dropna().mean()) if usable_ecg_df["ecg_heart_rate_bpm"].notna().any() else np.nan
            self.stress_rmssd_mean = float(pd.to_numeric(usable_ecg_df["ecg_rmssd_ms"], errors="coerce").dropna().mean()) if usable_ecg_df["ecg_rmssd_ms"].notna().any() else np.nan
            self.current_eeg_final = "NORMAL"
            self.current_ecg_final = "NORMAL"
            self.current_fusion_final = "NORMAL"
            self.current_state_text = "STRESS_BASELINE_READY"

    def start_detection(self) -> None:
        with self.lock:
            self.haptic_controller.reset("HAPTIC_IDLE")
            self.haptic_status = self.haptic_controller.status
            if not self.normal_baseline_ready:
                self.current_state_text = "NO_NORMAL_BASELINE"
                self.current_fusion_final = "IDLE"
                return
            if not self.stress_baseline_ready:
                self.current_state_text = "NO_STRESS_BASELINE"
                self.current_fusion_final = "IDLE"
                return
            self.detection_running = True
            self.collecting_normal_baseline = False
            self.collecting_stress_baseline = False
            if self.detection_started_at is None:
                self.detection_started_at = time.time()
            self._reset_probabilities()
            self.last_infer_cursor = max(0, len(self.signal_eeg1) - self.stride_samples)
            self.current_state_text = "DETECTING"

    def stop_detection(self) -> None:
        with self.lock:
            self.haptic_controller.reset("HAPTIC_IDLE")
            self.haptic_status = self.haptic_controller.status
            self.detection_running = False
            self.current_state_text = "DETECTION_STOPPED"

    def _infer_current_window(self) -> None:
        eeg_end = len(self.signal_eeg1)
        eeg_start = eeg_end - self.eeg_window_size
        eeg_row = build_eeg_window_row(
            raw_eeg1_window=np.asarray(self.signal_eeg1[eeg_start:eeg_end], dtype=np.float64),
            raw_eeg2_window=np.asarray(self.signal_eeg2[eeg_start:eeg_end], dtype=np.float64),
            sampling_rate=self.current_sampling_rate,
            source_path=Path("serial_live.csv"),
            window_start_sec=eeg_start / self.current_sampling_rate,
            window_end_sec=eeg_end / self.current_sampling_rate,
        )
        self.current_eeg_quality = str(eeg_row["quality_bucket"])
        if self.current_eeg_quality == "bad":
            self.current_eeg_probability = np.nan
            self.current_eeg_smoothed_probability = np.nan if len(self.eeg_prob_history) == 0 else float(np.mean(np.asarray(self.eeg_prob_history, dtype=np.float64)))
            self.current_eeg_score = np.nan
            self.current_eeg_smoothed_score = np.nan if not np.isfinite(self.current_eeg_smoothed_probability) else map_probability_to_display_score(self.current_eeg_smoothed_probability, self.eeg_normal_score_mean, self.eeg_personalized_threshold, self.eeg_stress_score_mean)
            self.current_eeg_final = "BAD_QUALITY"
        else:
            eeg_relative_df = transform_relative_features(pd.DataFrame([eeg_row]), self.normal_baseline_stats_map)
            eeg_probability = float(extract_probability(self.eeg_model, align_feature_frame(eeg_relative_df, self.base_feature_columns))[0])
            self.current_eeg_probability = eeg_probability
            self.eeg_prob_history.append(eeg_probability)
            self.current_eeg_smoothed_probability = float(np.mean(np.asarray(self.eeg_prob_history, dtype=np.float64)))
            self.current_eeg_score = map_probability_to_display_score(self.current_eeg_probability, self.eeg_normal_score_mean, self.eeg_personalized_threshold, self.eeg_stress_score_mean)
            self.current_eeg_smoothed_score = map_probability_to_display_score(self.current_eeg_smoothed_probability, self.eeg_normal_score_mean, self.eeg_personalized_threshold, self.eeg_stress_score_mean)
            eeg_decision = self.current_eeg_probability if self.args["decision_mode"] == "raw" else self.current_eeg_smoothed_probability
            self.current_eeg_final = "STRESS" if eeg_decision >= float(self.eeg_personalized_threshold) else "NORMAL"

        ecg_end = len(self.signal_ecg)
        ecg_start = ecg_end - self.ecg_window_size
        ecg_row = build_ecg_window_row(
            raw_ecg_window=np.asarray(self.signal_ecg[ecg_start:ecg_end], dtype=np.float64),
            sampling_rate=self.current_sampling_rate,
            window_start_sec=ecg_start / self.current_sampling_rate,
            window_end_sec=ecg_end / self.current_sampling_rate,
        )
        self.current_ecg_quality = str(ecg_row["quality_bucket"])
        self.current_hr_bpm = float(ecg_row["ecg_heart_rate_bpm"]) if np.isfinite(ecg_row["ecg_heart_rate_bpm"]) else np.nan
        self.current_rmssd_ms = float(ecg_row["ecg_rmssd_ms"]) if np.isfinite(ecg_row["ecg_rmssd_ms"]) else np.nan
        if self.current_ecg_quality == "bad":
            self.current_ecg_probability = np.nan
            self.current_ecg_smoothed_probability = np.nan if len(self.ecg_prob_history) == 0 else float(np.mean(np.asarray(self.ecg_prob_history, dtype=np.float64)))
            self.current_ecg_score = np.nan
            self.current_ecg_smoothed_score = np.nan if not np.isfinite(self.current_ecg_smoothed_probability) else map_ecg_probability_to_display_score(self.current_ecg_smoothed_probability, self.ecg_normal_score_mean, self.ecg_personalized_threshold, "BAD_QUALITY")
            self.current_ecg_final = "BAD_QUALITY"
            self.current_ecg_rule_text = "bad_quality"
            self.current_ecg_rule_status = "BAD_QUALITY"
        else:
            ecg_probability = float(self._predict_probabilities_for_ecg_df(pd.DataFrame([ecg_row]))[0])
            self.current_ecg_probability = ecg_probability
            self.ecg_prob_history.append(ecg_probability)
            self.current_ecg_smoothed_probability = float(np.mean(np.asarray(self.ecg_prob_history, dtype=np.float64)))
            ecg_decision = self.current_ecg_probability if self.args["decision_mode"] == "raw" else self.current_ecg_smoothed_probability
            active_ecg_profile = self.personal_ecg_stress_profile or self.ecg_stress_profile
            profile_source = "personal" if self.personal_ecg_stress_profile is not None else "global"
            rule_result = evaluate_ecg_rule(
                ecg_row,
                baseline_stats=self.normal_ecg_feature_stats,
                stress_profile=active_ecg_profile,
            ) if self.normal_ecg_feature_stats else {"status": "UNCERTAIN", "direction_vote_count": 0, "direction_min_votes": 2, "range_pass": False}
            vote_count = int(rule_result.get("direction_vote_count", 0))
            min_votes = int(rule_result.get("direction_min_votes", 2))
            range_pass = bool(rule_result.get("range_pass", False))
            self.current_ecg_rule_status = str(rule_result.get("status", "UNCERTAIN"))
            self.current_ecg_rule_text = f"{profile_source} votes={vote_count}/{min_votes} range={'pass' if range_pass else 'fail'}"
            self.current_ecg_score = map_ecg_probability_to_display_score(self.current_ecg_probability, self.ecg_normal_score_mean, self.ecg_personalized_threshold, self.current_ecg_rule_status)
            self.current_ecg_smoothed_score = map_ecg_probability_to_display_score(self.current_ecg_smoothed_probability, self.ecg_normal_score_mean, self.ecg_personalized_threshold, self.current_ecg_rule_status)
            if ecg_decision < float(self.ecg_personalized_threshold):
                self.current_ecg_final = "NORMAL"
            else:
                self.current_ecg_final = self.current_ecg_rule_status

        if self.current_eeg_final == "BAD_QUALITY":
            self.current_fusion_final = "UNCERTAIN"
        elif self.current_eeg_final != "STRESS":
            self.current_fusion_final = "NORMAL"
        elif self.current_ecg_final == "STRESS_SUPPORTED":
            self.current_fusion_final = "STRESS"
        elif self.current_ecg_final == "REJECT_OTHER":
            self.current_fusion_final = "NOT_STRESS_OTHER_ACTIVATION"
        elif self.current_ecg_final in {"BAD_QUALITY", "UNCERTAIN"}:
            self.current_fusion_final = "UNCERTAIN"
        else:
            self.current_fusion_final = "NORMAL"
        self.current_display_state = resolve_display_state(self.current_eeg_smoothed_score, self.current_ecg_smoothed_score, self.current_ecg_rule_status)
        self._update_haptic_logic()

    def _trim_signal_buffers(self) -> None:
        # Drop the oldest samples once the buffer grows well past what inference
        # needs, adjusting the inference cursor by the same amount so detection
        # behavior is unchanged (the cursor is just "length at last inference").
        unit = max(self.eeg_window_size, self.ecg_window_size) + self.stride_samples
        if len(self.signal_eeg1) <= unit * SIGNAL_BUFFER_TRIM_WINDOWS:
            return
        excess = len(self.signal_eeg1) - unit * SIGNAL_BUFFER_KEEP_WINDOWS
        del self.signal_eeg1[:excess]
        del self.signal_eeg2[:excess]
        del self.signal_ecg[:excess]
        self.last_infer_cursor = max(0, self.last_infer_cursor - excess)

    def _append_sample(self, eeg1_value: float, eeg2_value: float, ecg_value: float, received_at: str) -> None:
        self.last_sample_received_at = time.time()
        self.signal_eeg1.append(float(eeg1_value))
        self.signal_eeg2.append(float(eeg2_value))
        self.signal_ecg.append(float(ecg_value))
        self._trim_signal_buffers()
        self.raw_plot_eeg1.append(float(eeg1_value))
        self.raw_plot_eeg2.append(float(eeg2_value))
        self.raw_plot_ecg.append(float(ecg_value))
        self.current_eeg1 = float(eeg1_value)
        self.current_eeg2 = float(eeg2_value)
        self.current_ecg = float(ecg_value)
        if self.collecting_normal_baseline:
            self.normal_baseline_eeg1.append(float(eeg1_value))
            self.normal_baseline_eeg2.append(float(eeg2_value))
            self.normal_baseline_ecg.append(float(ecg_value))
        if self.collecting_stress_baseline:
            self.stress_baseline_eeg1.append(float(eeg1_value))
            self.stress_baseline_eeg2.append(float(eeg2_value))
            self.stress_baseline_ecg.append(float(ecg_value))
        if self.detection_running and self.normal_baseline_ready and self.stress_baseline_ready:
            if len(self.signal_eeg1) >= self.eeg_window_size and len(self.signal_ecg) >= self.ecg_window_size:
                if (len(self.signal_eeg1) - self.last_infer_cursor) >= self.stride_samples:
                    self._infer_current_window()
                    self.last_infer_cursor = len(self.signal_eeg1)
        self.eeg_score_plot_smooth.append(np.nan if not np.isfinite(self.current_eeg_smoothed_score) else float(self.current_eeg_smoothed_score))
        self.ecg_score_plot_smooth.append(np.nan if not np.isfinite(self.current_ecg_smoothed_score) else float(self.current_ecg_smoothed_score))
        self._write_fusion_log_row(received_at)
        self._flush_output_logs_if_needed()

    def _update_haptic_logic(self) -> None:
        serial_ready = self.serial_connection is not None and self.serial_connection.is_open
        active = self.detection_running and self.current_display_state in {"stress", "danger"}
        should_send, command, status = self.haptic_controller.update(active=active, serial_ready=serial_ready, now_monotonic=time.monotonic())
        self.haptic_status = status
        if not should_send or command is None:
            return
        try:
            assert self.serial_connection is not None
            self.serial_connection.write(command.encode("ascii"))
            self.serial_connection.flush()
        except Exception as exc:
            self.haptic_status = f"HAPTIC_SEND_ERROR {exc}"

    def _resolve_unity_levels(self) -> tuple[str, str]:
        eeg_score = self.current_eeg_smoothed_score
        ecg_score = self.current_ecg_smoothed_score
        if not np.isfinite(eeg_score):
            eeg_level = "low"
        elif float(eeg_score) >= 80.0:
            eeg_level = "high"
        elif float(eeg_score) >= 60.0:
            eeg_level = "mid"
        else:
            eeg_level = "low"

        if self.current_ecg_rule_status == "REJECT_OTHER":
            ecg_level = "high"
        elif not np.isfinite(ecg_score):
            ecg_level = "low"
        elif float(ecg_score) >= 80.0:
            ecg_level = "high"
        elif float(ecg_score) >= 60.0:
            ecg_level = "mid"
        else:
            ecg_level = "low"
        return eeg_level, ecg_level

    def _resolve_unity_state(self) -> str:
        eeg_level, ecg_level = self._resolve_unity_levels()
        if eeg_level == "low":
            return "stress" if ecg_level == "mid" else "normal"
        return "danger" if ecg_level == "mid" else "stress"

    def _resolve_unity_stress_value(self) -> int:
        eeg_level, ecg_level = self._resolve_unity_levels()
        if ecg_level == "high":
            if eeg_level == "low":
                return UNITY_STRESS_CAUTION
            return UNITY_STRESS_STRESS
        if ecg_level == "mid":
            if eeg_level == "low":
                return UNITY_STRESS_STRESS
            return UNITY_STRESS_DANGER
        if eeg_level == "low":
            return UNITY_STRESS_NORMAL
        if eeg_level == "mid":
            return UNITY_STRESS_STRESS
        return UNITY_STRESS_CAUTION

    def _build_unity_payload(self) -> dict[str, Any]:
        if np.isfinite(self.current_hr_bpm):
            self.last_valid_heart_rate = float(self.current_hr_bpm)
        state = self._resolve_unity_state()
        stress = self._resolve_unity_stress_value()
        return {
            "heartRate": round(float(self.last_valid_heart_rate), 2),
            "state": state,
            "stress": stress,
        }

    def _poll_serial_once(self) -> None:
        if self.serial_connection is None:
            return
        bytes_available = int(self.serial_connection.in_waiting)
        if bytes_available <= 0:
            return
        chunk = self.serial_connection.read(bytes_available).decode("utf-8", errors="ignore")
        if not chunk:
            return
        self.serial_text_buffer += chunk
        if len(self.serial_text_buffer) > SERIAL_TEXT_BUFFER_MAX_CHARS:
            newline_index = self.serial_text_buffer.rfind("\n")
            if newline_index >= 0:
                self.serial_text_buffer = self.serial_text_buffer[max(0, newline_index - (SERIAL_TEXT_BUFFER_MAX_CHARS // 2)):]
            else:
                self.serial_text_buffer = self.serial_text_buffer[-(SERIAL_TEXT_BUFFER_MAX_CHARS // 2):]
        processed_lines = 0
        while processed_lines < SERIAL_MAX_LINES_PER_TICK and "\n" in self.serial_text_buffer:
            line, self.serial_text_buffer = self.serial_text_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                processed_lines += 1
                continue
            parsed = parse_serial_line(line)
            if parsed is None or parsed.get("eeg1") is None or parsed.get("eeg2") is None or parsed.get("ecg") is None:
                processed_lines += 1
                continue
            device_millis = parsed.get("device_millis")
            if device_millis is not None:
                self.device_millis_history.append(int(device_millis))
                estimated_fs = estimate_sampling_rate(self.device_millis_history, int(round(self.current_sampling_rate)))
                if abs(float(estimated_fs) - float(self.current_sampling_rate)) >= 1.0:
                    self._update_sampling_rate_dependent_sizes(float(estimated_fs))
            received_at = datetime.now().strftime("%H:%M:%S.%f")
            self._write_raw_capture_row(
                received_at=received_at,
                device_millis=None if device_millis is None else int(device_millis),
                ecg_value=int(parsed["ecg"]),
                eeg_value=int(parsed["eeg"]),
                eeg1_value=int(parsed["eeg1"]),
                eeg2_value=int(parsed["eeg2"]),
            )
            self._append_sample(float(parsed["eeg1"]), float(parsed["eeg2"]), float(parsed["ecg"]), received_at)
            processed_lines += 1

    def _run_loop(self) -> None:
        while self.running:
            try:
                with self.lock:
                    self._poll_serial_once()
            except Exception as exc:
                self.current_state_text = f"SERIAL_LOOP_ERROR {exc}"
            time.sleep(0.01)

    def _run_unity_loop(self) -> None:
        while self.running:
            try:
                with self.lock:
                    if self.unity_sender is not None:
                        self.unity_sender.send(self._build_unity_payload())
            except Exception as exc:
                self.current_state_text = f"UNITY_SEND_ERROR {exc}"
            time.sleep(UNITY_SEND_INTERVAL_SEC)

    def _resolve_device_connected(self) -> bool:
        serial_ready = self.serial_connection is not None and self.serial_connection.is_open and self.startup_error is None
        if not serial_ready:
            return False
        if self.last_sample_received_at is None:
            return False
        return (time.time() - self.last_sample_received_at) <= 2.0

    def _resolve_signal_quality(self) -> str:
        eeg_quality = str(self.current_eeg_quality).lower()
        ecg_quality = str(self.current_ecg_quality).lower()
        if eeg_quality == "good" and ecg_quality == "good":
            return "good"
        if "bad" in {eeg_quality, ecg_quality}:
            return "poor"
        if any(value in {"good", "warning"} for value in {eeg_quality, ecg_quality}):
            return "fair"
        return "unknown"

    def _resolve_measurement_state_label(self) -> str:
        if self.collecting_normal_baseline:
            return "평상시 기준 측정 중"
        if self.collecting_stress_baseline:
            return "스트레스 기준 측정 중"
        if self.detection_running:
            return "실시간 측정 중"
        if self.normal_baseline_ready and self.stress_baseline_ready:
            return "측정 준비 완료"
        if self.normal_baseline_ready and not self.stress_baseline_ready:
            return "스트레스 기준 대기"
        return "대기 중"

    def _resolve_measurement_elapsed_sec(self) -> int:
        if self.detection_started_at is None:
            return 0
        return max(0, int(time.time() - self.detection_started_at))

    def get_state(self) -> dict[str, Any]:
        with self.lock:
            normal_label = "Stop Normal / Build Baseline" if self.collecting_normal_baseline else "Start Normal Baseline"
            stress_label = "Stop Stress / Calibrate" if self.collecting_stress_baseline else "Start Stress Baseline"
            stress_disabled = self.collecting_normal_baseline or (not self.normal_baseline_ready and not self.collecting_stress_baseline)
            return {
                "status": self.current_state_text,
                "device": {
                    "connected": self._resolve_device_connected(),
                    "signalQuality": self._resolve_signal_quality(),
                    "eegQuality": self.current_eeg_quality,
                    "ecgQuality": self.current_ecg_quality,
                    "hapticStatus": self.haptic_status,
                },
                "measurement": {
                    "stateLabel": self._resolve_measurement_state_label(),
                    "elapsedSec": self._resolve_measurement_elapsed_sec(),
                },
                "flags": {
                    "collectingNormal": self.collecting_normal_baseline,
                    "collectingStress": self.collecting_stress_baseline,
                    "detecting": self.detection_running,
                    "normalReady": self.normal_baseline_ready,
                    "stressReady": self.stress_baseline_ready,
                },
                "ui": {
                    "normalButtonLabel": normal_label,
                    "stressButtonLabel": stress_label,
                    "stressButtonDisabled": stress_disabled,
                    "normalButtonDisabled": self.collecting_stress_baseline,
                },
                "current": {
                    "eegFinal": self.current_eeg_final,
                    "ecgFinal": self.current_ecg_final,
                    "fusionFinal": self.current_fusion_final,
                    "displayState": self.current_display_state,
                    "eegProbability": None if not np.isfinite(self.current_eeg_probability) else float(self.current_eeg_probability),
                    "eegSmoothedProbability": None if not np.isfinite(self.current_eeg_smoothed_probability) else float(self.current_eeg_smoothed_probability),
                    "eegScore": None if not np.isfinite(self.current_eeg_score) else float(self.current_eeg_score),
                    "eegSmoothedScore": None if not np.isfinite(self.current_eeg_smoothed_score) else float(self.current_eeg_smoothed_score),
                    "ecgProbability": None if not np.isfinite(self.current_ecg_probability) else float(self.current_ecg_probability),
                    "ecgSmoothedProbability": None if not np.isfinite(self.current_ecg_smoothed_probability) else float(self.current_ecg_smoothed_probability),
                    "ecgScore": None if not np.isfinite(self.current_ecg_score) else float(self.current_ecg_score),
                    "ecgSmoothedScore": None if not np.isfinite(self.current_ecg_smoothed_score) else float(self.current_ecg_smoothed_score),
                    "ecgRule": self.current_ecg_rule_text,
                    "heartRate": None if not np.isfinite(self.current_hr_bpm) else float(self.current_hr_bpm),
                    "rmssd": None if not np.isfinite(self.current_rmssd_ms) else float(self.current_rmssd_ms),
                    "samplingRate": float(self.current_sampling_rate),
                },
                "baseline": {
                    "normalSamples": len(self.normal_baseline_eeg1),
                    "stressSamples": len(self.stress_baseline_eeg1),
                    "eegNormalMean": None if not np.isfinite(self.eeg_normal_score_mean) else float(self.eeg_normal_score_mean),
                    "eegStressMean": None if not np.isfinite(self.eeg_stress_score_mean) else float(self.eeg_stress_score_mean),
                    "ecgNormalMean": None if not np.isfinite(self.ecg_normal_score_mean) else float(self.ecg_normal_score_mean),
                    "ecgStressMean": None if not np.isfinite(self.ecg_stress_score_mean) else float(self.ecg_stress_score_mean),
                },
                "plots": {
                    "rawEeg1": list(self.raw_plot_eeg1),
                    "rawEeg2": list(self.raw_plot_eeg2),
                    "rawEcg": list(self.raw_plot_ecg),
                    "eegScore": list(self.eeg_score_plot_smooth),
                    "ecgScore": list(self.ecg_score_plot_smooth),
                    "thresholds": {
                        "baseline": SCORE_BASELINE,
                        "stress": SCORE_STRESS_THRESHOLD,
                        "reject": SCORE_REJECT_THRESHOLD,
                    },
                },
            }

    def close(self) -> None:
        with self.lock:
            self.running = False
            self._close_output_logs()
            try:
                if self.serial_connection is not None and self.serial_connection.is_open:
                    self.serial_connection.close()
            except Exception:
                pass
            try:
                if self.unity_sender is not None:
                    self.unity_sender.close()
            except Exception:
                pass
