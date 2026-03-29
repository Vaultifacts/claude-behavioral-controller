# Plan: create_accounting_ai_course.py

## Context
The user wants a single, self-contained Python 3 script that generates a complete 12-month "AI & Accounting Mastery" course as a nested folder structure filled with rich Markdown files. The script must be idiot-proof, cross-platform via `pathlib`, accept one CLI arg (output base dir), and write thousands of words of content across 60+ `.md` files covering AI literacy, prompt engineering, Excel/Power BI, SQL, Python, agentic AI, ethics, and capstone projects — all framed for a new accounting graduate with zero AI knowledge.

The output directory (`C:\Users\Matt1\OneDrive\Desktop\AI & Accounting Course\`) currently exists but is **empty**. The script itself will be written there as `create_accounting_ai_course.py`.

---

## Output File
**`C:\Users\Matt1\OneDrive\Desktop\AI & Accounting Course\create_accounting_ai_course.py`**

---

## Script Architecture (5 Zones)

### Zone 1 — Header & Imports (lines ~1-40)
- `#!/usr/bin/env python3` + `# -*- coding: utf-8 -*-`
- Module docstring: usage, what it does, requirements
- Stdlib only: `pathlib`, `sys`, `textwrap`, `datetime`, `platform`
- Python version guard: `if sys.version_info < (3, 8): sys.exit(...)`

### Zone 2 — Runtime Engine (lines ~41-220)
```
main() → parse_args() → validate_output_dir() → create_all_files() → print_success_tree()
```
Key decisions:
- `Path(arg).expanduser().resolve()` for cross-platform path handling
- OneDrive path warning (relevant to this user's location)
- `write_text(content, encoding="utf-8")` on every file — mandatory on Windows (avoids cp1252 corruption)
- Individual `PermissionError` catch per file so one locked file doesn't abort the run
- `exist_ok=True` everywhere — script is idempotent/re-runnable
- Stats dict `{files, dirs, bytes, errors}` passed to success printer

### Zone 3 — Files Registry (lines ~221-340)
Single function `_build_files_registry() -> dict` returns `{relative_path_str: content_str}`.
`FILES = _build_files_registry()` called at module level.

### Zone 4 — Content Builder Functions (lines ~341-800)
Shared helpers:
- `lesson_template(d: dict) -> str` — expands a lesson data dict into full Markdown
- `callout_box(title, content, style)` — GitHub-flavored `> [!NOTE]` blocks
- `prompt_block(use_case, prompt, customize)` — fenced code block with label
- `failure_modes_table(rows)` — two-column Failure Mode / Fix table
- `self_assessment_quiz(questions)` — `<details>/<summary>` spoiler answers
- `portfolio_checkpoint(task, deliverable)` — standardized checkpoint callout
- `lesson_header(...)` and `lesson_footer(next, prev)` — navigation

Named builders for special files:
- `build_readme()`, `build_progress_tracker()`, `build_course_guide()`
- `build_tools_checklist()`, `build_ethics_framework()`
- `build_assignment(data)`, `build_quiz(data)`, `build_resources(data)`
- `build_capstone_overview()`, `build_portfolio_readme()`

### Zone 5 — Raw Content (lines ~801-end, ~4,000+ lines)

**Tier 1 (fully authored):** Modules 1 & 2 — 20 lesson files written in full as named module-level constants (`_LESSON_M1_01_WHAT_IS_AI`, etc.), each ~800-1,200 words.

**Tier 2 (parametric):** Modules 3-19 — each module has a `_M{N}_LESSONS` list of dicts; `lesson_template()` expands each to ~600-900 word Markdown. Content data covers all real accounting context.

**Tier 3 (structured stubs):** Modules 20-22, Capstone, Portfolio — project-based, 300-500 words each pointing to student deliverables.

---

## Complete File Tree to Generate (~67 files, ~38 dirs)

```
AI-Accounting-Mastery-Course/
├── README.md                                      [START HERE — full overview + 12-mo schedule table]
├── Progress_Tracker_Template.md                   [52-week Markdown table]
├── 00_Program_Rules_And_Tools/
│   ├── Course_Guide.md
│   ├── Tools_Setup_Checklist.md
│   └── Ethics_And_Judgment_Framework.md
├── 01_Phase1_Foundations/
│   ├── Month01_Weeks1-2/
│   │   ├── Module1_AI_Literacy/
│   │   │   ├── 01_What_is_AI.md
│   │   │   ├── 02_How_LLMs_Work.md
│   │   │   ├── 03_Generative_vs_Agentic_AI.md
│   │   │   ├── 04_AI_Hallucinations_And_Bias.md
│   │   │   ├── 05_Data_Privacy_In_Accounting.md
│   │   │   ├── 06_AI_In_The_Accounting_Profession.md
│   │   │   ├── 07_AICPA_And_AI_2026.md
│   │   │   ├── 08_Critical_Assessment_Mindset.md
│   │   │   ├── 09_AI_Ethics_CPA_Code.md
│   │   │   ├── 10_Week1-2_Reflection_Journal.md
│   │   │   ├── Assignments/Assignment1_AI_Audit_Worksheet.md
│   │   │   ├── Quizzes/Quiz1_AI_Literacy.md
│   │   │   └── Resources/Resources1_Free_Links.md
│   │   └── Module2_Prompt_Engineering_Basics/
│   │       ├── 01_What_Is_A_Prompt.md
│   │       ├── 02_Anatomy_of_a_Great_Prompt.md
│   │       ├── 03_Prompting_For_Financial_Summaries.md
│   │       ├── 04_Prompting_For_Tax_Research.md
│   │       ├── 05_Prompting_For_Variance_Analysis.md
│   │       ├── 06_Chain_Of_Thought_Prompting.md
│   │       ├── 07_Few_Shot_Prompting.md
│   │       ├── 08_Prompt_Templates_Library.md       [20-25 copy-paste accounting prompts]
│   │       ├── 09_Common_Prompt_Failures_And_Fixes.md
│   │       ├── 10_Week3-4_Reflection_Journal.md
│   │       ├── Assignments/Assignment2_Prompt_Library_Build.md
│   │       ├── Quizzes/Quiz2_Prompting.md
│   │       └── Resources/Resources2_Prompting_Links.md
│   └── Month01_Weeks3-4/
│       ├── Module3_Advanced_Prompting/             (10 lessons, parametric)
│       └── Module4_AI_Tool_Ecosystem/              (8 lessons, parametric)
├── 02_Phase2_Technical_Superpowers/
│   ├── Month02_Weeks5-8/
│   │   ├── Module5_Excel_And_Copilot/              (10 lessons)
│   │   ├── Module6_Power_BI_Dashboards/            (8 lessons)
│   │   └── Module7_SQL_For_Accountants/            (8 lessons)
│   └── Month03_Weeks9-12/
│       ├── Module8_Python_For_Finance/             (10 lessons)
│       └── Module9_Accounting_AI_Tools/            (8 lessons)
├── 03_Phase3_Agentic_AI/
│   ├── Month04_Weeks13-16/
│   │   ├── Module10_What_Are_Agents/               (6 lessons)
│   │   └── Module11_Building_Your_First_Agent/     (8 lessons)
│   └── Month05_Weeks17-20/
│       ├── Module12_Multi_Step_Workflows/          (8 lessons)
│       └── Module13_Agent_Orchestration/           (8 lessons)
├── 04_Phase4_Professional_Mastery/
│   ├── Month06_Weeks21-24/
│   │   ├── Module14_AI_Audit_And_Tax/              (8 lessons)
│   │   └── Module15_FP_And_A_Analytics/            (6 lessons)
│   ├── Month07_Weeks25-28/
│   │   ├── Module16_Ethics_Compliance_Deep_Dive/   (6 lessons)
│   │   └── Module17_Client_Communication/          (6 lessons)
│   └── Month08_Weeks29-32/
│       ├── Module18_Advanced_Orchestration/        (6 lessons)
│       └── Module19_Quality_Control_And_Review/    (6 lessons)
├── 05_Phase5_Launch_And_Legacy/
│   ├── Month09_Weeks33-36/
│   │   └── Module20_Portfolio_Projects/            (structured stubs)
│   ├── Month10_Weeks37-40/
│   │   └── Module21_Job_Search_AI_Edge/            (resume, interview prep)
│   └── Month11-12_Weeks41-52/
│       └── Module22_Capstone_And_Beyond/           (graduation + career paths)
├── Portfolio_Template/
│   ├── README.md
│   ├── Project1_Month_End_Close_Dashboard/
│   ├── Project2_AI_Reconciliation_Agent/
│   └── Project3_Tax_Research_Workflow/
└── Capstone_Projects/
    ├── Capstone_Overview.md
    ├── Capstone1_Automated_Close/
    ├── Capstone2_Audit_Exception_Agent/
    └── Capstone3_FP_And_A_Dashboard/
```

---

## Critical Content Rules (Non-Negotiable)
Every lesson MD must include:
1. Header: title, module #, week #, estimated time
2. Learning objectives (3-5 checkboxes)
3. Prerequisites check
4. Core content with accounting context and analogies
5. Copy-paste prompt examples in fenced code blocks
6. Failure modes + fixes table
7. `> [!TIP] Why this matters for accountants` callout
8. Self-assessment quiz (5 Q, spoiler answers via `<details>`)
9. Portfolio checkpoint
10. Prev/Next lesson navigation footer

---

## Edge Cases Handled
- `Path.expanduser().resolve()` → handles `~`, relative paths, Windows backslashes
- OneDrive path detection → print warning about sync conflicts
- Existing non-empty directory → warn and continue (overwrite), do NOT exit
- Existing file at path (not dir) → exit with error
- Per-file `PermissionError` catch → skip + log, don't abort
- `encoding="utf-8"` on every `write_text` → no cp1252 corruption on Windows
- Python < 3.8 guard → clean error message
- Idempotent: re-running refreshes all content

---

## Success Message Format
```
============================================================
  AI & ACCOUNTING MASTERY COURSE — GENERATED SUCCESSFULLY
============================================================
  Output  : C:\Users\...\AI-Accounting-Mastery-Course\
  Files   : 67   Directories: 38   Size: ~1.2 MB
------------------------------------------------------------
  NEXT STEPS:
  1. Open README.md in Obsidian or VS Code
  2. Complete 00_Program_Rules_And_Tools/Tools_Setup_Checklist.md
  3. Begin Module 1: 01_Phase1_Foundations/.../01_What_is_AI.md
  4. Log your start date in Progress_Tracker_Template.md

  Your career transformation starts NOW. Open README.md.
============================================================
```

---

## Verification
After running `python create_accounting_ai_course.py "C:\path\to\output"`:
1. Check `README.md` renders correctly in a Markdown viewer
2. Verify `01_Phase1.../Module1.../01_What_is_AI.md` has all 10 required sections
3. Confirm `Progress_Tracker_Template.md` has 52 weeks in a Markdown table
4. Re-run the script — no errors, files overwritten cleanly
5. Check `05_Data_Privacy_In_Accounting.md` contains the red/yellow/green data classification table
