import { openDB, DBSchema, IDBPDatabase } from 'idb';
import { MeetingCard, MeetingsGroups } from '@/types/meeting';

interface MeetingsCacheDB extends DBSchema {
  meetings: {
    key: string;
    value: {
      byId: Record<string, MeetingCard>;
      groups: MeetingsGroups;
      last_event_id: number;
      etag: string;
      timestamp: number;
    };
  };
  prefetch: {
    key: string;
    value: {
      session_id: string;
      manifest: any;
      timestamp: number;
    };
  };
}

const DB_NAME = 'mina-meetings-cache';
const DB_VERSION = 1;
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000; // 24 hours

class IndexedDBCache {
  private db: IDBPDatabase<MeetingsCacheDB> | null = null;
  private initPromise: Promise<void> | null = null;

  async init(): Promise<void> {
    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = (async () => {
      try {
        this.db = await openDB<MeetingsCacheDB>(DB_NAME, DB_VERSION, {
          upgrade(db) {
            if (!db.objectStoreNames.contains('meetings')) {
              db.createObjectStore('meetings');
            }
            if (!db.objectStoreNames.contains('prefetch')) {
              db.createObjectStore('prefetch');
            }
          },
        });
      } catch (error) {
        console.error('Failed to initialize IndexedDB:', error);
        throw error;
      }
    })();

    return this.initPromise;
  }

  async getMeetingsCache(key: string = 'default') {
    await this.init();
    if (!this.db) return null;

    try {
      const cached = await this.db.get('meetings', key);
      if (!cached) return null;

      if (Date.now() - cached.timestamp > CACHE_EXPIRY_MS) {
        await this.db.delete('meetings', key);
        return null;
      }

      return {
        byId: cached.byId,
        groups: cached.groups,
        last_event_id: cached.last_event_id,
        etag: cached.etag,
      };
    } catch (error) {
      console.error('Error reading meetings cache:', error);
      return null;
    }
  }

  async setMeetingsCache(
    data: {
      byId: Record<string, MeetingCard>;
      groups: MeetingsGroups;
      last_event_id: number;
      etag: string;
    },
    key: string = 'default'
  ): Promise<void> {
    await this.init();
    if (!this.db) return;

    try {
      await this.db.put('meetings', {
        ...data,
        timestamp: Date.now(),
      }, key);
    } catch (error) {
      console.error('Error writing meetings cache:', error);
    }
  }

  async getPrefetchManifest(session_id: string) {
    await this.init();
    if (!this.db) return null;

    try {
      const cached = await this.db.get('prefetch', session_id);
      if (!cached) return null;

      if (Date.now() - cached.timestamp > 60000) { // 1 minute expiry
        await this.db.delete('prefetch', session_id);
        return null;
      }

      return cached.manifest;
    } catch (error) {
      console.error('Error reading prefetch cache:', error);
      return null;
    }
  }

  async setPrefetchManifest(session_id: string, manifest: any): Promise<void> {
    await this.init();
    if (!this.db) return;

    try {
      await this.db.put('prefetch', {
        session_id,
        manifest,
        timestamp: Date.now(),
      }, session_id);
    } catch (error) {
      console.error('Error writing prefetch cache:', error);
    }
  }

  async clear(): Promise<void> {
    await this.init();
    if (!this.db) return;

    try {
      await this.db.clear('meetings');
      await this.db.clear('prefetch');
    } catch (error) {
      console.error('Error clearing cache:', error);
    }
  }
}

export const indexedDBCache = new IndexedDBCache();
