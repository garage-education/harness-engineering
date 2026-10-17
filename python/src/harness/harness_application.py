"""Starts the harness."""

import uvicorn
from fastapi import FastAPI

from harness.ai_config import AiConfig
from harness.application_properties import ApplicationProperties
from harness.assistant import Assistant
from harness.log_tools import LogTools
from harness.test_controller import TestController


def create_app() -> FastAPI:
    """Creates every object and wires them together.

    It plays the part of Spring's application context: one place builds each object once
    and passes it to the constructors that need it.

    Returns:
        the web app, with the ``TestController`` routes
    """
    properties = ApplicationProperties.load()
    chat = AiConfig(properties).chat_model()
    log_tools = LogTools()
    controller = TestController(Assistant(chat, log_tools))
    app = FastAPI(title="harness")
    app.include_router(controller.router)
    return app


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
