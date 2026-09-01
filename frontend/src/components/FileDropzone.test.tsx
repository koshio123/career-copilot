import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { FileDropzone } from './FileDropzone'

const pdf = () => new File(['%PDF-1.4'], 'cv.pdf', { type: 'application/pdf' })

test('reports a dropped file', () => {
  const onFile = vi.fn()
  render(<FileDropzone label="Upload a PDF or DOCX" accept=".pdf" onFile={onFile} />)

  const file = pdf()
  fireEvent.drop(screen.getByRole('button'), { dataTransfer: { files: [file] } })

  expect(onFile).toHaveBeenCalledWith(file)
})

test('reports a file chosen through the hidden input', () => {
  const onFile = vi.fn()
  render(<FileDropzone label="Upload a PDF or DOCX" accept=".pdf" onFile={onFile} />)

  const file = pdf()
  fireEvent.change(screen.getByLabelText(/upload a pdf or docx/i), { target: { files: [file] } })

  expect(onFile).toHaveBeenCalledWith(file)
})

test('ignores drops while disabled', () => {
  const onFile = vi.fn()
  render(<FileDropzone label="Upload a PDF or DOCX" accept=".pdf" disabled onFile={onFile} />)

  fireEvent.drop(screen.getByRole('button'), { dataTransfer: { files: [pdf()] } })

  expect(onFile).not.toHaveBeenCalled()
})
