"""
Quick test script to verify the backend components.
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from models import DiagnosisContext, Role, AgentID
from ontology.parser import OntologyParser
from agents.orchestrator import OrchestratorAgent
from agents.symptom_parser import SymptomParserAgent
from agents.ontology_fetcher import OntologyFetcherAgent
from agents.rule_engine import RuleEngineAgent
from agents.confidence_calc import ConfidenceCalcAgent
from agents.output_adapter import OutputAdapterAgent


async def test_components():
    """Test all components."""
    print("=" * 60)
    print("Testing Backend Components")
    print("=" * 60)
    
    # Test 1: Ontology Parser
    print("\n[1] Testing Ontology Parser...")
    ontology_path = Path(__file__).parent / "vehicle_power_ontology_GLM_Minimax_Merged.ttl"
    if not ontology_path.exists():
        # Try parent directory
        ontology_path = Path(__file__).parent.parent / "vehicle_power_ontology_GLM_Minimax_Merged.ttl"
    
    parser = OntologyParser(str(ontology_path))
    if parser.load():
        print(f"  ✓ Loaded {len(parser.classes)} classes")
        print(f"  ✓ Loaded {len(parser.datatype_properties)} datatype properties")
        print(f"  ✓ Power modes: {list(parser.get_power_mode_info().keys())}")
    else:
        print("  ✗ Failed to load ontology")
    
    # Test 2: Create Agents
    print("\n[2] Testing Agent Creation...")
    agents = {
        AgentID.ORCH: OrchestratorAgent(AgentID.ORCH),
        AgentID.SYM: SymptomParserAgent(AgentID.SYM),
        AgentID.ONT: OntologyFetcherAgent(AgentID.ONT),
        AgentID.RULE: RuleEngineAgent(AgentID.RULE),
        AgentID.CONF: ConfidenceCalcAgent(AgentID.CONF),
        AgentID.OUT: OutputAdapterAgent(AgentID.OUT)
    }
    
    for agent_id, agent in agents.items():
        print(f"  ✓ Created {agent_id.value} agent")
    
    # Set ontology parser
    agents[AgentID.ONT].set_ontology_parser(parser)
    
    # Test 3: Test Context Creation
    print("\n[3] Testing Context Creation...")
    context = DiagnosisContext(
        symptom="踩刹车按启动按钮，车辆无法上电",
        role=Role.OWNER,
        signals={
            "sv-pm": "0:Off (St1)",
            "sv-kv": "INVALID",
            "sv-ble": "1"
        }
    )
    print(f"  ✓ Created context with symptom: {context.symptom[:20]}...")
    print(f"  ✓ Role: {context.role.value}")
    print(f"  ✓ Signals: {len(context.signals)} keys")
    
    # Test 4: Test SymptomParser
    print("\n[4] Testing SymptomParser Agent...")
    sym_agent = agents[AgentID.SYM]
    message_log = []
    
    async def mock_sender(msg):
        message_log.append(msg)
        print(f"    → {msg.get('type', 'unknown')}: {str(msg)[:80]}...")
    
    sym_agent.set_sender(mock_sender)
    
    try:
        result = await sym_agent.run(context)
        print(f"  ✓ Parsed {len(result.reasoning_steps)} reasoning steps")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # Test 5: Test RuleEngine
    print("\n[5] Testing RuleEngine Agent...")
    rule_agent = agents[AgentID.RULE]
    rule_agent.set_sender(mock_sender)
    
    try:
        result = await rule_agent.run(context)
        print(f"  ✓ Matched {len(result.matched_rules)} rules")
        print(f"  ✓ Generated {len(result.hypotheses)} hypotheses")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print("\nTo start the server, run:")
    print("  cd backend")
    print("  pip install -r requirements.txt")
    print("  python main.py")
    print("\nThen open http://localhost:8765 in browser")


if __name__ == "__main__":
    asyncio.run(test_components())
