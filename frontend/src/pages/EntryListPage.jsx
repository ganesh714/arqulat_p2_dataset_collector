import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api';

export default function EntryListPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all | draft | submitted | approved | needs_fix | rejected
  const navigate = useNavigate();

  useEffect(() => {
    fetchEntries();
  }, [filter]);

  async function fetchEntries() {
    setLoading(true);
    try {
      const params = {};
      if (filter !== 'all') params.entry_status = filter;
      const res = await api.get('/api/entries', { params });
      setEntries(res.data);
    } catch (err) {
      console.error('Failed to load entries', err);
    } finally {
      setLoading(false);
    }
  }

  const statusCounts = entries.reduce((acc, e) => {
    acc[e.status] = (acc[e.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <div className="page-header">
        <h1>My Entries</h1>
        <p>Your assigned prompts and their current status</p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-2" style={{ marginBottom: 20 }}>
        {['all', 'draft', 'needs_fix', 'submitted', 'approved', 'rejected'].map((f) => (
          <button
            key={f}
            className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'All' : f.replace('_', ' ')}
            {f === 'all'
              ? ` (${entries.length})`
              : statusCounts[f]
                ? ` (${statusCounts[f]})`
                : ''}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-page" style={{ minHeight: 200 }}>
          <span className="spinner" />
        </div>
      ) : entries.length === 0 ? (
        <div className="empty-state">
          <p>No entries found{filter !== 'all' ? ` with status "${filter}"` : ''}.</p>
          <p className="text-muted mt-1">Entries appear here once a Lead assigns prompts to you.</p>
        </div>
      ) : (
        <div className="entry-list">
          {entries
            .filter((e) => filter === 'all' || e.status === filter)
            .map((entry) => (
              <Link
                to={`/entries/${entry.id}`}
                key={entry.id}
                className="entry-card"
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
                <div className="entry-card-left">
                  <span className="entry-prompt">
                    {entry.code || `Entry ${entry.id.substring(0,8)}`}
                  </span>
                  <span className="entry-meta">
                    Updated {new Date(entry.updated_at).toLocaleDateString()} &middot; Batch {entry.batch_id.substring(0, 8)}
                  </span>
                </div>
                <div className="entry-card-right">
                  <span className={`status-badge status-${entry.status}`}>
                    {entry.status.replace('_', ' ')}
                  </span>
                </div>
              </Link>
            ))}
        </div>
      )}
    </div>
  );
}
