# Beaver's Choice Paper Company – Multi-Agent Quoting & Ordering System

**Reflection report**

| Submission file | Content |
|---|---|
| `workflow_diagram.png` (editable source: `workflow_diagram.excalidraw`) | Agent workflow diagram |
| `project_starter.py` | Complete implementation (single Python file) |
| `test_results.csv` | Evaluation output for all 20 requests in `quote_requests_sample.csv` |
| `reflection_report.md` | This report |

Framework: **smolagents 1.26** (`ToolCallingAgent`, `@tool`, `managed_agents`). Model: `gpt-4o-mini`. Store: SQLite (`munder_difflin.db`).

---

## 1. The multi-agent system

### 1.1 Agents and responsibilities

The system has **four agents** (the limit is five): one orchestrator and three workers. Their responsibilities do not overlap.

| Agent | Responsibility | Decides | Does **not** do |
|---|---|---|---|
| **Orchestrator** (customer-facing) | Reads the request, registers the order, delegates in a fixed order, writes the customer reply | Which items and quantities the customer asked for; what to tell the customer | Stock checks, pricing, booking sales |
| **Inventory agent** | Availability of every ordered item as of the request date; reordering from the supplier | Whether each item is available, and whether and how much to reorder | Pricing, customer communication |
| **Quoting agent** | Prices the available items with bulk discounts, using historical quotes as context | The quote (via `calculate_quote`) and its explanation | Stock decisions, booking |
| **Sales / fulfilment agent** | Finalises the order: re-checks stock and deadline, records the sale; runs a financial health check before large orders | Which quoted lines are booked | Reordering, pricing |

### 1.2 Workflow (diagram steps 1–8)

1. The customer's request arrives with its request date.
2. The orchestrator reads each item, quantity (with unit) and the deadline, and calls `match_catalog_items`. This maps the free-text names ("A4 glossy paper", "heavy cardstock", "500 reams of printer paper") to exact catalog names and **registers the order**. It then asks the inventory agent to check the order's items.
3. The inventory agent calls `restock_item` once per item. It returns, for each item, "available on `<date>`" or "unavailable: `<reason>`".
4. The orchestrator asks the quoting agent to price the order.
5. The quoting agent looks up similar past quotes (`search_quote_history_tool`) and calls `calculate_quote()`. This prices exactly the items that inventory confirmed as available, applies the bulk-discount tier and returns a `quote_id`.
6. The orchestrator passes the `quote_id` to the sales agent.
7. The sales agent runs `generate_financial_report_tool()` for orders of $1,000 or more, then calls `fulfill_order(quote_id)`. This books every deliverable line as a `sales` transaction and returns the delivery dates.
8. The orchestrator writes the customer reply. Code then appends a pricing rationale and a list of every item that could not be supplied, with its reason.

### 1.3 Tools and starter helper functions

Each tool is a smolagents `@tool` function (typed arguments and a docstring the LLM reads). All seven required helpers are used. A tool that wraps exactly one helper is named `<helper>_tool`.

| Tool | Agent | Purpose | Starter helper(s) |
|---|---|---|---|
| `match_catalog_items(requested_items, deadline_date)` | Orchestrator | Map descriptions to catalog names, check quantities, register the order | — (keyword rules over `paper_supplies`) |
| `get_stock_level_tool(item)` | Inventory, Sales | Stock of one item | `get_stock_level` |
| `get_all_inventory_tool()` | Inventory | Stock of all items, low-stock flags | `get_all_inventory` |
| `get_supplier_delivery_date_tool(qty)` | Inventory, Sales | Supplier lead time | `get_supplier_delivery_date` |
| `get_cash_balance_tool()` | Inventory | Cash available for purchases | `get_cash_balance` |
| `restock_item(item)` | Inventory | Decide availability and place a reorder | `get_stock_level`, `get_cash_balance`, `get_supplier_delivery_date`, `create_transaction('stock_orders')` |
| `search_quote_history_tool(terms)` | Quoting | Similar historical quotes | `search_quote_history` |
| `calculate_quote()` | Quoting | Price the available items, register the quote | — (catalog list prices) |
| `generate_financial_report_tool()` | Sales | Health check before large orders | `generate_financial_report` |
| `fulfill_order(quote_id)` | Sales | Book the sale | `get_stock_level`, `create_transaction('sales')` |

`init_database` (which calls `generate_sample_inventory`) runs once at the start of `run_test_scenarios`.

### 1.4 Business rules (all enforced in code)

- **Reordering:** reorder only when stock would fall short. Each reorder covers the order *and* restores `min_stock_level`. It is placed only if the company can afford it and the supplier delivers by the customer's deadline; otherwise the tool retries with just the shortfall. Restocks are bought at wholesale cost (assumed 70% of the catalog list price).
- **Pricing:** catalog list price × quantity. Bulk discount of 5% from 500 units, 10% from 2,000 and 15% from 10,000. Totals are rounded to whole dollars, as in the historical quotes.
- **Selling:** exactly the quoted lines at the quoted prices, once per quote, and only lines deliverable by the deadline.

### 1.5 Why this architecture

- **One agent per business function, plus a coordinator.** This maps directly to the three required capabilities (inventory, quoting, sales). A fifth agent, such as a separate reporting agent, was considered and rejected: the financial report is only a pre-sale check and belongs with sales.
- **The LLM handles language; code handles numbers and state.** The LLM interprets free text, delegates and writes replies. Stock, reorder quantities, cash checks, lead times, prices, discounts and bookings are deterministic Python. This was confirmed by the first test run (section 2.3), where giving the LLM free-form control over dates, items and prices produced invented dates and unordered purchases.
- **Shared order state instead of re-typed data.** Code, not the LLM, extracts the request date and the stated deadline from the request. The order registered by `match_catalog_items` is the single source of truth for every later tool. Tools therefore take no date arguments, accept only items in the registered order, and hand the quote to sales by `quote_id`. Agents coordinate through this state; they never re-type numbers to each other.
- **Guard rails that let the LLM correct itself.** Each agent has a smolagents `final_answer_check`: inventory cannot finish before every item is decided; quoting cannot finish without a quote; sales cannot finish before the quote is fulfilled. The orchestrator cannot reply until the workflow is complete, the order reference is included and no internal term appears. A failed check is returned to the agent as an error, and the agent fixes the missing step.
- **smolagents** was chosen because it is the framework used throughout the course. `managed_agents` gives the orchestrator its workers directly, and it works with the pinned `openai` client.

---

## 2. Evaluation (`test_results.csv`)

All 20 requests in `quote_requests_sample.csv` (2025-04-01 to 2025-04-17) were processed in one run of `python project_starter.py`.

### 2.1 Results against the requirements

| Requirement | Result |
|---|---|
| At least 3 requests change the cash balance | ✅ **19 of 20** (cash $45,059.70 → $47,969.85) |
| At least 3 quote requests fulfilled | ✅ **12 fully fulfilled** (every catalog item delivered) and **7 partially**; 19 of 20 requests with a sale |
| Not all requests fulfilled, with reasons | ✅ Request **#15 fully declined**; **20 requested items across 11 requests** declined (16 not deliverable in time, 4 not in the catalog), each with a stated reason |

| Metric | Value |
|---|---|
| Sales lines booked | 40, revenue **$12,493.00** |
| Supplier reorders | 33, cost **$9,582.85** |
| Net cash change | **+$2,910.15** |
| Discount tiers used | 0% (5 requests), 5% (10), 10% (3), 15% (1) |
| Failed runs / step-limit hits | 0 / 0 (8 guard trips, each corrected on the next step) |
| Replies with internal data | 0 of 20 |

Per request (charged amount; reasons abbreviated):

| # | Outcome | Charged | Not supplied |
|---|---|---|---|
| 1, 4–8, 10–12 | fulfilled | $65 · $81 · $128 · $73 · $549 · $648 · $138 · $146 · $49 | – |
| 2 | fulfilled | $133 | balloons (not in catalog) |
| 3 | fulfilled | $8,925 (15% off, 260,000 units) | A3 paper (size not carried) |
| 20 | fulfilled | $1,125 | tickets (not in catalog) |
| 9, 13 | partial | $22 · $30 | copy paper: earliest delivery after the 04-10 deadline |
| 14, 16, 17, 18, 19 | partial | $71 · $100 · $48 · $20 · $142 | items whose supplier delivery (04-16 to 04-22) is after the deadline |
| 15 | **declined** | $0 | A4 and colored paper (earliest 04-19 > 04-15); cardboard (not in catalog) |

### 2.2 Strengths

1. **Correct and reproducible decisions.** Every request followed the full workflow. The final run and an earlier independent run produced identical financial results to the cent. The database was reconciled against the tool log: 40 sales and 33 purchases, no stray or wrongly dated transactions.
2. **Recognises impossible constraints.** Items are declined when the supplier's lead time misses the deadline (e.g. 2,000 napkins by the next day), when the product is not sold (balloons, tickets, cardboard) or when the paper size is not carried (plain A3). The customer is told the earliest possible delivery date.
3. **Profitable inventory management.** Stock is bought only when an order needs it, sized to restore minimum stock levels, and never when the supplier would be too late. Wholesale purchasing keeps every discounted sale profitable (+$2,910 overall).
4. **Transparent customer replies.** Each reply with a sale states items, quantities, amounts, discount, total, delivery date and order reference. It also includes a pricing rationale ("15% bulk discount because the order has 260,000 units (10,000+ tier)") and the reason for every item not supplied. No reply mentions cash, stock levels, margins, suppliers' costs or internal agent and tool names. Only job titles and event types are handled, so no personal data is involved.
5. **Robust free-text understanding.** 45 different item descriptions in the sample map correctly to the catalog. Reams are converted to sheets in code, and every quantity is checked against the request text.

### 2.3 Areas for improvement found during testing

Eight full test runs were used to harden the system:

| Run | Problem found | Fix |
|---|---|---|
| 1 | LLM passed invented dates (e.g. 2023-10-09) → false rejections and wrongly dated transactions; bought 245,000 sheets nobody ordered ($42,875); skipped the sales step | Shared order state, date-free tools, order-bound quote and sale, orchestrator completion check |
| 2 | Replies sometimes lacked the reason; an over-broad guard caused a loop; deadlines misread | Narrow internal-data guard; deadline parsed by code; reasons appended by code |
| 3 | Inventory agent skipped `restock_item` for items it assumed were in stock | Completion checks for each worker agent |
| 4 | Orchestrator combined a delegation with its final answer in one step, which smolagents rejects → loop | One tool call per step (`parallel_tool_calls=False`) |
| 6 | Results contaminated by a second program writing to the same database file | Re-run in isolation; see suggestion 4 |
| 7 | LLM converted "500 reams" to 250,500 sheets ($17 overcharge) | Quantities and units passed as written; conversion and a check against the request text done in code |

Remaining weaknesses:
- **Partial orders are booked automatically.** The customer is never asked whether they want the available part only, or a later delivery.
- **Same-day orders compete for stock** in file order, with no prioritisation.
- **Restocked goods are recorded as available on the request date**, while the delivery promise uses the supplier's arrival date. This makes the harness figures current but is a simplification.
- **`generate_financial_report` only values the 18 initially stocked items**, so goods bought later are missing from the reported inventory value (it falls from $4,875 to $4,250 while cash rises).
- **Assumptions:** the 70% supplier cost and the discount tiers are not given in the brief.

---

## 3. Suggestions for further improvement

1. **Customer negotiation loop for partial orders.** Before booking a partial order, return an offer: "available now", "available on 04-19 if you accept a later date", "substitute: A4 instead of A3". Book only after the customer accepts. This needs order status "offered" → "accepted" and a conversation id. Revenue lost today on requests 14–19 could be partly recovered by offering the earliest possible delivery date.
2. **Forward-looking inventory with committed stock.** Record supplier orders on their arrival date and track *available-to-promise* stock (on hand + incoming − committed). Add a periodic replenishment review that uses sales history (e.g. standard copy paper was declined in 5 of 20 requests because it could not arrive in time), so fast-moving items are reordered before a customer asks. That would have avoided most deadline rejections in the test set.
3. **Data-driven pricing.** Learn discount levels from the 100 historical quotes (order size, event type, customer type), and add a minimum-margin rule, so discounts adapt to demand while staying above cost. The quoting agent currently uses history only for context.
4. **Safe concurrent operation and evaluation.** Give each run its own database (or wrap each order in a database transaction with a lock). Add automated checks after every run: DB reconciled with tool logs, no reply leaks, every declined item has a reason. Add an LLM-as-judge score for reply quality, so regressions are caught before release.

---

## 4. Code quality notes

- Everything is in one file, as required, split into sections: environment and model, constants and shared state, helpers, catalog matching, one block of tools per agent, guard rails, agent classes, request handling, and the test harness.
- Names are snake_case for functions and variables and PascalCase for the agent classes (`OrchestratorAgent`, `InventoryAgent`, `QuotingAgent`, `SalesAgent`).
- Every tool, helper and class has a docstring. Comments explain non-obvious decisions (date normalisation, wholesale cost, why parallel tool calls are disabled).
- Configuration is kept in named constants (`BULK_DISCOUNT_TIERS`, `SUPPLIER_COST_RATE`, `DEFAULT_DELIVERY_WINDOW_DAYS`). The model is chosen by environment variables: the `UDACITY_OPENAI_API_KEY` proxy, or a personal `OPENAI_API_KEY`.
