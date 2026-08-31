import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'

import type { ApiError } from '../api/client'
import { Button, Field, Input, Spinner } from '../components/ui'
import { useMe, useRequestOtp, useVerifyOtp } from '../auth/hooks'

const emailSchema = z.object({ email: z.email('Enter a valid email address') })
const codeSchema = z.object({ code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code') })

type EmailForm = z.infer<typeof emailSchema>
type CodeForm = z.infer<typeof codeSchema>

export function LoginPage() {
  const { data: user, isLoading } = useMe()
  const location = useLocation() as { state?: { from?: string } }
  const navigate = useNavigate()

  const [email, setEmail] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const requestOtp = useRequestOtp()
  const verifyOtp = useVerifyOtp()

  const emailForm = useForm<EmailForm>({ resolver: zodResolver(emailSchema) })
  const codeForm = useForm<CodeForm>({ resolver: zodResolver(codeSchema) })

  if (!isLoading && user) return <Navigate to={location.state?.from ?? '/'} replace />

  const submitEmail = emailForm.handleSubmit(async ({ email: value }) => {
    setError(null)
    try {
      await requestOtp.mutateAsync(value)
      setEmail(value)
    } catch (e) {
      setError((e as ApiError).detail)
    }
  })

  const submitCode = codeForm.handleSubmit(async ({ code }) => {
    setError(null)
    try {
      await verifyOtp.mutateAsync({ email: email!, code })
      navigate(location.state?.from ?? '/', { replace: true })
    } catch (e) {
      setError((e as ApiError).detail)
    }
  })

  return (
    <div className="grid min-h-dvh place-items-center px-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold">Sign in to Career Copilot</h1>
          <p className="text-sm text-neutral-500">
            {email ? `We sent a code to ${email}` : "We'll email you a one-time code"}
          </p>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
          >
            {error}
          </p>
        )}

        {!email ? (
          <form key="email" onSubmit={submitEmail} className="space-y-4" noValidate>
            <Field label="Email" error={emailForm.formState.errors.email?.message}>
              <Input type="email" autoComplete="email" autoFocus {...emailForm.register('email')} />
            </Field>
            <Button type="submit" className="w-full" disabled={requestOtp.isPending}>
              {requestOtp.isPending ? <Spinner /> : 'Send code'}
            </Button>
          </form>
        ) : (
          <form key="code" onSubmit={submitCode} className="space-y-4" noValidate>
            <Field label="6-digit code" error={codeForm.formState.errors.code?.message}>
              <Input
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                autoFocus
                {...codeForm.register('code')}
              />
            </Field>
            <Button type="submit" className="w-full" disabled={verifyOtp.isPending}>
              {verifyOtp.isPending ? <Spinner /> : 'Verify'}
            </Button>
            <button
              type="button"
              onClick={() => {
                setEmail(null)
                setError(null)
              }}
              className="w-full text-center text-xs text-neutral-500 hover:underline"
            >
              Use a different email
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
