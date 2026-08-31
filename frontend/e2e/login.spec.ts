import { expect, test } from '@playwright/test'

const USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'e2e@example.com',
  display_name: null,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
}

test('sign in with an email OTP, then sign out', async ({ page }) => {
  let signedIn = false

  await page.route('**/api/v1/me', (route) =>
    signedIn
      ? route.fulfill({ json: USER })
      : route.fulfill({
          status: 401,
          contentType: 'application/problem+json',
          json: { code: 'authentication-required', detail: 'Not signed in.' },
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
  await expect(page).toHaveURL(/\/login$/)

  await page.getByLabel('Email').fill(USER.email)
  await page.getByRole('button', { name: 'Send code' }).click()

  await page.getByLabel('6-digit code').fill('123456')
  await page.getByRole('button', { name: 'Verify' }).click()

  await expect(page).toHaveURL('http://localhost:3000/')
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  await expect(page.getByRole('banner').getByText(USER.email)).toBeVisible()

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
})
