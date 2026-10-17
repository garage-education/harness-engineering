"""Log tools the model can call."""

import logging
from typing import Annotated, Final

from pydantic import Field

from harness.tool_support import tool

log: Final = logging.getLogger(__name__)


class LogTools:
    """Log tools the model can call.

    The model sees only the tool name, the ``@tool`` description, and each parameter
    description. It never sees the method body.
    """

    @tool(description="Count error log events for one service in the last N minutes. Use this to check for a current error spike.")
    def count_errors(
        self,
        service: Annotated[str, Field(description="Service name, for example checkout")],
        minutes: Annotated[int, Field(description="Look-back window in minutes, from 1 to 1440")],
    ) -> int:
        """Counts error log events for one service.

        The data is fake. The ``checkout`` service returns 412. Every other service returns 3.

        Args:
            service: the service name, for example ``checkout``
            minutes: the look-back window in minutes, from 1 to 1440; the fake data ignores it

        Returns:
            the number of error events
        """
        count = 412 if service == "checkout" else 3  # fake data
        log.debug("[tool] count_errors(service=%s, minutes=%s) returned %s", service, minutes, count)
        return count
