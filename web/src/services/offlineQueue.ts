import { ulid } from 'ulid';
import { meetingsStore } from '@/stores/meetingsStore';
import { patchSession } from '@/api/sessions';
import { OfflineOperation } from '@/types/meeting';

class OfflineQueueService {
  private isProcessing = false;

  enqueueArchive(session_id: string): string {
    const client_ulid = ulid();
    meetingsStore.addToOfflineQueue({
      type: 'archive',
      session_id,
      client_ulid,
    });
    return client_ulid;
  }

  enqueueRename(session_id: string, title: string): string {
    const client_ulid = ulid();
    meetingsStore.addToOfflineQueue({
      type: 'rename',
      session_id,
      payload: { title },
      client_ulid,
    });
    return client_ulid;
  }

  async processQueue(): Promise<void> {
    const { offlineQueue, isOnline } = meetingsStore.getState();

    if (!isOnline || this.isProcessing || offlineQueue.length === 0) {
      return;
    }

    this.isProcessing = true;

    try {
      for (const operation of offlineQueue) {
        try {
          await this.processOperation(operation);
          meetingsStore.removeFromOfflineQueue(operation.client_ulid);
        } catch (error) {
          console.error(`Failed to process offline operation ${operation.client_ulid}:`, error);
          if (!navigator.onLine) {
            break;
          }
        }
      }
    } finally {
      this.isProcessing = false;
    }
  }

  private async processOperation(operation: OfflineOperation): Promise<void> {
    const { type, session_id, payload, client_ulid } = operation;

    if (type === 'archive') {
      await patchSession(session_id, 'archive', {}, client_ulid);
    } else if (type === 'rename') {
      await patchSession(session_id, 'rename', payload, client_ulid);
    }
  }

  init(): void {
    window.addEventListener('online', () => {
      meetingsStore.setOnlineStatus(true);
      this.processQueue();
    });

    window.addEventListener('offline', () => {
      meetingsStore.setOnlineStatus(false);
    });

    if (navigator.onLine) {
      this.processQueue();
    }
  }
}

export const offlineQueue = new OfflineQueueService();
