import type { LastTick, TrackProgressSample } from "./types";

const MAX_WORLD_POINTS = 12_000;

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function drawSplineFallback(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  samples: TrackProgressSample[],
  currentSpline: number
): void {
  const width = canvas.width;
  const height = canvas.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.34;

  ctx.strokeStyle = cssVar("--line");
  ctx.lineWidth = 16;
  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
  ctx.stroke();

  [0.0, 0.3333, 0.6666].forEach((sectorSpline) => {
    const angle = -Math.PI / 2 + sectorSpline * Math.PI * 2;
    ctx.strokeStyle = cssVar("--muted");
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.moveTo(
      centerX + Math.cos(angle) * (radius - 14),
      centerY + Math.sin(angle) * (radius - 14)
    );
    ctx.lineTo(
      centerX + Math.cos(angle) * (radius + 14),
      centerY + Math.sin(angle) * (radius + 14)
    );
    ctx.stroke();
  });

  samples.slice(-1800).forEach((point) => {
    const spline = Number(point.spline ?? 0);
    const speed = Number(point.speed_kmh ?? 0);
    const angle = -Math.PI / 2 + spline * Math.PI * 2;
    const x = centerX + Math.cos(angle) * radius;
    const y = centerY + Math.sin(angle) * radius;
    const normalized = Math.min(1, speed / 220);
    const red = Math.round(230 - 140 * normalized);
    const green = Math.round(80 + 150 * normalized);
    ctx.fillStyle = `rgb(${red},${green},120)`;
    ctx.fillRect(x - 1.2, y - 1.2, 2.4, 2.4);
  });

  const angle = -Math.PI / 2 + currentSpline * Math.PI * 2;
  const x = centerX + Math.cos(angle) * radius;
  const y = centerY + Math.sin(angle) * radius;
  ctx.fillStyle = cssVar("--accent");
  ctx.beginPath();
  ctx.arc(x, y, 6, 0, Math.PI * 2);
  ctx.fill();
}

function drawWorldMap(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  points: Array<{ world_x: number; world_z: number; speed_kmh?: number }>,
  currentX: number,
  currentZ: number
): void {
  const width = canvas.width;
  const height = canvas.height;
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;

  points.forEach((point) => {
    minX = Math.min(minX, point.world_x);
    maxX = Math.max(maxX, point.world_x);
    minZ = Math.min(minZ, point.world_z);
    maxZ = Math.max(maxZ, point.world_z);
  });

  const spanX = Math.max(1.0, maxX - minX);
  const spanZ = Math.max(1.0, maxZ - minZ);
  const pad = 18;
  const drawW = width - pad * 2;
  const drawH = height - pad * 2;
  const scale = Math.min(drawW / spanX, drawH / spanZ);
  const offX = (width - spanX * scale) / 2;
  const offY = (height - spanZ * scale) / 2;

  function project(x: number, z: number): { x: number; y: number } {
    return {
      x: offX + (x - minX) * scale,
      y: height - (offY + (z - minZ) * scale)
    };
  }

  ctx.strokeStyle = cssVar("--line");
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < points.length; i += 1) {
    const p = project(points[i].world_x, points[i].world_z);
    if (i === 0) {
      ctx.moveTo(p.x, p.y);
    } else {
      ctx.lineTo(p.x, p.y);
    }
  }
  ctx.stroke();

  const step = Math.max(1, Math.floor(points.length / 900));
  for (let i = 0; i < points.length; i += step) {
    const sample = points[i];
    const p = project(sample.world_x, sample.world_z);
    const normalized = Math.min(1, (sample.speed_kmh ?? 0) / 220);
    const red = Math.round(230 - 140 * normalized);
    const green = Math.round(80 + 150 * normalized);
    ctx.fillStyle = `rgb(${red},${green},120)`;
    ctx.fillRect(p.x - 1.2, p.y - 1.2, 2.4, 2.4);
  }

  if (Number.isFinite(currentX) && Number.isFinite(currentZ)) {
    const cur = project(currentX, currentZ);
    ctx.fillStyle = cssVar("--accent");
    ctx.beginPath();
    ctx.arc(cur.x, cur.y, 6, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function drawTrackMap(
  canvas: HTMLCanvasElement | null,
  samples: TrackProgressSample[],
  lastTick: LastTick
): string {
  if (!canvas) {
    return "-";
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return "-";
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = cssVar("--map-bg");
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const world = samples.filter(
    (point): point is TrackProgressSample & { world_x: number; world_z: number } =>
      Number.isFinite(point.world_x) && Number.isFinite(point.world_z)
  );

  if (world.length >= 60) {
    let minX = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let minZ = Number.POSITIVE_INFINITY;
    let maxZ = Number.NEGATIVE_INFINITY;
    world.forEach((point) => {
      minX = Math.min(minX, point.world_x as number);
      maxX = Math.max(maxX, point.world_x as number);
      minZ = Math.min(minZ, point.world_z as number);
      maxZ = Math.max(maxZ, point.world_z as number);
    });

    if (maxX - minX > 30 && maxZ - minZ > 30) {
      drawWorldMap(
        ctx,
        canvas,
        world.slice(-MAX_WORLD_POINTS).map((item) => ({
          world_x: Number(item.world_x),
          world_z: Number(item.world_z),
          speed_kmh: item.speed_kmh
        })),
        Number(lastTick.world_pos_x),
        Number(lastTick.world_pos_z)
      );
      return "Modo mapa: coordenadas reais (world X/Z)";
    }
  }

  drawSplineFallback(ctx, canvas, samples, Number(lastTick.spline ?? 0));
  return "Modo mapa: fallback por spline (aguardando trajeto real)";
}
