import { Outlet } from 'react-router'

import { Button } from '../components/ui'
import { useLogout, useMe } from '../auth/hooks'

export function AppLayout() {
  const { data: user } = useMe()
  const logout = useLogout()

  return (
    <div className="min-h-dvh">
      <header className="flex items-center justify-between border-b border-neutral-200 px-6 py-3 dark:border-neutral-800">
        <span className="font-semibold">Career Copilot</span>
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
