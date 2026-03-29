# Build Plan: Recovery Feature Group (Session 4)

## Context
Auth (Session 1), workout loop (Session 2), and gamification + home dashboard (Session 3) are shipped.
Session 4 adds daily recovery monitoring: morning check-in wizard, sleep logging, a scored recovery
dashboard, AI-generated recommendations, and device-only menstrual cycle tracking.

## Scope
**In:** F-RCV-01 (Recovery Score), F-RCV-02 (Morning Check-in), F-RCV-03 (Sleep Log),
F-RCV-04 (AI Recommendation — stored in RecoveryScore.recommendation), F-RCV-05 (Cycle Tracking — device-only)

**Out this session:** Wearable HRV integration (V1.1), barcode scanner (V1.1)

---

## Files to Create / Modify

### Backend (7 files)
| File | Action | Purpose |
|------|--------|---------|
| `backend/src/models/mood-check-in.model.ts` | Create | MoodCheckIn Mongoose schema |
| `backend/src/models/sleep-log.model.ts` | Create | SleepLog Mongoose schema |
| `backend/src/models/recovery-score.model.ts` | Create | RecoveryScore schema (includes recommendation + aiGenerated) |
| `backend/src/services/recovery.service.ts` | Create | Score formula + Grok recommendation + rule-based fallback |
| `backend/src/controllers/recovery.controller.ts` | Create | 5 HTTP handlers |
| `backend/src/routes/recovery.routes.ts` | Create | Route definitions |
| `backend/src/index.ts` | Modify | Mount recovery routes |

### Mobile (10 files)
| File | Action | Purpose |
|------|--------|---------|
| `types/api.ts` | Modify | Add MoodCheckIn, SleepLog, RecoveryScore, TodayRecovery interfaces |
| `lib/api/recovery.ts` | Create | API client wrappers |
| `stores/cycle-store.ts` | Create | Device-only cycle data (AsyncStorage + SecureStore — ADR-008) |
| `app/(tabs)/more.tsx` | Overwrite | Minimal Redirect stub (directory `more/` takes Expo Router precedence) |
| `app/(tabs)/more/_layout.tsx` | Create | Stack navigator for More tab |
| `app/(tabs)/more/index.tsx` | Create | More hub: Recovery row + Check-in row + Cycle row |
| `app/(tabs)/more/morning-check-in.tsx` | Create | 4-step wizard (mood → energy/stress → sleep → review/submit) |
| `app/(tabs)/more/recovery.tsx` | Create | Score card + AI recommendation + 7-day trend dots |
| `app/(tabs)/more/cycle-tracking.tsx` | Create | Phase display + calibration inputs (zero server calls) |
| `app/(tabs)/index.tsx` | Modify | Add Recovery card between XP card and Quick Start CTA |

---

## Architecture Details

### Models

**mood-check-in.model.ts**
- `userId` (ObjectId), `date` (Date — midnight UTC), `mood` (enum: great|good|okay|tired|stressed|sad|anxious), `energyLevel` (1–5), `stressLevel` (1–5)
- Compound unique index: `{ userId: 1, date: 1 }`

**sleep-log.model.ts**
- `userId`, `date` (midnight UTC), `bedtime` ("HH:MM"), `wakeTime` ("HH:MM"), `durationHours` (server-computed float), `quality` (1–5)
- Compound unique index: `{ userId: 1, date: 1 }`

**recovery-score.model.ts**
- `userId`, `date` (midnight UTC), `sleepScore` (0–40), `moodScore` (0–30), `muscleScore` (0–30), `totalScore` (0–100), `recommendation` (string), `aiGenerated` (boolean)
- Compound unique index: `{ userId: 1, date: 1 }` — upserted on every recompute

### Recovery Score Formula (recovery.service.ts)

```
sleepScore (0-40):
  Math.round((quality / 5) * 20 + Math.min(durationHours / 8, 1) * 20)

moodScore (0-30):
  weights = { great:2, good:1.8, okay:1.2, tired:0.8, stressed:0.6, sad:0.4, anxious:0.5 }
  raw = weights[mood] * 12 + energyLevel * 1.5 + (5 - stressLevel) * 1.5
  Math.round(Math.min(raw, 30))

muscleScore (0-30):
  Sessions with completedAt in last 72h → if none: return 30 (fully rested)
  avgRPE = avg overallRpe of those sessions (sessions missing RPE count as 5.0)
  volumeFactor = Math.min(sessionCount / 3, 1) * 6
  Math.max(0, Math.round(30 - (avgRPE * volumeFactor)))

totalScore = Math.min(100, sleepScore + moodScore + muscleScore)
```

**computeDurationHours(bedtime, wakeTime):** parse HH:MM, compute diff, add 24h if bedtime > wakeTime (midnight crossover), clamp [0, 18].

**normaliseDateToMidnightUTC(date):** zero out H/M/S/ms in UTC. All model queries use this.

**computeAndSaveRecoveryScore(userId, date):**
1. Normalise date; fetch MoodCheckIn + SleepLog for userId+date
2. Component = 0 if either is missing (partial score is valid)
3. computeMuscleScore (queries WorkoutSession)
4. Compute totalScore; call generateRecommendation
5. `findOneAndUpdate(..., upsert:true, new:true)` on RecoveryScore; return saved doc

**generateRecommendation(score, components, profile):**
- Follow `ai.service.ts` pattern exactly: AbortController + 10s timeout + `grok-2-latest`
- Returns `{ text: string, aiGenerated: boolean }`
- Rule-based fallback (used if GROK_API_KEY absent or Grok fails):
  - `>= 80`: "You're well-recovered. Hit a tough session today — your body is ready."
  - `>= 60`: "Moderate recovery. A normal workout is fine, but listen to your body."
  - `>= 40`: "Take it easy today. Consider active recovery or a mobility session."
  - `< 40`: "Your body needs rest. Prioritise sleep tonight and light movement only."

### API Endpoints

```
POST  /api/v1/recovery/check-in       submitMorningCheckIn  → upsert MoodCheckIn + SleepLog + recompute score
GET   /api/v1/recovery/today          getTodayRecovery      → { score: RecoveryScore|null, checkInDone: boolean }
GET   /api/v1/recovery/history        getRecoveryHistory    → { scores: RecoveryScore[] } (?days=7 default, max 30)
POST  /api/v1/recovery/sleep          logSleep              → upsert SleepLog + recompute score
GET   /api/v1/recovery/recommendation getRecommendation     → { recommendation, aiGenerated, score }
```

All behind `requireAuth`. All follow `{ success, data }` / `{ success, error }` shape from sessions.controller.ts pattern.

**submitMorningCheckIn body:** `{ mood, energyLevel, stressLevel, bedtime, wakeTime, sleepQuality, date? }`
Returns: `{ checkIn, sleepLog, recoveryScore }`

**index.ts addition:** Add two lines after existing `workoutRoutes` import+mount (same pattern):
```typescript
import recoveryRoutes from './routes/recovery.routes';
app.use('/api/v1', recoveryRoutes);
```

### Mobile Types (types/api.ts additions — append only)

```typescript
export interface MoodCheckIn {
  _id: string; date: string;
  mood: 'great' | 'good' | 'okay' | 'tired' | 'stressed' | 'sad' | 'anxious';
  energyLevel: number; stressLevel: number;
}
export interface SleepLog {
  _id: string; date: string; bedtime: string; wakeTime: string;
  durationHours: number; quality: number;
}
export interface RecoveryScore {
  _id: string; date: string; sleepScore: number; moodScore: number;
  muscleScore: number; totalScore: number; recommendation: string; aiGenerated: boolean;
}
export interface TodayRecovery { score: RecoveryScore | null; checkInDone: boolean; }
```

### Mobile API Client (lib/api/recovery.ts)
Thin wrappers over `apiClient`, mirror pattern of `lib/api/workouts.ts`.
Functions: `submitCheckIn(data)`, `getTodayRecovery()`, `getRecoveryHistory(days?)`, `getRecommendation()`

### React Query Keys
- `['recovery-today']` — home dashboard + More hub + recovery screen (invalidated on check-in submit)
- `['recovery-history', 7]` — recovery screen trend, staleTime 300_000
- `['recovery-recommendation']` — recovery screen, staleTime 300_000

### More Tab Directory Structure

Expo Router directories take precedence over same-named flat files. Overwrite `app/(tabs)/more.tsx` to:
```tsx
import { Redirect } from 'expo-router';
export default function MoreRedirect() { return <Redirect href="/(tabs)/more" />; }
```

**`app/(tabs)/more/_layout.tsx`:** Mirror `app/(tabs)/workouts/_layout.tsx` exactly.
Stack screens: `index`, `morning-check-in`, `recovery`, `cycle-tracking`.

**`app/(tabs)/more/index.tsx` — More Hub:**
- SafeAreaView + ScrollView, dark theme, title "More"
- Recovery row → `/(tabs)/more/recovery`. Secondary text: today's score (if loaded) or "Check in now →"
- Morning Check-in row → `/(tabs)/more/morning-check-in`. Green "✓" suffix if `checkInDone === true`.
- Cycle Tracking row (only if `profile?.enableMenstrualTracking === true`) → `/(tabs)/more/cycle-tracking`
- One query: `['recovery-today']` with `staleTime: 60_000` for the check-in status nudge

### Morning Check-In Wizard (app/(tabs)/more/morning-check-in.tsx)

All state is local `useState` — ephemeral, NOT Zustand.

```
step: 1 | 2 | 3 | 4
mood: string | null
energyLevel: number | null
stressLevel: number | null
bedtime: string  (e.g. "23:30")
wakeTime: string (e.g. "07:00")
sleepQuality: number | null
```

Progress dots: 4 small circles, filled = current step. Back button top-left (step 1 → router.back(), steps 2–4 → step--).

**Step 1 — Mood:** 7 pill buttons in 2-column grid. Selected = `#6366f1` bg. Next enabled when mood selected.

**Step 2 — Energy & Stress:** Two rows of 5 numbered buttons (1–5 each). Next enabled when both selected.

**Step 3 — Sleep:** Two `TextInput` (keyboardType="numeric", placeholder "23:30"). Validate with `isValidTime(v)`: `/^\d{2}:\d{2}$/` + range check (0–23h, 0–59m). 5 quality star buttons. Next enabled when both times valid + quality selected.

**Step 4 — Review & Submit:** Summary of all selections. `useMutation` → `submitCheckIn(...)`. On success: `invalidateQueries(['recovery-today'])` + `router.replace('/(tabs)/more/recovery')`. On error: `Alert.alert`. Button shows `ActivityIndicator` while `isPending`.

### Recovery Screen (app/(tabs)/more/recovery.tsx)

Queries: `['recovery-today']` + `['recovery-history', 7]`

Sections (SafeAreaView + ScrollView, `#111827` bg):
1. **Back + title bar**
2. **Score card** (if `score` exists): large `totalScore` (font 56, bold) coloured by tier. Colour: `>= 80` → `#10b981`, `>= 60` → `#f59e0b`, `< 60` → `#ef4444`. Component row: sleepScore/40 · moodScore/30 · muscleScore/30 in `#9ca3af`
3. **Check-in CTA** (if `checkInDone === false`): tappable `#1f2937` card "Log your morning check-in →" → `router.push('/(tabs)/more/morning-check-in')`
4. **AI Recommendation** (if score): `#1f2937` card, "Coach Recommendation" header, recommendation text, tag "AI" `#a78bfa` if aiGenerated else "Auto" `#6b7280`
5. **7-Day Trend**: Build array of last 7 days (oldest left, today right). Match each date against `historyData.scores`. Filled coloured circle (40×40) with score text inside; grey circle + "—" for missing dates. Date label below. Pure View layout — no chart library.

### Cycle Store (stores/cycle-store.ts) — ADR-008 Compliance

Zustand store. Zero HTTP calls — no `fetch`, `apiClient`, or URL strings anywhere in this file.

Storage: AsyncStorage key `'cycle_data'` + SecureStore key `'cycle_secure'` (mirrored writes, SecureStore failure is non-fatal).

State shape:
```typescript
{ lastPeriodStart: string | null, cycleLength: number (default 28), isLoaded: boolean }
```

Actions: `loadCycleData()`, `setLastPeriodStart(date)`, `setCycleLength(n)`, `clearCycleData()`, `getCurrentPhase()`

**getCurrentPhase() — pure sync:**
```
dayOfCycle = daysSince(lastPeriodStart) + 1
phaseOffset = cycleLength - 28
day <= 5              → 'menstrual'   (#ef4444)
day <= 13             → 'follicular'  (#f59e0b)
day <= 17+phaseOffset → 'ovulatory'   (#10b981)
else                  → 'luteal'      (#6366f1)
```

`loadCycleData()`: try SecureStore first, fall back to AsyncStorage. Called once on mount in cycle-tracking.tsx.

### Cycle Tracking Screen (app/(tabs)/more/cycle-tracking.tsx)

Imports: ONLY `stores/cycle-store`, `stores/auth-store`, React Native primitives. Zero `lib/api/*` imports.

- If `enableMenstrualTracking === false`: show "Enable cycle tracking in Settings → Profile" and stop.
- Mandatory privacy notice card: "Your cycle data is stored only on this device and never shared."
- Last period start: MM + DD `TextInput` fields + "Set date" button → `setLastPeriodStart(dateStr)`
- Cycle length: numeric `TextInput` (21–35) + "Save" button → `setCycleLength(n)`
- Phase display (when `lastPeriodStart` set): large coloured phase name + "Day X of your cycle" + one-line plain-English description (hardcoded per phase)

### Home Dashboard Modification (app/(tabs)/index.tsx)

Add import: `import { getTodayRecovery } from '../../lib/api/recovery';`

Add query at top of `HomeScreen`:
```typescript
const { data: recoveryData } = useQuery({ queryKey: ['recovery-today'], queryFn: getTodayRecovery, staleTime: 60_000 });
```

Insert between XP/Streak card and Quick Start CTA:
- `checkInDone === false` (or no data): `#1f2937` card tappable → `router.push('/(tabs)/more/morning-check-in')` with text "Morning Check-in →"
- `checkInDone === true` and `score` present: compact tappable card showing "Recovery" label + large score number coloured by tier → `router.push('/(tabs)/more/recovery')`

---

## ADR-008 Hard Constraints (cycle data — never break)
1. `stores/cycle-store.ts` — zero HTTP imports
2. `app/(tabs)/more/cycle-tracking.tsx` — zero `lib/api/*` imports
3. Backend models — no fields: `cycleLength`, `lastPeriodStart`, `periodDate`, `cycleDay`
4. `recovery.controller.ts` — `submitMorningCheckIn` accepts only mood/energy/stress/sleep fields
5. `types/api.ts` — MoodCheckIn and SleepLog interfaces contain zero cycle fields

---

## Key Files to Reference During Implementation
- `backend/src/services/ai.service.ts` — Grok call pattern (AbortController + 10s timeout + null-on-fail) for `generateRecommendation`
- `backend/src/controllers/sessions.controller.ts` — auth guard + try-catch + response shape to replicate
- `stores/workout-store.ts` — Zustand + AsyncStorage persist pattern for `cycle-store.ts`
- `app/(tabs)/workouts/_layout.tsx` — Stack layout pattern for `more/_layout.tsx`
- `app/(tabs)/index.tsx` — existing dashboard for insertion point of Recovery card

---

## Verification
1. `GET /api/v1/recovery/today` (fresh user, valid JWT) → `{ score: null, checkInDone: false }`
2. Home tab shows "Morning Check-in →" CTA. Tap → 4-step wizard completes → Recovery screen opens
3. Verify `totalScore = sleepScore + moodScore + muscleScore` in MongoDB RecoveryScore document
4. If `GROK_API_KEY` set: `aiGenerated: true` + custom text. Unset → rule-based fallback text.
5. Recovery screen score colour matches tier (green / amber / red)
6. 7-day trend: today's dot filled, prior 6 grey circles
7. Complete a workout (RPE 9), then check-in → `muscleScore < 30` (expect ~12 with 1 session)
8. More hub shows all 3 rows; back navigation from sub-screens returns to hub
9. Enable `enableMenstrualTracking`. Enter cycle data. Kill app. Reopen → data persists from AsyncStorage
10. Network monitor during cycle tracking: zero outbound HTTP calls
11. All prior tabs (Home, Workouts, Nutrition, Progress) still functional after `more.tsx` → directory migration
