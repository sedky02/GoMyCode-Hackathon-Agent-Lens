#!/usr/bin/env python3
"""
Synthetic dataset generator for the SupplyzPro "Find the Hidden Failures" hackathon challenge.

Generates supplyzpro_agent_logs.db: a SQLite database of realistic multi-turn AI agent
sessions (an ERP assistant), with full event-level history (user messages, agent
messages, tool calls, tool results), master ERP data (customers, products, orders,
invoices), tool definitions, and a hidden ground_truth table for evaluation.

Run:
    python3 generate_dataset.py                              # the committed dataset (seed 42)
    python3 generate_dataset.py --seed 7 --out heldout.db    # same scenario templates, different entities and values

Recreates the database from scratch every time (deterministic, seeded RNG).
"""

import argparse
import sqlite3
import json
import random
import itertools
from datetime import datetime, timedelta

DB_PATH = "supplyzpro_agent_logs.db"
SEED = 42

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS ground_truth;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS tool_definitions;
DROP TABLE IF EXISTS sessions;

CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    ended_at        TEXT NOT NULL,
    scenario_type   TEXT NOT NULL,
    outcome         TEXT NOT NULL,   -- success | recovered | failed | ambiguous
    metadata        TEXT             -- JSON
);

CREATE TABLE customers (
    customer_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    phone           TEXT NOT NULL,
    email           TEXT NOT NULL,
    city            TEXT NOT NULL
);

CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    price           REAL NOT NULL,
    stock_quantity  INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id        TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers(customer_id),
    product_id      TEXT NOT NULL REFERENCES products(product_id),
    quantity        INTEGER NOT NULL,
    status          TEXT NOT NULL,   -- confirmed | processing | shipped | delivered | cancelled | pending_scheduling
    delivery_date   TEXT,            -- NULL allowed: represents a real un-scheduled delivery
    created_at      TEXT NOT NULL
);

CREATE TABLE invoices (
    invoice_id      TEXT PRIMARY KEY,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    amount          REAL NOT NULL,
    issued_date     TEXT NOT NULL,
    paid_status     TEXT NOT NULL    -- paid | unpaid | overdue
);

CREATE TABLE tool_definitions (
    tool_name       TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    parameters_json TEXT NOT NULL
);

CREATE TABLE events (
    event_id             INTEGER PRIMARY KEY,
    session_id           TEXT NOT NULL REFERENCES sessions(session_id),
    sequence_number      INTEGER NOT NULL,
    timestamp            TEXT NOT NULL,
    event_type           TEXT NOT NULL,   -- user_message | agent_message | tool_call | tool_result
    role                 TEXT NOT NULL,   -- user | assistant | tool
    content               TEXT NOT NULL,
    tool_name            TEXT,
    tool_arguments_json  TEXT,
    tool_result_json     TEXT,
    tool_status          TEXT,            -- success | error (tool_result events only)
    latency_ms           INTEGER
);

CREATE INDEX idx_events_session ON events(session_id, sequence_number);
CREATE INDEX idx_events_tool ON events(tool_name);

CREATE TABLE ground_truth (
    ground_truth_id      INTEGER PRIMARY KEY,
    session_id           TEXT NOT NULL REFERENCES sessions(session_id),
    outcome              TEXT NOT NULL,   -- success | recovered | failed | ambiguous
    failure_type         TEXT,            -- unsupported_success | repeated_question | no_progress | wrong_record | incomplete_request
    recovery_type        TEXT,            -- retry_success | search_refinement | clarification_success | corrected_tool_arguments | alternative_tool_success
    ambiguity_type       TEXT,            -- multiple_customers | multiple_orders | missing_information | unclear_user_intent
    severity             TEXT,            -- low | medium | high (failures only)
    explanation          TEXT NOT NULL,
    evidence_event_ids   TEXT NOT NULL    -- JSON array of event_id
);
"""

# ---------------------------------------------------------------------------
# Master data definitions
# ---------------------------------------------------------------------------

# (name, city) — first 8 are intentionally ambiguous (duplicate/shared names)
CUSTOMER_SEED = [
    ("Ahmed Ben Ali", "Tunis"),
    ("Ahmed Ben Salah", "Sfax"),
    ("Ahmed Trabelsi", "Sousse"),
    ("Ahmed Gharbi", "Tunis"),
    ("Mohamed Karray", "Tunis"),
    ("Mohamed Karray", "Sfax"),
    ("Sana Jlassi", "Tunis"),
    ("Sana Jlassi", "Bizerte"),
    ("Salma Bouazizi", "Ariana"),
    ("Karim Cherif", "Sousse"),
    ("Ines Mejri", "Tunis"),
    ("Walid Haddad", "Nabeul"),
    ("Nour Abidi", "Monastir"),
    ("Rania Fekih", "Tunis"),
    ("Omar Chaabane", "Sfax"),
    ("Leila Snoussi", "Gabes"),
    ("Hedi Mansour", "Tunis"),
    ("Amira Zouari", "Sfax"),
    ("Bilel Rekik", "Kairouan"),
    ("Syrine Gharsallah", "Tunis"),
    ("Anis Belhaj", "Bizerte"),
    ("Mariem Souissi", "Sousse"),
    ("Tarek Jendoubi", "Jendouba"),
    ("Nesrine Kahlaoui", "Tunis"),
    ("Ziad Chtioui", "Sfax"),
    ("Dorra Ayari", "Ariana"),
    ("Mehdi Slim", "Tunis"),
    ("Hana Bouzidi", "Nabeul"),
    ("Sami Aouadi", "Sousse"),
    ("Ghada Riahi", "Tunis"),
    ("Fares Ltaief", "Sfax"),
    ("Yosra Ben Romdhane", "Monastir"),
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "supplyzpro-client.com"]

PRODUCT_SEED = [
    ("Samsung TV 43-inch", "Electronics", 450.0, 22),
    ("Samsung TV 55-inch", "Electronics", 620.0, 37),
    ("Samsung TV 65-inch", "Electronics", 890.0, 11),
    ("LG TV 55-inch", "Electronics", 580.0, 52),
    ("LG TV 65-inch", "Electronics", 860.0, 18),
    ("Sony TV 50-inch", "Electronics", 610.0, 14),
    ("iPhone 13", "Electronics", 699.0, 40),
    ("iPhone 14", "Electronics", 799.0, 28),
    ("iPhone 15", "Electronics", 899.0, 33),
    ("Samsung Galaxy A54", "Electronics", 399.0, 60),
    ("Samsung Galaxy S23", "Electronics", 749.0, 25),
    ("Dell Inspiron 15", "Computers", 520.0, 19),
    ("HP Pavilion 14", "Computers", 540.0, 21),
    ("Lenovo ThinkPad E14", "Computers", 610.0, 15),
    ("MacBook Air M2", "Computers", 1150.0, 9),
    ("Samsung Refrigerator 350L", "Appliances", 480.0, 12),
    ("LG Washing Machine 8kg", "Appliances", 430.0, 17),
    ("Samsung Microwave 25L", "Appliances", 120.0, 44),
    ("HP LaserJet Printer", "Office", 210.0, 26),
    ("Canon Scanner", "Office", 160.0, 20),
    ("Office Desk Chair", "Office", 95.0, 55),
    ("Standing Desk", "Office", 275.0, 30),
    ("Wireless Mouse", "Accessories", 18.0, 150),
    ("Bluetooth Speaker", "Accessories", 45.0, 80),
]

CONFUSION_PAIRS = [
    ("Samsung TV 55-inch", "LG TV 55-inch"),
    ("iPhone 14", "iPhone 13"),
    ("Samsung Galaxy A54", "Samsung Galaxy S23"),
    ("Samsung TV 43-inch", "Samsung TV 65-inch"),
    ("HP Pavilion 14", "Dell Inspiron 15"),
]

TOOL_DEFINITIONS = [
    ("find_customer", "Search the customer database by name, phone, or email. May return zero, one, or multiple matches.",
     {"query": "string (name, phone, or email fragment)", "city": "string (optional filter)"}),
    ("get_stock", "Look up the current stock quantity and warehouse for a product by name.",
     {"product_name": "string"}),
    ("find_order", "Search orders by customer_id, order_id, or product name. May return multiple matches.",
     {"customer_id": "string (optional)", "order_id": "string (optional)", "product_name": "string (optional)"}),
    ("get_invoice", "Retrieve invoice details for a given order_id.",
     {"order_id": "string"}),
    ("create_order", "Create a new order for a customer.",
     {"customer_id": "string", "product_id": "string", "quantity": "integer", "delivery_date": "string (YYYY-MM-DD, optional)"}),
    ("update_order", "Update fields on an existing order (e.g. status, delivery_date).",
     {"order_id": "string", "fields": "object"}),
    ("update_customer", "Update contact fields on an existing customer record.",
     {"customer_id": "string", "fields": "object"}),
    ("get_sales_report", "Generate an aggregated sales report for a period and optional category.",
     {"period": "string (YYYY-MM, optional)", "category": "string (optional)"}),
]

# ---------------------------------------------------------------------------
# World state (built once, then mutated as sessions are generated)
# ---------------------------------------------------------------------------

class World:
    def __init__(self, rng):
        self.rng = rng
        self.customers = {}       # customer_id -> dict
        self.products = {}        # product_id -> dict
        self.products_by_name = {}
        self.orders = {}          # order_id -> dict
        self.invoices = {}        # invoice_id -> dict
        self.order_counter = itertools.count(1)
        self.invoice_counter = itertools.count(1)

    def new_order_id(self):
        return f"O{next(self.order_counter):04d}"

    def new_invoice_id(self):
        return f"INV{next(self.invoice_counter):04d}"


def build_customers(world):
    for i, (name, city) in enumerate(CUSTOMER_SEED, start=1):
        cid = f"C{i:03d}"
        first = name.split()[0].lower()
        last = name.split()[-1].lower()
        phone = f"+216-{20 + (i * 3) % 9}{10000000 + i * 137 % 8999999:07d}"
        domain = EMAIL_DOMAINS[i % len(EMAIL_DOMAINS)]
        email = f"{first}.{last}{i}@{domain}"
        world.customers[cid] = {
            "customer_id": cid, "name": name, "phone": phone, "email": email, "city": city,
        }
    ids = list(world.customers.keys())
    world.ahmed_ids = ids[0:4]
    world.mohamed_ids = ids[4:6]
    world.sana_ids = ids[6:8]
    world.ambiguous_groups = [
        ("Ahmed", world.ahmed_ids),
        ("Mohamed Karray", world.mohamed_ids),
        ("Sana Jlassi", world.sana_ids),
    ]
    world.unique_ids = ids[8:]


def build_products(world):
    for i, (name, category, price, stock) in enumerate(PRODUCT_SEED, start=1):
        pid = f"P{i:03d}"
        world.products[pid] = {
            "product_id": pid, "name": name, "category": category,
            "price": price, "stock_quantity": stock,
        }
        world.products_by_name[name] = pid


def build_baseline_orders(world, base_date):
    rng = world.rng
    statuses_open = ["confirmed", "processing", "shipped", "delivered"]
    for cid in world.customers:
        n_orders = rng.choice([1, 1, 1, 2, 2, 3])
        for _ in range(n_orders):
            pid = rng.choice(list(world.products.keys()))
            product = world.products[pid]
            qty = rng.randint(1, 4)
            created_at = base_date - timedelta(days=rng.randint(3, 90), hours=rng.randint(0, 10))
            status = rng.choices(statuses_open, weights=[2, 2, 3, 3])[0]
            delivery_date = (created_at + timedelta(days=rng.randint(1, 10))).date().isoformat()
            oid = world.new_order_id()
            world.orders[oid] = {
                "order_id": oid, "customer_id": cid, "product_id": pid,
                "quantity": qty, "status": status, "delivery_date": delivery_date,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if status in ("shipped", "delivered") and rng.random() < 0.7:
                amount = round(product["price"] * qty * rng.uniform(0.97, 1.0), 2)
                issued = (created_at + timedelta(days=1)).date().isoformat()
                paid = rng.choices(["paid", "unpaid", "overdue"], weights=[6, 3, 1])[0]
                iid = world.new_invoice_id()
                world.invoices[iid] = {
                    "invoice_id": iid, "order_id": oid, "amount": amount,
                    "issued_date": issued, "paid_status": paid,
                }


def customer_open_orders(world, customer_id):
    return [o for o in world.orders.values()
            if o["customer_id"] == customer_id and o["status"] != "cancelled"]


def customers_with_multiple_open_orders(world):
    result = []
    for cid in world.customers:
        if len(customer_open_orders(world, cid)) >= 2:
            result.append(cid)
    return result

# ---------------------------------------------------------------------------
# Session/event construction helpers
# ---------------------------------------------------------------------------

EVENT_ID_SEQ = itertools.count(1)


class SessionBuilder:
    def __init__(self, session_id, start_time, rng):
        self.session_id = session_id
        self.t = start_time
        self.seq = 1
        self.events = []
        self.rng = rng

    def _advance(self, gap):
        self.t = self.t + timedelta(seconds=gap)
        return self.t

    def add(self, event_type, role, content, tool_name=None, tool_arguments=None,
            tool_result=None, tool_status=None, latency_ms=None, gap=None):
        if gap is None:
            gap = self.rng.randint(2, 10)
        ts = self._advance(gap)
        ev = {
            "event_id": next(EVENT_ID_SEQ),
            "session_id": self.session_id,
            "sequence_number": self.seq,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
            "role": role,
            "content": content,
            "tool_name": tool_name,
            "tool_arguments_json": json.dumps(tool_arguments) if tool_arguments is not None else None,
            "tool_result_json": json.dumps(tool_result) if tool_result is not None else None,
            "tool_status": tool_status,
            "latency_ms": latency_ms,
        }
        self.seq += 1
        self.events.append(ev)
        return ev

    def user(self, content):
        return self.add("user_message", "user", content, gap=self.rng.randint(15, 240))

    def agent(self, content):
        return self.add("agent_message", "assistant", content, gap=self.rng.randint(3, 25))

    def call(self, tool_name, args, result, status="success", latency=None):
        if latency is None:
            latency = self.rng.randint(120, 900) if status == "success" else self.rng.randint(400, 4000)
        c = self.add("tool_call", "assistant", f"Agent invokes {tool_name}",
                      tool_name=tool_name, tool_arguments=args, gap=self.rng.randint(1, 3))
        r = self.add("tool_result", "tool",
                      f"{tool_name} returned {'an error' if status == 'error' else 'a result'}",
                      tool_name=tool_name, tool_result=result, tool_status=status,
                      latency_ms=latency, gap=self.rng.randint(1, 2))
        return c, r


def gt(outcome, explanation, evidence, failure_type=None, recovery_type=None,
       ambiguity_type=None, severity=None):
    return {
        "outcome": outcome,
        "failure_type": failure_type,
        "recovery_type": recovery_type,
        "ambiguity_type": ambiguity_type,
        "severity": severity,
        "explanation": explanation,
        "evidence_event_ids": [e["event_id"] for e in evidence],
    }

# ---------------------------------------------------------------------------
# Scenario family A: inventory_check (get_stock)
# ---------------------------------------------------------------------------

INVENTORY_QUESTIONS = [
    "How many {p} do we have in stock?",
    "Can you check the stock level for {p}?",
    "What's our current inventory for {p}?",
    "I need to know how many {p} units are available.",
]
INVENTORY_ANSWERS = [
    "You currently have {q} units of {p} in stock.",
    "We have {q} {p} available right now.",
]


def gen_inventory(ctx, variant, world):
    rng = ctx.rng
    if variant == "wrong_record":
        requested_name, wrong_name = rng.choice(CONFUSION_PAIRS)
        requested_id = world.products_by_name[requested_name]
        wrong_id = world.products_by_name[wrong_name]
        requested = world.products[requested_id]
        wrong = world.products[wrong_id]
    else:
        pid = rng.choice(list(world.products.keys()))
        requested = world.products[pid]

    if variant == "success":
        u = ctx.user(rng.choice(INVENTORY_QUESTIONS).format(p=requested["name"]))
        ctx.agent("Sure, let me check that for you.")
        c, r = ctx.call("get_stock", {"product_name": requested["name"]},
                         {"product_id": requested["product_id"], "product_name": requested["name"],
                          "stock_quantity": requested["stock_quantity"], "warehouse": "Main Warehouse"})
        af = ctx.agent(rng.choice(INVENTORY_ANSWERS).format(q=requested["stock_quantity"], p=requested["name"]))
        return gt("success",
                   f"The agent queried the exact product the user asked about ({requested['name']}) and "
                   f"reported the stock quantity returned by the tool without alteration.",
                   [u, c, r, af])

    if variant == "retry_success":
        u = ctx.user(rng.choice(INVENTORY_QUESTIONS).format(p=requested["name"]))
        c1, r1 = ctx.call("get_stock", {"product_name": requested["name"]},
                           {"error": "Database connection timeout, please retry."}, status="error")
        a_retry = ctx.agent("I ran into a temporary issue retrieving that. Let me try again.")
        c2, r2 = ctx.call("get_stock", {"product_name": requested["name"]},
                           {"product_id": requested["product_id"], "product_name": requested["name"],
                            "stock_quantity": requested["stock_quantity"], "warehouse": "Main Warehouse"})
        af = ctx.agent(rng.choice(INVENTORY_ANSWERS).format(q=requested["stock_quantity"], p=requested["name"]))
        return gt("recovered",
                   "The first stock lookup failed with a transient database timeout. The agent retried the "
                   "identical query, the retry succeeded, and the reported quantity matches the tool result.",
                   [c1, r1, c2, r2, af], recovery_type="retry_success")

    if variant == "wrong_record":
        u = ctx.user(rng.choice(INVENTORY_QUESTIONS).format(p=requested["name"]))
        ctx.agent("Sure, let me check that for you.")
        c, r = ctx.call("get_stock", {"product_name": wrong["name"]},
                         {"product_id": wrong["product_id"], "product_name": wrong["name"],
                          "stock_quantity": wrong["stock_quantity"], "warehouse": "Main Warehouse"})
        af = ctx.agent(f"You currently have {wrong['stock_quantity']} units of {requested['name']} in stock.")
        return gt("failed",
                   f"The user asked about stock for '{requested['name']}' but the agent queried "
                   f"'{wrong['name']}' instead (a similar but different product) and reported that quantity "
                   f"as if it belonged to the requested product. The tool call itself succeeded, so the error "
                   f"is hidden unless the requested product name is compared against the tool_arguments_json.",
                   [u, c, r, af], failure_type="wrong_record", severity="medium")

    if variant == "unsupported_success":
        u = ctx.user(rng.choice(INVENTORY_QUESTIONS).format(p=requested["name"]))
        c1, r1 = ctx.call("get_stock", {"product_name": requested["name"]},
                           {"error": "Database connection timeout, please retry."}, status="error")
        a_retry = ctx.agent("Let me try that again.")
        c2, r2 = ctx.call("get_stock", {"product_name": requested["name"]},
                           {"error": "Database connection timeout, please retry."}, status="error")
        af = ctx.agent(rng.choice(INVENTORY_ANSWERS).format(q=requested["stock_quantity"], p=requested["name"]))
        return gt("failed",
                   "Both stock lookups failed with database errors, yet the agent reported a specific stock "
                   "quantity that was never confirmed by any successful tool result.",
                   [c1, r1, c2, r2, af], failure_type="unsupported_success", severity="high")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Scenario family B: customer_order_lookup (find_customer, find_order)
# ---------------------------------------------------------------------------

def _matches(world, ids):
    return [{"customer_id": cid, "name": world.customers[cid]["name"], "city": world.customers[cid]["city"]}
            for cid in ids]


def gen_customer_lookup(ctx, variant, world):
    rng = ctx.rng

    if variant == "success_unique":
        cid = rng.choice(world.unique_ids)
        cust = world.customers[cid]
        open_orders = customer_open_orders(world, cid)
        order = rng.choice(open_orders) if open_orders else None
        u = ctx.user(f"Can you find the latest order for {cust['name']}?")
        ctx.agent("Sure, one moment.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        if order:
            product = world.products[order["product_id"]]
            c2, r2 = ctx.call("find_order", {"customer_id": cid},
                               {"orders": [{"order_id": order["order_id"], "product": product["name"],
                                             "quantity": order["quantity"], "status": order["status"]}], "count": 1})
            af = ctx.agent(f"{cust['name']}'s latest order is #{order['order_id']} for {order['quantity']}x "
                            f"{product['name']} (status: {order['status']}).")
            evidence = [u, c1, r1, c2, r2, af]
        else:
            c2, r2 = ctx.call("find_order", {"customer_id": cid}, {"orders": [], "count": 0})
            af = ctx.agent(f"I couldn't find any orders on file for {cust['name']}.")
            evidence = [u, c1, r1, c2, r2, af]
        return gt("success", f"The agent found the single matching customer and reported the correct order "
                              f"on the first attempt.", evidence)

    if variant == "success_clarify":
        stem, ids = rng.choice(world.ambiguous_groups)
        target = rng.choice(ids)
        target_cust = world.customers[target]
        u = ctx.user(f"Find {stem}'s order.")
        c1, r1 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        names = ", ".join(f"{world.customers[i]['name']} ({world.customers[i]['city']})" for i in ids)
        a1 = ctx.agent(f"I found multiple customers matching '{stem}': {names}. Which one did you mean?")
        u2 = ctx.user(f"{target_cust['name']}, the one in {target_cust['city']}.")
        c2, r2 = ctx.call("find_customer", {"query": target_cust["name"], "city": target_cust["city"]},
                           {"matches": _matches(world, [target])[0:1] or [_matches(world, [target])[0]], "count": 1})
        open_orders = customer_open_orders(world, target)
        if open_orders:
            order = rng.choice(open_orders)
            product = world.products[order["product_id"]]
            c3, r3 = ctx.call("find_order", {"customer_id": target},
                               {"orders": [{"order_id": order["order_id"], "product": product["name"],
                                             "quantity": order["quantity"], "status": order["status"]}], "count": 1})
            af = ctx.agent(f"{target_cust['name']}'s latest order is #{order['order_id']} for "
                            f"{order['quantity']}x {product['name']} (status: {order['status']}).")
            evidence = [u, c1, r1, a1, u2, c2, r2, c3, r3, af]
        else:
            c3, r3 = ctx.call("find_order", {"customer_id": target}, {"orders": [], "count": 0})
            af = ctx.agent(f"I couldn't find any orders on file for {target_cust['name']}.")
            evidence = [u, c1, r1, a1, u2, c2, r2, c3, r3, af]
        return gt("success",
                   "The request was genuinely ambiguous (multiple customers with the same name). The agent "
                   "asked a clarifying question, the user answered, and the agent correctly resolved the "
                   "request. Asking for clarification on a truly ambiguous name is normal, correct behavior.",
                   evidence)

    if variant == "search_refinement":
        stem, ids = rng.choice(world.ambiguous_groups)
        target = rng.choice(ids)
        target_cust = world.customers[target]
        u = ctx.user(f"Find {stem}'s order, the one from {target_cust['city']}.")
        c1, r1 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        c2, r2 = ctx.call("find_customer", {"query": stem, "city": target_cust["city"]},
                           {"matches": [_matches(world, [target])[0]], "count": 1})
        open_orders = customer_open_orders(world, target)
        order = rng.choice(open_orders) if open_orders else None
        if order:
            product = world.products[order["product_id"]]
            c3, r3 = ctx.call("find_order", {"customer_id": target},
                               {"orders": [{"order_id": order["order_id"], "product": product["name"],
                                             "quantity": order["quantity"], "status": order["status"]}], "count": 1})
            af = ctx.agent(f"{target_cust['name']}'s latest order is #{order['order_id']} for "
                            f"{order['quantity']}x {product['name']} (status: {order['status']}).")
            evidence = [u, c1, r1, c2, r2, c3, r3, af]
        else:
            c3, r3 = ctx.call("find_order", {"customer_id": target}, {"orders": [], "count": 0})
            af = ctx.agent(f"I couldn't find any orders on file for {target_cust['name']}.")
            evidence = [u, c1, r1, c2, r2, c3, r3, af]
        return gt("recovered",
                   "The first search for the shared name returned multiple matches. Instead of asking the "
                   "user again, the agent noticed the city detail already present in the user's message and "
                   "used it to refine the search itself, reaching a unique match without extra back-and-forth.",
                   evidence, recovery_type="search_refinement")

    if variant == "clarification_recovered":
        stem, ids = rng.choice(world.ambiguous_groups)
        # pick two ids sharing the same city to force a second ambiguous round
        by_city = {}
        for i in ids:
            by_city.setdefault(world.customers[i]["city"], []).append(i)
        multi_city = [city for city, lst in by_city.items() if len(lst) >= 2]
        if not multi_city:
            # fall back: just reuse ids[:2] and pretend same city for narrative purposes
            city = world.customers[ids[0]]["city"]
            same_city_ids = ids[:2]
        else:
            city = rng.choice(multi_city)
            same_city_ids = by_city[city]
        target = rng.choice(same_city_ids)
        target_cust = world.customers[target]
        u = ctx.user(f"Find {stem}'s order.")
        c1, r1 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        names_all = ", ".join(world.customers[i]["name"] for i in ids)
        a1 = ctx.agent(f"I found several customers matching '{stem}': {names_all}. Which one did you mean?")
        u2 = ctx.user(f"The one from {city}.")
        c2, r2 = ctx.call("find_customer", {"query": stem, "city": city},
                           {"matches": _matches(world, same_city_ids), "count": len(same_city_ids)})
        a2 = ctx.agent(f"There are still {len(same_city_ids)} customers named {stem} in {city}: "
                        f"{', '.join(world.customers[i]['name'] for i in same_city_ids)}. Could you confirm "
                        f"the full name?")
        u3 = ctx.user(f"{target_cust['name']}.")
        c3, r3 = ctx.call("find_customer", {"query": target_cust["name"]},
                           {"matches": [_matches(world, [target])[0]], "count": 1})
        open_orders = customer_open_orders(world, target)
        order = rng.choice(open_orders) if open_orders else None
        if order:
            product = world.products[order["product_id"]]
            c4, r4 = ctx.call("find_order", {"customer_id": target},
                               {"orders": [{"order_id": order["order_id"], "product": product["name"],
                                             "quantity": order["quantity"], "status": order["status"]}], "count": 1})
            af = ctx.agent(f"{target_cust['name']}'s latest order is #{order['order_id']} for "
                            f"{order['quantity']}x {product['name']} (status: {order['status']}).")
            evidence = [u, c1, r1, a1, u2, c2, r2, a2, u3, c3, r3, c4, r4, af]
        else:
            c4, r4 = ctx.call("find_order", {"customer_id": target}, {"orders": [], "count": 0})
            af = ctx.agent(f"I couldn't find any orders on file for {target_cust['name']}.")
            evidence = [u, c1, r1, a1, u2, c2, r2, a2, u3, c3, r3, c4, r4, af]
        return gt("recovered",
                   "The name was ambiguous at two levels (multiple people with the same name, then multiple "
                   "in the same city). The agent's first clarifying question was insufficient, but it "
                   "recognized the residual ambiguity, asked a second time, and correctly resolved the "
                   "request once the full name was confirmed.",
                   evidence, recovery_type="clarification_success")

    if variant == "multiple_customers":
        stem, ids = rng.choice(world.ambiguous_groups)
        u = ctx.user(f"Find {stem}'s order.")
        c1, r1 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        names = ", ".join(f"{world.customers[i]['name']} ({world.customers[i]['city']})" for i in ids)
        a1 = ctx.agent(f"I found multiple customers matching '{stem}': {names}. Which one did you mean?")
        return gt("ambiguous",
                   "The name matched several customers and the agent correctly asked which one the user "
                   "meant. The user never replied, so the session ends without resolution. This is not a "
                   "failure: the agent behaved correctly given genuinely ambiguous input.",
                   [u, c1, r1, a1], ambiguity_type="multiple_customers")

    if variant == "no_progress":
        stem, ids = rng.choice(world.ambiguous_groups)
        u = ctx.user(f"Find {stem}'s order.")
        c1, r1 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        a1 = ctx.agent("Let me check that.")
        c2, r2 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        a2 = ctx.agent("One moment, checking again.")
        c3, r3 = ctx.call("find_customer", {"query": stem},
                           {"matches": _matches(world, ids), "count": len(ids)})
        af = ctx.agent("I'm having some trouble finding the right match, let me look into it.")
        return gt("failed",
                   f"The agent issued the exact same '{stem}' search three times in a row, receiving the "
                   f"identical ambiguous result each time. It never refined the query and never asked the "
                   f"user a clarifying question, so no progress was made toward resolving the request.",
                   [c1, r1, c2, r2, c3, r3, af], failure_type="no_progress", severity="medium")

    if variant == "repeated_question":
        cid = rng.choice(world.unique_ids)
        cust = world.customers[cid]
        u = ctx.user(f"Find the order for {cust['name']}, phone {cust['phone']}.")
        a1 = ctx.agent("Sure, could you tell me the customer's name?")
        u2 = ctx.user(f"I just gave it to you — {cust['name']}.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        open_orders = customer_open_orders(world, cid)
        order = rng.choice(open_orders) if open_orders else None
        if order:
            product = world.products[order["product_id"]]
            c2, r2 = ctx.call("find_order", {"customer_id": cid},
                               {"orders": [{"order_id": order["order_id"], "product": product["name"],
                                             "quantity": order["quantity"], "status": order["status"]}], "count": 1})
            af = ctx.agent(f"{cust['name']}'s latest order is #{order['order_id']} for {order['quantity']}x "
                            f"{product['name']} (status: {order['status']}).")
            evidence = [u, a1, u2, c1, r1, c2, r2, af]
        else:
            c2, r2 = ctx.call("find_order", {"customer_id": cid}, {"orders": [], "count": 0})
            af = ctx.agent(f"I couldn't find any orders on file for {cust['name']}.")
            evidence = [u, a1, u2, c1, r1, c2, r2, af]
        return gt("failed",
                   "The user already provided the customer's full name in their first message, but the "
                   "agent asked for it again instead of using the information already given. The final "
                   "answer may still be correct, but the agent failed to track information already present "
                   "in the conversation.",
                   evidence, failure_type="repeated_question", severity="low")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Scenario family C: update_customer
# ---------------------------------------------------------------------------

def gen_update_customer(ctx, variant, world):
    rng = ctx.rng
    cid = rng.choice(world.unique_ids + world.ahmed_ids)
    cust = world.customers[cid]
    new_local = f"{rng.randint(20, 29)}{rng.randint(100000, 999999)}"

    if variant == "success":
        u = ctx.user(f"Please update {cust['name']}'s phone number to {new_local}.")
        ctx.agent("Sure, let me pull up that customer's record.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        new_phone = f"+216-{new_local}"
        c2, r2 = ctx.call("update_customer", {"customer_id": cid, "fields": {"phone": new_phone}},
                           {"customer_id": cid, "updated_fields": ["phone"], "status": "updated"})
        af = ctx.agent(f"Done — {cust['name']}'s phone number has been updated to {new_phone}.")
        cust["phone"] = new_phone  # master data reflects the real, successful update
        return gt("success",
                   "The update tool call succeeded and the agent reported exactly the field and value that "
                   "were confirmed by the tool result.",
                   [u, c1, r1, c2, r2, af])

    if variant == "corrected_args":
        u = ctx.user(f"Please update {cust['name']}'s phone number to {new_local}.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        c2, r2 = ctx.call("update_customer", {"customer_id": cid, "fields": {"phone": new_local}},
                           {"error": "Validation failed: phone must include country code (+216)."}, status="error")
        a_fix = ctx.agent("Let me fix the phone format and try again.")
        new_phone = f"+216-{new_local}"
        c3, r3 = ctx.call("update_customer", {"customer_id": cid, "fields": {"phone": new_phone}},
                           {"customer_id": cid, "updated_fields": ["phone"], "status": "updated"})
        af = ctx.agent(f"Done — {cust['name']}'s phone number has been updated to {new_phone}.")
        cust["phone"] = new_phone
        return gt("recovered",
                   "The first update attempt failed validation because the phone number was missing the "
                   "country code. The agent corrected the argument format and retried, and the second "
                   "attempt succeeded with the correct value confirmed by the tool.",
                   [c1, r1, c2, r2, c3, r3, af], recovery_type="corrected_tool_arguments")

    if variant == "unsupported_success":
        u = ctx.user(f"Please update {cust['name']}'s phone number to {new_local}.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        new_phone = f"+216-{new_local}"
        c2, r2 = ctx.call("update_customer", {"customer_id": cid, "fields": {"phone": new_phone}},
                           {"error": "Database write conflict, the record could not be saved."}, status="error")
        af = ctx.agent(f"Done, {cust['name']}'s phone number has been updated.")
        # customers table intentionally NOT mutated: the update never actually happened
        return gt("failed",
                   "The update_customer call returned an error (write conflict) and the phone number was "
                   "never actually changed, yet the agent told the user it was done. Cross-referencing the "
                   "tool_result_json (error) or the customers table (unchanged phone) against the agent's "
                   "claim reveals the failure.",
                   [c1, r1, c2, r2, af], failure_type="unsupported_success", severity="high")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Scenario family D: create_order
# ---------------------------------------------------------------------------

def gen_create_order(ctx, variant, world):
    rng = ctx.rng
    cid = rng.choice(world.unique_ids)
    cust = world.customers[cid]
    pid = rng.choice(list(world.products.keys()))
    product = world.products[pid]
    qty = rng.randint(2, 10)
    created_at = ctx.t

    if variant == "success":
        delivery = (created_at + timedelta(days=1)).date().isoformat()
        u = ctx.user(f"Create an order for {qty} {product['name']} for {cust['name']}, deliver tomorrow.")
        ctx.agent("Sure, let me set that up.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        oid = world.new_order_id()
        c2, r2 = ctx.call("create_order",
                           {"customer_id": cid, "product_id": pid, "quantity": qty, "delivery_date": delivery},
                           {"order_id": oid, "status": "confirmed", "delivery_date": delivery})
        af = ctx.agent(f"Your order for {qty}x {product['name']} has been created (#{oid}) and will be "
                        f"delivered on {delivery}.")
        world.orders[oid] = {"order_id": oid, "customer_id": cid, "product_id": pid, "quantity": qty,
                              "status": "confirmed", "delivery_date": delivery,
                              "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S")}
        return gt("success",
                   "The order was created with the exact delivery date confirmed by the tool result, and "
                   "the agent's message matches that date.",
                   [u, c1, r1, c2, r2, af])

    if variant == "incomplete_request":
        u = ctx.user(f"Create an order for {qty} {product['name']} for {cust['name']} and deliver it tomorrow.")
        ctx.agent("Sure, let me set that up.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        oid = world.new_order_id()
        c2, r2 = ctx.call("create_order",
                           {"customer_id": cid, "product_id": pid, "quantity": qty, "delivery_date": "tomorrow"},
                           {"order_id": oid, "status": "pending_scheduling", "delivery_date": None,
                            "note": "delivery date not yet scheduled, pending logistics confirmation"})
        af = ctx.agent(f"Your order for {qty}x {product['name']} has been created (#{oid}) and will be "
                        f"delivered tomorrow.")
        world.orders[oid] = {"order_id": oid, "customer_id": cid, "product_id": pid, "quantity": qty,
                              "status": "pending_scheduling", "delivery_date": None,
                              "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S")}
        return gt("failed",
                   "The tool result shows delivery_date = null and status = pending_scheduling — the order "
                   "was created but no delivery was actually scheduled. The agent nonetheless told the user "
                   "it would be delivered tomorrow, a promise the system cannot back up.",
                   [u, c1, r1, c2, r2, af], failure_type="incomplete_request", severity="high")

    if variant == "corrected_args":
        big_qty = qty + rng.randint(8, 15)
        available = product["stock_quantity"]
        u = ctx.user(f"Create an order for {big_qty} {product['name']} for {cust['name']}.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        c2, r2 = ctx.call("create_order", {"customer_id": cid, "product_id": pid, "quantity": big_qty},
                           {"error": f"Insufficient stock: only {available} units available."}, status="error")
        a_ask = ctx.agent(f"We only have {available} units of {product['name']} in stock right now — "
                           f"would you like me to proceed with {available} instead?")
        u2 = ctx.user(f"Yes, go ahead with {available}.")
        oid = world.new_order_id()
        delivery = (created_at + timedelta(days=3)).date().isoformat()
        c3, r3 = ctx.call("create_order",
                           {"customer_id": cid, "product_id": pid, "quantity": available, "delivery_date": delivery},
                           {"order_id": oid, "status": "confirmed", "delivery_date": delivery})
        af = ctx.agent(f"Your order for {available}x {product['name']} has been created (#{oid}), delivery "
                        f"expected {delivery}.")
        world.orders[oid] = {"order_id": oid, "customer_id": cid, "product_id": pid, "quantity": available,
                              "status": "confirmed", "delivery_date": delivery,
                              "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S")}
        return gt("recovered",
                   "The first order attempt exceeded available stock and failed. The agent transparently "
                   "informed the user of the real stock limit, got confirmation, and retried with corrected, "
                   "smaller quantity, which succeeded.",
                   [c1, r1, c2, r2, a_ask, u2, c3, r3, af], recovery_type="corrected_tool_arguments")

    if variant == "retry_success":
        delivery = (created_at + timedelta(days=2)).date().isoformat()
        u = ctx.user(f"Create an order for {qty} {product['name']} for {cust['name']}.")
        c1, r1 = ctx.call("find_customer", {"query": cust["name"]},
                           {"matches": [_matches(world, [cid])[0]], "count": 1})
        c2, r2 = ctx.call("create_order", {"customer_id": cid, "product_id": pid, "quantity": qty},
                           {"error": "Order service temporarily unavailable, please retry."}, status="error")
        a_retry = ctx.agent("The order service timed out, let me try that again.")
        oid = world.new_order_id()
        c3, r3 = ctx.call("create_order",
                           {"customer_id": cid, "product_id": pid, "quantity": qty, "delivery_date": delivery},
                           {"order_id": oid, "status": "confirmed", "delivery_date": delivery})
        af = ctx.agent(f"Your order for {qty}x {product['name']} has been created (#{oid}), delivery expected "
                        f"{delivery}.")
        world.orders[oid] = {"order_id": oid, "customer_id": cid, "product_id": pid, "quantity": qty,
                              "status": "confirmed", "delivery_date": delivery,
                              "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S")}
        return gt("recovered",
                   "The first create_order call failed due to a transient service outage. The agent retried "
                   "the identical request and it succeeded on the second attempt.",
                   [c1, r1, c2, r2, c3, r3, af], recovery_type="retry_success")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Scenario family E: cancel_order (update_order)
# ---------------------------------------------------------------------------

def gen_cancel_order(ctx, variant, world):
    rng = ctx.rng

    if variant in ("success",):
        candidates = [cid for cid in world.customers if len(customer_open_orders(world, cid)) == 1]
        cid = rng.choice(candidates) if candidates else rng.choice(list(world.customers.keys()))
        cust = world.customers[cid]
        open_orders = customer_open_orders(world, cid)
        order = open_orders[0] if open_orders else None
        if order is None:
            oid = world.new_order_id()
            pid = rng.choice(list(world.products.keys()))
            order = {"order_id": oid, "customer_id": cid, "product_id": pid, "quantity": 1,
                     "status": "confirmed", "delivery_date": None, "created_at": ctx.t.strftime("%Y-%m-%d %H:%M:%S")}
            world.orders[oid] = order
        product = world.products[order["product_id"]]
        u = ctx.user(f"Please cancel my order for the {product['name']}, this is {cust['name']}.")
        ctx.agent("Sure, let me look that up.")
        c1, r1 = ctx.call("find_order", {"customer_id": cid},
                           {"orders": [{"order_id": order["order_id"], "product": product["name"],
                                         "status": order["status"]}], "count": 1})
        c2, r2 = ctx.call("update_order", {"order_id": order["order_id"], "fields": {"status": "cancelled"}},
                           {"order_id": order["order_id"], "status": "cancelled"})
        af = ctx.agent(f"Order #{order['order_id']} for {product['name']} has been cancelled.")
        order["status"] = "cancelled"
        return gt("success",
                   "There was exactly one matching open order, and the agent cancelled it and confirmed "
                   "using the status returned by the tool.",
                   [u, c1, r1, c2, r2, af])

    candidates = customers_with_multiple_open_orders(world)
    cid = rng.choice(candidates) if candidates else rng.choice(list(world.customers.keys()))
    cust = world.customers[cid]
    open_orders = customer_open_orders(world, cid)
    if len(open_orders) < 2:
        pid1, pid2 = rng.sample(list(world.products.keys()), 2)
        for pid in (pid1, pid2):
            oid = world.new_order_id()
            order = {"order_id": oid, "customer_id": cid, "product_id": pid, "quantity": 1,
                      "status": "confirmed", "delivery_date": None, "created_at": ctx.t.strftime("%Y-%m-%d %H:%M:%S")}
            world.orders[oid] = order
        open_orders = customer_open_orders(world, cid)

    order_list = [{"order_id": o["order_id"], "product": world.products[o["product_id"]]["name"],
                   "status": o["status"]} for o in open_orders]

    if variant == "multiple_orders":
        u = ctx.user(f"Please cancel my order, this is {cust['name']}.")
        c1, r1 = ctx.call("find_order", {"customer_id": cid}, {"orders": order_list, "count": len(order_list)})
        names = ", ".join(f"#{o['order_id']} ({o['product']})" for o in order_list)
        af = ctx.agent(f"You have {len(order_list)} open orders: {names}. Which one would you like me to cancel?")
        return gt("ambiguous",
                   "The customer has multiple open orders and the agent correctly asked which one to cancel. "
                   "The user never specified, so the request could not be completed — this is a legitimate "
                   "open question, not a failure.",
                   [u, c1, r1, af], ambiguity_type="multiple_orders")

    if variant == "clarification_recovered":
        target = rng.choice(open_orders)
        target_product = world.products[target["product_id"]]
        u = ctx.user(f"Please cancel my order, this is {cust['name']}.")
        c1, r1 = ctx.call("find_order", {"customer_id": cid}, {"orders": order_list, "count": len(order_list)})
        names = ", ".join(f"#{o['order_id']} ({o['product']})" for o in order_list)
        a1 = ctx.agent(f"You have {len(order_list)} open orders: {names}. Which one would you like me to cancel?")
        # fixed gaps keep the RNG stream (and so every other session) unchanged
        u_vague = ctx.add("user_message", "user", "The one I placed recently.", gap=47)
        a_again = ctx.add("agent_message", "assistant",
                          "Several of those were placed recently. Could you give me the order number or the product?",
                          gap=6)
        u2 = ctx.user(f"The {target_product['name']} one, #{target['order_id']}.")
        c2, r2 = ctx.call("update_order", {"order_id": target["order_id"], "fields": {"status": "cancelled"}},
                           {"order_id": target["order_id"], "status": "cancelled"})
        af = ctx.agent(f"Order #{target['order_id']} for {target_product['name']} has been cancelled.")
        target["status"] = "cancelled"
        return gt("recovered",
                   "The customer had multiple open orders, so the agent asked which one to cancel. The user's "
                   "first answer was too vague to identify an order, so the agent asked again for the order "
                   "number or product, then completed the cancellation correctly once the user specified it.",
                   [u, c1, r1, a1, u_vague, a_again, u2, c2, r2, af], recovery_type="clarification_success")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Scenario family F: invoice lookup (get_invoice)
# ---------------------------------------------------------------------------

def gen_invoice(ctx, variant, world):
    rng = ctx.rng

    if variant == "success":
        invoiced_orders = [oid for oid in world.orders if oid in [inv["order_id"] for inv in world.invoices.values()]]
        oid = rng.choice(invoiced_orders)
        invoice = next(inv for inv in world.invoices.values() if inv["order_id"] == oid)
        order = world.orders[oid]
        cust = world.customers[order["customer_id"]]
        u = ctx.user(f"Can you pull up the invoice for order {oid}?")
        ctx.agent("Sure, let me pull that up.")
        c1, r1 = ctx.call("get_invoice", {"order_id": oid},
                           {"invoice_id": invoice["invoice_id"], "order_id": oid, "amount": invoice["amount"],
                            "issued_date": invoice["issued_date"], "paid_status": invoice["paid_status"]})
        af = ctx.agent(f"Invoice {invoice['invoice_id']} for order {oid} is {invoice['amount']:.2f} TND, "
                        f"issued {invoice['issued_date']}, currently {invoice['paid_status']}.")
        return gt("success",
                   "The agent queried the invoice for the exact order the user asked about and reported the "
                   "amount, date, and payment status exactly as returned by the tool.",
                   [u, c1, r1, af])

    if variant == "missing_information":
        u = ctx.user("Can you get me the invoice?")
        af = ctx.agent("Sure — which order or customer is this invoice for?")
        return gt("ambiguous",
                   "The user asked for an invoice without specifying which order or customer. The agent "
                   "correctly asked for the missing information instead of guessing, and the session ends "
                   "without an answer.",
                   [u, af], ambiguity_type="missing_information")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Scenario family G: sales_report (get_sales_report)
# ---------------------------------------------------------------------------

def gen_sales_report(ctx, variant, world):
    rng = ctx.rng
    period = f"2026-{rng.randint(5, 8):02d}"

    if variant == "success":
        total = round(rng.uniform(15000, 60000), 2)
        count = rng.randint(80, 400)
        u = ctx.user(f"What were our total sales for {period}?")
        ctx.agent("Sure, generating that report now.")
        c1, r1 = ctx.call("get_sales_report", {"period": period},
                           {"period": period, "total_sales": total, "orders_count": count})
        af = ctx.agent(f"In {period}, total sales were {total:.2f} TND across {count} orders.")
        return gt("success",
                   "The agent generated the report for the exact period requested and reported the figures "
                   "exactly as returned by the tool.",
                   [u, c1, r1, af])

    if variant == "unclear_intent":
        u = ctx.user("Can you give me the sales report?")
        af = ctx.agent("Sure — for which period, and any specific category, would you like the report?")
        return gt("ambiguous",
                   "The user's request did not specify a period or category, both of which are required to "
                   "generate a meaningful report. The agent asked for the missing scope instead of "
                   "guessing, and the conversation ends without an answer.",
                   [u, af], ambiguity_type="unclear_user_intent")

    raise ValueError(variant)

# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

FAMILY_GENERATORS = {
    "inventory_check": (gen_inventory, {"success": 14, "retry_success": 4, "wrong_record": 5, "unsupported_success": 2}),
    "customer_order_lookup": (gen_customer_lookup, {
        "success_unique": 10, "success_clarify": 8, "search_refinement": 4, "clarification_recovered": 4,
        "multiple_customers": 5, "no_progress": 4, "repeated_question": 3,
    }),
    "update_customer": (gen_update_customer, {"success": 8, "corrected_args": 4, "unsupported_success": 4}),
    "create_order": (gen_create_order, {"success": 10, "incomplete_request": 3, "corrected_args": 4, "retry_success": 2}),
    "cancel_order": (gen_cancel_order, {"success": 6, "multiple_orders": 3, "clarification_recovered": 2}),
    "invoice_lookup": (gen_invoice, {"success": 4, "missing_information": 2}),
    "sales_report": (gen_sales_report, {"success": 2, "unclear_intent": 3}),
}

CHANNELS = ["web_chat", "mobile_app", "internal_dashboard"]


def build_session_specs(rng):
    specs = []
    for scenario_type, (_, counts) in FAMILY_GENERATORS.items():
        for variant, n in counts.items():
            for _ in range(n):
                specs.append((scenario_type, variant))
    rng.shuffle(specs)
    return specs


def random_start_time(rng, base_date):
    offset_days = rng.randint(0, 44)
    hour = rng.randint(8, 19)
    minute = rng.randint(0, 59)
    return base_date + timedelta(days=offset_days, hours=hour, minutes=minute)


def main(seed=SEED, db_path=DB_PATH):
    rng = random.Random(seed)
    world = World(rng)
    build_customers(world)
    build_products(world)

    baseline_base = datetime(2026, 9, 26, 12, 0)
    build_baseline_orders(world, baseline_base)

    session_base = datetime(2026, 8, 13, 0, 0)
    specs = build_session_specs(rng)
    timed_specs = [(random_start_time(rng, session_base), scenario_type, variant) for scenario_type, variant in specs]
    timed_specs.sort(key=lambda x: x[0])

    sessions_rows = []
    events_rows = []
    ground_truth_rows = []

    for idx, (start_time, scenario_type, variant) in enumerate(timed_specs, start=1):
        session_id = f"S{idx:03d}"
        ctx = SessionBuilder(session_id, start_time, rng)
        generator_fn, _ = FAMILY_GENERATORS[scenario_type]
        result = generator_fn(ctx, variant, world)

        metadata = {
            "channel": rng.choice(CHANNELS),
            "agent_version": "erp-assistant-v1",
            "locale": "en",
        }
        sessions_rows.append({
            "session_id": session_id,
            "started_at": ctx.events[0]["timestamp"],
            "ended_at": ctx.events[-1]["timestamp"],
            "scenario_type": scenario_type,
            "outcome": result["outcome"],
            "metadata": json.dumps(metadata),
        })
        events_rows.extend(ctx.events)

        ground_truth_rows.append({
            "session_id": session_id,
            "outcome": result["outcome"],
            "failure_type": result["failure_type"],
            "recovery_type": result["recovery_type"],
            "ambiguity_type": result["ambiguity_type"],
            "severity": result["severity"],
            "explanation": result["explanation"],
            "evidence_event_ids": json.dumps(result["evidence_event_ids"]),
        })

    # --- write to SQLite ---
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)

    conn.executemany(
        "INSERT INTO customers (customer_id, name, phone, email, city) VALUES (?, ?, ?, ?, ?)",
        [(c["customer_id"], c["name"], c["phone"], c["email"], c["city"]) for c in world.customers.values()],
    )
    conn.executemany(
        "INSERT INTO products (product_id, name, category, price, stock_quantity) VALUES (?, ?, ?, ?, ?)",
        [(p["product_id"], p["name"], p["category"], p["price"], p["stock_quantity"]) for p in world.products.values()],
    )
    conn.executemany(
        "INSERT INTO orders (order_id, customer_id, product_id, quantity, status, delivery_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(o["order_id"], o["customer_id"], o["product_id"], o["quantity"], o["status"],
          o["delivery_date"], o["created_at"]) for o in world.orders.values()],
    )
    conn.executemany(
        "INSERT INTO invoices (invoice_id, order_id, amount, issued_date, paid_status) VALUES (?, ?, ?, ?, ?)",
        [(i["invoice_id"], i["order_id"], i["amount"], i["issued_date"], i["paid_status"]) for i in world.invoices.values()],
    )
    conn.executemany(
        "INSERT INTO tool_definitions (tool_name, description, parameters_json) VALUES (?, ?, ?)",
        [(name, desc, json.dumps(params)) for name, desc, params in TOOL_DEFINITIONS],
    )
    conn.executemany(
        "INSERT INTO sessions (session_id, started_at, ended_at, scenario_type, outcome, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(s["session_id"], s["started_at"], s["ended_at"], s["scenario_type"], s["outcome"], s["metadata"])
         for s in sessions_rows],
    )
    conn.executemany(
        "INSERT INTO events (event_id, session_id, sequence_number, timestamp, event_type, role, content, "
        "tool_name, tool_arguments_json, tool_result_json, tool_status, latency_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(e["event_id"], e["session_id"], e["sequence_number"], e["timestamp"], e["event_type"], e["role"],
          e["content"], e["tool_name"], e["tool_arguments_json"], e["tool_result_json"], e["tool_status"],
          e["latency_ms"]) for e in events_rows],
    )
    conn.executemany(
        "INSERT INTO ground_truth (session_id, outcome, failure_type, recovery_type, ambiguity_type, "
        "severity, explanation, evidence_event_ids) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(g["session_id"], g["outcome"], g["failure_type"], g["recovery_type"], g["ambiguity_type"],
          g["severity"], g["explanation"], g["evidence_event_ids"]) for g in ground_truth_rows],
    )
    conn.commit()

    # --- summary ---
    print(f"Sessions: {len(sessions_rows)}")
    print(f"Events:   {len(events_rows)}")
    print(f"Customers: {len(world.customers)}  Products: {len(world.products)}  "
          f"Orders: {len(world.orders)}  Invoices: {len(world.invoices)}")
    from collections import Counter
    outcome_counts = Counter(s["outcome"] for s in sessions_rows)
    print("Outcome distribution:", dict(outcome_counts))
    scenario_counts = Counter(s["scenario_type"] for s in sessions_rows)
    print("Scenario distribution:", dict(scenario_counts))

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", default=DB_PATH, help="path of the SQLite file to (re)create")
    args = parser.parse_args()
    main(args.seed, args.out)
