# Trophi-inspired roadmap for this MVP

Reference checked:
- https://www.trophi.ai/

## Implemented now

- Realtime corner coaching with severity (`warn`, `critical`)
- Baseline modes:
  - `session_best`
  - `external` (load pro reference from CSV/Parquet)
- Metrics for braking and corner phases:
  - brake start, peak and duration
  - turn-in point
  - apex point
  - throttle-on point
  - time to full throttle
  - exit speed
- Visual in-race overlay (top-most local window)
- Local dashboard with live telemetry, last laps, messages and active config
- Raw tick recorder and replay provider

## Next features aligned with advanced coaching platforms

- Per-corner scorecard (entry/mid/exit score)
- Skill trend over stints (consistency and repeatability metrics)
- Racing line deviation against reference lap
- Sector and corner gain/loss heatmap
- Session objective mode ("focus on T3/T7 brake + turn-in")
- Smarter anti-spam prioritization for realtime hints

