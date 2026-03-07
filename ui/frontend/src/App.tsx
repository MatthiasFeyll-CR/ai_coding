import { Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ErrorModal } from './components/modals/ErrorModal';
import { LinkProjectModal } from './components/modals/LinkProjectModal';
import { ModelSelectorModal } from './components/modals/ModelSelectorModal';
import { ReinstantiateModal } from './components/modals/ReinstantiateModal';
import { DashboardPage } from './pages/DashboardPage';
import { EditorPage } from './pages/EditorPage';
import { RequirementsPage } from './pages/RequirementsPage';
import { SettingsPage } from './pages/SettingsPage';

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="dashboard/:projectId" element={<DashboardPage />} />
          <Route path="editor" element={<EditorPage />} />
          <Route path="editor/:projectId" element={<EditorPage />} />
          <Route path="requirements" element={<RequirementsPage />} />
          <Route path="requirements/:projectId" element={<RequirementsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>

      {/* Global modals */}
      <LinkProjectModal />
      <ModelSelectorModal />
      <ReinstantiateModal />
      <ErrorModal />
    </>
  );
}
