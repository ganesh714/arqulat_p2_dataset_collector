import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../context/AuthContext';

export default function BatchesPage() {
  const { user } = useAuth();
  const [batches, setBatches] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active batch + detail
  const [activeBatch, setActiveBatch] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Assignment form
  const [panelView, setPanelView] = useState('overview'); // overview | assign
  const [selectedPromptIds, setSelectedPromptIds] = useState(new Set());
  const [contributorId, setContributorId] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [toast, setToast] = useState(null);

  // Create batch form (admin only)
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newBatchName, setNewBatchName] = useState('');
  const [newReviewerId, setNewReviewerId] = useState('');
  const [newContributorIds, setNewContributorIds] = useState(new Set());
  const [creatingBatch, setCreatingBatch] = useState(false);

  useEffect(() => { fetchData(); }, []);
  useEffect(() => {
    if (toast) { const t = setTimeout(() => setToast(null), 4000); return () => clearTimeout(t); }
  }, [toast]);

  async function fetchData() {
    setLoading(true);
    try {
      const requests = [api.get('/api/batches'), api.get('/api/prompts')];
      if (user?.role === 'admin') requests.push(api.get('/api/users'));
      const results = await Promise.all(requests);
      setBatches(results[0].data);
      setPrompts(results[1].data);
      if (results[2]) setUsers(results[2].data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }

  async function selectBatch(batch) {
    setActiveBatch(batch);
    setPanelView('overview');
    setSelectedPromptIds(new Set());
    setAdminSelectedPromptIds(new Set());
    await loadDetail(batch.id);
  }

  async function loadDetail(batchId) {
    setDetailLoading(true);
    try {
      const res = await api.get(`/api/batches/${batchId}/detail`);
      setDetail(res.data);
    } catch (err) { console.error(err); setDetail(null); }
    finally { setDetailLoading(false); }
  }

  const [adminSelectedPromptIds, setAdminSelectedPromptIds] = useState(new Set());
  const [addingPrompts, setAddingPrompts] = useState(false);

  function togglePrompt(id) {
    setSelectedPromptIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleAdminPrompt(id) {
    setAdminSelectedPromptIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function handleAddPromptsToBatch() {
    if (adminSelectedPromptIds.size === 0) return setToast({ type: 'error', message: 'Select at least one prompt' });
    setAddingPrompts(true);
    try {
      const res = await api.post(`/api/batches/${activeBatch.id}/prompts`, {
        prompt_ids: Array.from(adminSelectedPromptIds),
      });
      setAdminSelectedPromptIds(new Set());
      setToast({ type: 'success', message: `Added ${res.data.added} prompts to batch. ${res.data.ignored} ignored.` });
      await loadDetail(activeBatch.id);
    } catch (err) {
      setToast({ type: 'error', message: err.response?.data?.detail || 'Failed to add prompts' });
    } finally { setAddingPrompts(false); }
  }

  async function handleAssign() {
    if (!contributorId) return setToast({ type: 'error', message: 'Pick a contributor' });
    if (selectedPromptIds.size === 0) return setToast({ type: 'error', message: 'Select at least one prompt' });

    setAssigning(true);
    try {
      const res = await api.post(`/api/batches/${activeBatch.id}/assignments`, {
        prompt_ids: Array.from(selectedPromptIds),
        contributor_id: contributorId,
      });
      setSelectedPromptIds(new Set());
      setToast({ type: 'success', message: `Assigned ${res.data.moved} prompts. ${res.data.ignored} already assigned.` });
      setPanelView('overview');
      await loadDetail(activeBatch.id);
    } catch (err) {
      setToast({ type: 'error', message: err.response?.data?.detail || 'Assignment failed' });
    } finally { setAssigning(false); }
  }

  // Stats from detail
  const stats = detail ? (() => {
    const a = detail.assignments;
    const statusCounts = {};
    a.forEach(r => { statusCounts[r.entry_status] = (statusCounts[r.entry_status] || 0) + 1; });
    return { total: a.length, statusCounts };
  })() : null;

  // Already assigned prompt IDs in this batch (by Reviewer)
  const assignedPromptIds = new Set(detail?.assignments?.map(a => a.prompt_id) || []);
  
  // Prompts already added to this batch (by Admin)
  const batchPromptIds = new Set(detail?.batch_prompts?.map(p => p.id) || []);

  const reviewerUsers = users.filter(u => ['reviewer', 'lead'].includes(u.role));
  const contributorUsers = users.filter(u => u.role === 'contributor');

  function toggleNewContributor(id) {
    setNewContributorIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function handleCreateBatch(e) {
    e.preventDefault();
    if (!newReviewerId) return setToast({ type: 'error', message: 'Select a reviewer' });
    if (newContributorIds.size === 0) return setToast({ type: 'error', message: 'Select at least one contributor' });
    setCreatingBatch(true);
    try {
      const res = await api.post('/api/batches', {
        name: newBatchName,
        reviewer_id: newReviewerId,
        contributor_ids: Array.from(newContributorIds),
      });
      setNewBatchName(''); setNewReviewerId(''); setNewContributorIds(new Set());
      setShowCreateForm(false);
      setToast({ type: 'success', message: `Batch "${res.data.name}" created!` });
      await fetchData();
      selectBatch(res.data);
    } catch (err) {
      setToast({ type: 'error', message: err.response?.data?.detail || 'Failed to create batch' });
    } finally { setCreatingBatch(false); }
  }

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><span className="spinner" /></div>;

  return (
    <div>
      <div className="page-header">
        <h1>My Batches</h1>
        <p>
          {user?.role === 'admin'
            ? 'All batches in the system'
            : 'Batches assigned to you — assign prompts to your contributors'}
        </p>
      </div>

      {toast && (
        <div style={{
          padding: '10px 16px', marginBottom: 16, borderRadius: 'var(--radius)', fontSize: '0.9rem',
          background: toast.type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${toast.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          color: toast.type === 'success' ? 'var(--status-approved)' : 'var(--status-rejected)',
        }}>{toast.message}</div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

        {/* ── LEFT: Batch List ── */}
        <div style={{ width: 260, flexShrink: 0 }}>
          {/* Admin: Create Batch Button */}
          {user?.role === 'admin' && (
            <div style={{ marginBottom: 12 }}>
              <button className="btn btn-primary" style={{ width: '100%', marginBottom: 8 }}
                onClick={() => setShowCreateForm(v => !v)}>
                {showCreateForm ? '✕ Cancel' : '+ Create New Batch'}
              </button>

              {showCreateForm && (
                <form onSubmit={handleCreateBatch} className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div className="form-group">
                    <label style={{ fontSize: '0.8rem' }}>Batch Name</label>
                    <input type="text" className="form-input" required value={newBatchName}
                      onChange={e => setNewBatchName(e.target.value)} placeholder="e.g. Week 1 Chairs" />
                  </div>
                  <div className="form-group">
                    <label style={{ fontSize: '0.8rem' }}>Reviewer</label>
                    <select className="form-input" value={newReviewerId} onChange={e => setNewReviewerId(e.target.value)} required>
                      <option value="">Select...</option>
                      {reviewerUsers.map(u => <option key={u.id} value={u.id}>{u.display_name}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label style={{ fontSize: '0.8rem' }}>Contributors ({newContributorIds.size})</label>
                    <div style={{ maxHeight: 140, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      {contributorUsers.map(u => (
                        <label key={u.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: '1px solid var(--border)', cursor: 'pointer', fontSize: '0.85rem' }}>
                          <input type="checkbox" checked={newContributorIds.has(u.id)} onChange={() => toggleNewContributor(u.id)} style={{ accentColor: 'var(--accent)' }} />
                          {u.display_name}
                        </label>
                      ))}
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={creatingBatch}>
                    {creatingBatch ? <span className="spinner" /> : 'Create Batch'}
                  </button>
                </form>
              )}
            </div>
          )}

          {batches.length === 0 ? (
            <p className="text-muted" style={{ fontSize: '0.85rem', padding: 12 }}>
              {user?.role === 'admin' ? 'No batches yet. Click the button above.' : 'No batches assigned to you yet.'}
            </p>
          ) : batches.map(b => (
            <button key={b.id} onClick={() => selectBatch(b)}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '12px 14px',
                marginBottom: 4, borderRadius: 'var(--radius)',
                border: activeBatch?.id === b.id ? '1px solid var(--accent)' : '1px solid var(--border)',
                background: activeBatch?.id === b.id ? 'rgba(99,102,241,0.08)' : 'var(--bg-card)',
                cursor: 'pointer', transition: 'all 0.15s',
              }}>
              <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{b.name}</div>
              <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: 2 }}>
                {new Date(b.created_at).toLocaleDateString()} · {b.status}
              </div>
            </button>
          ))}
        </div>

        {/* ── RIGHT: Detail Panel ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!activeBatch ? (
            <div className="card" style={{ textAlign: 'center', padding: 48 }}>
              <p className="text-muted">← Select a batch</p>
            </div>
          ) : detailLoading ? (
            <div className="card" style={{ textAlign: 'center', padding: 48 }}><span className="spinner" /></div>
          ) : !detail ? (
            <div className="card"><p className="text-muted">Failed to load batch detail</p></div>
          ) : (
            <div className="card">
              {/* Header */}
              <div className="flex justify-between items-center" style={{ marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: '1.1rem', marginBottom: 2 }}>{detail.name}</h2>
                  <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                    Reviewer: <strong>{detail.reviewer?.display_name || '—'}</strong>
                  </span>
                </div>
                <div className="flex gap-2">
                  <button className={`btn btn-sm ${panelView === 'overview' ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => setPanelView('overview')}>Overview</button>
                  <button className={`btn btn-sm ${panelView === 'assign' ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => setPanelView('assign')}>Assign to Team</button>
                  {(user?.role === 'admin' || user?.role === 'lead') && (
                    <button className={`btn btn-sm ${panelView === 'manage_prompts' ? 'btn-primary' : 'btn-outline'}`}
                      onClick={() => setPanelView('manage_prompts')}>+ Add Prompts to Batch</button>
                  )}
                </div>
              </div>

              {/* Team Info */}
              <div style={{
                display: 'flex', gap: 16, marginBottom: 16, padding: '10px 16px',
                background: 'var(--bg-primary)', borderRadius: 'var(--radius)', fontSize: '0.85rem',
                flexWrap: 'wrap',
              }}>
                <div>
                  <span className="text-muted">Contributors:</span>{' '}
                  <strong>{detail.contributors?.map(c => c.display_name).join(', ') || 'None'}</strong>
                </div>
                {stats && stats.total > 0 && (
                  <>
                    <div style={{ borderLeft: '1px solid var(--border)', paddingLeft: 16 }}>
                      <strong>{stats.total}</strong> <span className="text-muted">assigned</span>
                    </div>
                    {Object.entries(stats.statusCounts).map(([s, c]) => (
                      <span key={s} className={`status-badge status-${s}`}>{c} {s}</span>
                    ))}
                  </>
                )}
              </div>

              {/* ── OVERVIEW ── */}
              {panelView === 'overview' && (
                detail.assignments.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 32 }}>
                    <p className="text-muted" style={{ marginBottom: 12 }}>No prompts assigned yet.</p>
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
                          <th style={{ padding: 8 }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.assignments.map(row => (
                          <tr key={row.assignment_id} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: '10px 8px 10px 0' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent)', fontSize: '0.8rem' }}>
                                {row.prompt_code || '—'}
                              </span>
                              <div className="text-muted" style={{ fontSize: '0.8rem', marginTop: 2, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {row.prompt_text}
                              </div>
                            </td>
                            <td style={{ padding: 8, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                              {row.entry_code || '—'}
                            </td>
                            <td style={{ padding: 8 }}>{row.contributor_name}</td>
                            <td style={{ padding: 8 }}>
                              <span className={`status-badge status-${row.entry_status}`}>{row.entry_status}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              )}

              {/* ── ASSIGN PROMPTS (Reviewer View) ── */}
              {panelView === 'assign' && (
                <>
                  {/* Contributor Picker */}
                  <div style={{
                    display: 'flex', gap: 12, marginBottom: 16, padding: '12px 16px',
                    background: 'var(--bg-primary)', borderRadius: 'var(--radius)', alignItems: 'flex-end',
                  }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 500, marginBottom: 4, display: 'block' }}>
                        Assign to Contributor
                      </label>
                      <select className="form-input" value={contributorId} onChange={e => setContributorId(e.target.value)}>
                        <option value="">Select contributor...</option>
                        {detail.contributors?.map(c => (
                          <option key={c.id} value={c.id}>{c.display_name}</option>
                        ))}
                      </select>
                    </div>
                    <button className="btn btn-primary" onClick={handleAssign}
                      disabled={assigning || selectedPromptIds.size === 0} style={{ whiteSpace: 'nowrap' }}>
                      {assigning ? <span className="spinner" /> : `Assign (${selectedPromptIds.size})`}
                    </button>
                  </div>

                  {/* Prompt Checklist from Batch's Prompts */}
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, marginBottom: 8, display: 'block' }}>
                    Select Prompts ({detail.batch_prompts?.length || 0} total in this batch, {assignedPromptIds.size} already assigned)
                  </label>

                  {(!detail.batch_prompts || detail.batch_prompts.length === 0) ? (
                    <p className="text-muted" style={{ padding: 16, textAlign: 'center' }}>No prompts have been added to this batch yet.</p>
                  ) : (
                    <div style={{ maxHeight: 400, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      {detail.batch_prompts.map(p => {
                        const alreadyAssigned = assignedPromptIds.has(p.id);
                        const checked = selectedPromptIds.has(p.id);
                        return (
                          <label key={p.id} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
                            borderBottom: '1px solid var(--border)', cursor: alreadyAssigned ? 'default' : 'pointer',
                            background: alreadyAssigned ? 'rgba(16,185,129,0.04)' : checked ? 'rgba(99,102,241,0.06)' : 'transparent',
                            opacity: alreadyAssigned ? 0.6 : 1,
                          }}>
                            <input type="checkbox" checked={checked} disabled={alreadyAssigned}
                              onChange={() => togglePrompt(p.id)}
                              style={{ marginTop: 3, accentColor: 'var(--accent)' }} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent)', fontFamily: 'monospace' }}>
                                  {p.code || '—'}
                                </span>
                                {alreadyAssigned && (
                                  <span className="text-muted" style={{ fontSize: '0.7rem' }}>✓ assigned</span>
                                )}
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

              {/* ── MANAGE PROMPTS (Admin/Lead View) ── */}
              {panelView === 'manage_prompts' && (
                <>
                  <div style={{
                    display: 'flex', gap: 12, marginBottom: 16, padding: '12px 16px',
                    background: 'var(--bg-primary)', borderRadius: 'var(--radius)', alignItems: 'center', justifyContent: 'space-between'
                  }}>
                    <span style={{ fontSize: '0.85rem' }}>Select prompts from the global pool to add to this batch.</span>
                    <button className="btn btn-primary btn-sm" onClick={handleAddPromptsToBatch}
                      disabled={addingPrompts || adminSelectedPromptIds.size === 0} style={{ whiteSpace: 'nowrap' }}>
                      {addingPrompts ? <span className="spinner" /> : `Add to Batch (${adminSelectedPromptIds.size})`}
                    </button>
                  </div>

                  {prompts.length === 0 ? (
                    <p className="text-muted" style={{ padding: 16, textAlign: 'center' }}>No prompts exist in the system yet.</p>
                  ) : (
                    <div style={{ maxHeight: 400, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      {prompts.map(p => {
                        const alreadyInBatch = batchPromptIds.has(p.id);
                        const checked = adminSelectedPromptIds.has(p.id);
                        return (
                          <label key={p.id} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
                            borderBottom: '1px solid var(--border)', cursor: alreadyInBatch ? 'default' : 'pointer',
                            background: alreadyInBatch ? 'rgba(16,185,129,0.04)' : checked ? 'rgba(99,102,241,0.06)' : 'transparent',
                            opacity: alreadyInBatch ? 0.6 : 1,
                          }}>
                            <input type="checkbox" checked={checked} disabled={alreadyInBatch}
                              onChange={() => toggleAdminPrompt(p.id)}
                              style={{ marginTop: 3, accentColor: 'var(--accent)' }} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent)', fontFamily: 'monospace' }}>
                                  {p.code || '—'}
                                </span>
                                {alreadyInBatch && (
                                  <span className="text-muted" style={{ fontSize: '0.7rem' }}>✓ in batch</span>
                                )}
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
