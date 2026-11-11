---
version: alpha
name: AgentLens dashboard
description: An audit tool for engineers who check an AI agent's claims against what its tools returned. It should read like a working paper, plain and exact.
colors:
  ground: "#151d19"
  sheet: "#1c2621"
  inset: "#25312b"
  rule: "#303f37"
  rule-strong: "#4c6156"
  ink: "#e8ede6"
  ink-muted: "#adb9b0"
  ink-subtle: "#87968c"
  ok: "#5cbd88"
  info: "#6bafe8"
  bad: "#f2726b"
  warn: "#dea54b"
  highlighter: "#ffe14d"
  highlighter-ink: "#3b2f00"
typography:
  display:
    fontFamily: IBM Plex Sans Condensed
    fontSize: 28px
    fontWeight: 600
  body:
    fontFamily: IBM Plex Sans
    fontSize: 15px
    lineHeight: 1.6
  code:
    fontFamily: IBM Plex Mono
    fontSize: 13px
rounded:
  sm: 3px
spacing:
  sm: 8px
  md: 16px
  lg: 48px
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.sm}"
  section-heading:
    borderTop: "2px solid {colors.ink-subtle}"
---

## Overview

AgentLens compares what a user asked, what the agent looked up, what the tool returned and what
the agent claimed. That is an audit, so the dashboard borrows from an auditor's ledger: a dark
green ledger-cover ground, chalk-coloured text, red for discrepancies, a yellow highlighter for
evidence, and tick and cross marks next to each compared value. It is dark only; the people who
use it are engineers reading traces.

The tokens live in `src/index.css` under `@theme`. Tailwind class names keep their older names:
`canvas` is ground, `surface` is sheet, `raised` is inset, `line` is rule, `fg` is ink,
`evidence` is highlighter.

## Colors

- **Ground (#151d19):** the page. A dark green slate, tinted on purpose and not neutral near-black.
- **Sheet (#1c2621):** a slightly lifted sheet for the few things that are separate objects: the
  demo controls and the side panels on a session.
- **Inset (#25312b):** row hover, code blocks, type tags.
- **Ink (#e8ede6):** text, rules, primary buttons, meters, focus rings. There is no separate
  accent hue; actions are ink. About 14:1 on ground.
- **Ink muted (#adb9b0)** and **ink subtle (#87968c):** secondary text, about 8:1 and 5:1 on ground.
- **Status (ok, info, bad, warn):** outcome and severity only, as a dot, a bar segment or a tint.
- **Red pencil (bad):** also marks a value that disagrees with its reference, always with an underline.
- **Highlighter (#ffe14d):** marks evidence events and nothing else. Text on it is always highlighter-ink.

## Typography

- IBM Plex Sans for text. Plex Sans Condensed for page titles, section headings, column heads,
  figure labels and large figures. Plex Mono only for tool calls, JSON and machine identifiers.
- Sentence case everywhere. No all-caps labels.
- Numbers use `tabular-nums` and are right-aligned in tables.
- Scale: 56px outcome counts, 28px page title, 26px figures, 18px section heading, 15px body,
  13px column heads and labels, 12px fine print.

## Layout

- One column, `max-w-7xl`, left-aligned. The header is a plain bar with a 2px rule; it does not stick.
- A section starts with a 2px rule and a heading (`SectionTitle`). Its content sits directly
  on the page: figures in a grid (`Figures`, `Figure`), tables with a 2px rule under the
  column heads and hairlines between rows. Tables are not wrapped in cards.
- Heavy 2px rules use ink subtle, never full ink: on the dark ground a full-ink rule outweighs the text.
- 48px between sections, 16 to 24px inside them.
- The session page opens with the verdict sentence, then the claim check, then the transcript.

## Elevation & Depth

Flat. No shadows and no blur. A sheet is distinguished by its slightly lighter fill and a hairline border.

## Shapes

3px radius on buttons, inputs, tags, code blocks and sheets. Meters and the outcome bar have
square ends. Status dots are the only circles.

## Components

All shared pieces are in `src/components/ui.jsx`: `PageHeader`, `SectionTitle`, `Figures` and
`Figure`, `Meter`, `Th`/`Td`/`LinkRow`, `Button`, `Card` (the sheet), `OutcomeBadge`,
`SeverityBadge`, `TypeBadge`, `EmptyState`, `ErrorState`. `src/components/Evidence.jsx` holds the
claim check (`DetectedCard`), the transcript (`Timeline`) and `RED_PENCIL`.

## Do's and Don'ts

- Do build new pages from the components above and the tokens in `src/index.css`.
- Do add a token here and in `@theme` before a page uses a new colour or size.
- Do keep red for failures and mismatches, and yellow for evidence.
- Don't add a second accent colour, gradients, shadows, blur or a light theme without changing this file first.
- Don't wrap tables or figure rows in cards, and don't bring back grids of boxed stat tiles.
- Don't use mono for labels, all-caps labels, middle-dot metadata strings or arrow glyphs on links.
- Don't use Inter, a neutral near-black ground with one bright accent (indigo, lime), or a cream ground with a terracotta accent.
