import { Navigate, Outlet, useLocation } from 'react-router'

import { FullPageSpinner } from '../components/ui'
import { useMe } from '../auth/hooks'

export function ProtectedRoute() {
  const { data: user, isLoading } = useMe()
  const location = useLocation()

  if (isLoading) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
