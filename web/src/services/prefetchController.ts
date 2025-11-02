import { getTranscriptManifest } from '@/api/sessions';
import { indexedDBCache } from '@/lib/cache/indexedDb';

interface PrefetchOptions {
  maxConcurrent?: number;
  maxCacheSize?: number;
  cacheTimeout?: number;
}

class PrefetchController {
  private activeRequests = new Map<string, Promise<any>>();
  private options: Required<PrefetchOptions>;

  constructor(options: PrefetchOptions = {}) {
    this.options = {
      maxConcurrent: options.maxConcurrent ?? 3,
      maxCacheSize: options.maxCacheSize ?? 50,
      cacheTimeout: options.cacheTimeout ?? 60000,
    };
  }

  async prefetchManifest(session_id: string): Promise<any | null> {
    const cached = await indexedDBCache.getPrefetchManifest(session_id);
    if (cached) {
      return cached;
    }

    if (this.activeRequests.has(session_id)) {
      return this.activeRequests.get(session_id)!;
    }

    if (this.activeRequests.size >= this.options.maxConcurrent) {
      return null;
    }

    const promise = this.fetchAndCache(session_id);
    this.activeRequests.set(session_id, promise);

    try {
      const result = await promise;
      return result;
    } finally {
      this.activeRequests.delete(session_id);
    }
  }

  private async fetchAndCache(session_id: string): Promise<any> {
    try {
      const manifest = await getTranscriptManifest(session_id);
      await indexedDBCache.setPrefetchManifest(session_id, manifest);
      return manifest;
    } catch (error) {
      console.error(`Failed to prefetch manifest for ${session_id}:`, error);
      return null;
    }
  }

  async prefetchTopCards(session_ids: string[]): Promise<void> {
    const topTwo = session_ids.slice(0, 2);
    const promises = topTwo.map((id) => this.prefetchManifest(id));
    await Promise.allSettled(promises);
  }

  hasManifest(session_id: string): boolean {
    return this.activeRequests.has(session_id);
  }

  async warmRefinedRoute(): Promise<void> {
    try {
      await import('@/routes/dashboard/meetings/refined');
    } catch (error) {
      console.warn('Failed to warm refined route:', error);
    }
  }
}

export const prefetchController = new PrefetchController();
