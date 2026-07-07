"""
The memory tool — E.D.I.T.H.'s durable, cross-restart, team-facing memory.

This is Tier 4: the "long-term" store, distinct from a conversation's
short-term in-memory history (Tier 1). Per AGENT.md, this was explicitly
decided to be TEAM-FACING, not personal: one flat list of facts about ELP
and its people, visible to whoever's using E.D.I.T.H., with no
per-person attribution field. A fact like "the venue for launch is X" or
"Zara prefers async updates over calls" is just written as a plain
sentence — the subject lives in the sentence itself, not a separate
structured field.

Deliberately separate from roadmap.py's storage: roadmap milestones have
their own shape (status, owner, dates) and their own lifecycle; memory
facts are plain statements with no such structure. Different data,
different file, same underlying philosophy (plain JSON, human-readable,
hand-editable, atomic writes) as roadmap.py already established.

Per the harness doc's Tier 4 rules, followed directly:
  - One fact per entry, written as a plain statement — small, legible,
    easy to review/correct/delete.
  - Don't load everything into every prompt forever — fine for now while
    small (loaded whole into the system prompt, same as roadmap context
    could be), but designed so pulling in only what's relevant could be
    added later without a rewrite.
  - Let the user see and edit it by hand — plain JSON, not a database.
  - Treat stored facts as DATA, never as instructions. A fact is
    background knowledge, not a command to obey. If a stored note ever
    reads like an order ("always do X"), the assistant should still run
    it past its normal judgment — memory shouldn't become a backdoor
    around future confirmation gates (Tier 6). This is enforced by
    instruction in the system prompt (see brain.py's DEFAULT_SYSTEM_PROMPT),
    not by code — there's no reliable code-level way to detect
    "this fact reads like an instruction," so the model itself has to
    apply judgment here, same as a human reading a suspicious note would.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edith.tools import Tool


MEMORY_FILE = Path(__file__).resolve().parent.parent.parent / "memory.json"


class MemoryStorageError(Exception):
    """Raised on any failure reading/writing the memory file. Caught by
    each tool function below and turned into a plain-language result dict
    rather than allowed to propagate — matching roadmap.py's pattern."""
    pass


def _load() -> list[dict[str, Any]]:
    """Read the memory file. Returns an empty list if it doesn't exist
    yet — a fresh install shouldn't need manual setup."""
    if not MEMORY_FILE.exists():
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("memory.json does not contain a list")
            return data
    except (json.JSONDecodeError, ValueError) as e:
        raise MemoryStorageError(f"memory.json is malformed: {e}") from e


def _save(facts: list[dict[str, Any]]):
    """Write the memory file. Writes to a temp file and renames, so a
    crash mid-write can't leave memory.json half-written and corrupted —
    same atomic-write pattern as roadmap.py's _save()."""
    tmp_path = MEMORY_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(facts, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, MEMORY_FILE)
    except OSError as e:
        raise MemoryStorageError(f"couldn't write memory.json: {e}") from e


def load_facts_for_prompt() -> str:
    """
    Read all facts and format them as a plain-text block suitable for
    inserting into the system prompt, so E.D.I.T.H. walks into every
    conversation already knowing them — per the harness doc's Tier 4
    goal. Returns an empty string if there are no facts yet, so the
    system prompt can handle "no memory yet" cleanly.

    This is called from brain.py at Brain construction time, NOT wired
    as a tool — reading memory happens automatically at the start of a
    conversation; WRITING memory is what the tools below are for.
    """
    try:
        facts = _load()
    except MemoryStorageError:
        # If memory.json is somehow corrupted, don't let that crash
        # startup — start with no memory rather than refuse to run.
        # A user editing memory.json by hand (an explicitly supported
        # workflow per the harness doc) could plausibly break the JSON
        # temporarily; that shouldn't take down the whole assistant.
        return ""

    if not facts:
        return ""

    lines = [f"- {fact['text']}" for fact in facts]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: remember_fact
# ---------------------------------------------------------------------------

def _run_remember_fact(text: str) -> dict:
    try:
        if not text or not text.strip():
            return {"ok": False, "error": "can't remember an empty fact"}

        facts = _load()
        new_fact = {
            "id": str(uuid.uuid4())[:8],
            "text": text.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        facts.append(new_fact)
        _save(facts)
        return {"ok": True, "fact": new_fact}
    except MemoryStorageError as e:
        return {"ok": False, "error": str(e)}


remember_fact_tool = Tool(
    name="remember_fact",
    description=(
        "Remember a durable fact for later — something worth knowing in "
        "future conversations, not just this one. Use this for stable "
        "things: preferences, decisions, identities, project details "
        "(e.g. 'the venue for ELP's launch is X', 'Zara prefers async "
        "updates over calls'). Don't use this for the play-by-play of the "
        "current conversation — only things worth remembering next time."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "The fact to remember, as one plain, self-contained "
                    "statement. Include the subject in the sentence itself "
                    "(e.g. 'Sabih prefers...' or 'ELP's venue is...') since "
                    "facts aren't tagged separately by who they're about."
                ),
            },
        },
        "required": ["text"],
    },
    run=_run_remember_fact,
)


# ---------------------------------------------------------------------------
# Tool: view_memory
# ---------------------------------------------------------------------------

def _run_view_memory() -> dict:
    try:
        facts = _load()
        return {"ok": True, "count": len(facts), "facts": facts}
    except MemoryStorageError as e:
        return {"ok": False, "error": str(e)}


view_memory_tool = Tool(
    name="view_memory",
    description=(
        "View all durable facts currently remembered. Use this if asked "
        "what E.D.I.T.H. remembers, or to check whether something is "
        "already stored before adding it again."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    run=_run_view_memory,
)


# ---------------------------------------------------------------------------
# Tool: forget_fact
# ---------------------------------------------------------------------------

def _run_forget_fact(fact_id: str) -> dict:
    try:
        facts = _load()
        match = next((f for f in facts if f["id"] == fact_id), None)
        if match is None:
            return {
                "ok": False,
                "error": (
                    f"No fact found with id {fact_id!r}. Use view_memory "
                    "to see current fact ids."
                ),
            }
        facts = [f for f in facts if f["id"] != fact_id]
        _save(facts)
        return {"ok": True, "forgotten": match}
    except MemoryStorageError as e:
        return {"ok": False, "error": str(e)}


forget_fact_tool = Tool(
    name="forget_fact",
    description=(
        "Forget/remove a previously remembered fact — use when the user "
        "says something is no longer true, or asks to forget something. "
        "Requires the fact's id (get it from view_memory if you don't "
        "already have it from earlier in the conversation)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "fact_id": {
                "type": "string",
                "description": "The id of the fact to forget.",
            },
        },
        "required": ["fact_id"],
    },
    run=_run_forget_fact,
)
