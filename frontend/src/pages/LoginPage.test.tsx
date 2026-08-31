import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { MemoryRouter } from 'react-router'

import { LoginPage } from './LoginPage'

// `fetch` is mocked in setupTests.ts; the default is a signed-out 401 so useMe
// resolves cleanly. Individual tests override it with mockImplementation.

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  return input instanceof URL ? input.href : input.url
}

test('renders the email step', async () => {
  renderPage()
  expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  expect(screen.getByLabelText('Email')).toBeInTheDocument()
})

test('rejects an invalid email before sending', async () => {
  renderPage()
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Email'), 'not-an-email')
  await user.click(screen.getByRole('button', { name: /send code/i }))
  expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
})

test('the code step starts empty, not carried over from the email input', async () => {
  vi.mocked(fetch).mockImplementation(async (input) =>
    urlOf(input).includes('/auth/otp/request')
      ? new Response(JSON.stringify({ status: 'accepted' }), { status: 202 })
      : new Response('{}', { status: 401 }),
  )
  renderPage()
  const user = userEvent.setup()

  await user.type(await screen.findByLabelText('Email'), 'me@example.com')
  await user.click(screen.getByRole('button', { name: /send code/i }))

  expect(await screen.findByLabelText('6-digit code')).toHaveValue('')
})
