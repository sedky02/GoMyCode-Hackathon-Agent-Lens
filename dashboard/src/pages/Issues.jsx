import { Link } from 'react-router-dom'
import { ChevronRight, CircleCheck } from 'lucide-react'
import { api } from '../api.js'
import {
  useApi,
  pct,
  Card,
  PageHeader,
  Loading,
  ErrorState,
  EmptyState,
  SeverityBadge,
  TypeBadge,
  buttonCls,
  Th,
  Td,
  LinkRow,
} from '../components/ui.jsx'

export function PriorityBar({ value }) {
  const v = Math.max(0, Math.min(100, value ?? 0))
  return (
    <div className="flex items-center gap-2.5" title={`Priority ${v.toFixed(1)} / 100`}>
      <span className="w-9 text-right text-sm font-medium tabular-nums text-fg">{v.toFixed(1)}</span>
      <div className="h-1 w-full min-w-16 overflow-hidden rounded-full bg-line-strong">
        <div className="h-full rounded-full bg-fg-muted" style={{ width: `${v}%` }} />
      </div>
    </div>
  )
}

export default function Issues() {
  const { data, loading, error, reload } = useApi(() => api.issues(), [])

  return (
    <div>
      <PageHeader
        title="Issues"
        subtitle="Hidden failures grouped into issues, ranked by priority (severity, affected sessions, confidence)."
      />
      {loading ? (
        <Loading label="Loading issues…" />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data?.length ? (
        <EmptyState
          icon={CircleCheck}
          title="No issues detected"
          hint="Run an analysis from the Overview page."
          action={
            <Link to="/" className={buttonCls('secondary')}>
              Go to Overview
            </Link>
          }
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <Th className="w-12 pr-0">#</Th>
                  <Th>Issue</Th>
                  <Th>Severity</Th>
                  <Th align="right">Sessions</Th>
                  <Th align="right">Avg confidence</Th>
                  <Th className="w-56">Priority</Th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {data.map((issue, i) => (
                  <LinkRow key={issue.issue_id} to={`/issues/${issue.issue_id}`}>
                    <Td className="py-3 pr-0 align-top tabular-nums text-fg-subtle">{i + 1}</Td>
                    <Td className="min-w-72 py-3">
                      <div className="font-medium text-fg">{issue.title}</div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <TypeBadge type={issue.failure_type} />
                        {(issue.tools || []).map((t) => (
                          <span key={t} className="font-mono text-xs text-fg-subtle">
                            {t}
                          </span>
                        ))}
                      </div>
                    </Td>
                    <Td className="py-3 align-top">
                      <SeverityBadge severity={issue.severity} />
                    </Td>
                    <Td align="right" className="py-3 align-top font-medium tabular-nums text-fg">
                      {issue.session_count}
                    </Td>
                    <Td align="right" className="py-3 align-top tabular-nums text-fg-muted">
                      {pct(issue.avg_confidence)}
                    </Td>
                    <Td className="py-3 align-top">
                      <PriorityBar value={issue.priority} />
                    </Td>
                    <td className="pr-3 pt-3 align-top">
                      <ChevronRight className="h-4 w-4 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
                    </td>
                  </LinkRow>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-line px-4 py-2.5 text-xs tabular-nums text-fg-subtle">
            {data.length} issue{data.length === 1 ? '' : 's'}, highest priority first
          </div>
        </Card>
      )}
    </div>
  )
}
