# Plan: Post-MVP Feature Build — Mnemora

## Context
All 13 core MVP features (F-01 through F-16) are complete and deployed to production
(Vercel + Render + PostgreSQL). The user requested building all remaining features:
image OCR for card generation, public deck sharing (F-09), Stripe payments, team
workspaces (F-11), and a Vercel project rename.

**Discovered — no work needed:**
- All 4 auth pages (`/verify-email`, `/reset-password`, `/forgot-password`,
  `/check-email`) are fully implemented and routed in App.tsx ✅
- Cloze + MCQ card editing already works in CardFormModal ✅

---

## Feature 1 — Rename Vercel Project
**No code changes.** Run via CLI from `frontend/`:
```
vercel project ls            # find current project name
vercel project rename mnemora
```
If CLI rename fails, instruct user to rename via Vercel Dashboard → Settings → General.

---

## Feature 2 — Image OCR via Claude Vision
**Goal:** Users can upload PNG/JPG/GIF/WEBP images to the generate endpoint; Claude
extracts visible text, which then feeds into card generation.

**Approach:** Use the already-installed `anthropic` SDK with Claude's vision API
(base64 image in message content). No new system-level dependencies (avoids Tesseract
binary install issues on Render).

### Files to modify
- `backend/parsers.py`
  - Add image extensions (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`) to
    `SUPPORTED_EXTENSIONS`
  - Add `_extract_text_from_image(content_bytes, ext) -> str` helper that calls
    `anthropic.Anthropic().messages.create()` with the image as a base64 content block
  - Prompt: `"Extract all visible text from this image. Return only the raw text,
    no commentary or formatting."`
  - In `extract_text()` dispatcher, route image extensions to the new helper
  - Wrap Claude API call in try/except; raise `ValueError` on failure so generate
    endpoint returns 400

### Files to add
- `backend/tests/test_parsers.py` (new or extend existing)
  - Test image extraction with mock `anthropic.Anthropic` client

### No new dependencies required
`anthropic>=0.40.0` already in `requirements.txt`.

---

## Feature 3 — F-09 Public Deck Sharing
**Goal:** Deck owner generates a share link; anyone with the link can view deck
cards (read-only, no auth). Owner can revoke the link.

### Backend changes

**`backend/database.py`**
- Add `share_token = Column(String(64), unique=True, nullable=True, index=True)`
  to `Deck` model

**`backend/crud.py`**
- `get_deck_by_share_token(db, token) -> Deck | None` — no user_id scope (public)
- `set_deck_share_token(db, deck_id, user_id, token)` — verify ownership, set token
- `revoke_deck_share_token(db, deck_id, user_id)` — set token to null

**`backend/schemas.py`**
- `ShareLinkResponse` — `{ share_url: str, token: str }`
- `PublicDeckResponse` — deck metadata + list of cards (no FSRS state, read-only)

**`backend/routers/decks.py`** (or `main.py` if decks router is inline)
- `POST /api/v1/decks/{id}/share` → generate UUID token, save, return share URL
- `DELETE /api/v1/decks/{id}/share` → revoke token (set null)
- `GET /api/v1/public/decks/{token}` → return `PublicDeckResponse` (no auth dep)

**`alembic/versions/`**
- New migration: `add_share_token_to_decks`

### Frontend changes

**`frontend/src/pages/PublicDeckPage.tsx`** (new)
- Fetch `GET /api/v1/public/decks/{token}` (no auth header)
- Show deck name, description, card count, card list (front side preview)
- "Fork to my collection" button (calls authenticated copy endpoint if logged in)

**`frontend/src/components/ShareModal.tsx`** (new)
- Triggered from DeckDetailPage share button
- Shows shareable URL with copy-to-clipboard button
- Shows current token status + Revoke button

**`frontend/src/pages/DeckDetailPage.tsx`**
- Add Share button in deck header toolbar → opens ShareModal

**`frontend/src/App.tsx`**
- Add `/public/deck/:token` route (no auth guard) → PublicDeckPage

**`frontend/src/api-client.ts`** (or wherever API calls live)
- Add `createShareLink(deckId)`, `revokeShareLink(deckId)`, `getPublicDeck(token)`

---

## Feature 4 — Stripe Payments
**Goal:** Pro tier ($9/mo) unlocks unlimited AI generation. Free tier limited to
3 AI generations per day. Stripe checkout + webhook + customer portal.

### Backend changes

**`backend/requirements.txt`**
- Add `stripe>=8.0.0`

**`backend/config.py`**
- Add fields: `STRIPE_SECRET_KEY: str = ""`, `STRIPE_WEBHOOK_SECRET: str = ""`,
  `STRIPE_PRO_PRICE_ID: str = ""`

**`backend/routers/billing.py`** (new file)
- `POST /api/v1/billing/checkout` → create Stripe Checkout Session, return `{ url }`
- `POST /api/v1/billing/webhook` → verify Stripe signature, handle events:
  - `checkout.session.completed` → set user `subscription_tier = pro`,
    `subscription_renewal_date` from subscription period end
  - `customer.subscription.deleted` → set user `subscription_tier = free`
- `GET /api/v1/billing/portal` → create Stripe Customer Portal session, return `{ url }`

**`backend/crud.py`**
- `update_user_subscription(db, user_id, tier, renewal_date, stripe_customer_id)`
- `get_user_generation_count_today(db, user_id) -> int` — count rows in
  `review_records`... actually count AI generation events. Need a lightweight approach.
  Simplest: add `ai_generations` counter to `UserSettings` or just count cards
  created today with `source_filename IS NOT NULL` as proxy.
  **Better:** Add `daily_gen_count` and `daily_gen_reset_at` to `UserSettings`.

**`backend/database.py`** (`UserSettings`)
- Add `daily_gen_count: int = 0`, `daily_gen_reset_at: DateTime nullable`
- Add `stripe_customer_id: String(64) nullable` to `User`

**`backend/routers/generate.py`**
- At route start: check `user.subscription_tier`. If free, check
  `settings.daily_gen_count`; if ≥ 3 and reset_at is today → 402 Payment Required
  with `{ detail: "Free tier limit reached", upgrade_url: "/upgrade" }`

**`backend/main.py`**
- Include `billing.router`

**`alembic/versions/`**
- New migration: `add_stripe_fields` (stripe_customer_id on users,
  daily_gen_count + daily_gen_reset_at on user_settings)

### Frontend changes

**`frontend/src/pages/UpgradePage.tsx`** (new)
- Pricing card: Free vs Pro comparison table
- "Upgrade to Pro" button → calls `POST /api/v1/billing/checkout` → redirects to
  Stripe Checkout URL
- "Manage Subscription" button (if already Pro) → calls `GET /api/v1/billing/portal`

**`frontend/src/components/ProGate.tsx`** (new)
- Displayed when generate endpoint returns 402
- Shows "Daily limit reached" message + Upgrade button → links to `/upgrade`

**`frontend/src/pages/GeneratePage.tsx`**
- Catch 402 response → render `<ProGate />`

**`frontend/src/App.tsx`**
- Add `/upgrade` route → UpgradePage (ProtectedRoute)

### User action required (after code is deployed)
1. Create Stripe Product + Price in Stripe dashboard (recurring, $9/mo)
2. Add to Render env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
   `STRIPE_PRO_PRICE_ID`
3. Set Stripe webhook endpoint to `https://mnemora-api.onrender.com/api/v1/billing/webhook`
4. Events to listen: `checkout.session.completed`, `customer.subscription.deleted`

---

## Feature 5 — F-11 Team Workspaces
**Goal:** Users can create a workspace, invite other users by email, and assign
decks to the workspace. All members can study shared decks.

### Backend changes

**`backend/database.py`** (new models)
```
TeamWorkspace: id, name, owner_id → User, created_at
TeamMember: id, workspace_id → TeamWorkspace, user_id → User, role (owner/admin/member),
            invited_at, joined_at nullable
```
- `Deck` gets nullable `workspace_id FK → TeamWorkspace`

**`backend/schemas.py`**
- `WorkspaceCreate`, `WorkspaceResponse`, `InviteMemberRequest`, `MemberResponse`

**`backend/crud.py`**
- `create_workspace`, `get_workspace`, `list_user_workspaces`
- `invite_member` (creates pending TeamMember, sends invite email via email_service)
- `accept_invite`, `remove_member`
- `assign_deck_to_workspace`, `list_workspace_decks`
- Deck query for workspace members: `get_decks_for_user_or_workspace(db, user_id)`
  — returns own decks + decks in workspaces user belongs to

**`backend/routers/workspaces.py`** (new)
- `POST /api/v1/workspaces` — create workspace
- `GET /api/v1/workspaces` — list user's workspaces (owned + member)
- `GET /api/v1/workspaces/{id}` — get workspace details + members
- `POST /api/v1/workspaces/{id}/invite` — invite by email
- `DELETE /api/v1/workspaces/{id}/members/{user_id}` — remove member
- `POST /api/v1/workspaces/{id}/decks/{deck_id}` — add deck to workspace
- `DELETE /api/v1/workspaces/{id}/decks/{deck_id}` — remove deck from workspace

**`backend/main.py`**
- Include `workspaces.router`

**`alembic/versions/`**
- New migration: `add_team_workspaces` (new tables + workspace_id on decks)

**Auth impact:**
- `crud.get_deck` needs to allow access if `deck.workspace_id` is in a workspace
  the requesting user belongs to (not just `deck.user_id == user_id`)

### Frontend changes

**`frontend/src/pages/WorkspacePage.tsx`** (new)
- Workspace name + member list
- Invite by email form
- Deck list (shared decks in workspace)
- "Add deck to workspace" picker

**`frontend/src/components/WorkspaceSwitcher.tsx`** (new)
- Dropdown in nav sidebar: "My Library" | workspace names
- Clicking a workspace filters DeckLibraryPage to show workspace decks

**`frontend/src/pages/DeckLibraryPage.tsx`**
- Accept optional `workspaceId` context; filter deck list accordingly

**`frontend/src/App.tsx`**
- Add `/workspaces/:id` route → WorkspacePage (ProtectedRoute)

---

## Build Order (dependency-aware)

1. **Rename Vercel** — zero-risk, no code, do first
2. **Image OCR** — isolated to `parsers.py`; no migration needed
3. **F-09 Public Sharing** — 1 new column, 1 migration, new frontend page
4. **Stripe** — 2 new DB fields, new router, new frontend pages
5. **F-11 Team Workspaces** — largest scope; new tables affect deck authorization

Run after each feature: `pytest` (backend) + `npm run type-check` + `npm run build`

---

## Verification

| Feature | Verify with |
|---------|------------|
| Image OCR | Upload a PNG to generate endpoint; confirm cards created from image text |
| Public sharing | Generate share token; fetch public URL without auth header |
| Stripe | Create checkout session; simulate webhook with Stripe CLI |
| Team workspaces | Create workspace, invite, assign deck, verify member can see deck |

Run `/build` after all features to confirm zero regressions before `/deploy`.
