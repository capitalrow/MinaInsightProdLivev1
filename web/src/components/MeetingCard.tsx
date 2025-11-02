import { MeetingCard as MeetingCardType } from '@/types/meeting';
import { formatDistanceToNow, format } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { indexedDBCache } from '@/lib/cache/indexedDb';

interface MeetingCardProps {
  card: MeetingCardType;
  index: number;
  onArchive: (session_id: string) => void;
}

export function MeetingCard({ card, index, onArchive }: MeetingCardProps) {
  const navigate = useNavigate();

  const handleCardClick = async () => {
    const prefetchManifest = await indexedDBCache.getPrefetchManifest(card.session_id);
    
    navigate(`/sessions/${card.session_id}/refined`, {
      state: {
        prefetchManifest,
        backState: {
          scrollY: window.scrollY,
        },
      },
    });
  };

  const handleArchive = (e: React.MouseEvent) => {
    e.stopPropagation();
    onArchive(card.session_id);
  };

  const statusColors = {
    recording: 'bg-red-500 animate-pulse',
    processing: 'bg-yellow-500',
    ready: 'bg-green-500',
    archived: 'bg-gray-500',
  };

  return (
    <div
      className="meeting-card"
      style={{
        animationDelay: `${Math.min(index * 0.1, 0.7)}s`,
      }}
      onClick={handleCardClick}
    >
      <div className="meeting-card-inner">
        <div className="meeting-icon">
          <svg width="28" height="28" fill="white" viewBox="0 0 24 24">
            <path d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </div>

        <div className="meeting-content">
          <div className="meeting-header">
            <h3 className="meeting-title">{card.title || 'Untitled Meeting'}</h3>
            <span className={`status-pill ${statusColors[card.status]}`}>
              {card.status}
            </span>
          </div>

          <p className="meeting-date">
            {format(new Date(card.started_at), 'MMMM d, yyyy at h:mm a')}
          </p>

          <div className="meeting-meta">
            {card.duration_s && (
              <span className="meta-item">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {Math.round(card.duration_s / 60)} min
              </span>
            )}
            {card.tasks > 0 && (
              <span className="meta-item">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                {card.tasks} tasks
              </span>
            )}
            {card.highlights > 0 && (
              <span className="meta-item">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
                {card.highlights} highlights
              </span>
            )}
          </div>
        </div>

        <div className="meeting-actions">
          {card.status !== 'archived' && (
            <button className="btn-archive" onClick={handleArchive} title="Archive meeting">
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
              </svg>
              Archive
            </button>
          )}
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ opacity: 0.5 }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </div>
  );
}
