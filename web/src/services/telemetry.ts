import { TelemetryEvent } from '@/types/meeting';

class TelemetryService {
  private events: TelemetryEvent[] = [];
  private maxEvents = 100;

  track(event: Omit<TelemetryEvent, 'surface' | 'ts'>): void {
    const telemetryEvent: TelemetryEvent = {
      surface: 'meetings',
      ts: new Date().toISOString(),
      ...event,
    };

    this.events.push(telemetryEvent);

    if (this.events.length > this.maxEvents) {
      this.events.shift();
    }

    if (event.event === 'ws_flush' && event.ws_buffered && event.ws_buffered > 50) {
      console.warn('[TELEMETRY ALERT] WebSocket buffer stalled:', event);
    }

    console.log('[TELEMETRY]', telemetryEvent);
  }

  getEvents(): TelemetryEvent[] {
    return [...this.events];
  }

  clear(): void {
    this.events = [];
  }
}

export const telemetry = new TelemetryService();
