---
name: source-credibility-reminder
enabled: true
event: prompt
action: warn
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: (?i)(look\s+up|look\s+into|search\s+(for|the)|find\s+(the|out|current)|what\s+is\s+the|what\s+are\s+the|current\s+\w+|latest\s+\w+|rate|limit|deadline|regulation|law|policy|how\s+much|requirement|check\s+(if|the|what)|verify|research|fetch|retrieve\s+(the|from))
---

**Source Standards** — when fetching or citing web content this session:

**Tier priority**: Official/govt/standards (Tier 1) > Established press/professional orgs (Tier 2) > Wikipedia/Stack Overflow with corroboration (Tier 3). Skip blogs, vendor marketing, undated content.

**Recency**: Tax/benefit figures and regulatory thresholds need current-year data. API/library docs need content within 12 months (or use the user-specified version). Regulatory text needs content within 24 months — flag older content as potentially superseded.

**Always state** the source URL and its publication or last-updated date when making factual claims. If no date is visible on the page, say "no date visible" — do not assume current.

User-explicit overrides (e.g., "rough estimate is fine", "I know it's old") suspend freshness requirements.
