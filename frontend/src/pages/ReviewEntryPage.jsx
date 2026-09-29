import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';

export default function ReviewEntryPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const [entry, setEntry] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Review form
  const [action, setAction] = useState('approved');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [reviewDone, setReviewDone] = useState(false);

  const [viewMode, setViewMode] = useState('3d');
  const modelViewerRef = useRef(null);

  useEffect(() => {
    fetchEntry();
  }, [id]);

  async function fetchEntry() {
    setLoading(true);
    setError('');
    try {
      // Fetch entry via the entries list and find by ID
      const res = await api.get('/api/entries');
      const found = res.data.find((e) => e.id === id);
      if (!found) {
        setError('Entry not found');
        setLoading(false);
        return;
      }
      setEntry(found);

      // Fetch prompt details
      if (found.prompt_id) {
        try {
          const promptRes = await api.get(`/api/prompts/${found.prompt_id}`);
          setPrompt(promptRes.data);
        } catch {}
      }
    } catch (err) {
      setError('Failed to load entry');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitReview(e) {
    e.preventDefault();
    if (!entry) return;

    setSubmitting(true);
    setReviewError('');

    try {
      await api.post(`/api/reviews/${entry.id}`, {
        action,
        notes: notes || undefined,
      });
      setReviewDone(true);
    } catch (err) {
      setReviewError(err.response?.data?.detail || 'Review submission failed');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-page" style={{ minHeight: 400 }}>
        <span className="spinner" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="btn btn-outline mt-2" onClick={() => navigate('/review-queue')}>
          ← Back to Queue
        </button>
      </div>
    );
  }

  if (reviewDone) {
    return (
      <div className="empty-state" style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '3rem', marginBottom: 16 }}>
          {action === 'approved' ? '✅' : action === 'needs_fix' ? '🔧' : '❌'}
        </div>
        <h2>Review Submitted!</h2>
        <p style={{ marginTop: 8 }}>
          Entry <strong>{entry.code}</strong> has been marked as{' '}
          <span className={`status-badge status-${action}`}>{action.replace('_', ' ')}</span>
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 20 }}>
          <button className="btn btn-primary" onClick={() => navigate('/review-queue')}>
            ← Back to Queue
          </button>
          <button className="btn btn-outline" onClick={() => window.close()}>
            Close Tab
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rv-page">
      {/* Header */}
      <div className="rv-header">
        <div className="rv-header-left">
          <button className="btn btn-sm btn-outline" onClick={() => navigate('/review-queue')}>
            ← Queue
          </button>
          <h1 className="rv-title">{entry.code || `Entry ${id.substring(0, 8)}`}</h1>
          <span className={`status-badge status-${entry.status}`}>
            {entry.status.replace('_', ' ')}
          </span>
        </div>
      </div>

      <div className="rv-layout">
        {/* ── Left: 3D Viewer ── */}
        <div className="rv-viewer-col">
          {/* Prompt info */}
          {prompt && (
            <div className="rv-prompt-card">
              <h3>📋 Prompt</h3>
              <p className="rv-prompt-text">{prompt.prompt_text}</p>
              {prompt.tags && prompt.tags.length > 0 && (
                <div className="rv-tags">
                  {prompt.tags.map((t, i) => (
                    <span key={i} className="rv-tag">{t}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* View toggle */}
          <div className="ee-view-toggle" style={{ marginBottom: 8 }}>
            <label className={viewMode === '3d' ? 'active' : ''}>
              <input type="radio" checked={viewMode === '3d'} onChange={() => setViewMode('3d')} />
              3D View
            </label>
            <label className={viewMode === 'render' ? 'active' : ''}>
              <input type="radio" checked={viewMode === 'render'} onChange={() => setViewMode('render')} />
              Render
            </label>
          </div>

          {/* 3D / Render viewer */}
          <div className="rv-viewer-box">
            {viewMode === '3d' ? (
              entry.glb_url ? (
                <model-viewer
                  ref={modelViewerRef}
                  src={`${baseUrl}/api/entries/${entry.id}/model?token=${localStorage.getItem('access_token')}`}
                  alt="3D Model"
                  auto-rotate
                  camera-controls
                  min-camera-orbit="auto 0deg auto"
                  max-camera-orbit="auto 180deg auto"
                  shadow-intensity="1"
                  interaction-prompt="none"
                  style={{ width: '100%', height: '100%' }}
                />
              ) : (
                <div className="rv-viewer-empty">No 3D model available</div>
              )
            ) : entry.render_url ? (
              <img
                src={`${baseUrl}/api/entries/${entry.id}/render?token=${localStorage.getItem('access_token')}`}
                alt="Render"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            ) : (
              <div className="rv-viewer-empty">No render available</div>
            )}
          </div>
        </div>

        {/* ── Right: Code + Review Form ── */}
        <div className="rv-details-col">
          {/* Think Block */}
          <div className="rv-section">
            <h3>💭 Think Block</h3>
            <pre className="rv-code-block">{entry.think_block || '(empty)'}</pre>
          </div>

          {/* Phase 2 Code */}
          <div className="rv-section">
            <h3>🐍 Phase 2 Code</h3>
            <pre className="rv-code-block rv-code-tall">{entry.phase2_code || '(empty)'}</pre>
          </div>

          {/* Reviewer Notes (if any exist from previous reviews) */}
          {entry.reviewer_notes && (
            <div className="rv-section">
              <h3>📝 Previous Reviewer Notes</h3>
              <div className="rv-notes-display">{entry.reviewer_notes}</div>
            </div>
          )}

          {/* Review Decision Form */}
          {entry.status === 'submitted' && (
            <form onSubmit={handleSubmitReview} className="rv-review-form">
              <h3>⚖️ Your Decision</h3>

              {reviewError && <div className="login-error">{reviewError}</div>}

              <div className="rv-decision-btns">
                <button
                  type="button"
                  className={`rv-decision-btn rv-decision-approve ${action === 'approved' ? 'rv-decision-active' : ''}`}
                  onClick={() => setAction('approved')}
                >
                  ✅ Approve
                </button>
                <button
                  type="button"
                  className={`rv-decision-btn rv-decision-fix ${action === 'needs_fix' ? 'rv-decision-active' : ''}`}
                  onClick={() => setAction('needs_fix')}
                >
                  🔧 Needs Fix
                </button>
                <button
                  type="button"
                  className={`rv-decision-btn rv-decision-reject ${action === 'rejected' ? 'rv-decision-active' : ''}`}
                  onClick={() => setAction('rejected')}
                >
                  ❌ Reject
                </button>
              </div>

              {(action === 'needs_fix' || action === 'rejected') && (
                <textarea
                  className="form-input rv-notes-input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  required
                  placeholder="Explain what needs to be fixed or why it was rejected..."
                />
              )}

              <button
                type="submit"
                className={`btn ${action === 'rejected' ? 'btn-danger' : 'btn-primary'}`}
                disabled={submitting}
                style={{ width: '100%' }}
              >
                {submitting ? <span className="spinner" /> : `Submit: ${action.replace('_', ' ')}`}
              </button>
            </form>
          )}

          {entry.status !== 'submitted' && (
            <div className="rv-already-reviewed">
              This entry is currently <span className={`status-badge status-${entry.status}`}>{entry.status.replace('_', ' ')}</span> and cannot be reviewed.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
