import { expect, test } from '@playwright/test'

import { signIn, USER } from './helpers'

test('sign in with an email OTP, then sign out', async ({ page }) => {
  await signIn(page)

  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  await expect(page.getByRole('banner').getByText(USER.email)).toBeVisible()

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
})
