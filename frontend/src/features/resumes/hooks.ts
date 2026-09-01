import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { components } from '../../api/schema'

export type Resume = components['schemas']['ResumeOut']
export type ResumeDetail = components['schemas']['ResumeDetailOut']
export type ResumeVersion = components['schemas']['ResumeVersionOut']
export type ResumeStructured = components['schemas']['ResumeStructured']

const KEY = 'resumes'

export function useResumes() {
  return useQuery({
    queryKey: [KEY],
    queryFn: () => api.GET('/api/v1/resumes').then(unwrap),
  })
}

export function useResume(resumeId: string | undefined) {
  return useQuery({
    queryKey: [KEY, resumeId],
    enabled: !!resumeId,
    queryFn: () =>
      api
        .GET('/api/v1/resumes/{resume_id}', { params: { path: { resume_id: resumeId! } } })
        .then(unwrap),
    // poll while the latest version is still being processed
    refetchInterval: (query) => {
      const status = query.state.data?.latest_version?.status
      return status && status !== 'ready' && status !== 'failed' ? 2000 : false
    },
  })
}

async function putFile(url: string, file: File): Promise<void> {
  const res = await fetch(url, {
    method: 'PUT',
    body: file,
    headers: { 'content-type': file.type },
  })
  if (!res.ok) throw new Error(`Upload failed (${res.status})`)
}

export function useUploadResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const { key, url } = unwrap(
        await api.POST('/api/v1/resumes/uploads', {
          body: { filename: file.name, content_type: file.type },
        }),
      )
      await putFile(url, file)
      return unwrap(
        await api.POST('/api/v1/resumes', { body: { source_key: key, label: file.name } }),
      )
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [KEY] }),
  })
}

export function useCreateResumeFromText() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (raw_text: string) =>
      api.POST('/api/v1/resumes', { body: { raw_text, label: 'My résumé' } }).then(unwrap),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [KEY] }),
  })
}

export function useUpdateVersion(resumeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { versionId: string; structured: ResumeStructured }) =>
      api
        .PATCH('/api/v1/resumes/{resume_id}/versions/{version_id}', {
          params: { path: { resume_id: resumeId, version_id: vars.versionId } },
          body: { structured: vars.structured },
        })
        .then(unwrap),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [KEY, resumeId] }),
  })
}
