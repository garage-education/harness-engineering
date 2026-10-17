"""Starts the harness."""

import uvicorn
from fastapi import FastAPI

from harness.application_properties import ApplicationProperties


def create_app() -> FastAPI:
    """Creates every object and wires them together.

    It plays the part of Spring's application context: one place builds each object once
    and passes it to the constructors that need it. Chapter 3 adds the first objects.

    Returns:
        the web app
    """
    return FastAPI(title="harness")


def main() -> None:
    """Runs the app on port 8080.

    ``reload=True`` restarts the app when a source file changes, like Spring Boot DevTools.
    """
    properties = ApplicationProperties.load()
    uvicorn.run(
        "harness.harness_application:create_app",
        factory=True,
        port=properties.port,
        reload=True,
        log_config=properties.logging,
    )
