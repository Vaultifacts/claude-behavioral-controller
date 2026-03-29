"""
notion-recall.py — SessionStart hook that pulls recent knowledge from Notion.

Closes the learning loop: notion-capture.py writes insights at session end,
this hook reads them back at session start so Claude learns from past mistakes.

Outputs a condensed summary to stdout (injected into Claude's context).
Runs on every SessionStart. Always exits 0. No side effects.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _notion_shared import (
    load_token, detect_project_name, notion_headers,
    NOTION_VERSION, NOTION_BASE,
    DB_LESSONS_LEARNED, DB_EXTERNAL_REFS, DB_GLOSSARY, DB_BROWSER_NAV, DB_PROMPT_LIBRARY,
)


MAX_LESSONS = 10
MAX_REFS = 5
MAX_GLOSSARY = 8
MAX_NAV = 5
MAX_PROMPTS = 3
MAX_AGE_DAYS = 30  # Only pull entries from the last N days


def load_payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def notion_patch(page_id, properties, token):
    """Update a page's properties (e.g. increment Recall Count)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    body = {"properties": properties}
    req = urllib.request.Request(
        f"{NOTION_BASE}/pages/{page_id}",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True
    except Exception:
        return False


def notion_query(db_id, token, filter_obj=None, sorts=None, page_size=10):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    body = {"page_size": page_size}
    if filter_obj:
        body["filter"] = filter_obj
    if sorts:
        body["sorts"] = sorts

    req = urllib.request.Request(
        f"{NOTION_BASE}/databases/{db_id}/query",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"results": []}


def get_text(prop):
    if not prop:
        return ""
    if prop.get("type") == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if prop.get("type") == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if prop.get("type") == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if prop.get("type") == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    return ""


def fetch_lessons(token, project_name=None):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=MAX_AGE_DAYS)).isoformat()
    sorts = [{"property": "Date", "direction": "descending"}]

    # Recency + project filter
    date_filter = {"property": "Date", "date": {"on_or_after": cutoff}}
    if project_name:
        filter_obj = {"and": [
            date_filter,
            {"property": "Project", "multi_select": {"contains": project_name}},
        ]}
    else:
        filter_obj = date_filter

    data = notion_query(DB_LESSONS_LEARNED, token, filter_obj, sorts, MAX_LESSONS)
    results = data.get("results", [])

    # Fetch evergreen lessons: high recall count (>= 3) bypasses age filter
    evergreen_filter = {"property": "Recall Count", "number": {"greater_than_or_equal_to": 3}}
    evergreen_data = notion_query(DB_LESSONS_LEARNED, token, evergreen_filter, sorts, 5)
    seen_ids = {r["id"] for r in results}
    for r in evergreen_data.get("results", []):
        if r["id"] not in seen_ids:
            results.append(r)
            seen_ids.add(r["id"])

    # If project filter returned too few, supplement with unfiltered
    if len(results) < 3 and project_name:
        all_data = notion_query(DB_LESSONS_LEARNED, token, None, sorts, MAX_LESSONS)
        for r in all_data.get("results", []):
            if r["id"] not in seen_ids:
                results.append(r)
                seen_ids.add(r["id"])
                if len(results) >= MAX_LESSONS:
                    break

    # Score and sort by relevance: recency (days ago) + recall frequency
    from datetime import date
    today = date.today()
    scored = []
    for r in results[:MAX_LESSONS * 2]:  # Over-fetch to allow scoring
        props = r.get("properties", {})
        takeaway = get_text(props.get("Takeaway", {}))
        if not takeaway:
            continue
        category = get_text(props.get("Category", {}))
        project = get_text(props.get("Project", {}))
        recall_count = 0
        rc_prop = props.get("Recall Count", {})
        if rc_prop and rc_prop.get("type") == "number" and rc_prop.get("number") is not None:
            recall_count = rc_prop["number"]

        # Recency score: 0-10 (today=10, 30 days ago=0)
        date_str = ""
        date_prop = props.get("Date", {})
        if date_prop and date_prop.get("date"):
            date_str = date_prop["date"].get("start", "")
        try:
            entry_date = date.fromisoformat(date_str)
            days_ago = (today - entry_date).days
            recency = max(0, 10 - (days_ago / 3))
        except Exception:
            recency = 5

        # Project match bonus
        proj_bonus = 3 if (project_name and project_name in project) else 0

        # Total relevance score
        score = recency + min(recall_count, 5) + proj_bonus

        scored.append({
            "id": r["id"],
            "takeaway": takeaway,
            "category": category,
            "project": project,
            "recall_count": recall_count,
            "score": score,
        })

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:MAX_LESSONS]

    # Increment Recall Count for fetched lessons, decay old ones
    # Run in a background thread to avoid blocking session start
    import threading
    fetched_ids = {e["id"] for e in top}
    def _update_counts():
        for entry in scored:
            if entry["id"] in fetched_ids:
                notion_patch(entry["id"], {"Recall Count": {"number": entry["recall_count"] + 1}}, token)
            elif entry["recall_count"] > 0:
                notion_patch(entry["id"], {"Recall Count": {"number": max(0, entry["recall_count"] - 1)}}, token)
    t = threading.Thread(target=_update_counts, daemon=True)
    t.start()

    lessons = []
    for entry in top:
        tag = f" [{entry['project']}]" if entry["project"] else ""
        lessons.append(f"- [{entry['category']}]{tag} {entry['takeaway'][:150]}")
    return lessons


def fetch_glossary(token, project_name=None):
    filter_obj = None
    if project_name:
        filter_obj = {"property": "Project", "multi_select": {"contains": project_name}}
    data = notion_query(DB_GLOSSARY, token, filter_obj, None, MAX_GLOSSARY)
    results = data.get("results", [])

    # Supplement with unfiltered if too few project-specific entries
    if len(results) < 3 and project_name:
        all_data = notion_query(DB_GLOSSARY, token, None, None, MAX_GLOSSARY)
        seen_ids = {r["id"] for r in results}
        for r in all_data.get("results", []):
            if r["id"] not in seen_ids:
                results.append(r)
                if len(results) >= MAX_GLOSSARY:
                    break

    terms = []
    for r in results[:MAX_GLOSSARY]:
        props = r.get("properties", {})
        term = get_text(props.get("Term", {}))
        definition = get_text(props.get("Definition", {}))
        if term and definition:
            terms.append(f"- **{term}**: {definition[:120]}")
    return terms


def fetch_external_refs(token, project_name=None):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=MAX_AGE_DAYS)).isoformat()

    filter_obj = {"property": "Name", "title": {"is_not_empty": True}}
    if project_name:
        filter_obj = {
            "and": [
                {"property": "Project", "multi_select": {"contains": project_name}},
                {"property": "Name", "title": {"is_not_empty": True}},
            ]
        }
    data = notion_query(DB_EXTERNAL_REFS, token, filter_obj, None, MAX_REFS)
    results = data.get("results", [])

    # Supplement with unfiltered if too few
    if len(results) < 2 and project_name:
        all_data = notion_query(DB_EXTERNAL_REFS, token, None, None, MAX_REFS)
        seen_ids = {r["id"] for r in results}
        for r in all_data.get("results", []):
            if r["id"] not in seen_ids:
                results.append(r)
                if len(results) >= MAX_REFS:
                    break

    refs = []
    for r in results[:MAX_REFS]:
        props = r.get("properties", {})
        name = get_text(props.get("Name", {}))
        category = get_text(props.get("Category", {}))
        notes = get_text(props.get("Notes", {}))
        if name:
            refs.append(f"- [{category}] {name}: {notes[:100]}")
    return refs


def fetch_prompts(token, project_name=None):
    sorts = [{"property": "Last Used", "direction": "descending"}]
    filter_obj = None
    if project_name:
        filter_obj = {"property": "Project", "multi_select": {"contains": project_name}}
    data = notion_query(DB_PROMPT_LIBRARY, token, filter_obj, sorts, MAX_PROMPTS)
    results = data.get("results", [])
    if len(results) < 2 and project_name:
        all_data = notion_query(DB_PROMPT_LIBRARY, token, None, sorts, MAX_PROMPTS)
        seen_ids = {r["id"] for r in results}
        for r in all_data.get("results", []):
            if r["id"] not in seen_ids:
                results.append(r)
                if len(results) >= MAX_PROMPTS:
                    break
    prompts = []
    for r in results[:MAX_PROMPTS]:
        props = r.get("properties", {})
        name = get_text(props.get("Name", {}))
        ptype = get_text(props.get("Type", {}))
        rating = get_text(props.get("Success Rate", {}))
        if name:
            prompts.append(f"- [{ptype}] {name} {rating}")
    return prompts


def fetch_browser_nav(token):
    sorts = [{"property": "Attempt Count", "direction": "descending"}]
    data = notion_query(DB_BROWSER_NAV, token, None, sorts, MAX_NAV)
    patterns = []
    for r in data.get("results", []):
        props = r.get("properties", {})
        action = get_text(props.get("Action", {}))
        app = get_text(props.get("App", {}))
        if action:
            patterns.append(f"- {app}: {action[:100]}")
    return patterns


def main():
    payload = load_payload()
    token = load_token()
    if not token:
        return

    project_name = detect_project_name(payload)

    # Parallel queries — fetch all 5 databases concurrently
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(fetch_lessons, token, project_name): "lessons",
            pool.submit(fetch_glossary, token, project_name): "glossary",
            pool.submit(fetch_prompts, token, project_name): "prompts",
            pool.submit(fetch_external_refs, token, project_name): "refs",
            pool.submit(fetch_browser_nav, token): "nav",
        }
        for future in as_completed(futures, timeout=15):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception:
                results[key] = []

    sections = []

    lessons = results.get("lessons", [])
    if lessons:
        header = "Lessons Learned"
        if project_name:
            header += f" (prioritizing {project_name})"
        sections.append(f"## {header}\n" + "\n".join(lessons))

    glossary = results.get("glossary", [])
    if glossary:
        sections.append("## Key Terms\n" + "\n".join(glossary))

    prompts = results.get("prompts", [])
    if prompts:
        sections.append("## Top Prompts\n" + "\n".join(prompts))

    refs = results.get("refs", [])
    if refs:
        sections.append("## External References\n" + "\n".join(refs))

    nav = results.get("nav", [])
    if nav:
        sections.append("## Browser Navigation Patterns\n" + "\n".join(nav))

    if sections:
        proj_tag = f" | project: {project_name}" if project_name else ""
        output = f"[notion-recall]{proj_tag} Knowledge from past sessions:\n\n"
        output += "\n\n".join(sections)
        output += "\n\nApply these lessons to avoid repeating past mistakes."
        print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
