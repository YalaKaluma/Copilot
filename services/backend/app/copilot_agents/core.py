from abc import ABC, abstractmethod
from typing import AsyncGenerator
from models.copilot.base import ChatEvent
from config.versioning import ResolvedVersion
from models.copilot.orchestrators import OrchestratorEvent
from services.llm.openai_client import AsyncOpenaiClient
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client
from services.python_repl import PythonREPL


class Agent(ABC):
    def __init__(
        self,
        session_id: str,
        chat_history: list[ChatEvent],
        llm_service: AsyncOpenaiClient,
        skai_service: SKAIApi | SkaiApiV2Client,
        version_config: ResolvedVersion,
    ):
        self.session_id = session_id
        self.chat_history = chat_history
        self.llm_service = llm_service
        self.skai_service = skai_service
        self._version_config = version_config
        self.version_id = version_config.config.version
        self.python_repl: PythonREPL | None = None

    @abstractmethod
    def execute(self, *args, **kwargs) -> AsyncGenerator[OrchestratorEvent, None]:
        pass
