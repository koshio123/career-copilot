import { useState } from 'react'
import { Link } from 'react-router'

import type { ApiError } from '../api/client'
import { Button, Field, Input, Spinner } from '../components/ui'
import {
  useAddJobSource,
  useJobSourceActions,
  useJobSources,
  type JobSource,
} from '../features/jobs/hooks'

const ROBOTS_LABEL: Record<JobSource['robots_state'], string> = {
  allowed: 'robots: ok',
  disallowed: 'robots: blocked',
  unknown: 'robots: unknown',
}

function statusLine(s: JobSource): string {
  if (s.last_error) return s.last_error
  if (s.last_success_at) return `Last fetched ${new Date(s.last_success_at).toLocaleString()}`
  if (s.last_fetched_at) return `Fetched ${new Date(s.last_fetched_at).toLocaleString()}`
  return 'Waiting for first fetch…'
}

export function JobSourcesPage() {
  const [pollUntil, setPollUntil] = useState(0)
  const bump = () => setPollUntil(Date.now() + 20_000)
  const sources = useJobSources(pollUntil)
  const add = useAddJobSource()
  const actions = useJobSourceActions(bump)
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onAdd = async () => {
    setError(null)
    try {
      await add.mutateAsync({ url })
      setUrl('')
      bump()
    } catch (e) {
      setError((e as ApiError).detail)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Career-page sources</h1>
        <p className="text-sm text-neutral-500">
          Register a company&apos;s careers or job-list URL. We re-check it on a schedule.{' '}
          <Link to="/jobs" className="text-sky-600 hover:underline">
            Back to jobs
          </Link>
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <section className="flex items-end gap-3">
        <Field label="Careers URL">
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://boards.greenhouse.io/acme"
          />
        </Field>
        <Button onClick={() => void onAdd()} disabled={add.isPending || url.trim() === ''}>
          {add.isPending ? <Spinner /> : 'Add source'}
        </Button>
      </section>

      <section className="space-y-3">
        {sources.isLoading && <Spinner />}
        {sources.data?.length === 0 && <p className="text-sm text-neutral-500">No sources yet.</p>}
        {sources.data?.map((s) => (
          <div
            key={s.id}
            className="space-y-2 rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-medium">{s.label ?? s.url}</p>
                <p className="truncate text-neutral-500">{s.url}</p>
              </div>
              <span className="shrink-0 rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
                {s.status}
              </span>
            </div>
            <p className="text-neutral-500">
              {statusLine(s)} · {ROBOTS_LABEL[s.robots_state]}
              {s.source_type ? ` · ${s.source_type}` : ''}
            </p>
            <div className="flex flex-wrap gap-2">
              {s.status === 'active' ? (
                <>
                  <Button variant="ghost" onClick={() => actions.fetchNow.mutate(s.id)}>
                    Fetch now
                  </Button>
                  <Button variant="ghost" onClick={() => actions.pause.mutate(s.id)}>
                    Pause
                  </Button>
                </>
              ) : (
                <Button variant="ghost" onClick={() => actions.resume.mutate(s.id)}>
                  Resume
                </Button>
              )}
              <Button variant="ghost" onClick={() => actions.remove.mutate(s.id)}>
                Delete
              </Button>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
