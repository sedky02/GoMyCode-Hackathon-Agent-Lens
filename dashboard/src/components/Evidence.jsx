import { Fragment } from 'react'
import { Timer } from 'lucide-react'
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

// Muted syntax colours so flagged values are the loudest thing in a code block.
const SYNTAX = {
  key: 'text-fg-muted',
  string: 'text-[#93cfa8]',
  literal: 'text-[#b4a2ee]',
  number: 'text-[#e0b872]',
  flagged: 'rounded-sm bg-bad/20 px-0.5 text-[#ffb4bc] ring-1 ring-bad/50',
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

// ---------- Detected comparison ----------
const MISMATCH_BG = 'bg-[color-mix(in_srgb,var(--color-bad)_9%,var(--color-surface))]'

export function DetectedCard({ details }) {
  if (!details || typeof details !== 'object') return null
  const info = mismatchInfo(details)
  const flow = FLOW.filter((f) => info[f.key])
  const rest = Object.entries(details).filter(([k]) => !FLOW.some((f) => f.key === k))
  const anyMismatch = flow.some((f) => info[f.key].mismatch)

  return (
    <div>
      {flow.length > 0 && (
        <>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-fg">Detected</h2>
            {anyMismatch && <span className="text-xs font-medium text-bad">Mismatch</span>}
          </div>
          <div className="grid gap-px overflow-hidden rounded-md border border-line bg-line sm:auto-cols-fr sm:grid-flow-col">
            {flow.map((f) => {
              const c = info[f.key]
              return (
                <div key={f.key} className={`min-w-0 px-3 py-2.5 ${c.mismatch ? MISMATCH_BG : 'bg-surface'}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={`text-xs font-medium ${c.mismatch ? 'text-bad' : 'text-fg-muted'}`}>{f.label}</span>
                    {c.mismatch ? (
                      <span className="text-[11px] text-bad/80">≠ {c.refKey}</span>
                    ) : c.refKey ? (
                      <span className="text-[11px] text-fg-subtle">= {c.refKey}</span>
                    ) : (
                      <span className="truncate text-[11px] text-fg-subtle">{f.hint}</span>
                    )}
                  </div>
                  <div className="mt-1 break-words text-[15px] font-medium leading-snug text-fg">{display(c.value)}</div>
                </div>
              )
            })}
          </div>
        </>
      )}
      {rest.length > 0 && (
        <dl className={`grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm ${flow.length ? 'mt-3' : ''}`}>
          {rest.map(([k, v]) => (
            <Fragment key={k}>
              <dt className="capitalize text-fg-subtle">{humanize(k)}</dt>
              <dd className="break-words font-mono text-[13px] text-fg">{display(v)}</dd>
            </Fragment>
          ))}
        </dl>
      )}
    </div>
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

function Meta({ ev, label, evidence }) {
  return (
    <div className="mb-1.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-xs">
      <span className="font-medium text-fg">{label}</span>
      <span className="font-mono text-[11px] text-fg-subtle">
        seq {ev.sequence_number ?? '?'} · ev {ev.event_id}
        {ev.timestamp && <> · {fmtTime(ev.timestamp).slice(11)}</>}
      </span>
      {evidence && <span className="text-[11px] font-medium text-evidence">Evidence</span>}
    </div>
  )
}

const box = (evidence) => (evidence ? 'border-evidence/45' : 'border-line')

export function Timeline({ events = [], evidenceIds = new Set(), redValues = [], textMarks = [], flashId }) {
  if (!events.length) return <div className="py-10 text-center text-sm text-fg-subtle">No events recorded.</div>
  const sorted = [...events].sort((a, b) => (a.sequence_number ?? 0) - (b.sequence_number ?? 0))

  return (
    <div className="relative">
      <div aria-hidden className="absolute bottom-3 left-[5px] top-2 w-px bg-line" />
      <ol className="relative space-y-5">
      {sorted.map((ev) => {
        const kind = kindOf(ev)
        const evidence = evidenceIds.has(ev.event_id)
        const flash = flashId === ev.event_id ? 'flash' : ''
        const anchor = `ev-${ev.event_id}`

        let body
        if (kind === 'user') {
          body = (
            <div className={`rounded-md border bg-raised px-3.5 py-2.5 text-[15px] leading-relaxed text-fg ${box(evidence)} ${flash}`}>
              {ev.content}
            </div>
          )
        } else if (kind === 'agent') {
          body = (
            <div className={`rounded-md border px-3.5 py-2.5 text-[15px] leading-relaxed text-fg ${box(evidence)} ${flash}`}>
              <MarkText text={ev.content} terms={textMarks} />
            </div>
          )
        } else if (kind === 'tool_call') {
          const args = parseMaybeJson(ev.tool_arguments)
          const argText = args === null || args === undefined ? '' : typeof args === 'object' ? compactJson(args) : String(args)
          body = (
            <div className={`overflow-hidden rounded-md border bg-canvas ${box(evidence)} ${flash}`}>
              <pre className="overflow-x-auto px-3.5 py-2.5 font-mono text-[13px] leading-relaxed text-fg-muted">
                <span className="font-medium text-fg">{ev.tool_name || 'tool'}</span>(
                <JsonCode text={argText} redValues={redValues} />)
              </pre>
            </div>
          )
        } else if (kind === 'tool_result') {
          const result = parseMaybeJson(ev.tool_result ?? ev.content)
          const text = result === null || result === undefined ? 'null' : typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result)
          const status = (ev.tool_status || '').toLowerCase()
          const ok = status === 'success'
          const err = status === 'error'
          body = (
            <div className={`overflow-hidden rounded-md border bg-canvas ${box(evidence)} ${flash}`}>
              <div className="flex items-center gap-3 border-b border-line px-3.5 py-1.5 text-xs">
                <span className="font-mono text-fg-muted">{ev.tool_name || 'tool'}</span>
                {ev.tool_status && (
                  <span className={`inline-flex items-center gap-1.5 ${err ? 'text-bad' : 'text-fg-muted'}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${ok ? 'bg-ok' : err ? 'bg-bad' : 'bg-fg-subtle'}`} />
                    {ev.tool_status}
                  </span>
                )}
                {ev.latency_ms != null && (
                  <span className="ml-auto inline-flex items-center gap-1 font-mono text-fg-subtle">
                    <Timer className="h-3 w-3" />
                    {ev.latency_ms} ms
                  </span>
                )}
              </div>
              <pre className={`overflow-x-auto px-3.5 py-2.5 font-mono text-[13px] leading-relaxed ${err ? 'text-[#ffb4bc]' : 'text-fg-muted'}`}>
                <JsonCode text={text} redValues={redValues} />
              </pre>
            </div>
          )
        } else {
          body = (
            <div className={`rounded-md border bg-raised px-3.5 py-2.5 text-sm text-fg-muted ${box(evidence)} ${flash}`}>
              {ev.content || <span className="font-mono text-xs">{compactJson(ev)}</span>}
            </div>
          )
        }

        return (
          <li key={ev.event_id} id={anchor} className="relative scroll-mt-24 pl-6">
            <span
              aria-hidden
              className={`absolute left-0 top-[3px] h-[11px] w-[11px] rounded-full border-2 border-surface ${
                evidence ? 'bg-evidence' : 'bg-line-strong'
              }`}
            />
            <Meta ev={ev} label={KIND_LABEL[kind] || humanize(ev.event_type) || 'event'} evidence={evidence} />
            {body}
          </li>
        )
      })}
      </ol>
    </div>
  )
}
