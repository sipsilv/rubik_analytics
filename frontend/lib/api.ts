import axios from 'axios'
import Cookies from 'js-cookie'

const API_URL = process.env.NEXT_PUBLIC_API_URL

if(!API_URL){
	throw new Error("api url is not found");
}

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout for network requests (increased for better idle connection handling)
  withCredentials: true, // Include credentials (cookies) in requests
})

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = Cookies.get('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  // If data is FormData, don't set Content-Type - let browser set it with boundary
  // This is critical for file uploads - FormData needs multipart/form-data with boundary
  if (config.data instanceof FormData) {
    // Remove Content-Type header completely - browser will set it with proper boundary
    // Axios will automatically set the correct Content-Type with boundary for FormData
    delete config.headers['Content-Type']
    // Also ensure it's not in common headers
    if (config.headers && config.headers.common) {
      delete config.headers.common['Content-Type']
    }
  }

  return config
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Don't redirect if we're already on login page (to handle OTP flow)
      // or if it's the specific OTP required error
      const isOtpError = error.response.data?.detail?.includes('OTP')
      const isLoginPage = typeof window !== 'undefined' && window.location.pathname === '/login'

      if (!isOtpError && !isLoginPage) {
        Cookies.remove('auth_token')
        Cookies.remove('user')
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
    }

    // Handle network errors (backend unreachable)
    if (!error.response) {
      // Check for various network error conditions
      const isNetworkError =
        error.code === 'ECONNREFUSED' ||
        error.code === 'ERR_NETWORK' ||
        error.code === 'ENOTFOUND' ||
        error.message?.includes('Network Error') ||
        error.message?.includes('network error') ||
        error.message?.includes('Failed to fetch') ||
        error.message?.includes('fetch failed') ||
        (error.request && !error.response)

      if (isNetworkError) {
        error.isNetworkError = true
        error.backendUnreachable = true
        error.userMessage = `Unable to connect to backend server at ${API_URL}. Please ensure the backend is running.`
      } else if (error.code === 'ETIMEDOUT' || error.message?.includes('timeout')) {
        error.isTimeoutError = true
        error.userMessage = 'Request timed out. The backend server is taking too long to respond.'
      }
    }

    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authAPI = {
  login: async (identifier: string, password: string, otp?: string) => {
    const response = await api.post('/auth/login', { identifier, password, otp })
    return response.data
  },
  logout: async () => {
    await api.post('/auth/logout')
    Cookies.remove('auth_token')
    Cookies.remove('user')
  },
  forgotPassword: async (email: string) => {
    const response = await api.post('/auth/forgot-password', { email })
    return response.data
  },
  resetPassword: async (identifier: string, otp: string, newPassword: string) => {
    const response = await api.post('/auth/reset-password', {
      identifier,
      otp,
      new_password: newPassword
    })
    return response.data
  },
  refreshToken: async () => {
    const response = await api.post('/auth/refresh')
    return response.data
  },
  requestAccess: async (data: any) => {
    // Remove requested_role and any other unsupported fields - backend will auto-assign "user"
    const { requested_role, ...requestData } = data

    // Ensure only supported fields are sent
    const payload: {
      name: string
      email?: string | null
      mobile: string
      company?: string | null
      reason: string
    } = {
      name: requestData.name,
      mobile: requestData.mobile,
      reason: requestData.reason,
    }

    // Add optional fields only if provided
    if (requestData.email !== undefined) {
      payload.email = requestData.email
    }
    if (requestData.company !== undefined) {
      payload.company = requestData.company
    }

    const response = await api.post('/admin/requests', payload)
    return response.data
  },
}

// User API
export const userAPI = {
  getCurrentUser: async () => {
    const response = await api.get('/users/me')
    return response.data
  },
  updateProfile: async (data: any) => {
    const response = await api.put('/users/me', data)
    return response.data
  },
  updateTheme: async (theme: 'dark' | 'light') => {
    const response = await api.put('/users/me', { theme_preference: theme })
    return response.data
  },
  changePassword: async (currentPassword: string, newPassword: string, confirmPassword: string) => {
    const response = await api.post('/users/me/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword
    })
    return response.data
  },
  createFeedback: async (subject: string, message: string) => {
    const response = await api.post('/users/feedback', {
      subject,
      message
    })
    return response.data
  },
  createFeatureRequest: async (description: string, context?: { page?: string; module?: string; issue_type?: string }) => {
    const response = await api.post('/users/feature-requests', {
      description,
      context
    })
    return response.data
  },
  getMyFeatureRequests: async () => {
    const response = await api.get('/users/feature-requests')
    return response.data
  },
  pingActivity: async () => {
    const response = await api.post('/users/me/ping')
    return response.data
  },
  disconnectTelegram: async () => {
    const response = await api.delete('/telegram/disconnect')
    return response.data
  },
}

// Admin API
export const adminAPI = {
  getUsers: async (search?: string) => {
    const params = search ? { search } : {}
    const response = await api.get('/admin/users', { params })
    return response.data
  },
  getUser: async (id: string) => {
    const response = await api.get(`/admin/users/${id}`)
    return response.data
  },
  createUser: async (data: any) => {
    const response = await api.post('/admin/users', data)
    return response.data
  },
  updateUser: async (id: string, data: any) => {
    const response = await api.put(`/admin/users/${id}`, data)
    return response.data
  },
  changeUserPassword: async (id: string, password: string) => {
    const response = await api.patch(`/admin/users/${id}/change-password`, { password })
    return response.data
  },
  deleteUser: async (id: string) => {
    const response = await api.delete(`/admin/users/${id}`)
    return response.data
  },
  updateUserStatus: async (id: string, status: string, reason?: string) => {
    const response = await api.patch(`/admin/users/${id}/status`, { status, reason })
    return response.data
  },
  sendMessage: (userId: string, message: string) => {
    const response = api.post(`/admin/users/${userId}/message`, { message })
    return response.then(res => res.data)
  },
  getMessages: (userId: string, limit?: number) => {
    const params = limit ? { limit } : {}
    const response = api.get(`/admin/users/${userId}/messages`, { params })
    return response.then(res => res.data)
  },
  toggleUserStatus: async (id: string) => {
    // Get current user first to check status, then toggle
    const user = await adminAPI.getUser(id)
    const newStatus = user.is_active ? 'INACTIVE' : 'ACTIVE'
    const response = await api.patch(`/admin/users/${id}/status`, { status: newStatus })
    return response.data
  },
  promoteToSuperAdmin: async (id: string) => {
    const response = await api.patch(`/admin/users/${id}/promote-to-super-admin`)
    return response.data
  },
  demoteFromSuperAdmin: async (id: string) => {
    const response = await api.patch(`/admin/users/${id}/demote-from-super-admin`)
    return response.data
  },
  getRequests: async (status?: string) => {
    const params = status ? { status } : {}
    const response = await api.get('/admin/requests', { params })
    return response.data
  },
  approveRequest: async (id: string) => {
    const response = await api.post(`/admin/requests/${id}/approve`)
    return response.data
  },
  rejectRequest: async (id: string, reason?: string) => {
    const response = await api.post(`/admin/requests/${id}/reject`, reason ? { reason } : {})
    return response.data
  },
  getFeedback: async (search?: string, status?: string) => {
    const params: any = {}
    if (search) params.search = search
    if (status) params.status = status
    const response = await api.get('/admin/feedback', { params })
    return response.data
  },
  updateFeedbackStatus: async (id: string, status: string) => {
    const response = await api.patch(`/admin/feedback/${id}`, null, {
      params: { status }
    })
    return response.data
  },
  getConnections: async (category?: string) => {
    const params = category ? { category } : {}
    const response = await api.get('/admin/connections', { params })
    return response.data
  },
  getConnection: async (id: string) => {
    const response = await api.get(`/admin/connections/${id}`)
    return response.data
  },
  createConnection: async (data: any) => {
    const response = await api.post('/admin/connections', data)
    return response.data
  },
  updateConnection: async (id: string, data: any) => {
    const response = await api.put(`/admin/connections/${id}`, data)
    return response.data
  },
  deleteConnection: async (id: string) => {
    const response = await api.delete(`/admin/connections/${id}`)
    return response.data
  },
  testConnection: async (id: string) => {
    const response = await api.post(`/admin/connections/${id}/test`)
    return response.data
  },
  getAiModels: async (provider: string, baseUrl?: string) => {
    const params: any = { provider }
    if (baseUrl) params.base_url = baseUrl
    const response = await api.get('/admin/connections/ai/models', { params })
    return response.data
  },
  getProcessorData: async (type: string) => {
    // Assuming `api` is the correct client to use, similar to other methods.
    // The path `/processors/data/${type}` is inferred from the `getProcessorStats` method's path `/processors/stats`.
    const response = await api.get(`/processors/data/${type}`)
    return response.data
  },
  toggleConnection: async (id: string) => {
    const response = await api.post(`/admin/connections/${id}/toggle`)
    return response.data
  },
  generateToken: async (id: string) => {
    const response = await api.post(`/admin/connections/${id}/token/generate`)
    return response.data
  },
  getTokenStatus: async (id: string) => {
    const response = await api.get(`/admin/connections/${id}/token/status`)
    return response.data
  },
  refreshToken: async (id: string) => {
    const response = await api.post(`/admin/connections/${id}/token/refresh`)
    return response.data
  },
  getTrueDataToken: async (connectionId?: number) => {
    const params = connectionId ? { connection_id: connectionId } : {}
    const response = await api.get('/admin/connections/truedata/token', { params })
    return response.data
  },
  getActiveConnections: async () => {
    const response = await api.get('/admin/connections/active')
    return response.data
  },
  getSymbols: async () => {
    const response = await api.get('/admin/reference-data/symbols')
    return response.data
  },
  getIndicators: async () => {
    const response = await api.get('/admin/reference-data/indicators')
    return response.data
  },
  getFeatureRequests: async (status?: string, search?: string) => {
    const params: any = {}
    if (status) params.status = status
    if (search) params.search = search
    const response = await api.get('/admin/feature-requests', { params })
    return response.data
  },
  getFeatureRequest: async (id: string) => {
    const response = await api.get(`/admin/feature-requests/${id}`)
    return response.data
  },
  updateFeatureRequest: async (id: string, data: { status?: string; admin_note?: string }) => {
    const response = await api.put(`/admin/feature-requests/${id}`, data)
    return response.data
  },
  getProcessorStats: async () => {
    const response = await api.get('/processors/stats')
    return response.data
  },
  getAIEnrichmentConfig: async () => {
    const response = await api.get('/admin/ai-enrichment-config')
    return response.data
  },
  createAIEnrichmentConfig: async (data: any) => {
    const response = await api.post('/admin/ai-enrichment-config', data)
    return response.data
  },
  updateAIEnrichmentConfig: async (id: string, data: any) => {
    const response = await api.put(`/admin/ai-enrichment-config/${id}`, data)
    return response.data
  },
}



// Telegram API
export const telegramAPI = {
  requestOtp: async (apiId: string, apiHash: string, phone: string) => {
    const response = await api.post('/telegram/request-otp', {
      api_id: parseInt(apiId),
      api_hash: apiHash,
      phone
    })
    return response.data
  },
  verifyOtp: async (apiId: string, apiHash: string, phone: string, code: string, phoneCodeHash: string, sessionString: string, password?: string) => {
    const response = await api.post('/telegram/verify-otp', {
      api_id: parseInt(apiId),
      api_hash: apiHash,
      phone,
      code,
      phone_code_hash: phoneCodeHash,
      session_string: sessionString,
      password
    })
    return response.data
    return response.data
  }
}

// Telegram Channels API
export const telegramChannelsAPI = {
  discoverChannels: async (connectionId: number) => {
    const response = await api.get(`/telegram-channels/discover/${connectionId}`)
    return response.data
  },
  registerChannels: async (connectionId: number, channels: any[]) => {
    const response = await api.post(`/telegram-channels/${connectionId}/register`, { channels })
    return response.data
  },
  getChannels: async (connectionId: number) => {
    const response = await api.get(`/telegram-channels/list/${connectionId}`)
    return response.data
  },
  toggleChannel: async (channelId: number, isEnabled: boolean) => {
    const response = await api.patch(`/telegram-channels/${channelId}/toggle`, { is_enabled: isEnabled })
    return response.data
  },
  searchChannels: async (connectionId: number, query: string) => {
    const response = await api.get(`/telegram-channels/search/${connectionId}`, { params: { q: query } })
    return response.data
  },
  deleteChannel: async (channelId: number) => {
    const response = await api.delete(`/telegram-channels/${channelId}`)
    return response.data
  }
}

// Symbols API
export const symbolsAPI = {
  getStats: async () => {
    const response = await api.get('/admin/symbols/stats')
    return response.data
  },
  getSymbols: async (params?: { search?: string; exchange?: string; status?: string; expiry?: string; sort_by?: string; page_size?: number; page?: number }) => {
    const response = await api.get('/admin/symbols', { params })
    return response.data
  },
  getUploadLogs: async (limit?: number, page?: number) => {
    try {
      const params: any = {}
      if (limit) params.limit = limit
      if (page) params.page = page

      console.log('[API] Fetching upload logs:', { limit, page, url: '/admin/symbols/upload/logs' })
      // Use longer timeout for upload logs to handle idle connections
      const response = await api.get('/admin/symbols/upload/logs', {
        params,
        timeout: 30000 // 30 seconds for history queries
      })

      // Backend returns data in nested structure: { logs: [], pagination: { ... } }
      const data = response.data || {}
      const pagination = data.pagination || {}
      const logs = data.logs || []

      console.log('[API] Upload logs response:', {
        status: response.status,
        has_data: !!data,
        logs_count: logs.length,
        total: pagination.total || 0,
        page: pagination.page || 1,
        total_pages: pagination.total_pages || 1,
        has_pagination_object: !!pagination
      })

      // CRITICAL: Ensure response always has logs array, even if empty
      return {
        logs: logs,
        total: pagination.total || 0,
        page: pagination.page || 1,
        page_size: pagination.page_size || limit || 10,
        total_pages: pagination.total_pages || 1
      }
    } catch (error: any) {
      // On error, log detailed error information
      console.error('[API] Failed to fetch upload logs:', {
        message: error?.message,
        response: error?.response?.data,
        status: error?.response?.status,
        url: error?.config?.url,
        method: error?.config?.method,
        code: error?.code,
        isTimeout: error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')
      })

      // Retry once on timeout or network error (prevent infinite recursion)
      if ((error?.code === 'ECONNABORTED' || error?.message?.includes('timeout') || error?.code === 'ERR_NETWORK') && !error._retried) {
        console.log('[API] Retrying upload logs fetch after timeout/network error...')
        error._retried = true
        // Wait a bit before retry
        await new Promise(resolve => setTimeout(resolve, 1000))
        try {
          const retryResponse = await api.get('/admin/symbols/upload/logs', {
            params: { limit, page },
            timeout: 30000
          })
          const retryData = retryResponse.data || {}
          const retryPagination = retryData.pagination || {}
          return {
            logs: retryData.logs || [],
            total: retryPagination.total || 0,
            page: retryPagination.page || 1,
            page_size: retryPagination.page_size || limit || 10,
            total_pages: retryPagination.total_pages || 1
          }
        } catch (retryError: any) {
          console.error('[API] Retry also failed:', retryError?.message)
        }
      }

      return {
        logs: [],
        total: 0,
        page: page || 1,
        page_size: limit || 10,
        total_pages: 1
      }
    }
  },
  getUploadStatus: async (jobIdOrLogId: string) => {
    const response = await api.get(`/admin/symbols/upload/status/${jobIdOrLogId}`)
    return response.data
  },
  cancelUpload: async (jobIdOrLogId: string) => {
    const response = await api.post(`/admin/symbols/upload/${jobIdOrLogId}/cancel`)
    return response.data
  },
  reloadSeriesLookup: async (force: boolean = false) => {
    const response = await api.post(`/admin/symbols/series-lookup/reload?force=${force}`)
    return response.data
  },
  deleteAllSymbols: async () => {
    const response = await api.delete('/admin/symbols/delete_all')
    return response.data
  },
  uploadManual: async (file: File | Blob, scriptId?: number) => {
    // Validate that file is actually a File/Blob object
    if (!file || (typeof file !== 'object')) {
      throw new Error('Invalid file object. Expected File or Blob instance.')
    }

    // Check if it's a File, Blob, or File-like object
    const isFile = file instanceof File
    const isBlob = file instanceof Blob
    const fileObj = file as any
    const hasFileProperties = 'name' in fileObj && 'size' in fileObj && 'type' in fileObj

    if (!isFile && !isBlob && !hasFileProperties) {
      console.error('File validation failed:', {
        isFile,
        isBlob,
        hasFileProperties,
        fileType: typeof file,
        constructor: fileObj.constructor?.name,
        keys: Object.keys(fileObj)
      })
      throw new Error('Invalid file object. Expected File or Blob instance.')
    }

    const formData = new FormData()
    // Ensure file is appended correctly - use the file object directly
    try {
      if (isFile) {
        formData.append('file', file, (file as File).name)
      } else if (isBlob) {
        // For Blob, use the name property if available (technically File extends Blob), otherwise use default
        const blobName = (file as any).name || 'upload.csv'
        formData.append('file', file, blobName)
      } else {
        // Last resort: try to append as-is
        formData.append('file', file as any, (file as any).name || 'upload.csv')
      }
    } catch (appendError) {
      console.error('Error appending file to FormData:', appendError)
      throw new Error(`Failed to prepare file for upload: ${appendError}`)
    }

    if (scriptId) {
      formData.append('script_id', scriptId.toString())
    }

    // Create a separate axios instance for file uploads without default Content-Type
    const uploadApi = axios.create({
      baseURL: `${API_URL}/api/v1`,
      timeout: 30000, // Longer timeout for file uploads
    })

    // Add auth token
    const token = Cookies.get('auth_token')
    if (token) {
      uploadApi.defaults.headers.common['Authorization'] = `Bearer ${token}`
    }

    // Don't set Content-Type - let browser set it with boundary for FormData
    const response = await uploadApi.post('/admin/symbols/upload/manual', formData, {
      headers: {
        // Explicitly don't set Content-Type - browser will set multipart/form-data with boundary
      }
    })
    return response.data
  },
  uploadAuto: async (data: {
    url: string
    source_type?: string
    method?: string
    headers?: Record<string, string>
    auth_type?: string
    auth_value?: string
    auth_token?: string
    file_handling_mode?: string
    file_type?: string
    script_id?: number
  }) => {
    const response = await api.post('/admin/symbols/upload/auto', data)
    return response.data
  },
  confirmUpload: async (previewId: string) => {
    // Use longer timeout for large file uploads (5 minutes)
    const confirmApi = axios.create({
      baseURL: `${API_URL}/api/v1`,
      timeout: 300000, // 5 minutes for large file processing
    })

    const token = Cookies.get('auth_token')
    if (token) {
      confirmApi.defaults.headers.common['Authorization'] = `Bearer ${token}`
    }

    const response = await confirmApi.post('/admin/symbols/upload/confirm', {
      preview_id: previewId
    })
    return response.data
  },

  getTemplate: async () => {
    const response = await api.get('/admin/symbols/template')
    return response.data
  },
  // Health check
  checkHealth: async () => {
    try {
      // Health check uses base URL directly (not /api/v1)
      const response = await axios.get(`${API_URL}/health`, {
        timeout: 5000,
        withCredentials: true
      })
      return { healthy: true, data: response.data }
    } catch (error: any) {
      // Only mark as unhealthy if there's NO HTTP response (truly unreachable)
      const isUnreachable = !error.response && (
        error.code === 'ECONNREFUSED' ||
        error.code === 'ERR_NETWORK' ||
        error.code === 'ENOTFOUND' ||
        error.message?.includes('Network Error') ||
        error.message?.includes('Failed to fetch')
      )

      return {
        healthy: !isUnreachable, // Healthy if we got ANY HTTP response (even 500)
        error: isUnreachable ? 'Backend server is not reachable' : error.message
      }
    }
  },
  // V2: Scripts & Bulk
  getScripts: async () => {
    const response = await api.get('/admin/symbols/scripts')
    return response.data
  },
  createScript: async (data: any) => {
    const response = await api.post('/admin/symbols/scripts', data)
    return response.data
  },
  updateScript: async (id: number, data: any) => {
    const response = await api.put(`/admin/symbols/scripts/${id}`, data)
    return response.data
  },
  deleteScript: async (id: number) => {
    try {
      const response = await api.delete(`/admin/symbols/scripts/${id}`)
      console.log('Delete script API response:', response.data)
      return response.data
    } catch (error: any) {
      console.error('Delete script API error:', error)
      // Re-throw to let caller handle it
      throw error
    }
  },
  toggleSymbolStatus: async (id: number, status: string) => {
    const response = await api.patch('/admin/symbols/status/bulk', { ids: [id], status })
    return response.data
  },
  testScript: async (id: number) => {
    const response = await api.post(`/admin/symbols/scripts/${id}/test`)
    return response.data
  },
  bulkDelete: async (ids: number[], hardDelete: boolean = false) => {
    const response = await api.post('/admin/symbols/delete/bulk', { ids, hard_delete: hardDelete })
    return response.data
  },
  // Scheduled Ingestion
  getSchedulers: async () => {
    try {
      console.log('[API] Fetching schedulers from:', '/admin/symbols/schedulers')
      const response = await api.get('/admin/symbols/schedulers')
      console.log('[API] Schedulers response:', {
        status: response.status,
        has_data: !!response.data,
        is_array: Array.isArray(response.data),
        count: Array.isArray(response.data) ? response.data.length : 0,
        data: response.data
      })
      return response.data || []
    } catch (error: any) {
      console.error('[API] Failed to fetch schedulers:', {
        message: error?.message,
        response: error?.response?.data,
        status: error?.response?.status,
        url: error?.config?.url
      })
      throw error
    }
  },
  getScheduler: async (id: number) => {
    const response = await api.get(`/admin/symbols/schedulers/${id}`)
    return response.data
  },
  createScheduler: async (data: any) => {
    const response = await api.post('/admin/symbols/schedulers', data)
    return response.data
  },
  updateScheduler: async (id: number, data: any) => {
    const response = await api.put(`/admin/symbols/schedulers/${id}`, data)
    return response.data
  },
  deleteScheduler: async (id: number) => {
    const response = await api.delete(`/admin/symbols/schedulers/${id}`)
    return response.data
  },
  triggerScheduler: async (id: number) => {
    const response = await api.post(`/admin/symbols/schedulers/${id}/trigger`)
    return response.data
  },
  runSchedulerNow: async (id: number) => {
    console.log('[API] runSchedulerNow called with id:', id)
    console.log('[API] Full URL will be:', `${api.defaults.baseURL}/admin/symbols/schedulers/${id}/run-now`)
    try {
      const response = await api.post(`/admin/symbols/schedulers/${id}/run-now`)
      console.log('[API] runSchedulerNow response:', response.data)
      return response.data
    } catch (error: any) {
      console.error('[API] runSchedulerNow ERROR:', error)
      console.error('[API] Error response:', error.response?.data)
      console.error('[API] Error status:', error.response?.status)
      throw error
    }
  },
  testScheduler: async (id: number) => {
    console.log('[API] testScheduler called with id:', id)
    try {
      const response = await api.post(`/admin/symbols/schedulers/${id}/test`)
      console.log('[API] testScheduler response:', response.data)
      return response.data
    } catch (error: any) {
      console.error('[API] testScheduler ERROR:', error)
      console.error('[API] Error response:', error.response?.data)
      console.error('[API] Error status:', error.response?.status)
      throw error
    }
  },
  testConnection: async (url: string, sourceType: string, method?: string, headers?: any) => {
    const formData = new FormData()
    formData.append('url', url)
    formData.append('source_type', sourceType)
    if (method) formData.append('method', method)
    if (headers) formData.append('headers', JSON.stringify(headers))
    const response = await api.post('/admin/symbols/test-connection', formData)
    return response.data
  },
  addSource: async (schedulerId: number, data: any) => {
    const response = await api.post(`/admin/symbols/schedulers/${schedulerId}/sources`, data)
    return response.data
  },
  updateSource: async (schedulerId: number, sourceId: number, data: any) => {
    const response = await api.put(`/admin/symbols/schedulers/${schedulerId}/sources/${sourceId}`, data)
    return response.data
  },
  deleteSource: async (schedulerId: number, sourceId: number) => {
    const response = await api.delete(`/admin/symbols/schedulers/${schedulerId}/sources/${sourceId}`)
    return response.data
  },
  bulkStatus: async (ids: number[], status: string) => {
    const response = await api.patch('/admin/symbols/status/bulk', { ids, status })
    return response.data
  },
}

export const announcementsAPI = {
  // Get announcements list
  getAnnouncements: async (params?: {
    from_date?: string
    to_date?: string
    symbol?: string
    search?: string
    limit?: number
    offset?: number
    page?: number
    page_size?: number
  }) => {
    const response = await api.get('/announcements', { params })
    return response.data
  },

  // Get single announcement
  getAnnouncement: async (id: string) => {
    const response = await api.get(`/announcements/${id}`)
    return response.data
  },

  // Get TrueData connection
  getTrueDataConnection: async () => {
    const response = await api.get('/announcements/truedata-connection')
    return response.data
  },

  // Get database status
  getDatabaseStatus: async () => {
    const response = await api.get('/announcements/db-status')
    return response.data
  },

  // Fetch announcements from TrueData
  fetchAnnouncements: async (connectionId: number, params?: {
    from_date?: string
    to_date?: string
    symbol?: string
    top_n?: number
  }) => {
    const response = await api.post('/announcements/fetch', {
      connection_id: connectionId,
      ...params
    })
    return response.data
  },

  // Get announcement attachment (on-demand fetch from TrueData)
  // Returns blob directly (axios with responseType: 'blob' returns blob in response.data)
  getAttachment: async (id: string) => {
    const response = await api.get(`/announcements/${id}/attachment`, {
      responseType: 'blob',
      timeout: 60000 // 60 seconds timeout (backend has retry logic, so this is total time)
    })
    return response.data // axios returns blob in data when responseType is 'blob'
  },

  // Refresh descriptor metadata
  refreshDescriptors: async (connectionId: number) => {
    const response = await api.post('/announcements/descriptors/refresh', {
      connection_id: connectionId
    })
    return response.data
  },
}

// Screener API
export const screenerAPI = {
  getScrapingStatus: async (jobId: string) => {
    const response = await api.get(`/admin/screener/scrape/status/${jobId}`)
    return response.data
  },
  getStats: async () => {
    const response = await api.get('/admin/screener/stats')
    return response.data
  },
  getData: async (params?: {
    symbol?: string
    period_type?: string
    statement_group?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/admin/screener/data', { params })
    return response.data
  },
  getConnections: async () => {
    const response = await api.get('/admin/screener/connections')
    return response.data
  },
  createConnection: async (connection: any) => {
    const response = await api.post('/admin/screener/connections', connection)
    return response.data
  },
  startScraping: async (connectionId: number) => {
    const response = await api.post(`/admin/screener/connections/${connectionId}/start`)
    return response.data
  },
  stopScraping: async (connectionId: number) => {
    const response = await api.post(`/admin/screener/connections/${connectionId}/stop`)
    return response.data
  },
  triggerScraping: async () => {
    const response = await api.post('/admin/screener/scrape')
    return response.data
  },
  getConfig: async () => {
    const response = await api.get('/admin/screener/config')
    return response.data
  },
  saveConfig: async (config: any) => {
    const response = await api.post('/admin/screener/config', config)
    return response.data
  },
  getLogs: async (params?: {
    job_id?: string
    connection_id?: number
    action?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/admin/screener/logs', { params })
    return response.data
  },
}

// Analytics API
export const analyticsAPI = {
  getDashboard: async () => {
    const response = await api.get('/analytics/dashboard')
    return response.data
  },
  getReports: async () => {
    const response = await api.get('/analytics/reports')
    return response.data
  },
}

export const newsAPI = {
  getNews: async (params?: { page?: number; page_size?: number; search?: string }) => {
    const response = await api.get('/news', { params })
    return response.data
  },
  getStatus: async () => {
    const response = await api.get('/news/status')
    return response.data
  },
  toggleStatus: async (enabled: boolean) => {
    const response = await api.post('/news/toggle', null, { params: { enabled } })
    return response.data
  }
}

