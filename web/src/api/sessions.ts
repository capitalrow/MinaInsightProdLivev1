import { SessionHeaderResponse, SessionDiffResponse, MeetingCard } from '@/types/meeting';

const API_BASE = '/api';

export async function getSessionsHeader(
  range: string,
  archived: boolean,
  signal?: AbortSignal
): Promise<SessionHeaderResponse> {
  const params = new URLSearchParams({
    range,
    archived: archived.toString(),
  });

  const response = await fetch(`${API_BASE}/sessions/header?${params}`, {
    signal,
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

export async function getSessionsDiff(
  range: string,
  sort: string,
  since_event_id?: number,
  cursor?: string,
  signal?: AbortSignal
): Promise<SessionDiffResponse> {
  const params = new URLSearchParams({
    range,
    sort,
  });

  if (since_event_id !== undefined) {
    params.set('since_event_id', since_event_id.toString());
  }

  if (cursor) {
    params.set('cursor', cursor);
  }

  const response = await fetch(`${API_BASE}/sessions?${params}`, {
    signal,
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

export async function patchSession(
  session_id: string,
  operation: 'archive' | 'rename' | 'restore',
  payload: any,
  client_ulid: string,
  signal?: AbortSignal
): Promise<{ success: boolean; error?: string }> {
  const response = await fetch(`${API_BASE}/sessions/${session_id}`, {
    method: 'PATCH',
    signal,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      op: operation,
      client_ulid,
      ...payload,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`HTTP ${response.status}: ${error}`);
  }

  return response.json();
}

export async function getTranscriptManifest(
  session_id: string,
  signal?: AbortSignal
): Promise<any> {
  const response = await fetch(`${API_BASE}/transcript/manifest?session_id=${session_id}`, {
    signal,
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}
