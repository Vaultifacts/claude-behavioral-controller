---
name: smart-web-research
enabled: true
event: prompt
pattern: .*
action: warn
---

**Web Research Strategy** — Apply this whenever this task involves fetching web content:

1. **Search first, fetch second**: Use `WebSearch` to find current valid URLs before attempting `WebFetch`. Never guess or construct URLs from memory — they go stale and produce 404s.

2. **Know what blocks bots** (these will 403 every time — use browser automation instead):
   - All `canada.ca` / CRA pages
   - Professional services: `bdo.ca`, `pwc.com`, `kpmg.com`, `deloitte.ca`, `ey.com`
   - Use `mcp__claude-in-chrome` or `chrome-devtools-mcp` for these domains.

3. **Don't retry 403s**: A 403 is a server-side bot block, not a transient failure. Retrying the same URL will not change the result.

4. **Follow redirects explicitly**: If you receive a 301/302, extract the destination URL and make a new `WebFetch` call to it — don't treat the redirect response as content.

5. **Treat tiny responses as failures**: Any response under ~500 bytes is almost certainly a redirect stub or empty page, not real content.

If this task does not involve web research, ignore this message.
