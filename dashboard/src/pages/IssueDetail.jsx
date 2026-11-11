import { useParams } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api } from '../api.js'
import {
  useApi,
  pct,
  fmtTime,
  Card,
  PageHeader,
  SectionTitle,
  BackLink,
  StatGroup,
  Loading,
  ErrorState,
  EmptyState,
  SeverityBadge,
  TypeBadge,
  ConfidenceBar,
  Th,
  Td,
  LinkRow,
} from '../components/ui.jsx'
import { PriorityBar } from './Issues.jsx'

function Field({ label, children, className = '' }) {
  return (
    <div className={`min-w-0 bg-surface px-4 py-3.5 ${className}`}>
      <div className="text-xs text-fg-muted">{label}</div>
      <div className="mt-1.5 flex min-h-7 items-center text-xl font-semibold tabular-nums tracking-tight text-fg">{children}</div>
    </div>
  )
}

export default function IssueDetail() {
  const { id } = useParams()
  const { data, loading, error, reload } = useApi(() => api.issue(id), [id])

  const back = <BackLink to="/issues">All issues</BackLink>

  if (loading)
    return (
      <div>
        <div className="mb-6">{back}</div>
        <Loading label="Loading issue…" rows={5} />
      </div>
    )
  if (error)
    return (
      <div>
        <div className="mb-6">{back}</div>
        <ErrorState error={error} onRetry={reload} />
      </div>
    )
  if (!data) return <EmptyState title="Issue not found" />

  const sessions = data.sessions || []

  return (
    <div>
      <PageHeader
        back={back}
        title={
          <span>
            <span className="mr-2 font-normal tabular-nums text-fg-subtle">#{data.issue_id}</span>
            {data.title}
          </span>
        }
      />

      <Card className="mb-8 overflow-hidden">
        <StatGroup cols={5}>
          <Field label="Failure type">
            <TypeBadge type={data.failure_type} />
          </Field>
          <Field label="Severity">
            <SeverityBadge severity={data.severity} />
          </Field>
          <Field label="Affected sessions">{data.session_count ?? sessions.length}</Field>
          <Field label="Avg confidence">{pct(data.avg_confidence)}</Field>
          <Field label="Priority" className="col-span-2 md:col-span-1">
            <div className="w-full">
              <PriorityBar value={data.priority} />
            </div>
          </Field>
        </StatGroup>
        {data.tools?.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-4 py-2.5 text-xs text-fg-subtle">
            Tools involved
            {data.tools.map((t) => (
              <span key={t} className="font-mono text-fg-muted">
                {t}
              </span>
            ))}
          </div>
        )}
      </Card>

      <SectionTitle>
        Affected sessions <span className="ml-1 font-normal tabular-nums text-fg-subtle">{sessions.length}</span>
      </SectionTitle>
      {sessions.length === 0 ? (
        <EmptyState title="No sessions attached" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <Th>Session</Th>
                  <Th>Confidence</Th>
                  <Th>Reason</Th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <LinkRow key={s.session_id} to={`/sessions/${s.session_id}`}>
                    <Td className="whitespace-nowrap py-3 align-top">
                      <div className="font-mono text-[13px] font-medium text-fg">{s.session_id}</div>
                      <div className="mt-0.5 text-xs tabular-nums text-fg-subtle">{fmtTime(s.started_at)}</div>
                    </Td>
                    <Td className="py-3 align-top">
                      <ConfidenceBar value={s.confidence} />
                    </Td>
                    <Td className="min-w-80 py-3 leading-relaxed text-fg-muted">{s.reason || '—'}</Td>
                    <td className="pr-3 pt-3 align-top">
                      <ChevronRight className="h-4 w-4 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
                    </td>
                  </LinkRow>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
