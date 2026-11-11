import { Fragment } from 'react'
import { Check, X } from 'lucide-react'
import { fmtTime, humanize } from './ui.jsx'

// ---------- helpers ----------
const parseMaybeJson = (v) => {
  if (typeof v !== 'string') return v
  const t = v.trim()
  if (!(t.startsWith('{') || t.startsWith('['))) return v
  try {
    return JSON.parse(t)
  } catch {
    return v
  }
}

// Compact, Python-ish JSON: {"a": 1, "b": [1, 2]}
function compactJson(v) {
  if (v === null || v === undefined) return 'null'
  if (Array.isArray(v)) return `[${v.map(compactJson).join(', ')}]`
  if (typeof v === 'object') return `{${Object.entries(v).map(([k, x]) => `${JSON.stringify(k)}: ${compactJson(x)}`).join(', ')}}`
  return JSON.stringify(v)
}

export const norm = (v) => (v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)).trim().toLowerCase()
export const display = (v) => (v === null || v === undefined ? '—' : typeof v === 'object' ? compactJson(v) : String(v))

export const RED_PENCIL = 'bg-bad/10 font-medium text-bad underline decoration-2 underline-offset-[3px]'

// Syntax stays in ink so the red-pencilled values are the only colour in a code block.
const SYNTAX = {
  key: 'text-fg-muted',
  string: 'text-fg',
  literal: 'text-fg-muted italic',
  number: 'text-fg',
  flagged: `rounded-sm px-0.5 ${RED_PENCIL}`,
}

// Tokenize a JSON string and color it; string tokens whose value is in `redValues` get flagged.
function JsonCode({ text, redValues = [] }) {
  const red = new Set(redValues.map(norm).filter(Boolean))
  const re = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g
  const out = []
  let last = 0
  let m
  let i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(<Fragment key={i++}>{text.slice(last, m.index)}</Fragment>)
    if (m[1]) {
      if (m[2]) {
        out.push(
          <span key={i++} className={SYNTAX.key}>
            {m[1]}
          </span>,
        )
        out.push(<Fragment key={i++}>{m[2]}</Fragment>)
      } else {
        let val = m[1]
        try {
          val = JSON.parse(m[1])
        } catch {
          /* keep raw */
        }
        const flagged = red.has(norm(val))
        out.push(
          <span
            key={i++}
            className={flagged ? SYNTAX.flagged : SYNTAX.string}
            title={flagged ? 'Mismatch with what the user requested' : undefined}
          >
            {m[1]}
          </span>,
        )
      }
    } else if (m[3]) {
      out.push(
        <span key={i++} className={SYNTAX.literal}>
          {m[3]}
        </span>,
      )
    } else if (m[4]) {
      out.push(
        <span key={i++} className={SYNTAX.number}>
          {m[4]}
        </span>,
      )
    }
    last = re.lastIndex
  }
  if (last < text.length) out.push(<Fragment key={i++}>{text.slice(last)}</Fragment>)
  return out
}

// Highlight given substrings inside free text
function MarkText({ text, terms = [] }) {
  const valid = terms.filter((t) => t && t.value && String(t.value).length > 1)
  if (!text || !valid.length) return text || null
  const esc = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${valid.map((t) => esc(t.value)).join('|')})`, 'gi')
  return String(text)
    .split(re)
    .map((part, i) => {
      const t = valid.find((x) => norm(x.value) === norm(part))
      return t ? (
        <mark key={i} className={`rounded-sm px-0.5 ${t.cls}`} title={t.title}>
          {part}
        </mark>
      ) : (
        <Fragment key={i}>{part}</Fragment>
      )
    })
}

// ---------- mismatch model ----------
const FLOW = [
  { key: 'requested', label: 'Requested', hint: 'user asked' },
  { key: 'queried', label: 'Queried', hint: 'what the agent looked up' },
  { key: 'returned', label: 'Returned', hint: 'what the tool gave back' },
  { key: 'claimed', label: 'Claimed', hint: 'what the agent told the user' },
]

export function mismatchInfo(details = {}) {
  const has = (k) => details[k] !== undefined && details[k] !== null && details[k] !== ''
  const res = {}
  for (const { key } of FLOW) {
    if (!has(key)) continue
    let ref = null
    let refKey = null
    if (key === 'queried' || key === 'returned') {
      if (has('requested')) [ref, refKey] = [details.requested, 'requested']
    } else if (key === 'claimed') {
      if (has('returned')) [ref, refKey] = [details.returned, 'returned']
      else if (has('queried')) [ref, refKey] = [details.queried, 'queried']
    }
    res[key] = { value: details[key], mismatch: ref !== null && norm(ref) !== norm(details[key]), refKey }
  }
  return res
}

// ---------- Claim check ----------
function Tick({ cell, hint }) {
  if (cell.mismatch)
    return (
      <span className="inline-flex items-center gap-1 text-[13px] font-medium text-bad">
        <X className="h-4 w-4" strokeWidth={2.5} /> differs from {cell.refKey}
      </span>
    )
  if (cell.refKey)
    return (
      <span className="inline-flex items-center gap-1 text-[13px] text-ok">
        <Check className="h-4 w-4" strokeWidth={2.5} /> matches {cell.refKey}
      </span>
    )
  return <span className="text-[13px] text-fg-subtle">{hint}</span>
}

export function DetectedCard({ details }) {
  if (!details || typeof details !== 'object') return null
  const info = mismatchInfo(details)
  const flow = FLOW.filter((f) => info[f.key])
  const rest = Object.entries(details).filter(([k]) => !FLOW.some((f) => f.key === k))
  const anyMismatch = flow.some((f) => info[f.key].mismatch)

  return (
    <section className={`border-t-2 pt-2.5 ${anyMismatch ? 'border-bad' : 'border-fg'}`}>
      <h2 className="font-display text-lg font-semibold text-fg">Claim check</h2>
      {flow.length > 0 && (
        <div className="mt-3 grid gap-y-4 sm:auto-cols-fr sm:grid-flow-col sm:divide-x sm:divide-line">
          {flow.map((f) => {
            const cell = info[f.key]
            return (
              <div key={f.key} className="min-w-0 sm:px-4 sm:first:pl-0">
                <div className="font-display text-[13px] font-medium text-fg-muted">{f.label}</div>
                <div
                  className={`mt-1 break-words text-[17px] font-medium leading-snug ${
                    cell.mismatch ? 'text-bad underline decoration-2 underline-offset-4' : 'text-fg'
                  }`}
                >
                  {display(cell.value)}
                </div>
                <div className="mt-1.5">
                  <Tick cell={cell} hint={f.hint} />
                </div>
              </div>
            )
          })}
        </div>
      )}
      {rest.length > 0 && (
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          {rest.map(([k, v]) => (
            <Fragment key={k}>
              <dt className="capitalize text-fg-muted">{humanize(k)}</dt>
              <dd className="break-words font-mono text-[13px] text-fg">{display(v)}</dd>
            </Fragment>
          ))}
        </dl>
      )}
    </section>
  )
}

// ---------- Timeline ----------
function kindOf(ev) {
  const t = (ev.event_type || '').toLowerCase()
  if (t === 'tool_call') return 'tool_call'
  if (t === 'tool_result' || ev.role === 'tool') return 'tool_result'
  if (t.startsWith('user') || ev.role === 'user') return 'user'
  if (t.startsWith('agent') || t.startsWith('assistant') || ev.role === 'assistant') return 'agent'
  return 'other'
}

const KIND_LABEL = { user: 'User', agent: 'Agent', tool_call: 'Tool call', tool_result: 'Tool result' }

const codeBlock = 'overflow-x-auto rounded-sm bg-raised px-3.5 py-2.5 font-mono text-[13px] leading-relaxed'

function EventBody({ ev, kind, redValues, textMarks }) {
  if (kind === 'user') return <p className="text-[15px] leading-relaxed text-fg">{ev.content}</p>
  if (kind === 'agent')
    return (
      <p className="text-[15px] leading-relaxed text-fg">
        <MarkText text={ev.content} terms={textMarks} />
      </p>
    )
  if (kind === 'tool_call') {
    const args = parseMaybeJson(ev.tool_arguments)
    const argText = args === null || args === undefined ? '' : typeof args === 'object' ? compactJson(args) : String(args)
    return (
      <pre className={`${codeBlock} text-fg-muted`}>
        <span className="font-medium text-fg">{ev.tool_name || 'tool'}</span>(
        <JsonCode text={argText} redValues={redValues} />)
      </pre>
    )
  }
  if (kind === 'tool_result') {
    const result = parseMaybeJson(ev.tool_result ?? ev.content)
    const text = result === null || result === undefined ? 'null' : typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result)
    const status = (ev.tool_status || '').toLowerCase()
    const failed = status === 'error'
    return (
      <>
        <div className="mb-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-fg-muted">
          <span className="font-mono text-fg">{ev.tool_name || 'tool'}</span>
          {ev.tool_status && (
            <span className={`inline-flex items-center gap-1.5 ${failed ? 'font-medium text-bad' : ''}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${status === 'success' ? 'bg-ok' : failed ? 'bg-bad' : 'bg-fg-subtle'}`} />
              {ev.tool_status}
            </span>
          )}
          {ev.latency_ms != null && <span className="tabular-nums">{ev.latency_ms} ms</span>}
        </div>
        <pre className={`${codeBlock} ${failed ? 'text-bad' : 'text-fg-muted'}`}>
          <JsonCode text={text} redValues={redValues} />
        </pre>
      </>
    )
  }
  return <p className="text-sm text-fg-muted">{ev.content || <span className="font-mono text-xs">{compactJson(ev)}</span>}</p>
}

export function Timeline({ events = [], evidenceIds = new Set(), redValues = [], textMarks = [], flashId }) {
  if (!events.length) return <div className="py-10 text-sm text-fg-muted">No events recorded.</div>
  const sorted = [...events].sort((a, b) => (a.sequence_number ?? 0) - (b.sequence_number ?? 0))

  return (
    <ol className="divide-y divide-line">
      {sorted.map((ev) => {
        const kind = kindOf(ev)
        const evidence = evidenceIds.has(ev.event_id)
        return (
          <li
            key={ev.event_id}
            id={`ev-${ev.event_id}`}
            className={`relative grid scroll-mt-6 gap-x-6 gap-y-2 py-4 pl-4 sm:grid-cols-[8rem_minmax(0,1fr)] ${
              flashId === ev.event_id ? 'flash' : ''
            }`}
          >
            {evidence && <span aria-hidden className="absolute inset-y-3 left-0 w-1.5 bg-evidence" />}
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 sm:block">
              <div className="font-display text-[15px] font-semibold text-fg">{KIND_LABEL[kind] || humanize(ev.event_type) || 'Event'}</div>
              <div className="text-xs tabular-nums text-fg-subtle sm:mt-0.5">
                {ev.timestamp ? fmtTime(ev.timestamp).slice(11) : `Step ${ev.sequence_number ?? '?'}`}
              </div>
              <div className="text-xs tabular-nums text-fg-subtle">Event {ev.event_id}</div>
              {evidence && <mark className="bg-evidence px-1 text-xs font-medium text-evidence-ink sm:mt-1.5 sm:inline-block">Evidence</mark>}
            </div>
            <div className="min-w-0">
              <EventBody ev={ev} kind={kind} redValues={redValues} textMarks={textMarks} />
            </div>
          </li>
        )
      })}
    </ol>
  )
}
