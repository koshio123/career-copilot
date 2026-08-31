import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../api/client'
import type { components } from '../api/schema'

export type User = components['schemas']['UserOut']

const ME_KEY = ['me'] as const

/** The current user, or null when signed out. */
export function useMe() {
  return useQuery<User | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me')
      if (result.response.status === 401) return null
      return unwrap(result)
    },
  })
}

export function useRequestOtp() {
  return useMutation({
    mutationFn: (email: string) =>
      api.POST('/api/v1/auth/otp/request', { body: { email } }).then(unwrap),
  })
}

export function useVerifyOtp() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { email: string; code: string }) =>
      api.POST('/api/v1/auth/otp/verify', { body: vars }).then(unwrap),
    onSuccess: (user) => queryClient.setQueryData(ME_KEY, user),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.POST('/api/v1/auth/logout').then(() => undefined),
    onSettled: () => {
      queryClient.setQueryData(ME_KEY, null)
      void queryClient.invalidateQueries()
    },
  })
}
