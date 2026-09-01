import { useRef, useState } from 'react'

import { cx } from '../lib/cn'

interface Props {
  onFile: (file: File) => void
  accept: string
  disabled?: boolean
  label: string
}

export function FileDropzone({ onFile, accept, disabled = false, label }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const open = () => {
    if (!disabled) inputRef.current?.click()
  }

  const take = (files: FileList | null) => {
    const file = files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          open()
        }
      }}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        if (!disabled) take(e.dataTransfer.files)
      }}
      className={cx(
        'flex flex-col items-center gap-1 rounded-lg border-2 border-dashed px-6 py-8 text-center text-sm transition',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500',
        dragging
          ? 'border-sky-500 bg-sky-50 dark:bg-sky-950'
          : 'border-neutral-300 dark:border-neutral-700',
        disabled ? 'opacity-50' : 'cursor-pointer hover:border-neutral-400',
      )}
    >
      <span className="font-medium">Drop a PDF or DOCX here</span>
      <span className="text-neutral-500">or click to browse</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        disabled={disabled}
        aria-label={label}
        className="sr-only"
        onChange={(e) => take(e.target.files)}
      />
    </div>
  )
}
