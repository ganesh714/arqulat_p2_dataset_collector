import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  // Nav links per role
  const navItems = getNavItems(user?.role);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>ARQULAT</h2>
          <div className="user-info">
            {user?.display_name || user?.username}
            <br />
            <span className="user-role">{user?.role}</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sidebar-link${isActive ? ' active' : ''}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="btn btn-outline btn-sm" onClick={handleLogout} style={{ width: '100%' }}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

function getNavItems(role) {
  const items = [];

  // Contributor
  items.push({ to: '/entries', label: 'My Entries' });
  items.push({ to: '/notifications', label: 'Notifications' });

  // Reviewer+
  if (['reviewer', 'lead', 'admin'].includes(role)) {
    items.push({ to: '/review-queue', label: 'Review Queue' });
    items.push({ to: '/batches', label: 'My Batches' });
    items.push({ to: '/workers', label: 'Worker Health' });
  }

  // Lead+
  if (['lead', 'admin'].includes(role)) {
    items.push({ to: '/prompts', label: 'Prompts' });
  }

  // Admin
  if (role === 'admin') {
    items.push({ to: '/users', label: 'Users' });
    items.push({ to: '/taxonomy', label: 'Taxonomy' });
    items.push({ to: '/export', label: 'Export Dataset' });
  }

  return items;
}
