#!/usr/bin/env python3
"""Layer 16 -- Rollback & Undo Capability (PreToolUse on Edit/Write).
Captures file snapshots before edits. Enables rollback to any recent state.
Stores last 20 snapshots per session in ~/.claude/snapshots/.
"""
import hashlib, json, os, shutil, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
SNAPSHOT_DIR = os.path.expanduser("~/.claude/snapshots")
MAX_SNAPSHOTS = 20
MAX_FILE_SIZE = 512 * 1024


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def _ensure_snapshot_dir(snapshot_dir=None):
    d = snapshot_dir or SNAPSHOT_DIR
    os.makedirs(d, exist_ok=True)
    return d


def capture_snapshot(file_path, snapshot_dir=None):
    """Capture file content before edit. Returns snapshot metadata or None."""
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE or size == 0:
            return None
    except Exception:
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return None
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    snap_dir = _ensure_snapshot_dir(snapshot_dir)
    snap_name = "{}_{}.snap".format(int(time.time()), content_hash)
    snap_path = os.path.join(snap_dir, snap_name)
    try:
        with open(snap_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        return None
    return {
        "file_path": file_path,
        "snapshot_path": snap_path,
        "content_hash": content_hash,
        "size": len(content),
        "ts": time.time(),
    }


def prune_snapshots(state):
    """Keep only the last MAX_SNAPSHOTS entries. Remove old snapshot files."""
    snapshots = state.get("layer16_snapshots", [])
    if len(snapshots) <= MAX_SNAPSHOTS:
        return snapshots
    to_remove = snapshots[:-MAX_SNAPSHOTS]
    for s in to_remove:
        try:
            p = s.get("snapshot_path", "")
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
    return snapshots[-MAX_SNAPSHOTS:]


def restore_snapshot(snapshot_meta):
    """Restore a file from a snapshot. Returns True on success."""
    snap_path = snapshot_meta.get("snapshot_path", "")
    file_path = snapshot_meta.get("file_path", "")
    if not snap_path or not file_path:
        return False
    if not os.path.exists(snap_path):
        return False
    try:
        with open(snap_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False


def get_snapshots_for_file(file_path, state=None):
    """Get all snapshots for a given file path, newest first."""
    if state is None:
        state = ss.read_state()
    snapshots = state.get("layer16_snapshots", [])
    norm = os.path.normpath(file_path).replace(chr(92), "/")
    matches = [s for s in snapshots
               if os.path.normpath(s.get("file_path", "")).replace(chr(92), "/") == norm]
    return sorted(matches, key=lambda s: s.get("ts", 0), reverse=True)


def cleanup_session_snapshots(snapshot_dir=None):
    """Remove all snapshot files. Called at session end."""
    d = snapshot_dir or SNAPSHOT_DIR
    if not os.path.isdir(d):
        return 0
    count = 0
    for f in os.listdir(d):
        if f.endswith(".snap"):
            try:
                os.remove(os.path.join(d, f))
                count += 1
            except Exception:
                pass
    return count


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return

    meta = capture_snapshot(file_path)
    if not meta:
        return

    state = ss.read_state()
    snapshots = state.get("layer16_snapshots", [])
    snapshots.append(meta)
    state["layer16_snapshots"] = prune_snapshots({"layer16_snapshots": snapshots})
    ss.write_state(state)

    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer16",
        "category": "FILE_SNAPSHOT",
        "severity": "info",
        "detection_signal": "snapshot captured for {}".format(os.path.basename(file_path)),
        "file_path": file_path,
        "snapshot_count": len(state["layer16_snapshots"]),
    }
    _write_event(event)

    count = len(state["layer16_snapshots"])
    file_snaps = len(get_snapshots_for_file(file_path, state))
    basename = os.path.basename(file_path)
    text = "[Layer 16] Snapshot #{} captured for {} ({} for this file). Undo available.".format(
        count, basename, file_snaps)
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}
    print(json.dumps(out))


if __name__ == "__main__":  # pragma: no cover
    main()
