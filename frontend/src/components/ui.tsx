import type { ComponentPropsWithRef, ReactNode } from 'react'

const cx = (...parts: (string | false | undefined)[]) => parts.filter(Boolean).join(' ')

export function Button({
  className,
  variant = 'primary',
  ...props
}: ComponentPropsWithRef<'button'> & { variant?: 'primary' | 'ghost' }) {
  const base =
    'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium ' +
    'transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 ' +
    'focus-visible:outline-offset-2 focus-visible:outline-sky-500'
  const styles = {
    primary: 'bg-sky-600 text-white hover:bg-sky-700',
    ghost:
      'border border-neutral-300 text-neutral-800 hover:bg-neutral-100 ' +
      'dark:border-neutral-700 dark:text-neutral-100 dark:hover:bg-neutral-800',
  }
  return <button className={cx(base, styles[variant], className)} {...props} />
}

export function Input({ className, ...props }: ComponentPropsWithRef<'input'>) {
  return (
    <input
      className={cx(
        'w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm ' +
          'placeholder:text-neutral-400 focus:border-sky-500 focus:outline-none ' +
          'dark:border-neutral-700 dark:bg-neutral-900',
        className,
      )}
      {...props}
    />
  )
}

export function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: ReactNode
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-neutral-700 dark:text-neutral-300">{label}</span>
      {children}
      {error && (
        <span role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </span>
      )}
    </label>
  )
}

export function Spinner() {
  return (
    <span
      role="status"
      aria-label="Loading"
      className="inline-block size-5 animate-spin rounded-full border-2 border-neutral-300 border-t-sky-600"
    />
  )
}

export function FullPageSpinner() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <Spinner />
    </div>
  )
}
