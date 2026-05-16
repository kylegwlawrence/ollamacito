import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useCourseGeneration } from '@/hooks/useCourseGeneration'
import { useConfirmStore } from '@/stores/confirmStore'
import { useCourseStore } from '@/stores/courseStore'
import { useToastStore } from '@/stores/toastStore'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ViewHeader } from '../common/ViewHeader'
import { OutlineRenderer } from './OutlineRenderer'
import { ResearchTrace } from './ResearchTrace'
import type { CourseOutline, ValidationErrorEntry } from '@/types'
import './courses.css'

export const CourseDetail = () => {
  const { courseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const autoStart = (location.state as { autoStart?: boolean } | null)?.autoStart

  const course = useCourseStore((s) =>
    courseId ? s.coursesById[courseId] : null
  )
  const loadOne = useCourseStore((s) => s.loadOne)
  const updateCourse = useCourseStore((s) => s.updateCourse)
  const removeCourse = useCourseStore((s) => s.removeCourse)
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)

  const gen = useCourseGeneration()

  const startedRef = useRef(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

  useEffect(() => {
    if (courseId) {
      loadOne(courseId)
    }
  }, [courseId, loadOne])

  // Auto-fire generation when arriving from the form.
  useEffect(() => {
    if (autoStart && courseId && !startedRef.current) {
      startedRef.current = true
      gen.start(courseId).catch(() => {})
    }
  }, [autoStart, courseId, gen])

  if (!courseId) return null
  if (!course) {
    return (
      <div className="course-detail">
        <div className="course-detail__body">
          <LoadingSpinner />
        </div>
      </div>
    )
  }

  const handleRename = async () => {
    if (!editingTitle) {
      setTitleDraft(course.title)
      setEditingTitle(true)
      return
    }
    if (titleDraft.trim() && titleDraft.trim() !== course.title) {
      const updated = await updateCourse(course.id, { title: titleDraft.trim() })
      if (updated) showToast('Title updated', 'success')
    }
    setEditingTitle(false)
  }

  const handleRegenerate = async () => {
    const ok = await confirm({
      title: 'Regenerate this course?',
      message:
        'The current outline will be replaced with a freshly generated one. This can take a minute.',
      confirmLabel: 'Regenerate',
    })
    if (!ok) return
    await gen.regenerate(course.id)
  }

  const handleDelete = async () => {
    const ok = await confirm({
      title: 'Delete this course?',
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    await removeCourse(course.id)
    navigate('/courses')
  }

  const handleDownload = () => {
    const data = gen.outline ?? course.outline
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${course.title.replace(/\s+/g, '_').toLowerCase()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Resolve which outline to render: in-flight generation result first, then
  // whatever was persisted on the row.
  const outline: CourseOutline | null = gen.outline ?? course.outline
  const validationErrors: ValidationErrorEntry[] | null =
    gen.validationErrors ?? course.validation_errors

  const isStreaming = gen.isStreaming
  const showResearchTrace =
    isStreaming || gen.toolCalls.length > 0 || gen.researchChunks

  return (
    <div className="course-detail">
      <ViewHeader
        breadcrumb={
          <button
            onClick={() => navigate('/courses')}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}
          >
            ← Courses
          </button>
        }
        title={
          editingTitle ? (
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              className="new-course__input"
              style={{ minWidth: 320 }}
            />
          ) : (
            course.title
          )
        }
        actions={
          <div className="course-detail__actions">
            <Button onClick={handleRename} variant="ghost" size="sm">
              {editingTitle ? 'Save' : 'Rename'}
            </Button>
            <Button
              onClick={handleRegenerate}
              variant="secondary"
              size="sm"
              disabled={isStreaming}
              leadingIcon="refresh"
            >
              Regenerate
            </Button>
            <Button
              onClick={handleDownload}
              variant="ghost"
              size="sm"
              disabled={!outline}
              leadingIcon="download"
            >
              Download JSON
            </Button>
            <Button
              onClick={handleDelete}
              variant="danger"
              size="sm"
              leadingIcon="delete"
              disabled={isStreaming}
            >
              Delete
            </Button>
          </div>
        }
      />
      <div className="course-detail__body">
        {course.status === 'pending' && !isStreaming && (
          <div>
            <Button
              onClick={() => gen.start(course.id)}
              variant="primary"
            >
              Generate now
            </Button>
          </div>
        )}

        {showResearchTrace && (
          <ResearchTrace
            phase={gen.phase}
            toolCalls={gen.toolCalls}
            notes={gen.researchChunks}
          />
        )}

        {gen.error && (
          <div className="course-detail__banner course-detail__banner--error" role="alert">
            {gen.error}
          </div>
        )}

        {validationErrors && validationErrors.length > 0 && (
          <div className="course-detail__banner course-detail__banner--warn" role="status">
            <strong>Needs review:</strong>
            <ul style={{ margin: 'var(--s-2) 0 0 var(--s-5)' }}>
              {validationErrors.map((v, i) => (
                <li key={i}>
                  <code style={{ marginRight: 'var(--s-2)' }}>{v.path}</code>
                  {v.msg}
                </li>
              ))}
            </ul>
          </div>
        )}

        {outline ? (
          <OutlineRenderer outline={outline} />
        ) : (
          !isStreaming && course.status !== 'pending' && (
            <p>No outline produced yet.</p>
          )
        )}
      </div>
    </div>
  )
}
