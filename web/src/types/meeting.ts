export type MeetingStatus = 'recording' | 'processing' | 'ready' | 'archived';

export interface MeetingCard {
  session_id: string;
  title: string;
  started_at: string;
  ended_at?: string;
  status: MeetingStatus;
  tasks: number;
  highlights: number;
  duration_s?: number;
  etag: string;
  updated_at: string;
}

export type RangeFilter = 'last30' | 'last90' | 'all';
export type SortOrder = 'newest' | 'oldest';

export interface MeetingsGroups {
  liveNow: string[];
  today: string[];
  thisWeek: string[];
  earlier: string[];
  archived: string[];
}

export interface OfflineOperation {
  type: 'archive' | 'rename';
  session_id: string;
  payload?: any;
  client_ulid: string;
}

export interface MeetingsState {
  range: RangeFilter;
  sort: SortOrder;
  showArchived: boolean;
  groups: MeetingsGroups;
  byId: Record<string, MeetingCard>;
  last_event_id: number;
  etag: string;
  cursor?: string;
  isHydrated: boolean;
  isOnline: boolean;
  offlineQueue: OfflineOperation[];
}

export interface SessionHeaderResponse {
  total: number;
  live: number;
  archived: number;
  last_event_id: number;
  etag: string;
}

export interface SessionDiffResponse {
  upserts: MeetingCard[];
  deletes: string[];
  cursor?: string;
  last_event_id: number;
}

export interface TelemetryEvent {
  surface: 'meetings';
  event: 'bootstrap' | 'diff_fetch' | 'ws_flush' | 'card_open';
  latency_ms: number;
  cache_hit: boolean;
  ws_buffered?: number;
  cards_painted?: number;
  groups?: { live: number; today: number; week: number; earlier: number };
  calm_score?: number;
  ts: string;
}
