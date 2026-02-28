export type NumberMap = Record<string, number>;

export interface LastTick {
  session_time_s?: number;
  lap_count?: number;
  lap_time_s?: number;
  sector?: number;
  spline?: number;
  speed_kmh?: number;
  throttle?: number;
  brake?: number;
  steer?: number;
  steering_angle_deg?: number | null;
  gear?: number;
  rpm?: number;
  is_in_pit?: boolean;
  track_name?: string;
  track_length_m?: number;
  car_name?: string;
  world_pos_x?: number;
  world_pos_z?: number;
  fuel_l?: number | null;
  fuel_estimated_laps?: number | null;
  laps_remaining?: number | null;
  fuel_will_finish?: boolean | null;
}

export interface TrackProgressSample {
  spline?: number;
  speed_kmh?: number;
  sector?: number;
  world_x?: number | null;
  world_z?: number | null;
}

export interface TimingSnapshot {
  current_lap_number?: number | null;
  current_sector?: number | null;
  best_lap_time_s?: number | null;
  best_lap_number?: number | null;
  best_sector_times?: NumberMap;
  theoretical_best_s?: number | null;
}

export interface BenchmarkReference {
  track_slug?: string;
  track_name?: string;
  car_slug?: string;
  car_name?: string;
  car_class?: string;
  condition?: string;
  lap_time_s?: number;
  lap_time_text?: string;
  source_url?: string;
  scope?: string;
  requested_condition?: string;
}

export interface CoachMessage {
  lap_number?: number;
  corner_index?: number;
  text?: string;
  severity?: string;
  category?: string;
  ts?: number;
}

export interface LapResult {
  lap_number?: number;
  lap_time_s?: number;
  is_best_lap?: boolean;
  delta_to_best_lap_s?: number;
  summary?: string[];
  features_count?: number;
  sectors?: NumberMap;
  sector_deltas_to_best?: NumberMap;
  theoretical_best_s?: number | null;
  benchmark_gap_s?: number | null;
  benchmark_percent?: number | null;
  benchmark_scope?: string;
  benchmark_reference_lap_s?: number;
}

export interface DashboardApiState {
  status: string;
  provider: string;
  uptime_s: number;
  tick_count: number;
  last_tick: LastTick;
  track_progress: TrackProgressSample[];
  timing: TimingSnapshot;
  benchmark_reference: BenchmarkReference;
  recent_laps: LapResult[];
  recent_messages: CoachMessage[];
  config: Record<string, unknown>;
}

export const INITIAL_STATE: DashboardApiState = {
  status: "booting",
  provider: "-",
  uptime_s: 0,
  tick_count: 0,
  last_tick: {},
  track_progress: [],
  timing: {},
  benchmark_reference: {},
  recent_laps: [],
  recent_messages: [],
  config: {}
};
