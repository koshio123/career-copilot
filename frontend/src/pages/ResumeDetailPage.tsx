import { useState } from 'react'
import { useParams } from 'react-router'

import { Button, Field, Input, Spinner, Textarea } from '../components/ui'
import {
  useResume,
  useUpdateVersion,
  type ResumeStructured,
  type ResumeVersion,
} from '../features/resumes/hooks'

type Company = NonNullable<ResumeStructured['companies']>[number]
type Structured = { summary: string; skills: string[]; companies: Company[] }

// Coerce whatever the source produced ("2021-4", "2021-04-01", …) into the
// YYYY-MM string an <input type="month"> accepts; anything unparseable → "".
function toMonth(v: string | null | undefined): string {
  const m = /^(\d{4})-(\d{1,2})/.exec((v ?? '').trim())
  return m ? `${m[1]}-${m[2].padStart(2, '0')}` : ''
}

function thisMonth(): string {
  return new Date().toISOString().slice(0, 7)
}

function normalize(raw: ResumeVersion['structured']): Structured {
  const s = raw as ResumeStructured
  return {
    summary: s.summary ?? '',
    skills: s.skills ?? [],
    companies: (s.companies ?? []).map((c) => ({
      ...c,
      period_start: toMonth(c.period_start),
      period_end: toMonth(c.period_end),
      achievements: c.achievements ?? [],
    })),
  }
}

// Blank period fields become null so the API stores "unknown", not an empty string.
function toPayload(d: Structured): Structured {
  return {
    ...d,
    companies: d.companies.map((c) => ({
      ...c,
      period_start: c.period_start || null,
      period_end: c.period_end || null,
    })),
  }
}

export function ResumeDetailPage() {
  const { resumeId } = useParams<{ resumeId: string }>()
  const query = useResume(resumeId)
  const version = query.data?.latest_version ?? undefined

  if (query.isLoading) return <Spinner />
  if (!version) return <p className="text-sm text-neutral-500">Not found.</p>

  if (version.status === 'failed') {
    return (
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">Couldn’t process this résumé</h1>
        <p className="text-sm text-red-600 dark:text-red-400">{version.error}</p>
      </div>
    )
  }

  if (version.status !== 'ready') {
    return (
      <div className="flex items-center gap-3 text-sm text-neutral-500">
        <Spinner /> Reading and structuring your résumé…
      </div>
    )
  }

  return <Editor key={version.id + version.updated_at} resumeId={resumeId!} version={version} />
}

function Editor({ resumeId, version }: { resumeId: string; version: ResumeVersion }) {
  const save = useUpdateVersion(resumeId)
  const [data, setData] = useState<Structured>(() => normalize(version.structured))

  const patch = (next: Partial<Structured>) => setData((d) => ({ ...d, ...next }))
  const patchCompany = (index: number, next: Partial<Company>) =>
    patch({ companies: data.companies.map((c, i) => (i === index ? { ...c, ...next } : c)) })

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ versionId: version.id, structured: toPayload(data) })
      }}
    >
      <h1 className="text-2xl font-semibold">Review your résumé</h1>

      <Field label="Summary">
        <Textarea
          rows={3}
          value={data.summary}
          onChange={(e) => patch({ summary: e.target.value })}
        />
      </Field>

      <Field label="Skills (comma separated)">
        <Input
          value={data.skills.join(', ')}
          onChange={(e) =>
            patch({
              skills: e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </Field>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-neutral-500">Experience</h2>
        {data.companies.map((company, ci) => (
          <div
            key={ci}
            className="space-y-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Company">
                <Input
                  value={company.name}
                  onChange={(e) => patchCompany(ci, { name: e.target.value })}
                />
              </Field>
              <Field label="Role">
                <Input
                  value={company.role}
                  onChange={(e) => patchCompany(ci, { role: e.target.value })}
                />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Start">
                <Input
                  type="month"
                  value={company.period_start ?? ''}
                  onChange={(e) => patchCompany(ci, { period_start: e.target.value })}
                />
              </Field>
              <div>
                <Field label="End">
                  <Input
                    type="month"
                    className="disabled:opacity-50"
                    value={company.period_end ?? ''}
                    disabled={!company.period_end}
                    onChange={(e) => patchCompany(ci, { period_end: e.target.value })}
                  />
                </Field>
                <label className="mt-1 flex items-center gap-2 text-xs text-neutral-500">
                  <input
                    type="checkbox"
                    checked={!company.period_end}
                    onChange={(e) =>
                      patchCompany(ci, { period_end: e.target.checked ? '' : thisMonth() })
                    }
                  />
                  I currently work here
                </label>
              </div>
            </div>
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
              Achievements
            </p>
            <ul className="space-y-2">
              {(company.achievements ?? []).map((ach, ai) => (
                <li key={ai}>
                  <Input
                    value={ach.text}
                    onChange={(e) =>
                      patchCompany(ci, {
                        achievements: (company.achievements ?? []).map((a, j) =>
                          j === ai ? { ...a, text: e.target.value } : a,
                        ),
                      })
                    }
                  />
                  {!ach.has_metric && ach.suggestion && (
                    <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                      💡 {ach.suggestion}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? <Spinner /> : 'Save'}
        </Button>
        {save.isSuccess && <span className="text-sm text-green-600">Saved</span>}
      </div>
    </form>
  )
}
