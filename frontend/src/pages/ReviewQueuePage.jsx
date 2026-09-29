import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';

export default function ReviewQueuePage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQueue();
  }, []);

  async function fetchQueue() {
    setLoading(true);
    try {
      const res = await api.get('/api/entries', { params: { entry_status: 'submitted' } });
      setEntries(res.data);
    } catch (err) {
      console.error('Failed to load review queue', err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Review Queue</h1>
        <p>
          Click an entry to review it. Use middle-click or right-click → "Open in new tab" to open
          multiple entries side by side.
        </p>
      </div>

      {loading ? (
        <span className="spinner" />
      ) : entries.length === 0 ? (
        <div className="empty-state">
          <p>Your queue is empty!</p>
          <p className="text-muted mt-1">No submitted entries await your review.</p>
        </div>
      ) : (
        <>
          <div className="el-results-summary" style={{ marginBottom: 12 }}>
            <strong>{entries.length}</strong> {entries.length === 1 ? 'entry' : 'entries'} awaiting
            review
          </div>

          <div className="entry-list">
            {entries.map((entry) => (
              <Link
                to={`/review/${entry.id}`}
                key={entry.id}
                className="entry-card"
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
                <div className="entry-card-left">
                  <span className="entry-prompt">
                    {entry.code || `Entry for Prompt ${entry.prompt_id.substring(0, 8)}...`}
                  </span>
                  <span className="entry-meta">
                    Contributor: {entry.contributor_id.substring(0, 8)} &middot; Updated{' '}
                    {new Date(entry.updated_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="entry-card-right">
                  <span className="status-badge status-submitted">Pending Review</span>
                  <span className="rv-open-hint">Open →</span>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
