#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DTC Diagnosis CLI - Command-line interface for DTC-based vehicle diagnosis.

Usage:
    python dtc_cli.py --dtc U0100,P0562
    python dtc_cli.py --dtc U0100 --symptom "无法上电"
    python dtc_cli.py --dtc U0100,P0562,B2799 --role technician
    python dtc_cli.py --interactive
"""

import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import argparse
import json
from pathlib import Path
from typing import Optional, List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint

from models import DiagnosisContext, Role, DTCSeverity
from dtc_parser import get_dtc_parser, DTCParser
from diagnosis_knowledge import (
    DTC_KNOWLEDGE_BASE,
    DTC_OUTPUT_TEMPLATES,
    DTC_HYPOTHESIS_TEMPLATES,
)
from scenario_detector import detect_scenario_from_dtc


console = Console()


class DTCDiagnosisCLI:
    """CLI for DTC-based diagnosis."""
    
    def __init__(self):
        self.parser = get_dtc_parser()
    
    def parse_dtcs(self, dtc_codes: List[str]) -> None:
        """Parse and display DTC codes."""
        console.rule("[bold blue]DTC故障码解析[/bold blue]")
        
        parsed = self.parser.parse_multiple(dtc_codes)
        
        if not parsed:
            console.print("[red]无效的DTC代码[/red]")
            return
        
        # Summary table
        table = Table(title=f"检测到 {len(parsed)} 个故障码")
        table.add_column("代码", style="cyan", width=8)
        table.add_column("类别", style="green", width=12)
        table.add_column("严重度", style="yellow", width=10)
        table.add_column("描述", style="white")
        
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
        
        max_severity = self.parser.get_max_severity(dtc_codes)
        is_critical = max_severity == DTCSeverity.CRITICAL
        
        console.print()
        severity_text = " | ".join([
            f"{s.value}: {c}" for s, c in severity_counts.items()
        ])
        console.print(f"[bold]严重度分布:[/bold] {severity_text}")
        
        if is_critical:
            console.print("[bold red]⚠️ 检测到严重故障码，需要立即检修！[/bold red]")
        
        # Related scenarios
        scenarios = detect_scenario_from_dtc(dtc_codes)
        if scenarios:
            console.print(f"[bold]相关场景:[/bold] {', '.join(scenarios)}")
        
        # Related ECUs
        ecus = self.parser.get_related_ecus(dtc_codes)
        if ecus:
            console.print(f"[bold]相关ECU:[/bold] {', '.join(ecus[:5])}")
        
        # Related signals
        signals = self.parser.get_related_signals(dtc_codes)
        if signals:
            console.print(f"[bold]相关信号:[/bold] {', '.join(signals[:5])}")
    
    def show_dtc_details(self, dtc_code: str) -> None:
        """Show detailed information for a single DTC."""
        dtc_info = self.parser.parse(dtc_code)
        
        if not dtc_info:
            console.print(f"[red]无效的DTC代码: {dtc_code}[/red]")
            return
        
        console.rule(f"[bold blue]{dtc_info.code} 详细信息[/bold blue]")
        
        # Basic info
        console.print(f"\n[bold]代码:[/bold] {dtc_info.code}")
        console.print(f"[bold]类别:[/bold] {dtc_info.category.value.upper()}")
        console.print(f"[bold]严重度:[/bold] {dtc_info.severity.value}")
        console.print(f"[bold]描述:[/bold] {dtc_info.description}")
        console.print(f"[bold]中文描述:[/bold] {dtc_info.description_zh}")
        
        # Related components
        if dtc_info.related_ecu:
            console.print(f"\n[bold]相关ECU:[/bold]")
            for ecu in dtc_info.related_ecu:
                console.print(f"  • {ecu}")
        
        if dtc_info.related_signals:
            console.print(f"\n[bold]相关信号:[/bold]")
            for signal in dtc_info.related_signals:
                console.print(f"  • {signal}")
        
        # Possible causes
        if dtc_info.possible_causes:
            console.print(f"\n[bold]可能原因:[/bold]")
            for i, cause in enumerate(dtc_info.possible_causes, 1):
                console.print(f"  {i}. {cause}")
        
        # Hypotheses
        if dtc_info.hypothesis:
            console.print(f"\n[bold]故障假设:[/bold]")
            for hypo in dtc_info.hypothesis:
                pct_style = "green" if hypo.pct > 50 else ("yellow" if hypo.pct > 20 else "dim")
                console.print(f"  • [{pct_style}]{hypo.name}[/{pct_style}] ({hypo.pct}%)")
    
    def show_output(self, dtc_codes: List[str], role: str = "owner") -> None:
        """Show role-adapted output for DTC codes."""
        if not dtc_codes:
            return
        
        primary_dtc = dtc_codes[0].upper()
        
        console.rule(f"[bold blue]诊断输出 ({role})[/bold blue]")
        
        if primary_dtc in DTC_OUTPUT_TEMPLATES:
            output = DTC_OUTPUT_TEMPLATES[primary_dtc].get(role)
            if output:
                # Print directly without Markdown/Panel to avoid rendering issues
                console.print(output)
                return
        
        # Generate default output
        dtc_info = self.parser.parse(primary_dtc)
        if dtc_info:
            output = self._generate_default_output(dtc_info, role)
            console.print(output)
    
    def _generate_default_output(self, dtc_info, role: str) -> str:
        """Generate default output for DTC without template."""
        code = dtc_info.code
        desc_zh = dtc_info.description_zh
        severity = dtc_info.severity.value
        
        if role == "owner":
            return f"""### ⚠️ 检测到故障码 {code}

{desc_zh}（严重度：{severity}）

**建议操作:**
1. 如故障灯持续亮起，请尽快到店检测
2. 如有其他异常症状，请联系：400-XXX-XXXX"""
        
        elif role == "technician":
            ecu_list = ", ".join(dtc_info.related_ecu[:3]) if dtc_info.related_ecu else "N/A"
            return f"""### 【诊断结论】{code} - {desc_zh}

**DTC:** {code} | **Category:** {dtc_info.category.value} | **Related ECU:** {ecu_list}

**诊断步骤:**
1. OBD读取DTC快照和冻结帧数据
2. 检查相关ECU供电和接地
3. 检查CAN通信链路"""
        
        else:
            return f"""### 【系统诊断】检测到故障码 {code}

"您好，车辆检测到故障码 {code}，建议到店进行专业检测。\""""
    
    def list_supported_dtcs(self, category: Optional[str] = None) -> None:
        """List all supported DTC codes."""
        console.rule("[bold blue]支持的DTC代码[/bold blue]")
        
        # Group by category
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
            table.add_column("代码", style="cyan", width=8)
            table.add_column("描述", style="white")
            table.add_column("严重度", style="yellow", width=10)
            
            for code, info in sorted(by_category[cat]):
                table.add_row(
                    code,
                    info["description_zh"][:50],
                    info["severity"]
                )
            
            console.print(table)
            console.print()
    
    def run_interactive(self) -> None:
        """Run interactive mode."""
        console.print(Panel.fit(
            "[bold blue]DTC故障诊断系统[/bold blue]\n"
            "输入DTC代码进行诊断，输入 'quit' 退出",
            border_style="blue"
        ))
        
        while True:
            console.print()
            dtc_input = console.input("[green bold]请输入DTC代码[/green bold] (多个用逗号分隔): ").strip()
            
            if dtc_input.lower() in ['quit', 'exit', 'q']:
                console.print("[yellow]再见！[/yellow]")
                break
            
            if not dtc_input:
                continue
            
            # Parse DTC codes
            dtc_codes = [c.strip().upper() for c in dtc_input.split(',') if c.strip()]
            valid_codes = [c for c in dtc_codes if self.parser.is_valid_dtc(c)]
            
            if not valid_codes:
                console.print("[red]无效的DTC代码格式。示例: U0100, P0562[/red]")
                continue
            
            # Select role
            console.print("\n[bold]选择角色:[/bold]")
            console.print("  1. owner (车主)")
            console.print("  2. technician (技师)")
            console.print("  3. customer_service (客服)")
            
            role_choice = console.input("[green bold]请选择 (1-3, 默认1):[/green bold] ").strip()
            role_map = {"1": "owner", "2": "technician", "3": "customer_service", "": "owner"}
            role = role_map.get(role_choice, "owner")
            
            # Show diagnosis
            console.print()
            self.parse_dtcs(valid_codes)
            
            # Ask for details
            if len(valid_codes) == 1:
                show_detail = console.input("\n[bold]显示详细信息? (y/n):[/bold] ").strip().lower()
                if show_detail == 'y':
                    console.print()
                    self.show_dtc_details(valid_codes[0])
            
            # Show output
            show_output = console.input("\n[bold]显示诊断输出? (y/n):[/bold] ").strip().lower()
            if show_output == 'y':
                console.print()
                self.show_output(valid_codes, role)


def main():
    parser = argparse.ArgumentParser(
        description="DTC故障诊断命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 解析单个DTC
  python dtc_cli.py --dtc U0100

  # 解析多个DTC
  python dtc_cli.py --dtc U0100,P0562,B2799

  # 指定角色输出
  python dtc_cli.py --dtc U0100 --role technician

  # 显示DTC详情
  python dtc_cli.py --dtc U0100 --detail

  # 列出所有支持的DTC
  python dtc_cli.py --list

  # 交互模式
  python dtc_cli.py --interactive
        """
    )
    
    parser.add_argument(
        "--dtc", "-d",
        type=str,
        help="DTC代码，多个用逗号分隔 (如: U0100,P0562)"
    )
    
    parser.add_argument(
        "--symptom", "-s",
        type=str,
        help="症状描述"
    )
    
    parser.add_argument(
        "--role", "-r",
        type=str,
        choices=["owner", "technician", "customer_service"],
        default="owner",
        help="用户角色 (默认: owner)"
    )
    
    parser.add_argument(
        "--detail",
        action="store_true",
        help="显示DTC详细信息"
    )
    
    parser.add_argument(
        "--output", "-o",
        action="store_true",
        help="显示角色适配输出"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有支持的DTC代码"
    )
    
    parser.add_argument(
        "--category", "-c",
        type=str,
        choices=["network", "powertrain", "chassis", "body"],
        help="筛选DTC类别 (配合 --list 使用)"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互模式"
    )
    
    args = parser.parse_args()
    
    cli = DTCDiagnosisCLI()
    
    # Interactive mode
    if args.interactive:
        cli.run_interactive()
        return
    
    # List mode
    if args.list:
        cli.list_supported_dtcs(args.category)
        return
    
    # DTC mode
    if args.dtc:
        dtc_codes = [c.strip().upper() for c in args.dtc.split(',') if c.strip()]
        
        # Validate
        valid_codes = []
        for code in dtc_codes:
            if cli.parser.is_valid_dtc(code):
                valid_codes.append(code)
            else:
                console.print(f"[yellow]警告: 无效的DTC代码 '{code}'，已跳过[/yellow]")
        
        if not valid_codes:
            console.print("[red]错误: 没有有效的DTC代码[/red]")
            sys.exit(1)
        
        # Parse and display
        cli.parse_dtcs(valid_codes)
        
        # Show details
        if args.detail and len(valid_codes) == 1:
            console.print()
            cli.show_dtc_details(valid_codes[0])
        
        # Show output
        if args.output:
            console.print()
            cli.show_output(valid_codes, args.role)
        
        # If only one DTC, show output by default
        if len(valid_codes) == 1 and not args.output and not args.detail:
            show_output = console.input("\n[bold]显示诊断输出? (y/n, 默认y):[/bold] ").strip().lower()
            if show_output in ['', 'y']:
                console.print()
                cli.show_output(valid_codes, args.role)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
