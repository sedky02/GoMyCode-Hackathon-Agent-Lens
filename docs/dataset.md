# SupplyzPro Agent Logs: synthetic dataset

A synthetic SQLite dataset of AI agent sessions for the "Find the Hidden Failures"
hackathon challenge. It simulates an ERP assistant (similar to SupplyzPro) handling
inventory checks, customer/order lookups, contact updates, order creation,
cancellations, invoices, and sales reports — including realistic **hidden**
failures, legitimate recoveries, and legitimate ambiguity.

## Files

- `generate_dataset.py` regenerates the database from scratch (deterministic, seeded).
- `supplyzpro_agent_logs.db` is the committed SQLite database for seed 42. It is fully regenerable, and
  `tests/test_dataset.py` checks that regenerating seed 42 reproduces every table.

```bash
python3 generate_dataset.py                              # rewrites supplyzpro_agent_logs.db (seed 42)
python3 generate_dataset.py --seed 7 --out heldout.db    # same scenario templates, different entities and values
```

The generator uses only the Python standard library. The same seed always produces the same table
contents. The file bytes can differ between SQLite versions, so compare contents, not checksums.

A different seed reshuffles sessions and draws different customers, products, quantities and
timestamps. It does not introduce new scenario templates or phrasing.

## Dataset size

- 120 sessions
- 838 events
- 32 customers, 24 products, 74 orders, 20 invoices
- Outcome distribution: 62 success / 24 recovered / 21 failed / 13 ambiguous
  (~52% / 20% / 17.5% / 10.5%)

## Schema

### `sessions`

| column        | notes |
|---------------|-------|
| session_id    | PK, e.g. `S001` |
| started_at / ended_at | timestamps of first/last event |
| scenario_type | one of: `inventory_check`, `customer_order_lookup`, `update_customer`, `create_order`, `cancel_order`, `invoice_lookup`, `sales_report` |
| outcome       | `success` \| `recovered` \| `failed` \| `ambiguous` (same value as `ground_truth.outcome`, denormalized onto the session for convenience) |
| metadata      | JSON: `{channel, agent_version, locale}` |

### `events` — the full chronological session history

| column | notes |
|---|---|
| event_id | PK, globally unique, increases with time across the whole dataset |
| session_id | FK → sessions |
| sequence_number | 1-based position within the session |
| timestamp | `YYYY-MM-DD HH:MM:SS`, strictly increasing within a session |
| event_type | `user_message` \| `agent_message` \| `tool_call` \| `tool_result` |
| role | `user` \| `assistant` \| `tool` |
| content | short human-readable text for the event |
| tool_name | set on `tool_call`/`tool_result` events only |
| tool_arguments_json | JSON text, set on `tool_call` events |
| tool_result_json | JSON text, set on `tool_result` events |
| tool_status | `success` \| `error`, set on `tool_result` events only |
| latency_ms | set on `tool_result` events only |

A session is always a `tool_call` immediately followed by its `tool_result` (never
detached), and `user_message`/`agent_message` events carry the conversational turns
around them.

### `customers`

32 synthetic customers. Deliberately includes **duplicate/shared names** so
ambiguity arises naturally:
- 4 customers named "Ahmed ..." (Ben Ali/Tunis, Ben Salah/Sfax, Trabelsi/Sousse, Gharbi/Tunis)
- 2 "Mohamed Karray" (Tunis, Sfax)
- 2 "Sana Jlassi" (Tunis, Bizerte)
- 24 other customers with unique names

`customers.phone` reflects the **true current state** — i.e. if an agent's
`update_customer` call actually succeeded, the phone here is updated; if the
agent merely *claimed* success while the tool errored, the phone here is
unchanged. This is one of the cross-referencing signals for detecting
`unsupported_success`.

### `products`

24 products across Electronics/Computers/Appliances/Office/Accessories, with
`stock_quantity`. Several products are intentionally similar/confusable
(e.g. "Samsung TV 55-inch" vs "LG TV 55-inch", "iPhone 14" vs "iPhone 13"),
enabling the `wrong_record` failure type.

### `orders`

74 orders: most are pre-existing "baseline" ERP history (created before any
session), plus new orders created during `create_order` sessions. `status`
includes `pending_scheduling` for orders where a `create_order` tool call
technically succeeded but delivery was never actually scheduled
(`delivery_date IS NULL`) — the ground truth for that scenario.

### `invoices`

20 invoices tied to a subset of shipped/delivered orders, with `amount`,
`issued_date`, `paid_status`.

### `tool_definitions`

The 8 tools available to the agent: `find_customer`, `get_stock`, `find_order`,
`get_invoice`, `create_order`, `update_order`, `update_customer`,
`get_sales_report`. Each row has a `description` and a `parameters_json`
sketch of its arguments.

### `ground_truth` — hidden evaluation table

**Do not have your analyzer read this table.** It exists only so you can score
your own detector afterwards.

| column | notes |
|---|---|
| ground_truth_id | PK |
| session_id | FK → sessions (1 row per session) |
| outcome | `success` \| `recovered` \| `failed` \| `ambiguous` |
| failure_type | set only when `outcome = failed`: `unsupported_success` \| `repeated_question` \| `no_progress` \| `wrong_record` \| `incomplete_request` |
| recovery_type | set only when `outcome = recovered`: `retry_success` \| `search_refinement` \| `clarification_success` \| `corrected_tool_arguments` |
| ambiguity_type | set only when `outcome = ambiguous`: `multiple_customers` \| `multiple_orders` \| `missing_information` \| `unclear_user_intent` |
| severity | `low` \| `medium` \| `high`, set on failures |
| explanation | one-paragraph human explanation of the classification |
| evidence_event_ids | JSON array of the exact `event_id`s that justify the label |

No event or session row is tagged with an explicit `is_failure` flag — the
labels only exist in `ground_truth`, and the surface-level dialogue for a given
failure/recovery/ambiguity type intentionally overlaps with other outcomes for
the same scenario family (e.g. a retry pattern appears under both `recovered`
and `failed`; a "which Ahmed do you mean?" clarifying question appears under
both `ambiguous` and `success`/`recovered`). The distinguishing signal is always
in the actual tool arguments/results and how the conversation resolves, not in
any label baked into the event content.

## Scenario types (event_type patterns) and what they represent

- **`inventory_check`** — stock questions via `get_stock`. Includes clean
  success, a transient-DB-error retry that recovers, a `wrong_record` case
  (agent queries a similar-but-wrong product and reports its number as if it
  were the requested product), and an `unsupported_success` case (two failed
  lookups, agent invents a number anyway).
- **`customer_order_lookup`** — `find_customer` + `find_order` on ambiguous
  names ("Ahmed", "Mohamed Karray", "Sana Jlassi"). Covers: unique match,
  clarify-and-resolve (success), agent self-refines using context already in
  the message (`search_refinement`, recovered), two-round clarification
  (`clarification_success`, recovered), clarification with no reply
  (`multiple_customers`, ambiguous), repeating the identical ambiguous search
  3x with no refinement (`no_progress`, failed), and asking for info the user
  already gave (`repeated_question`, failed).
- **`update_customer`** — `update_customer` on a phone number. Covers success,
  a validation-error-then-corrected-format retry (recovered), and a write
  conflict where the agent claims success anyway (`unsupported_success`,
  failed — verifiable against `customers.phone`).
- **`create_order`** — `create_order` with a quantity/delivery date. Covers
  success, `incomplete_request` (delivery_date comes back `null` but the agent
  promises "tomorrow" anyway — verifiable against `orders.delivery_date`),
  a stock-limit error that the agent transparently negotiates down and retries
  (recovered/`corrected_tool_arguments`), and a transient-outage retry
  (recovered/`retry_success`).
- **`cancel_order`** — `find_order` + `update_order` to cancel. Covers a
  single-open-order success, multiple open orders with no reply
  (`multiple_orders`, ambiguous), and multiple open orders resolved by
  clarification (recovered).
- **`invoice_lookup`** — `get_invoice`. Covers success and a vague request with
  no order/customer specified (`missing_information`, ambiguous).
- **`sales_report`** — `get_sales_report`. Covers success and a vague request
  with no period/category specified (`unclear_user_intent`, ambiguous).

## Example SQL queries

**1. Reconstruct one session's full timeline**
```sql
SELECT sequence_number, timestamp, event_type, role, content, tool_name,
       tool_arguments_json, tool_result_json, tool_status
FROM events
WHERE session_id = 'S036'
ORDER BY sequence_number;
```

**2. All tool calls (with their paired results) for a session**
```sql
SELECT e1.sequence_number, e1.tool_name, e1.tool_arguments_json,
       e2.tool_result_json, e2.tool_status, e2.latency_ms
FROM events e1
JOIN events e2
  ON e2.session_id = e1.session_id
 AND e2.sequence_number = e1.sequence_number + 1
 AND e2.event_type = 'tool_result'
WHERE e1.session_id = 'S036' AND e1.event_type = 'tool_call'
ORDER BY e1.sequence_number;
```

**3. Sessions containing repeated identical tool calls (candidate no-progress patterns)**
```sql
SELECT session_id, tool_name, tool_arguments_json, COUNT(*) AS n
FROM events
WHERE event_type = 'tool_call'
GROUP BY session_id, tool_name, tool_arguments_json
HAVING COUNT(*) >= 2
ORDER BY n DESC;
```

**4. Count sessions by scenario type and outcome**
```sql
SELECT scenario_type, outcome, COUNT(*)
FROM sessions
GROUP BY scenario_type, outcome
ORDER BY scenario_type, outcome;
```

**5. All sessions with at least one tool error**
```sql
SELECT DISTINCT session_id, tool_name
FROM events
WHERE event_type = 'tool_result' AND tool_status = 'error';
```

**6. Join a `find_customer` tool result with the real customers table**
```sql
SELECT e.session_id, e.tool_arguments_json, c.customer_id, c.name, c.city, c.phone
FROM events e
JOIN customers c
  ON json_extract(e.tool_arguments_json, '$.query') = c.name
WHERE e.tool_name = 'find_customer' AND e.event_type = 'tool_call';
```

**7. Cross-check `update_customer` claims against the real customers table**
```sql
SELECT s.session_id, e.tool_arguments_json AS attempted_update,
       c.phone AS actual_current_phone
FROM sessions s
JOIN events e ON e.session_id = s.session_id AND e.tool_name = 'update_customer'
              AND e.event_type = 'tool_call'
JOIN customers c ON c.customer_id = json_extract(e.tool_arguments_json, '$.customer_id')
WHERE s.scenario_type = 'update_customer';
```

**8. Orders created with a delivery date that was never actually scheduled**
```sql
SELECT order_id, customer_id, product_id, status, delivery_date, created_at
FROM orders
WHERE delivery_date IS NULL;
```

**9. Full ground truth for one session, with its evidence events expanded**
```sql
SELECT * FROM ground_truth WHERE session_id = 'S036';
-- then, using evidence_event_ids (a JSON array):
SELECT * FROM events
WHERE event_id IN (SELECT value FROM json_each(
  (SELECT evidence_event_ids FROM ground_truth WHERE session_id = 'S036')
))
ORDER BY sequence_number;
```

**10. Distribution of failure/recovery/ambiguity subtypes**
```sql
SELECT outcome, failure_type, recovery_type, ambiguity_type, COUNT(*)
FROM ground_truth
GROUP BY outcome, failure_type, recovery_type, ambiguity_type
ORDER BY outcome;
```

## Recommended queries to run before building your analyzer

1. `SELECT outcome, COUNT(*) FROM sessions GROUP BY outcome;` — confirm the
   class balance.
2. `SELECT scenario_type, outcome, COUNT(*) FROM sessions GROUP BY 1,2 ORDER BY 1,2;`
   — see which scenario families produce which outcomes, and note that the
   same family produces multiple outcomes (this is the point).
3. Pick 2–3 `session_id`s per outcome class and read their full timelines with
   query #1 above, then read their `ground_truth` row, to build intuition for
   what "hidden" looks like here.
4. `SELECT * FROM ground_truth WHERE failure_type = 'wrong_record';` then read
   those sessions — notice the tool call *itself* reports `status = 'success'`.
5. `SELECT * FROM ground_truth WHERE outcome = 'ambiguous';` — confirm these
   all end on an agent clarifying question with no reply, and are not
   flagged as failures anywhere in the event data.
6. Run query #3 above (repeated tool calls) and manually compare its output
   against `ground_truth.failure_type = 'no_progress'` and
   `ground_truth.recovery_type = 'search_refinement'` sessions — the same
   surface signal ("same tool called twice") appears in both a failure and a
   non-failure, so a naive "count repeated calls" rule will misclassify some
   of them. That's intentional.
7. `SELECT * FROM orders WHERE delivery_date IS NULL;` then trace each
   `order_id` back to its session via
   `json_extract(tool_result_json,'$.order_id')` to see the corresponding
   `incomplete_request` session.

## Notes on design

- Every hidden failure is technically a "successful" tool call
  (`tool_status = 'success'`) except for `unsupported_success`, where the tool
  genuinely errored but the agent's final message claims otherwise — the
  point in both cases is that `tool_status` alone is not sufficient to judge
  the session; you need to compare the user's actual request, the tool
  arguments, the tool result, and the agent's final claim, and where
  relevant, the true state in `customers`/`orders`/`invoices`.
- Retries look identical at the surface (`tool_call` → `error` →
  `tool_call` → ...) whether they end in `recovered` or `failed` — what
  differs is whether the retry actually succeeded and whether the agent's
  final message matches that outcome.
- Clarifying questions on ambiguous names look identical whether the outcome
  is `success` (user answers, resolved), `recovered` (multiple rounds needed),
  or `ambiguous` (user never answers) — what differs is purely how the
  conversation ends.
