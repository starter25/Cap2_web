# Web Viz

`web_viz`는 `stress_model.dual_eeg_baseline`의 dual-EEG + curated-ECG 로직을 웹 UI로 감싸는 별도 프론트/백엔드 폴더입니다.

- **백엔드**: FastAPI (`web_viz.backend.app`) — 시리얼 장치에서 신호를 읽어 추론하고 `/api/*` JSON API로 노출.
- **프론트엔드**: React + TypeScript + Vite (`frontend/`) — 빌드 결과(`frontend/dist`)를 백엔드가 같이 서빙하므로 운영 시 **프로세스는 하나**입니다.

> 실행하려면 이 폴더가 `web_viz`라는 이름으로 외부 `stress_model` 패키지 옆에 있고, 번들 루트가 `sys.path`에 있어야 합니다(아래 "권장 구조" 참고). 이 레포 단독으로는 백엔드가 동작하지 않습니다.

## 빠른 실행 (운영)

번들 루트(= `web_viz/`와 `stress_model/`가 같이 있는 폴더)에서:

```bash
# 1) 프론트 빌드 (최초 1회, 또는 프론트 변경 시)
cd web_viz/frontend
npm install
npm run build          # frontend/dist 생성

# 2) 백엔드 실행 (SPA + API 둘 다 서빙)
cd ../..
python -m web_viz.backend.app
```

브라우저에서 `http://127.0.0.1:5080`을 엽니다. `frontend/dist`가 없으면 백엔드는 경고를 출력하고 API만 서빙합니다.

주요 CLI 플래그(`backend/app.py`의 `parse_args` 참고): `--serial-port`(미지정 시 자동 감지), `--baudrate`, `--sampling-rate`, `--decision-mode {raw,smoothed}`, `--threshold`, `--ecg-threshold`, 모델/프로파일 경로, `--unity-host`, `--unity-bio-port`, `--disable-unity-bio`.

## 프론트엔드 개발

핫 리로드로 UI를 개발할 때는 Vite 개발 서버를 씁니다.

```bash
cd web_viz/frontend
npm run dev            # http://127.0.0.1:5173, /api 는 127.0.0.1:5080 으로 프록시
```

백엔드가 다른 호스트/포트에 있으면 프록시 대상을 바꿀 수 있습니다.

```bash
VITE_API_TARGET=http://192.168.0.10:5080 npm run dev
```

백엔드가 연결되지 않으면 앱이 자동으로 **오프라인 목**(`src/mock.ts`)으로 폴백해, 장치/백엔드 없이도 차트·지수·마스코트가 살아 움직입니다 → 디자인 작업에 사용.

자세한 프론트 구조와 API 계약은 [`frontend/README.md`](frontend/README.md) 참고. 이전 바닐라 HTML/CSS/JS 구현은 [`frontend/legacy/`](frontend/legacy/)에 보존되어 있습니다.

## 폴더 하나로 전달할 때 권장 구조

```text
stress_web_bundle/
  web_viz/                 <- 이 레포
    backend/
    frontend/
      dist/                <- npm run build 결과 (백엔드가 서빙)
  stress_model/            <- ML 로직, 모델 로더, 시리얼 유틸 (외부)
  data/
    models/
      dual_eeg_ecg_curated_extra_trees.pkl
      dual_eeg_ecg_curated_stress_profile.json
    stress_model/
      dual_eeg_baseline/
        runs/
          include_warning/
            models/
              extra_trees.pkl
              feature_columns.json
```

전달 전 `web_viz/frontend`에서 `npm run build`로 `dist`를 만들어 포함하면, 받는 쪽은 Node 없이 `python -m web_viz.backend.app`만으로 실행할 수 있습니다.

## 디자이너에게 프론트만 전달할 때

`web_viz/frontend` 폴더를 전달하면 됩니다. 받는 쪽에서:

```bash
npm install
npm run dev            # 백엔드 없이도 오프라인 목으로 미리보기
```

API 경로·필드명은 [`frontend/src/types.ts`](frontend/src/types.ts)에 타입으로 정의되어 있으며, 백엔드 `controller.py:get_state()`와 항상 일치해야 합니다.
