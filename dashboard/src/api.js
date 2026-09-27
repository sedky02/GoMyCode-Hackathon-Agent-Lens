// All data fetching for AgentLens lives here.
// Falls back to bundled mock JSON when VITE_USE_MOCK=1 or when a request fails.
import mockOverview from './mock/overview.json'
import mockIssues from './mock/issues.json'
import mockIssue1 from './mock/issue_1.json'
import mockSessions from './mock/sessions.json'
import mockSessionS008 from './mock/session_S008.json'

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

async function withFallback(path, mockFn, opts) {
  if (FORCE_MOCK) return mockFn()
  try {
    const data = await request(path, opts)
    setSource('live')
    return data
  } catch (err) {
    if (err.notFound) {
      setSource('live')
      throw err
    }
    console.warn(`[AgentLens] ${path} failed (${err.message}); using mock data`)
    setSource('mock')
    return mockFn()
  }
}

// ---- mock state (so "Run analysis" visibly does something in mock mode) ----
let mockLastRun = clone(mockOverview.last_run)

function mockAnalyze() {
  const prev = mockLastRun?.run_id ?? 0
  const total = mockOverview.totals.sessions
  mockLastRun = {
    run_id: prev + 1,
    started_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
    analyzed: 0,
    skipped: total,
    judge_calls: 0,
    duration_ms: 37,
  }
  return new Promise((r) => setTimeout(() => r(clone(mockLastRun)), 600))
}

// Live-only calls (demo controls + background analysis): no mock fallback.
async function live(path, opts) {
  const data = await request(path, opts)
  setSource('live')
  return data
}

// ---- public API ----
export const api = {
  overview: () =>
    withFallback('/v1/overview', () => ({ ...clone(mockOverview), last_run: clone(mockLastRun) })),

  // Starts a background analysis run and returns its status immediately; poll analyzeStatus().
  analyze: () => (FORCE_MOCK ? mockAnalyze() : live('/v1/analyze', { method: 'POST', timeout: 30000 })),
  analyzeStatus: () => live('/v1/analyze/status'),

  demoStatus: () => live('/v1/demo/status'),
  sendWave: (wave) => live(`/v1/demo/waves/${wave}`, { method: 'POST', timeout: 60000 }),
  resetDemo: () => live('/v1/demo/reset', { method: 'POST', timeout: 30000 }),

  issues: () => withFallback('/v1/issues', () => clone(mockIssues)),

  issue: (id) =>
    withFallback(`/v1/issues/${encodeURIComponent(id)}`, () => {
      const base = mockIssues.find((i) => String(i.issue_id) === String(id))
      const detail = clone(mockIssue1)
      return base ? { ...detail, ...clone(base), sessions: detail.sessions } : detail
    }),

  sessions: (outcome) => {
    const q = outcome ? `?outcome=${encodeURIComponent(outcome)}` : ''
    return withFallback(`/v1/sessions${q}`, () =>
      clone(mockSessions).filter((s) => !outcome || s.outcome === outcome),
    )
  },

  session: (id) =>
    withFallback(`/v1/sessions/${encodeURIComponent(id)}`, () => ({
      ...clone(mockSessionS008),
      session_id: id,
    })),
}
