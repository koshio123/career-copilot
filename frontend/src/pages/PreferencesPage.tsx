import { useEffect } from 'react'
import { useForm } from 'react-hook-form'

import { Button, Field, Input, Spinner } from '../components/ui'
import { usePreferences, useSavePreferences, type Preferences } from '../features/preferences/hooks'

interface FormValues {
  desired_roles: string
  locations: string
  employment_types: string
  salary_min: string
  salary_max: string
  remote_required: boolean
  target_start: string
}

const csv = (value: string): string[] =>
  value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)

const toInt = (value: string): number | null => (value === '' ? null : Number.parseInt(value, 10))

export function PreferencesPage() {
  const query = usePreferences()
  const save = useSavePreferences()
  const { register, handleSubmit, reset } = useForm<FormValues>()

  useEffect(() => {
    if (!query.data) return
    reset({
      desired_roles: query.data.desired_roles.join(', '),
      locations: query.data.locations.join(', '),
      employment_types: query.data.employment_types.join(', '),
      salary_min: query.data.salary_min?.toString() ?? '',
      salary_max: query.data.salary_max?.toString() ?? '',
      remote_required: query.data.remote_required,
      target_start: query.data.target_start ?? '',
    })
  }, [query.data, reset])

  if (query.isLoading) return <Spinner />

  const onSubmit = (values: FormValues) => {
    const payload: Preferences = {
      desired_roles: csv(values.desired_roles),
      locations: csv(values.locations),
      employment_types: csv(values.employment_types),
      salary_min: toInt(values.salary_min),
      salary_max: toInt(values.salary_max),
      remote_required: values.remote_required,
      target_start: values.target_start || null,
    }
    save.mutate(payload)
  }

  return (
    <form className="max-w-lg space-y-5" onSubmit={handleSubmit(onSubmit)}>
      <h1 className="text-2xl font-semibold">Job preferences</h1>

      <Field label="Desired roles (comma separated)">
        <Input {...register('desired_roles')} placeholder="Backend Engineer, Platform Engineer" />
      </Field>
      <Field label="Locations (comma separated)">
        <Input {...register('locations')} placeholder="Tokyo, Remote" />
      </Field>
      <Field label="Employment types">
        <Input {...register('employment_types')} placeholder="full_time" />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Salary min (JPY/yr)">
          <Input type="number" min={0} {...register('salary_min')} />
        </Field>
        <Field label="Salary max (JPY/yr)">
          <Input type="number" min={0} {...register('salary_max')} />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register('remote_required')} />
        Remote required
      </label>
      <Field label="Target start date">
        <Input type="date" {...register('target_start')} />
      </Field>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? <Spinner /> : 'Save'}
        </Button>
        {save.isSuccess && <span className="text-sm text-green-600">Saved</span>}
      </div>
    </form>
  )
}
