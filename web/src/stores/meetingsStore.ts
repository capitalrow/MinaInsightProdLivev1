import { 
  MeetingCard, 
  MeetingsState, 
  MeetingsGroups, 
  RangeFilter,
  SortOrder 
} from '@/types/meeting';
import { 
  isToday, 
  isThisWeek, 
  parseISO, 
  startOfDay, 
  getISOWeek,
  getYear 
} from 'date-fns';

export function buildGroups(
  byId: Record<string, MeetingCard>,
  range: RangeFilter,
  showArchived: boolean
): MeetingsGroups {
  const groups: MeetingsGroups = {
    liveNow: [],
    today: [],
    thisWeek: [],
    earlier: [],
    archived: [],
  };

  const now = new Date();
  const currentWeek = getISOWeek(now);
  const currentYear = getYear(now);

  Object.values(byId).forEach((card) => {
    const { session_id, status, started_at } = card;
    const startDate = parseISO(started_at);

    if (status === 'archived') {
      if (showArchived) {
        groups.archived.push(session_id);
      }
      return;
    }

    if (status === 'recording') {
      groups.liveNow.push(session_id);
      return;
    }

    if (isToday(startDate)) {
      groups.today.push(session_id);
      return;
    }

    const cardWeek = getISOWeek(startDate);
    const cardYear = getYear(startDate);
    if (cardWeek === currentWeek && cardYear === currentYear) {
      groups.thisWeek.push(session_id);
      return;
    }

    groups.earlier.push(session_id);
  });

  return groups;
}

export function createInitialState(): MeetingsState {
  return {
    range: 'last30',
    sort: 'newest',
    showArchived: false,
    groups: {
      liveNow: [],
      today: [],
      thisWeek: [],
      earlier: [],
      archived: [],
    },
    byId: {},
    last_event_id: 0,
    etag: '',
    cursor: undefined,
    isHydrated: false,
    isOnline: navigator.onLine,
    offlineQueue: [],
  };
}

type StateListener = (state: MeetingsState) => void;

class MeetingsStore {
  private state: MeetingsState = createInitialState();
  private listeners: Set<StateListener> = new Set();

  getState(): MeetingsState {
    return this.state;
  }

  subscribe(listener: StateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    this.listeners.forEach((listener) => listener(this.state));
  }

  setState(updates: Partial<MeetingsState>) {
    this.state = { ...this.state, ...updates };
    this.notify();
  }

  applyDiff(upserts: MeetingCard[], deletes: string[]) {
    const newById = { ...this.state.byId };

    upserts.forEach((card) => {
      newById[card.session_id] = card;
    });

    deletes.forEach((session_id) => {
      delete newById[session_id];
    });

    const newGroups = buildGroups(newById, this.state.range, this.state.showArchived);

    this.setState({
      byId: newById,
      groups: newGroups,
    });
  }

  updateFilters(range?: RangeFilter, sort?: SortOrder, showArchived?: boolean) {
    const updates: Partial<MeetingsState> = {};
    
    if (range !== undefined) updates.range = range;
    if (sort !== undefined) updates.sort = sort;
    if (showArchived !== undefined) updates.showArchived = showArchived;

    if (range !== undefined || showArchived !== undefined) {
      const newRange = range ?? this.state.range;
      const newShowArchived = showArchived ?? this.state.showArchived;
      updates.groups = buildGroups(this.state.byId, newRange, newShowArchived);
    }

    this.setState(updates);
  }

  setOnlineStatus(isOnline: boolean) {
    this.setState({ isOnline });
  }

  addToOfflineQueue(operation: MeetingsState['offlineQueue'][0]) {
    this.setState({
      offlineQueue: [...this.state.offlineQueue, operation],
    });
  }

  removeFromOfflineQueue(client_ulid: string) {
    this.setState({
      offlineQueue: this.state.offlineQueue.filter(
        (op) => op.client_ulid !== client_ulid
      ),
    });
  }

  clearOfflineQueue() {
    this.setState({ offlineQueue: [] });
  }

  reset() {
    this.state = createInitialState();
    this.notify();
  }
}

export const meetingsStore = new MeetingsStore();
