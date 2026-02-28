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
