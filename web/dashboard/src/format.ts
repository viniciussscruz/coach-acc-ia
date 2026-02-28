export function n(value: unknown, digits = 3): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const num = Number(value);
  if (Number.isNaN(num)) {
    return "-";
  }
  return num.toFixed(digits);
}

export function lapTime(value: unknown, digits = 3): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const total = Number(value);
  if (Number.isNaN(total) || !Number.isFinite(total)) {
    return "-";
  }
  const sign = total < 0 ? "-" : "";
  const abs = Math.abs(total);
  const minutes = Math.floor(abs / 60);
  const seconds = abs - minutes * 60;
  const secondsText = seconds.toFixed(digits).padStart(2 + 1 + digits, "0");
  return `${sign}${minutes}:${secondsText}`;
}

export function deltaTime(value: unknown, digits = 3): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const delta = Number(value);
  if (Number.isNaN(delta) || !Number.isFinite(delta)) {
    return "-";
  }
  const sign = delta > 0 ? "+" : delta < 0 ? "-" : "+";
  const abs = Math.abs(delta);
  const minutes = Math.floor(abs / 60);
  const seconds = abs - minutes * 60;
  const secondsText = seconds.toFixed(digits).padStart(2 + 1 + digits, "0");
  return `${sign}${minutes}:${secondsText}`;
}

export function severityClass(severity?: string): string {
  if (severity === "critical") {
    return "bad";
  }
  if (severity === "warn") {
    return "warn";
  }
  return "";
}

export function deltaClass(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "";
  }
  if (value <= 0) {
    return "ok";
  }
  if (value >= 0.25) {
    return "bad";
  }
  return "warn";
}

export function percentClass(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "";
  }
  if (value <= 0) {
    return "ok";
  }
  if (value >= 2.0) {
    return "bad";
  }
  return "warn";
}

export function readSector(map?: Record<string, number>, sector?: number): number | undefined {
  if (!map || !sector) {
    return undefined;
  }
  return map[String(sector)];
}
