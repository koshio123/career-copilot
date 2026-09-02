import { useState } from 'react'
import { Link } from 'react-router'
import { useForm } from 'react-hook-form'

import type { ApiError } from '../api/client'
import { Button, Field, Input, Spinner, Textarea } from '../components/ui'
import {
  useAddJobPosting,
  useJobPostings,
  useUpdateJobPosting,
  type JobPosting,
  type JobPostingManualIn,
} from '../features/jobs/hooks'

interface ManualForm {
  company_name: string
  title: string
  location: string
  description: string
}

interface Structured {
  employment_type?: string | null
  remote?: boolean | null
  salary_min?: number | null
  salary_max?: number | null
  required_skills?: string[]
  preferred_skills?: string[]
  description?: string
  apply_url?: string | null
}

function score(value: number | null): string {
  return value === null ? '—' : `${Math.round(value)}`
}

const yen = (n: number) => `¥${n.toLocaleString()}`

function salaryLine(s: Structured): string | null {
  if (s.salary_min != null && s.salary_max != null)
    return `${yen(s.salary_min)}–${yen(s.salary_max)}`
  if (s.salary_min != null) return `from ${yen(s.salary_min)}`
  if (s.salary_max != null) return `up to ${yen(s.salary_max)}`
  return null
}

function JobRow({ job, onBookmark }: { job: JobPosting; onBookmark: () => void }) {
  const [open, setOpen] = useState(false)
  const s = (job.structured ?? {}) as Structured
  const salary = salaryLine(s)

  return (
    <li className="py-1">
      <div className="group flex items-center justify-between gap-4 rounded-md transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-2 rounded-md py-2 pl-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
        >
          <span
            aria-hidden
            className={`shrink-0 text-neutral-400 transition-transform group-hover:text-neutral-600 dark:group-hover:text-neutral-300 ${open ? 'rotate-90' : ''}`}
          >
            ▸
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium">{job.canonical_title}</span>
            <span className="block truncate text-sm text-neutral-500">
              {job.company_name}
              {job.location_normalized ? ` · ${job.location_normalized}` : ''}
              {s.remote ? ' · remote' : ''}
            </span>
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-3 pr-2 text-sm">
          <span className="tabular-nums text-neutral-500" title="Match score">
            {score(job.match_score)}
          </span>
          <button
            type="button"
            aria-label={job.bookmarked ? 'Remove bookmark' : 'Bookmark'}
            onClick={onBookmark}
            className="text-lg leading-none"
          >
            {job.bookmarked ? '★' : '☆'}
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-3 space-y-3 rounded-md bg-neutral-50 p-4 text-sm dark:bg-neutral-900">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-neutral-600 dark:text-neutral-400">
            {s.employment_type && (
              <>
                <dt className="font-medium">Type</dt>
                <dd>{s.employment_type}</dd>
              </>
            )}
            {salary && (
              <>
                <dt className="font-medium">Salary</dt>
                <dd>{salary}</dd>
              </>
            )}
            {s.required_skills && s.required_skills.length > 0 && (
              <>
                <dt className="font-medium">Must have</dt>
                <dd>{s.required_skills.join(', ')}</dd>
              </>
            )}
            {s.preferred_skills && s.preferred_skills.length > 0 && (
              <>
                <dt className="font-medium">Nice to have</dt>
                <dd>{s.preferred_skills.join(', ')}</dd>
              </>
            )}
          </dl>
          {s.description ? (
            <p className="whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
              {s.description}
            </p>
          ) : (
            <p className="text-neutral-500">No description.</p>
          )}
          {s.apply_url && (
            <a
              href={s.apply_url}
              target="_blank"
              rel="noreferrer"
              className="inline-block text-sky-600 hover:underline"
            >
              Open posting ↗
            </a>
          )}
        </div>
      )}
    </li>
  )
}

export function JobsPage() {
  const jobs = useJobPostings()
  const add = useAddJobPosting()
  const update = useUpdateJobPosting()
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, reset } = useForm<ManualForm>()

  const onSubmit = async (values: ManualForm) => {
    setError(null)
    const body: JobPostingManualIn = {
      company_name: values.company_name,
      title: values.title,
      location: values.location || null,
      description: values.description,
      required_skills: [],
      preferred_skills: [],
    }
    try {
      await add.mutateAsync(body)
      reset()
      setShowForm(false)
    } catch (e) {
      setError((e as ApiError).detail)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Jobs</h1>
          <p className="text-sm text-neutral-500">
            Ranked by match score.{' '}
            <Link to="/jobs/sources" className="text-sky-600 hover:underline">
              Manage career-page sources
            </Link>
          </p>
        </div>
        <Button variant="ghost" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'Add a job manually'}
        </Button>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-3 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800"
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Company">
              <Input {...register('company_name', { required: true })} />
            </Field>
            <Field label="Title">
              <Input {...register('title', { required: true })} />
            </Field>
          </div>
          <Field label="Location">
            <Input {...register('location')} placeholder="Tokyo / Remote" />
          </Field>
          <Field label="Description">
            <Textarea
              rows={5}
              {...register('description')}
              placeholder="Paste the job description…"
            />
          </Field>
          <Button type="submit" disabled={add.isPending}>
            {add.isPending ? <Spinner /> : 'Add job'}
          </Button>
        </form>
      )}

      <section className="space-y-2">
        {jobs.isLoading && <Spinner />}
        {jobs.data?.length === 0 && (
          <p className="text-sm text-neutral-500">
            No jobs yet. Use <span className="font-medium">Add a job manually</span> above —
            automatic extraction from registered career pages is coming next.
          </p>
        )}
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
          {jobs.data?.map((job) => (
            <JobRow
              key={job.id}
              job={job}
              onBookmark={() =>
                update.mutate({ id: job.id, body: { bookmarked: !job.bookmarked } })
              }
            />
          ))}
        </ul>
      </section>
    </div>
  )
}
