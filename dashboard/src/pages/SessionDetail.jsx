import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { api } from '../api.js'
import {
  useApi,
  pct,
  fmtTime,
  humanize,
  Card,
  BackLink,
  Skeleton,
  ErrorState,
  EmptyState,
  OutcomeBadge,
  TypeBadge,
  SourceBadge,
  SeverityBadge,
  buttonCls,
} from '../components/ui.jsx'
import { Timeline, DetectedCard, mismatchInfo, display } from '../components/Evidence.jsx'

function durationOf(a, b) {
  const t1 = Date.parse(String(a || '').replace(' ', 'T'))
  const t2 = Date.parse(String(b || '').replace(' ', 'T'))
  if (Number.isNaN(t1) || Number.isNaN(t2)) return null
  const s = Math.max(0, Math.round((t2 - t1) / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <dt className="text-sm text-fg-muted">{label}</dt>
      <dd className="text-right text-sm">{children}</dd>
    </div>
  )
}

function PanelHeader({ children, right }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
      <h2 className="text-sm font-semibold text-fg">{children}</h2>
      {right}
    </div>
  )
}

function SessionSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading session trace…</span>
      <Skeleton className="h-6 w-40" />
      <Skeleton className="mt-3 h-3 w-72" />
      <div className="mt-8 grid gap-6 lg:grid-cols-3">
        <Card className="space-y-6 p-5 lg:col-span-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i}>
              <Skeleton className="h-3 w-32" />
              <Skeleton className="mt-2.5 h-12 w-full" />
            </div>
          ))}
        </Card>
        <Card className="space-y-4 p-5">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-3 w-full" />
          ))}
        </Card>
      </div>
    </div>
  )
}

export default function SessionDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useApi(() => api.session(id), [id])
  const [flashId, setFlashId] = useState(null)

  const derived = useMemo(() => {
    const analysis = data?.analysis || null
    const findings = data?.findings || []
    const evidenceIds = new Set([
      ...(analysis?.evidence_event_ids || []),
      ...findings.flatMap((f) => f.evidence_event_ids || []),
    ])
    const redValues = []
    const textMarks = []
    for (const f of findings) {
      const info = mismatchInfo(f.details || {})
      for (const k of ['queried', 'returned']) if (info[k]?.mismatch) redValues.push(info[k].value)
      if (info.claimed?.mismatch) {
        textMarks.push({
          value: display(info.claimed.value),
          cls: 'bg-bad/20 text-[#ffc9cf] ring-1 ring-bad/50',
          title: `Claimed "${display(info.claimed.value)}" but ${info.claimed.refKey} was "${display(f.details[info.claimed.refKey])}"`,
        })
      }
    }
    return { analysis, findings, evidenceIds, redValues, textMarks }
  }, [data])

  const jumpTo = (eventId) => {
    const el = document.getElementById(`ev-${eventId}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setFlashId(null)
    requestAnimationFrame(() => setFlashId(eventId))
    setTimeout(() => setFlashId((cur) => (cur === eventId ? null : cur)), 2000)
  }

  const back = (
    <div className="mb-3">
      <BackLink onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/sessions'))}>Back</BackLink>
    </div>
  )

  if (loading)
    return (
      <div>
        {back}
        <SessionSkeleton />
      </div>
    )
  if (error)
    return (
      <div>
        {back}
        <ErrorState error={error} onRetry={reload} />
      </div>
    )
  if (!data) return <EmptyState title="Session not found" />

  const { analysis, findings, evidenceIds, redValues, textMarks } = derived
  const events = data.events || []
  const dur = durationOf(data.started_at, data.ended_at)
  const issueIds = [...new Set(findings.map((f) => f.issue_id).filter((x) => x !== null && x !== undefined))]
  const detectedFindings = findings.filter((f) => f.details && Object.keys(f.details).length)

  return (
    <div>
      {back}

      <div className="mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xl font-semibold tracking-tight text-fg">
            <span className="font-mono">{data.session_id}</span>
            {analysis && <OutcomeBadge outcome={analysis.outcome} size="lg" />}
            {analysis?.failure_type && <TypeBadge type={analysis.failure_type} />}
          </h1>
          <div className="mt-1.5 flex flex-wrap gap-x-2 text-sm tabular-nums text-fg-subtle">
            <span>{fmtTime(data.started_at)}</span>
            {dur && <span>· {dur} duration</span>}
            <span>· {events.length} events</span>
            <span>· {evidenceIds.size} evidence events</span>
          </div>
        </div>
        {issueIds.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {issueIds.map((iid) => (
              <Link key={iid} to={`/issues/${iid}`} className={buttonCls('secondary')}>
                Part of issue #{iid} <ArrowUpRight className="h-3.5 w-3.5 text-fg-muted" />
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main: detected + timeline */}
        <div className="min-w-0 space-y-6 lg:col-span-2">
          {detectedFindings.map((f) => (
            <Card key={f.finding_id} className="border-l-2 border-l-bad p-4">
              <DetectedCard details={f.details} />
            </Card>
          ))}

          <Card>
            <PanelHeader
              right={
                <span className="inline-flex items-center gap-1.5 text-xs text-fg-subtle">
                  <span className="h-2 w-2 rounded-full bg-evidence" /> Evidence
                </span>
              }
            >
              Session timeline
            </PanelHeader>
            <div className="p-4 sm:p-5">
              <Timeline events={events} evidenceIds={evidenceIds} redValues={redValues} textMarks={textMarks} flashId={flashId} />
            </div>
          </Card>
        </div>

        {/* Side: analysis */}
        <aside className="min-w-0 space-y-6 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <PanelHeader>Analysis</PanelHeader>
            {!analysis ? (
              <div className="px-4 py-5 text-sm text-fg-muted">This session has not been analyzed yet.</div>
            ) : (
              <>
                <dl className="divide-y divide-line px-4">
                  <Row label="Outcome">
                    <OutcomeBadge outcome={analysis.outcome} />
                  </Row>
                  {analysis.failure_type && (
                    <Row label="Failure type">
                      <TypeBadge type={analysis.failure_type} />
                    </Row>
                  )}
                  {analysis.recovery_type && (
                    <Row label="Recovery type">
                      <TypeBadge type={analysis.recovery_type} />
                    </Row>
                  )}
                  {analysis.ambiguity_type && (
                    <Row label="Ambiguity type">
                      <TypeBadge type={analysis.ambiguity_type} />
                    </Row>
                  )}
                  <Row label="Confidence">
                    <span className="font-medium tabular-nums text-fg">{pct(analysis.confidence)}</span>
                  </Row>
                  <Row label="Decided by">
                    <SourceBadge source={analysis.source} />
                  </Row>
                </dl>
                {analysis.reason && (
                  <p className="border-t border-line px-4 py-3.5 text-sm leading-relaxed text-fg-muted">{analysis.reason}</p>
                )}
              </>
            )}

            {evidenceIds.size > 0 && (
              <div className="border-t border-line px-4 py-3.5">
                <div className="mb-2 text-xs text-fg-subtle">Jump to evidence</div>
                <div className="flex flex-wrap gap-1.5">
                  {[...evidenceIds].sort((a, b) => a - b).map((eid) => (
                    <button
                      key={eid}
                      onClick={() => jumpTo(eid)}
                      className="inline-flex h-6 items-center gap-1.5 rounded border border-line-strong px-2 font-mono text-xs text-fg-muted transition-colors hover:border-evidence/60 hover:text-fg"
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-evidence" />
                      ev {eid}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {findings.length > 0 && (
            <Card>
              <PanelHeader>
                Findings <span className="ml-1 font-normal tabular-nums text-fg-subtle">{findings.length}</span>
              </PanelHeader>
              <ul className="divide-y divide-line">
                {findings.map((f) => (
                  <li key={f.finding_id} className="px-4 py-3.5">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                      <TypeBadge type={f.failure_type} />
                      <SeverityBadge severity={f.severity} />
                      <span className="ml-auto text-xs tabular-nums text-fg-subtle">{pct(f.confidence)} conf.</span>
                    </div>
                    {f.tool && (
                      <div className="mt-2 text-xs text-fg-subtle">
                        Tool <span className="font-mono text-fg-muted">{f.tool}</span>
                      </div>
                    )}
                    {f.signature && <div className="mt-1.5 break-words font-mono text-[11px] text-fg-subtle">{f.signature}</div>}
                    {f.issue_id != null && (
                      <Link
                        to={`/issues/${f.issue_id}`}
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-accent-fg hover:text-fg"
                      >
                        View issue #{f.issue_id} <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {analysis && !findings.length && analysis.outcome !== 'failed' && (
            <p className="px-1 text-xs text-fg-subtle">No hidden failures detected in this session ({humanize(analysis.outcome)}).</p>
          )}
        </aside>
      </div>
    </div>
  )
}
