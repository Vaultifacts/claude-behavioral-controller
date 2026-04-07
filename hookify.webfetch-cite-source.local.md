---
name: webfetch-cite-source
enabled: true
event: posttooluse
tool_matcher: WebFetch
action: warn
conditions:
  - field: url
    operator: regex_match
    pattern: .*
---

**Source Citation Checklist** — apply to the content just fetched:

1. **Publication date**: Look for "last updated", "published on", or date metadata. If none is visible, state "no date visible" — do not assume the content is current.

2. **Cite the URL** in your response so the user can verify independently.

3. **Freshness thresholds** (flag or re-search if content is older):
   - Tax/benefit figures, regulatory thresholds: current year required
   - API/library/SDK docs: within 12 months (unless user specifies a version)
   - Legal/regulatory guidance: within 24 months

4. **Credibility tier** of the fetched source:
   - Tier 1 (preferred): Official govt/regulator/standards body — cite directly
   - Tier 2 (acceptable): Established press, professional associations — cite with context
   - Tier 3 (needs corroboration): Wikipedia, Stack Overflow — cross-reference before citing
   - Skip: Blogs, vendor marketing, undated SEO content
