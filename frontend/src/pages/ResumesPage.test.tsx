import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { MemoryRouter } from 'react-router'

import { ResumesPage } from './ResumesPage'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }),
    ),
  )
})
afterEach(() => vi.unstubAllGlobals())

test('offers both an upload and a paste-text path', async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ResumesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )

  expect(await screen.findByLabelText(/upload a pdf or docx/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/paste your résumé/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /create from text/i })).toBeDisabled()
})
