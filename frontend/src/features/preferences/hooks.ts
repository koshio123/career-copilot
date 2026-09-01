import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { components } from '../../api/schema'

export type Preferences = components['schemas']['PreferenceIn']

const KEY = ['preferences']

export function usePreferences() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => api.GET('/api/v1/preferences').then(unwrap),
  })
}

export function useSavePreferences() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Preferences) => api.PUT('/api/v1/preferences', { body }).then(unwrap),
    onSuccess: (data) => queryClient.setQueryData(KEY, data),
  })
}
