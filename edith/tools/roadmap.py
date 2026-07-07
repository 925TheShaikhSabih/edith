"""
The roadmap tool — E.D.I.T.H.'s first real capability.

Lets E.D.I.T.H. add, view, and update milestones for ELP's tournament launch.
This is tool-owned storage, deliberately separate from Tier 4's future
long-term memory system: memory (Tier 4) will hold facts about people
(preferences, identities); this holds ELP project data (milestones, status).
Different lifecycle, different owner, kept apart on purpose so Tier 4 doesn't
inherit a pile of unrelated project data when it's built.

Storage: a single JSON file, human-readable and editable by hand if needed —
in the same spirit as Tier 4's "let me see and edit it" principle, applied
early because there's no reason a JSON file needs to be opaque.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edith.tools import Tool


# Kept next to the project root, not inside the edith/ package, so it's
# obviously data and not code — same instinct as keeping secrets in .env
# rather than in source.
ROADMAP_FILE = Path(__file__).resolve().parent.parent.parent / "roadmap.json"

VALID_STATUSES = ("not started", "in progress", "blocked", "done")


def _load() -> list[dict[str, Any]]:
    """Read the roadmap file. Returns an empty list if it doesn't exist yet
    — a fresh install shouldn't need a manual setup step."""
    if not ROADMAP_FILE.exists():
        return []
    try:
        with open(ROADMAP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("roadmap.json does not contain a list")
            return data
    except (json.JSONDecodeError, ValueError) as e:
        # A corrupted or hand-edited-into-brokenness file shouldn't crash
        # the tool. Surface it as a normal failure the model can explain.
        raise RoadmapStorageError(f"roadmap.json is malformed: {e}") from e


def _save(milestones: list[dict[str, Any]]):
    """Write the roadmap file. Writes to a temp file and renames, so a
    crash mid-write can't leave roadmap.json half-written and corrupted."""
    tmp_path = ROADMAP_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(milestones, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, ROADMAP_FILE)  # atomic on POSIX
    except OSError as e:
        raise RoadmapStorageError(f"couldn't write roadmap.json: {e}") from e


class RoadmapStorageError(Exception):
    """Raised on any failure reading/writing the roadmap file. Caught by
    each tool function below and turned into a plain-language result dict
    rather than allowed to propagate — per the doc's Tier 2 edge cases."""
    pass


# ---------------------------------------------------------------------------
# Tool: add_milestone
# ---------------------------------------------------------------------------

def _run_add_milestone(name: str, target_date: str = "", owner: str = "", notes: str = "") -> dict:
    try:
        milestones = _load()
        new_milestone = {
            "id": str(uuid.uuid4())[:8],  # short id, easy for a human to reference back
            "name": name,
            "status": "not started",
            "target_date": target_date or None,
            "owner": owner or None,
            "notes": notes or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        milestones.append(new_milestone)
        _save(milestones)
        return {"ok": True, "milestone": new_milestone}
    except RoadmapStorageError as e:
        return {"ok": False, "error": str(e)}


add_milestone_tool = Tool(
    name="add_milestone",
    description=(
        "Add a new milestone to the ELP tournament launch roadmap. Use this "
        "when the user describes a new goal, deliverable, or deadline that "
        "should be tracked as part of the launch plan."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "A short, clear name for the milestone, e.g. 'Finalize sponsorship deck'.",
            },
            "target_date": {
                "type": "string",
                "description": "Target date or rough timeframe, e.g. '2026-08-15' or 'end of July'. Optional.",
            },
            "owner": {
                "type": "string",
                "description": "Who on the ELP founding team owns this milestone, if known. Optional.",
            },
            "notes": {
                "type": "string",
                "description": "Any additional context worth recording. Optional.",
            },
        },
        "required": ["name"],
    },
    run=_run_add_milestone,
)


# ---------------------------------------------------------------------------
# Tool: view_roadmap
# ---------------------------------------------------------------------------

def _run_view_roadmap(status: str = "") -> dict:
    try:
        milestones = _load()
        if status:
            status_norm = status.strip().lower()
            if status_norm not in VALID_STATUSES:
                return {
                    "ok": False,
                    "error": (
                        f"{status!r} isn't a recognized status. "
                        f"Valid statuses are: {', '.join(VALID_STATUSES)}."
                    ),
                }
            milestones = [m for m in milestones if m["status"] == status_norm]
        return {"ok": True, "count": len(milestones), "milestones": milestones}
    except RoadmapStorageError as e:
        return {"ok": False, "error": str(e)}


view_roadmap_tool = Tool(
    name="view_roadmap",
    description=(
        "View milestones on the ELP tournament launch roadmap. Use this "
        "whenever the user asks what's on the roadmap, what's next, what's "
        "blocked, or anything about current launch progress. Optionally "
        "filter by status."
    ),
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": (
                    "Optional filter. One of: 'not started', 'in progress', "
                    "'blocked', 'done'. Leave empty to see everything."
                ),
            },
        },
        "required": [],
    },
    run=_run_view_roadmap,
)


# ---------------------------------------------------------------------------
# Tool: update_milestone
# ---------------------------------------------------------------------------

def _run_update_milestone(
    milestone_id: str,
    status: str = "",
    target_date: str = "",
    owner: str = "",
    notes: str = "",
) -> dict:
    try:
        milestones = _load()
        match = next((m for m in milestones if m["id"] == milestone_id), None)
        if match is None:
            return {
                "ok": False,
                "error": (
                    f"No milestone found with id {milestone_id!r}. "
                    "Use view_roadmap to see current milestone ids."
                ),
            }

        if status:
            status_norm = status.strip().lower()
            if status_norm not in VALID_STATUSES:
                return {
                    "ok": False,
                    "error": (
                        f"{status!r} isn't a recognized status. "
                        f"Valid statuses are: {', '.join(VALID_STATUSES)}."
                    ),
                }
            match["status"] = status_norm
        if target_date:
            match["target_date"] = target_date
        if owner:
            match["owner"] = owner
        if notes:
            match["notes"] = notes
        match["updated_at"] = datetime.now(timezone.utc).isoformat()

        _save(milestones)
        return {"ok": True, "milestone": match}
    except RoadmapStorageError as e:
        return {"ok": False, "error": str(e)}


update_milestone_tool = Tool(
    name="update_milestone",
    description=(
        "Update an existing milestone on the ELP roadmap — its status, "
        "target date, owner, or notes. Use this when the user reports "
        "progress, a change in ownership, or a new deadline for something "
        "already on the roadmap. Requires the milestone's id (get it from "
        "view_roadmap if you don't already have it from earlier in the "
        "conversation)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "milestone_id": {
                "type": "string",
                "description": "The id of the milestone to update.",
            },
            "status": {
                "type": "string",
                "description": "New status. One of: 'not started', 'in progress', 'blocked', 'done'.",
            },
            "target_date": {
                "type": "string",
                "description": "New target date or timeframe.",
            },
            "owner": {
                "type": "string",
                "description": "New owner.",
            },
            "notes": {
                "type": "string",
                "description": "New or additional notes.",
            },
        },
        "required": ["milestone_id"],
    },
    run=_run_update_milestone,
)
