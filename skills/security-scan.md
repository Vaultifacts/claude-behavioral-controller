---
name: security-scan
description: Use when asked to check security, find vulnerabilities, scan for secrets, or run a dedicated security audit. For general code review where security is one concern among many, use code-review instead.
---

Security scan of: $ARGUMENTS (or entire project if no argument given)

## Step 1 — Scope

If `$ARGUMENTS` specifies a file or directory, scan only that. Otherwise scan the full project, focusing on:
- Entry points: routes, API handlers, CLI commands
- Auth: login, session, token handling
- Data persistence: DB queries, file writes, cache
- Config: environment variables, secrets management, headers
- Dependencies: package files

## Step 2 — Run automated checks first

**Secrets in tracked files:**
```bash
git grep -r -i "password\s*=\s*['\"][^'\"]\|api_key\s*=\s*['\"][^'\"]\|secret\s*=\s*['\"][^'\"]" -- ':!*.md' 2>/dev/null | head -20
git ls-files | grep -i "\.env$"
```

**Dependency vulnerabilities (run whichever applies):**
- Node: `npm audit --audit-level=moderate 2>/dev/null | tail -20`
- Python: `pip-audit 2>/dev/null || safety check 2>/dev/null`
- Rust: `cargo audit 2>/dev/null | tail -20`

Note HIGH/CRITICAL findings. Record "tool not available" and continue if tools are missing.

## Step 3 — Manual code review by category

Use the researcher agent to read relevant files, then check each category:

### A. Secrets & Credentials
- Hardcoded API keys, passwords, tokens in source code
- `.env` files committed to git
- Credentials in config files, comments, or test fixtures
- Secrets passed as command-line arguments (visible in process listings)

### B. Injection
- **SQL injection**: string concatenation in queries — must use parameterized queries or ORM
- **Shell injection**: child process calls with user-controlled input and shell interpolation — input must be validated against an allowlist and passed as an argument array
- **XSS**: unsanitized user input rendered to the DOM via raw HTML insertion — check template auto-escaping, direct innerHTML assignments, and React's raw HTML prop
- **Path traversal**: file read/write using user-supplied paths without resolve + allowlist prefix check
- **Template injection**: user-controlled strings passed to template engines

### C. Authentication & Authorization
- Missing auth checks on sensitive routes/functions
- Auth bypass via parameter manipulation (e.g., `?admin=true`, `?role=admin`)
- Insecure password storage (plaintext, MD5/SHA1 without salt — use bcrypt/argon2)
- JWT: missing signature verification, `alg: none` accepted, weak secret
- Session: no expiry, no invalidation on logout, predictable IDs
- Missing rate limiting on login/auth endpoints

### D. Sensitive Data Exposure
- PII or secrets logged to console/files
- Sensitive fields returned in API responses unnecessarily
- Unencrypted sensitive data at rest
- Internal error messages / stack traces exposed to clients

### E. Security Misconfiguration
- CORS: wildcard origin on authenticated endpoints
- Missing security headers: CSP, X-Frame-Options, HSTS, X-Content-Type-Options
- Debug mode enabled in production config
- Default credentials unchanged
- Unnecessary ports/services exposed in config

### F. Insecure Dependencies
- Known CVEs in direct dependencies (from Step 2 audit)
- Packages with no recent updates (>2 years) handling security-critical operations
- Transitive dependencies with critical CVEs

### G. File & Resource Handling
- User-controlled file uploads without type/size validation
- Temporary files with predictable names in shared directories
- Missing cleanup of sensitive temporary data
- TOCTOU (time-of-check/time-of-use) on file operations

## Step 4 — Output

Format each finding as:
```
[CRITICAL|HIGH|MEDIUM|LOW] Category: Title
File: path:line
Issue: description of the vulnerability
Impact: what an attacker could do
Fix: specific remediation
```

Group by severity. End with:

```
## Security Scan Summary
CRITICAL: X | HIGH: Y | MEDIUM: Z | LOW: W

### Immediate action required (CRITICAL + HIGH)
[list]

### Dependency scan
[npm audit / cargo audit summary or "tool not available"]

### Not checked (manual review recommended)
- Infrastructure/network config (out of scope for static scan)
- Runtime behavior (dynamic analysis not performed)
```

## Step 5 — For CRITICAL findings

Offer to fix immediately. For each fix:
1. Show the vulnerable code
2. Show the safe replacement
3. Ask for confirmation before modifying

Do not auto-fix without confirmation — security changes need human review.
