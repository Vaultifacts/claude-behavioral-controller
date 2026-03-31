# Layer 14 — Response Efficiency Analysis
**File:** `~/.claude/hooks/qg_layer14.py` (160 LOC, 6 functions)
**Hook event:** Stop
**Purpose:** Measures tool call efficiency: redundant reads, excessive tool counts vs complexity class
**pytest-cov:** 37% (99 stmts, 62 missed)
**Live events:** 0
**Unit tests:** 17 methods in TestLayer14ResponseEfficiency

---

## 1. Redundant Read Detection
**Code:** `detect_redundant_reads()` (lines 70-73)

### 1.1 Logic
**Score: 9/10**
**Evidence:** Uses Counter on normalized paths. Detects same file read multiple times.

### 1.2 Unit tests
**Score: 10/10**
**Evidence:** 5 tests: no redundant, detected, multiple, empty, path normalization.

---

## 2. Tool Count vs Complexity
**Code:** `check_tool_count()`, `COMPLEXITY_THRESHOLDS` (lines 9-14, 76-84)

### 2.1 Logic
**Score: 8/10**
**Evidence:** Thresholds per complexity: TRIVIAL<5, SIMPLE<10, MODERATE<20, COMPLEX<40, DEEP<80.
**Missing:** No dynamic threshold adjustment based on task type. A MODERATE refactor may need more tools than a MODERATE question.

### 2.2 Unit tests
**Score: 10/10**
**Evidence:** 5 tests: under threshold, over, trivial exceeded, no complexity, unknown.

---

## 3. Transcript Parsing
**Code:** `parse_tool_calls()` (lines 30-67)

### 3.1 Logic
**Score: 6/10**
**Evidence:** Parses JSONL transcript, extracts tool_use blocks from last turn.
**Missing:** Only tested with empty/nonexistent paths. No test with actual transcript format.
**To reach 10:** Add test with mock transcript JSONL.

### 3.2 Unit tests
**Score: 4/10**
**Evidence:** Only 2 tests (empty, None). No positive case with actual transcript data.

---

## 4. Integration
### 4.1 Coverage gap
**Score: 4/10**
**Evidence:** 37% coverage. main() and parse_tool_calls untested. Lowest coverage of new layers.
**To reach 10:** Add transcript mock tests and main() test.

### 4.2 settings.json wiring
**Score: 10/10**
**Evidence:** Stop hook registered.

---

## 5. Live Effectiveness
**Score: 3/10**
**Evidence:** 0 events. Just deployed, needs sessions to accumulate data.
