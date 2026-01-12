import api from './api'
import type {
  ProjectListResponse,
  ProjectWithDetails,
  ProjectCreate,
  ProjectResponse,
  ProjectUpdate,
  ChatListResponse,
  ProjectFile,
  ProjectFileCreate,
} from '@/types'

export const projectApi = {
  list: async (
    page = 1,
    pageSize = 20,
    includeArchived = false
  ): Promise<ProjectListResponse> => {
    const { data } = await api.get('/projects', {
      params: { page, page_size: pageSize, include_archived: includeArchived },
    })
    return data
  },

  get: async (projectId: string): Promise<ProjectWithDetails> => {
    const { data } = await api.get(`/projects/${projectId}`)
    return data
  },

  create: async (projectData: ProjectCreate): Promise<ProjectResponse> => {
    const { data } = await api.post('/projects', projectData)
    return data
  },

  update: async (
    projectId: string,
    projectData: ProjectUpdate
  ): Promise<ProjectResponse> => {
    const { data } = await api.patch(`/projects/${projectId}`, projectData)
    return data
  },

  delete: async (projectId: string): Promise<void> => {
    await api.delete(`/projects/${projectId}`)
  },

  getChats: async (
    projectId: string,
    page = 1,
    pageSize = 20
  ): Promise<ChatListResponse> => {
    const { data } = await api.get(`/projects/${projectId}/chats`, {
      params: { page, page_size: pageSize },
    })
    return data
  },

  // File management endpoints
  uploadFile: async (
    projectId: string,
    fileData: ProjectFileCreate
  ): Promise<ProjectFile> => {
    const { data } = await api.post(`/projects/${projectId}/files`, fileData)
    return data
  },

  getFile: async (projectId: string, fileId: string): Promise<ProjectFile> => {
    const { data } = await api.get(`/projects/${projectId}/files/${fileId}`)
    return data
  },

  deleteFile: async (projectId: string, fileId: string): Promise<void> => {
    await api.delete(`/projects/${projectId}/files/${fileId}`)
  },
}
