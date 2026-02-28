import { useEffect, useMemo, useRef, useState } from "react";

import { deltaClass, deltaTime, lapTime, n, readSector, severityClass } from "./format";
import { drawTrackMap } from "./map";
import { INITIAL_STATE, type DashboardApiState, type NumberMap } from "./types";

const POLL_INTERVAL_MS = 1000;

function valueFromSectorMap(map: NumberMap | undefined, sector: number): number | undefined {
  return readSector(map, sector);
}

export function App(): JSX.Element {
  const [data, setData] = useState<DashboardApiState>(INITIAL_STATE);
  const [connected, setConnected] = useState<boolean>(true);
  const [theme, setTheme] = useState<"dark" | "light">("light");
  const [mapMode, setMapMode] = useState<string>("-");
  const [trackFilter, setTrackFilter] = useState<string>("all");
  const [carFilter, setCarFilter] = useState<string>("all");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const preferred = window.localStorage.getItem("aidc_theme");
    if (preferred === "light" || preferred === "dark") {
      setTheme(preferred);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("aidc_theme", theme);
  }, [theme]);

  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`status ${response.status}`);
        }
        const json = (await response.json()) as DashboardApiState;
        if (mounted) {
          setData(json);
          setConnected(true);
        }
      } catch {
        if (mounted) {
          setConnected(false);
        }
      }
    };

    void poll();
    const timer = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const mode = drawTrackMap(canvasRef.current, data.track_progress ?? [], data.last_tick ?? {});
    setMapMode(mode);
  }, [data.last_tick, data.track_progress, theme]);

  const lastTick = data.last_tick ?? {};
  const timing = data.timing ?? {};
  const benchmark = data.benchmark_reference ?? {};
  const running = data.status === "running";
  const statusText = connected
    ? `provider=${data.provider} uptime=${n(data.uptime_s, 1)}s ticks=${data.tick_count}`
    : "dashboard desconectado";
  const fuelLaps = lastTick.fuel_estimated_laps ?? lastTick.laps_remaining ?? null;
  const fuelLow = fuelLaps != null && Number(fuelLaps) <= 5.0;

  const trackOptions = useMemo(() => {
    return Array.from(
      new Set(
        data.recent_laps
          .map((lap) => (lap.track_name ?? "").trim())
          .filter((name) => name.length > 0)
      )
    ).sort((a, b) => a.localeCompare(b));
  }, [data.recent_laps]);

  const carOptions = useMemo(() => {
    return Array.from(
      new Set(
        data.recent_laps
          .map((lap) => (lap.car_name ?? "").trim())
          .filter((name) => name.length > 0)
      )
    ).sort((a, b) => a.localeCompare(b));
  }, [data.recent_laps]);

  useEffect(() => {
    if (trackFilter !== "all" && !trackOptions.includes(trackFilter)) {
      setTrackFilter("all");
    }
  }, [trackFilter, trackOptions]);

  useEffect(() => {
    if (carFilter !== "all" && !carOptions.includes(carFilter)) {
      setCarFilter("all");
    }
  }, [carFilter, carOptions]);

  const filteredLaps = useMemo(() => {
    return data.recent_laps.filter((lap) => {
      const trackOk = trackFilter === "all" || (lap.track_name ?? "") === trackFilter;
      const carOk = carFilter === "all" || (lap.car_name ?? "") === carFilter;
      return trackOk && carOk;
    });
  }, [carFilter, data.recent_laps, trackFilter]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Driving Coach Dashboard</h1>
          <p className="subtitle">
            {`${lastTick.track_name ?? "-"} | ${lastTick.car_name ?? "-"} | lap=${lastTick.lap_count ?? "-"} setor=${lastTick.sector ?? "-"}`}
          </p>
        </div>
        <div className="top-actions">
          <span className={`pill ${running ? "running" : "stopped"}`}>{data.status}</span>
          <button
            className="theme-btn"
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            Tema: {theme === "dark" ? "Dark" : "Light"}
          </button>
        </div>
      </header>

      <p className="status-line">{statusText}</p>

      <section className="kpi-grid">
        <article className="kpi-card">
          <span>Velocidade</span>
          <strong>{n(lastTick.speed_kmh, 1)} km/h</strong>
        </article>
        <article className="kpi-card">
          <span>Throttle</span>
          <strong>{n((lastTick.throttle ?? 0) * 100, 0)}%</strong>
        </article>
        <article className="kpi-card">
          <span>Freio</span>
          <strong>{n((lastTick.brake ?? 0) * 100, 0)}%</strong>
        </article>
        <article className="kpi-card">
          <span>Spline</span>
          <strong>{n(lastTick.spline, 4)}</strong>
        </article>
      </section>

      <section className="content-grid">
        <article className="panel panel-map">
          <header className="panel-head">
            <h2>Mapa Da Pista</h2>
            <span>{mapMode}</span>
          </header>
          <canvas id="trackCanvas" ref={canvasRef} width={1200} height={360} />
        </article>

        <article className="panel panel-timing">
          <header className="panel-head">
            <h2>Tempos E Referencia</h2>
          </header>
          <table className="compact-table">
            <tbody>
              <tr>
                <th>Melhor volta</th>
                <td>
                  {timing.best_lap_time_s != null
                    ? `${lapTime(timing.best_lap_time_s, 3)} (L${timing.best_lap_number ?? "-"})`
                    : "-"}
                </td>
              </tr>
              <tr>
                <th>Volta teorica</th>
                <td>{timing.theoretical_best_s != null ? lapTime(timing.theoretical_best_s, 3) : "-"}</td>
              </tr>
              <tr>
                <th>Setor 1 best</th>
                <td>{lapTime(valueFromSectorMap(timing.best_sector_times, 1), 3)}</td>
              </tr>
              <tr>
                <th>Setor 2 best</th>
                <td>{lapTime(valueFromSectorMap(timing.best_sector_times, 2), 3)}</td>
              </tr>
              <tr>
                <th>Setor 3 best</th>
                <td>{lapTime(valueFromSectorMap(timing.best_sector_times, 3), 3)}</td>
              </tr>
              <tr>
                <th>Benchmark</th>
                <td>
                  {benchmark.lap_time_s != null
                    ? `${lapTime(benchmark.lap_time_s, 3)} (${benchmark.condition ?? "-"})`
                    : "-"}
                </td>
              </tr>
              <tr>
                <th>Pista/Carro ref</th>
                <td>{benchmark.track_name ? `${benchmark.track_name} | ${benchmark.car_name ?? "-"}` : "-"}</td>
              </tr>
              <tr>
                <th>Combustivel</th>
                <td>{lastTick.fuel_l != null ? `${n(lastTick.fuel_l, 1)}L` : "-"}</td>
              </tr>
              <tr>
                <th>Autonomia</th>
                <td className={fuelLow ? "bad" : ""}>
                  {fuelLaps != null ? `${n(fuelLaps, 1)} voltas` : "-"}
                </td>
              </tr>
            </tbody>
          </table>
        </article>

        <article className="panel panel-coach">
          <header className="panel-head">
            <h2>Coach Em Tempo Real</h2>
          </header>
          <table className="compact-table">
            <thead>
              <tr>
                <th>t(s)</th>
                <th>Volta</th>
                <th>Sev</th>
                <th>Mensagem</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_messages.length === 0 && (
                <tr>
                  <td colSpan={4}>Sem mensagens</td>
                </tr>
              )}
              {data.recent_messages.slice(0, 8).map((msg, idx) => (
                <tr key={`msg-${idx}-${msg.ts ?? 0}`}>
                  <td>{n(msg.ts, 1)}</td>
                  <td>{msg.lap_number ?? "-"}</td>
                  <td className={severityClass(msg.severity)}>{msg.severity ?? "-"}</td>
                  <td>{msg.text ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>

        <article className="panel panel-laps">
          <header className="panel-head">
            <h2>Tabela De Tempos</h2>
            <span>{filteredLaps.length} voltas</span>
          </header>
          <div className="laps-toolbar">
            <label className="filter-field">
              <span>Pista</span>
              <select value={trackFilter} onChange={(event) => setTrackFilter(event.target.value)}>
                <option value="all">Todas</option>
                {trackOptions.map((trackName) => (
                  <option key={trackName} value={trackName}>
                    {trackName}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span>Carro</span>
              <select value={carFilter} onChange={(event) => setCarFilter(event.target.value)}>
                <option value="all">Todos</option>
                {carOptions.map((carName) => (
                  <option key={carName} value={carName}>
                    {carName}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <table className="laps-table">
            <thead>
              <tr>
                <th>Volta</th>
                <th>S1</th>
                <th>S2</th>
                <th>S3</th>
                <th>Tempo</th>
                <th>Delta</th>
                <th>Gap Ref</th>
              </tr>
            </thead>
            <tbody>
              {filteredLaps.length === 0 && (
                <tr>
                  <td colSpan={7}>Sem voltas concluidas</td>
                </tr>
              )}
              {filteredLaps.map((lap, idx) => (
                <tr key={`lap-${idx}-${lap.lap_number ?? idx}`} className={lap.is_best_lap ? "best-row" : ""}>
                  <td>
                    <span className="lap-badge">{lap.lap_number ?? "-"}</span>
                  </td>
                  <td>{lapTime(valueFromSectorMap(lap.sectors, 1), 3)}</td>
                  <td>{lapTime(valueFromSectorMap(lap.sectors, 2), 3)}</td>
                  <td>{lapTime(valueFromSectorMap(lap.sectors, 3), 3)}</td>
                  <td className={lap.is_best_lap ? "ok" : ""}>{lapTime(lap.lap_time_s, 3)}</td>
                  <td className={deltaClass(lap.delta_to_best_lap_s)}>{deltaTime(lap.delta_to_best_lap_s, 3)}</td>
                  <td className={deltaClass(lap.benchmark_gap_s)}>{deltaTime(lap.benchmark_gap_s, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>
    </main>
  );
}
