import { expect, test } from '@playwright/test'

import { signIn } from './helpers'

const SOURCE_ID = '33333333-3333-3333-3333-333333333333'

function source(over: Record<string, unknown> = {}) {
  return {
    id: SOURCE_ID,
    url: 'https://boards.greenhouse.io/acme',
    label: null,
    status: 'active',
    source_type: null,
    ats_vendor: null,
    robots_state: 'unknown',
    fetch_interval_hours: 24,
    last_fetched_at: null,
    last_success_at: null,
    last_error: null,
    consecutive_failures: 0,
    created_at: '2026-01-01T00:00:00Z',
    ...over,
  }
}

test('register a career-page source', async ({ page }) => {
  await signIn(page)

  let sources: unknown[] = []
  await page.route('**/api/v1/job-sources', (route) => {
    if (route.request().method() === 'POST') {
      sources = [source()]
      return route.fulfill({ status: 201, json: source() })
    }
    return route.fulfill({ json: sources })
  })

  await page.goto('/jobs/sources')
  await page.getByLabel('Careers URL').fill('https://boards.greenhouse.io/acme')
  await page.getByRole('button', { name: 'Add source' }).click()

  await expect(page.getByText('https://boards.greenhouse.io/acme').first()).toBeVisible()
  await expect(page.getByText('robots: unknown')).toBeVisible()
})

test('add a job manually and bookmark it', async ({ page }) => {
  await signIn(page)

  let jobs: Record<string, unknown>[] = []
  await page.route('**/api/v1/jobs', (route) => {
    if (route.request().method() === 'POST') {
      const job = {
        id: '44444444-4444-4444-4444-444444444444',
        company_name: 'Acme',
        canonical_title: 'Staff Engineer',
        location_normalized: 'tokyo',
        status: 'new',
        bookmarked: false,
        match_score: null,
        structured: { description: 'Own the platform roadmap.', required_skills: ['Go'] },
        source_type: 'manual',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }
      jobs = [job]
      return route.fulfill({ status: 201, json: job })
    }
    return route.fulfill({ json: jobs })
  })
  await page.route('**/api/v1/jobs/*', (route) => {
    jobs = [{ ...jobs[0], bookmarked: true }]
    return route.fulfill({ json: jobs[0] })
  })

  await page.goto('/jobs')
  await page.getByRole('button', { name: 'Add a job manually' }).click()
  await page.getByLabel('Company').fill('Acme')
  await page.getByLabel('Title').fill('Staff Engineer')
  await page.getByRole('button', { name: 'Add job' }).click()

  await expect(page.getByText('Staff Engineer')).toBeVisible()

  // expand to see the description
  await page.getByRole('button', { name: /Staff Engineer/ }).click()
  await expect(page.getByText('Own the platform roadmap.')).toBeVisible()

  await page.getByRole('button', { name: 'Bookmark' }).click()
  await expect(page.getByRole('button', { name: 'Remove bookmark' })).toBeVisible()
})
