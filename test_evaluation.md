# Step 5 – Test & Evaluation (`quote_requests_sample.csv`)

Run: `python project_starter.py` with `gpt-4o-mini` (OpenAI endpoint), 20 requests, 2025-04-01 → 2025-04-17.
Output: `test_results.csv`. The table below is from the final run (run 5).

## 1. Results per request

| # | Date | Outcome | Charged | Not supplied (reason given to the customer) |
|---|---|---|---|---|
| 1 | 04-01 | fulfilled | $65.00 | – |
| 2 | 04-03 | fulfilled (5% off) | $133.00 | balloons: not in catalog |
| 3 | 04-04 | fulfilled (15% off, 260,000 sheets) | $8,925.00 | A3 paper: size not carried |
| 4 | 04-05 | fulfilled (5% off) | $81.00 | – |
| 5 | 04-05 | fulfilled (5% off) | $128.00 | – |
| 6 | 04-06 | fulfilled (5% off) | $73.00 | – |
| 7 | 04-07 | fulfilled (10% off) | $549.00 | – |
| 8 | 04-07 | fulfilled (10% off) | $648.00 | – |
| 9 | 04-07 | partially fulfilled | $22.00 | copy paper: cannot be delivered by 04-10 (earliest 04-11) |
| 13 | 04-08 | partially fulfilled | $30.00 | copy paper: cannot be delivered by 04-10 (earliest 04-12) |
| 12 | 04-08 | fulfilled (5% off) | $49.00 | – |
| 10 | 04-08 | fulfilled (5% off) | $138.00 | – |
| 11 | 04-08 | fulfilled (5% off) | $146.00 | – |
| 14 | 04-09 | partially fulfilled (5% off) | $71.00 | A4 paper, poster paper: cannot be delivered by 04-15 (earliest 04-16) |
| 15 | 04-12 | **not fulfilled** | $0.00 | A4 paper, colored paper: earliest 04-19 > deadline 04-15; cardboard: not in catalog |
| 16 | 04-13 | partially fulfilled | $100.00 | copy paper, construction paper: earliest 04-17 |
| 17 | 04-14 | partially fulfilled (5% off) | $48.00 | copy paper, colored paper, cups: earliest 04-18; napkins: earliest 04-21 |
| 18 | 04-14 | partially fulfilled | $20.00 | cardstock, copy paper: earliest 04-18 |
| 19 | 04-15 | partially fulfilled (5% off) | $142.00 | glossy, matte paper: earliest 04-22 > deadline 04-20 |
| 20 | 04-17 | fulfilled (10% off) | $1,125.00 | tickets: not in catalog |

(Request ids follow the CSV row order. The harness processes requests by date.)

## 2. Requirement check

| Requirement | Result |
|---|---|
| Fulfil at least 3 orders | ✅ 12 fully fulfilled (every catalog item delivered) and 7 partially fulfilled; 19 of 20 requests with a sale |
| Reject / leave unfulfilled at least 1 order with a clear reason | ✅ #15 fully rejected; 20 requested items across 11 requests declined, each with a reason listed in the reply |
| Handle varied inquiries | ✅ catalog mapping for 45 free-text item names, ream conversion, unsupported products and sizes, deadlines from 04-10 to 05-15 |
| Inventory use & profitability | ✅ 40 sales lines, $12,493.00 revenue; 33 restock orders, $9,582.85 cost; cash $45,059.70 → **$47,969.85 (+$2,910.15)**; restocks also restore `min_stock_level` |
| Competitive, consistent pricing | ✅ catalog list prices with 0 / 5 / 10 / 15% bulk tiers; totals rounded to whole dollars like the historical quotes; identical financial results in runs 2 and 5 (final cash $47,969.85) |
| Cash / inventory visible in `test_results.csv` | ✅ cash changes after 18 of 20 requests |
| No internal data in replies | ✅ no reply mentions cash, stock levels, margins, agents or tools; 19 of 19 replies with a sale include the order reference |

## 3. How the system got here (iterations)

| Run | Problem found | Fix |
|---|---|---|
| 1 | LLM passed invented dates (2023-10-09 …) → false "insufficient cash" rejections and wrongly dated transactions; bought items nobody ordered (245,000 photo paper for $42,875); skipped the sales step | Shared **order state**: request date parsed by code, `match_catalog_items` registers the order, tools take no dates and only accept registered items; `calculate_quote()` / `fulfill_order(quote_id)` bound to the order; orchestrator **completion check** |
| 2 | Replies did not always give the reason; the guard's broad "supplier" ban made the orchestrator loop until the step limit; LLM misread some deadlines | Narrower internal-data guard that names the offending word; deadline parsed by code; unsupplied items and reasons appended to each reply by code |
| 3 | Inventory agent sometimes skipped `restock_item` for items it saw in stock | Per-agent completion checks (inventory / quoting / sales) |
| 4 | Orchestrator combined a delegation and `final_answer` in one step (rejected by smolagents) → loop | One tool call per step (`parallel_tool_calls=False`); instruction to finalise available items without asking for confirmation |
| 5 | – | 0 step-limit hits, 0 errors, 4 guard trips, each fixed on the next step |

## 4. Known limitations

- Orders dated the same day are processed in CSV order, so an earlier request can use up stock a later one wanted.
- The supplier cost rate (70% of list price) and the discount tiers are assumptions, not given in the brief.
- Partial fulfilment is automatic; the customer is not asked whether they still want the remaining items.
- Stock bought for a deadline is recorded as available on the request date (the arrival date is used for the delivery promise), which keeps `test_results.csv` in line with each request.
- The LLM's wording varies between runs; amounts, items and decisions do not.
