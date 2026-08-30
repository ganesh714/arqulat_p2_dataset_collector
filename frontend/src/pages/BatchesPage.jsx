import { useState, useEffect } from 'react';
import api from '../api';

export default function BatchesPage() {
  const [batches, setBatches] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Form states
  const [batchName, setBatchName] = useState('');
  const [creatingBatch, setCreatingBatch] = useState(false);

  // Assignment states
  const [selectedBatchId, setSelectedBatchId] = useState('');
  const [selectedPromptId, setSelectedPromptId] = useState('');
  const [assignContributorId, setAssignContributorId] = useState('');
  const [assignReviewerId, setAssignReviewerId] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState('');
  const [assignSuccess, setAssignSuccess] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const [batchesRes, promptsRes, usersRes] = await Promise.all([
        api.get('/api/batches'),
        api.get('/api/prompts'),
        api.get('/api/users')
      ]);
      setBatches(batchesRes.data);
      setPrompts(promptsRes.data);
      setUsers(usersRes.data);
      if (batchesRes.data.length > 0) setSelectedBatchId(batchesRes.data[0].id);
      if (promptsRes.data.length > 0) setSelectedPromptId(promptsRes.data[0].id);
    } catch (err) {
      console.error('Error loading batch data', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBatch(e) {
    e.preventDefault();
    setCreatingBatch(true);
    try {
      await api.post('/api/batches', { name: batchName });
      setBatchName('');
      await fetchData();
    } catch (err) {
      console.error(err);
      alert('Failed to create batch');
    } finally {
      setCreatingBatch(false);
    }
  }

  async function handleAssign(e) {
    e.preventDefault();
    setAssigning(true);
    setAssignError('');
    setAssignSuccess('');
    try {
      // Step 1: ensure prompt is in batch (idempotent/ignores if already added, but backend requires it)
      // Actually backend /api/batches/{id}/prompts adds it. We should do that first.
      try {
        await api.post(`/api/batches/${selectedBatchId}/prompts`, { prompt_id: selectedPromptId });
      } catch (err) {
        // Ignore 409 if already in batch
        if (err.response?.status !== 409) throw err;
      }

      // Step 2: Create assignment
      const res = await api.post(`/api/batches/${selectedBatchId}/assignments`, {
        prompt_ids: [selectedPromptId],
        contributor_id: assignContributorId,
        reviewer_id: assignReviewerId
      });
      
      setAssignSuccess(`Assigned! Moved: ${res.data.moved}, Ignored: ${res.data.ignored}`);
    } catch (err) {
      setAssignError(err.response?.data?.detail || 'Assignment failed');
    } finally {
      setAssigning(false);
    }
  }

  const contributors = users.filter(u => u.role === 'contributor');
  const reviewers = users.filter(u => ['reviewer', 'lead', 'admin'].includes(u.role));

  return (
    <div>
      <div className="page-header">
        <h1>Batches & Assignments</h1>
        <p>Group prompts and assign to teams</p>
      </div>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* Create Batch */}
        <div className="card" style={{ flex: 1 }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Create Batch</h2>
          <form onSubmit={handleCreateBatch} className="form-group">
            <label>Batch Name</label>
            <input 
              type="text" 
              className="form-input" 
              value={batchName} 
              onChange={e => setBatchName(e.target.value)} 
              required 
            />
            <button type="submit" className="btn btn-primary mt-2" disabled={creatingBatch}>
              {creatingBatch ? <span className="spinner"/> : 'Create'}
            </button>
          </form>

          <h3 style={{ fontSize: '0.9rem', marginTop: 24, marginBottom: 8, color: 'var(--text-secondary)' }}>Existing Batches</h3>
          {loading ? <span className="spinner"/> : (
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {batches.map(b => (
                <li key={b.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: '0.9rem' }}>
                  <strong>{b.name}</strong> <span className="text-muted">({b.id.substring(0,8)})</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Assignments */}
        <div className="card" style={{ flex: 1 }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Assign Prompts</h2>
          {assignError && <div className="login-error mb-2">{assignError}</div>}
          {assignSuccess && <div className="reviewer-notes mb-2" style={{ background: 'rgba(16,185,129,0.1)', borderColor: 'rgba(16,185,129,0.2)', color: 'var(--status-approved)' }}>{assignSuccess}</div>}
          
          <form onSubmit={handleAssign} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="form-group">
              <label>Target Batch</label>
              <select className="form-input" value={selectedBatchId} onChange={e => setSelectedBatchId(e.target.value)} required>
                {batches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>Prompt</label>
              <select className="form-input" value={selectedPromptId} onChange={e => setSelectedPromptId(e.target.value)} required>
                {prompts.map(p => <option key={p.id} value={p.id}>{p.prompt_text.substring(0, 50)}...</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>Assign to Contributor</label>
              <select className="form-input" value={assignContributorId} onChange={e => setAssignContributorId(e.target.value)} required>
                <option value="">Select a contributor...</option>
                {contributors.map(u => <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>Assign to Reviewer</label>
              <select className="form-input" value={assignReviewerId} onChange={e => setAssignReviewerId(e.target.value)} required>
                <option value="">Select a reviewer...</option>
                {reviewers.map(u => <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>)}
              </select>
            </div>

            <button type="submit" className="btn btn-primary mt-2" disabled={assigning}>
              {assigning ? <span className="spinner"/> : 'Assign Prompt'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
