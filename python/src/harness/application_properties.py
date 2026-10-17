"""Reads application.yaml into one typed object."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

DEFAULT_PATH: Final = Path(__file__).resolve().parents[2] / "application.yaml"


@dataclass(frozen=True)
class ApplicationProperties:
    """The settings in ``application.yaml``.

    Spring Boot binds ``application.yaml`` for you. Python reads it here, once, at startup.

    Attributes:
        port: the HTTP port, 8080
        base_url: the LM Studio URL, ending in ``/v1``
        api_key: any value; LM Studio ignores it
        chat_model: the chat model identifier in LM Studio
        log_prompt: log every prompt sent to the model
        log_completion: log every reply from the model
        logging: the ``logging`` section, in ``logging.config.dictConfig`` format
    """

    port: int
    base_url: str
    api_key: str
    chat_model: str
    log_prompt: bool
    log_completion: bool
    logging: dict[str, Any]

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> ApplicationProperties:
        """Reads ``application.yaml``.

        Args:
            path: the file to read; ``python/application.yaml`` by default

        Returns:
            the settings
        """
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        openai = data["ai"]["openai"]
        observations = data["ai"]["chat"]["observations"]
        return cls(
            port=data["server"]["port"],
            base_url=openai["base-url"],
            api_key=openai["api-key"],
            chat_model=openai["chat"]["model"],
            log_prompt=observations["log-prompt"],
            log_completion=observations["log-completion"],
            logging=data["logging"],
        )
