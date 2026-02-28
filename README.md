# AI Driving Coach MVP (ACC)

Python MVP for ACC coaching with:
- one telemetry pipeline for realtime and post-lap
- realtime rule-based hints
- post-lap comparison
- visual local overlay and dashboard (React + TypeScript)
- benchmark externo (accsetups.com) por pista/carro

## Main capabilities

- ACC shared memory provider (`acc`)
- mock provider (`mock`)
- replay provider from raw ticks (`replay`)
- internal event bus (`tick`, `lap_started`, `lap_finished`, `sector_changed`)
- corner feature extraction:
  - `brake_start_point`
  - `turn_in_point`
  - `apex_point`
  - `brake_peak`
  - `brake_duration`
  - `min_speed`
  - `throttle_on_point`
  - `exit_stabilization_point`
  - `time_to_full_throttle`
  - `exit_speed`
- baseline modes:
  - `session_best`
  - `external` (CSV/Parquet reference features)
- persistence:
  - lap features CSV/Parquet
  - raw ticks CSV/Parquet (for replay and offline analysis)
- benchmark database (SQLite) com referencias externas

## Install

```powershell
.\venv\Scripts\python -m pip install -r requirements.txt
```

## Build do Dashboard React

```powershell
cd web/dashboard
npm install
npm run build
cd ../..
```

Obs.: sem o build em `web/dashboard/dist`, o backend sobe e exibe uma pagina de aviso.

## Run (ACC live)

```powershell
$env:PYTHONPATH="src"
$env:AIDC_PROVIDER="acc"
$env:AIDC_TICK_LIMIT="0"                 # 0 = continuous
$env:AIDC_DASHBOARD="1"
$env:AIDC_OVERLAY="1"
.\venv\Scripts\python -m ai_driving_coach.main
```

Expected:
- console boot line
- dashboard line: `[DASH] running at http://127.0.0.1:8765`
- overlay window on top of game (best with borderless windowed mode in ACC)
- no overlay clique em `Mover`, arraste para onde quiser, clique `Travar`

## Run (quick capture check)

```powershell
$env:PYTHONPATH="src"
$env:AIDC_PROVIDER="acc"
$env:AIDC_TICK_LIMIT="900"
$env:AIDC_CAPTURE_HEARTBEAT="1"
$env:AIDC_CAPTURE_HEARTBEAT_EVERY="120"
.\venv\Scripts\python -m ai_driving_coach.main
```

If telemetry is active you should see changing `speed/throttle/brake/spline` values.

## Run (mock)

```powershell
$env:PYTHONPATH="src"
$env:AIDC_PROVIDER="mock"
$env:AIDC_TICK_LIMIT="1200"
.\venv\Scripts\python -m ai_driving_coach.main
```

## Run (replay)

Use a saved raw tick file from `data/session_output/lap_XXX_ticks.csv` or `.parquet`.

```powershell
$env:PYTHONPATH="src"
$env:AIDC_PROVIDER="replay"
$env:AIDC_REPLAY_FILE="data/session_output/lap_001_ticks.csv"
$env:AIDC_REPLAY_SPEED="1.0"             # 2.0 = 2x speed
.\venv\Scripts\python -m ai_driving_coach.main
```

## External reference baseline (pro lap)

```powershell
$env:PYTHONPATH="src"
$env:AIDC_PROVIDER="acc"
$env:AIDC_BASELINE_MODE="external"
$env:AIDC_REFERENCE_FEATURES_PATH="data/reference/pro_spa_features.csv"
.\venv\Scripts\python -m ai_driving_coach.main
```

With external baseline loaded, hints report early/late braking and turn-in against that lap.

## Sync benchmark externo (accsetups.com)

Popula o banco local com melhores tempos por pista/carro:

```powershell
$env:PYTHONPATH="src"
.\venv\Scripts\python -m ai_driving_coach.tools.sync_benchmarks
```

Banco gerado em: `data/benchmarks/accsetups.sqlite`

Obs.: a classificacao `dry/wet` vem da flag de variante de setup no site.

## Dashboard

- URL: `http://127.0.0.1:8765`
- Shows:
  - live telemetry
  - mapa de pista por coordenadas reais (world X/Z) com fallback spline
  - melhores tempos de volta e setores
  - deltas por setor nas ultimas voltas
  - ultima volta teorica (somatorio dos melhores setores)
  - referencia externa por pista/carro e gap vs benchmark
  - last laps
  - realtime coach messages
  - active runtime config
- Frontend stack:
  - React 18
  - TypeScript
  - Vite

## Dashboard Dev (frontend hot reload)

Com backend Python rodando na porta `8765`, rode o frontend separado:

```powershell
cd web/dashboard
npm install
npm run dev
```

URL dev: `http://127.0.0.1:5173` (proxy para `/api` -> `127.0.0.1:8765`)

## Overlay

- Local top-most window for in-race hints:
  - lap/sector, speed, throttle, brake, spline
  - angulo de volante (graus) com dial e historico curto
  - combustivel atual, autonomia estimada e indicacao se termina a prova
  - botao `Pneus` abre segunda janela com 4 pneus:
    - pressao
    - temperatura de carcaca
    - temperatura de freio
    - slip traseiro (indicador de detracao)
  - latest priority hint with severity
- Works best when ACC is not in exclusive fullscreen.

## Output files

Default output directory:
- `data/session_output`

Saved artifacts:
- `lap_XXX_features.csv`
- `lap_XXX_features.parquet`
- `lap_XXX_ticks.csv`
- `lap_XXX_ticks.parquet`

## Environment variables

- `AIDC_PROVIDER` = `mock|acc|replay`
- `AIDC_TICK_LIMIT` (default: `0`)
- `AIDC_ACC_POLL_HZ` (default: `60`)
- `AIDC_ACC_MAX_IDLE_S` (default: `0`)
- `AIDC_REPLAY_FILE` (required in replay mode)
- `AIDC_REPLAY_SPEED` (default: `1.0`)
- `AIDC_BASELINE_MODE` = `session_best|external`
- `AIDC_REFERENCE_FEATURES_PATH` (used when baseline mode is `external`)
- `AIDC_TRACK_LENGTH_M` (manual fallback track length)
- `AIDC_CAPTURE_HEARTBEAT` = `1|0`
- `AIDC_CAPTURE_HEARTBEAT_EVERY` (default: `120`)
- `AIDC_DASHBOARD` = `1|0`
- `AIDC_DASHBOARD_HOST` (default: `127.0.0.1`)
- `AIDC_DASHBOARD_PORT` (default: `8765`)
- `AIDC_OVERLAY` = `1|0`
- `AIDC_OVERLAY_X`, `AIDC_OVERLAY_Y`, `AIDC_OVERLAY_W`, `AIDC_OVERLAY_H`
- `AIDC_OVERLAY_HINT_SECONDS` (default: `3.0`, use `0` para manter ate a proxima dica)
- `AIDC_PERSIST_RAW_TICKS` = `1|0`
- `AIDC_PERSIST_PARQUET` = `1|0`
- `AIDC_BENCHMARK_DB` (default: `data/benchmarks/accsetups.sqlite`)
- `AIDC_BENCHMARK_CONDITION` = `overall|dry|wet`
