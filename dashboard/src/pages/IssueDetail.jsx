import { useParams } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api } from '../api.js'
import {
  useApi,
  pct,
  fmtTime,
  PageHeader,
  SectionTitle,
  BackLink,
  Figures,
  Figure,
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

      <div className="mb-12">
        <Figures className="md:grid-cols-5">
          <Figure label="Affected sessions">{data.session_count ?? sessions.length}</Figure>
          <Figure label="Average confidence">{pct(data.avg_confidence)}</Figure>
          <Figure label="Priority, out of 100">{(data.priority ?? 0).toFixed(1)}</Figure>
          <Figure label="Severity">
            <span className="font-sans font-normal">
              <SeverityBadge severity={data.severity} />
            </span>
          </Figure>
          <Figure label="Failure type" className="col-span-2 md:col-span-1">
            <TypeBadge type={data.failure_type} />
          </Figure>
        </Figures>
        {data.tools?.length > 0 && (
          <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-muted">
            Tools involved
            {data.tools.map((t) => (
              <span key={t} className="font-mono text-[13px] text-fg">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>

      <SectionTitle>
        Affected sessions <span className="ml-1 font-normal tabular-nums text-fg-subtle">{sessions.length}</span>
      </SectionTitle>
      {sessions.length === 0 ? (
        <EmptyState title="No sessions attached" />
      ) : (
        <div className="-mt-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <Th>Session</Th>
                  <Th>Confidence</Th>
                  <Th>Reason</Th>
                  <th className="w-8 border-b-2 border-fg" />
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
                    <Td className="min-w-80 py-3 leading-relaxed text-fg">{s.reason || '—'}</Td>
                    <td className="pr-3 pt-3 align-top">
                      <ChevronRight className="h-4 w-4 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
                    </td>
                  </LinkRow>
                ))}
              </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
