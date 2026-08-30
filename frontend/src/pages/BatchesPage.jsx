import { useState, useEffect } from 'react';
import api from '../api';

export default function BatchesPage() {
  const [batches, setBatches] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active batch
  const [activeBatch, setActiveBatch] = useState(null);

  // Create batch
  const [batchName, setBatchName] = useState('');
  const [creatingBatch, setCreatingBatch] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Assignment
  const [selectedPromptIds, setSelectedPromptIds] = useState(new Set());
  const [contributorId, setContributorId] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [toast, setToast] = useState(null); // { type: 'success'|'error', message }

  useEffect(() => { fetchData(); }, []);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  async function fetchData() {
    setLoading(true);
    try {
      const [batchesRes, promptsRes, usersRes] = await Promise.all([
        api.get('/api/batches'),
        api.get('/api/prompts'),
        api.get('/api/users'),
      ]);
      setBatches(batchesRes.data);
      setPrompts(promptsRes.data);
      setUsers(usersRes.data);
    } catch (err) {
      console.error('Error loading batch data', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBatch(e) {
    e.preventDefault();
    if (!batchName.trim()) return;
    setCreatingBatch(true);
    try {
      const res = await api.post('/api/batches', { name: batchName.trim() });
      setBatchName('');
      setShowCreateForm(false);
      await fetchData();
      setActiveBatch(res.data);
      setToast({ type: 'success', message: `Batch "${res.data.name}" created` });
    } catch (err) {
      setToast({ type: 'error', message: err.response?.data?.detail || 'Failed to create batch' });
    } finally {
      setCreatingBatch(false);
    }
  }

  function togglePrompt(id) {
    setSelectedPromptIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    if (selectedPromptIds.size === prompts.length) {
      setSelectedPromptIds(new Set());
    } else {
      setSelectedPromptIds(new Set(prompts.map(p => p.id)));
    }
  }

  async function handleAssign() {
    if (selectedPromptIds.size === 0) return setToast({ type: 'error', message: 'Select at least one prompt' });
    if (!contributorId) return setToast({ type: 'error', message: 'Pick a contributor' });
    if (!reviewerId) return setToast({ type: 'error', message: 'Pick a reviewer' });
    if (contributorId === reviewerId) return setToast({ type: 'error', message: 'Contributor and reviewer must be different people' });

    setAssigning(true);
    try {
      // Add prompts to batch first (idempotent)
      for (const pid of selectedPromptIds) {
        try {
          await api.post(`/api/batches/${activeBatch.id}/prompts`, { prompt_id: pid });
        } catch (err) {
          if (err.response?.status !== 400 && err.response?.status !== 409) throw err;
        }
      }

      // Bulk assign
      const res = await api.post(`/api/batches/${activeBatch.id}/assignments`, {
        prompt_ids: Array.from(selectedPromptIds),
        contributor_id: contributorId,
        reviewer_id: reviewerId,
      });

      setSelectedPromptIds(new Set());
      setToast({
        type: 'success',
        message: `Done! ${res.data.moved} assigned, ${res.data.ignored} skipped (already in progress).`
      });
    } catch (err) {
      setToast({ type: 'error', message: err.response?.data?.detail || 'Assignment failed' });
    } finally {
      setAssigning(false);
    }
  }

  const contributors = users.filter(u => u.role === 'contributor');
  const reviewers = users.filter(u => ['reviewer', 'lead', 'admin'].includes(u.role));

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><span className="spinner" /></div>;

  return (
    <div>
      <div className="page-header">
        <h1>Batches</h1>
        <p>Create batches, then assign prompts with a contributor + reviewer pair</p>
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          padding: '10px 16px',
          marginBottom: 16,
          borderRadius: 'var(--radius)',
          fontSize: '0.9rem',
          background: toast.type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${toast.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          color: toast.type === 'success' ? 'var(--status-approved)' : 'var(--status-rejected)',
        }}>
          {toast.message}
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

        {/* ─── LEFT: Batch List ─── */}
        <div style={{ width: 260, flexShrink: 0 }}>
          <div className="flex justify-between items-center mb-2">
            <h2 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Batches</h2>
            <button
              className="btn btn-sm btn-primary"
              onClick={() => setShowCreateForm(v => !v)}
              style={{ padding: '4px 10px', fontSize: '0.8rem' }}
            >
              {showCreateForm ? 'Cancel' : '+ New'}
            </button>
          </div>

          {showCreateForm && (
            <form onSubmit={handleCreateBatch} style={{ marginBottom: 12 }}>
              <input
                type="text"
                className="form-input"
                placeholder="Batch name..."
                value={batchName}
                onChange={e => setBatchName(e.target.value)}
                autoFocus
                style={{ marginBottom: 8 }}
              />
              <button type="submit" className="btn btn-primary btn-sm" disabled={creatingBatch} style={{ width: '100%' }}>
                {creatingBatch ? <span className="spinner" /> : 'Create Batch'}
              </button>
            </form>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {batches.length === 0 && (
              <p className="text-muted" style={{ fontSize: '0.85rem', padding: 12 }}>No batches yet. Create one above.</p>
            )}
            {batches.map(b => (
              <button
                key={b.id}
                onClick={() => { setActiveBatch(b); setSelectedPromptIds(new Set()); }}
                style={{
                  textAlign: 'left',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius)',
                  border: activeBatch?.id === b.id ? '1px solid var(--accent)' : '1px solid var(--border)',
                  background: activeBatch?.id === b.id ? 'rgba(99,102,241,0.08)' : 'var(--bg-card)',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{b.name}</div>
                <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: 2 }}>
                  Created {new Date(b.created_at).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* ─── RIGHT: Assignment Panel ─── */}
        <div style={{ flex: 1 }}>
          {!activeBatch ? (
            <div className="card" style={{ textAlign: 'center', padding: 48 }}>
              <p className="text-muted">← Select a batch to start assigning prompts</p>
            </div>
          ) : (
            <div className="card">
              <h2 style={{ fontSize: '1.1rem', marginBottom: 4 }}>{activeBatch.name}</h2>
              <p className="text-muted" style={{ fontSize: '0.8rem', marginBottom: 20 }}>
                Select prompts below, pick a contributor + reviewer, then hit Assign.
              </p>

              {/* ── Team Selection (sticky at top) ── */}
              <div style={{
                display: 'flex',
                gap: 12,
                marginBottom: 16,
                padding: '12px 16px',
                background: 'var(--bg-primary)',
                borderRadius: 'var(--radius)',
                alignItems: 'flex-end',
              }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 500, marginBottom: 4, display: 'block' }}>Contributor</label>
                  <select className="form-input" value={contributorId} onChange={e => setContributorId(e.target.value)}>
                    <option value="">Select...</option>
                    {contributors.map(u => (
                      <option key={u.id} value={u.id}>{u.display_name}</option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 500, marginBottom: 4, display: 'block' }}>Reviewer</label>
                  <select className="form-input" value={reviewerId} onChange={e => setReviewerId(e.target.value)}>
                    <option value="">Select...</option>
                    {reviewers.map(u => (
                      <option key={u.id} value={u.id}>{u.display_name}</option>
                    ))}
                  </select>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={handleAssign}
                  disabled={assigning || selectedPromptIds.size === 0}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {assigning ? <span className="spinner" /> : `Assign ${selectedPromptIds.size > 0 ? `(${selectedPromptIds.size})` : ''}`}
                </button>
              </div>

              {/* ── Prompt Checklist ── */}
              <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 500 }}>
                  Prompts ({prompts.length})
                </label>
                <button
                  className="btn btn-sm btn-outline"
                  onClick={selectAll}
                  style={{ fontSize: '0.75rem', padding: '2px 10px' }}
                >
                  {selectedPromptIds.size === prompts.length ? 'Deselect All' : 'Select All'}
                </button>
              </div>

              {prompts.length === 0 ? (
                <p className="text-muted" style={{ padding: 16, textAlign: 'center', fontSize: '0.85rem' }}>
                  No prompts created yet. Go to the Prompts page to add some first.
                </p>
              ) : (
                <div style={{
                  maxHeight: 400,
                  overflowY: 'auto',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                }}>
                  {prompts.map(p => {
                    const checked = selectedPromptIds.has(p.id);
                    return (
                      <label
                        key={p.id}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 10,
                          padding: '10px 12px',
                          borderBottom: '1px solid var(--border)',
                          cursor: 'pointer',
                          background: checked ? 'rgba(99,102,241,0.06)' : 'transparent',
                          transition: 'background 0.1s',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => togglePrompt(p.id)}
                          style={{ marginTop: 3, accentColor: 'var(--accent)' }}
                        />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                            <span style={{
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              color: 'var(--accent)',
                              fontFamily: 'monospace',
                            }}>
                              {p.code || '—'}
                            </span>
                            {p.tags?.length > 0 && (
                              <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                                {p.tags.slice(0, 3).join(', ')}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '0.85rem', lineHeight: 1.4 }}>
                            {p.prompt_text}
                          </div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
