import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import DemoControls from '../components/DemoControls.jsx'
import {
  useApi,
  pct,
  OUTCOMES,
  OUTCOME_KEYS,
  SectionTitle,
  PageHeader,
  Figures,
  Figure,
  Meter,
  StatusDot,
  Skeleton,
  ErrorState,
  fmtTime,
} from '../components/ui.jsx'

const fmtDuration = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`)

const numCell = 'px-2 py-2 text-right tabular-nums last:pr-0'

function Totals({ totals }) {
  const items = [
    ['sessions', totals?.sessions, '/sessions'],
    ['events', totals?.events],
    ['findings', totals?.findings],
    ['issues', totals?.issues, '/issues'],
  ]
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-fg-muted">
      {items.map(([label, v, to]) => {
        const inner = (
          <>
            <span className="font-medium tabular-nums text-fg">{v ?? '—'}</span> {label}
          </>
        )
        return to ? (
          <Link key={label} to={to} className="underline decoration-line-strong underline-offset-4 hover:decoration-fg">
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
      <div className="grid grid-cols-2 gap-x-8 gap-y-6 lg:grid-cols-4">
        {OUTCOME_KEYS.map((k) => {
          const m = OUTCOMES[k]
          const n = outcomes?.[k] ?? 0
          return (
            <Link key={k} to={`/sessions?outcome=${k}`} className="group block focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg">
              <div className="font-display text-[56px] font-semibold leading-none tabular-nums text-fg">{n}</div>
              <div className="mt-2 flex items-center gap-2 text-[15px] text-fg">
                <StatusDot className={m.dot} />
                <span className="underline decoration-transparent underline-offset-4 transition-colors group-hover:decoration-fg">
                  {m.label}
                </span>
                <span className="tabular-nums text-fg-subtle">{pct(total ? n / total : 0, 1)}</span>
              </div>
            </Link>
          )
        })}
      </div>
      <div className="mt-6 flex h-3 gap-px bg-line" role="img" aria-label="Share of sessions by outcome">
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
      {unclassified > 0 && <div className="mt-2 text-sm tabular-nums text-fg-muted">{unclassified} not yet classified</div>}
    </section>
  )
}

function LastRun({ run, justRan }) {
  const total = run ? (run.analyzed ?? 0) + (run.skipped ?? 0) : 0
  const analyzedShare = total ? run.analyzed / total : 0

  return (
    <section>
      <SectionTitle
        right={
          run && (
            <span className="text-sm tabular-nums text-fg-muted">
              Run {run.run_id}, {fmtTime(run.started_at)}
            </span>
          )
        }
      >
        Last analysis run
      </SectionTitle>
      {!run ? (
        <p className="text-[15px] text-fg-muted">No analysis has run yet. Send wave 1, then run analysis.</p>
      ) : (
        <div className={`rounded-sm ${justRan ? 'flash-accent' : ''}`}>
          <Figures className="md:grid-cols-4">
            <Figure label="Analyzed">{run.analyzed}</Figure>
            <Figure label="Skipped, unchanged">{run.skipped}</Figure>
            <Figure label="LLM judge calls">{run.judge_calls}</Figure>
            <Figure label="Duration">{run.duration_ms != null ? fmtDuration(run.duration_ms) : '—'}</Figure>
          </Figures>
          {total > 0 && (
            <div className="mt-5 max-w-xl">
              <Meter share={analyzedShare} className="h-3" />
              <div className="mt-1.5 flex justify-between gap-4 text-sm tabular-nums text-fg-muted">
                <span>{pct(analyzedShare)} re-analyzed</span>
                <span>{pct(1 - analyzedShare)} reused from the previous run</span>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function Panel({ title, hint, children }) {
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h3 className="font-display text-[15px] font-semibold text-fg">{title}</h3>
        {hint && <span className="text-xs text-fg-subtle">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function ColHead({ align = 'right', children }) {
  return (
    <th scope="col" className={`border-b border-fg-subtle px-2 pb-1.5 first:pl-0 last:pr-0 font-display text-[13px] font-semibold text-fg-muted ${align === 'right' ? 'text-right' : 'text-left'}`}>
      {children}
    </th>
  )
}

function PerClass({ perClass }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <ColHead align="left">Outcome</ColHead>
            <ColHead>Precision</ColHead>
            <ColHead>Recall</ColHead>
            <ColHead>F1</ColHead>
            <ColHead>Count</ColHead>
          </tr>
        </thead>
        <tbody>
          {OUTCOME_KEYS.filter((k) => perClass?.[k]).map((k) => {
            const c = perClass[k]
            return (
              <tr key={k} className="border-b border-line">
                <td className="py-2 pr-3">
                  <span className="inline-flex items-center gap-2 text-fg">
                    <StatusDot className={OUTCOMES[k].dot} />
                    {OUTCOMES[k].label}
                  </span>
                </td>
                <td className={`${numCell} text-fg-muted`}>{pct(c.precision, 1)}</td>
                <td className={`${numCell} font-medium text-fg`}>{pct(c.recall, 1)}</td>
                <td className={`${numCell} text-fg-muted`}>{pct(c.f1, 1)}</td>
                <td className={`${numCell} text-fg-muted`}>{c.support}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ConfusionMatrix({ cm }) {
  if (!cm?.labels || !cm?.matrix) return <div className="text-sm text-fg-muted">No comparison data.</div>
  const max = Math.max(1, ...cm.matrix.flat())
  const tint = (token, share) => `color-mix(in srgb, var(--color-${token}) ${Math.round(12 + share * 30)}%, transparent)`
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[18rem] table-fixed border-separate border-spacing-px text-sm">
        <colgroup>
          <col className="w-[5.25rem]" />
        </colgroup>
        <thead>
          <tr>
            <th />
            {cm.labels.map((l) => (
              <th key={l} className="truncate pb-1 text-center font-display text-[13px] font-semibold text-fg-muted" title={OUTCOMES[l]?.label || l}>
                {OUTCOMES[l]?.label || l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cm.matrix.map((row, i) => (
            <tr key={i}>
              <th scope="row" className="truncate pr-2 text-right font-display text-[13px] font-semibold text-fg-muted">
                {OUTCOMES[cm.labels[i]]?.label || cm.labels[i]}
              </th>
              {row.map((v, j) => (
                <td
                  key={j}
                  title={`actual ${cm.labels[i]}, predicted ${cm.labels[j]}: ${v}`}
                  className={`h-9 text-center tabular-nums ${v ? 'font-medium text-fg' : 'text-fg-subtle'}`}
                  style={{ background: v ? tint(i === j ? 'ok' : 'bad', v / max) : 'var(--color-surface)' }}
                >
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ModeComparison({ ev, modes }) {
  const label = { rules: 'Rules only', llm: 'LLM judge only', hybrid: 'Hybrid' }
  const best = (field) => Math.max(...modes.map((k) => ev.modes[k][field] ?? 0))
  const bestAccuracy = best('accuracy')
  const bestF1 = best('macro_f1')
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <ColHead align="left">Mode</ColHead>
              <ColHead>Accuracy</ColHead>
              <ColHead>Macro F1</ColHead>
            </tr>
          </thead>
          <tbody>
            {modes.map((k) => {
              const m = ev.modes[k]
              return (
                <tr key={k} className="border-b border-line">
                  <td className="py-2 pr-3 text-fg">
                    {label[k]}
                    {k === ev.mode && <span className="ml-2 text-xs text-fg-subtle">in use</span>}
                  </td>
                  <td className={`${numCell} ${m.accuracy === bestAccuracy ? 'font-semibold text-fg' : 'text-fg-muted'}`}>{pct(m.accuracy, 1)}</td>
                  <td className={`${numCell} ${m.macro_f1 === bestF1 ? 'font-semibold text-fg' : 'text-fg-muted'}`}>{pct(m.macro_f1, 1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {modes.length > 1 && <p className="mt-2 text-xs text-fg-subtle">Best score per column in bold.</p>}
    </>
  )
}

function Evaluation({ ev }) {
  if (!ev) return null
  const fd = ev.failure_detection
  const modes = ev.modes ? ['rules', 'llm', 'hybrid'].filter((k) => ev.modes[k]) : []

  return (
    <section>
      <SectionTitle
        description="Verdicts compared against the dataset's hidden labels"
        right={
          ev.mode && (
            <span className="text-sm text-fg-muted">
              Mode <span className="font-mono text-[13px] text-fg">{ev.mode}</span>
            </span>
          )
        }
      >
        Evaluation
      </SectionTitle>
      <Figures className="md:grid-cols-4">
        <Figure label="Accuracy">{pct(ev.accuracy, 1)}</Figure>
        <Figure label="Macro F1" hint={`Precision ${pct(ev.macro_precision)}, recall ${pct(ev.macro_recall)}`}>
          {pct(ev.macro_f1, 1)}
        </Figure>
        {fd && (
          <Figure label="Failure detection F1" hint={`Failed against the rest: precision ${pct(fd.precision, 1)}, recall ${pct(fd.recall, 1)}`}>
            {pct(fd.f1, 1)}
          </Figure>
        )}
        {ev.subtype_accuracy != null && (
          <Figure label="Subtype accuracy" hint="Failure, recovery and ambiguity type">
            {pct(ev.subtype_accuracy, 1)}
          </Figure>
        )}
      </Figures>
      <div className={`mt-8 grid gap-x-12 gap-y-8 ${modes.length > 0 ? 'lg:grid-cols-3' : 'lg:grid-cols-2'}`}>
        <Panel title="By outcome">
          <PerClass perClass={ev.per_class} />
        </Panel>
        <Panel title="Confusion matrix" hint="Rows actual, columns predicted">
          <ConfusionMatrix cm={ev.confusion_matrix} />
        </Panel>
        {modes.length > 0 && (
          <Panel title="Classifier comparison">
            <ModeComparison ev={ev} modes={modes} />
          </Panel>
        )}
      </div>
    </section>
  )
}

function OverviewSkeleton() {
  return (
    <div className="space-y-12" role="status" aria-live="polite">
      <span className="sr-only">Loading overview…</span>
      {[0, 1, 2].map((n) => (
        <div key={n} className="border-t-2 border-line pt-3">
          <Skeleton className="mb-5 h-4 w-40" />
          <div className="grid grid-cols-2 gap-8 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i}>
                <Skeleton className={n === 0 ? 'h-12 w-20' : 'h-7 w-16'} />
                <Skeleton className="mt-3 h-3 w-24" />
              </div>
            ))}
          </div>
        </div>
      ))}
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

      <div className="space-y-12">
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
