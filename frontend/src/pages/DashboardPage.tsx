import { useMe } from '../auth/hooks'

export function DashboardPage() {
  const { data: user } = useMe()

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Welcome back</h1>
      <p className="text-neutral-600 dark:text-neutral-400">
        Signed in as <span className="font-medium">{user?.email}</span>
        {user?.email_verified ? ' (verified)' : ''}.
      </p>
      <div className="rounded-lg border border-neutral-200 p-6 text-sm text-neutral-500 dark:border-neutral-800">
        Résumé import, job sources, and gap analysis land in the next phases.
      </div>
    </div>
  )
}
