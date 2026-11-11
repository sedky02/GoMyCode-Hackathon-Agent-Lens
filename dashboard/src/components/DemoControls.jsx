import { useCallback, useEffect, useRef, useState } from 'react'
import { Play, RotateCcw, LoaderCircle, Check, CircleCheck, TriangleAlert } from 'lucide-react'
import { api, API_URL, FORCE_MOCK } from '../api.js'
import { Card, Button } from './ui.jsx'

const PHASE_LABEL = {
  starting: 'Finding changed sessions…',
  analyzing: 'Analyzing sessions',
  grouping: 'Grouping findings into issues…',
  done: 'Done',
  error: 'Failed',
}

// One step of the demo flow. The primary step is the product's main action;
// finished steps recede so the next one reads first.
function StepButton({ step, icon: Icon, label, sub, onClick, disabled, busy, done, primary = false }) {
  const tone = primary
    ? 'border-transparent bg-accent text-white hover:bg-accent-hover'
    : done
      ? 'border-line bg-transparent text-fg-muted'
      : 'border-line-strong bg-raised text-fg hover:border-fg-subtle/60 hover:bg-raised-hover'
  const marker = primary
    ? 'bg-white/15 text-white'
    : done
      ? 'bg-ok/10 text-ok'
      : 'border border-line-strong text-fg-muted'
  return (
    <button
      onClick={onClick}
      disabled={disabled || busy}
      className={`flex min-w-0 flex-1 items-center gap-3 rounded-md border px-3 py-2.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed ${tone} ${
        (disabled || busy) && !done && !busy ? 'opacity-45' : ''
      } ${done ? 'disabled:cursor-default' : ''}`}
    >
      <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold tabular-nums ${marker}`}>
        {busy ? (
          <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
        ) : done ? (
          <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
        ) : Icon ? (
          <Icon className="h-3 w-3 fill-current" />
        ) : (
          step
        )}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        {sub && <span className={`block truncate text-xs ${primary ? 'text-white/70' : 'text-fg-subtle'}`}>{sub}</span>}
      </span>
    </button>
  )
}

function Progress({ job }) {
  const total = job.total || 0
  const done = job.done || 0
  const share = total ? done / total : job.phase === 'grouping' ? 1 : 0
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm">
        <span className="flex items-center gap-2 text-fg">
          <LoaderCircle className="h-3.5 w-3.5 animate-spin text-accent-fg" />
          {PHASE_LABEL[job.phase] || job.phase}
          {job.phase === 'analyzing' && total > 0 && (
            <span className="tabular-nums text-fg-muted">
              {done} / {total}
            </span>
          )}
        </span>
        <span className="flex flex-wrap items-center gap-x-3 text-xs tabular-nums text-fg-subtle">
          <span>{job.skipped} skipped unchanged</span>
          <span>{job.judge_calls} LLM calls</span>
          {job.current && <span className="font-mono text-fg-muted">{job.current}</span>}
        </span>
      </div>
      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-line-strong">
        <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${share * 100}%` }} />
      </div>
      {job.mode && job.mode !== 'rules' && (
        <p className="mt-2 text-xs text-fg-subtle">
          The LLM judge is rate-limited on free tiers, so this can take a few minutes. Results are saved as they
          finish; you can leave this page.
        </p>
      )}
    </div>
  )
}

export default function DemoControls({ onDataChanged, onRunFinished }) {
  const [demo, setDemo] = useState(null)
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(null)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [unavailable, setUnavailable] = useState(FORCE_MOCK)
  const callbacks = useRef({ onDataChanged, onRunFinished })
  callbacks.current = { onDataChanged, onRunFinished }

  const refresh = useCallback(async () => {
    try {
      const [d, j] = await Promise.all([api.demoStatus(), api.analyzeStatus()])
      setDemo(d)
      setJob(j)
      setUnavailable(false)
    } catch {
      setUnavailable(true)
    }
  }, [])

  useEffect(() => {
    if (!FORCE_MOCK) refresh()
  }, [refresh])

  const running = Boolean(job?.running)
  useEffect(() => {
    if (!running) return undefined
    const timer = setInterval(async () => {
      try {
        const j = await api.analyzeStatus()
        setJob(j)
        callbacks.current.onDataChanged?.()
        if (!j.running) {
          clearInterval(timer)
          await refresh()
          if (j.error) {
            setError(`Analysis failed: ${j.error}`)
          } else if (j.last_run) {
            const r = j.last_run
            const retry = r.judge_failures ? ` ${r.judge_failures} LLM calls failed (rate limit?). Run analysis again to retry them.` : ''
            setMessage(
              `Run #${r.run_id}: analyzed ${r.analyzed} sessions, skipped ${r.skipped} unchanged, ` +
                `${r.judge_calls} LLM judge calls in ${(r.duration_ms / 1000).toFixed(1)} s.${retry}`,
            )
            callbacks.current.onRunFinished?.()
          }
        }
      } catch {
        /* transient: keep polling */
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [running, refresh])

  const act = async (key, fn, describe) => {
    setBusy(key)
    setError(null)
    setMessage(null)
    try {
      const result = await fn()
      if (describe) setMessage(describe(result))
      await refresh()
      callbacks.current.onDataChanged?.()
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(null)
    }
  }

  const sendWave = (wave) =>
    act(`wave${wave}`, () => api.sendWave(wave), (r) =>
      wave === 1
        ? `Wave 1 ingested: ${r.accepted} new events across ${r.sessions} sessions. Next: run analysis.`
        : `Wave 2 ingested: ${r.accepted} new events changed ${r.sessions} sessions. Run analysis: only those ${r.sessions} will be re-analyzed.`,
    )

  const runAnalysis = () =>
    act('analyze', async () => {
      const status = await api.analyze()
      setJob(status)
      return status
    })

  const reset = () => {
    if (!window.confirm('Clear all ingested traces and analysis results? Cached LLM verdicts are kept, so the next run is fast.')) return
    act('reset', api.resetDemo, () => 'Demo reset. Start again with wave 1.')
  }

  if (unavailable) {
    return (
      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-medium text-fg">Demo controls are offline</div>
          <p className="mt-1 text-fg-muted">
            They need the live API at <span className="font-mono text-fg">{API_URL}</span>. Start it with{' '}
            <code className="break-all rounded bg-canvas px-1.5 py-0.5 font-mono text-xs text-fg">
              .venv/bin/uvicorn agentlens.api:app --port 8100
            </code>
          </p>
        </div>
        {!FORCE_MOCK && (
          <Button onClick={refresh} className="h-7 self-start px-2.5 text-xs">
            Retry
          </Button>
        )}
      </Card>
    )
  }

  const w1 = demo?.wave1
  const w2 = demo?.wave2
  const locked = running || Boolean(busy)

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-fg">Live demo</h2>
          <p className="mt-0.5 text-xs text-fg-subtle">Replay recorded agent traces, then analyze incrementally.</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-fg-subtle">
          <span className="tabular-nums">
            <span className="text-fg-muted">{demo?.events_ingested ?? 0}</span> events ingested
          </span>
          <span>
            Mode <span className="font-mono text-fg-muted">{demo?.mode ?? '—'}</span>
          </span>
          <Button variant="ghost" onClick={reset} disabled={locked} className="h-7 px-2 text-xs disabled:opacity-40">
            {busy === 'reset' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Reset demo
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2 p-4 md:flex-row">
        <StepButton
          step={1}
          label="Send wave 1"
          sub={w1 ? `${w1.events} events in ${w1.sessions} sessions` : ''}
          onClick={() => sendWave(1)}
          disabled={locked || w1?.sent}
          busy={busy === 'wave1'}
          done={w1?.sent}
        />
        <StepButton
          step={2}
          label="Send wave 2"
          sub={w2 ? `${w2.events} new events change ${w2.sessions} sessions` : ''}
          onClick={() => sendWave(2)}
          disabled={locked || !w1?.sent || w2?.sent}
          busy={busy === 'wave2'}
          done={w2?.sent}
        />
        <StepButton
          primary
          icon={Play}
          label={running ? 'Analyzing…' : 'Run analysis'}
          sub="Incremental: only changed sessions"
          onClick={runAnalysis}
          disabled={locked || !demo?.events_ingested}
          busy={running || busy === 'analyze'}
        />
      </div>

      <div className="border-t border-line px-4 py-3" aria-live="polite">
        {running ? (
          <Progress job={job} />
        ) : error ? (
          <div role="alert" className="flex items-start gap-2 text-sm text-fg">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-bad" />
            {error}
          </div>
        ) : message ? (
          <div className="flex items-start gap-2 text-sm text-fg">
            <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
            {message}
          </div>
        ) : (
          <p className="text-xs text-fg-subtle">
            Send wave 1, run analysis, send wave 2, then run analysis again and watch it skip the unchanged sessions.
          </p>
        )}
      </div>
    </Card>
  )
}
