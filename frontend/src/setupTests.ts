import '@testing-library/jest-dom/vitest'
import { beforeEach, vi } from 'vitest'

// The app calls the API with same-origin relative paths (`/api/v1/...`) and lets
// the browser resolve them against the current origin. jsdom's `Request` can't
// parse a relative URL, so resolve them against a fixed dev origin in tests.
const BaseRequest = globalThis.Request
class RelativeAwareRequest extends BaseRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(
      typeof input === 'string' && input.startsWith('/') ? `http://localhost:3000${input}` : input,
      init,
    )
  }
}
vi.stubGlobal('Request', RelativeAwareRequest)

// openapi-fetch binds `globalThis.fetch` when the API client module is first
// imported (which happens before any test runs), so the mock has to be installed
// here — not in a per-test `stubGlobal`, which the client would never see. Tests
// change its behaviour with `vi.mocked(fetch).mockImplementation(...)`.
const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  fetchMock.mockReset()
  // Default: every request is unauthenticated. A fresh Response per call so the
  // body can be read each time.
  fetchMock.mockImplementation(async () => new Response('{}', { status: 401 }))
})
