import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';

interface LocationState {
  prefetchManifest?: any;
  backState?: {
    range?: string;
    sort?: string;
    showArchived?: boolean;
    scrollY?: number;
  };
}

export function RefinedMeetingView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState;
  
  const [transcriptData, setTranscriptData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Use prefetched manifest if available
    if (state?.prefetchManifest) {
      setTranscriptData(state.prefetchManifest);
      setLoading(false);
    } else {
      // Fetch transcript data
      fetchTranscript();
    }
  }, [sessionId]);

  const fetchTranscript = async () => {
    try {
      const response = await fetch(`/api/transcript/manifest?session_id=${sessionId}`);
      const data = await response.json();
      setTranscriptData(data);
    } catch (error) {
      console.error('Failed to fetch transcript:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    // Restore previous state if available
    if (state?.backState) {
      navigate('/dashboard/meetings', {
        state: state.backState,
      });
      
      // Restore scroll position
      if (state.backState.scrollY) {
        setTimeout(() => {
          window.scrollTo(0, state.backState!.scrollY!);
        }, 0);
      }
    } else {
      navigate('/dashboard/meetings');
    }
  };

  if (loading) {
    return (
      <div className="refined-view-container">
        <div className="loading">Loading transcript...</div>
      </div>
    );
  }

  return (
    <div className="refined-view-container">
      <div className="refined-header">
        <button onClick={handleBack} className="back-button">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Meetings
        </button>
        <h1>{transcriptData?.title || 'Meeting Transcript'}</h1>
      </div>
      
      <div className="refined-content">
        {transcriptData ? (
          <div className="transcript-view">
            {/* Render transcript content here */}
            <pre>{JSON.stringify(transcriptData, null, 2)}</pre>
          </div>
        ) : (
          <div className="no-data">No transcript available</div>
        )}
      </div>
    </div>
  );
}

export default RefinedMeetingView;
