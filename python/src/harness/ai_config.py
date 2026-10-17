"""Creates the objects that talk to the model."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from harness.application_properties import ApplicationProperties
from harness.observation_logging import ChatModelObservationHandler


class AiConfig:
    """Creates the objects that talk to the model.

    It plays the part of the Spring ``@Configuration`` class.
    """

    def __init__(self, properties: ApplicationProperties) -> None:
        self.properties = properties

    def chat_model(self) -> BaseChatModel:
        """Builds one chat model for the whole app.

        ``ChatOpenAI`` speaks the OpenAI API, so ``base_url`` points it at LM Studio.
        Every class that needs the model receives this object.

        Returns:
            the shared chat model
        """
        return ChatOpenAI(
            base_url=self.properties.base_url,
            api_key=SecretStr(self.properties.api_key),
            model=self.properties.chat_model,
            callbacks=[ChatModelObservationHandler(self.properties.log_prompt, self.properties.log_completion)],
        )
