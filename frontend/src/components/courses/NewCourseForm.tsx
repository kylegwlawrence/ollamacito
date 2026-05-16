import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCourseStore } from '@/stores/courseStore'
import { useRagServersStore } from '@/stores/ragServersStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { useToastStore } from '@/stores/toastStore'
import { useModels } from '@/hooks/useModels'
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
  if (
    youngLevels.includes(age) &&
    (target === 'proficient' || target === 'expert')
  ) {
    return 'A primary/elementary audience aiming for proficient/expert mastery is ambitious — verify this is what you want.'
  }
  return null
}

export const NewCourseForm = () => {
  const navigate = useNavigate()
  const ragServers = useRagServersStore((s) => s.servers)
  const ragServersLoading = useRagServersStore((s) => s.loading)
  const ragServersLoaded = useRagServersStore((s) => s.loaded)
  const createCourse = useCourseStore((s) => s.createCourse)
  const showToast = useToastStore((s) => s.showToast)
  const globalSettings = useSettingsStore((s) => s.settings)
  const { models } = useModels()

  const [ragServerId, setRagServerId] = useState<string>('')
  const [ragTopK, setRagTopK] = useState<string>('5')
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
  const [overrideModel, setOverrideModel] = useState<string>('')
  const [overrideTemperature, setOverrideTemperature] = useState<string>(() =>
    String(globalSettings.default_temperature)
  )
  const [overrideNumCtx, setOverrideNumCtx] = useState<string>(() =>
    String(globalSettings.num_ctx)
  )
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const validationError = (): string | null => {
    if (!ragServerId) return 'Pick a RAG server.'
    const topK = Number(ragTopK)
    if (!Number.isFinite(topK) || topK < 1 || topK > 50) {
      return 'top_k must be a number between 1 and 50.'
    }
    if (topic.trim().length < 2) return 'Topic is too short.'
    const min = Number(hoursMin)
    const max = Number(hoursMax)
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return 'Hours must be numbers.'
    }
    if (min < 1 || max < 1) return 'Hours must be ≥ 1.'
    if (max < min) return 'Maximum hours must be ≥ minimum hours.'
    const temp = Number(overrideTemperature)
    if (!Number.isFinite(temp) || temp < 0 || temp > 2) {
      return 'Temperature must be between 0 and 2.'
    }
    const ctx = Number(overrideNumCtx)
    if (!Number.isFinite(ctx) || ctx < 512 || ctx > 131072) {
      return 'Context window must be between 512 and 131072.'
    }
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
    const created = await createCourse({
      rag_server_id: ragServerId,
      rag_top_k: Number(ragTopK),
      input,
      override_model: overrideModel || null,
      override_temperature: Number(overrideTemperature),
      override_num_ctx: Number(overrideNumCtx),
    })
    setSubmitting(false)
    if (created) {
      showToast('Course created. Starting generation…', 'success')
      navigate(`/courses/${created.id}`, { state: { autoStart: true } })
    } else {
      setSubmitError(
        'Failed to create course. Check that the RAG server you picked still exists.'
      )
    }
  }

  return (
    <div className="new-course">
      <ViewHeader title="New course" />
      <div className="new-course__body">
        {ragServersLoading && !ragServersLoaded ? (
          <div className="card new-course__section">
            <p>Loading RAG servers…</p>
          </div>
        ) : ragServers.length === 0 ? (
          <div className="card new-course__section">
            <h3 className="new-course__section-title">RAG Source</h3>
            <p>No RAG servers configured. Add one before creating a course.</p>
            <Button
              onClick={() => navigate('/rag-servers')}
              variant="primary"
              size="sm"
              leadingIcon="add"
            >
              Manage RAG servers
            </Button>
          </div>
        ) : (
          <>
            {/* ───── RAG Source ───────────────────────────────────────── */}
            <div className="card new-course__section">
              <h3 className="new-course__section-title">RAG Source</h3>
              <div className="new-course__field">
                <span className="new-course__label">RAG server</span>
                <Select
                  value={ragServerId}
                  onChange={setRagServerId}
                  placeholder="Choose a RAG server"
                  options={ragServers.map((s) => ({
                    value: s.id,
                    label: `${s.name} (${s.corpus_id})`,
                  }))}
                  aria-label="RAG server"
                />
                <span className="new-course__hint">
                  Pick the corpus the research agent will search during
                  generation.
                </span>
              </div>
              <div className="new-course__field">
                <label className="new-course__label" htmlFor="topk">
                  Retrieval top_k
                </label>
                <input
                  id="topk"
                  className="new-course__input"
                  type="number"
                  min={1}
                  max={50}
                  value={ragTopK}
                  onChange={(e) => setRagTopK(e.target.value)}
                  style={{ maxWidth: 120 }}
                />
                <span className="new-course__hint">
                  How many results the agent fetches per query (1–50, default
                  5).
                </span>
              </div>
            </div>

            {/* ───── Topic & Audience ─────────────────────────────────── */}
            <div className="card new-course__section">
              <h3 className="new-course__section-title">Topic & Audience</h3>
              <div className="new-course__field">
                <label className="new-course__label" htmlFor="topic">
                  Topic
                </label>
                <input
                  id="topic"
                  className="new-course__input"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Photosynthesis"
                  maxLength={200}
                />
              </div>
              <div className="new-course__field">
                <span className="new-course__label">Audience age</span>
                <Select
                  value={age}
                  onChange={(v) => setAge(v as AgeCategory)}
                  options={AGE_CATEGORIES.map((v) => ({
                    value: v,
                    label: AGE_CATEGORY_LABELS[v],
                  }))}
                  aria-label="Audience age"
                />
              </div>
              <div className="new-course__row">
                <div className="new-course__field">
                  <span className="new-course__label">Current expertise</span>
                  <Select
                    value={current}
                    onChange={(v) => setCurrent(v as ExpertiseLevel)}
                    options={EXPERTISE_LEVELS.map((v) => ({
                      value: v,
                      label: v,
                    }))}
                    aria-label="Current expertise"
                  />
                </div>
                <div className="new-course__field">
                  <span className="new-course__label">Target expertise</span>
                  <Select
                    value={target}
                    onChange={(v) => setTarget(v as ExpertiseLevel)}
                    options={EXPERTISE_LEVELS.map((v) => ({
                      value: v,
                      label: v,
                    }))}
                    aria-label="Target expertise"
                  />
                </div>
              </div>
              {audienceWarning && (
                <span className="new-course__warning" role="alert">
                  {audienceWarning}
                </span>
              )}
            </div>

            {/* ───── Course Length ────────────────────────────────────── */}
            <div className="card new-course__section">
              <h3 className="new-course__section-title">Course Length</h3>
              <div className="new-course__row">
                <div className="new-course__field">
                  <label className="new-course__label" htmlFor="hmin">
                    Hours (min)
                  </label>
                  <input
                    id="hmin"
                    className="new-course__input"
                    type="number"
                    min={1}
                    max={500}
                    value={hoursMin}
                    onChange={(e) => setHoursMin(e.target.value)}
                  />
                </div>
                <div className="new-course__field">
                  <label className="new-course__label" htmlFor="hmax">
                    Hours (max)
                  </label>
                  <input
                    id="hmax"
                    className="new-course__input"
                    type="number"
                    min={1}
                    max={500}
                    value={hoursMax}
                    onChange={(e) => setHoursMax(e.target.value)}
                  />
                </div>
              </div>
              <div className="new-course__field">
                <span className="new-course__label">Included resources</span>
                <div className="new-course__resources">
                  {RESOURCE_TYPES.map((r) => {
                    const on = resources.has(r)
                    return (
                      <button
                        key={r}
                        type="button"
                        className={`new-course__resource-chip${on ? ' new-course__resource-chip--on' : ''}`}
                        onClick={() => {
                          const next = new Set(resources)
                          if (on) {
                            next.delete(r)
                          } else {
                            next.add(r)
                          }
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
            </div>

            {/* ───── Model Overrides ──────────────────────────────────── */}
            <div className="card new-course__section">
              <h3 className="new-course__section-title">Model Overrides</h3>
              <div className="new-course__field">
                <span className="new-course__label">Model</span>
                <Select
                  value={overrideModel}
                  onChange={setOverrideModel}
                  placeholder={`Default (${globalSettings.default_model || 'global setting'})`}
                  options={models.map((m) => ({
                    value: m.name,
                    label: m.name,
                  }))}
                  aria-label="Model override"
                />
                <span className="new-course__hint">
                  Leave blank to use the global default model.
                </span>
              </div>
              <div className="new-course__row">
                <div className="new-course__field">
                  <label className="new-course__label" htmlFor="temperature">
                    Temperature
                  </label>
                  <input
                    id="temperature"
                    className="new-course__input"
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={overrideTemperature}
                    onChange={(e) => setOverrideTemperature(e.target.value)}
                    style={{ maxWidth: 120 }}
                  />
                  <span className="new-course__hint">0.0–2.0</span>
                </div>
                <div className="new-course__field">
                  <label className="new-course__label" htmlFor="num-ctx">
                    Context window
                  </label>
                  <input
                    id="num-ctx"
                    className="new-course__input"
                    type="number"
                    min={512}
                    max={131072}
                    step={512}
                    value={overrideNumCtx}
                    onChange={(e) => setOverrideNumCtx(e.target.value)}
                    style={{ maxWidth: 160 }}
                  />
                  <span className="new-course__hint">512–131072 tokens</span>
                </div>
              </div>
            </div>

            {/* ───── Optional Notes ───────────────────────────────────── */}
            <div className="card new-course__section">
              <h3 className="new-course__section-title">Optional Notes</h3>
              <div className="new-course__field">
                <label className="new-course__label" htmlFor="ctx">
                  Learner context
                </label>
                <textarea
                  id="ctx"
                  className="new-course__textarea"
                  value={learnerContext}
                  onChange={(e) =>
                    setLearnerContext(e.target.value.slice(0, 1000))
                  }
                  placeholder="Anything else the model should know about the learner."
                />
                <span className="new-course__hint">
                  {learnerContext.length} / 1000
                </span>
              </div>
            </div>

            {submitError && (
              <span className="new-course__error" role="alert">
                {submitError}
              </span>
            )}

            <div className="new-course__actions">
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
    </div>
  )
}
