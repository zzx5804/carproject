"""
Output Formatter for CLI.

Formats diagnosis results as clean, readable text output.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Import DiagnosisResult from diagnosis_service to avoid duplication
from cli.diagnosis_service import DiagnosisResult


class OutputFormatter:
    """
    Format diagnosis results as plain text.
    
    Provides clear, structured output suitable for terminal display.
    """
    
    # Color codes for terminal output
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "dim": "\033[90m",
    }
    
    def __init__(self, use_color: bool = True):
        """
        Initialize formatter.
        
        Args:
            use_color: Whether to use ANSI colors in output
        """
        self.use_color = use_color
    
    def _color(self, text: str, color: str) -> str:
        """Apply color to text if enabled."""
        if not self.use_color:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
    
    def format(self, result: DiagnosisResult, role: str = "owner") -> str:
        """
        Format diagnosis result as text.
        
        Args:
            result: Diagnosis result to format
            role: User role for output adaptation
            
        Returns:
            Formatted text output
        """
        lines = []
        
        # Header
        lines.append("")
        lines.append(self._color("╔══════════════════════════════════════════════════════════╗", "cyan"))
        lines.append(self._color("║                    诊断结果报告                          ║", "cyan"))
        lines.append(self._color("╚══════════════════════════════════════════════════════════╝", "cyan"))
        lines.append("")
        
        # Summary
        lines.append(self._color("【故障摘要】", "bold"))
        lines.append(f"  {result.summary}")
        lines.append("")
        
        # Fault Analysis
        if result.analysis:
            lines.append(self._color("【故障分析】", "bold"))
            for line in result.analysis:
                if line.strip():
                    lines.append(f"  {line}")
            lines.append("")
        
        # Possible Causes
        if result.possible_causes:
            lines.append(self._color("【可能原因】", "bold"))
            for i, cause in enumerate(result.possible_causes, 1):
                # Handle confidence - can be string ("高"/"中"/"低") or number (0-1)
                conf_raw = cause.get("confidence", 0.5)
                if isinstance(conf_raw, str):
                    conf_map = {"高": 0.85, "中": 0.6, "低": 0.35}
                    confidence_pct = int(conf_map.get(conf_raw, 0.5) * 100)
                else:
                    confidence_pct = int(conf_raw * 100)
                conf_color = "green" if confidence_pct >= 70 else "yellow" if confidence_pct >= 40 else "red"
                
                priority = cause.get("priority", "medium")
                priority_icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
                if not self.use_color:
                    priority_icon = f"[{priority.upper()}]"
                
                lines.append(f"  {i}. {cause.get('description', cause.get('name', '未知原因'))}")
                lines.append(f"     {self._color(f'置信度: {confidence_pct}%', conf_color)}  {priority_icon}")
                lines.append("")
        
        # Troubleshooting Steps
        if result.troubleshooting_steps:
            lines.append(self._color("【排查步骤】", "bold"))
            lines.append("")
            
            for i, step in enumerate(result.troubleshooting_steps, 1):
                lines.append(f"  ▶ 步骤 {i}: {step}")
                lines.append("")
        
        # Signal Recommendations
        if result.signal_recommendations:
            lines.append(self._color("【信号读取建议】", "bold"))
            lines.append("")
            lines.append(self._color("  建议读取以下车辆信号以辅助诊断:", "dim"))
            lines.append("")
            
            for i, signal in enumerate(result.signal_recommendations, 1):
                name = signal.get("name", "未知信号")
                desc_zh = signal.get("description_zh", "")
                reason = signal.get("reason", "")
                priority = signal.get("priority", "optional")
                read_method = signal.get("read_method", "")
                
                # Priority indicator
                if priority == "required":
                    priority_icon = "🔴" if self.use_color else "[必读]"
                    priority_text = "必读"
                elif priority == "recommended":
                    priority_icon = "🟡" if self.use_color else "[推荐]"
                    priority_text = "推荐"
                else:
                    priority_icon = "🟢" if self.use_color else "[可选]"
                    priority_text = "可选"
                
                lines.append(f"  {i}. {self._color(name, 'cyan')} {priority_icon}")
                if desc_zh:
                    lines.append(f"     描述: {desc_zh}")
                if reason:
                    lines.append(f"     原因: {self._color(reason, 'dim')}")
                if read_method:
                    lines.append(f"     方法: {read_method}")
                lines.append("")
        
        # Confidence
        conf_pct = int(result.confidence * 100)
        conf_color = "green" if conf_pct >= 80 else "yellow" if conf_pct >= 60 else "red"
        conf_label = "高" if conf_pct >= 80 else "中" if conf_pct >= 60 else "低"
        
        lines.append(self._color("【诊断置信度】", "bold"))
        lines.append(f"  {self._color(f'{conf_pct}% ({conf_label})', conf_color)}")
        
        # Confidence bar
        bar_length = 20
        filled = int(conf_pct / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        lines.append(f"  [{self._color(bar, conf_color)}]")
        
        # 显示置信度因素
        if hasattr(result, 'confidence_factors') and result.confidence_factors:
            lines.append("")
            lines.append(self._color("  【置信度分析】", "dim"))
            factors = result.confidence_factors
            cause_count = factors.get("cause_count", 0)
            step_count = factors.get("step_count", 0)
            analysis_len = factors.get("analysis_length", 0)
            kw_score = factors.get("keyword_match_score", 0)
            
            # 原因数量
            cause_score = "⭐⭐⭐" if 2 <= cause_count <= 4 else "⭐⭐" if cause_count == 1 else "⭐"
            lines.append(f"    可能原因: {cause_count}个 {cause_score}")
            
            # 排查步骤
            step_score = "⭐⭐⭐" if step_count >= 6 else "⭐⭐" if 3 <= step_count < 6 else "⭐"
            lines.append(f"    排查步骤: {step_count}步 {step_score}")
            
            # 分析详细度
            analysis_score = "⭐⭐⭐" if analysis_len >= 3 else "⭐⭐" if analysis_len > 0 else "⭐"
            lines.append(f"    分析深度: {analysis_len}项 {analysis_score}")
            
            # 关键词匹配
            kw_pct = int(kw_score * 100)
            lines.append(f"    关键词匹配: {kw_pct}%")
        
        lines.append("")
        
        # Role-specific notes
        lines.append(self._color("【建议】", "bold"))
        if role == "owner":
            lines.append("  如问题持续，请联系授权服务中心进行专业检测。")
        elif role == "technician":
            lines.append("  建议使用OBD诊断工具读取详细故障码，进行进一步分析。")
        elif role == "customer_service":
            lines.append("  如用户反馈问题仍未解决，建议升级至技术支持团队。")
        lines.append("")
        
        # Footer
        lines.append(self._color("─" * 60, "dim"))
        
        return "\n".join(lines)
    
    def format_simple(self, result: DiagnosisResult) -> str:
        """
        Format as simple text without box drawing.
        
        Args:
            result: Diagnosis result
            
        Returns:
            Simple text output
        """
        lines = []
        
        lines.append(f"故障摘要: {result.summary}")
        lines.append("")
        
        if result.analysis:
            lines.append("故障分析:")
            lines.extend(result.analysis)
            lines.append("")
        
        if result.possible_causes:
            lines.append("可能原因:")
            for i, cause in enumerate(result.possible_causes, 1):
                conf_raw = cause.get("confidence", 0.5)
                if isinstance(conf_raw, str):
                    conf_map = {"高": 85, "中": 60, "低": 35}
                    conf = conf_map.get(conf_raw, 50)
                else:
                    conf = int(conf_raw * 100)
                lines.append(f"  {i}. {cause.get('description', cause.get('name', '未知'))} (置信度: {conf}%)")
            lines.append("")
        
        if result.troubleshooting_steps:
            lines.append("排查步骤:")
            for i, step in enumerate(result.troubleshooting_steps, 1):
                lines.append(f"  {i}. {step}")
            lines.append("")
        
        lines.append(f"置信度: {int(result.confidence * 100)}%")
        
        return "\n".join(lines)
    
    def format_json(self, result: DiagnosisResult) -> str:
        """
        Format as JSON string.
        
        Args:
            result: Diagnosis result
            
        Returns:
            JSON formatted output
        """
        import json
        
        data = {
            "summary": result.summary,
            "analysis": result.analysis,
            "possible_causes": result.possible_causes,
            "troubleshooting_steps": result.troubleshooting_steps,
            "signal_recommendations": result.signal_recommendations,
            "confidence": result.confidence,
            "model_used": result.model_used,
            "processing_time_ms": result.processing_time_ms,
        }
        
        return json.dumps(data, ensure_ascii=False, indent=2)
