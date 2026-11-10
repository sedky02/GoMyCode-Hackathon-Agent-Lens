// All data fetching for AgentLens lives here.
// Mock data is a snapshot of real API responses and is only used when VITE_USE_MOCK=1.
import mockOverview from './mock/overview.json'
import mockIssues from './mock/issues.json'
import mockIssueDetails from './mock/issue_details.json'
import mockSessions from './mock/sessions.json'
import mockSessionDetails from './mock/session_details.json'

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8100').replace(/\/$/, '')
export const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === '1' || import.meta.env.VITE_USE_MOCK === 'true'

// ---- data-source status (live vs mock), observable by the nav badge ----
let source = FORCE_MOCK ? 'mock' : 'unknown'
const listeners = new Set()
function setSource(s) {
  if (s === source) return
  source = s
  listeners.forEach((fn) => fn(s))
}
export function getSource() {
  return source
}
export function subscribeSource(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

const clone = (x) => JSON.parse(JSON.stringify(x))

async function request(path, { method = 'GET', timeout = 5000 } = {}) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeout)
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      signal: ctrl.signal,
      headers: { Accept: 'application/json' },
    })
    if (res.status === 404) {
      // The backend is up and answered: this is a real "not found", not an outage.
      let detail = 'not found'
      try {
        detail = (await res.json())?.detail || detail
      } catch {
        /* ignore */
      }
      const e = new Error(detail)
      e.notFound = true
      throw e
    }
    if (!res.ok) {
      let detail = `HTTP ${res.status} on ${path}`
      try {
        detail = (await res.json())?.detail || detail
      } catch {
        /* ignore */
      }
      throw new Error(detail)
    }
    return await res.json()
  } finally {
    clearTimeout(t)
  }
}

function notInSnapshot(what) {
  const e = new Error(`${what} is not part of the bundled mock snapshot`)
  e.notFound = true
  return e
}

// Live data, or the mock snapshot when forced. A failing API surfaces as an error, never as mock data.
async function liveOrMock(path, mockFn, opts) {
  if (FORCE_MOCK) return mockFn()
  try {
    const data = await request(path, opts)
    setSource('live')
    return data
  } catch (err) {
    setSource(err.notFound ? 'live' : 'offline')
    throw err
  }
}

// Live-only calls (demo controls + background analysis).
async function live(path, opts) {
  try {
    const data = await request(path, opts)
    setSource('live')
    return data
  } catch (err) {
    if (!err.notFound) setSource('offline')
    throw err
  }
}

// ---- public API ----
export const api = {
  overview: () => liveOrMock('/v1/overview', () => clone(mockOverview)),

  // Starts a background analysis run and returns its status immediately; poll analyzeStatus().
  analyze: () => live('/v1/analyze', { method: 'POST', timeout: 30000 }),
  analyzeStatus: () => live('/v1/analyze/status'),

  demoStatus: () => live('/v1/demo/status'),
  sendWave: (wave) => live(`/v1/demo/waves/${wave}`, { method: 'POST', timeout: 60000 }),
  resetDemo: () => live('/v1/demo/reset', { method: 'POST', timeout: 30000 }),

  issues: () => liveOrMock('/v1/issues', () => clone(mockIssues)),

  issue: (id) =>
    liveOrMock(`/v1/issues/${encodeURIComponent(id)}`, () => {
      const detail = mockIssueDetails[String(id)]
      if (!detail) throw notInSnapshot(`Issue ${id}`)
      return clone(detail)
    }),

  sessions: (outcome) => {
    const q = outcome ? `?outcome=${encodeURIComponent(outcome)}` : ''
    return liveOrMock(`/v1/sessions${q}`, () =>
      clone(mockSessions).filter((s) => !outcome || s.outcome === outcome),
    )
  },

  session: (id) =>
    liveOrMock(`/v1/sessions/${encodeURIComponent(id)}`, () => {
      const detail = mockSessionDetails[id]
      if (!detail) throw notInSnapshot(`Session ${id} (only failed sessions are bundled)`)
      return clone(detail)
    }),
}
