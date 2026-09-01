import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { ApiError } from '../api/client'
import { FileDropzone } from '../components/FileDropzone'
import { Button, Field, Spinner, Textarea } from '../components/ui'
import { useCreateResumeFromText, useResumes, useUploadResume } from '../features/resumes/hooks'

const ACCEPT =
  '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const ACCEPTED_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

export function ResumesPage() {
  const navigate = useNavigate()
  const resumes = useResumes()
  const upload = useUploadResume()
  const fromText = useCreateResumeFromText()

  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onFile = async (file: File) => {
    setError(null)
    if (file.type && !ACCEPTED_TYPES.has(file.type)) {
      setError('Only PDF and DOCX files are accepted.')
      return
    }
    try {
      const resume = await upload.mutateAsync(file)
      navigate(`/resumes/${resume.id}`)
    } catch (e) {
      setError((e as ApiError).detail ?? (e as Error).message)
    }
  }

  const onText = async () => {
    setError(null)
    try {
      const resume = await fromText.mutateAsync(text)
      navigate(`/resumes/${resume.id}`)
    } catch (e) {
      setError((e as ApiError).detail)
    }
  }

  const busy = upload.isPending || fromText.isPending

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Résumés</h1>
        <p className="text-sm text-neutral-500">Upload a file or paste your experience as text.</p>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <section className="space-y-4 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
        <FileDropzone
          label="Upload a PDF or DOCX"
          accept={ACCEPT}
          disabled={busy}
          onFile={(file) => void onFile(file)}
        />

        <div className="text-center text-xs text-neutral-400">or</div>

        <Field label="Paste your résumé">
          <Textarea
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Companies, roles, dates, achievements…"
          />
        </Field>
        <Button onClick={() => void onText()} disabled={busy || text.trim().length < 40}>
          {busy ? <Spinner /> : 'Create from text'}
        </Button>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-neutral-500">Your résumés</h2>
        {resumes.isLoading && <Spinner />}
        {resumes.data?.length === 0 && <p className="text-sm text-neutral-500">Nothing yet.</p>}
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
          {resumes.data?.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-3">
              <Link to={`/resumes/${r.id}`} className="text-sky-600 hover:underline">
                {r.label}
              </Link>
              <span className="text-xs text-neutral-500">{r.latest_version?.status ?? '—'}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
