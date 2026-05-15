import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCourseStore } from '@/stores/courseStore'
import { useProjectsStore } from '@/stores/projectsStore'
import { useToastStore } from '@/stores/toastStore'
import { Button } from '../common/Button'
import { Select } from '../common/Select'
import { ViewHeader } from '../common/ViewHeader'
import {
  AGE_CATEGORY_LABELS,
  EXPERTISE_LEVELS,
  RESOURCE_LABELS,
} from '@/types'
import type {
  AgeCategory,
  CourseGenerationRequest,
  ExpertiseLevel,
  ResourceType,
} from '@/types'
import './courses.css'

const RESOURCE_TYPES: ResourceType[] = [
  'readings',
  'practice_questions',
  'quizzes',
  'projects',
]

const AGE_CATEGORIES = Object.keys(AGE_CATEGORY_LABELS) as AgeCategory[]

/** Crude age↔target heuristic for the soft-warning banner. */
const mismatchedAudienceWarning = (
  age: AgeCategory,
  target: ExpertiseLevel
): string | null => {
  const universityLevels: AgeCategory[] = ['bachelors', 'masters', 'phd']
  const youngLevels: AgeCategory[] = ['primary', 'elementary']
  if (universityLevels.includes(age) && target === 'novice') {
    return 'A university audience aiming for "novice" mastery is unusual — verify this is what you want.'
  }
  if (youngLevels.includes(age) && (target === 'proficient' || target === 'expert')) {
    return 'A primary/elementary audience aiming for proficient/expert mastery is ambitious — verify this is what you want.'
  }
  return null
}

export const NewCourseForm = () => {
  const navigate = useNavigate()
  const projects = useProjectsStore((s) => s.projects)
  const projectsLoading = useProjectsStore((s) => s.loading)
  const createCourse = useCourseStore((s) => s.createCourse)
  const showToast = useToastStore((s) => s.showToast)

  const ragReadyProjects = useMemo(
    () => projects.filter((p) => p.rag_enabled && p.rag_server_id),
    [projects]
  )

  const [projectId, setProjectId] = useState<string>('')
  const [topic, setTopic] = useState('')
  const [current, setCurrent] = useState<ExpertiseLevel>('novice')
  const [target, setTarget] = useState<ExpertiseLevel>('competent')
  const [age, setAge] = useState<AgeCategory>('elementary')
  const [hoursMin, setHoursMin] = useState('4')
  const [hoursMax, setHoursMax] = useState('6')
  const [resources, setResources] = useState<Set<ResourceType>>(
    new Set(['readings', 'quizzes'])
  )
  const [learnerContext, setLearnerContext] = useState('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const validationError = (): string | null => {
    if (!projectId) return 'Pick a project with RAG configured.'
    if (topic.trim().length < 2) return 'Topic is too short.'
    const min = Number(hoursMin)
    const max = Number(hoursMax)
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return 'Hours must be numbers.'
    }
    if (min < 1 || max < 1) return 'Hours must be ≥ 1.'
    if (max < min) return 'Maximum hours must be ≥ minimum hours.'
    return null
  }

  const audienceWarning = mismatchedAudienceWarning(age, target)
  const formError = validationError()

  const handleSubmit = async () => {
    if (formError) {
      setSubmitError(formError)
      return
    }
    setSubmitting(true)
    setSubmitError(null)
    const input: CourseGenerationRequest = {
      topic: topic.trim(),
      current_expertise: current,
      target_expertise: target,
      age_category: age,
      hours_min: Number(hoursMin),
      hours_max: Number(hoursMax),
      included_resources: Array.from(resources),
      learner_context: learnerContext.trim() || null,
    }
    const created = await createCourse({ project_id: projectId, input })
    setSubmitting(false)
    if (created) {
      showToast('Course created. Starting generation…', 'success')
      navigate(`/courses/${created.id}`, { state: { autoStart: true } })
    } else {
      setSubmitError('Failed to create course. Check that the project still has RAG configured.')
    }
  }

  return (
    <>
      <ViewHeader title="New course" />
      <div className="course-form">
        {projectsLoading ? (
          <p>Loading projects…</p>
        ) : ragReadyProjects.length === 0 ? (
          <div className="course-form__error">
            No projects with RAG configured. Open a project and configure its
            RAG server before creating a course.
          </div>
        ) : (
          <>
            <div className="course-form__field">
              <label className="course-form__label" htmlFor="project">
                Project
              </label>
              <Select
                value={projectId}
                onChange={setProjectId}
                placeholder="Choose a project"
                options={ragReadyProjects.map((p) => ({
                  value: p.id,
                  label: p.name,
                }))}
              />
              <span className="course-form__hint">
                Only projects with RAG enabled + a RAG server selected are
                shown.
              </span>
            </div>

            <div className="course-form__field">
              <label className="course-form__label" htmlFor="topic">
                Topic
              </label>
              <input
                id="topic"
                className="course-form__input"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Photosynthesis"
                maxLength={200}
              />
            </div>

            <div className="course-form__row">
              <div className="course-form__field">
                <label className="course-form__label">Current expertise</label>
                <Select
                  value={current}
                  onChange={(v) => setCurrent(v as ExpertiseLevel)}
                  options={EXPERTISE_LEVELS.map((v) => ({ value: v, label: v }))}
                />
              </div>
              <div className="course-form__field">
                <label className="course-form__label">Target expertise</label>
                <Select
                  value={target}
                  onChange={(v) => setTarget(v as ExpertiseLevel)}
                  options={EXPERTISE_LEVELS.map((v) => ({ value: v, label: v }))}
                />
              </div>
            </div>

            <div className="course-form__field">
              <label className="course-form__label">Audience age</label>
              <Select
                value={age}
                onChange={(v) => setAge(v as AgeCategory)}
                options={AGE_CATEGORIES.map((v) => ({
                  value: v,
                  label: AGE_CATEGORY_LABELS[v],
                }))}
              />
            </div>

            {audienceWarning && (
              <div className="course-form__warning" role="alert">
                {audienceWarning}
              </div>
            )}

            <div className="course-form__row">
              <div className="course-form__field">
                <label className="course-form__label" htmlFor="hmin">
                  Hours (min)
                </label>
                <input
                  id="hmin"
                  className="course-form__input"
                  type="number"
                  min={1}
                  max={500}
                  value={hoursMin}
                  onChange={(e) => setHoursMin(e.target.value)}
                />
              </div>
              <div className="course-form__field">
                <label className="course-form__label" htmlFor="hmax">
                  Hours (max)
                </label>
                <input
                  id="hmax"
                  className="course-form__input"
                  type="number"
                  min={1}
                  max={500}
                  value={hoursMax}
                  onChange={(e) => setHoursMax(e.target.value)}
                />
              </div>
            </div>

            <div className="course-form__field">
              <label className="course-form__label">Included resources</label>
              <div className="course-form__resources">
                {RESOURCE_TYPES.map((r) => {
                  const on = resources.has(r)
                  return (
                    <button
                      key={r}
                      type="button"
                      className={`course-form__resource-chip${on ? ' course-form__resource-chip--on' : ''}`}
                      onClick={() => {
                        const next = new Set(resources)
                        on ? next.delete(r) : next.add(r)
                        setResources(next)
                      }}
                      aria-pressed={on}
                    >
                      {RESOURCE_LABELS[r]}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="course-form__field">
              <label className="course-form__label" htmlFor="ctx">
                Learner context (optional)
              </label>
              <textarea
                id="ctx"
                className="course-form__textarea"
                value={learnerContext}
                onChange={(e) => setLearnerContext(e.target.value.slice(0, 1000))}
                placeholder="Anything else the model should know about the learner."
              />
              <span className="course-form__hint">
                {learnerContext.length} / 1000
              </span>
            </div>

            {submitError && (
              <div className="course-form__error" role="alert">
                {submitError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 'var(--s-3)' }}>
              <Button
                onClick={handleSubmit}
                disabled={submitting || !!formError}
                variant="primary"
              >
                {submitting ? 'Creating…' : 'Create course'}
              </Button>
              <Button
                onClick={() => navigate('/courses')}
                variant="ghost"
                disabled={submitting}
              >
                Cancel
              </Button>
            </div>
          </>
        )}
      </div>
    </>
  )
}
