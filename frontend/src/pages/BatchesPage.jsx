import { useState, useEffect } from 'react';
import api from '../api';

export default function BatchesPage() {
  const [batches, setBatches] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active batch + its detail
  const [activeBatch, setActiveBatch] = useState(null);
  const [batchDetail, setBatchDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Create batch
  const [batchName, setBatchName] = useState('');
  const [creatingBatch, setCreatingBatch] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Assignment form
  const [selectedPromptIds, setSelectedPromptIds] = useState(new Set());
  const [contributorId, setContributorId] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [toast, setToast] = useState(null);

  // View toggle: 'assign' or 'view'
  const [panelView, setPanelView] = useState('view');

  useEffect(() => { fetchData(); }, []);

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

  async function selectBatch(batch) {
    setActiveBatch(batch);
    setSelectedPromptIds(new Set());
    setPanelView('view');
    await loadBatchDetail(batch.id);
  }

  async function loadBatchDetail(batchId) {
    setDetailLoading(true);
    try {
      const res = await api.get(`/api/batches/${batchId}/detail`);
      setBatchDetail(res.data);
    } catch (err) {
      console.error('Failed to load batch detail', err);
      setBatchDetail(null);
    } finally {
      setDetailLoading(false);
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
      selectBatch(res.data);
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
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function selectAll() {
    if (selectedPromptIds.size === prompts.length) setSelectedPromptIds(new Set());
    else setSelectedPromptIds(new Set(prompts.map(p => p.id)));
  }

  async function handleAssign() {
    if (selectedPromptIds.size === 0) return setToast({ type: 'error', message: 'Select at least one prompt' });
    if (!contributorId) return setToast({ type: 'error', message: 'Pick a contributor' });
    if (!reviewerId) return setToast({ type: 'error', message: 'Pick a reviewer' });
    if (contributorId === reviewerId) return setToast({ type: 'error', message: 'Contributor and reviewer must be different' });

    setAssigning(true);
    try {
      for (const pid of selectedPromptIds) {
        try { await api.post(`/api/batches/${activeBatch.id}/prompts`, { prompt_id: pid }); }
        catch (err) { if (err.response?.status !== 400 && err.response?.status !== 409) throw err; }
      }
      const res = await api.post(`/api/batches/${activeBatch.id}/assignments`, {
        prompt_ids: Array.from(selectedPromptIds),
        contributor_id: contributorId,
        reviewer_id: reviewerId,
      });
      setSelectedPromptIds(new Set());
      setToast({ type: 'success', message: `Done! ${res.data.moved} assigned, ${res.data.ignored} skipped.` });
      setPanelView('view');
      await loadBatchDetail(activeBatch.id);
    } catch (err) {
      setToast({ type: 'error', message: err.response?.data?.detail || 'Assignment failed' });
    } finally {
      setAssigning(false);
    }
  }

  const contributors = users.filter(u => u.role === 'contributor');
  const reviewers = users.filter(u => ['reviewer', 'lead', 'admin'].includes(u.role));

  // Compute summary stats from batch detail
  const stats = batchDetail ? (() => {
    const a = batchDetail.assignments;
    const uniqueContributors = new Set(a.map(r => r.contributor_id));
    const uniqueReviewers = new Set(a.map(r => r.reviewer_id));
    const statusCounts = {};
    a.forEach(r => { statusCounts[r.entry_status] = (statusCounts[r.entry_status] || 0) + 1; });
    return { total: a.length, contributors: uniqueContributors.size, reviewers: uniqueReviewers.size, statusCounts };
  })() : null;

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><span className="spinner" /></div>;

  return (
    <div>
      <div className="page-header">
        <h1>Batches</h1>
        <p>Create batches, assign prompts to contributor + reviewer pairs, track progress</p>
      </div>

      {toast && (
        <div style={{
          padding: '10px 16px', marginBottom: 16, borderRadius: 'var(--radius)', fontSize: '0.9rem',
          background: toast.type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${toast.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          color: toast.type === 'success' ? 'var(--status-approved)' : 'var(--status-rejected)',
        }}>
          {toast.message}
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

        {/* ─── LEFT: Batch Sidebar ─── */}
        <div style={{ width: 240, flexShrink: 0 }}>
          <div className="flex justify-between items-center mb-2">
            <h2 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Batches</h2>
            <button className="btn btn-sm btn-primary" onClick={() => setShowCreateForm(v => !v)}
              style={{ padding: '4px 10px', fontSize: '0.8rem' }}>
              {showCreateForm ? '✕' : '+ New'}
            </button>
          </div>

          {showCreateForm && (
            <form onSubmit={handleCreateBatch} style={{ marginBottom: 12 }}>
              <input type="text" className="form-input" placeholder="Batch name..."
                value={batchName} onChange={e => setBatchName(e.target.value)} autoFocus style={{ marginBottom: 8 }} />
              <button type="submit" className="btn btn-primary btn-sm" disabled={creatingBatch} style={{ width: '100%' }}>
                {creatingBatch ? <span className="spinner" /> : 'Create'}
              </button>
            </form>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {batches.length === 0 && (
              <p className="text-muted" style={{ fontSize: '0.85rem', padding: 12 }}>No batches yet.</p>
            )}
            {batches.map(b => (
              <button key={b.id} onClick={() => selectBatch(b)}
                style={{
                  textAlign: 'left', padding: '10px 12px', borderRadius: 'var(--radius)',
                  border: activeBatch?.id === b.id ? '1px solid var(--accent)' : '1px solid var(--border)',
                  background: activeBatch?.id === b.id ? 'rgba(99,102,241,0.08)' : 'var(--bg-card)',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}>
                <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{b.name}</div>
                <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: 2 }}>
                  {new Date(b.created_at).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* ─── RIGHT: Detail / Assign Panel ─── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!activeBatch ? (
            <div className="card" style={{ textAlign: 'center', padding: 48 }}>
              <p className="text-muted">← Select a batch to see its assignments</p>
            </div>
          ) : (
            <div className="card">
              {/* Header */}
              <div className="flex justify-between items-center" style={{ marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: '1.1rem', marginBottom: 2 }}>{activeBatch.name}</h2>
                  <span className="text-muted" style={{ fontSize: '0.8rem' }}>Status: {activeBatch.status}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    className={`btn btn-sm ${panelView === 'view' ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => setPanelView('view')}>
                    View Assignments
                  </button>
                  <button
                    className={`btn btn-sm ${panelView === 'assign' ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => setPanelView('assign')}>
                    + Assign Prompts
                  </button>
                </div>
              </div>

              {/* ── Stats Bar ── */}
              {stats && stats.total > 0 && (
                <div style={{
                  display: 'flex', gap: 16, marginBottom: 16, padding: '10px 16px',
                  background: 'var(--bg-primary)', borderRadius: 'var(--radius)', fontSize: '0.85rem',
                }}>
                  <div><strong>{stats.total}</strong> <span className="text-muted">prompts</span></div>
                  <div><strong>{stats.contributors}</strong> <span className="text-muted">contributors</span></div>
                  <div><strong>{stats.reviewers}</strong> <span className="text-muted">reviewers</span></div>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                    {Object.entries(stats.statusCounts).map(([s, c]) => (
                      <span key={s} className={`status-badge status-${s}`}>{c} {s}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* ── VIEW: Assignments Table ── */}
              {panelView === 'view' && (
                detailLoading ? (
                  <div style={{ textAlign: 'center', padding: 32 }}><span className="spinner" /></div>
                ) : !batchDetail || batchDetail.assignments.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 32 }}>
                    <p className="text-muted" style={{ marginBottom: 12 }}>No assignments yet in this batch.</p>
                    <button className="btn btn-sm btn-primary" onClick={() => setPanelView('assign')}>
                      + Assign Prompts Now
                    </button>
                  </div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '2px solid var(--border)' }}>
                          <th style={{ padding: '8px 8px 8px 0' }}>Prompt</th>
                          <th style={{ padding: 8 }}>Entry</th>
                          <th style={{ padding: 8 }}>Contributor</th>
                          <th style={{ padding: 8 }}>Reviewer</th>
                          <th style={{ padding: 8 }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {batchDetail.assignments.map(row => (
                          <tr key={row.assignment_id} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: '10px 8px 10px 0' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent)', fontSize: '0.8rem' }}>
                                {row.prompt_code || '—'}
                              </span>
                              <div className="text-muted" style={{ fontSize: '0.8rem', marginTop: 2, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {row.prompt_text}
                              </div>
                            </td>
                            <td style={{ padding: 8, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                              {row.entry_code || '—'}
                            </td>
                            <td style={{ padding: 8 }}>{row.contributor_name}</td>
                            <td style={{ padding: 8 }}>{row.reviewer_name}</td>
                            <td style={{ padding: 8 }}>
                              <span className={`status-badge status-${row.entry_status}`}>
                                {row.entry_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              )}

              {/* ── ASSIGN: Prompt Picker ── */}
              {panelView === 'assign' && (
                <>
                  {/* Team Selection Bar */}
                  <div style={{
                    display: 'flex', gap: 12, marginBottom: 16, padding: '12px 16px',
                    background: 'var(--bg-primary)', borderRadius: 'var(--radius)', alignItems: 'flex-end',
                  }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 500, marginBottom: 4, display: 'block' }}>Contributor</label>
                      <select className="form-input" value={contributorId} onChange={e => setContributorId(e.target.value)}>
                        <option value="">Select...</option>
                        {contributors.map(u => <option key={u.id} value={u.id}>{u.display_name}</option>)}
                      </select>
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 500, marginBottom: 4, display: 'block' }}>Reviewer</label>
                      <select className="form-input" value={reviewerId} onChange={e => setReviewerId(e.target.value)}>
                        <option value="">Select...</option>
                        {reviewers.map(u => <option key={u.id} value={u.id}>{u.display_name}</option>)}
                      </select>
                    </div>
                    <button className="btn btn-primary" onClick={handleAssign}
                      disabled={assigning || selectedPromptIds.size === 0} style={{ whiteSpace: 'nowrap' }}>
                      {assigning ? <span className="spinner" /> : `Assign ${selectedPromptIds.size > 0 ? `(${selectedPromptIds.size})` : ''}`}
                    </button>
                  </div>

                  {/* Prompt Checklist */}
                  <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label style={{ fontSize: '0.85rem', fontWeight: 500 }}>Prompts ({prompts.length})</label>
                    <button className="btn btn-sm btn-outline" onClick={selectAll} style={{ fontSize: '0.75rem', padding: '2px 10px' }}>
                      {selectedPromptIds.size === prompts.length ? 'Deselect All' : 'Select All'}
                    </button>
                  </div>

                  {prompts.length === 0 ? (
                    <p className="text-muted" style={{ padding: 16, textAlign: 'center', fontSize: '0.85rem' }}>
                      No prompts yet. Go to the Prompts page to create some.
                    </p>
                  ) : (
                    <div style={{ maxHeight: 400, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      {prompts.map(p => {
                        const checked = selectedPromptIds.has(p.id);
                        return (
                          <label key={p.id} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
                            borderBottom: '1px solid var(--border)', cursor: 'pointer',
                            background: checked ? 'rgba(99,102,241,0.06)' : 'transparent', transition: 'background 0.1s',
                          }}>
                            <input type="checkbox" checked={checked} onChange={() => togglePrompt(p.id)}
                              style={{ marginTop: 3, accentColor: 'var(--accent)' }} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent)', fontFamily: 'monospace' }}>
                                  {p.code || '—'}
                                </span>
                              </div>
                              <div style={{ fontSize: '0.85rem', lineHeight: 1.4 }}>{p.prompt_text}</div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
