import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NewCourseForm } from './NewCourseForm'
import { useCourseStore } from '@/stores/courseStore'
import { useRagServersStore } from '@/stores/ragServersStore'
import { useToastStore } from '@/stores/toastStore'

const navigateMock = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>(
    'react-router-dom'
  )
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

const buildRagServer = (
  overrides: Partial<{
    id: string
    name: string
    url: string
    corpus_id: string
  }> = {}
) => ({
  id: 'rs1',
  name: 'Simple Wiki',
  url: 'http://rag.local:8001',
  corpus_id: 'simplewiki',
  created_at: '',
  updated_at: '',
  ...overrides,
})

describe('NewCourseForm', () => {
  beforeEach(() => {
    // jsdom doesn't implement scrollIntoView, which the Select component uses
    // to keep its highlighted option in view.
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    navigateMock.mockReset()
    useToastStore.setState({ toasts: [] })
    useCourseStore.setState({
      courses: [],
      coursesById: {},
      loading: false,
      loaded: true,
      error: null,
    })
  })

  it('shows a helpful empty state when no RAG servers exist', () => {
    useRagServersStore.setState({
      servers: [],
      loading: false,
      loaded: true,
      error: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    expect(
      screen.getByText(/No RAG servers configured/)
    ).toBeInTheDocument()
    // The CTA button is rendered too.
    expect(
      screen.getByRole('button', { name: /Manage RAG servers/ })
    ).toBeInTheDocument()
  })

  it('disables submit when topic is empty or invalid', async () => {
    useRagServersStore.setState({
      servers: [buildRagServer()],
      loading: false,
      loaded: true,
      error: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    const submit = screen.getByRole('button', { name: /Create course/ })
    // Submit is disabled because no RAG server picked yet AND topic is empty
    expect(submit).toBeDisabled()
  })

  it('submits and navigates with autoStart on success', async () => {
    const user = userEvent.setup()
    const createCourseMock = vi.fn(async () => ({
      id: 'c-new',
      user_id: 'u',
      rag_server_id: 'rs1',
      rag_top_k: 5,
      title: 'Photosynthesis',
      status: 'pending' as const,
      input: {
        topic: 'Photosynthesis',
        current_expertise: 'novice' as const,
        target_expertise: 'competent' as const,
        age_category: 'elementary' as const,
        hours_min: 4,
        hours_max: 6,
        included_resources: ['readings' as const, 'quizzes' as const],
        learner_context: null,
      },
      outline: null,
      validation_errors: null,
      override_model: null,
      override_temperature: null,
      override_num_ctx: null,
      model_used: null,
      created_at: '',
      updated_at: '',
      generated_at: null,
    }))
    useCourseStore.setState({
      courses: [],
      coursesById: {},
      loading: false,
      loaded: true,
      error: null,
      createCourse: createCourseMock,
    } as Partial<ReturnType<typeof useCourseStore.getState>> as never)
    useRagServersStore.setState({
      servers: [buildRagServer()],
      loading: false,
      loaded: true,
      error: null,
    })

    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )

    // Pick RAG server — the Select's accessible name is "RAG server"
    // (aria-label takes precedence over placeholder)
    const ragSelect = screen.getByRole('button', { name: 'RAG server' })
    await user.click(ragSelect)
    await user.click(
      screen.getByRole('option', { name: 'Simple Wiki (simplewiki)' })
    )

    // Topic
    await user.type(screen.getByLabelText('Topic'), 'Photosynthesis')

    // Submit
    const submit = screen.getByRole('button', { name: /Create course/ })
    expect(submit).not.toBeDisabled()
    await user.click(submit)

    expect(createCourseMock).toHaveBeenCalledTimes(1)
    expect(createCourseMock).toHaveBeenCalledWith(
      expect.objectContaining({
        rag_server_id: 'rs1',
        rag_top_k: 5,
        input: expect.objectContaining({ topic: 'Photosynthesis' }),
      })
    )

    expect(navigateMock).toHaveBeenCalledWith('/courses/c-new', {
      state: { autoStart: true },
    })
  })

  it('rejects hours_max < hours_min', () => {
    useRagServersStore.setState({
      servers: [buildRagServer()],
      loading: false,
      loaded: true,
      error: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    const hmin = screen.getByLabelText('Hours (min)')
    const hmax = screen.getByLabelText('Hours (max)')
    fireEvent.change(hmin, { target: { value: '10' } })
    fireEvent.change(hmax, { target: { value: '5' } })

    const submit = screen.getByRole('button', { name: /Create course/ })
    expect(submit).toBeDisabled()
  })

  it('rejects top_k out of range', () => {
    useRagServersStore.setState({
      servers: [buildRagServer()],
      loading: false,
      loaded: true,
      error: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    const topK = screen.getByLabelText('Retrieval top_k')
    fireEvent.change(topK, { target: { value: '100' } })

    const submit = screen.getByRole('button', { name: /Create course/ })
    expect(submit).toBeDisabled()
  })

  it('toggles resource chips on click', async () => {
    const user = userEvent.setup()
    useRagServersStore.setState({
      servers: [buildRagServer()],
      loading: false,
      loaded: true,
      error: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    // 'Readings' starts ON; click it to toggle off.
    const readings = screen.getByRole('button', { name: 'Readings' })
    expect(readings).toHaveAttribute('aria-pressed', 'true')
    await user.click(readings)
    expect(readings).toHaveAttribute('aria-pressed', 'false')
  })
})
