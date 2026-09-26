# Step 2 – Starter Code Review (`project_starter.py`)

Facts marked ✅ were verified by running the helpers against a scratch copy of the database.

## 1. Data model

| Table | Source | Purpose |
|---|---|---|
| `transactions` | created empty, then seeded | **Single source of truth** for stock and cash. Rows are `stock_orders` (stock in, cash out) or `sales` (stock out, cash in). Stock and cash are never stored, only derived from these rows. |
| `inventory` | `generate_sample_inventory` | Reference table for the 18 initially stocked items: `unit_price`, `current_stock` at seed time, `min_stock_level` (the reorder threshold). |
| `quotes` | `quotes.csv` | 100 historical quotes (`total_amount`, `quote_explanation`, `job_type`, `order_size`, `event_type`). |
| `quote_requests` | `quote_requests.csv` | The original customer text for each historical quote (joined to `quotes` by `request_id` = `id`). |

The catalog (`paper_supplies`, 47 items with `unit_price`) is a Python list, not a table.

## 2. Helper functions: what each one does

| # | Function | Purpose | Returns | Used by (our design) |
|---|---|---|---|---|
| 1 | `generate_sample_inventory(paper_supplies, coverage=0.4, seed=137)` | Randomly picks 40% of the catalog (✅ 18 of 47 items) and gives each a starting stock (200–800) and `min_stock_level` (50–150). Reproducible via the seed. | `DataFrame` (item_name, category, unit_price, current_stock, min_stock_level) | Called by `init_database` at setup |
| 2 | `init_database(db_engine, seed=137)` | Builds the whole DB: empty `transactions`, loads `quote_requests` and `quotes` (unpacking metadata), generates the inventory, and seeds a $50,000 opening "sale" plus one `stock_orders` row per stocked item. | the engine | System setup in `run_test_scenarios` |
| 3 | `create_transaction(item_name, transaction_type, quantity, price, date)` | Appends one `stock_orders` or `sales` row. `price` is the **total**, not the unit price. Validates the type. | new row id (`int`) | `restock_item` (Inventory), `fulfill_order` (Sales) |
| 4 | `get_all_inventory(as_of_date)` | Net stock for every item with stock > 0 as of a date. | `Dict[item_name, units]` | `get_all_inventory_tool` (Inventory) |
| 5 | `get_stock_level(item_name, as_of_date)` | Net stock for one item as of a date (0 if never stocked). | **1-row `DataFrame`** (`item_name`, `current_stock`) | `get_stock_level_tool` (Inventory and Sales), re-check inside `fulfill_order` |
| 6 | `get_supplier_delivery_date(input_date_str, quantity)` | Supplier lead time by quantity: ≤10 same day, ≤100 +1 day, ≤1000 +4 days, >1000 +7 days. | `'YYYY-MM-DD'` | `get_supplier_delivery_date_tool` (Inventory and Sales), inside `restock_item` |
| 7 | `get_cash_balance(as_of_date)` | Σ sales − Σ stock_orders up to the date (✅ $45,059.70 on 2025-04-01). | `float` | `get_cash_balance_tool` (Inventory), affordability check in `restock_item` |
| 8 | `generate_financial_report(as_of_date)` | Cash, inventory value, total assets, per-item stock and value, top-5 sellers. | `dict` | `generate_financial_report_tool` (Sales: health check before large orders); also used by the test harness |
| 9 | `search_quote_history(search_terms, limit=5)` | LIKE-searches past customer requests and quote explanations. | `List[dict]` | `search_quote_history_tool` (Quoting) |

The test harness `run_test_scenarios()` loads `quote_requests_sample.csv` (20 requests, 2025-04-01 → 2025-04-17), processes them in date order, and after each one records cash and inventory from `generate_financial_report` into `test_results.csv`.

All 9 helpers are covered. The three the brief calls out (`get_all_inventory`, `get_cash_balance`, `generate_financial_report`) are each assigned to an agent.

## 3. Gotchas that shape the implementation

1. **Harness crash:** `run_test_scenarios()` calls `init_database()` without `db_engine` → ✅ `TypeError`. Must be called as `init_database(db_engine)`. `response` is also undefined until our system is wired in.
2. **Date-string comparison:** dates are compared as text. A transaction written as `2025-04-05T10:00:00` is **invisible** to a query `as_of_date='2025-04-05'` (✅ verified; it only appears the next day). → We always write transactions as `'YYYY-MM-DD'`.
3. **`get_stock_level` returns a DataFrame**, not a number → tools must use `.iloc[0]["current_stock"]`. Unknown items return 0, not an error.
4. **Only 18 of 47 catalog items are stocked.** Frequently requested items (Standard copy paper, Letter-sized paper, Matte paper, Recycled paper, Poster paper, Construction paper, Paper napkins, Flyers, washi tape) start at 0, so reordering is a core path, not an edge case.
5. **Requests don't use catalog names** ("A4 glossy paper", "heavy cardstock", "printer paper", "A3 paper", "balloons", "tickets"). Transactions only work with exact names, so they must be mapped first, and some items can't be matched at all.
6. **`min_stock_level` exists only for the 18 seeded items.** Items bought later need a default reorder rule.
7. **`generate_financial_report` only values items in the `inventory` table.** Stock of other items bought later is not counted in `inventory_value` (cash still drops), so reported assets understate.
8. **The seed $50k "sale" has `item_name = NULL`**, so ✅ `top_selling_products[0]` is `{item_name: None, total_revenue: 50000}`. Filter it out before showing a report.
9. **`search_quote_history` AND-combines terms**, so more terms means fewer hits. All historical quotes share one `order_date`, so "most recent" ordering is meaningless. → Search one term at a time and merge the results.
10. **Future-dated rows:** a restock dated on its supplier delivery date is not counted until then (stock and cash). We need a consistent rule for when to date restocks and sales. Proposal: date the restock on the request date (paid now, and the ETA is checked against the deadline) and the sale on the request date, so the harness report after each request reflects it.
11. `init_database` reads the CSVs relative to the current directory, so run from `project/`. It also emits pandas chained-assignment `FutureWarning`s (harmless).
12. `get_supplier_delivery_date` prints a debug line on every call (noisy but harmless).

## 4. Changes to the Step 1 tool draft

Every agent tool now wraps a starter helper (see `workflow_diagram.excalidraw`).

**Naming convention:** a tool that wraps exactly one helper is named `<helper>_tool` (the tool cannot reuse the helper's own name, because both live in `project_starter.py` and the tool would shadow the helper it calls). Tools that combine several helpers or none get descriptive names (`restock_item`, `fulfill_order`, `calculate_quote`, `match_catalog_items`).

| Agent | Tool | Wraps |
|---|---|---|
| Orchestrator | `match_catalog_items` | pure Python over `paper_supplies` (no DB access needed) |
| Inventory | `get_stock_level_tool` | `get_stock_level` |
| Inventory | `get_all_inventory_tool` | `get_all_inventory` |
| Inventory | `get_supplier_delivery_date_tool` | `get_supplier_delivery_date` |
| Inventory | `get_cash_balance_tool` | `get_cash_balance` |
| Inventory | `restock_item` | `get_cash_balance` + `get_supplier_delivery_date` + `create_transaction('stock_orders')` |
| Quoting | `search_quote_history_tool` | `search_quote_history` (one term per call) |
| Quoting | `calculate_quote` | pure Python: `paper_supplies` unit price × qty, bulk-discount tier |
| Sales | `get_stock_level_tool` | `get_stock_level` |
| Sales | `get_supplier_delivery_date_tool` | `get_supplier_delivery_date` |
| Sales | `generate_financial_report_tool` | `generate_financial_report` |
| Sales | `fulfill_order` | `get_stock_level` (re-check) + `create_transaction('sales')` |
| Setup | `run_test_scenarios` | `init_database(db_engine)` → `generate_sample_inventory` |

Hypothetical tools removed or renamed from Step 1: `inventory_snapshot`, `supplier_eta`, `cash_balance`, `quote_history`, `catalog_prices` (folded into `calculate_quote`), `financial_report`.
