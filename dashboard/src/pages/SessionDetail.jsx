import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
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
import { Timeline, DetectedCard, mismatchInfo, display, RED_PENCIL } from '../components/Evidence.jsx'

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
      <h2 className="font-display text-[17px] font-semibold text-fg">{children}</h2>
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
          cls: RED_PENCIL,
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

      <div className="mb-10">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h1 className="font-display text-[28px] font-semibold leading-tight text-fg">Session {data.session_id}</h1>
            {analysis && <OutcomeBadge outcome={analysis.outcome} size="lg" />}
            {analysis?.failure_type && <TypeBadge type={analysis.failure_type} />}
          </div>
          {issueIds.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {issueIds.map((iid) => (
                <Link key={iid} to={`/issues/${iid}`} className={buttonCls('secondary')}>
                  Part of issue #{iid}
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-sm tabular-nums text-fg-muted">
          <span>{fmtTime(data.started_at)}</span>
          {dur && <span>{dur} long</span>}
          <span>{events.length} events</span>
          <span>{evidenceIds.size} marked as evidence</span>
        </div>
        {analysis?.reason && <p className="mt-5 max-w-3xl text-[19px] leading-relaxed text-fg">{analysis.reason}</p>}
      </div>

      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-3">
        <div className="min-w-0 space-y-10 lg:col-span-2">
          {detectedFindings.map((f) => (
            <DetectedCard key={f.finding_id} details={f.details} />
          ))}

          <section className="border-t-2 border-fg-subtle pt-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="font-display text-lg font-semibold text-fg">Transcript</h2>
              <span className="text-sm text-fg-muted">
                <mark className="bg-evidence px-1 text-evidence-ink">Highlighted</mark> events support the verdict
              </span>
            </div>
            <div className="mt-1">
              <Timeline events={events} evidenceIds={evidenceIds} redValues={redValues} textMarks={textMarks} flashId={flashId} />
            </div>
          </section>
        </div>

        {/* Side: analysis */}
        <aside className="min-w-0 space-y-6 lg:sticky lg:top-6 lg:self-start">
          <Card>
            <PanelHeader>Analysis</PanelHeader>
            {!analysis ? (
              <div className="px-4 py-5 text-sm text-fg-muted">This session has not been analyzed yet.</div>
            ) : (
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
            )}

            {evidenceIds.size > 0 && (
              <div className="border-t border-line px-4 py-3.5">
                <div className="mb-2 text-sm text-fg-muted">Jump to evidence</div>
                <div className="flex flex-wrap gap-1.5">
                  {[...evidenceIds].sort((a, b) => a - b).map((eid) => (
                    <button
                      key={eid}
                      onClick={() => jumpTo(eid)}
                      className="inline-flex h-7 items-center rounded-sm bg-evidence/85 px-2 text-[13px] font-medium tabular-nums text-evidence-ink transition-colors hover:bg-evidence focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fg"
                    >
                      Event {eid}
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
                      <span className="ml-auto text-xs tabular-nums text-fg-subtle">{pct(f.confidence)} confidence</span>
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
                        className="mt-2 inline-block text-[13px] font-medium text-fg underline decoration-line-strong underline-offset-4 hover:decoration-fg"
                      >
                        View issue #{f.issue_id}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {analysis && !findings.length && analysis.outcome !== 'failed' && (
            <p className="text-sm text-fg-muted">No hidden failures detected in this session ({humanize(analysis.outcome)}).</p>
          )}
        </aside>
      </div>
    </div>
  )
}
