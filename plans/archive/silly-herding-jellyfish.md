# Plan: Sync Notion & Commit Uncommitted Accessibility Changes

## Context
After the last commit (`e755348` — Dark mode CSS polish round 10), additional accessibility improvements were made to `app.js` and `main.css` but never committed or logged in Notion. These changes need to be:
1. Added to Notion's "Waiting for Manual Approval" section
2. Committed to git

Notion is currently rate-limited (429); we must wait before running Notion scripts.

---

## Current State
- **2 modified, uncommitted files**: `src/frontend/app.js`, `src/frontend/styles/main.css`
- **3 untracked junk files** (do NOT commit): `test.txt`, `test_write.txt`, `tmp_notion_checkoff.mjs`
- **Notion**: 0 pending to-do items, 483 items in "Waiting for Manual Approval" — the a11y changes are NOT yet among them
- **Rate limit**: Notion API returning 429; must wait ~15 min or retry

---

## What the Uncommitted Changes Are
**app.js** — Comprehensive accessibility audit:
- ARIA attributes on dialogs/modals (`role="dialog"`, `aria-modal`, `aria-label`)
- `aria-current="page"` on nav items (sidebar + mobile)
- `aria-expanded` sync on dropdowns; `aria-selected` on tabs
- `role="status"` + `aria-live="polite"` on toasts
- `<span class="sr-only">` for screen readers
- Skip link (`<a class="skip-link" href="#main-content">`)
- `<div>` → `<button>` for dropdowns and high-contrast toggle
- Focus management on route change

**main.css** — Focus/contrast/touch:
- `:focus-visible` outlines on search, range, size inputs
- Improved focus shadow contrast (`--primary-100` → `--primary-500`)
- Touch targets: `.btn-xs`, `.header-icon-btn`, `.btn-icon` → min 44×44px
- Dark mode contrast: stat-card-title + modal-close → `#d1d5db`
- `font-size: 100%` on html (was `16px`)
- `--text-secondary` CSS variable

---

## Steps

### Step 1 — Update Notion (once rate limit clears)
Run `bun scripts/session-end.js` and provide item details when prompted, OR use `bun scripts/add-to-approval.js` to add the a11y audit as a new "Waiting for Manual Approval" toggle block.

Item to add:
- **Title**: `♿ Accessibility audit — ARIA, focus indicators, touch targets, screen reader improvements`
- **Description**: Comprehensive a11y pass on app.js and main.css: ARIA attributes on all dialogs/modals/tabs/dropdowns, aria-current on nav, aria-live on toasts, skip link, sr-only spans, div→button semantic fixes, focus-visible outlines, 44px touch targets, dark mode contrast corrections
- **Files**: `src/frontend/app.js`, `src/frontend/styles/main.css`

### Step 2 — Git commit (only the 2 app files)
```bash
git add src/frontend/app.js src/frontend/styles/main.css
git commit -m "feat: Accessibility audit — ARIA attributes, focus indicators, touch targets, and screen reader improvements

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

Do NOT add: `test.txt`, `test_write.txt`, `tmp_notion_checkoff.mjs`

### Step 3 — Push to GitHub
```bash
git push
```

### Step 4 — Clean up junk files (optional, ask user)
`test.txt`, `test_write.txt`, `tmp_notion_checkoff.mjs` are empty/trivial artifacts. Offer to delete them or add to `.gitignore`.

---

## Files to Modify
- `src/frontend/app.js` — stage and commit
- `src/frontend/styles/main.css` — stage and commit

## Verification
- `git log --oneline -3` confirms new commit present
- `git status` shows clean working tree (except untracked junk files)
- Notion "Waiting for Manual Approval" section has new a11y toggle block
