import { expect, test } from '@playwright/test'

import { signIn } from './helpers'

const RESUME_ID = '11111111-1111-1111-1111-111111111111'
const VERSION_ID = '22222222-2222-2222-2222-222222222222'

function version(status: string, structured: Record<string, unknown> = {}) {
  return {
    id: VERSION_ID,
    version_no: 1,
    source: 'upload',
    status,
    error: null,
    structured,
    has_raw_text: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: `2026-01-01T00:00:0${status.length}Z`,
  }
}

const READY_STRUCTURED = {
  summary: 'Backend engineer, six years.',
  skills: ['python', 'postgres'],
  companies: [
    {
      name: 'Acme',
      role: 'Senior Engineer',
      period_start: '2019-01',
      period_end: null,
      achievements: [
        { text: 'Improved throughput', has_metric: false, suggestion: 'By how much? add a %' },
      ],
    },
  ],
}

test('upload a résumé, wait for structuring, edit and save', async ({ page }) => {
  await signIn(page)

  let processed = false
  await page.route('**/api/v1/resumes', (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill({
        status: 201,
        json: {
          id: RESUME_ID,
          label: 'cv.pdf',
          is_primary: true,
          created_at: 'x',
          latest_version: version('pending'),
        },
      })
    }
    return route.fulfill({ json: [] })
  })
  await page.route('**/api/v1/resumes/uploads', (route) =>
    route.fulfill({
      json: {
        key: `resumes/u/${VERSION_ID}.pdf`,
        url: 'https://s3.test/upload',
        max_bytes: 10485760,
      },
    }),
  )
  await page.route('https://s3.test/upload', (route) => route.fulfill({ status: 200, body: '' }))
  await page.route(`**/api/v1/resumes/${RESUME_ID}`, (route) => {
    const body = processed ? version('ready', READY_STRUCTURED) : version('structuring')
    processed = true // second poll returns ready
    return route.fulfill({
      json: {
        id: RESUME_ID,
        label: 'cv.pdf',
        is_primary: true,
        created_at: 'x',
        latest_version: body,
      },
    })
  })
  let saved: Record<string, unknown> = {}
  await page.route(`**/api/v1/resumes/${RESUME_ID}/versions/${VERSION_ID}`, (route) => {
    saved = JSON.parse(route.request().postData() ?? '{}').structured
    return route.fulfill({ json: { ...version('ready'), structured: saved } })
  })

  await page.goto('/resumes')
  await page
    .getByLabel('Upload a PDF or DOCX')
    .setInputFiles({ name: 'cv.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') })

  await expect(page).toHaveURL(`http://localhost:3000/resumes/${RESUME_ID}`)
  await expect(page.getByText('Reading and structuring')).toBeVisible()

  // poll flips to ready
  await expect(page.getByRole('heading', { name: 'Review your résumé' })).toBeVisible()
  await expect(page.getByText('add a %')).toBeVisible() // quantification hint

  // existing start date shows; the résumé has no end date, so "currently here" is on
  await expect(page.getByLabel('Start')).toHaveValue('2019-01')
  await expect(page.getByLabel('I currently work here')).toBeChecked()
  await page.getByLabel('I currently work here').uncheck()
  await page.getByLabel('End', { exact: true }).fill('2023-06')

  const summary = page.getByLabel('Summary')
  await summary.fill('Backend engineer, six years. Edited.')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Saved')).toBeVisible()

  const company = (saved.companies as Array<Record<string, unknown>>)[0]
  expect(company.period_start).toBe('2019-01')
  expect(company.period_end).toBe('2023-06')
})

test('set job preferences', async ({ page }) => {
  await signIn(page)

  let stored = {
    desired_roles: [] as string[],
    locations: [] as string[],
    employment_types: [] as string[],
    salary_min: null as number | null,
    salary_max: null as number | null,
    remote_required: false,
    target_start: null as string | null,
  }
  await page.route('**/api/v1/preferences', (route) => {
    if (route.request().method() === 'PUT') {
      stored = JSON.parse(route.request().postData() ?? '{}')
      return route.fulfill({ json: stored })
    }
    return route.fulfill({ json: stored })
  })

  await page.goto('/preferences')
  await page.getByLabel('Desired roles (comma separated)').fill('Backend Engineer, SRE')
  await page.getByLabel('Salary min (JPY/yr)').fill('8000000')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Saved')).toBeVisible()
  expect(stored.desired_roles).toEqual(['Backend Engineer', 'SRE'])
  expect(stored.salary_min).toBe(8000000)
})
