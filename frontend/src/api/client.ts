import createClient, { type Middleware } from 'openapi-fetch'

import type { paths } from './schema'

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

/** Double-submit CSRF: echo the cc_csrf cookie in a header on mutating requests. */
const csrf: Middleware = {
  onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) {
      const token = readCookie('cc_csrf')
      if (token) request.headers.set('x-csrf-token', token)
    }
    return request
  },
}

// Same-origin: no baseUrl. The schema paths are absolute (/api/v1/...); Vite
// proxies /api to the backend in dev, CloudFront does it in prod.
export const api = createClient<paths>({ credentials: 'include' })
api.use(csrf)

export interface ApiError {
  status: number
  code: string
  title: string
  detail: string
}

export function toApiError(response: Response, body: unknown): ApiError {
  const problem = (body ?? {}) as Record<string, unknown>
  return {
    status: response.status,
    code: typeof problem.code === 'string' ? problem.code : 'unknown',
    title: typeof problem.title === 'string' ? problem.title : 'Something went wrong',
    detail:
      typeof problem.detail === 'string' && problem.detail
        ? problem.detail
        : response.statusText || 'Request failed',
  }
}

/** Turn an openapi-fetch result into data, or throw a normalised ApiError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response, result.error)
  }
  return result.data as T
}
