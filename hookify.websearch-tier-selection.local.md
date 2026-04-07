---
name: websearch-tier-selection
enabled: true
event: posttooluse
tool_matcher: WebSearch
action: warn
conditions:
  - field: query
    operator: regex_match
    pattern: .*
---

**Search Result Selection** — before choosing which URLs to fetch:

1. **Tier 1 first** (official/government/standards body results): Prefer `canada.ca`, `gc.ca`, `irs.gov`, `iso.org`, IETF RFCs, official library/framework docs, peer-reviewed DOIs. These are authoritative and should be selected over secondary sources when available.

2. **Tier 2 if Tier 1 unavailable**: CBC, Globe and Mail, Reuters, AP, CPA Canada, academic institutions, professional associations.

3. **Tier 3 with corroboration only**: Wikipedia, Stack Overflow (vote count > 50 + recent), MDN for web APIs. Cross-reference against a Tier 1/2 source before citing.

4. **Skip entirely**: Personal blogs, vendor/marketing pages, undated content, press releases as primary fact, SEO content farms.

5. **Bot-blocked domains** (will 403 — use mcp__claude-in-chrome or chrome-devtools-mcp instead): `canada.ca`, `cra-arc.gc.ca`, `bdo.ca`, `pwc.com`, `kpmg.com`, `deloitte.ca`, `ey.com`.
