import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { components } from '../../api/schema'

export type JobSource = components['schemas']['JobSourceOut']
export type JobPosting = components['schemas']['JobPostingOut']
export type JobPostingManualIn = components['schemas']['JobPostingManualIn']
export type JobPostingUpdateIn = components['schemas']['JobPostingUpdateIn']

const SOURCES = ['job-sources']
const JOBS = ['jobs']

// --- sources ---------------------------------------------------------------

export function useJobSources(pollUntil = 0) {
  return useQuery({
    queryKey: SOURCES,
    queryFn: () => api.GET('/api/v1/job-sources').then(unwrap),
    // The worker fetches out of band, so poll for a bit after any action
    // (add / fetch-now / resume) and while a source has never been fetched.
    refetchInterval: (query) => {
      if (Date.now() < pollUntil) return 2000
      const waiting = query.state.data?.some(
        (s) => s.last_fetched_at === null && s.status === 'active',
      )
      return waiting ? 3000 : false
    },
  })
}

export function useAddJobSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { url: string; label?: string | null; fetch_interval_hours?: number }) =>
      api
        .POST('/api/v1/job-sources', {
          body: { fetch_interval_hours: 24, ...input },
        })
        .then(unwrap),
    onSuccess: () => qc.invalidateQueries({ queryKey: SOURCES }),
  })
}

function sourceAction(
  path:
    | '/api/v1/job-sources/{source_id}/pause'
    | '/api/v1/job-sources/{source_id}/resume'
    | '/api/v1/job-sources/{source_id}/fetch',
) {
  return (source_id: string) => api.POST(path, { params: { path: { source_id } } }).then(unwrap)
}

export function useJobSourceActions(onChange: () => void = () => {}) {
  const qc = useQueryClient()
  const done = () => {
    void qc.invalidateQueries({ queryKey: SOURCES })
    onChange()
  }
  return {
    pause: useMutation({
      mutationFn: sourceAction('/api/v1/job-sources/{source_id}/pause'),
      onSuccess: done,
    }),
    resume: useMutation({
      mutationFn: sourceAction('/api/v1/job-sources/{source_id}/resume'),
      onSuccess: done,
    }),
    fetchNow: useMutation({
      mutationFn: sourceAction('/api/v1/job-sources/{source_id}/fetch'),
      onSuccess: done,
    }),
    remove: useMutation({
      mutationFn: (source_id: string) =>
        api
          .DELETE('/api/v1/job-sources/{source_id}', { params: { path: { source_id } } })
          .then(unwrap),
      onSuccess: done,
    }),
  }
}

// --- postings -------------------------------------------------------------

export function useJobPostings() {
  return useQuery({
    queryKey: JOBS,
    queryFn: () => api.GET('/api/v1/jobs').then(unwrap),
  })
}

export function useAddJobPosting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: JobPostingManualIn) => api.POST('/api/v1/jobs', { body }).then(unwrap),
    onSuccess: () => qc.invalidateQueries({ queryKey: JOBS }),
  })
}

export function useUpdateJobPosting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; body: JobPostingUpdateIn }) =>
      api
        .PATCH('/api/v1/jobs/{job_id}', { params: { path: { job_id: vars.id } }, body: vars.body })
        .then(unwrap),
    onSuccess: () => qc.invalidateQueries({ queryKey: JOBS }),
  })
}
