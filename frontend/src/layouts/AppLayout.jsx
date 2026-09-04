import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { PanelLeftClose, PanelLeft, LogOut, FileText, Bell, CheckSquare, Layers, Activity, MessageSquare, Users, Tags, Download } from 'lucide-react';

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  // Nav links per role
  const navItems = getNavItems(user?.role);

  return (
    <div className={`app-layout ${isSidebarOpen ? '' : 'sidebar-closed'}`}>
      <aside className={`sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <div className="header-top">
            {isSidebarOpen && <h2>ARQULAT</h2>}
            <button className="sidebar-border-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)} title="Toggle sidebar">
              {isSidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
            </button>
          </div>
          {isSidebarOpen && (
            <div className="user-info">
              {user?.display_name || user?.username}
              <br />
              <span className="user-role">{user?.role}</span>
            </div>
          )}
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `sidebar-link${isActive ? ' active' : ''} ${isSidebarOpen ? '' : 'icon-only'}`
                }
                title={!isSidebarOpen ? item.label : undefined}
              >
                <Icon size={20} className="nav-icon" />
                {isSidebarOpen && <span className="nav-label">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <button className={`btn btn-outline btn-sm logout-btn ${isSidebarOpen ? '' : 'icon-only'}`} onClick={handleLogout} style={{ width: '100%', padding: isSidebarOpen ? '8px 16px' : '8px 0', justifyContent: isSidebarOpen ? 'flex-start' : 'center', border: 'none' }} title="Sign out">
            <LogOut size={20} /> {isSidebarOpen && <span>Sign out</span>}
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
  items.push({ to: '/entries', label: 'My Entries', icon: FileText });
  items.push({ to: '/notifications', label: 'Notifications', icon: Bell });

  // Reviewer+
  if (['reviewer', 'lead', 'admin'].includes(role)) {
    items.push({ to: '/review-queue', label: 'Review Queue', icon: CheckSquare });
    items.push({ to: '/batches', label: 'My Batches', icon: Layers });
    items.push({ to: '/workers', label: 'Worker Health', icon: Activity });
  }

  // Lead+
  if (['lead', 'admin'].includes(role)) {
    items.push({ to: '/prompts', label: 'Prompts', icon: MessageSquare });
  }

  // Admin
  if (role === 'admin') {
    items.push({ to: '/users', label: 'Users', icon: Users });
    items.push({ to: '/taxonomy', label: 'Taxonomy', icon: Tags });
    items.push({ to: '/export', label: 'Export Dataset', icon: Download });
  }

  return items;
}
