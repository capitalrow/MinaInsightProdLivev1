import { useEffect, useState } from 'react';
import { useMeetingsBootstrap } from '@/hooks/useMeetingsBootstrap';
import { useMeetingsStore } from '@/hooks/useMeetingsStore';
import { MeetingCard } from '@/components/MeetingCard';
import { meetingsStore } from '@/stores/meetingsStore';
import { offlineQueue } from '@/services/offlineQueue';
import { patchSession } from '@/api/sessions';
import { ulid } from 'ulid';
import './meetings.css';

const WORKSPACE_ID = 1; // TODO: Get from context/props

export function MeetingsPage() {
  const { isBootstrapping, lastSync } = useMeetingsBootstrap(WORKSPACE_ID);
  const state = useMeetingsStore();
  const [undoTimers, setUndoTimers] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    offlineQueue.init();
  }, []);

  const handleArchive = async (session_id: string) => {
    const client_ulid = ulid();
    
    // Optimistic UI update
    const card = state.byId[session_id];
    if (!card) return;

    const updatedCard = { ...card, status: 'archived' as const };
    meetingsStore.applyDiff([updatedCard], []);

    // Show toast with undo
    const timer = window.setTimeout(() => {
      setUndoTimers((prev) => {
        const next = new Map(prev);
        next.delete(session_id);
        return next;
      });
    }, 15000);

    setUndoTimers((prev) => new Map(prev).set(session_id, timer));

    try {
      if (navigator.onLine) {
        await patchSession(session_id, 'archive', {}, client_ulid);
      } else {
        offlineQueue.enqueueArchive(session_id);
      }
    } catch (error) {
      console.error('Archive failed:', error);
      meetingsStore.applyDiff([card], []);
    }
  };

  const handleUndo = (session_id: string) => {
    const timer = undoTimers.get(session_id);
    if (timer) {
      clearTimeout(timer);
      setUndoTimers((prev) => {
        const next = new Map(prev);
        next.delete(session_id);
        return next;
      });
    }

    const card = state.byId[session_id];
    if (card) {
      const restoredCard = { ...card, status: 'ready' as const };
      meetingsStore.applyDiff([restoredCard], []);
      
      // Send restore request to backend
      patchSession(session_id, 'restore', {}, ulid()).catch(console.error);
    }
  };

  const handleFilterChange = (range?: any, sort?: any, showArchived?: boolean) => {
    meetingsStore.updateFilters(range, sort, showArchived);
  };

  const renderGroup = (title: string, sessionIds: string[]) => {
    if (sessionIds.length === 0) return null;

    return (
      <div className="meeting-group" key={title}>
        <h2 className="group-title">{title}</h2>
        <div className="meeting-grid">
          {sessionIds.map((id, index) => {
            const card = state.byId[id];
            if (!card) return null;
            return (
              <MeetingCard
                key={id}
                card={card}
                index={index}
                onArchive={handleArchive}
              />
            );
          })}
        </div>
      </div>
    );
  };

  if (isBootstrapping && !state.isHydrated) {
    return (
      <div className="meetings-container">
        <div className="loading-skeleton">
          <div className="skeleton-header"></div>
          <div className="skeleton-cards">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-card"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const liveCount = state.groups.liveNow.length;

  return (
    <div className="meetings-container">
      <div className="meetings-header">
        <div>
          <h1 className="meetings-title">Meetings</h1>
          <p className="meetings-subtitle">View and manage all your recorded meetings</p>
          {lastSync && (
            <p className="last-sync">Updated {lastSync.toLocaleTimeString()}</p>
          )}
        </div>
        <button className="btn-primary">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          New Recording
        </button>
      </div>

      <div className="meetings-tabs">
        <button
          className={`tab-btn ${!state.showArchived ? 'active' : ''}`}
          onClick={() => handleFilterChange(undefined, undefined, false)}
        >
          Active
          <span className="tab-count">
            {state.groups.liveNow.length + state.groups.today.length + state.groups.thisWeek.length + state.groups.earlier.length}
          </span>
        </button>
        <button
          className={`tab-btn ${state.showArchived ? 'active' : ''}`}
          onClick={() => handleFilterChange(undefined, undefined, true)}
        >
          Archive
          <span className="tab-count">{state.groups.archived.length}</span>
        </button>
      </div>

      <div className="filters-card">
        <select
          value={state.range}
          onChange={(e) => handleFilterChange(e.target.value as any, undefined, undefined)}
          className="filter-select"
        >
          <option value="last30">Last 30 Days</option>
          <option value="last90">Last 90 Days</option>
          <option value="all">All Time</option>
        </select>
      </div>

      {liveCount > 0 && (
        <div className="live-now-banner">
          <span className="live-indicator"></span>
          <span>Live Now ({liveCount})</span>
        </div>
      )}

      <div className="meetings-content">
        {renderGroup('Live Now', state.groups.liveNow)}
        {renderGroup('Today', state.groups.today)}
        {renderGroup('This Week', state.groups.thisWeek)}
        {renderGroup('Earlier', state.groups.earlier)}
        {state.showArchived && renderGroup('Archived', state.groups.archived)}
      </div>

      {!state.isOnline && (
        <div className="offline-banner">
          You're offline. Changes will sync when you reconnect.
        </div>
      )}
      
      {/* Undo toast */}
      {Array.from(undoTimers.keys()).map((session_id) => (
        <div key={session_id} className="undo-toast">
          <span>Meeting archived</span>
          <button onClick={() => handleUndo(session_id)} className="undo-button">
            Undo
          </button>
        </div>
      ))}
    </div>
  );
}
