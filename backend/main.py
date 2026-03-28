"""
Main entry point for the Vehicle Power Diagnosis System.
Supports both server mode and CLI diagnosis mode.
"""

import os
import sys
import asyncio
import argparse
import io
from pathlib import Path
from loguru import logger

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from server import app, initialize_app
from models import AgentID, DTCSeverity
from agents import AgentFactory
from agents.orchestrator import OrchestratorAgent
from agents.symptom_parser import SymptomParserAgent
from agents.ontology_fetcher import OntologyFetcherAgent
from agents.rule_engine import RuleEngineAgent
from agents.confidence_calc import ConfidenceCalcAgent
from agents.output_adapter import OutputAdapterAgent
from agents.llm_diagnosis_agent import LLMDiagnosisAgent
from agents.dtc_agent import DTCAgent
from agents.signal_recommender import SignalRecommenderAgent
from ontology.parser import OntologyParser

# Import centralized configuration
from config import get_settings, setup_logging

# DTC imports
from dtc_parser import get_dtc_parser
from diagnosis_knowledge import (
    DTC_KNOWLEDGE_BASE,
    DTC_OUTPUT_TEMPLATES,
    DTC_HYPOTHESIS_TEMPLATES,
)
from scenario_detector import detect_scenario_from_dtc


# =============================================================================
# Diagnosis Pipeline
# =============================================================================

class DiagnosisPipeline:
    """Main diagnosis pipeline that coordinates all agents."""
    
    def __init__(self, ontology_parser: OntologyParser, use_llm: bool = True):
        self.ontology_parser = ontology_parser
        self.use_llm = use_llm
        
        # Create orchestrator with LLM mode setting
        self.orchestrator = OrchestratorAgent(AgentID.ORCH, use_llm=use_llm)
        
        # Create all agents
        self.agents = {
            AgentID.ORCH: self.orchestrator,
            AgentID.DTC: DTCAgent(AgentID.DTC),
            AgentID.SYM: SymptomParserAgent(AgentID.SYM),
            AgentID.ONT: OntologyFetcherAgent(AgentID.ONT),
            AgentID.RULE: RuleEngineAgent(AgentID.RULE),
            AgentID.SIG: SignalRecommenderAgent(AgentID.SIG),
            AgentID.CONF: ConfidenceCalcAgent(AgentID.CONF),
            AgentID.OUT: OutputAdapterAgent(AgentID.OUT)
        }
        
        # Add LLM agent if enabled
        if use_llm:
            self.agents[AgentID.LLM] = LLMDiagnosisAgent(AgentID.LLM)
            # Set ontology parser for LLM agent
            self.agents[AgentID.LLM].set_ontology_parser(ontology_parser)
            logger.info("LLM Diagnosis Agent enabled")
        
        # Set ontology parser for OntologyFetcher
        self.agents[AgentID.ONT].set_ontology_parser(ontology_parser)
        
        # Register all agents with orchestrator
        for agent in self.agents.values():
            if agent.agent_id != AgentID.ORCH:
                self.orchestrator.register_agent(agent)
        
        mode_str = "LLM智能诊断模式" if use_llm else "传统规则诊断模式"
        logger.info(f"DiagnosisPipeline initialized ({mode_str}) with agents:")
        for agent_id in self.agents:
            logger.info(f"  - {agent_id.value}")
    
    async def run(self, context, send_message):
        """Run the diagnosis pipeline."""
        # Set message sender for all agents
        for agent in self.agents.values():
            agent.set_sender(send_message)
        
        # Run through orchestrator
        result = await self.orchestrator.run(context)
        
        return result


# =============================================================================
# Application Startup
# =============================================================================

# Note: setup_logging is imported from config.py


def get_ontology_path() -> str:
    """Get the path to the ontology file or folder."""
    settings = get_settings()
    
    # Prefer folder path
    folder = settings.get_ontology_folder()
    if folder.exists():
        logger.info(f"Using ontology folder: {folder}")
        return str(folder)
    
    # Fall back to single file path
    single_file = settings.get_ontology_path()
    if single_file.exists():
        logger.info(f"Using ontology file: {single_file}")
        return str(single_file)
    
    # Return folder path as default (will show warning during loading)
    logger.warning(f"Ontology not found, using default folder path: {folder}")
    return str(folder)


# =============================================================================
# CLI Mode - DTC Diagnosis
# =============================================================================

def run_dtc_diagnosis(args):
    """Run DTC diagnosis from command line."""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    parser = get_dtc_parser()
    
    # Parse DTC codes
    dtc_codes = [c.strip().upper() for c in args.dtc.split(',')] if args.dtc else []
    
    if args.list:
        # List all supported DTCs
        console.rule("[bold blue]支持的DTC代码[/bold blue]")
        category = args.category
        
        by_category = {}
        for code, info in DTC_KNOWLEDGE_BASE.items():
            cat = info["category"]
            if category and cat != category:
                continue
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append((code, info))
        
        for cat in ["network", "powertrain", "chassis", "body"]:
            if cat not in by_category:
                continue
            
            table = Table(title=f"{cat.upper()} Codes ({len(by_category[cat])}个)")
            table.add_column("Code", style="cyan", width=8)
            table.add_column("Description", style="white")
            table.add_column("Severity", style="yellow", width=10)
            
            for code, info in sorted(by_category[cat]):
                table.add_row(code, info["description_zh"], info["severity"])
            
            console.print(table)
            console.print()
        return
    
    if not dtc_codes:
        console.print("[red]Error: No DTC codes provided. Use --dtc or --list[/red]")
        return
    
    # Validate DTC codes
    valid_codes = []
    for code in dtc_codes:
        if parser.is_valid_dtc(code):
            valid_codes.append(code)
        else:
            console.print(f"[yellow]Warning: Invalid DTC code '{code}' skipped[/yellow]")
    
    if not valid_codes:
        console.print("[red]Error: No valid DTC codes[/red]")
        return
    
    role = args.role or "owner"
    
    # Parse and display
    console.rule("[bold blue]DTC故障码解析[/bold blue]")
    parsed = parser.parse_multiple(valid_codes)
    
    # Summary table
    table = Table(title=f"检测到 {len(parsed)} 个故障码")
    table.add_column("Code", style="cyan", width=8)
    table.add_column("Category", style="green", width=12)
    table.add_column("Severity", style="yellow", width=10)
    table.add_column("Description", style="white")
    
    for dtc in parsed:
        severity_style = {
            DTCSeverity.CRITICAL: "bold red",
            DTCSeverity.HIGH: "bold yellow",
            DTCSeverity.MEDIUM: "yellow",
            DTCSeverity.LOW: "dim",
        }.get(dtc.severity, "white")
        
        table.add_row(
            dtc.code,
            dtc.category.value.upper(),
            f"[{severity_style}]{dtc.severity.value}[/{severity_style}]",
            dtc.description_zh[:40] + ("..." if len(dtc.description_zh) > 40 else "")
        )
    
    console.print(table)
    
    # Severity summary
    severity_counts = {}
    for dtc in parsed:
        severity_counts[dtc.severity] = severity_counts.get(dtc.severity, 0) + 1
    
    max_severity = parser.get_max_severity(valid_codes)
    is_critical = max_severity == DTCSeverity.CRITICAL
    
    console.print()
    severity_text = " | ".join([f"{s.value}: {c}" for s, c in severity_counts.items()])
    console.print(f"[bold]严重度分布:[/bold] {severity_text}")
    
    if is_critical:
        console.print("[bold red]⚠️ 检测到严重故障码，需要立即检修！[/bold red]")
    
    # Related scenarios
    scenarios = detect_scenario_from_dtc(valid_codes)
    if scenarios:
        console.print(f"[bold]相关场景:[/bold] {', '.join(scenarios)}")
    
    # Related ECUs
    ecus = parser.get_related_ecus(valid_codes)
    if ecus:
        console.print(f"[bold]相关ECU:[/bold] {', '.join(ecus[:5])}")
    
    # Related signals
    signals = parser.get_related_signals(valid_codes)
    if signals:
        console.print(f"[bold]相关信号:[/bold] {', '.join(signals[:5])}")
    
    # Show details if requested
    if args.detail and len(valid_codes) == 1:
        console.print()
        console.rule(f"[bold blue]{valid_codes[0]} 详细信息[/bold blue]")
        dtc_info = parser.parse(valid_codes[0])
        
        if dtc_info:
            console.print(f"[bold]Code:[/bold] {dtc_info.code}")
            console.print(f"[bold]Category:[/bold] {dtc_info.category.value.upper()}")
            console.print(f"[bold]Severity:[/bold] {dtc_info.severity.value}")
            console.print(f"[bold]Description:[/bold] {dtc_info.description}")
            console.print(f"[bold]Description (ZH):[/bold] {dtc_info.description_zh}")
            
            if dtc_info.related_ecu:
                console.print(f"\n[bold]Related ECUs:[/bold]")
                for ecu in dtc_info.related_ecu:
                    console.print(f"  • {ecu}")
            
            if dtc_info.related_signals:
                console.print(f"\n[bold]Related Signals:[/bold]")
                for signal in dtc_info.related_signals:
                    console.print(f"  • {signal}")
            
            if dtc_info.possible_causes:
                console.print(f"\n[bold]Possible Causes:[/bold]")
                for i, cause in enumerate(dtc_info.possible_causes, 1):
                    console.print(f"  {i}. {cause}")
            
            if dtc_info.hypothesis:
                console.print(f"\n[bold]Hypotheses:[/bold]")
                for hypo in dtc_info.hypothesis:
                    pct_style = "green" if hypo.pct > 50 else ("yellow" if hypo.pct > 20 else "dim")
                    console.print(f"  • [{pct_style}]{hypo.name}[/{pct_style}] ({hypo.pct}%)")
        else:
            console.print(f"[yellow]No detailed information available for {valid_codes[0]}[/yellow]")
    
    # Show output if requested
    if args.output or (len(valid_codes) == 1 and not args.detail):
        console.print()
        console.rule(f"[bold blue]诊断输出 ({role})[/bold blue]")
        
        primary_dtc = valid_codes[0].upper()
        
        if primary_dtc in DTC_OUTPUT_TEMPLATES:
            output = DTC_OUTPUT_TEMPLATES[primary_dtc].get(role)
            if output:
                console.print(output)
        else:
            # Generate default output
            dtc_info = parser.parse(primary_dtc)
            if dtc_info:
                code = dtc_info.code
                desc_zh = dtc_info.description_zh
                severity = dtc_info.severity.value
                
                if role == "owner":
                    console.print(f"""### ⚠️ 检测到故障码 {code}

{desc_zh}（严重度：{severity}）

**建议操作:**
1. 如故障灯持续亮起，请尽快到店检测
2. 如有其他异常症状，请联系：400-XXX-XXXX""")
                elif role == "technician":
                    ecu_list = ", ".join(dtc_info.related_ecu[:3]) if dtc_info.related_ecu else "N/A"
                    console.print(f"""### 【诊断结论】{code} - {desc_zh}

**DTC:** {code} | **Category:** {dtc_info.category.value} | **ECU:** {ecu_list}

**Steps:**
1. OBD读取DTC快照和冻结帧数据
2. 检查相关ECU供电和接地
3. 检查CAN通信链路""")
                else:
                    console.print(f"### 【系统诊断】检测到故障码 {code}\n\n您好，车辆检测到故障码 {code}，建议到店进行专业检测。")


# =============================================================================
# Server Mode
# =============================================================================

async def start_server():
    """Start the FastAPI + WebSocket server."""
    # Use centralized configuration
    settings = get_settings()
    setup_logging(settings)
    
    logger.info("=" * 60)
    logger.info(f"Vehicle Power Diagnosis System v{settings.app_version}")
    logger.info("=" * 60)
    
    # Load ontology from folder (or single file if configured)
    ontology_folder = settings.get_ontology_folder()
    logger.info(f"Loading ontology from folder: {ontology_folder}")
    
    parser = OntologyParser(str(ontology_folder))
    if parser.load():
        logger.info(f"Ontology loaded successfully!")
        logger.info(f"  Loaded files: {len(parser.loaded_files)}")
        logger.info(f"  Total classes: {len(parser.classes)}")
        logger.info(f"  Object Properties: {len(parser.object_properties)}")
        logger.info(f"  Datatype Properties: {len(parser.datatype_properties)}")
        logger.info(f"  Individuals: {len(parser.individuals)}")
    else:
        logger.warning("Failed to load ontology, using fallback mode")
    
    # Create pipeline using centralized config
    pipeline = DiagnosisPipeline(parser, use_llm=settings.use_llm_mode)
    
    # Initialize app
    initialize_app(pipeline, parser)
    
    # Import uvicorn for running server
    import uvicorn
    
    logger.info("Starting server on ws://localhost:8765")
    logger.info("Open the frontend at: http://localhost:8000")
    logger.info("WebSocket endpoint: ws://localhost:8765/ws")
    logger.info("=" * 60)
    
    # Run server using centralized config
    config = uvicorn.Config(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
        reload=settings.server_reload
    )
    server = uvicorn.Server(config)
    await server.serve()


# =============================================================================
# Main Entry Point
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Vehicle Power Diagnosis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server (default)
  python main.py

  # DTC diagnosis from command line
  python main.py --dtc U0100
  python main.py --dtc U0100,P0562 --role technician
  python main.py --dtc U0100 --detail --output

  # List supported DTC codes
  python main.py --list
  python main.py --list --category network

Note: Server mode and CLI mode are mutually exclusive.
      Use --dtc or --list for CLI mode, otherwise starts server.
        """
    )
    
    # Server options (parsed when not in CLI mode)
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Server host (default from config)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (default: 8765)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM mode, use rule-based diagnosis"
    )
    
    # CLI options (DTC diagnosis)
    parser.add_argument(
        "--dtc", "-d",
        type=str,
        help="DTC codes (comma-separated): U0100,P0562"
    )
    parser.add_argument(
        "--role", "-r",
        type=str,
        choices=["owner", "technician", "customer_service"],
        help="User role for output"
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show DTC details"
    )
    parser.add_argument(
        "--output", "-o",
        action="store_true",
        help="Show diagnosis output"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all supported DTC codes"
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        choices=["network", "powertrain", "chassis", "body"],
        help="Filter DTC category (for --list)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Check if CLI mode (DTC diagnosis)
    if args.dtc or args.list:
        # CLI mode - run DTC diagnosis
        run_dtc_diagnosis(args)
    else:
        # Server mode - start the server
        try:
            asyncio.run(start_server())
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
