# UFile Full Interview Sheet — Complete Rewrite to Mirror UFile 2025

## Context
User is filling out UFile 2025 and wants the "UFile Full Interview" sheet to be a comprehensive mirror of every page/field in UFile's interview, including $0/N/A fields for structural reference. Current sheet (436 rows) has gaps: T2125 is just a summary, medical section is duplicated, stale text, doesn't match UFile's page-by-page flow. User selected full duplication — every individual line item from T2125 included inline.

## Approach
Python script clears "UFile Full Interview" sheet and rebuilds it (~800+ rows) mirroring UFile 2025's exact interview navigation. 3 columns: A=Field, B=Value, C=Notes. Every field from every UFile page, in the exact order UFile presents them.

## File
`C:\Users\Matt1\OneDrive\Desktop\Receipt Organizer\Vaultifacts_2025_Tax_Receipts.xlsx` — sheet "UFile Full Interview"

---

## COMPLETE SECTION-BY-SECTION FIELD LIST

### PART A: SETUP & PERSONAL INFO

**Section 1: INTERVIEW SETUP (UFile "Interview" page)**
Master checklist — every checkbox topic in UFile, organized by category:
- Employment and other benefits:
  - Employment income (T4, T4E/RL-6) → YES
  - Social assistance, workers comp (T5007) → NO
  - Union/professional dues not on T4 → NO
  - Employment expenses (T777/T2200) → NO
  - GST/QST rebate on employment expenses → NO
- Pension and other income:
  - Pension, retirement income (T4A, T4A(OAS), T4A(P)) → YES (RBC T4A)
  - CPP/QPP benefits (T4A(P)) → NO
  - OAS pension (T4A(OAS)) → NO
  - RRSP/RRIF income (T4RSP, T4RIF) → NO
  - FHSA (T4FHSA) → NO
  - Social assistance, workers comp → NO
- Self-employment:
  - Self-employed business income (T2125) → YES
  - Self-employed professional income → NO
  - Self-employed commission income → NO
  - Farming income (T2042) → NO
  - Fishing income (T2121) → NO
  - Immediate expensing limit agreement → YES
  - Investment tax credits → NO
- Rental income:
  - Rental property income (T776) → NO
- Investment income:
  - Interest, dividends, carrying charges (T3, T5, T5008) → YES
  - Partnership income (T5013) → NO
  - Capital gains/losses → YES
  - Foreign income or property (T1135) → NO
  - Nova Scotia venture capital credit → NO
- Student:
  - Tuition, student loans, Canada training credit (T2202) → YES
- Common deductions:
  - Medical expenses, disability, caregiver → YES (medical $118.40)
  - Donations and political contributions → NO
  - RRSP, HBP, LLP, FHSA → NO
- Parents and children:
  - Alimony/support payments → NO
  - Universal child care (RC62) → NO
  - Child care expenses → NO
  - Adoption expenses → NO
- Instalments:
  - Tax paid by instalments → NO
- Other topics:
  - Moving expenses → NO
  - Repaid amounts (Crown debt) → YES ($678.12)
  - Other deductions and credits → YES
  - Adjustment request → NO
  - Northern residents deduction → NO
  - Clergy residence deduction → NO
- Carryforward:
  - Losses of prior years → NO
  - Alternative minimum tax → NO
  - Prior year information (tuition) → YES

**Section 2: IDENTIFICATION (UFile "Identification" page)**
- Last name: Cheung
- First name: Mathew
- SIN: [YOUR SIN]
- Date of birth: [YOUR DOB]
- Language of correspondence: English
- Province/territory on Dec 31, 2025: Alberta
- Province/territory on Jan 1, 2025: Alberta (if different)
- Marital status on Dec 31: [Single/Married/CLP]
- Did marital status change in 2025? No
- Canadian citizen? Yes
- Date of death: N/A
- Date became Canadian resident (if immigration): N/A
- Date ceased Canadian residency (if emigration): N/A
- Bankruptcy in 2025? No
- Care of (c/o): Leave blank
- CRA NETFILE Access Code: [From NOA]

**Section 3: CURRENT ADDRESS (UFile "Address" page)**
- Address line 1: 45 Panorama Hills Rise NW
- Address line 2: (blank)
- City: Calgary
- Province: Alberta
- Postal code: T3K 5M5
- Country: Canada
- Telephone — Home: [YOUR PHONE]
- Telephone — Work: (blank)
- Email: [YOUR EMAIL]
- Is mailing address different? No

**Section 4: CRA QUESTIONS (UFile "CRA questions" page)**
- Apply for GST/HST credit? Yes (~$519/year)
- Canada Carbon Rebate (CCR/CAIP) — outside CMA? No (Calgary is CMA; still get base ~$772)
- Elections Canada authorization? Yes/No (your choice)
- CRA online mail? Yes
- Authorize representative? No

**Section 4a: DIRECT DEPOSIT**
- Institution number: [3 digits]
- Transit number: [5 digits]
- Account number: [Your acct #]

**Section 5: NETFILE**
- Filing method: NETFILE
- First-time filing? No

**Section 6: AUTO-FILL MY RETURN**
- Use CRA Auto-fill? Yes
- Accept downloaded slips? Yes (review first)

---

### PART B: INCOME SLIPS & SELF-EMPLOYMENT

**Section 7: T4 — EMPLOYMENT INCOME (every box)**
- Employer name: [Your employer]
- Box 10 — Province of employment: AB
- Box 12 — SIN: [YOUR SIN]
- Box 14 — Employment income: $17,400.24
- Box 16 — Employee CPP contributions: $827.09
- Box 17 — Employee QPP contributions: $0
- Box 18 — Employee EI premiums: $285.38
- Box 20 — RPP contributions: $0
- Box 22 — Income tax deducted: $813.51
- Box 24 — EI insurable earnings: [From slip]
- Box 26 — CPP/QPP pensionable earnings: [From slip]
- Box 28 — Exempt (CPP/EI/PPIP): [Check if marked]
- Box 29 — Employment code: (blank)
- Box 32 — Travel in a prescribed zone: $0
- Box 34 — Personal use of employer's auto: $0
- Box 36 — Interest-free/low-interest loan: $0
- Box 38 — Security options benefits: $0
- Box 40 — Other taxable allowances/benefits: $0
- Box 42 — Employment commissions: $0
- Box 44 — Union dues: $0
- Box 46 — Charitable donations: $0
- Box 50 — RPP or DPSP registration #: (blank)
- Box 52 — Pension adjustment: $0
- Box 54 — Business number: [Employer BN]
- Box 55 — Employee PPIP premiums: $0
- Box 56 — PPIP insurable earnings: $0
- Box 66 — Eligible retiring allowance: $0
- Box 67 — Non-eligible retiring allowance: $0
- Box 71 — Indian (exempt employment income): $0
- Box 73 — Number of days in pay period: (blank)
- Box 74 — Past service contributions: $0
- Box 75 — Employee EMPE contributions: $0
- Box 77 — Workers compensation repaid: $0
- Box 81 — Placement/employment agency: $0
- Box 82 — Taxi/vehicle driver: $0
- Box 83 — Barber/hairdresser: $0
- Box 84 — Public transit pass: $0
- Box 85 — Employee home relocation loan: $0
- Other information codes: [Enter any from bottom of T4]

**Section 8: T4A — PENSION & OTHER INCOME (every box)**
Note: T4A auto-imported from RBC Direct Investing via CRA Auto-fill
- Payer name: RBC Direct Investing
- Box 016 — Pension or superannuation: $0
- Box 018 — Lump-sum payments: $0
- Box 020 — Self-employed commissions: $0
- Box 022 — Income tax deducted: [From slip]
- Box 024 — Annuities: $0
- Box 026 — Eligible retiring allowance: $0
- Box 027 — Non-eligible retiring allowance: $0
- Box 028 — Other income: $0
- Box 030 — Patronage allocations: $0
- Box 032 — Registered pension plan: $0
- Box 034 — Pension adjustment: $0
- Box 036 — Annuities (non-registered): $0
- Box 040 — RESP accumulated income: $0
- Box 042 — RESP educational assistance: $0
- Box 046 — Charitable donations: $0
- Box 048 — Fees for services: $0
- Box 105 — Scholarships, bursaries: $0
- Box 130 — Recipient type: Individual
- Box 135 — Recipient number: [SIN]
- Other amounts: [Enter any shown on slip]

**Section 9: T2125 — SELF-EMPLOYMENT (COMPLETE FIELD-BY-FIELD)**

**9a. Business Identification (T2125 Part 1)**
- Business name: Vaultifacts
- Business address: Same as home
- Description of main product/service: Online reselling of consumer goods
- NAICS code: 454110 (Electronic shopping and mail-order houses)
- Business number (BN): (blank — not registered)
- Partnership? No — sole proprietorship
- Fiscal period start: 2025-05-01
- Fiscal period end: 2025-12-31
- First year of business? Yes
- Final year of business? No
- GST/HST registered? No (under $30K small supplier threshold)
- GST/HST registration number: N/A
- Method of accounting: Cash basis

**9b. Internet Business Activities (T2125 Part 2)**
- Internet business activities? Yes
- Approximate % of gross income from internet: 100%
- Do you have a website? Yes (Shopify store — no sales from it)
- Website address: [If applicable]

**9c. Business Income (T2125 Part 3 — Line 8000)**
- Line 8000 — Gross sales, commissions or fees: $5,679.67
  - Facebook Marketplace: $4,566.77
  - Poshmark: $571.00
  - Etsy (6 sales, incl 2 previously disputed): $345.13
  - Private Sales: $160.00
  - Whatnot: $120.00
  - eBay (2 net payouts): $11.20
  - Etsy refund (anthony): -$94.43
- Reserves deducted last year: $0
- Other income: $0
- Line 8299 — Gross business income: $5,679.67

**9d. Cost of Goods Sold (T2125 Part 4)**
- Line 8300 — Opening inventory: $0 (first year)
- Line 8320 — Purchases (net of returns): $5,547.35
  [All 61 individual purchase line items — full detail from UFile T2125 Entry R42-R102]
  - 2025-04-27 | Goodwill (Varsity) | 13 items: $64.00
  - 2025-04-27 | Value Village (34th St NE) | 1 item: $10.49
  - 2025-04-27 | Value Village (34th St NE) | 3 items: $8.37
  - 2025-05-05 | Goodwill (Varsity) | 7 items: $80.50
  - 2025-05-05 | Value Village (Sage Hill) | 10 items: $51.35
  - 2025-06-01 | FB Marketplace | 72 items aggregate: $1,464.86
  - 2025-06-01 | Online | 6 items: $60.00
  - 2025-06-01 | Garage Sale | 1 item: $2.00
  - [+53 more Alibaba, AliExpress, Temu orders — all with dates, amounts, USD originals]
- Line 8340 — Direct wage costs: $0
- Line 8360 — Subcontracts: $0
- Line 8380 — Other costs: $0
- Line 8500 — Closing inventory: $3,673.92 (1,065 items at cost)
- Cost of goods sold: $1,873.43

**9e. Gross Profit**
- Gross profit: $3,806.24 (67.0% margin)

**9f. Business Expenses (T2125 Part 5 — EVERY line)**
- Line 8521 — Advertising: $23.55
  - 2025-05-24 | Design.com | Premium Logo Pack: $23.55
- Line 8523 — Meals and entertainment (50%): $0
- Long-haul truck driver meals: $0
- Line 8590 — Bad debts: $0
- Line 8690 — Insurance: $0
- Line 8710 — Interest and bank charges: $16.43
  - 2025-12-31 | Tangerine | CC interest (80% of $20.54): $16.43
- Line 8760 — Business tax, fees, licences, memberships, subscriptions: $739.46
  [All 26 items — Vendoo, Etsy setup, Shopify x6, PrimeLister x6, Ownr, Claude Pro, QuickBooks x8]
- Line 8810 — Office expenses: $309.25
  [All 8 items — photo light, storage, Costco bins, barcode scanner, Dollarama, eBay receiver, containers, craft case]
- Line 8811 — Office stationery and supplies: $0 (included in 8810)
- Line 8860 — Legal, accounting, and other professional fees: $0
- Line 8871 — Management and administration fees: $0
- Line 8910 — Rent: $0
- Line 8960 — Maintenance and repairs: $0
- Line 8990 — Salaries, wages, and benefits: $0
- Line 9060 — Property taxes: $0
- Line 9180 — Travel: $0
- Line 9220 — Telephone and utilities: $0
- Line 9224 — Fuel costs (not motor vehicles): $0
- Line 9270 — Delivery, freight, and express: $527.37
  [All 28 items — boxes, mailers, tape, labels, stamps, NELKO printer, Etsy/FB shipping fees]
- Other expenses (specify): $0
- Line 8863 — Commissions paid: $174.75
  - Etsy selling fees: $43.65
  - Poshmark selling fees: $119.62
  - eBay fees: $0 (excluded — netted in revenue)
  - Whatnot selling fees: $11.48
- Line 9368 — Total business expenses: $1,790.81
- Business use % (if less than 100%): N/A (already prorated)

**9g. Net Income Calculation (T2125 Part 6)**
- Line 9369 — Net income before adjustments: $2,015.43
- Line 9281 — Motor vehicle expenses (from Chart A): $179.84
- Line 9936 — CCA (from Area A): $1,057.36
- Line 9945 — Business-use-of-home (from Area B): $0
- Line 8235 — Net business income/(loss): $778.23

---

**Section 10: MOTOR VEHICLE EXPENSES (Chart A — within T2125)**
- Year/make/model: 2015 Volkswagen Golf GTI
- Date acquired: 2025-04-14
- Purchase price: $13,500 (private sale, FB Marketplace)
- Total km driven in 2025: 15,000 km (estimate)
- Business km driven in 2025: 1,700 km
- Business use %: 11.3%
- Chart A Line 1 — Fuel and oil: $1,312.39
- Chart A Line 2 — Maintenance and repairs: $169.39
  - Oil: $77.79
  - Oil change service: $51.60
  - Car washes: $40.00
- Chart A Line 3 — Insurance: $0 (parents pay)
- Chart A Line 4 — Licence and registration: $109.74
- Chart A Line 5 — CCA (vehicle portion — from Area A): $228.83
  Note: UFile applies 11.3% business use to the full CCA of $2,025
- Chart A Line 6 — Interest on vehicle loan (from Chart B): $0
- Chart A Line 7 — Leasing costs (from Chart C): $0
- Chart A Line 8 — Electricity (ZEV): $0
- Chart A Line 9 — Total vehicle operating costs: $1,591.52
- Chart A Line 10 — Business portion: $179.84 (11.3%)
- Chart A Line 11 — Parking: $0
- Chart A Line 12 — Supplementary insurance: $0
- Net motor vehicle expenses (Line 9281): $179.84

**Chart B — Interest on vehicle loan**: N/A (no loan)
**Chart C — Leasing costs**: N/A (not leased)

---

**Section 11: CCA — CAPITAL COST ALLOWANCE (Area A — within T2125)**

**Class 50 — Computer Equipment (iPhone 16 Pro 256GB)**
- Col 1 — Class number: 50 (55% rate)
- Col 2 — UCC at start of year: $0
- Col 3 — Cost of additions: $879.45 (50% of $1,758.90)
- Col 4 — Adjustments / DIEP: $0
- Col 5 — Proceeds of dispositions: $0
- Col 6 — Adjustments: $0
- Col 7 — UCC after additions: $879.45
- Col 8 — Base amount for CCA: $879.45
- Col 9–13 — (various adjustments): $0
- Col 14 — AIIP (Accelerated Investment Incentive): Applied (1.5x = 82.5%)
- Col 15–17 — (adjustments): $0
- Col 18 — CCA claim: $725.55
- Col 19 — UCC at end of year: $153.90

**Class 8 — General Equipment (Cricut Explore 3 + Supplies)**
- Col 1 — Class number: 8 (20% rate)
- Col 2 — UCC at start: $0
- Col 3 — Cost of additions: $343.28
- Col 4–6 — $0
- Col 7 — UCC after additions: $343.28
- Col 14 — AIIP: Applied (1.5x = 30%)
- Col 18 — CCA claim: $102.98
- Col 19 — UCC end: $240.30

**Class 10 — Motor Vehicle (2015 VW Golf GTI)**
- Col 1 — Class number: 10 (30% rate)
- Col 2 — UCC at start: $0
- Col 3 — Cost of additions: $13,500.00
- Col 7 — UCC after additions: $13,500.00
- Col 14 — Half-year rule: Applied (standard, not AIIP)
- Col 18 — CCA claim (full): $2,025.00 → business portion 11.3% = $228.83
- Col 19 — UCC end: $11,475.00

**CCA UFile Questions:**
- Were any assets disposed of during the year? No
- Do you have any additions in the year? Yes
- Do you want to claim maximum CCA? Yes
- Are there any assets with personal-use portion? Yes (iPhone 50%)

**CCA Summary:**
- Total CCA deduction: $1,057.36 ($725.55 + $102.98 + $228.83)
- Total UCC carry-forward: $11,869.20 ($153.90 + $240.30 + $11,475.00)
- Items under $500 expensed directly: NELKO printer $97.89, scale $5.00, scanner $20.32, photo light $6.50

---

**Section 12: BUSINESS-USE-OF-HOME (Area B — within T2125)**
- Use home for business? Yes (inventory storage, packing, listing)
- Total home sq ft: [Enter]
- Business sq ft: [Enter]
- Rent: $0 (live with parents)
- Mortgage interest: $0
- Property taxes: $0
- Home insurance: $0
- Utilities (heat/electricity/water): $0
- Maintenance and repairs: $0
- Telephone (business portion): $0
- Internet (business portion): $0
- Other: $0
- Total home office deduction: $0
- Note: Business is profitable ($778.23) — no ITA 18(12) restriction. Deduction is $0 solely because no home costs are paid.

---

**Section 13: IMMEDIATE EXPENSING (UFile page)**
- Eligible person for immediate expensing? Yes (sole proprietor)
- DIEP limit: $1,500,000
- Designate property for immediate expensing? No (using AIIP rates instead)
- Note: Tax is $0 in 2025 — AIIP provides UCC carry-forward ($394.20) for future years when deductions save tax.

---

### PART C: INVESTMENT INCOME

**Section 14: T5008 — SECURITIES TRANSACTIONS (each slip)**
For each T5008:
- Recipient type: Individual
- Currency: [CAD/USD]
- Date of settlement
- Type code
- Box 20 — Cost/book value (ACB)
- Box 21 — Proceeds
- Outlays and expenses
- Capital gain/(loss)

Slip 1: ARK ETF TRUSTARK INN (sale 1)
- Date: 2025-10-10
- Proceeds: $878.42
- ACB: $928.13
- Loss: ($49.71)

Slip 2: ARK ETF TRUSTARK INN (sale 2)
- Date: 2025-10-29
- Proceeds: $852.97
- ACB: $928.13
- Loss: ($75.16)

Slip 3: CHARGEPOINT HOLDIN (reverse split)
- Date: 2025-07-28
- NOT A DISPOSITION — do not enter (reverse split is not taxable per CRA T4037)
- ACB for remaining shares: $155.58

Slip 4: NORWEGIAN CRUISE LI
- Date: 2025-10-10
- Proceeds: $187.33
- ACB: $242.17
- Loss: ($54.84)

**Section 15: T3 — TRUST INCOME**: $0 (N/A)
**Section 16: T5 — INVESTMENT INCOME**: $0 (N/A)
**Section 17: OTHER INVESTMENT INCOME**
- Interest income not on T5 (Tangerine savings): $0 (report if earned)
- Foreign interest/dividends: $0
- Carrying charges and interest expenses: $0
- CNIL: auto-calculated

**Section 18: SCHEDULE 3 — CAPITAL GAINS/LOSSES**
- Publicly traded shares/MF/ETFs — gains: $0
- Publicly traded shares — losses: -$179.71
  - ARK ETF: -$49.71 + -$75.16 = -$124.87
  - Norwegian CL: -$54.84
  - ChargePoint: excluded (reverse split)
- Real estate: $0
- Other capital property: $0
- Personal-use property (>$1,000): $0
- Listed personal property: $0
- Capital gains deferral: $0
- Capital gains reserve: $0
- Inclusion rate (2025): 50%
- Allowable capital losses: -$89.86 (50% × $179.71)
- Line 12700 — Taxable capital gains: $0 (losses cannot go below $0)
- Net capital loss carryforward: $89.86 (forward indefinitely against future gains)

---

### PART D: DEDUCTIONS & CREDITS

**Section 19: T2202 — TUITION**
- Institution name: [Your school]
- Eligible tuition fees (Box 25+26): $8,149.21
- Months full-time: [From T2202]
- Months part-time: [From T2202]
- Unused federal tuition from prior years: [From NOA]
- Unused Alberta tuition from prior years: [From NOA]
- Transfer to parent? DECIDE (up to $5,000 → saves parent ~$1,250)
- Carry forward unused? Yes
- Federal credit (15%): $1,222.38 (carries forward — tax already $0)
- Alberta credit (10%): $814.92 (carries forward — tax already $0)

**Section 20: STUDENT LOAN INTEREST**: $0
**Section 21: CANADA TRAINING CREDIT**: $0

**Section 22: MEDICAL EXPENSES (Line 33099)**
- 12-month period for medical expenses: January 1 – December 31, 2025 (UFile default)
- Dextroamphetamine (prescription): $91.91
- Sertraline (prescription): $26.49
- Other medical/dental/vision expenses: $0 (add any unclaimed expenses here)
- Total medical expenses: $118.40
- 3% net income threshold: $500.20 (3% × $16,673.26)
- Lesser of 3% or $2,759 (2025 indexed): $500.20
- Result: BELOW threshold — no credit unless $381.80+ more in expenses added
- Line 33199 — Medical for dependants: $0

**Section 23: DISABILITY AMOUNT**: $0 (no T2201)
**Section 24: CAREGIVER AMOUNTS**
- Line 30300 — Spouse/CLP: $0
- Line 30400 — Eligible dependant: $0
- Line 30425 — Canada caregiver (spouse/CLP/dependant): $0
- Line 30450 — Canada caregiver (other infirm dependants): $0

**Section 25: DONATIONS**
- Line 34900 — Total charitable donations: $0
- Government gifts: $0
- Cultural/ecological gifts: $0
- Political contributions (federal): $0
- Political contributions (Alberta): $0

**Section 26: RRSP / PRPP / SPP**
- RRSP contributions in 2025: $0
- RRSP deduction limit: [From NOA]
- Unused RRSP deductions: [From NOA]
- HBP repayment: $0
- LLP repayment: $0
- Spousal RRSP contributions: $0

**Section 27: FHSA**
- FHSA contributions: $0
- FHSA income: $0

**Section 28: OTHER DEDUCTIONS (Lines 20700–23600)**
- Line 21200 — Union/professional dues: $0
- Line 21400 — Child care expenses: $0
- Line 21500 — Disability supports: $0
- Line 21900 — Moving expenses: $0
- Line 22000 — Support payments made: $0
- Line 22100 — Carrying charges: $0
- Line 22200 — CPP/QPP on self-employment: $0 (SE income $778.23 < $3,500 exemption)
- Line 22215 — CPP enhanced contributions on employment: [auto-calculated]
- Line 22900 — Other employment expenses: $0
- Line 23200 — Other deductions (Crown debt): $678.12
- Line 23500 — Social benefits repayment: $0

**Section 29: OTHER CREDITS (Lines 30000–31900)**
- Line 30000 — Basic personal amount: $16,129
- Line 30100 — Age amount: $0 (under 65)
- Line 30300 — Spouse/CLP amount: $0
- Line 30400 — Eligible dependant: $0
- Line 31220 — Canada employment amount: $1,368 (→ 15% = $205.20 credit)
- Line 31260 — Canada employment credit: $205.20
- Line 31270 — Home buyers amount: $0
- Line 31285 — Home accessibility: $0
- Line 31350 — Digital news subscription: $0
- Line 31400 — Volunteer firefighter: $0
- Line 31410 — Search and rescue volunteer: $0
- Line 31600 — Disability amount: $0
- Line 31800 — Disability transferred: $0
- Line 31900 — Interest on student loans: $0
- Line 31217 — Pension income amount: $0 (no eligible pension)
- Line 32600 — Amount transferred from spouse/CLP: $0
- CPP credit (15% × $827.09): $124.06
- EI credit (15% × $285.38): $42.81
- Tuition credit (15% × $8,149.21): $1,222.38

---

### PART E: CARRYFORWARD & PROVINCIAL

**Section 30: PRIOR YEAR AMOUNTS**
- Unused federal tuition from prior years: [From NOA]
- Unused Alberta tuition from prior years: [From NOA]
- Net capital losses from prior years: $0
- Non-capital losses from prior years: $0
- RRSP deduction limit for 2025: [From NOA]
- Allowable business investment losses: $0

**Section 31: AB428 — ALBERTA PROVINCIAL TAX**
- Alberta basic personal amount: $22,323
- Alberta spouse/CLP amount: $0
- Alberta age amount: $0
- Alberta disability amount: $0
- Alberta pension income amount: $0
- Alberta tuition and education: $8,149.21 (carries forward)
- Alberta political contributions credit: $0
- Alberta tax (10% of taxable income above BPA): $0 (below BPA)
- Alberta Climate Action Incentive (CCR/CAIP): ~$772/year (base, no rural supplement)

---

### PART F: RESULTS & FILING

**Section 32: TAX SUMMARY (T1 Lines)**
- Line 10100 — Employment income: $17,400.24
- Line 13500 — Self-employment income: $778.23
- Line 12700 — Taxable capital gains: $0
- Line 15000 — Total income: $18,178.47
- Line 20800 — RRSP deduction: $0
- Line 22200 — CPP on SE: $0
- Line 23200 — Other deductions: $678.12
- Line 23600 — Net income: $16,673.26
- Line 26000 — Taxable income: $16,673.26
- Federal tax (15%): $0 (below BPA after credits)
- Alberta tax (10%): $0 (below Alberta BPA)
- Total tax payable: $0
- Tax deducted (T4 Box 22): $813.51
- CPP overpayment: [auto-calculated]
- EI overpayment: [auto-calculated]
- Line 45355 — Multigenerational Home Renovation Tax Credit: $0
- Line 45200 — Refundable medical expense supplement: $0 (medical below threshold)
- **REFUND: $813.51**

**Section 33: SCHEDULE 6 — CANADA WORKERS BENEFIT**
- Line 35000 — Working income: $18,178.47 (employment + SE)
- Net income (Line 23600): $16,673.26
- CWB basic amount: ~$1,518
- CWB disability supplement: $0
- Note: MUST file Schedule 6 to receive CWB

**Section 34: SCHEDULE 8 — CPP ON SELF-EMPLOYMENT**
- Net SE income: $778.23
- CPP basic exemption: $3,500
- Pensionable SE earnings: $0 ($778.23 < $3,500)
- CPP contributions owing: $0

**Section 35: SCHEDULE 11 — FEDERAL TUITION**
- Eligible tuition (2025): $8,149.21
- Unused from prior years: [From NOA]
- Total available: $8,149.21 + prior
- Used in 2025: $0 (tax already $0)
- Transferred to parent: DECIDE (up to $5,000)
- Carry forward: $8,149.21 (+ prior if not transferred)

**Section 36: AB SCHEDULE 11 — ALBERTA TUITION**
- Same structure at provincial 10% rate ($814.92 credit value)

**Section 37: LINE 45200 — REFUNDABLE MEDICAL SUPPLEMENT**
- Eligible? Potentially (low-income with employment income)
- Requires: medical expenses exceeding 3% threshold
- Current status: $118.40 below $500.20 threshold → $0

**Section 38: ADDITIONAL BENEFITS (estimated annual)**
- GST/HST Credit: ~$519 (quarterly)
- CCR/CAIP: ~$772 (quarterly)
- CWB: ~$1,518
- Total estimated refund + benefits: ~$3,622.51

**Section 39: TFSA (informational)**
- 2025 annual TFSA limit: $7,000
- Cumulative room: [Check CRA My Account]
- TFSA income: tax-free (not on T1)
- Over-contribution: 1% monthly penalty if applicable

**Section 40: REVIEW & NETFILE**
- Step 1: Fix all RED messages in UFile
- Step 2: Verify refund = ~$813.51
- Step 3: Save PDF of completed T1
- Step 4: Click NETFILE to submit electronically
- Step 5: Record confirmation number
- Filing deadline (self-employed): June 15, 2026
- Tax owing deadline: April 30, 2026 (N/A — getting refund)
- Record retention: 6 years

**Section 41: REQUIRED SCHEDULES (auto-generated by UFile)**
- T2125 — Statement of Business Activities: MANDATORY
- Schedule 3 — Capital Gains/Losses: MANDATORY
- Schedule 6 — CWB: MANDATORY (without it, ~$1,518 not paid)
- Schedule 8 — CPP on SE: Auto-generated ($0 CPP)
- Schedule 11 — Federal Tuition: MANDATORY (carry forward)
- AB Schedule 11 — Alberta Tuition: MANDATORY

---

---

## VALUE VERIFICATION (all confirmed via tool output 2026-03-25)

**Federal tax calculation verified:**
- Taxable income $16,673.26 × 15% = $2,500.99
- BPA $2,419.35 + CEA $205.20 + CPP $124.06 + EI $42.81 = $2,791.42 credits
- Tax after credits: $0 (credits exceed tax by $290.43)
- Tuition credit ($1,222.38) fully carries forward — not needed

**Net income path verified:**
$18,178.47 - $827.09 (CPP) - $678.12 (Crown debt) = $16,673.26 ✓

**All 32 key values cross-checked against workbook cells — all match ✓**

## ADDITIONAL BUGS (outside this rewrite — fix separately)
- **T1 R17C2**: -$7,376.53 → should be -$7,338.16 (uses stale $1,829.18 intermediate)
- **T1 R20C1**: Contains "NOTE: was ITA 18(12) restricted in prior version" — should be cleaned

---

## 2025-SPECIFIC UFile FIELDS (included in rewrite)
- **FHSA (First Home Savings Account)** — new account type, $0 for user
- **CPP2 Enhancement** — second ceiling (YAMPE ~$81,200) for earnings above YMPE (~$71,300). User's $17,400 employment is well below → CPP2 = $0. UFile auto-calculates.
- **Capital gains inclusion rate** — proposed 66.67% above $250K was withdrawn. All 2025 gains at 50%.
- **Multigenerational Home Renovation Tax Credit** (Line 45355) — N/A for user, $0
- **Clean Technology Investment Tax Credit** — N/A
- **Canada Carbon Rebate for Small Businesses** — N/A (not a CCPC)

---

## Implementation
1. Write Python script (`~/.claude/ufile_interview_rewrite.py`) that:
   - Clears "UFile Full Interview" sheet
   - Writes all ~800 rows with 3 columns (Field | Value | Notes)
   - Section headers in ALL CAPS for easy scanning
   - Sub-section headers with "—" prefix
   - All numeric values as numbers (not strings) where they represent amounts
   - All individual T2125 line items from the UFile T2125 Entry sheet included inline
   - Reads purchase/expense items directly from "UFile T2125 Entry" sheet to avoid duplication errors
2. Run script
3. Fix T1 R17 and R20 stale bugs (separate quick fix)
4. Verify by reading back key cells

## Verification
1. Re-read sheet — spot-check 20+ key values against verified data
2. Count total rows and sections (expect 41 sections, ~800 rows)
3. Verify no stale values ($1,829.18, $735.91, $217.07, $2,009.02, $949.17)
4. Verify T2125 expense total sums to $1,790.81
5. Verify NBI cascade: $5,679.67 → $3,806.24 → $2,015.43 → $778.23
6. Run global stale scan across all sheets for $1,829.18 (T1 R17 fix)
