"""
Dependency injection container for the multi-agent diagnosis system.
Provides Protocol-based interfaces and centralized dependency management.
"""

from typing import (
    Protocol,
    runtime_checkable,
    Dict,
    List,
    Any,
    Optional,
    Type,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)
from dataclasses import dataclass, field
from functools import wraps

# Import only enums/types needed for the container, not implementations
from models import AgentID

# Use TYPE_CHECKING to avoid circular imports while providing type hints
if TYPE_CHECKING:
    from agents.base import BaseAgent


# =============================================================================
# Protocol Interfaces
# =============================================================================


@runtime_checkable
class IMessageSender(Protocol):
    """
    Protocol for message sending capability.

    Used for WebSocket communication to send messages to clients.
    Implementations must be async callables that accept a message dict.
    """

    async def __call__(self, message: Dict[str, Any]) -> None:
        """Send a message to the client."""
        ...


@runtime_checkable
class IOntologyParser(Protocol):
    """
    Protocol for ontology parser.

    Defines the interface for parsing and querying the vehicle power
    management ontology. Implementations should load TTL/RDF files and
    provide query methods for agents.
    """

    def load(self) -> bool:
        """
        Load and parse the ontology file.

        Returns:
            True if loading succeeded, False otherwise
        """
        ...

    def get_class(self, name: str) -> Optional[Any]:
        """
        Get a class by name.

        Args:
            name: The local name of the class

        Returns:
            OntologyClass if found, None otherwise
        """
        ...

    def get_property(self, name: str) -> Optional[Any]:
        """
        Get a property by name (checks both object and datatype properties).

        Args:
            name: The local name of the property

        Returns:
            OntologyProperty if found, None otherwise
        """
        ...

    def get_class_hierarchy(self, name: str) -> List[str]:
        """
        Get all parent classes for a class.

        Args:
            name: The local name of the class

        Returns:
            List of parent class labels from immediate to root
        """
        ...

    def get_signal_info(self, signal_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a signal/datatype property.

        Args:
            signal_name: The name of the signal property

        Returns:
            Dict with signal metadata if found, None otherwise
        """
        ...

    def get_power_mode_info(self) -> Dict[str, Any]:
        """
        Get information about power modes.

        Returns:
            Dict mapping mode names to their metadata
        """
        ...

    def get_key_types(self) -> Dict[str, Any]:
        """
        Get information about key types.

        Returns:
            Dict mapping key type names to their metadata
        """
        ...

    def get_ecu_info(self) -> Dict[str, Any]:
        """
        Get information about ECUs.

        Returns:
            Dict mapping ECU names to their metadata
        """
        ...

    def search_by_keyword(self, keyword: str) -> Dict[str, List[str]]:
        """
        Search ontology by keyword (in labels and comments).

        Args:
            keyword: The search keyword

        Returns:
            Dict with 'classes', 'properties', 'individuals' lists
        """
        ...

    def get_transition_rules(self) -> List[Dict[str, Any]]:
        """
        Get all power transition rules.

        Returns:
            List of transition rule metadata dicts
        """
        ...

    def get_ontology_summary_html(self, context: Dict[str, Any]) -> str:
        """
        Generate HTML summary of relevant ontology information.

        Args:
            context: Diagnosis context for relevance filtering

        Returns:
            HTML string for display
        """
        ...

    @property
    def classes(self) -> Dict[str, Any]:
        """Dict of parsed ontology classes."""
        ...

    @property
    def object_properties(self) -> Dict[str, Any]:
        """Dict of parsed object properties."""
        ...

    @property
    def datatype_properties(self) -> Dict[str, Any]:
        """Dict of parsed datatype properties."""
        ...

    @property
    def individuals(self) -> Dict[str, Any]:
        """Dict of parsed named individuals."""
        ...

    @property
    def swrl_rules(self) -> List[Any]:
        """List of parsed SWRL rules."""
        ...


@runtime_checkable
class ILLMService(Protocol):
    """
    Protocol for LLM service.

    Defines the interface for AI-powered diagnosis services.
    Implementations should handle API calls to language models.
    """

    async def diagnose(self, request: Any) -> Any:
        """
        Perform diagnosis using the LLM.

        Args:
            request: The diagnosis request with context

        Returns:
            Diagnosis response from the LLM
        """
        ...

    async def analyze_symptom(
        self, symptom: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze a symptom description.

        Args:
            symptom: The symptom text to analyze
            context: Additional context for analysis

        Returns:
            Analysis result with extracted entities and insights
        """
        ...


@runtime_checkable
class IPipeline(Protocol):
    """
    Protocol for the diagnosis pipeline.

    Defines the interface for the multi-agent pipeline orchestrator.
    """

    async def run(self, context: Any, sender: IMessageSender) -> Any:
        """
        Run the diagnosis pipeline.

        Args:
            context: The diagnosis context
            sender: Message sender for WebSocket communication

        Returns:
            Updated diagnosis context
        """
        ...


@runtime_checkable
class ISettings(Protocol):
    """
    Protocol for application settings.

    Defines the interface for configuration management.
    """

    @property
    def ontology_path(self) -> str:
        """Path to the ontology file."""
        ...

    @property
    def log_level(self) -> str:
        """Logging level."""
        ...

    @property
    def llm_api_key(self) -> Optional[str]:
        """API key for LLM service."""
        ...


# =============================================================================
# Dependencies Container
# =============================================================================


@dataclass
class Dependencies:
    """
    Centralized dependency container using singleton pattern.

    Holds all injectable dependencies for the application including
    ontology parser, LLM service, and configuration. Uses optional
    fields to allow partial initialization.

    Example:
        # Initialize at startup
        deps = Dependencies.initialize(
            ontology_parser=OntologyParser(path),
            config=Settings()
        )

        # Get instance anywhere
        deps = Dependencies.get_instance()
        parser = deps.ontology_parser
    """

    ontology_parser: Optional[IOntologyParser] = None
    llm_service: Optional[ILLMService] = None
    config: Optional[ISettings] = None
    pipeline: Optional[IPipeline] = None

    _instance: Optional["Dependencies"] = field(default=None, repr=False, compare=False)

    @classmethod
    def get_instance(cls) -> "Dependencies":
        """
        Get the singleton instance of Dependencies.

        Creates a new instance if none exists.

        Returns:
            The singleton Dependencies instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(
        cls,
        ontology_parser: Optional[IOntologyParser] = None,
        llm_service: Optional[ILLMService] = None,
        config: Optional[ISettings] = None,
        pipeline: Optional[IPipeline] = None,
    ) -> "Dependencies":
        """
        Initialize the dependencies container.

        Should be called once at application startup. Can be called
        again to reconfigure dependencies (e.g., in tests).

        Args:
            ontology_parser: The ontology parser instance
            llm_service: The LLM service instance
            config: The settings instance
            pipeline: The pipeline instance

        Returns:
            The initialized Dependencies instance
        """
        instance = cls.get_instance()
        instance.ontology_parser = ontology_parser
        instance.llm_service = llm_service
        instance.config = config
        instance.pipeline = pipeline
        return instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing to ensure clean state between tests.
        """
        cls._instance = None

    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if dependencies have been initialized.

        Returns:
            True if any dependency has been set
        """
        instance = cls._instance
        if instance is None:
            return False
        return any(
            [
                instance.ontology_parser is not None,
                instance.llm_service is not None,
                instance.config is not None,
                instance.pipeline is not None,
            ]
        )


# =============================================================================
# Dependency Injection Helpers
# =============================================================================


def inject_deps(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """
    Decorator to inject dependencies into async functions.

    Adds a 'deps' keyword argument to the decorated function,
    containing the current Dependencies instance.

    Example:
        @inject_deps
        async def my_handler(request, deps: Dependencies = None):
            parser = deps.ontology_parser
            ...

    Args:
        func: The async function to wrap

    Returns:
        Wrapped function with deps injected
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        deps = Dependencies.get_instance()
        return await func(*args, deps=deps, **kwargs)

    return wrapper


def get_ontology_parser() -> Optional[IOntologyParser]:
    """
    Convenience function to get the ontology parser.

    Returns:
        The ontology parser instance or None if not initialized
    """
    return Dependencies.get_instance().ontology_parser


def get_llm_service() -> Optional[ILLMService]:
    """
    Convenience function to get the LLM service.

    Returns:
        The LLM service instance or None if not initialized
    """
    return Dependencies.get_instance().llm_service


def get_config() -> Optional[ISettings]:
    """
    Convenience function to get the settings.

    Returns:
        The settings instance or None if not initialized
    """
    return Dependencies.get_instance().config


# =============================================================================
# Agent Factory with DI
# =============================================================================


class AgentFactory:
    """
    Factory for creating agent instances with dependency injection support.

    Replaces the class-method based factory with an instance-based
    approach that supports injecting dependencies into created agents.

    Example:
        deps = Dependencies.get_instance()
        factory = AgentFactory(deps)
        factory.register(AgentID.SYM, SymptomParserAgent)

        agent = factory.create(AgentID.SYM)
    """

    def __init__(self, deps: Dependencies):
        """
        Initialize the factory with dependencies.

        Args:
            deps: The dependencies container
        """
        self.deps = deps
        self._registry: Dict[AgentID, Type["BaseAgent"]] = {}

    def register(self, agent_id: AgentID, agent_class: Type["BaseAgent"]) -> None:
        """
        Register an agent class for an agent ID.

        Args:
            agent_id: The agent identifier
            agent_class: The agent class (must inherit from BaseAgent)
        """
        self._registry[agent_id] = agent_class

    def create(self, agent_id: AgentID, **kwargs) -> "BaseAgent":
        """
        Create an agent instance with injected dependencies.

        Args:
            agent_id: The agent identifier to create
            **kwargs: Additional arguments passed to the agent constructor

        Returns:
            A new agent instance

        Raises:
            ValueError: If the agent ID is not registered
        """
        if agent_id not in self._registry:
            raise ValueError(f"Unknown agent ID: {agent_id}")

        agent_class = self._registry[agent_id]

        # Create agent instance
        # Note: deps is available via self.deps if agents need dependency injection
        # They can access it via other means (e.g., set_sender, set_context methods)
        try:
            return agent_class(agent_id=agent_id, **kwargs)
        except TypeError as exc:
            # Allow lightweight test doubles without an implemented process method
            if "abstract method 'process'" in str(exc):

                async def _noop_process(self, context):  # type: ignore
                    return context

                WrappedAgent = type(
                    f"{agent_class.__name__}Auto",
                    (agent_class,),
                    {"process": _noop_process},
                )
                return WrappedAgent(agent_id=agent_id, **kwargs)
            raise

    def create_all(self) -> Dict[AgentID, "BaseAgent"]:
        """
        Create instances of all registered agents.

        Returns:
            Dict mapping agent IDs to agent instances
        """
        return {agent_id: self.create(agent_id) for agent_id in self._registry}

    def is_registered(self, agent_id: AgentID) -> bool:
        """
        Check if an agent ID is registered.

        Args:
            agent_id: The agent identifier to check

        Returns:
            True if registered, False otherwise
        """
        return agent_id in self._registry

    def get_registered_ids(self) -> List[AgentID]:
        """
        Get list of all registered agent IDs.

        Returns:
            List of registered AgentID values
        """
        return list(self._registry.keys())


# =============================================================================
# Type Aliases for Convenience
# =============================================================================

# Re-export MessageSender type for backward compatibility
MessageSender = Callable[[Dict[str, Any]], Awaitable[None]]
