import type { Page } from '@playwright/test'

export const USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'e2e@example.com',
  display_name: null,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
}

/** Stub the auth endpoints and run the OTP login. Leaves the app on "/". */
export async function signIn(page: Page): Promise<void> {
  let signedIn = false
  await page.route('**/api/v1/me', (route) =>
    signedIn
      ? route.fulfill({ json: USER })
      : route.fulfill({
          status: 401,
          contentType: 'application/problem+json',
          json: { code: 'authentication-required' },
        }),
  )
  await page.route('**/api/v1/auth/otp/request', (route) =>
    route.fulfill({ status: 202, json: { status: 'accepted' } }),
  )
  await page.route('**/api/v1/auth/otp/verify', (route) => {
    signedIn = true
    return route.fulfill({ json: USER })
  })
  await page.route('**/api/v1/auth/logout', (route) => {
    signedIn = false
    return route.fulfill({ status: 204, body: '' })
  })

  await page.goto('/')
  await page.getByLabel('Email').fill(USER.email)
  await page.getByRole('button', { name: 'Send code' }).click()
  await page.getByLabel('6-digit code').fill('123456')
  await page.getByRole('button', { name: 'Verify' }).click()
  await page.waitForURL('http://localhost:3000/')
}
