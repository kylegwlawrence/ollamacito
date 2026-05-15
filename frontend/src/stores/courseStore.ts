/**
 * Courses store. Mirrors projectsStore.ts.
 *
 * - `courses`: lightweight list for the sidebar + index page
 * - `coursesById`: full Course rows keyed by id (populated on demand)
 *
 * Auto-load with `useCoursesAutoLoad()` from App.tsx.
 */
import { useEffect } from 'react'
import { create } from 'zustand'
import { courseApi } from '@/services/courseApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type {
  Course,
  CourseCreate,
  CourseListItem,
  CourseUpdate,
} from '@/types'

interface CourseStore {
  courses: CourseListItem[]
  coursesById: Record<string, Course>
  loading: boolean
  loaded: boolean
  error: string | null

  loadList: () => Promise<void>
  loadOne: (id: string) => Promise<Course | null>
  createCourse: (body: CourseCreate) => Promise<Course | null>
  updateCourse: (id: string, body: CourseUpdate) => Promise<Course | null>
  removeCourse: (id: string) => Promise<void>
  upsertFromFullCourse: (course: Course) => void
}

const _toListItem = (c: Course): CourseListItem => ({
  id: c.id,
  title: c.title,
  project_id: c.project_id,
  status: c.status,
  total_hours: c.outline?.total_hours ?? null,
  topic: c.input?.topic ?? c.title,
  created_at: c.created_at,
  updated_at: c.updated_at,
  generated_at: c.generated_at,
})

export const useCourseStore = create<CourseStore>((set, _get) => ({
  courses: [],
  coursesById: {},
  loading: true,
  loaded: false,
  error: null,

  loadList: async () => {
    try {
      set({ loading: true, error: null })
      const list = await courseApi.list()
      set({ courses: list, loaded: true })
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to load courses') })
    } finally {
      set({ loading: false })
    }
  },

  loadOne: async (id) => {
    try {
      const course = await courseApi.get(id)
      set((s) => ({
        coursesById: { ...s.coursesById, [course.id]: course },
        courses: s.courses.some((c) => c.id === course.id)
          ? s.courses.map((c) => (c.id === course.id ? _toListItem(course) : c))
          : [_toListItem(course), ...s.courses],
      }))
      return course
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to load course') })
      return null
    }
  },

  createCourse: async (body) => {
    try {
      const course = await courseApi.create(body)
      set((s) => ({
        coursesById: { ...s.coursesById, [course.id]: course },
        courses: [_toListItem(course), ...s.courses],
      }))
      return course
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to create course') })
      return null
    }
  },

  updateCourse: async (id, body) => {
    try {
      const course = await courseApi.update(id, body)
      set((s) => ({
        coursesById: { ...s.coursesById, [course.id]: course },
        courses: s.courses.map((c) =>
          c.id === id ? _toListItem(course) : c
        ),
      }))
      return course
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to update course') })
      return null
    }
  },

  removeCourse: async (id) => {
    try {
      await courseApi.remove(id)
      set((s) => {
        const next = { ...s.coursesById }
        delete next[id]
        return {
          coursesById: next,
          courses: s.courses.filter((c) => c.id !== id),
        }
      })
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to delete course') })
      throw err
    }
  },

  upsertFromFullCourse: (course) =>
    set((s) => ({
      coursesById: { ...s.coursesById, [course.id]: course },
      courses: s.courses.some((c) => c.id === course.id)
        ? s.courses.map((c) =>
            c.id === course.id ? _toListItem(course) : c
          )
        : [_toListItem(course), ...s.courses],
    })),
}))

/** Mount once near the top of the tree to fetch courses on first paint. */
export const useCoursesAutoLoad = (): void => {
  const loaded = useCourseStore((s) => s.loaded)
  const loadList = useCourseStore((s) => s.loadList)
  useEffect(() => {
    if (!loaded) {
      loadList()
    }
  }, [loaded, loadList])
}
