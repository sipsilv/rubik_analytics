/**
 * Utility functions for handling API errors
 */

/**
 * Checks if an error is a network error (no response from server)
 */
export function isNetworkError(error: any): boolean {
  if (!error) return false
  
  // Axios network errors don't have a response property
  if (error.code === 'ECONNREFUSED' || 
      error.code === 'ERR_NETWORK' || 
      error.code === 'ETIMEDOUT' ||
      error.code === 'ENOTFOUND' ||
      error.message?.includes('Network Error') ||
      error.message?.includes('network error') ||
      (error.response === undefined && error.request !== undefined)) {
    return true
  }
  
  return false
}

/**
 * Safely extracts an error message from an API error response
 * Handles both string errors and Pydantic validation error objects
 * Also handles network errors with helpful messages
 * 
 * IMPORTANT: Only shows "Backend server not reachable" when there's NO HTTP response.
 * For HTTP errors (401, 403, 404, 5xx), shows specific error messages.
 */
export function getErrorMessage(error: any, fallback: string = 'An error occurred'): string {
  // If error is already a string, return it
  if (typeof error === 'string') {
    return error
  }

  // If error is null or undefined, return fallback
  if (error == null) {
    return fallback
  }

  // CRITICAL: Check if there's an HTTP response first
  // If error.response exists, it means the backend IS reachable
  // Only show "Backend server not reachable" when error.response is undefined
  if (error.response) {
    // Backend IS reachable - handle HTTP status codes
    const status = error.response.status
    const detail = error.response.data?.detail

    // Handle specific HTTP status codes
    if (status === 401) {
      // Check if it's a login error or session error
      if (detail && typeof detail === 'string' && (
        detail.includes('identifier') || 
        detail.includes('password') || 
        detail.includes('token') ||
        detail.includes('authentication')
      )) {
        return detail // Show the actual error message
      }
      return 'Session expired. Please login again.'
    }
    if (status === 403) {
      // For 403 errors, show the detail message if available (e.g., "User account is inactive")
      if (detail && typeof detail === 'string') {
        return detail
      }
      return 'You do not have permission to perform this action.'
    }
    if (status === 404) {
      return 'API endpoint not found. Please check the endpoint URL.'
    }
    if (status >= 500) {
      return 'Server error. Please check backend logs for details.'
    }

    // For other HTTP errors (400, etc.), try to extract the detail message
  if (typeof detail === 'string') {
    return detail
  }

  // If detail is an array (Pydantic validation errors), format them
  if (Array.isArray(detail)) {
    return detail
      .map((err: any) => {
        if (typeof err === 'string') {
          return err
        }
        if (err && typeof err === 'object') {
          if (err.msg) {
            const loc = err.loc && Array.isArray(err.loc) ? err.loc.join('.') : ''
            return loc ? `${loc}: ${err.msg}` : err.msg
          }
          if (err.type && err.msg) {
            const loc = err.loc && Array.isArray(err.loc) ? err.loc.join('.') : ''
            return loc ? `${loc}: ${err.msg}` : err.msg
          }
        }
        return JSON.stringify(err)
      })
      .join(', ')
  }

  // If detail is an object, try to extract message
  if (detail && typeof detail === 'object') {
    if (detail.msg) {
      const loc = detail.loc && Array.isArray(detail.loc) ? detail.loc.join('.') : ''
      return loc ? `${loc}: ${detail.msg}` : detail.msg
    }
    if (detail.message) {
      return detail.message
    }
    return JSON.stringify(detail)
  }

    // Fallback for HTTP errors
    return `Request failed with status ${status}. ${detail || error.response.statusText || ''}`
  }

  // NO HTTP RESPONSE - Backend is truly unreachable
  // Check for network errors (no response from server)
  if (isNetworkError(error)) {
    return `Unable to connect to server. Please ensure the backend is running. Check the troubleshooting guide for help.`
  }

  // Try error.message as fallback
  if (error?.message && typeof error.message === 'string') {
    return error.message
  }

  // Fallback
  return fallback
}
