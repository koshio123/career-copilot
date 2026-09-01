import { NavLink, Outlet } from 'react-router'

import { Button } from '../components/ui'
import { useLogout, useMe } from '../auth/hooks'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm ${isActive ? 'font-semibold text-neutral-900 dark:text-neutral-100' : 'text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'}`

export function AppLayout() {
  const { data: user } = useMe()
  const logout = useLogout()

  return (
    <div className="min-h-dvh">
      <header className="flex items-center justify-between border-b border-neutral-200 px-6 py-3 dark:border-neutral-800">
        <div className="flex items-center gap-6">
          <span className="font-semibold">Career Copilot</span>
          <nav className="flex items-center gap-4">
            <NavLink to="/" end className={linkClass}>
              Home
            </NavLink>
            <NavLink to="/resumes" className={linkClass}>
              Résumés
            </NavLink>
            <NavLink to="/preferences" className={linkClass}>
              Preferences
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-neutral-500">{user?.email}</span>
          <Button variant="ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Outlet />
      </main>
    </div>
  )
}
