# Plan: Vaultifacts Purchase Audit — Actual vs Recorded

## Context
The user's Purchases v3 sheet has 361 rows across multiple sources. An inventory audit found 10 items with negative inventory (sold more than purchased). The user wants every purchase crosschecked against actual platform order history, with results in a new "Audit" sheet.

## Approach: Gmail-First Extraction + Fuzzy Matching

### Why Gmail, not browser scraping
- AliExpress confirmation emails contain order ID, product name, qty, total
- Alibaba payment emails contain order ID, product name, qty, total USD
- Temu emails have order ID only (no line items) — browser needed as fallback for 7 orders
- Gmail avoids auth/anti-bot issues and is faster than paginating through order pages

### Coverage
| Source | Rows | Verifiable? | Method |
|--------|------|-------------|--------|
| Alibaba | 76 | Yes | Gmail payment emails |
| AliExpress (3 spellings) | 57 | Yes | Gmail confirmation emails |
| Temu | 48 | Partial | Gmail (order-level) + browser (item-level) |
| Facebook | 72 | No | Mark UNVERIFIABLE |
| Thrift/Garage/Sportchek/Online | 32 | No | Mark UNVERIFIABLE |
| Blank source | 76 | No | Mark UNVERIFIABLE |

**181 rows verifiable (49%), 180 rows unverifiable (51%)**

### Execution Steps

**Step 1: Gmail Extraction → JSON file**
- Search AliExpress: `from:transaction@notice.aliexpress.com "order confirmed" after:2025/4/1` (paginate, ~57 emails)
- Search Alibaba: `from:credit@notice.alibaba.com "Payment for your Trade Assurance order" after:2025/4/1` (~14 emails)
- Search Temu: `from:orders@order.temu.com "order confirmation" after:2025/4/1` (~10 emails)
- Read each email body, parse order ID, date, product name, qty, total
- Save to `C:\Users\Matt1\Downloads\vaultifacts_order_data.json`

**Step 2: Temu Browser Scrape (7 orders)**
- Navigate to temu.com/orders for each order ID from Step 1
- Extract item names and quantities
- Add to the JSON

**Step 3: Matching Logic (Python script)**
- Load JSON + spreadsheet
- Normalize sources ("Ali-Express"/"Ali Express"/"Aliexpress" → "AliExpress")
- Match by date first, then fuzzy product name match within that date's orders
- Use `difflib.SequenceMatcher` with 0.4 threshold
- Compute discrepancies

**Step 4: Write Audit Sheet**
- Add "Audit" sheet to merged Excel via openpyxl (or ZIP/XML if pivot corruption risk)
- Columns: Item Code, Item Name, Source, Recorded Qty, Recorded Cost, Order Date, Order ID, Actual Qty, Discrepancy, Match Confidence, Status, Notes
- Status codes: MATCHED, QTY_MISMATCH, PRODUCT_NOT_MATCHED, DATE_NOT_FOUND, DATE_MISSING, UNVERIFIABLE, ORDER_MATCHED_ONLY
- Conditional formatting: green=matched, yellow=partial, red=mismatch, grey=unverifiable
- Summary section at bottom with counts per status

### Estimated API calls
- Gmail search: 3-6 calls (with pagination)
- Gmail read: ~81 calls (57 AliExpress + 14 Alibaba + 10 Temu)
- Browser: ~7 Temu order pages
- Total: ~95 operations

### Output
- `C:\Users\Matt1\Downloads\vaultifacts_order_data.json` — raw order data from platforms
- `C:\Users\Matt1\Downloads\Vaultifacts 2025 Merged.xlsx` — updated with new "Audit" sheet

### Verification
1. Open merged file in Excel, check Audit sheet has 361+ rows
2. Verify MATCHED rows have matching quantities
3. Verify QTY_MISMATCH rows flag the 10 known negative-inventory items
4. Verify UNVERIFIABLE rows cover all Facebook/thrift/blank entries
5. Summary totals should add up to total purchase rows
