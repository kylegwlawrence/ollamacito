import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NewCourseForm } from './NewCourseForm'
import { useCourseStore } from '@/stores/courseStore'
import { useProjectsStore } from '@/stores/projectsStore'
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

const buildProject = (overrides: Partial<{
  id: string
  name: string
  rag_enabled: boolean
  rag_server_id: string | null
}> = {}) => ({
  id: 'p1',
  name: 'Project One',
  custom_instructions: null,
  is_archived: false,
  default_model: null,
  temperature: null,
  max_tokens: null,
  auto_attach_all_files: false,
  memory: null,
  rag_enabled: true,
  rag_server_id: 'rs1',
  rag_top_k: 5,
  created_at: '',
  updated_at: '',
  chat_count: 0,
  file_count: 0,
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

  it('shows a helpful empty state when no RAG-configured projects exist', () => {
    useProjectsStore.setState({
      projects: [buildProject({ rag_enabled: false, rag_server_id: null })],
      loading: false,
      loaded: true,
      error: null,
      currentProject: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    expect(
      screen.getByText(/No projects with RAG configured/)
    ).toBeInTheDocument()
  })

  it('disables submit when topic is empty or invalid', async () => {
    useProjectsStore.setState({
      projects: [buildProject()],
      loading: false,
      loaded: true,
      error: null,
      currentProject: null,
    })
    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )
    const submit = screen.getByRole('button', { name: /Create course/ })
    // Submit is disabled because no project picked yet AND topic is empty
    expect(submit).toBeDisabled()
  })

  it('submits and navigates with autoStart on success', async () => {
    const user = userEvent.setup()
    const createCourseMock = vi.fn(async () => ({
      id: 'c-new',
      user_id: 'u',
      project_id: 'p1',
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
    useProjectsStore.setState({
      projects: [buildProject()],
      loading: false,
      loaded: true,
      error: null,
      currentProject: null,
    })

    render(
      <MemoryRouter>
        <NewCourseForm />
      </MemoryRouter>
    )

    // Pick project
    const projectSelect = screen.getByRole('button', {
      name: /Choose a project/,
    })
    await user.click(projectSelect)
    await user.click(screen.getByRole('option', { name: 'Project One' }))

    // Topic
    await user.type(screen.getByLabelText('Topic'), 'Photosynthesis')

    // Submit
    const submit = screen.getByRole('button', { name: /Create course/ })
    expect(submit).not.toBeDisabled()
    await user.click(submit)

    expect(createCourseMock).toHaveBeenCalledTimes(1)
    expect(createCourseMock).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 'p1',
        input: expect.objectContaining({ topic: 'Photosynthesis' }),
      })
    )

    expect(navigateMock).toHaveBeenCalledWith('/courses/c-new', {
      state: { autoStart: true },
    })
  })

  it('rejects hours_max < hours_min', async () => {
    useProjectsStore.setState({
      projects: [buildProject()],
      loading: false,
      loaded: true,
      error: null,
      currentProject: null,
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

    // The Create button is disabled when validationError() returns non-null
    const submit = screen.getByRole('button', { name: /Create course/ })
    expect(submit).toBeDisabled()
  })

  it('toggles resource chips on click', async () => {
    const user = userEvent.setup()
    useProjectsStore.setState({
      projects: [buildProject()],
      loading: false,
      loaded: true,
      error: null,
      currentProject: null,
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
