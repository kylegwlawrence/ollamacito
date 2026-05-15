import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OutlineRenderer } from './OutlineRenderer'
import type { CourseOutline } from '@/types'

const outline: CourseOutline = {
  title: 'Photosynthesis 101',
  summary: 'Intro',
  target_audience: 'elementary',
  total_hours: 4,
  course_outcomes: [
    { id: 'out-c-1', text: 'Explain photosynthesis', bloom_level: 'understand' },
  ],
  modules: [
    {
      id: 'mod-1',
      title: 'Inputs and outputs',
      summary: 'M1',
      estimated_hours: 2,
      outcomes: [
        { id: 'out-m-1-1', text: 'List inputs', bloom_level: 'remember' },
      ],
      lessons: [
        {
          id: 'les-1-1',
          title: 'What goes in',
          summary: 's',
          estimated_hours: 2,
          objectives: [
            { id: 'obj-1-1-1', text: 'Identify CO2', bloom_level: 'remember' },
          ],
          prerequisite_ids: [],
          readings: [
            {
              title: 'Photosynthesis',
              url: 'https://example.com',
              snippet: null,
            },
          ],
          assessments: [],
        },
      ],
    },
    {
      id: 'mod-2',
      title: 'Why it matters',
      summary: 'M2',
      estimated_hours: 2,
      outcomes: [
        { id: 'out-m-2-1', text: 'Connect to ecosystem', bloom_level: 'understand' },
      ],
      lessons: [
        {
          id: 'les-2-1',
          title: 'Food chains',
          summary: 's',
          estimated_hours: 2,
          objectives: [
            { id: 'obj-2-1-1', text: 'Describe chains', bloom_level: 'understand' },
          ],
          prerequisite_ids: ['mod-1'],
          readings: [],
          assessments: [],
        },
      ],
    },
  ],
}

describe('OutlineRenderer', () => {
  it('renders course header and total hours', () => {
    render(<OutlineRenderer outline={outline} />)
    expect(screen.getByText('Photosynthesis 101')).toBeInTheDocument()
    expect(screen.getByText(/Total: 4 hours/)).toBeInTheDocument()
  })

  it('renders all modules and lessons', () => {
    render(<OutlineRenderer outline={outline} />)
    // "Inputs and outputs" appears twice: once as a module heading and once
    // as a prerequisite chip on les-2-1 — assert the heading specifically.
    expect(
      screen.getByRole('heading', { level: 3, name: 'Inputs and outputs' })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: 'Why it matters' })
    ).toBeInTheDocument()
    expect(screen.getByText('What goes in')).toBeInTheDocument()
    expect(screen.getByText('Food chains')).toBeInTheDocument()
  })

  it('renders Bloom badges on objectives', () => {
    render(<OutlineRenderer outline={outline} />)
    // Two `remember` and two `understand` labels exist across outcomes +
    // objectives. Assert all expected Bloom levels are present.
    expect(screen.getAllByText('remember').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('understand').length).toBeGreaterThanOrEqual(1)
  })

  it('renders external reading links with new tab target', () => {
    render(<OutlineRenderer outline={outline} />)
    const link = screen.getByRole('link', { name: 'Photosynthesis' })
    expect(link).toHaveAttribute('href', 'https://example.com')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('prerequisite chips trigger scrollIntoView on the referenced module', () => {
    const scrollSpy = vi.fn()
    Element.prototype.scrollIntoView = scrollSpy
    render(<OutlineRenderer outline={outline} />)
    // les-2-1 declares mod-1 as a prerequisite — chip should be labeled with
    // the module's title.
    const chip = screen.getByRole('button', { name: /Inputs and outputs/ })
    fireEvent.click(chip)
    expect(scrollSpy).toHaveBeenCalled()
  })
})
