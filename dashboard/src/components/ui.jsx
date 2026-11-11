import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, TriangleAlert, Inbox, RotateCw } from 'lucide-react'

// ---------- data hook ----------
export function useApi(fn, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const fnRef = useRef(fn)
  fnRef.current = fn

  const load = useCallback(async (silent = false) => {
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await fnRef.current()
      setState({ data, loading: false, error: null })
    } catch (error) {
      setState({ data: null, loading: false, error })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    load()
  }, [load])

  return { ...state, reload: load }
}

// ---------- formatting ----------
export const pct = (v, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(digits)}%`

export const humanize = (s) => (s ? String(s).replace(/_/g, ' ') : '—')

export const fmtTime = (s) => (s ? String(s).replace('T', ' ').slice(0, 19) : '—')

// ---------- outcome / severity metadata ----------
// Status colour is carried by a small dot (or bar); labels stay neutral text.
export const OUTCOMES = {
  success: { label: 'Success', dot: 'bg-ok', text: 'text-ok', bar: 'bg-ok', tint: 'bg-ok/10 text-ok' },
  recovered: { label: 'Recovered', dot: 'bg-info', text: 'text-info', bar: 'bg-info', tint: 'bg-info/10 text-info' },
  failed: { label: 'Failed', dot: 'bg-bad', text: 'text-bad', bar: 'bg-bad', tint: 'bg-bad/10 text-bad' },
  ambiguous: { label: 'Ambiguous', dot: 'bg-warn', text: 'text-warn', bar: 'bg-warn', tint: 'bg-warn/10 text-warn' },
}
export const OUTCOME_KEYS = ['success', 'recovered', 'failed', 'ambiguous']

const SEVERITY = {
  critical: { label: 'Critical', dot: 'bg-bad', text: 'text-bad font-medium' },
  high: { label: 'High', dot: 'bg-bad', text: 'text-fg' },
  medium: { label: 'Medium', dot: 'bg-warn', text: 'text-fg' },
  low: { label: 'Low', dot: 'bg-fg-subtle', text: 'text-fg-muted' },
}

const SOURCES = {
  rules: 'Rules',
  llm: 'LLM judge',
  llm_judge: 'LLM judge',
  judge: 'LLM judge',
  hybrid: 'Hybrid',
}

// ---------- status & labels ----------
export function StatusDot({ className = 'bg-fg-subtle' }) {
  return <span aria-hidden className={`inline-block h-2 w-2 shrink-0 rounded-full ${className}`} />
}

export function Badge({ className = '', children, title }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  )
}

export function OutcomeBadge({ outcome, size = 'sm' }) {
  const m = OUTCOMES[outcome]
  if (!m) return <span className="text-sm text-fg-muted">{humanize(outcome)}</span>
  if (size === 'lg') {
    return (
      <Badge className={`${m.tint} px-2 py-1 text-[13px]`}>
        <StatusDot className={m.dot} />
        {m.label}
      </Badge>
    )
  }
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-sm text-fg">
      <StatusDot className={m.dot} />
      {m.label}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const m = SEVERITY[severity]
  if (!m) return <span className="text-sm text-fg-subtle">{severity || '—'}</span>
  return (
    <span className={`inline-flex items-center gap-2 whitespace-nowrap text-sm ${m.text}`}>
      <StatusDot className={m.dot} />
      {m.label}
    </span>
  )
}

// Machine identifiers (failure types, tools) render as quiet monospace tags.
export function TypeBadge({ type }) {
  if (!type) return <span className="text-fg-subtle">—</span>
  return (
    <span className="inline-block whitespace-nowrap rounded bg-white/[0.06] px-1.5 py-px font-mono text-[12px] text-fg-muted">
      {type}
    </span>
  )
}

export function SourceBadge({ source }) {
  return <span className="whitespace-nowrap text-sm text-fg-muted">{SOURCES[source] || source || 'Unknown'}</span>
}

// ---------- actions ----------
const BUTTON = {
  primary:
    'bg-accent text-white hover:bg-accent-hover disabled:bg-accent/60 disabled:text-white/80',
  secondary:
    'border border-line-strong bg-raised text-fg hover:border-fg-subtle/60 hover:bg-raised-hover disabled:opacity-60',
  ghost: 'text-fg-muted hover:bg-raised hover:text-fg',
}

export const buttonCls = (variant = 'secondary', extra = '') =>
  `inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed ${BUTTON[variant]} ${extra}`

export function Button({ variant = 'secondary', className = '', children, ...rest }) {
  return (
    <button className={buttonCls(variant, className)} {...rest}>
      {children}
    </button>
  )
}

// ---------- layout primitives ----------
export function Card({ className = '', children, ...rest }) {
  return (
    <div className={`rounded-lg border border-line bg-surface ${className}`} {...rest}>
      {children}
    </div>
  )
}

export function SectionTitle({ children, description, right }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-fg">{children}</h2>
        {description && <p className="mt-0.5 text-xs text-fg-subtle">{description}</p>}
      </div>
      {right}
    </div>
  )
}

export function PageHeader({ title, subtitle, right, back }) {
  return (
    <div className="mb-6">
      {back && <div className="mb-3">{back}</div>}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
          {subtitle && <p className="mt-1 max-w-2xl text-sm text-fg-muted">{subtitle}</p>}
        </div>
        {right && <div className="flex shrink-0 items-center gap-3">{right}</div>}
      </div>
    </div>
  )
}

export function BackLink({ to, onClick, children }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={onClick || (() => navigate(to))}
      className="-ml-1 inline-flex items-center gap-1 rounded px-1 py-0.5 text-sm text-fg-subtle transition-colors hover:text-fg"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      {children}
    </button>
  )
}

// A row of key figures separated by hairlines. The gap-px/bg-line trick draws
// dividers that stay correct however the grid wraps.
const STAT_COLS = {
  2: 'grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-3',
  4: 'grid-cols-2 lg:grid-cols-4',
  5: 'grid-cols-2 md:grid-cols-5',
}

export function StatGroup({ cols = 4, className = '', children }) {
  return <div className={`grid gap-px bg-line ${STAT_COLS[cols]} ${className}`}>{children}</div>
}

export function Stat({ label, value, hint, className = '' }) {
  return (
    <div className={`min-w-0 bg-surface px-4 py-3.5 ${className}`}>
      <div className="text-xs text-fg-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums tracking-tight text-fg">{value ?? '—'}</div>
      {hint && <div className="mt-0.5 text-xs text-fg-subtle">{hint}</div>}
    </div>
  )
}

export function ConfidenceBar({ value }) {
  const v = Math.max(0, Math.min(1, value ?? 0))
  return (
    <div className="flex items-center gap-2.5" title={`Confidence ${pct(value, 1)}`}>
      <span className="w-9 text-right text-sm tabular-nums text-fg">{pct(value)}</span>
      <div className="h-1 w-12 overflow-hidden rounded-full bg-line-strong">
        <div className="h-full rounded-full bg-fg-muted" style={{ width: `${v * 100}%` }} />
      </div>
    </div>
  )
}

// ---------- tables ----------
export function Th({ align = 'left', className = '', children }) {
  return (
    <th
      scope="col"
      className={`h-9 whitespace-nowrap px-4 text-xs font-medium text-fg-subtle ${align === 'right' ? 'text-right' : 'text-left'} ${className}`}
    >
      {children}
    </th>
  )
}

export function Td({ align = 'left', className = '', children }) {
  return <td className={`px-4 py-2.5 ${align === 'right' ? 'text-right' : ''} ${className}`}>{children}</td>
}

// Whole-row navigation that also works from the keyboard.
export function LinkRow({ to, className = '', children }) {
  const navigate = useNavigate()
  return (
    <tr
      tabIndex={0}
      onClick={() => navigate(to)}
      onKeyDown={(e) => e.key === 'Enter' && navigate(to)}
      className={`group cursor-pointer border-t border-line transition-colors hover:bg-raised focus-visible:bg-raised focus-visible:outline-none ${className}`}
    >
      {children}
    </tr>
  )
}

// ---------- states ----------
export function Skeleton({ className = '' }) {
  return <div aria-hidden className={`skeleton rounded bg-raised ${className}`} />
}

export function Loading({ label = 'Loading…', rows = 6 }) {
  return (
    <Card className="overflow-hidden" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <div className="flex h-9 items-center gap-6 border-b border-line px-4">
        <Skeleton className="h-2.5 w-16" />
        <Skeleton className="h-2.5 w-20" />
        <Skeleton className="ml-auto h-2.5 w-12" />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex h-11 items-center gap-6 border-t border-line px-4 first:border-t-0">
          <Skeleton className="h-3 w-14" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="hidden h-3 w-40 sm:block" />
          <Skeleton className="ml-auto h-3 w-16" />
        </div>
      ))}
    </Card>
  )
}

export function ErrorState({ error, onRetry }) {
  if (error?.notFound) return <EmptyState title="Not found" hint={String(error.message)} />
  return (
    <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start" role="alert">
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-bad" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-fg">Couldn’t load this data</div>
        <div className="mt-1 break-words font-mono text-xs text-fg-subtle">{String(error?.message || error)}</div>
      </div>
      {onRetry && (
        <Button onClick={() => onRetry()} className="self-start">
          <RotateCw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
    </Card>
  )
}

export function EmptyState({ title = 'Nothing here', hint, action, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed border-line-strong px-6 py-14 text-center">
      <Icon className="h-5 w-5 text-fg-subtle" />
      <div className="mt-3 text-sm font-medium text-fg">{title}</div>
      {hint && <div className="mt-1 max-w-sm text-sm text-fg-muted">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
