import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';

export default function EntryEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [entry, setEntry] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [script, setScript] = useState('');
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchEntry();
  }, [id]);

  async function fetchEntry() {
    setLoading(true);
    try {
      // Fetch entry
      const res = await api.get('/api/entries', { params: {} });
      const found = res.data.find((e) => e.id === id);
      if (!found) {
        setError('Entry not found');
        setLoading(false);
        return;
      }
      setEntry(found);
      setScript(found.script || '');

      // Fetch prompt text
      try {
        const promptRes = await api.get(`/api/prompts/${found.prompt_id}`);
        setPrompt(promptRes.data);
      } catch {
        // Prompt endpoint may not exist yet; just show the ID
        setPrompt(null);
      }
    } catch (err) {
      setError('Failed to load entry');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      const res = await api.patch(`/api/entries/${id}`, { script });
      setEntry(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit() {
    if (!script.trim()) {
      setError('Cannot submit an empty script.');
      return;
    }
    setSubmitting(true);
    try {
      // Save first, then submit
      await api.patch(`/api/entries/${id}`, { script });
      const res = await api.post(`/api/entries/${id}/submit`);
      setEntry(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleWithdraw() {
    setWithdrawing(true);
    try {
      const res = await api.post(`/api/entries/${id}/withdraw`);
      setEntry(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Withdraw failed');
    } finally {
      setWithdrawing(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-page" style={{ minHeight: 300 }}>
        <span className="spinner" /> Loading entry...
      </div>
    );
  }

  if (error && !entry) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="btn btn-outline mt-4" onClick={() => navigate('/entries')}>
          Back to entries
        </button>
      </div>
    );
  }

  const isEditable = ['draft', 'needs_fix'].includes(entry.status);
  const isSubmitted = entry.status === 'submitted';

  return (
    <div className="editor-container">
      {/* Header */}
      <div className="editor-header">
        <button className="back-link btn btn-outline btn-sm" onClick={() => navigate('/entries')}>
          &larr; Back to entries
        </button>
        <div className="flex items-center gap-2">
          <span className={`status-badge status-${entry.status}`}>
            {entry.status.replace('_', ' ')}
          </span>
        </div>
      </div>

      {/* Prompt */}
      <div className="editor-prompt-card">
        <h3>Prompt {prompt?.code ? `(${prompt.code})` : ''}</h3>
        <p>{prompt?.prompt_text || `Loading prompt...`}</p>
        {prompt?.tags?.length > 0 && (
          <div className="mt-1">
            {prompt.tags.map((tag, i) => (
              <span key={i} style={{
                display: 'inline-block',
                padding: '2px 8px',
                marginRight: 4,
                background: 'var(--accent-bg)',
                color: 'var(--accent)',
                borderRadius: 12,
                fontSize: '0.75rem'
              }}>
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Reviewer notes (if needs_fix) */}
      {entry.reviewer_notes && entry.status === 'needs_fix' && (
        <div className="reviewer-notes">
          <strong>Reviewer Notes:</strong>
          {entry.reviewer_notes}
        </div>
      )}

      {/* Error banner */}
      {error && <div className="login-error">{error}</div>}

      {/* Script Editor */}
      <div className="form-group">
        <label>Blender Python Script</label>
        <textarea
          className="form-input"
          value={script}
          onChange={(e) => setScript(e.target.value)}
          disabled={!isEditable}
          placeholder={`import bpy\n\n# Your Blender script here...\n# This script will be executed by the worker to generate\n# the 3D model and render for this prompt.`}
          style={{ minHeight: 320, fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}
        />
      </div>

      {/* Render preview (if completed) */}
      {entry.render_url && (
        <div className="card">
          <h3 style={{ fontSize: '0.85rem', marginBottom: 8, color: 'var(--text-secondary)' }}>Render Output</h3>
          <p style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>
            Render: <a href={entry.render_url} target="_blank" rel="noreferrer">{entry.render_url}</a>
          </p>
          {entry.glb_url && (
            <p style={{ fontSize: '0.85rem', wordBreak: 'break-all', marginTop: 4 }}>
              GLB: <a href={entry.glb_url} target="_blank" rel="noreferrer">{entry.glb_url}</a>
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="editor-actions">
        {isEditable && (
          <>
            <button className="btn btn-outline" onClick={handleSave} disabled={saving}>
              {saving ? <span className="spinner" /> : saved ? 'Saved!' : 'Save draft'}
            </button>
            <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
              {submitting ? <span className="spinner" /> : 'Submit for review'}
            </button>
          </>
        )}

        {isSubmitted && (
          <button className="btn btn-outline" onClick={handleWithdraw} disabled={withdrawing}>
            {withdrawing ? <span className="spinner" /> : 'Withdraw submission'}
          </button>
        )}

        {['approved', 'rejected'].includes(entry.status) && (
          <p className="text-muted" style={{ fontSize: '0.85rem' }}>
            This entry has been {entry.status} and is read-only.
          </p>
        )}
      </div>
    </div>
  );
}
