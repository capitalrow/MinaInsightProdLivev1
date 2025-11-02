import { io, Socket } from 'socket.io-client';
import { MeetingCard } from '@/types/meeting';
import { meetingsStore } from '@/stores/meetingsStore';

interface WebSocketMessage {
  event_id: number;
  type: 'upsert' | 'delete';
  data: MeetingCard | string;
}

class SessionChannel {
  private socket: Socket | null = null;
  private messageBuffer: WebSocketMessage[] = [];
  private isDiffApplied = false;
  private lastProcessedEventId = 0;

  connect(workspace_id: number): void {
    this.socket = io('/meetings', {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected to /meetings');
      this.socket?.emit('join_workspace', { workspace_id });
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected from /meetings');
    });

    this.socket.on('meeting_update', (message: WebSocketMessage) => {
      this.handleMessage(message);
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  subscribe(last_event_id: number): void {
    this.lastProcessedEventId = last_event_id;
    this.isDiffApplied = false;
    this.messageBuffer = [];
  }

  markDiffApplied(): void {
    this.isDiffApplied = true;
    this.flushBuffer();
  }

  private handleMessage(message: WebSocketMessage): void {
    if (!this.isDiffApplied) {
      this.messageBuffer.push(message);
      return;
    }

    this.applyMessage(message);
  }

  private flushBuffer(): void {
    const sortedMessages = this.messageBuffer.sort((a, b) => a.event_id - b.event_id);
    
    const relevantMessages = sortedMessages.filter(
      (msg) => msg.event_id > this.lastProcessedEventId
    );

    relevantMessages.forEach((message) => {
      this.applyMessage(message);
    });

    this.messageBuffer = [];
  }

  private applyMessage(message: WebSocketMessage): void {
    const { type, data, event_id } = message;

    if (event_id <= this.lastProcessedEventId) {
      return;
    }

    if (type === 'upsert') {
      meetingsStore.applyDiff([data as MeetingCard], []);
    } else if (type === 'delete') {
      meetingsStore.applyDiff([], [data as string]);
    }

    this.lastProcessedEventId = event_id;
    meetingsStore.setState({ last_event_id: event_id });
  }

  getBufferedCount(): number {
    return this.messageBuffer.length;
  }
}

export const sessionChannel = new SessionChannel();
