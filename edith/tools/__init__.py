"""
The tool registry: the shape every E.D.I.T.H. capability follows.

Per AGENT.md and the harness doc, this is the thing meant to be extended
forever. Adding a new capability later should mean writing one self-contained
Tool and registering it here — never editing brain.py's core loop.

A Tool is:
  - a name the model calls it by
  - a description written for a reader (the model), not a compiler
  - a JSON-schema-shaped input spec (OpenAPI style, per the Gemini API)
  - a run() function that takes validated kwargs and returns a plain string
    or plain dict result — never raises. Failures are caught inside run()
    and returned as a result the model can reason over, per the doc's
    "the agent reasoning over a failed tool result is a feature" note.
"""

from dataclasses import dataclass
from typing import Any, Callable

from google.genai import types as genai_types


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # OpenAPI-style JSON schema
    run: Callable[..., dict[str, Any]]

    def to_gemini_declaration(self) -> genai_types.FunctionDeclaration:
        """Shape this tool as a real genai.types.FunctionDeclaration.

        IMPORTANT — this had a bug in an earlier version: the SDK's types
        here are strict pydantic models (extra='forbid'), so a raw dict
        like {"type": "function", "name": ..., ...} gets rejected outright
        — that "type" key isn't a real field on FunctionDeclaration and
        pydantic refuses it rather than ignoring it. The offline stub used
        during development accepted anything, which is exactly why this
        slipped through testing: the stub couldn't catch a validation
        error that only the real pydantic model raises. Confirmed against
        three independent current sources (Google's own docs, the SDK
        GitHub README, and PyPI) before fixing, since guessing wrong twice
        here isn't acceptable.
        """
        return genai_types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class ToolRegistry:
    """Holds every tool E.D.I.T.H. currently has. brain.py hands this to
    Gemini each turn and looks tools up by name when the model calls one."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"a tool named {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def as_gemini_tools(self) -> list[genai_types.FunctionDeclaration]:
        """The list to pass into types.Tool(function_declarations=...)."""
        return [t.to_gemini_declaration() for t in self._tools.values()]

    def __len__(self):
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())
