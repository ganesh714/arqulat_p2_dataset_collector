import { useState, useEffect } from 'react';
import api from '../api';

export default function ReviewQueuePage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Review modal/inline state
  const [activeEntry, setActiveEntry] = useState(null);
  const [action, setAction] = useState('approved');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [viewMode, setViewMode] = useState('3d');

  useEffect(() => {
    fetchQueue();
  }, []);

  async function fetchQueue() {
    setLoading(true);
    try {
      // Reviewers see entries assigned to them (via backend logic).
      // They should primarily look at "submitted" entries waiting for review.
      const res = await api.get('/api/entries', { params: { entry_status: 'submitted' } });
      setEntries(res.data);
    } catch (err) {
      console.error('Failed to load review queue', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitReview(e) {
    e.preventDefault();
    if (!activeEntry) return;
    
    setSubmitting(true);
    setError('');
    
    try {
      await api.post(`/api/reviews/${activeEntry.id}`, {
        action,
        notes: notes || undefined
      });
      
      // Remove from queue locally
      setEntries(entries.filter(en => en.id !== activeEntry.id));
      setActiveEntry(null);
      setNotes('');
      setAction('approved');
    } catch (err) {
      setError(err.response?.data?.detail || 'Review failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Review Queue</h1>
        <p>Evaluate submitted entries and outputs</p>
      </div>

      {loading ? (
        <span className="spinner"/>
      ) : entries.length === 0 ? (
        <div className="empty-state">
          <p>Your queue is empty!</p>
          <p className="text-muted mt-1">No submitted entries await your review.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
          {/* List */}
          <div className="entry-list" style={{ flex: 1 }}>
            {entries.map(entry => (
              <div 
                key={entry.id} 
                className="entry-card"
                onClick={() => setActiveEntry(entry)}
                style={{ borderColor: activeEntry?.id === entry.id ? 'var(--accent)' : 'var(--border)' }}
              >
                <div className="entry-card-left">
                  <span className="entry-prompt">{entry.code || `Entry for Prompt ${entry.prompt_id.substring(0, 8)}...`}</span>
                  <span className="entry-meta">Contributor: {entry.contributor_id.substring(0,8)}</span>
                </div>
                <div className="entry-card-right">
                  <span className="status-badge status-submitted">Pending Review</span>
                </div>
              </div>
            ))}
          </div>

          {/* Active Review Panel */}
          {activeEntry && (
            <div className="card" style={{ flex: 1, position: 'sticky', top: 20 }}>
              <div className="flex justify-between items-center mb-4">
                <h2 style={{ fontSize: '1.1rem' }}>Review Entry</h2>
                <button className="btn btn-sm btn-outline" onClick={() => setActiveEntry(null)}>Close</button>
              </div>

              {error && <div className="login-error mb-2">{error}</div>}

              {/* Render Output */}
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Generated Output</h3>
                <div style={{ padding: 12, background: 'var(--bg-primary)', borderRadius: 'var(--radius)', marginTop: 8 }}>
                  <div className="ee-view-toggle" style={{ position: 'relative', top: 0, right: 0, marginBottom: 8, display: 'inline-flex' }}>
                    <label className={viewMode === '3d' ? 'active' : ''}>
                      <input type="radio" checked={viewMode === '3d'} onChange={() => setViewMode('3d')} />
                      3D View
                    </label>
                    <label className={viewMode === 'render' ? 'active' : ''}>
                      <input type="radio" checked={viewMode === 'render'} onChange={() => setViewMode('render')} />
                      Render
                    </label>
                  </div>
                  
                  <div style={{ height: 300, background: '#1e1e1e', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                    {viewMode === '3d' ? (
                      activeEntry.glb_url ? (
                        <model-viewer
                          src={`http://localhost:8000/api/entries/${activeEntry.id}/model?token=${localStorage.getItem('access_token')}`}
                          auto-rotate
                          camera-controls
                          shadow-intensity="1"
                          style={{ width: '100%', height: '100%' }}
                        />
                      ) : (
                        <div className="text-muted" style={{ padding: 20 }}>No 3D model available.</div>
                      )
                    ) : (
                      activeEntry.render_url ? (
                        <img 
                          src={`http://localhost:8000/api/entries/${activeEntry.id}/render?token=${localStorage.getItem('access_token')}`} 
                          alt="Render" 
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
                        />
                      ) : (
                        <div className="text-muted" style={{ padding: 20 }}>No render available.</div>
                      )
                    )}
                  </div>
                </div>
              </div>

              {/* Script */}
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Blender Script</h3>
                <pre style={{ 
                  background: 'var(--bg-input)', 
                  padding: 12, 
                  borderRadius: 'var(--radius)', 
                  fontSize: '0.75rem',
                  maxHeight: 150,
                  overflowY: 'auto',
                  marginTop: 8
                }}>
                  {activeEntry.script}
                </pre>
              </div>

              {/* Decision Form */}
              <form onSubmit={handleSubmitReview} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="form-group">
                  <label>Decision</label>
                  <select className="form-input" value={action} onChange={e => setAction(e.target.value)}>
                    <option value="approved">Approve</option>
                    <option value="needs_fix">Needs Fix</option>
                    <option value="rejected">Reject (Drop)</option>
                  </select>
                </div>
                
                {(action === 'needs_fix' || action === 'rejected') && (
                  <div className="form-group">
                    <label>Feedback Notes (Required)</label>
                    <textarea 
                      className="form-input" 
                      value={notes} 
                      onChange={e => setNotes(e.target.value)}
                      required
                      placeholder="Explain what needs to be fixed..."
                      style={{ minHeight: 80 }}
                    />
                  </div>
                )}

                <button type="submit" className={`btn ${action === 'rejected' ? 'btn-danger' : 'btn-primary'}`} disabled={submitting}>
                  {submitting ? <span className="spinner"/> : 'Submit Decision'}
                </button>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
