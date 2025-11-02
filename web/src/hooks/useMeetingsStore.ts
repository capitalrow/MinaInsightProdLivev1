import { useEffect, useState } from 'react';
import { meetingsStore } from '@/stores/meetingsStore';
import { MeetingsState } from '@/types/meeting';

export function useMeetingsStore(): MeetingsState {
  const [state, setState] = useState<MeetingsState>(meetingsStore.getState());

  useEffect(() => {
    const unsubscribe = meetingsStore.subscribe(setState);
    return unsubscribe;
  }, []);

  return state;
}
