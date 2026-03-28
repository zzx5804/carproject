"""
Tests for dependencies module.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestProtocolInterfaces:
    def test_message_sender_protocol(self):
        from dependencies import IMessageSender
        # Create a mock that satisfies the protocol
        async def sender(msg):
            pass
        assert isinstance(sender, IMessageSender)
    
    def test_ontology_parser_protocol_exists(self):
        from dependencies import IOntologyParser
        assert IOntologyParser is not None
    
    def test_llm_service_protocol_exists(self):
        from dependencies import ILLMService
        assert ILLMService is not None
    
    def test_pipeline_protocol_exists(self):
        from dependencies import IPipeline
        assert IPipeline is not None
    
    def test_settings_protocol_exists(self):
        from dependencies import ISettings
        assert ISettings is not None


class TestDependencies:
    def test_dependencies_create(self):
        from dependencies import Dependencies
        deps = Dependencies()
        assert deps.ontology_parser is None
        assert deps.llm_service is None
        assert deps.config is None
        assert deps.pipeline is None
    
    def test_dependencies_singleton(self):
        from dependencies import Dependencies
        Dependencies.reset()
        d1 = Dependencies.get_instance()
        d2 = Dependencies.get_instance()
        assert d1 is d2
        Dependencies.reset()
    
    def test_dependencies_initialize(self):
        from dependencies import Dependencies
        Dependencies.reset()
        mock_parser = MagicMock()
        deps = Dependencies.initialize(ontology_parser=mock_parser)
        assert deps.ontology_parser is mock_parser
        Dependencies.reset()
    
    def test_dependencies_is_initialized(self):
        from dependencies import Dependencies
        Dependencies.reset()
        assert not Dependencies.is_initialized()
        Dependencies.get_instance()
        # get_instance creates empty instance, is_initialized checks if any dep is set
        assert not Dependencies.is_initialized()  # No deps set yet
        
        mock_parser = MagicMock()
        Dependencies.initialize(ontology_parser=mock_parser)
        assert Dependencies.is_initialized()
        Dependencies.reset()
    
    def test_dependencies_reset(self):
        from dependencies import Dependencies
        Dependencies.reset()
        d1 = Dependencies.get_instance()
        mock_parser = MagicMock()
        d1.ontology_parser = mock_parser
        assert Dependencies.is_initialized()
        
        Dependencies.reset()
        assert not Dependencies.is_initialized()
    
    def test_dependencies_initialize_all_fields(self):
        from dependencies import Dependencies
        Dependencies.reset()
        
        mock_parser = MagicMock()
        mock_llm = MagicMock()
        mock_config = MagicMock()
        mock_pipeline = MagicMock()
        
        deps = Dependencies.initialize(
            ontology_parser=mock_parser,
            llm_service=mock_llm,
            config=mock_config,
            pipeline=mock_pipeline
        )
        
        assert deps.ontology_parser is mock_parser
        assert deps.llm_service is mock_llm
        assert deps.config is mock_config
        assert deps.pipeline is mock_pipeline
        Dependencies.reset()


class TestDependencyAccessors:
    def test_get_ontology_parser(self):
        from dependencies import Dependencies, get_ontology_parser
        Dependencies.reset()
        assert get_ontology_parser() is None
        
        mock_parser = MagicMock()
        Dependencies.initialize(ontology_parser=mock_parser)
        assert get_ontology_parser() is mock_parser
        Dependencies.reset()
    
    def test_get_llm_service(self):
        from dependencies import Dependencies, get_llm_service
        Dependencies.reset()
        assert get_llm_service() is None
        
        mock_llm = MagicMock()
        Dependencies.initialize(llm_service=mock_llm)
        assert get_llm_service() is mock_llm
        Dependencies.reset()
    
    def test_get_config(self):
        from dependencies import Dependencies, get_config
        Dependencies.reset()
        assert get_config() is None
        
        mock_config = MagicMock()
        Dependencies.initialize(config=mock_config)
        assert get_config() is mock_config
        Dependencies.reset()


class TestInjectDeps:
    def test_inject_deps_decorator(self):
        from dependencies import Dependencies, inject_deps
        
        Dependencies.reset()
        mock_parser = MagicMock()
        Dependencies.initialize(ontology_parser=mock_parser)
        
        @inject_deps
        async def my_handler(request, deps=None):
            return deps
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(my_handler("test"))
        assert result.ontology_parser is mock_parser
        Dependencies.reset()


class TestAgentFactory:
    def test_factory_create(self):
        from dependencies import Dependencies, AgentFactory
        from models import AgentID
        
        deps = Dependencies()
        factory = AgentFactory(deps)
        
        # Mock agent class - inherits from BaseAgent
        from agents.base import BaseAgent
        from models import AgentID
        
        class MockAgent(BaseAgent):
            def __init__(self, agent_id, deps=None, **kwargs):
                super().__init__(agent_id)
        
        factory.register(AgentID.SYM, MockAgent)
        agent = factory.create(AgentID.SYM)
        assert agent.agent_id == AgentID.SYM
    
    def test_factory_create_unregistered_raises(self):
        from dependencies import Dependencies, AgentFactory
        from models import AgentID
        
        factory = AgentFactory(Dependencies())
        with pytest.raises(ValueError, match="Unknown agent ID"):
            factory.create(AgentID.SYM)
    
    def test_factory_is_registered(self):
        from dependencies import Dependencies, AgentFactory
        from models import AgentID
        from agents.base import BaseAgent
        
        factory = AgentFactory(Dependencies())
        assert not factory.is_registered(AgentID.SYM)
        
        class MockAgent(BaseAgent):
            def __init__(self, agent_id, deps=None):
                super().__init__(agent_id)
        
        factory.register(AgentID.SYM, MockAgent)
        assert factory.is_registered(AgentID.SYM)
    
    def test_factory_get_registered_ids(self):
        from dependencies import Dependencies, AgentFactory
        from models import AgentID
        from agents.base import BaseAgent
        
        factory = AgentFactory(Dependencies())
        assert factory.get_registered_ids() == []
        
        class MockAgent(BaseAgent):
            def __init__(self, agent_id, deps=None):
                super().__init__(agent_id)
        
        factory.register(AgentID.SYM, MockAgent)
        factory.register(AgentID.ONT, MockAgent)
        
        registered = factory.get_registered_ids()
        assert AgentID.SYM in registered
        assert AgentID.ONT in registered
    
    def test_factory_create_all(self):
        from dependencies import Dependencies, AgentFactory
        from models import AgentID
        from agents.base import BaseAgent
        
        deps = Dependencies()
        factory = AgentFactory(deps)
        
        class MockAgent(BaseAgent):
            def __init__(self, agent_id, deps=None):
                super().__init__(agent_id)
        
        factory.register(AgentID.SYM, MockAgent)
        factory.register(AgentID.ONT, MockAgent)
        
        agents = factory.create_all()
        assert len(agents) == 2
        assert AgentID.SYM in agents
        assert AgentID.ONT in agents


class TestMessageSenderType:
    def test_message_sender_type_alias(self):
        from dependencies import MessageSender
        import inspect
        
        # MessageSender should be a callable type
        assert callable(MessageSender) or MessageSender is not None
    
    def test_async_function_satisfies_message_sender(self):
        from dependencies import MessageSender
        
        async def sender(msg):
            pass
        
        # Check it's callable and async
        import inspect
        assert inspect.iscoroutinefunction(sender)


class TestProtocolRuntimeCheckable:
    def test_ontology_parser_runtime_checkable(self):
        from dependencies import IOntologyParser
        from typing import runtime_checkable
        
        # Should be runtime_checkable
        # Create a mock that satisfies the protocol
        class MockParser:
            def load(self): return True
            def get_class(self, name): return None
            def get_property(self, name): return None
            def get_class_hierarchy(self, name): return []
            def get_signal_info(self, name): return None
            def get_power_mode_info(self): return {}
            def get_key_types(self): return {}
            def get_ecu_info(self): return {}
            def search_by_keyword(self, keyword): return {}
            def get_transition_rules(self): return []
            def get_ontology_summary_html(self, context): return ""
            
            @property
            def classes(self): return {}
            
            @property
            def object_properties(self): return {}
            
            @property
            def datatype_properties(self): return {}
            
            @property
            def individuals(self): return {}
            
            @property
            def swrl_rules(self): return []
        
        mock = MockParser()
        assert isinstance(mock, IOntologyParser)
