---
name: stop-fetch-failure-pattern
enabled: true
event: stop
action: warn
conditions:
  - field: transcript
    operator: regex_match
    pattern: (?s)(?:403|404 Not Found)(?:.*?)(?:403|404 Not Found)(?:.*?)(?:403|404 Not Found)
---

**Repeated fetch failures detected in this session** (3+ HTTP 403/404 errors found in transcript).

This pattern usually means URLs were guessed or constructed from memory rather than discovered via WebSearch first.

Review before the next session:
- Were URLs searched for before fetching, or assumed?
- Did any fetches hit bot-blocked domains (canada.ca, bdo.ca, pwc.com, kpmg.com, deloitte.ca, ey.com)? Use mcp__claude-in-chrome or chrome-devtools-mcp for those.
- Were 403s retried? A 403 is a permanent bot block — retrying the same URL will always fail.
