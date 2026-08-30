import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../context/AuthContext';

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('users'); // users, taxonomy, export
  
  return (
    <div>
      <div className="page-header">
        <h1>Admin Dashboard</h1>
        <p>System configuration and dataset export</p>
      </div>

      <div className="flex gap-2 mb-4">
        <button className={`btn btn-sm ${activeTab === 'users' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('users')}>Users</button>
        <button className={`btn btn-sm ${activeTab === 'taxonomy' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('taxonomy')}>Taxonomy</button>
        <button className={`btn btn-sm ${activeTab === 'export' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('export')}>Export</button>
      </div>

      {activeTab === 'users' && <UsersTab />}
      {activeTab === 'taxonomy' && <TaxonomyTab />}
      {activeTab === 'export' && <ExportTab />}
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Create user
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  async function fetchUsers() {
    try {
      const res = await api.get('/api/users');
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post('/api/users', { email, password, display_name: displayName });
      setEmail('');
      setPassword('');
      setDisplayName('');
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setCreating(false);
    }
  }

  async function handleRoleChange(userId, newRole) {
    try {
      await api.patch(`/api/users/${userId}/role`, { role: newRole });
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update role');
    }
  }

  return (
    <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
      <div className="card" style={{ flex: 2 }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>All Users</h2>
        {loading ? <span className="spinner"/> : (
          <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '8px 0' }}>Display Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '12px 0' }}>{u.display_name}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className="status-badge status-draft">{u.role}</span>
                  </td>
                  <td>
                    {u.role !== 'admin' && (
                      <select 
                        className="form-input" 
                        style={{ padding: '4px 8px', width: 'auto' }}
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      >
                        <option value="contributor">Contributor</option>
                        <option value="reviewer">Reviewer</option>
                        <option value="lead">Lead</option>
                      </select>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ flex: 1 }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Create User</h2>
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="form-group">
            <label>Email</label>
            <input type="email" required className="form-input" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="text" required className="form-input" value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Display Name</label>
            <input type="text" required className="form-input" value={displayName} onChange={e => setDisplayName(e.target.value)} />
          </div>
          <p className="text-muted mt-1" style={{ fontSize: '0.8rem' }}>New users are always created as Contributors.</p>
          <button type="submit" className="btn btn-primary mt-2" disabled={creating}>
            {creating ? <span className="spinner"/> : 'Create User'}
          </button>
        </form>
      </div>
    </div>
  );
}

function TaxonomyTab() {
  const [phases, setPhases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPhases();
  }, []);

  async function fetchPhases() {
    try {
      const res = await api.get('/api/taxonomy/phases');
      setPhases(res.data);
    } catch(err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function createPhase() {
    const name = prompt('Phase name:');
    if (name) {
      await api.post('/api/taxonomy/phases', { name });
      fetchPhases();
    }
  }

  async function createSubphase(phaseId) {
    const name = prompt('Subphase name:');
    if (name) {
      await api.post(`/api/taxonomy/phases/${phaseId}/subphases`, { name });
      fetchPhases();
    }
  }

  async function createCategory(subphaseId) {
    const name = prompt('Category name:');
    if (name) {
      await api.post(`/api/taxonomy/subphases/${subphaseId}/categories`, { name });
      fetchPhases();
    }
  }

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2 style={{ fontSize: '1.1rem' }}>Taxonomy Structure</h2>
        <button className="btn btn-sm btn-primary" onClick={createPhase}>+ Add Phase</button>
      </div>

      {loading ? <span className="spinner"/> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {phases.map(p => (
            <div key={p.id} style={{ padding: 16, background: 'var(--bg-primary)', borderRadius: 'var(--radius)' }}>
              <div className="flex justify-between items-center mb-2">
                <h3 style={{ fontSize: '1rem', color: 'var(--accent)' }}>{p.name}</h3>
                <button className="btn btn-sm btn-outline" onClick={() => createSubphase(p.id)}>+ Add Subphase</button>
              </div>
              
              <div style={{ paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {p.subphases?.map(s => (
                  <div key={s.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                    <div className="flex justify-between items-center mb-2">
                      <h4 style={{ fontSize: '0.9rem' }}>{s.name}</h4>
                      <button className="btn btn-sm btn-outline" onClick={() => createCategory(s.id)}>+ Add Category</button>
                    </div>
                    
                    {s.categories?.length > 0 && (
                      <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                        {s.categories.map(c => (
                          <span key={c.id} style={{ fontSize: '0.75rem', padding: '2px 8px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12 }}>
                            {c.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ExportTab() {
  const { user } = useAuth();
  
  async function handleExport() {
    try {
      // Must fetch as blob to trigger download for streaming JSONL response
      const res = await api.get('/api/export/dataset', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `dataset_export_${new Date().getTime()}.jsonl`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
    } catch (err) {
      alert('Export failed');
    }
  }

  return (
    <div className="card">
      <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Dataset Export</h2>
      <p style={{ marginBottom: 24, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
        Export all approved entries as a JSONL file suitable for training. The format matches {"{ prompt, script, category }"}.
      </p>
      
      <button className="btn btn-primary" onClick={handleExport}>
        Download Dataset (JSONL)
      </button>
    </div>
  );
}
