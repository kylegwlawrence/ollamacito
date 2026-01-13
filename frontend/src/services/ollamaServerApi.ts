/**
 * API service for Ollama server management
 */
import type {
  OllamaServer,
  OllamaServerCreate,
  OllamaServerUpdate,
  OllamaServerListResponse,
} from '../types/ollama_server'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const API_PREFIX = '/api/v1'

/**
 * Get list of all Ollama servers
 */
export async function listServers(): Promise<OllamaServer[]> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/ollama-servers`)
  if (!response.ok) {
    throw new Error(`Failed to list servers: ${response.statusText}`)
  }
  const data: OllamaServerListResponse = await response.json()
  return data.servers
}

/**
 * Get a specific Ollama server by ID
 */
export async function getServer(serverId: string): Promise<OllamaServer> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/ollama-servers/${serverId}`)
  if (!response.ok) {
    throw new Error(`Failed to get server: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Create a new Ollama server
 */
export async function createServer(data: OllamaServerCreate): Promise<OllamaServer> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/ollama-servers`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `Failed to create server: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Update an existing Ollama server
 */
export async function updateServer(
  serverId: string,
  data: OllamaServerUpdate
): Promise<OllamaServer> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/ollama-servers/${serverId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `Failed to update server: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Delete an Ollama server
 */
export async function deleteServer(serverId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/ollama-servers/${serverId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `Failed to delete server: ${response.statusText}`)
  }
}

/**
 * Manually trigger health check for a specific server
 */
export async function checkServerHealth(serverId: string): Promise<OllamaServer> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/ollama-servers/${serverId}/check-health`,
    {
      method: 'POST',
    }
  )
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `Failed to check server health: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Get list of models available on a specific server
 */
export async function getServerModels(serverId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/ollama-servers/${serverId}/models`)
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `Failed to get server models: ${response.statusText}`)
  }
  const data = await response.json()
  return data.models || []
}
