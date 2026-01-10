import { AxiosError } from 'axios'

/**
 * Extracts a user-friendly error message from various error types.
 * Handles Axios errors, standard Error objects, and unknown error types.
 */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    // Try to get the error message from the API response
    const responseMessage = error.response?.data?.detail || error.response?.data?.message
    if (responseMessage) {
      return responseMessage
    }
    // Fall back to Axios error message
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return fallback
}
