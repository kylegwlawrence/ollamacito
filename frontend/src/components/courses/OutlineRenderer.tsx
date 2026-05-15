import { useMemo, useRef } from 'react'
import type {
  CourseOutline,
  Lesson,
  Module,
} from '@/types'
import './courses.css'

interface OutlineRendererProps {
  outline: CourseOutline
}

interface PrereqLookup {
  [id: string]: { title: string; ref: React.RefObject<HTMLElement> }
}

const BloomBadge = ({ level }: { level: string }) => (
  <span className="outline__bloom-badge">{level}</span>
)

const LessonBlock = ({
  lesson,
  lookup,
  refMap,
}: {
  lesson: Lesson
  lookup: PrereqLookup
  refMap: React.MutableRefObject<Record<string, HTMLElement | null>>
}) => (
  <div
    className="outline__lesson"
    ref={(el) => {
      refMap.current[lesson.id] = el
    }}
  >
    <h4 style={{ margin: 0 }}>
      {lesson.title}
      <span style={{ color: 'var(--on-surf-dim)', fontWeight: 'normal', marginLeft: 'var(--s-2)' }}>
        ({lesson.estimated_hours}h)
      </span>
    </h4>
    <p style={{ color: 'var(--on-surf-1)', margin: 'var(--s-1) 0' }}>{lesson.summary}</p>

    {lesson.prerequisite_ids.length > 0 && (
      <div style={{ marginBottom: 'var(--s-2)' }}>
        <small style={{ color: 'var(--on-surf-dim)' }}>Prerequisites: </small>
        {lesson.prerequisite_ids.map((pid) => {
          const target = lookup[pid]
          return (
            <button
              key={pid}
              className="outline__prereq-chip"
              type="button"
              onClick={() => {
                const el = refMap.current[pid]
                el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              }}
              title={target?.title ?? pid}
            >
              {target?.title ?? pid}
            </button>
          )
        })}
      </div>
    )}

    {lesson.objectives.length > 0 && (
      <div style={{ marginBottom: 'var(--s-2)' }}>
        <small style={{ color: 'var(--on-surf-dim)' }}>Objectives:</small>
        <ul style={{ margin: 'var(--s-1) 0 0 0', paddingLeft: 'var(--s-5)' }}>
          {lesson.objectives.map((obj) => (
            <li key={obj.id} className="outline__objective">
              {obj.text}
              <BloomBadge level={obj.bloom_level} />
            </li>
          ))}
        </ul>
      </div>
    )}

    {lesson.readings.length > 0 && (
      <div>
        <small style={{ color: 'var(--on-surf-dim)' }}>Readings:</small>
        <ul className="outline__readings">
          {lesson.readings.map((r, i) => (
            <li key={i}>
              <a href={r.url} target="_blank" rel="noopener noreferrer">
                {r.title}
              </a>
            </li>
          ))}
        </ul>
      </div>
    )}

    {lesson.assessments.length > 0 && (
      <div style={{ marginTop: 'var(--s-2)' }}>
        <small style={{ color: 'var(--on-surf-dim)' }}>Assessments:</small>
        <ul style={{ margin: 'var(--s-1) 0 0 0', paddingLeft: 'var(--s-5)' }}>
          {lesson.assessments.map((a) => (
            <li key={a.id}>
              <span className="outline__assessment-type">{a.type}</span>
              {a.prompt}
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
)

const ModuleBlock = ({
  module,
  lookup,
  refMap,
}: {
  module: Module
  lookup: PrereqLookup
  refMap: React.MutableRefObject<Record<string, HTMLElement | null>>
}) => (
  <section
    className="outline__module"
    ref={(el) => {
      refMap.current[module.id] = el
    }}
  >
    <div className="outline__module-header">
      <h3 style={{ margin: 0 }}>{module.title}</h3>
      <span style={{ color: 'var(--on-surf-dim)' }}>{module.estimated_hours}h</span>
    </div>
    <p style={{ color: 'var(--on-surf-1)' }}>{module.summary}</p>

    {module.outcomes.length > 0 && (
      <div style={{ marginBottom: 'var(--s-3)' }}>
        <strong style={{ color: 'var(--on-surf-1)' }}>Module outcomes:</strong>
        <ul style={{ marginTop: 'var(--s-1)' }}>
          {module.outcomes.map((o) => (
            <li key={o.id}>
              {o.text}
              <BloomBadge level={o.bloom_level} />
            </li>
          ))}
        </ul>
      </div>
    )}

    <div className="outline__lessons">
      {module.lessons.map((lesson) => (
        <LessonBlock
          key={lesson.id}
          lesson={lesson}
          lookup={lookup}
          refMap={refMap}
        />
      ))}
    </div>
  </section>
)

export const OutlineRenderer = ({ outline }: OutlineRendererProps) => {
  // refs for scroll-into-view on prerequisite click
  const refMap = useRef<Record<string, HTMLElement | null>>({})

  const lookup = useMemo<PrereqLookup>(() => {
    const map: PrereqLookup = {}
    for (const m of outline.modules) {
      map[m.id] = { title: m.title, ref: { current: null } }
      for (const l of m.lessons) {
        map[l.id] = { title: l.title, ref: { current: null } }
      }
    }
    return map
  }, [outline])

  return (
    <div className="outline">
      <header className="outline__hero">
        <h1 style={{ margin: 0 }}>{outline.title}</h1>
        <p style={{ color: 'var(--on-surf-1)' }}>{outline.summary}</p>
        <div style={{ color: 'var(--on-surf-dim)', fontSize: 'var(--fs-body-sm)' }}>
          <span>Audience: {outline.target_audience}</span>
          <span style={{ marginLeft: 'var(--s-3)' }}>
            Total: {outline.total_hours} hours
          </span>
        </div>
        {outline.course_outcomes.length > 0 && (
          <div style={{ marginTop: 'var(--s-3)' }}>
            <strong>Course outcomes:</strong>
            <ul style={{ marginTop: 'var(--s-1)' }}>
              {outline.course_outcomes.map((o) => (
                <li key={o.id}>
                  {o.text}
                  <BloomBadge level={o.bloom_level} />
                </li>
              ))}
            </ul>
          </div>
        )}
      </header>

      {outline.modules.map((module) => (
        <ModuleBlock
          key={module.id}
          module={module}
          lookup={lookup}
          refMap={refMap}
        />
      ))}
    </div>
  )
}
