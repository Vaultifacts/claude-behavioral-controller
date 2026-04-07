import sys, json, re

# Exact domains known to block automated requests (verified 403s)
# Use mcp__claude-in-chrome or chrome-devtools-mcp for these instead.
#
# IMPORTANT: This is EXACT match only (not subdomain matching).
# Verified-accessible Canada subdomains (return 200 OK -- do NOT add here):
#   ised-isde.canada.ca, ic.gc.ca, canada.ca subdomains generally vary --
#   test each one individually before blocking.
# To add a domain: verify it returns 403 on a real fetch, then add the
# exact host string (e.g. 'www.example.com' and 'example.com' separately).
BLOCKED_DOMAINS = [
    'www.canada.ca',
    'canada.ca',
    'cra-arc.gc.ca',
    'bdo.ca',
    'www.bdo.ca',
    'pwc.com',
    'www.pwc.com',
    'kpmg.com',
    'www.kpmg.com',
    'deloitte.ca',
    'www.deloitte.ca',
    'ey.com',
    'www.ey.com',
]

data = json.loads(sys.stdin.read())
url = data.get('tool_input', {}).get('url', '')
domain = re.search(r'https?://([^/]+)', url)
if domain:
    host = domain.group(1).lower()
    if host in BLOCKED_DOMAINS:
        print(json.dumps({
            "decision": "block",
            "reason": host + " blocks automated requests (403). Use mcp__claude-in-chrome or chrome-devtools-mcp instead."
        }))
        sys.exit(0)
sys.exit(0)
