import { useEffect, useRef, useState } from 'react';
import { meetingsStore } from '@/stores/meetingsStore';
import { indexedDBCache } from '@/lib/cache/indexedDb';
import { getSessionsHeader, getSessionsDiff } from '@/api/sessions';
import { sessionChannel } from '@/ws/sessionChannel';
import { prefetchController } from '@/services/prefetchController';
import { telemetry } from '@/services/telemetry';
import { MeetingsState } from '@/types/meeting';

export function useMeetingsBootstrap(workspace_id: number) {
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const idleSyncIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    bootstrap();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (idleSyncIntervalRef.current) {
        clearInterval(idleSyncIntervalRef.current);
      }
      sessionChannel.disconnect();
    };
  }, [workspace_id]);

  async function bootstrap() {
    const startTime = Date.now();

    try {
      // Step 1: meetings_bootstrap - Paint from cache
      const cached = await indexedDBCache.getMeetingsCache();
      if (cached) {
        meetingsStore.setState({
          byId: cached.byId,
          groups: cached.groups,
          last_event_id: cached.last_event_id,
          etag: cached.etag,
          isHydrated: true,
        });

        telemetry.track({
          event: 'bootstrap',
          latency_ms: Date.now() - startTime,
          cache_hit: true,
          cards_painted: Object.keys(cached.byId).length,
        });
      } else {
        telemetry.track({
          event: 'bootstrap',
          latency_ms: Date.now() - startTime,
          cache_hit: false,
        });
      }

      // Step 2: meetings_ws_subscribe
      sessionChannel.connect(workspace_id);
      const state = meetingsStore.getState();
      sessionChannel.subscribe(state.last_event_id);

      // Step 3: meetings_header_reconcile
      await reconcileHeader();

      // Step 4: meetings_diff_fetch
      await fetchDiff();

      // Step 5: ws_buffer_flush
      sessionChannel.markDiffApplied();
      setLastSync(new Date());

      // Step 6: prefetch_controller
      await prefetchTopCards();

      // Step 7: idle_sync
      setupIdleSync();

      setIsBootstrapping(false);
    } catch (error) {
      console.error('Bootstrap error:', error);
      setIsBootstrapping(false);
    }
  }

  async function reconcileHeader(): Promise<boolean> {
    try {
      const state = meetingsStore.getState();
      const header = await getSessionsHeader(state.range, state.showArchived);

      if (header.etag === state.etag) {
        return false;
      }

      meetingsStore.setState({
        last_event_id: header.last_event_id,
        etag: header.etag,
      });

      return true;
    } catch (error) {
      console.error('Header reconcile error:', error);
      return true;
    }
  }

  async function fetchDiff() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    const startTime = Date.now();

    try {
      const state = meetingsStore.getState();
      const diff = await getSessionsDiff(
        state.range,
        state.sort,
        state.last_event_id,
        state.cursor,
        abortControllerRef.current.signal
      );

      meetingsStore.applyDiff(diff.upserts, diff.deletes);
      meetingsStore.setState({
        last_event_id: diff.last_event_id,
        cursor: diff.cursor,
      });

      const finalState = meetingsStore.getState();
      await indexedDBCache.setMeetingsCache({
        byId: finalState.byId,
        groups: finalState.groups,
        last_event_id: finalState.last_event_id,
        etag: finalState.etag,
      });

      telemetry.track({
        event: 'diff_fetch',
        latency_ms: Date.now() - startTime,
        cache_hit: false,
        cards_painted: diff.upserts.length,
        ws_buffered: sessionChannel.getBufferedCount(),
      });
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error('Diff fetch error:', error);
      }
    }
  }

  async function prefetchTopCards() {
    const state = meetingsStore.getState();
    const allCards = [
      ...state.groups.liveNow,
      ...state.groups.today,
      ...state.groups.thisWeek,
      ...state.groups.earlier,
    ];

    await prefetchController.prefetchTopCards(allCards);
    await prefetchController.warmRefinedRoute();
  }

  function setupIdleSync() {
    const syncInterval = 30000; // 30 seconds

    idleSyncIntervalRef.current = window.setInterval(async () => {
      const needsRefresh = await reconcileHeader();
      if (needsRefresh) {
        await fetchDiff();
        setLastSync(new Date());
      }
    }, syncInterval);

    document.addEventListener('visibilitychange', async () => {
      if (document.visibilityState === 'visible') {
        const needsRefresh = await reconcileHeader();
        if (needsRefresh) {
          await fetchDiff();
          setLastSync(new Date());
        }
      }
    });
  }

  return {
    isBootstrapping,
    lastSync,
    refetch: fetchDiff,
  };
}
