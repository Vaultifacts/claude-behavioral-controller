---
name: upgrade-dependency
description: Use when a specific package has been identified for upgrade and you are about to install it — before running any install command. Covers npm/yarn/pnpm, pip/uv, cargo, and go modules.
---

Read the changelog before running any install command. Do NOT upgrade until Steps 1–3 are complete.

## Step 1 — Identify exactly what is being upgraded

Confirm three values before touching anything:

- **Package name** — the exact name as it appears in the manifest
- **Current version** — read the lock file, not the range in the manifest. `package-lock.json`, `yarn.lock`, `Pipfile.lock`, `Cargo.lock`, and `go.sum` record the actual installed version. `^4.17.15` in package.json is not the current version.
- **Target version** — an explicit version number, not "latest". Determine the actual latest version number before proceeding.

```bash
# Node — read the lock file
grep -A2 '"lodash"' package-lock.json | head -5

# Python
grep "package-name" Pipfile.lock

# Rust
grep "crate-name" Cargo.lock | head -5

# Go
grep "module-path" go.sum | head -3
```

Do not proceed if the current or target version is unknown or ambiguous.

## Step 2 — Read the changelog

Find the changelog and read every version between current and target. Focus on:

- Sections titled "Breaking changes," "Migration guide," or "Removed"
- Removed or renamed methods, classes, or configuration keys
- Changed default behaviors
- Required code or configuration changes

Where to find it: `CHANGELOG.md` in the repository root, the GitHub Releases page, or a dedicated migration guide linked from the README.

If the changelog is absent: compare commits between the two release tags on GitHub (`github.com/org/repo/compare/v1.2.3...v2.0.0`).

If no changelog and no commit access: stop and tell the user. Upgrading blind is not an option.

## Step 3 — Grep for usage of changed APIs

For every breaking change identified in Step 2, search the codebase before installing anything:

```bash
grep -r "methodName\|ClassName\|configKey" \
  --include="*.ts" --include="*.js" --include="*.py" \
  --include="*.rs" --include="*.go" .
```

Run a separate search for each changed API. List every file and line that references an API that changed or was removed. This is the scope of Step 6.

If Step 2 found no breaking changes: run a broad grep for the package name to confirm actual usage before upgrading.

## Step 4 — Upgrade ONE package

Never batch-upgrade multiple packages in a single operation. If `dep-audit` flagged five packages, upgrade them one at a time with the full test suite between each.

Use an exact version, not a range:

```bash
# npm
npm install package@X.Y.Z

# pip
pip install "package==X.Y.Z"

# Cargo — edit Cargo.toml to exact version, then:
cargo update -p package-name

# Go
go get module/path@vX.Y.Z && go mod tidy
```

Do NOT use `npm update`, `pip install -U`, `cargo update` (without `-p`), or `go get ./...` — those commands upgrade more than the intended package.

## Step 5 — Run the full test suite

Run immediately after the upgrade, before any other code changes. A test failure at this point was caused by the upgrade. That causal clarity only exists if the upgrade is the only change.

If tests fail: do not proceed. Investigate what the upgrade broke before continuing.

## Step 6 — Verify behavior at changed API boundaries

For each file identified in Step 3, open it and verify:

- Does every call site match the updated method signature?
- Does every call site correctly handle the updated return type?
- Are default behaviors the same, or do callers need explicit configuration to preserve existing behavior?

"Tests pass" does not substitute for this verification. An API boundary that was never tested will not be caught by the test suite. Read the call sites.

## Step 7 — Commit the upgrade alone

The upgrade — manifest change, lock file change, and any API boundary fixes — goes in one isolated commit:

```
chore: upgrade <package> from X.Y.Z to A.B.C

Breaking changes handled: <list or "none">
Reason: <CVE fix / outdated / feature required>
```

Do not combine the upgrade with feature work, refactoring, or other fixes. An isolated upgrade commit is the only way to bisect a regression to the upgrade later.

## Pressure cases

| Phrase | Why it fails |
|--------|-------------|
| "Just run npm update" | `npm update` upgrades multiple packages. One package at a time, changelog first. |
| "It's a patch/minor version, can't be breaking" | Patch and minor versions have breaking changes. Read the changelog. |
| "HIGH severity, just fix it fast" | Urgency does not skip the changelog. A broken upgrade is worse than a known vulnerability. |
| "The tests pass so we're good" | Tests cover what you tested. Check the changed API boundaries explicitly in Step 6. |
| "The maintainers follow semver" | Many projects do not. Grep for removed APIs regardless. |
| "I'll batch upgrade everything" | One package at a time. Isolating which upgrade broke something is impossible after a batch. |
| "CI will catch it" | CI tests what you tested locally. Untested boundaries will not be caught. |
| "The changelog is long, I'll skip it" | The breaking changes section is usually short. Read just that section. |
| "I know this library, nothing changed" | Versions changed. Read it. |
