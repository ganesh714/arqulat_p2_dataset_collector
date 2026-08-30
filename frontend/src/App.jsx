import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import AppLayout from './layouts/AppLayout';
import EntryListPage from './pages/EntryListPage';
import EntryEditorPage from './pages/EntryEditorPage';
import NotificationsPage from './pages/NotificationsPage';
import ReviewQueuePage from './pages/ReviewQueuePage';
import BatchesPage from './pages/BatchesPage';
import WorkersPage from './pages/WorkersPage';
import AdminDashboard from './pages/AdminDashboard';
import PromptsPage from './pages/PromptsPage';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-page">
        <span className="spinner" /> Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        {/* Default redirect */}
        <Route index element={<Navigate to="/entries" replace />} />

        {/* Contributor views */}
        <Route path="entries" element={<EntryListPage />} />
        <Route path="entries/:id" element={<EntryEditorPage />} />
        <Route path="notifications" element={<NotificationsPage />} />

        {/* Real routes for later phases */}
        <Route path="review-queue" element={<ReviewQueuePage />} />
        <Route path="batches" element={<BatchesPage />} />
        <Route path="prompts" element={<PromptsPage />} />
        <Route path="workers" element={<WorkersPage />} />
        
        {/* Admin Dashboard handles Users, Taxonomy, Export */}
        <Route path="users" element={<AdminDashboard />} />
        <Route path="taxonomy" element={<AdminDashboard />} />
        <Route path="export" element={<AdminDashboard />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}



export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
