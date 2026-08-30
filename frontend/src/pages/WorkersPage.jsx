import { useState, useEffect } from 'react';
import api from '../api';

export default function WorkersPage() {
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWorkers();
    
    // Auto-refresh every 10 seconds since health changes frequently
    const interval = setInterval(fetchWorkers, 10000);
    return () => clearInterval(interval);
  }, []);

  async function fetchWorkers() {
    try {
      const res = await api.get('/api/workers/health');
      setWorkers(res.data);
    } catch (err) {
      console.error('Failed to load workers', err);
    } finally {
      setLoading(false);
    }
  }

  const onlineCount = workers.filter(w => w.status === 'online').length;

  return (
    <div>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Worker Health</h1>
          <p>Monitor render nodes in real-time</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '1.5rem', fontWeight: 600, color: onlineCount > 0 ? 'var(--status-approved)' : 'var(--status-rejected)' }}>
            {onlineCount} <span style={{ fontSize: '0.9rem', fontWeight: 400, color: 'var(--text-secondary)' }}>/ {workers.length} Online</span>
          </span>
        </div>
      </div>

      <div className="card">
        {loading && workers.length === 0 ? <span className="spinner"/> : (
          <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '8px 0' }}>Worker Name</th>
                <th>ID</th>
                <th>Last Heartbeat</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {workers.length === 0 ? (
                <tr><td colSpan="4" style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)' }}>No workers registered yet.</td></tr>
              ) : workers.map(w => (
                <tr key={w.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '12px 0', fontWeight: 500 }}>{w.name}</td>
                  <td className="text-muted" style={{ fontSize: '0.8rem' }}>{w.id}</td>
                  <td>{new Date(w.last_seen).toLocaleString()}</td>
                  <td>
                    <span style={{ 
                      display: 'inline-flex', 
                      alignItems: 'center',
                      gap: 6,
                      color: w.status === 'online' ? 'var(--status-approved)' : 'var(--status-rejected)'
                    }}>
                      <span style={{ 
                        width: 8, 
                        height: 8, 
                        borderRadius: '50%', 
                        background: w.status === 'online' ? 'var(--status-approved)' : 'var(--status-rejected)' 
                      }} />
                      {w.status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
