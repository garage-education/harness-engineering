"""Marks methods as tools and wraps them, like Spring AI's ``@Tool`` and ``ToolCallbacks.from``."""

import inspect
from collections.abc import Callable
from typing import Any, Final, TypeVar

from langchain_core.tools import BaseTool, StructuredTool

F = TypeVar("F", bound=Callable[..., Any])

DESCRIPTION: Final = "_tool_description"


def tool(description: str) -> Callable[[F], F]:
    """Marks a method as a tool the model can call.

    It plays the part of Spring AI's ``@Tool(description = ...)``.

    Args:
        description: what the tool does and when to use it; the model reads it

    Returns:
        the same method, marked
    """

    def mark(method: F) -> F:
        setattr(method, DESCRIPTION, description)
        return method

    return mark


def tools_from(target: object) -> list[BaseTool]:
    """Wraps each ``@tool`` method of ``target`` in a LangChain tool.

    It plays the part of Spring AI's ``ToolCallbacks.from(target)``.

    Args:
        target: an object with ``@tool`` methods

    Returns:
        one tool per marked method, named after the method
    """
    return [
        StructuredTool.from_function(method, description=getattr(method, DESCRIPTION))
        for _, method in inspect.getmembers(target, inspect.ismethod)
        if hasattr(method, DESCRIPTION)
    ]
