# Web Viz

`web_viz`는 `stress_model.dual_eeg_baseline`의 dual-EEG + curated-ECG 로직을 웹 UI로 감싸는 별도 프론트/백엔드 폴더입니다.

## 빠른 실행

루트에서:

```bash
run_web_viz.bat
```

또는 `web_viz` 폴더 안에서:

```bash
run_web_viz.bat
```

브라우저에서 `http://127.0.0.1:5080`을 엽니다.

## 폴더 하나로 전달할 때 권장 구조

아래처럼 하나의 상위 폴더에 묶으면 실행이 가장 쉽습니다.

```text
stress_web_bundle/
  run_web_viz.bat
  venv/
  web_viz/
    run_web_viz.bat
    frontend/
    backend/
  stress_model/
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

## 디자이너에게 프론트만 전달할 때

디자인 수정만 할 거면 아래 3개만 전달하면 됩니다.

- `web_viz/frontend/index.html`
- `web_viz/frontend/styles.css`
- `web_viz/frontend/app.js`

단, 이 3개만으로는 실시간 데이터 연결 없이 정적 편집만 가능합니다.

## 디자이너 확인용 preview 실행

프론트 3파일만 확인용으로 돌릴 때는 mock preview 서버를 씁니다.

```bash
run_designer_preview.bat
```

기본 주소는 `http://127.0.0.1:5082` 입니다.

## 디자이너 확인용 exe 빌드

```bash
build_designer_preview_exe.bat
```

빌드 후 아래 4개만 전달하면 됩니다.

- `dist/web_viz_designer_preview.exe`
- `frontend/index.html`
- `frontend/styles.css`
- `frontend/app.js`
