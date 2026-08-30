import { useState, useEffect } from 'react';
import api from '../api';

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotifications();
  }, []);

  async function fetchNotifications() {
    setLoading(true);
    try {
      const res = await api.get('/api/notifications');
      setNotifications(res.data);
    } catch (err) {
      console.error('Failed to load notifications', err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Notifications</h1>
        <p>Review feedback and system updates</p>
      </div>

      {loading ? (
        <div className="loading-page" style={{ minHeight: 200 }}>
          <span className="spinner" />
        </div>
      ) : notifications.length === 0 ? (
        <div className="empty-state">
          <p>No notifications yet.</p>
        </div>
      ) : (
        <div className="entry-list">
          {notifications.map((n) => (
            <div key={n.id} className="card" style={{ marginBottom: 8 }}>
              <div className="flex items-center justify-between">
                <span className={`status-badge status-${n.action === 'lead_override' ? 'submitted' : n.action}`}>
                  {n.action.replace('_', ' ')}
                </span>
                <span className="text-muted" style={{ fontSize: '0.78rem' }}>
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </div>
              <p style={{ marginTop: 8, fontSize: '0.9rem' }}>{n.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
