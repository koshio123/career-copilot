import { Navigate, Route, Routes } from 'react-router'

import { DashboardPage } from './pages/DashboardPage'
import { JobsPage } from './pages/JobsPage'
import { JobSourcesPage } from './pages/JobSourcesPage'
import { LoginPage } from './pages/LoginPage'
import { PreferencesPage } from './pages/PreferencesPage'
import { ResumeDetailPage } from './pages/ResumeDetailPage'
import { ResumesPage } from './pages/ResumesPage'
import { AppLayout } from './routes/AppLayout'
import { ProtectedRoute } from './routes/ProtectedRoute'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/resumes" element={<ResumesPage />} />
          <Route path="/resumes/:resumeId" element={<ResumeDetailPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/sources" element={<JobSourcesPage />} />
          <Route path="/preferences" element={<PreferencesPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
