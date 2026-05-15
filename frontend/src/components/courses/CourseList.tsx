import { useNavigate } from 'react-router-dom'
import { useCourseStore } from '@/stores/courseStore'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ViewHeader } from '../common/ViewHeader'
import type { CourseListItem } from '@/types'
import './courses.css'

const StatusBadge = ({ status }: { status: CourseListItem['status'] }) => (
  <span className={`course-status-badge course-status-badge--${status}`}>
    {status.replace('_', ' ')}
  </span>
)

const CourseCard = ({
  course,
  onClick,
}: {
  course: CourseListItem
  onClick: () => void
}) => (
  <div
    className="course-card"
    role="button"
    tabIndex={0}
    onClick={onClick}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') onClick()
    }}
  >
    <div>
      <h3 className="course-card__title">{course.title}</h3>
      <div className="course-card__meta">
        <span>Topic: {course.topic}</span>
        {course.total_hours != null && (
          <span>{course.total_hours.toFixed(0)} hours</span>
        )}
      </div>
    </div>
    <StatusBadge status={course.status} />
  </div>
)

export const CourseList = () => {
  const navigate = useNavigate()
  const courses = useCourseStore((s) => s.courses)
  const loading = useCourseStore((s) => s.loading)
  const loaded = useCourseStore((s) => s.loaded)

  return (
    <>
      <ViewHeader
        title="Courses"
        actions={
          <Button
            onClick={() => navigate('/courses/new')}
            variant="primary"
            size="sm"
            leadingIcon="add"
          >
            New Course
          </Button>
        }
      />
      <div className="course-list">
        {loading && !loaded && <LoadingSpinner />}
        {loaded && courses.length === 0 && (
          <div className="course-list__empty">
            <p>No courses yet. Click "New Course" to generate one.</p>
          </div>
        )}
        {courses.map((c) => (
          <CourseCard
            key={c.id}
            course={c}
            onClick={() => navigate(`/courses/${c.id}`)}
          />
        ))}
      </div>
    </>
  )
}
