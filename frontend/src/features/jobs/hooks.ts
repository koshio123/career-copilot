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

export function useJobSources() {
  return useQuery({
    queryKey: SOURCES,
    queryFn: () => api.GET('/api/v1/job-sources').then(unwrap),
    // a freshly added source is fetched by the worker within a few seconds
    refetchInterval: (query) =>
      query.state.data?.some((s) => s.last_fetched_at === null && s.status === 'active')
        ? 3000
        : false,
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

export function useJobSourceActions() {
  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: SOURCES })
  return {
    pause: useMutation({
      mutationFn: sourceAction('/api/v1/job-sources/{source_id}/pause'),
      onSuccess: invalidate,
    }),
    resume: useMutation({
      mutationFn: sourceAction('/api/v1/job-sources/{source_id}/resume'),
      onSuccess: invalidate,
    }),
    fetchNow: useMutation({
      mutationFn: sourceAction('/api/v1/job-sources/{source_id}/fetch'),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (source_id: string) =>
        api
          .DELETE('/api/v1/job-sources/{source_id}', { params: { path: { source_id } } })
          .then(unwrap),
      onSuccess: invalidate,
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
