import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';

const POLL_INTERVAL = 3000;

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

  // Test-run state
  const [running, setRunning] = useState(false);
  const [latestJob, setLatestJob] = useState(null);
  const [viewMode, setViewMode] = useState('3d'); // '3d' or 'render'
  const pollRef = useRef(null);
  const modelViewerRef = useRef(null);

  // Build token-bearing URLs for the proxy endpoints
  const token = localStorage.getItem('access_token');
  const modelUrl = entry?.glb_url ? `http://localhost:8000/api/entries/${id}/model?token=${token}` : null;
  const renderUrl = entry?.render_url ? `http://localhost:8000/api/entries/${id}/render?token=${token}` : null;

  useEffect(() => {
    fetchEntry();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [id]);

  async function fetchEntry() {
    setLoading(true);
    try {
      const res = await api.get('/api/entries', { params: {} });
      const found = res.data.find((e) => e.id === id);
      if (!found) { setError('Entry not found'); setLoading(false); return; }
      setEntry(found);
      setScript(found.script || '');

      try {
        const promptRes = await api.get(`/api/prompts/${found.prompt_id}`);
        setPrompt(promptRes.data);
      } catch { setPrompt(null); }

      // Fetch latest jobs
      try {
        const jobsRes = await api.get(`/api/entries/${id}/jobs`);
        if (jobsRes.data.length > 0) {
          setLatestJob(jobsRes.data[0]);
        }
      } catch { /* no jobs yet */ }
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
    if (!script.trim()) { setError('Cannot submit an empty script.'); return; }
    setSubmitting(true);
    try {
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

  // ─── Test Run ─────────────────────────────────────────────
  async function handleTestRun() {
    if (!script.trim()) { setError('Cannot run an empty script.'); return; }
    setRunning(true);
    setError('');
    try {
      const res = await api.post(`/api/entries/${id}/test-run`, { script });
      setLatestJob(res.data);
      startPolling();
    } catch (err) {
      setError(err.response?.data?.detail || 'Test run failed');
      setRunning(false);
    }
  }

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const jobsRes = await api.get(`/api/entries/${id}/jobs`);
        if (jobsRes.data.length > 0) {
          const latest = jobsRes.data[0];
          setLatestJob(latest);
          if (latest.status === 'done' || latest.status === 'failed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setRunning(false);
            // Refresh entry to get updated render_url / glb_url
            if (latest.status === 'done') {
              const entryRes = await api.get('/api/entries');
              const found = entryRes.data.find((e) => e.id === id);
              if (found) setEntry(found);
            }
          }
        }
      } catch { /* ignore poll errors */ }
    }, POLL_INTERVAL);
  }

  // ─── Viewer controls ─────────────────────────────────────
  function resetCamera() {
    const mv = modelViewerRef.current;
    if (!mv) return;
    mv.cameraOrbit = 'auto auto auto';
    mv.cameraTarget = 'auto auto auto';
    mv.fieldOfView = 'auto';
  }

  function toggleAutoRotate() {
    const mv = modelViewerRef.current;
    if (!mv) return;
    if (mv.hasAttribute('auto-rotate')) {
      mv.removeAttribute('auto-rotate');
    } else {
      mv.setAttribute('auto-rotate', '');
    }
  }

  // ─── Render ──────────────────────────────────────────────
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

  const jobStatusColor = {
    pending: 'var(--status-submitted)',
    running: 'var(--accent)',
    done: 'var(--status-approved)',
    failed: 'var(--status-rejected)',
  };

  return (
    <div className="entry-editor-layout">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="entry-editor-topbar">
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/entries')}>
          &larr; Back
        </button>
        <div className="flex items-center gap-2">
          <span className="entry-code-label">{entry.code || 'No code'}</span>
          <span className={`status-badge status-${entry.status}`}>
            {entry.status.replace('_', ' ')}
          </span>
        </div>
      </div>

      {error && <div className="login-error" style={{ margin: '0 0 12px' }}>{error}</div>}

      <div className="entry-editor-panels">
        {/* ── Left Panel: Script Editor ─────────────────── */}
        <div className="entry-editor-left">
          {/* Prompt */}
          <div className="ee-prompt-card">
            <div className="ee-prompt-label">Prompt {prompt?.code ? `(${prompt.code})` : ''}</div>
            <div className="ee-prompt-text">{prompt?.prompt_text || 'Loading prompt...'}</div>
            {prompt?.tags?.length > 0 && (
              <div className="ee-prompt-tags">
                {prompt.tags.map((tag, i) => (
                  <span key={i} className="ee-tag">{tag}</span>
                ))}
              </div>
            )}
          </div>

          {/* Reviewer notes */}
          {entry.reviewer_notes && entry.status === 'needs_fix' && (
            <div className="ee-reviewer-notes">
              <strong>Reviewer Notes:</strong> {entry.reviewer_notes}
            </div>
          )}

          {/* Script editor */}
          <div className="ee-editor-header">
            <span>Blender Python Script</span>
            <div className="ee-editor-actions">
              {isEditable && (
                <button
                  className="btn btn-sm ee-run-btn"
                  onClick={handleTestRun}
                  disabled={running}
                >
                  {running ? (
                    <><span className="spinner spinner-sm" /> Running...</>
                  ) : (
                    <>▶ Run (Test)</>
                  )}
                </button>
              )}
            </div>
          </div>
          <textarea
            className="ee-script-textarea"
            value={script}
            onChange={(e) => setScript(e.target.value)}
            disabled={!isEditable}
            placeholder={`import bpy\n\n# Your Blender script here...\n# This script will be executed by the worker to generate\n# the 3D model and render for this prompt.`}
            spellCheck={false}
          />

          {/* Execution log */}
          {latestJob && (
            <div className="ee-log-panel">
              <div className="ee-log-header">
                <span>Execution Log</span>
                <span className="ee-log-status" style={{ color: jobStatusColor[latestJob.status] || 'inherit' }}>
                  {latestJob.is_test_run ? '🧪 Test' : '📦 Submit'} • {latestJob.status.toUpperCase()}
                </span>
              </div>
              <div className="ee-log-body">
                {latestJob.status === 'pending' && 'Waiting for worker to claim job...'}
                {latestJob.status === 'running' && 'Blender is executing the script...'}
                {latestJob.status === 'done' && (latestJob.error_log || '✓ Script executed successfully. No errors.')}
                {latestJob.status === 'failed' && (latestJob.error_log || 'Job failed — no error log available.')}
              </div>
            </div>
          )}

          {/* Bottom actions */}
          <div className="ee-bottom-actions">
            {isEditable && (
              <>
                <button className="btn btn-outline" onClick={handleSave} disabled={saving}>
                  {saving ? <span className="spinner spinner-sm" /> : saved ? '✓ Saved!' : 'Save draft'}
                </button>
                <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
                  {submitting ? <span className="spinner spinner-sm" /> : 'Submit for review'}
                </button>
              </>
            )}
            {isSubmitted && (
              <button className="btn btn-outline" onClick={handleWithdraw} disabled={withdrawing}>
                {withdrawing ? <span className="spinner spinner-sm" /> : 'Withdraw'}
              </button>
            )}
            {['approved', 'rejected'].includes(entry.status) && (
              <p className="text-muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                This entry has been {entry.status} and is read-only.
              </p>
            )}
          </div>
        </div>

        {/* ── Right Panel: 3D Viewer ───────────────────── */}
        <div className="entry-editor-right">
          {/* View toggle */}
          <div className="ee-view-toggle">
            <label className={viewMode === '3d' ? 'active' : ''}>
              <input
                type="radio"
                name="viewMode"
                value="3d"
                checked={viewMode === '3d'}
                onChange={() => setViewMode('3d')}
              />
              3D View
            </label>
            <label className={viewMode === 'render' ? 'active' : ''}>
              <input
                type="radio"
                name="viewMode"
                value="render"
                checked={viewMode === 'render'}
                onChange={() => setViewMode('render')}
              />
              Render
            </label>
          </div>

          <div className="ee-viewer-container">
            {viewMode === '3d' ? (
              modelUrl ? (
                <model-viewer
                  ref={modelViewerRef}
                  src={modelUrl}
                  alt="Generated 3D Model"
                  auto-rotate
                  camera-controls
                  shadow-intensity="1"
                  interaction-prompt="none"
                  style={{ width: '100%', height: '100%' }}
                />
              ) : (
                <div className="ee-viewer-empty">
                  <div className="ee-viewer-empty-icon">📦</div>
                  <p>No 3D model yet</p>
                  <p className="text-muted">Run the script to generate a model</p>
                </div>
              )
            ) : (
              renderUrl ? (
                <img
                  src={renderUrl}
                  alt="Render output"
                  className="ee-render-img"
                />
              ) : (
                <div className="ee-viewer-empty">
                  <div className="ee-viewer-empty-icon">🖼️</div>
                  <p>No render yet</p>
                  <p className="text-muted">Run the script to generate a render</p>
                </div>
              )
            )}
          </div>

          {/* Viewer toolbar */}
          {viewMode === '3d' && modelUrl && (
            <div className="ee-viewer-toolbar">
              <button onClick={resetCamera} title="Reset View">🏠 Reset</button>
              <button onClick={toggleAutoRotate} title="Toggle Auto Rotate">🔁 Spin</button>
            </div>
          )}

          {/* File links */}
          {(entry.render_url || entry.glb_url) && (
            <div className="ee-file-links">
              {entry.render_url && (
                <a href={entry.render_url} target="_blank" rel="noreferrer" className="ee-file-link">
                  📷 Open render in Drive
                </a>
              )}
              {entry.glb_url && (
                <a href={entry.glb_url} target="_blank" rel="noreferrer" className="ee-file-link">
                  📦 Open model in Drive
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
