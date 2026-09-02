import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, test, vi } from 'vitest'

import { JobsPage } from './JobsPage'

const JOB = {
  id: 'j1',
  company_name: 'Acme',
  canonical_title: 'Backend Engineer',
  location_normalized: 'tokyo',
  status: 'new',
  bookmarked: false,
  match_score: 78,
  source_type: 'ats',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  structured: {
    description: 'Build APIs.',
    source_type: 'ats',
    ats_vendor: 'greenhouse',
    needs_review: ['salary'],
    match: {
      score: 78,
      rationale: 'Backend role in Tokyo — strong fit.',
      concerns: ['comp unknown'],
    },
  },
}

const mutate = vi.fn()
vi.mock('../features/jobs/hooks', () => ({
  useJobPostings: () => ({ data: [JOB], isLoading: false }),
  useAddJobPosting: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateJobPosting: () => ({ mutate }),
}))

test('shows the match score and, on expand, the rationale and concerns', () => {
  render(
    <MemoryRouter>
      <JobsPage />
    </MemoryRouter>,
  )

  expect(screen.getByText('Backend Engineer')).toBeInTheDocument()
  expect(screen.getByText('check')).toBeInTheDocument() // needs_review badge

  fireEvent.click(screen.getByRole('button', { name: /Backend Engineer/ }))

  expect(screen.getByText(/strong fit/)).toBeInTheDocument()
  expect(screen.getByText('comp unknown')).toBeInTheDocument()
  expect(screen.getByText(/via greenhouse/)).toBeInTheDocument()
})
