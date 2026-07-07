"""
Shared setup logic for building E.D.I.T.H.'s tool registry.

Extracted here so main.py (text) and main_voice.py (voice) both build the
exact same registry the exact same way — per the harness doc: "if you ever
find yourself writing the agent logic twice, stop and unify it." This isn't
agent logic itself, but it's the same instinct: one definition, reused, not
copy-pasted into a second entry point where it could quietly drift.
"""

from edith.tools import ToolRegistry
from edith.tools.roadmap import add_milestone_tool, view_roadmap_tool, update_milestone_tool
from edith.tools.memory import remember_fact_tool, view_memory_tool, forget_fact_tool


def build_registry() -> ToolRegistry:
    """The registry is built here, once, at startup — this is the one place
    that needs editing to add a new tool later. brain.py itself never
    changes when a new tool is added."""
    registry = ToolRegistry()
    registry.register(add_milestone_tool)
    registry.register(view_roadmap_tool)
    registry.register(update_milestone_tool)
    registry.register(remember_fact_tool)
    registry.register(view_memory_tool)
    registry.register(forget_fact_tool)
    return registry
