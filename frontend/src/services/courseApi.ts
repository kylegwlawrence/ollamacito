import api from './api'
import type {
  Course,
  CourseCreate,
  CourseListItem,
  CourseUpdate,
} from '@/types'

export const courseApi = {
  list: async (): Promise<CourseListItem[]> => {
    const { data } = await api.get('/courses')
    return data
  },

  get: async (courseId: string): Promise<Course> => {
    const { data } = await api.get(`/courses/${courseId}`)
    return data
  },

  create: async (body: CourseCreate): Promise<Course> => {
    const { data } = await api.post('/courses', body)
    return data
  },

  update: async (courseId: string, body: CourseUpdate): Promise<Course> => {
    const { data } = await api.patch(`/courses/${courseId}`, body)
    return data
  },

  remove: async (courseId: string): Promise<void> => {
    await api.delete(`/courses/${courseId}`)
  },

  getMarkdown: async (courseId: string): Promise<string> => {
    const { data } = await api.get(`/courses/${courseId}/markdown`, {
      responseType: 'text',
      transformResponse: [(d) => d],
    })
    return data
  },
}
