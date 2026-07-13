import {
  buildMockEsg,
  buildMockSummary,
  getMockTelemetry,
  getMockTraceability,
  mockDeposits,
  mockHubs,
  mockRoutes,
  mockUsers,
  mockVouchers,
} from './mockData'

const normalizeBaseUrl = (value) => value.replace(/\/$/, '')

export const API_BASE_URL = normalizeBaseUrl(
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
)
export const WS_BASE_URL = normalizeBaseUrl(
  import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000',
)
export const IS_DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'

const TOKEN_KEY = 'reloop_access_token'

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export const getStoredToken = () => sessionStorage.getItem(TOKEN_KEY)

export const storeToken = (token) => sessionStorage.setItem(TOKEN_KEY, token)

export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY)

const parseResponse = async (response) => {
  const contentType = response.headers.get('content-type') || ''
  const body = contentType.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const message = body?.detail || body?.message || body || `Request failed with status ${response.status}`
    throw new ApiError(String(message), response.status, body)
  }
  return body
}

const request = async (path, { token, method = 'GET', body, headers = {}, signal } = {}) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    signal,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return parseResponse(response)
}

const waitForDemo = () => new Promise((resolve) => setTimeout(resolve, 180))

export const api = {
  async login(email, password) {
    const response = await fetch(`${API_BASE_URL}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    })
    return parseResponse(response)
  },

  me: (token) => request('/auth/me', { token }),

  async dashboardSummary(period, token) {
    if (IS_DEMO_MODE) {
      await waitForDemo()
      return buildMockSummary(period)
    }
    return request(`/dashboard/summary?period=${encodeURIComponent(period)}`, { token })
  },

  async esgReport(period, token) {
    if (IS_DEMO_MODE) return buildMockEsg(period)
    return request(`/reports/esg?period=${encodeURIComponent(period)}`, { token })
  },

  async hubs(token) {
    if (IS_DEMO_MODE) return structuredClone(mockHubs)
    return request('/hubs?limit=1000', { token })
  },

  async telemetry(hubCode, hubId, period, token) {
    if (IS_DEMO_MODE) return getMockTelemetry(hubId)
    return request(`/hubs/${encodeURIComponent(hubCode)}/telemetry?period=${encodeURIComponent(period)}`, { token })
  },

  async routes(token) {
    if (IS_DEMO_MODE) return structuredClone(mockRoutes)
    return request('/routes', { token })
  },

  async deposits(token) {
    if (IS_DEMO_MODE) return structuredClone(mockDeposits)
    return request('/deposits?limit=100', { token })
  },

  async users(token) {
    if (IS_DEMO_MODE) return structuredClone(mockUsers)
    return request('/users?limit=1000', { token })
  },

  async vouchers(token) {
    if (IS_DEMO_MODE) return structuredClone(mockVouchers)
    return request('/vouchers', { token })
  },

  async traceability(traceCode, token) {
    if (IS_DEMO_MODE) return getMockTraceability(traceCode)
    return request(`/traceability/${encodeURIComponent(traceCode.trim())}`, { token })
  },
}

export const createHubSocket = (token) => {
  if (IS_DEMO_MODE || !token) return null
  return new WebSocket(`${WS_BASE_URL}/ws/hubs?token=${encodeURIComponent(token)}`)
}
