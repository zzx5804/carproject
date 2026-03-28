#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vehicle Intelligent Diagnosis CLI.

A command-line tool for vehicle fault diagnosis using:
- OWL Ontology (vehicle_power_mode_ontology.ttl)
- LLM-powered intelligent analysis
- Natural language symptom input
- DTC (Diagnostic Trouble Code) support

Usage:
    python -m cli.main "踩刹车按启动按钮，车辆无法上电"
    python -m cli.main --dtc U0100
    python -m cli.main --dtc U0100,P0562 --role service
    python -m cli.main --interactive
    python -m cli.main --help
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import Optional, List

# Fix Windows encoding issue
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore

# Check for rich library for progress bar
try:
    from rich.console import Console
    from rich.spinner import Spinner
    from rich.live import Live

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from cli.diagnosis_service import DiagnosisService
from cli.output_formatter import OutputFormatter

# Import DTC modules
from dtc_parser import get_dtc_parser
from diagnosis_knowledge import (
    DTC_KNOWLEDGE_BASE,
    DTC_OUTPUT_TEMPLATES,
)
from scenario_detector import detect_scenario_from_dtc
from models import DTCSeverity


# Configure logging
def setup_logging(verbose: bool = False, log_level: Optional[str] = None):
    """Configure loguru logging.

    Args:
        verbose: Enable DEBUG level (overridden by log_level if provided)
        log_level: Explicit log level (TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL)
    """
    logger.remove()

    # Determine log level: explicit level > verbose flag > default INFO
    if log_level:
        level = log_level.upper()
        # Validate
        valid_levels = [
            "TRACE",
            "DEBUG",
            "INFO",
            "SUCCESS",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]
        if level not in valid_levels:
            print(f"警告: 无效的日志级别 '{log_level}'，使用 INFO")
            level = "INFO"
    elif verbose:
        level = "DEBUG"
    else:
        level = "INFO"

    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        colorize=True,
    )


def get_default_ontology_path() -> str:
    """Get default ontology path (folder or file)."""
    # Prefer folder path
    project_root = Path(__file__).parent.parent.parent
    ontology_folder = project_root / "ontology files"

    if ontology_folder.exists() and ontology_folder.is_dir():
        return str(ontology_folder)

    # Fallback: try single file locations
    candidates = [
        project_root / "vehicle_power_mode_ontology.ttl",
        project_root.parent / "vehicle_power_mode_ontology.ttl",
        Path.cwd() / "vehicle_power_mode_ontology.ttl",
    ]

    for path in candidates:
        if path.exists():
            return str(path)

    # Return folder path as default (parser will show warning if not found)
    return str(ontology_folder)


async def run_diagnosis(
    symptom: str,
    ontology_path: str,
    role: str = "owner",
    model: Optional[str] = None,
    verbose: bool = False,
    load_ontology: bool = True,
    log_level: Optional[str] = None,
) -> None:
    """
    Run diagnosis for a given symptom.

    Args:
        symptom: User's symptom description
        ontology_path: Path to ontology TTL file
        role: User role (owner/technician/customer_service)
        model: LLM model to use (optional)
        verbose: Enable verbose output
        load_ontology: Whether to load ontology file (default: True)
        log_level: Explicit log level (optional)
    """
    setup_logging(verbose, log_level)

    print("\n" + "=" * 60)
    print("        车辆智能诊断系统 CLI v1.0")
    print("=" * 60)
    print(f"\n故障描述: {symptom}")
    print(f"用户角色: {role}")
    print("-" * 60)

    # Initialize service (ontology loaded in __init__)
    print("\n[1/3] 加载本体知识库...")
    service = DiagnosisService(
        ontology_path=ontology_path, model=model, load_ontology=load_ontology
    )

    if load_ontology and service.ontology_parser is None:
        print("错误: 无法加载本体文件，请检查路径")
        sys.exit(1)

    if load_ontology:
        print(f"      已加载 {service.get_ontology_stats()}")
    else:
        print("      已跳过本体加载（--no-ontology）")

    # Connect to LLM
    print("\n[2/3] 连接LLM服务...")
    llm_info = service.get_llm_info()
    provider = llm_info.get("provider", "unknown")
    provider_display = {
        "openrouter": "OpenRouter",
        "litellm": "本地LLM网关",
    }.get(provider, provider)
    print(f"      Provider: {provider_display}")
    print(f"      端点: {llm_info['endpoint']}")
    print(f"      模型: {llm_info['model']}")

    # Run diagnosis
    print("\n[3/3] 执行智能诊断...")
    print("-" * 60)

    try:
        if RICH_AVAILABLE:
            # Use rich progress bar
            from rich.console import Console as _Console

            console = _Console()

            with console.status(
                "[bold cyan]正在调用LLM进行智能诊断...", spinner="dots"
            ) as status:
                result = service.diagnose(symptom)

                # Update status with progress
                status.update("[bold green]正在解析诊断结果...")
        else:
            # Fallback without rich
            print("正在诊断", end="", flush=True)
            result = service.diagnose(symptom)
            print(" ✓")

        # Format and print output
        formatter = OutputFormatter()
        output = formatter.format(result, role=role)
        print(output)

    except Exception as e:
        logger.error(f"诊断失败: {e}")
        print(f"\n诊断服务异常: {e}")
        print("请检查LLM连接配置和网络状态")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60 + "\n")


async def interactive_mode(
    ontology_path: str,
    verbose: bool = False,
    load_ontology: bool = True,
    log_level: Optional[str] = None,
):
    """
    Interactive diagnosis mode.

    Continuously prompt for symptoms and diagnose.

    Args:
        ontology_path: Path to ontology TTL file
        verbose: Enable verbose output
        load_ontology: Whether to load ontology file (default: True)
        log_level: Explicit log level (optional)
    """
    setup_logging(verbose, log_level)

    print("\n" + "=" * 60)
    print("        车辆智能诊断系统 CLI v1.0")
    print("            交互式诊断模式")
    print("=" * 60)

    # Initialize service (ontology loaded in __init__)
    print("\n正在加载本体知识库...")
    service = DiagnosisService(ontology_path=ontology_path, load_ontology=load_ontology)

    if load_ontology and service.ontology_parser is None:
        print("错误: 无法加载本体文件")
        sys.exit(1)

    if load_ontology:
        print(f"已加载 {service.get_ontology_stats()}")
    else:
        print("已跳过本体加载（--no-ontology）")

    print("\n输入 'quit' 或 'exit' 退出程序")
    print("输入 'help' 查看帮助信息")
    print("-" * 60)

    role = "owner"
    formatter = OutputFormatter()

    while True:
        try:
            print(f"\n当前角色: {role} (输入 'role <角色>' 切换角色)")
            symptom = input("\n请输入故障描述> ").strip()

            if not symptom:
                continue

            if symptom.lower() in ["quit", "exit", "q"]:
                print("\n感谢使用，再见！")
                break

            if symptom.lower() == "help":
                print("""
可用命令:
  <故障描述>     - 输入故障描述进行诊断
  role owner    - 切换到车主角色
  role tech     - 切换到技师角色
  role service  - 切换到客服角色
  help          - 显示帮助信息
  quit/exit     - 退出程序

示例故障描述:
  - 踩刹车按启动按钮，车辆无法上电
  - 车门打开后车辆没有自动上电
  - 手机蓝牙钥匙无法解锁车辆
  - 车辆自动下电时间异常
""")
                continue

            if symptom.lower().startswith("role "):
                role_map = {
                    "owner": "owner",
                    "tech": "technician",
                    "technician": "technician",
                    "service": "customer_service",
                }
                new_role = symptom[5:].strip().lower()
                if new_role in role_map:
                    role = role_map[new_role]
                    print(f"已切换到角色: {role}")
                else:
                    print(f"未知角色: {new_role}，可选: owner, tech, service")
                continue

            # Run diagnosis
            print("\n正在诊断...")
            try:
                result = service.diagnose(symptom)
                output = formatter.format(result, role=role)
                print(output)
            except Exception as e:
                logger.error(f"诊断失败: {e}")
                print(f"\n诊断失败: {e}")

            print("\n" + "-" * 60)

        except KeyboardInterrupt:
            print("\n\n已中断，再见！")
            break
        except EOFError:
            break


def select_role() -> str:
    """交互式选择用户角色"""
    print("\n请选择您的角色:")
    print("  1. 车主 (owner)      - 通俗易懂的语言，提供简单操作建议")
    print("  2. 技师 (technician) - 专业术语，详细的诊断和分析")
    print("  3. 客服 (customer_service) - 友好专业，清晰指导")

    while True:
        choice = input("\n请输入选项 (1/2/3) 或角色名称: ").strip().lower()

        if choice in ["1", "owner"]:
            return "owner"
        elif choice in ["2", "tech", "technician"]:
            return "technician"
        elif choice in ["3", "service", "customer_service"]:
            return "customer_service"
        elif choice:
            print("无效选择，请输入 1、2 或 3")


# =============================================================================
# DTC Diagnosis Functions
# =============================================================================


def run_dtc_diagnosis(
    dtc_codes: List[str],
    role: str = "owner",
    verbose: bool = False,
    log_level: Optional[str] = None,
):
    """Run DTC-based diagnosis.

    Args:
        dtc_codes: List of DTC codes
        role: User role
        verbose: Enable verbose output
        log_level: Explicit log level (optional)
    """
    setup_logging(verbose, log_level)

    parser = get_dtc_parser()

    print("\n" + "=" * 60)
    print("        DTC故障码诊断")
    print("=" * 60)
    print(f"\nDTC Codes: {', '.join(dtc_codes)}")
    print(f"User Role: {role}")
    print("-" * 60)

    # Parse DTC codes
    parsed = parser.parse_multiple(dtc_codes)

    if not parsed:
        print("\n错误: 无有效的DTC代码")
        return

    print(f"\n检测到 {len(parsed)} 个故障码:\n")

    # Display each DTC
    for dtc in parsed:
        severity_icon = {
            DTCSeverity.CRITICAL: "🔴",
            DTCSeverity.HIGH: "🟠",
            DTCSeverity.MEDIUM: "🟡",
            DTCSeverity.LOW: "🟢",
        }.get(dtc.severity, "⚪")

        print(
            f"  {severity_icon} {dtc.code} | {dtc.category.value.upper():12} | {dtc.severity.value:8} | {dtc.description_zh}"
        )

    # Severity summary
    severity_counts = {}
    for dtc in parsed:
        severity_counts[dtc.severity] = severity_counts.get(dtc.severity, 0) + 1

    print("\n" + "-" * 60)
    print(
        "严重度分布:",
        " | ".join([f"{s.value}: {c}" for s, c in severity_counts.items()]),
    )

    max_severity = parser.get_max_severity(dtc_codes)
    if max_severity == DTCSeverity.CRITICAL:
        print("⚠️  检测到严重故障码，需要立即检修！")

    # Related scenarios
    scenarios = detect_scenario_from_dtc(dtc_codes)
    if scenarios:
        print(f"\n相关场景: {', '.join(scenarios)}")

    # Related ECUs
    ecus = parser.get_related_ecus(dtc_codes)
    if ecus:
        print(f"相关ECU: {', '.join(ecus[:5])}")

    # Related signals
    signals = parser.get_related_signals(dtc_codes)
    if signals:
        print(f"相关信号: {', '.join(signals[:5])}")

    # Show diagnosis output
    print("\n" + "=" * 60)
    print(f"诊断输出 ({role})")
    print("=" * 60)

    primary_dtc = dtc_codes[0].upper()

    if primary_dtc in DTC_OUTPUT_TEMPLATES:
        output = DTC_OUTPUT_TEMPLATES[primary_dtc].get(role)
        if output:
            print(output)
    else:
        # Generate default output
        dtc_info = parser.parse(primary_dtc)
        if dtc_info:
            if role == "owner":
                print(f"""⚠️ 检测到故障码 {dtc_info.code}

{dtc_info.description_zh}（严重度：{dtc_info.severity.value}）

建议操作:
1. 如故障灯持续亮起，请尽快到店检测
2. 如有其他异常症状，请联系：400-XXX-XXXX""")
            elif role == "technician":
                ecu_list = (
                    ", ".join(dtc_info.related_ecu[:3])
                    if dtc_info.related_ecu
                    else "N/A"
                )
                print(f"""【诊断结论】{dtc_info.code} - {dtc_info.description_zh}

DTC: {dtc_info.code} | Category: {dtc_info.category.value} | ECU: {ecu_list}

诊断步骤:
1. OBD读取DTC快照和冻结帧数据
2. 检查相关ECU供电和接地
3. 检查CAN通信链路""")
            else:
                print(
                    f"【系统诊断】检测到故障码 {dtc_info.code}\n\n您好，车辆检测到故障码 {dtc_info.code}，建议到店进行专业检测。"
                )

    print("\n" + "=" * 60)


def list_supported_dtcs(
    category: Optional[str] = None,
    verbose: bool = False,
    log_level: Optional[str] = None,
):
    """List all supported DTC codes.

    Args:
        category: DTC category filter
        verbose: Enable verbose output
        log_level: Explicit log level (optional)
    """
    setup_logging(verbose, log_level)

    print("\n" + "=" * 60)
    print("        支持的DTC故障码列表")
    print("=" * 60)

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

        print(f"\n{cat.upper()} ({len(by_category[cat])}个)")
        print("-" * 50)

        for code, info in sorted(by_category[cat]):
            severity_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(info["severity"], "⚪")

            print(f"  {severity_icon} {code:6} | {info['description_zh'][:35]}")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="车辆智能诊断CLI - 基于本体和LLM的故障诊断工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单次诊断
  python -m cli.main "踩刹车按启动按钮，车辆无法上电"
  
  # 交互式模式
  python -m cli.main -i
  
  # 指定角色
  python -m cli.main "车辆无法上电" --role technician
  
  # 指定本体文件
  python -m cli.main "故障描述" --ontology /path/to/ontology.ttl
  
  # 详细输出
  python -m cli.main "故障描述" -v
""",
    )

    parser.add_argument("symptom", nargs="?", help="故障描述（自然语言）")

    parser.add_argument(
        "-i", "--interactive", action="store_true", help="启动交互式诊断模式"
    )

    parser.add_argument(
        "--role",
        choices=["owner", "technician", "tech", "customer_service", "service"],
        default=None,
        help="用户角色: owner(车主), technician/tech(技师), customer_service/service(客服)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM模型: GLM-5-FP8, MiniMax, MiniMax-M2.5, MiniMax-M2.1",
    )

    parser.add_argument(
        "--ontology", type=str, default=None, help="本体文件路径（默认: 自动检测）"
    )

    parser.add_argument(
        "--no-ontology",
        action="store_true",
        help="跳过本体加载（降低诊断准确性，适用于快速测试）",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="启用详细输出 (DEBUG级别)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="设置日志级别: TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL",
    )

    # DTC diagnosis arguments
    parser.add_argument(
        "--dtc", "-d", type=str, help="DTC故障码 (逗号分隔): U0100,P0562"
    )

    parser.add_argument(
        "--list-dtc", action="store_true", help="列出所有支持的DTC故障码"
    )

    parser.add_argument(
        "--dtc-category",
        type=str,
        choices=["network", "powertrain", "chassis", "body"],
        help="DTC类别筛选 (配合 --list-dtc 使用)",
    )

    parser.add_argument("--dtc-detail", action="store_true", help="显示DTC详细信息")

    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    args = parser.parse_args()

    # Handle --ontology and --no-ontology mutual exclusivity
    if args.no_ontology and args.ontology:
        print("警告: 同时指定了 --ontology 和 --no-ontology，将跳过本体加载")

    # Determine whether to load ontology
    load_ontology = not args.no_ontology

    # Get ontology path
    ontology_path = args.ontology or get_default_ontology_path()

    # Get role - if not specified, prompt user to select
    role = args.role
    # Map short role names to full names
    role_map = {
        "owner": "owner",
        "tech": "technician",
        "technician": "technician",
        "service": "customer_service",
        "customer_service": "customer_service",
    }
    if role in role_map:
        role = role_map[role]

    if role is None and args.symptom:
        role = select_role()

    # Get model
    model = args.model

    # DTC mode - prioritized over symptom-based diagnosis
    if args.list_dtc:
        list_supported_dtcs(args.dtc_category, args.verbose, args.log_level)
        return

    if args.dtc:
        # Parse DTC codes
        dtc_codes = [c.strip().upper() for c in args.dtc.split(",") if c.strip()]

        # Validate
        parser = get_dtc_parser()
        valid_codes = [c for c in dtc_codes if parser.is_valid_dtc(c)]

        if not valid_codes:
            print("\n错误: 没有有效的DTC代码")
            print("DTC格式: 字母+4位数字 (如 U0100, P0562)")
            sys.exit(1)

        if role is None:
            role = "owner"

        run_dtc_diagnosis(valid_codes, role, args.verbose, args.log_level)
        return

    # Symptom-based or interactive mode
    if args.interactive:
        asyncio.run(
            interactive_mode(ontology_path, args.verbose, load_ontology, args.log_level)
        )
    elif args.symptom:
        if role is None:
            role = "owner"  # default if still None
        asyncio.run(
            run_diagnosis(
                args.symptom,
                ontology_path,
                role,
                model,
                args.verbose,
                load_ontology,
                args.log_level,
            )
        )
    else:
        # No arguments - start interactive mode by default
        asyncio.run(
            interactive_mode(ontology_path, args.verbose, load_ontology, args.log_level)
        )


if __name__ == "__main__":
    main()
