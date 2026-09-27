import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronRight, Search, X } from 'lucide-react'
import { api } from '../api.js'
import {
  useApi,
  fmtTime,
  OUTCOMES,
  OUTCOME_KEYS,
  Card,
  PageHeader,
  Loading,
  ErrorState,
  EmptyState,
  OutcomeBadge,
  TypeBadge,
  SourceBadge,
  ConfidenceBar,
  StatusDot,
  Button,
  Th,
  Td,
  LinkRow,
} from '../components/ui.jsx'

export default function Sessions() {
  const [params, setParams] = useSearchParams()
  const outcome = params.get('outcome') || ''
  const [q, setQ] = useState('')

  const { data, loading, error, reload } = useApi(() => api.sessions(outcome || undefined), [outcome])
  const { data: overview } = useApi(() => api.overview(), [])
  const counts = overview?.outcomes || {}
  const total = overview?.totals?.sessions ?? OUTCOME_KEYS.reduce((a, k) => a + (counts[k] || 0), 0)

  const rows = useMemo(() => {
    const list = data || []
    const needle = q.trim().toLowerCase()
    if (!needle) return list
    return list.filter((s) =>
      [s.session_id, s.failure_type, s.recovery_type, s.ambiguity_type, s.source]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle)),
    )
  }, [data, q])

  const tabs = [{ key: '', label: 'All', count: total || null }, ...OUTCOME_KEYS.map((k) => ({ key: k, label: OUTCOMES[k].label, dot: OUTCOMES[k].dot, count: counts[k] }))]

  return (
    <div>
      <PageHeader title="Sessions" subtitle="Every analyzed agent session with its classified outcome." />

      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
          <div role="tablist" aria-label="Filter by outcome" className="inline-flex gap-0.5 rounded-md border border-line bg-surface p-0.5">
            {tabs.map((t) => {
              const active = t.key === outcome
              return (
                <button
                  key={t.key || 'all'}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setParams(t.key ? { outcome: t.key } : {})}
                  className={`inline-flex h-7 items-center gap-2 whitespace-nowrap rounded px-2.5 text-sm transition-colors ${
                    active ? 'bg-raised text-fg shadow-[inset_0_0_0_1px_var(--color-line-strong)]' : 'text-fg-muted hover:text-fg'
                  }`}
                >
                  {t.dot && <StatusDot className={t.dot} />}
                  {t.label}
                  {t.count != null && <span className={`text-xs tabular-nums ${active ? 'text-fg-muted' : 'text-fg-subtle'}`}>{t.count}</span>}
                </button>
              )
            })}
          </div>
        </div>
        <label className="relative block md:w-64">
          <span className="sr-only">Filter sessions</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by id or type…"
            className="h-8 w-full rounded-md border border-line bg-surface pl-8 pr-8 text-sm text-fg placeholder:text-fg-subtle transition-colors hover:border-line-strong focus:border-accent/70 focus:outline-none"
          />
          {q && (
            <button
              type="button"
              onClick={() => setQ('')}
              aria-label="Clear filter"
              className="absolute right-1.5 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded text-fg-subtle hover:text-fg"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </label>
      </div>

      {loading ? (
        <Loading label="Loading sessions…" rows={8} />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No sessions match"
          hint={q ? `Nothing matches “${q.trim()}” in this view.` : 'No sessions have this outcome yet.'}
          action={
            (q || outcome) && (
              <Button
                onClick={() => {
                  setQ('')
                  setParams({})
                }}
              >
                Clear filters
              </Button>
            )
          }
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <Th>Session</Th>
                  <Th>Outcome</Th>
                  <Th>Type</Th>
                  <Th>Confidence</Th>
                  <Th>Source</Th>
                  <Th align="right">Events</Th>
                  <Th>Started</Th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => {
                  const type = s.failure_type || s.recovery_type || s.ambiguity_type
                  return (
                    <LinkRow key={s.session_id} to={`/sessions/${s.session_id}`}>
                      <Td className="font-mono text-[13px] font-medium text-fg">{s.session_id}</Td>
                      <Td>
                        <OutcomeBadge outcome={s.outcome} />
                      </Td>
                      <Td>
                        <TypeBadge type={type} />
                      </Td>
                      <Td>
                        <ConfidenceBar value={s.confidence} />
                      </Td>
                      <Td>
                        <SourceBadge source={s.source} />
                      </Td>
                      <Td align="right" className="tabular-nums text-fg-muted">
                        {s.event_count ?? '—'}
                      </Td>
                      <Td className="whitespace-nowrap tabular-nums text-fg-subtle">{fmtTime(s.started_at)}</Td>
                      <td className="pr-3">
                        <ChevronRight className="h-4 w-4 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
                      </td>
                    </LinkRow>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="border-t border-line px-4 py-2.5 text-xs tabular-nums text-fg-subtle">
            {rows.length} session{rows.length === 1 ? '' : 's'}
            {q && data && rows.length !== data.length && <> of {data.length}</>}
          </div>
        </Card>
      )}
    </div>
  )
}
