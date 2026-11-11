import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import DemoControls from '../components/DemoControls.jsx'
import {
  useApi,
  pct,
  OUTCOMES,
  OUTCOME_KEYS,
  Card,
  SectionTitle,
  PageHeader,
  StatGroup,
  Stat,
  StatusDot,
  Skeleton,
  ErrorState,
  fmtTime,
} from '../components/ui.jsx'

const fmtDuration = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`)

function LastRun({ run, justRan }) {
  const total = run ? (run.analyzed ?? 0) + (run.skipped ?? 0) : 0
  const analyzedPct = total ? (run.analyzed / total) * 100 : 0

  return (
    <section>
      <SectionTitle
        right={
          run && (
            <span className="text-xs tabular-nums text-fg-subtle">
              Run {run.run_id}, {fmtTime(run.started_at)}
            </span>
          )
        }
      >
        Last analysis run
      </SectionTitle>
      <Card className={`overflow-hidden ${justRan ? 'flash-accent' : ''}`}>
        {!run ? (
          <div className="px-4 py-4 sm:px-5">
            <div className="text-sm font-medium text-fg">No analysis run yet</div>
            <p className="mt-1 text-sm text-fg-muted">Send wave 1, then run analysis.</p>
          </div>
        ) : (
          <StatGroup cols={5}>
            <Stat label="Analyzed" value={run.analyzed} />
            <Stat label="Skipped (unchanged)" value={run.skipped} />
            <Stat label="LLM judge calls" value={run.judge_calls} />
            <Stat label="Duration" value={run.duration_ms != null ? fmtDuration(run.duration_ms) : '—'} />
            <div className="col-span-2 flex flex-col justify-center bg-surface px-4 py-3.5 md:col-span-1">
              {total > 0 ? (
                <>
                  <div className="flex h-1.5 overflow-hidden rounded-full bg-line-strong">
                    <div className="h-full bg-accent" style={{ width: `${analyzedPct}%` }} title={`${run.analyzed} analyzed`} />
                  </div>
                  <div className="mt-2 flex justify-between gap-2 text-xs tabular-nums text-fg-subtle">
                    <span>
                      <span className="text-fg-muted">{analyzedPct.toFixed(0)}%</span> re-analyzed
                    </span>
                    <span>
                      <span className="text-fg-muted">{(100 - analyzedPct).toFixed(0)}%</span> reused
                    </span>
                  </div>
                </>
              ) : (
                <span className="text-xs text-fg-subtle">Nothing analyzed</span>
              )}
            </div>
          </StatGroup>
        )}
      </Card>
    </section>
  )
}

function Totals({ totals }) {
  const items = [
    ['sessions', totals?.sessions, '/sessions'],
    ['events', totals?.events],
    ['findings', totals?.findings],
    ['issues', totals?.issues, '/issues'],
  ]
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-subtle">
      {items.map(([label, v, to]) => {
        const inner = (
          <>
            <span className="font-medium tabular-nums text-fg-muted">{v ?? '—'}</span> {label}
          </>
        )
        return to ? (
          <Link key={label} to={to} className="transition-colors hover:text-fg">
            {inner}
          </Link>
        ) : (
          <span key={label}>{inner}</span>
        )
      })}
    </div>
  )
}

function Outcomes({ outcomes, totals }) {
  const classified = OUTCOME_KEYS.reduce((a, k) => a + (outcomes?.[k] || 0), 0)
  const total = totals?.sessions || classified
  const unclassified = Math.max(0, total - classified)

  return (
    <section>
      <SectionTitle right={<Totals totals={totals} />}>Session outcomes</SectionTitle>
      <Card className="overflow-hidden">
        <div className="px-4 py-4 sm:px-5">
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full bg-line-strong" role="img" aria-label="Share of sessions by outcome">
            {OUTCOME_KEYS.map((k) => {
              const n = outcomes?.[k] ?? 0
              if (!n || !total) return null
              return (
                <div
                  key={k}
                  className={`h-full ${OUTCOMES[k].bar}`}
                  style={{ width: `${(n / total) * 100}%` }}
                  title={`${OUTCOMES[k].label}: ${n}`}
                />
              )
            })}
          </div>
          {unclassified > 0 && (
            <div className="mt-2 text-right text-xs tabular-nums text-fg-subtle">{unclassified} not yet classified</div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-px border-t border-line bg-line lg:grid-cols-4">
          {OUTCOME_KEYS.map((k) => {
            const m = OUTCOMES[k]
            const n = outcomes?.[k] ?? 0
            const share = total ? n / total : 0
            return (
              <Link
                key={k}
                to={`/sessions?outcome=${k}`}
                className="group block bg-surface px-4 py-3.5 transition-colors hover:bg-raised focus-visible:bg-raised focus-visible:outline-none sm:px-5"
              >
                <span className="inline-flex items-center gap-2 text-sm text-fg-muted transition-colors group-hover:text-fg">
                  <StatusDot className={m.dot} />
                  {m.label}
                </span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums tracking-tight text-fg">{n}</span>
                  <span className="text-xs tabular-nums text-fg-subtle">{pct(share, 1)}</span>
                </div>
              </Link>
            )
          })}
        </div>
      </Card>
    </section>
  )
}

function Evaluation({ ev }) {
  if (!ev) return null
  const fd = ev.failure_detection
  const subtype = ev.subtype_accuracy
  const modes = ev.modes ? ['rules', 'llm', 'hybrid'].filter((k) => ev.modes[k]) : []
  const bestAcc = modes.length ? Math.max(...modes.map((k) => ev.modes[k].accuracy ?? 0)) : null
  const bestF1 = modes.length ? Math.max(...modes.map((k) => ev.modes[k].macro_f1 ?? 0)) : null
  const modeLabel = { rules: 'Rules only', llm: 'LLM judge only', hybrid: 'Hybrid' }

  const headline = [
    <Stat key="acc" label="Accuracy" value={pct(ev.accuracy, 1)} />,
    <Stat key="f1" label="Macro F1" value={pct(ev.macro_f1, 1)} hint={`Precision ${pct(ev.macro_precision)}, recall ${pct(ev.macro_recall)}`} />,
    fd && (
      <Stat
        key="fd"
        label="Failure detection F1"
        value={pct(fd.f1, 1)}
        hint={`Failed against the rest: precision ${pct(fd.precision, 1)}, recall ${pct(fd.recall, 1)}`}
      />
    ),
    subtype != null && <Stat key="sub" label="Subtype accuracy" value={pct(subtype, 1)} hint="Failure, recovery and ambiguity type" />,
  ].filter(Boolean)

  return (
    <section>
      <SectionTitle
        description="Classifier output compared against labeled ground truth"
        right={
          ev.mode && (
            <span className="text-xs text-fg-subtle">
              Mode <span className="font-mono text-fg-muted">{ev.mode}</span>
            </span>
          )
        }
      >
        Evaluation
      </SectionTitle>
      <Card className="overflow-hidden">
        <StatGroup cols={headline.length}>{headline}</StatGroup>
        <div className={`grid gap-px border-t border-line bg-line ${modes.length > 0 ? 'lg:grid-cols-3' : 'lg:grid-cols-2'}`}>
          <Panel title="Per-class recall">
            <div className="space-y-3.5">
              {OUTCOME_KEYS.filter((k) => ev.per_class?.[k]).map((k) => {
                const c = ev.per_class[k]
                return (
                  <div
                    key={k}
                    title={`${OUTCOMES[k].label}: precision ${pct(c.precision, 1)}, recall ${pct(c.recall, 1)}, F1 ${pct(c.f1, 1)}, support ${c.support}`}
                  >
                    <div className="mb-1.5 flex items-center justify-between text-sm">
                      <span className="inline-flex items-center gap-2 text-fg-muted">
                        <StatusDot className={OUTCOMES[k].dot} />
                        {OUTCOMES[k].label}
                        <span className="text-xs tabular-nums text-fg-subtle">n={c.support}</span>
                      </span>
                      <span className="tabular-nums text-fg">{pct(c.recall, 1)}</span>
                    </div>
                    <div className="h-1 overflow-hidden rounded-full bg-line-strong">
                      <div className="h-full rounded-full bg-fg-muted" style={{ width: `${(c.recall ?? 0) * 100}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </Panel>

          <Panel title="Confusion matrix" hint="Rows actual, columns predicted">
            <ConfusionMatrix cm={ev.confusion_matrix} />
          </Panel>

          {modes.length > 0 && (
            <Panel title="Classifier comparison">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-fg-subtle">
                    <th className="pb-2 font-medium">Mode</th>
                    <th className="pb-2 text-right font-medium">Accuracy</th>
                    <th className="pb-2 text-right font-medium">Macro F1</th>
                  </tr>
                </thead>
                <tbody>
                  {modes.map((k) => {
                    const m = ev.modes[k]
                    const active = k === ev.mode
                    return (
                      <tr key={k} className="border-t border-line">
                        <td className="py-2.5">
                          <span className={active ? 'text-fg' : 'text-fg-muted'}>{modeLabel[k]}</span>
                          {active && <span className="ml-2 text-xs text-accent-fg">in use</span>}
                        </td>
                        <td className={`py-2.5 text-right tabular-nums ${m.accuracy === bestAcc ? 'font-semibold text-fg' : 'text-fg-muted'}`}>
                          {pct(m.accuracy, 1)}
                        </td>
                        <td className={`py-2.5 text-right tabular-nums ${m.macro_f1 === bestF1 ? 'font-semibold text-fg' : 'text-fg-muted'}`}>
                          {pct(m.macro_f1, 1)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {modes.length > 1 && <p className="mt-3 text-xs text-fg-subtle">Best score per column in bold.</p>}
            </Panel>
          )}
        </div>
      </Card>
    </section>
  )
}

function Panel({ title, hint, children }) {
  return (
    <div className="min-w-0 bg-surface p-4 sm:p-5">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium text-fg">{title}</h3>
        {hint && <span className="text-xs text-fg-subtle">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function ConfusionMatrix({ cm }) {
  if (!cm?.labels || !cm?.matrix) return <div className="text-sm text-fg-subtle">No comparison data.</div>
  const max = Math.max(1, ...cm.matrix.flat())
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[18rem] table-fixed border-separate border-spacing-1 text-xs">
        <colgroup>
          <col className="w-[4.75rem]" />
        </colgroup>
        <thead>
          <tr>
            <th />
            {cm.labels.map((l) => (
              <th key={l} className="truncate pb-1 text-center text-[11px] font-medium text-fg-subtle" title={OUTCOMES[l]?.label || l}>
                {OUTCOMES[l]?.label || l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cm.matrix.map((row, i) => (
            <tr key={i}>
              <th scope="row" className="truncate pr-1.5 text-right text-[11px] font-medium text-fg-subtle">
                {OUTCOMES[cm.labels[i]]?.label || cm.labels[i]}
              </th>
              {row.map((v, j) => {
                const diag = i === j
                const a = v / max
                return (
                  <td
                    key={j}
                    title={`actual ${cm.labels[i]}, predicted ${cm.labels[j]}: ${v}`}
                    className={`h-9 rounded text-center tabular-nums ${v ? 'font-medium text-fg' : 'text-fg-subtle/70'}`}
                    style={{
                      background: v
                        ? diag
                          ? `color-mix(in srgb, var(--color-accent) ${Math.round(14 + a * 46)}%, transparent)`
                          : `color-mix(in srgb, var(--color-bad) ${Math.round(20 + a * 40)}%, transparent)`
                        : 'color-mix(in srgb, var(--color-fg) 2.5%, transparent)',
                    }}
                  >
                    {v}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function OverviewSkeleton() {
  return (
    <div className="space-y-8" role="status" aria-live="polite">
      <span className="sr-only">Loading overview…</span>
      {[0, 1].map((n) => (
        <div key={n}>
          <Skeleton className="mb-4 h-3 w-32" />
          <Card className="p-5">
            {n === 0 && <Skeleton className="mb-8 h-2 w-full" />}
            <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <div key={i}>
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="mt-3 h-6 w-10" />
                </div>
              ))}
            </div>
          </Card>
        </div>
      ))}
      <div>
        <Skeleton className="mb-4 h-3 w-24" />
        <Card className="h-72" />
      </div>
    </div>
  )
}

export default function Overview() {
  const { data, loading, error, reload } = useApi(() => api.overview(), [])
  const [justRan, setJustRan] = useState(false)

  const onRunFinished = async () => {
    await reload(true)
    setJustRan(true)
    setTimeout(() => setJustRan(false), 2000)
  }

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="ERP assistant sessions that look fine but aren’t (wrong records, unsupported claims, loops), grouped and ranked into issues."
      />

      <div className="space-y-8">
        <DemoControls onDataChanged={() => reload(true)} onRunFinished={onRunFinished} />

        {loading && !data ? (
          <OverviewSkeleton />
        ) : error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : (
          <>
            <Outcomes outcomes={data.outcomes} totals={data.totals} />
            <LastRun run={data.last_run} justRan={justRan} />
            <Evaluation ev={data.evaluation} />
          </>
        )}
      </div>
    </div>
  )
}
