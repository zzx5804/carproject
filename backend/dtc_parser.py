"""
DTC (Diagnostic Trouble Code) Parser for vehicle power diagnosis.

Parses DTC codes according to SAE J2012 / ISO 15031-6 standards and
maps them to diagnosis knowledge.
"""

import re
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path

from loguru import logger

from models import DTCCategory, DTCSeverity, DTCParsedInfo, Hypothesis
from diagnosis_knowledge import DTC_KNOWLEDGE_BASE, DTC_HYPOTHESIS_TEMPLATES

if TYPE_CHECKING:
    from ontology.parser import OntologyParser

if TYPE_CHECKING:
    pass


__all__ = [
    "DTCParser",
    "OntologyDTCParser",
    "get_dtc_parser",
    "parse_dtc_code",
    "parse_dtc_codes",
]


class DTCParser:
    """
    Parser for Diagnostic Trouble Codes (DTC).
    
    Follows SAE J2012 / ISO 15031-6 standard for DTC format:
    - P0xxx/P1xxx: Powertrain (Engine/Transmission/Emissions)
    - C0xxx/C1xxx: Chassis (ABS/Steering/Suspension)
    - B0xxx/B1xxx: Body (Airbag/Climate/Lights)
    - U0xxx/U1xxx: Network (CAN/LIN Communication)
    
    Example codes:
    - U0100: Lost Communication with ECM/PCM
    - P0562: System Voltage Low
    - B2799: Engine Immobilizer System No Communication
    """
    
    # DTC format regex: Letter + 4 digits
    DTC_PATTERN = re.compile(r'^[PCBU]\d{4}$', re.IGNORECASE)
    
    # Category mapping from first character
    CATEGORY_MAP = {
        'P': DTCCategory.POWERTRAIN,
        'C': DTCCategory.CHASSIS,
        'B': DTCCategory.BODY,
        'U': DTCCategory.NETWORK,
    }
    
    # Default severity for unknown DTCs by category
    DEFAULT_SEVERITY = {
        DTCCategory.NETWORK: DTCSeverity.HIGH,
        DTCCategory.POWERTRAIN: DTCSeverity.HIGH,
        DTCCategory.CHASSIS: DTCSeverity.MEDIUM,
        DTCCategory.BODY: DTCSeverity.LOW,
    }
    
    def __init__(self, knowledge_base: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize DTC parser.
        
        Args:
            knowledge_base: Optional custom DTC knowledge base.
                           Defaults to DTC_KNOWLEDGE_BASE from diagnosis_knowledge.py.
        """
        self.knowledge_base = knowledge_base or DTC_KNOWLEDGE_BASE
        self.hypothesis_templates = DTC_HYPOTHESIS_TEMPLATES
    
    def is_valid_dtc(self, code: str) -> bool:
        """
        Check if a string is a valid DTC format.
        
        Args:
            code: String to check
            
        Returns:
            True if valid DTC format (e.g., "U0100", "P0562")
        """
        return bool(self.DTC_PATTERN.match(code.upper()))
    
    def normalize_dtc(self, code: str) -> str:
        """
        Normalize DTC code to uppercase standard format.
        
        Args:
            code: DTC code string (may have lowercase or spaces)
            
        Returns:
            Normalized uppercase DTC code
        """
        return code.upper().strip()
    
    def get_category(self, code: str) -> DTCCategory:
        """
        Get DTC category from the first character.
        
        Args:
            code: DTC code
            
        Returns:
            DTCCategory enum value
        """
        prefix = code[0].upper()
        return self.CATEGORY_MAP.get(prefix, DTCCategory.POWERTRAIN)
    
    def get_severity(self, code: str) -> DTCSeverity:
        """
        Get DTC severity level.
        
        Looks up severity from knowledge base, otherwise uses default
        based on category.
        
        Args:
            code: DTC code
            
        Returns:
            DTCSeverity enum value
        """
        code_upper = code.upper()
        
        # Check knowledge base first
        if code_upper in self.knowledge_base:
            severity_str = self.knowledge_base[code_upper].get("severity", "medium")
            return DTCSeverity(severity_str)
        
        # Default by category
        category = self.get_category(code_upper)
        return self.DEFAULT_SEVERITY.get(category, DTCSeverity.MEDIUM)
    
    def get_hypotheses(self, code: str) -> List[Hypothesis]:
        """
        Get hypothesis list for a DTC code.
        
        Args:
            code: DTC code
            
        Returns:
            List of Hypothesis objects
        """
        code_upper = code.upper()
        
        if code_upper in self.hypothesis_templates:
            templates = self.hypothesis_templates[code_upper]
            return [
                Hypothesis(name=t["name"], pct=t["pct"], cls=t["cls"])
                for t in templates
            ]
        
        # Default hypothesis based on category
        category = self.get_category(code_upper)
        default_hypotheses = {
            DTCCategory.NETWORK: [
                Hypothesis(name=f"{code_upper} 网络通信故障", pct=70, cls="p"),
                Hypothesis(name="CAN总线相关问题", pct=20, cls="s"),
                Hypothesis(name="ECU硬件故障", pct=10, cls="t"),
            ],
            DTCCategory.POWERTRAIN: [
                Hypothesis(name=f"{code_upper} 动力系统故障", pct=70, cls="p"),
                Hypothesis(name="传感器/执行器问题", pct=20, cls="s"),
                Hypothesis(name="控制模块故障", pct=10, cls="t"),
            ],
            DTCCategory.CHASSIS: [
                Hypothesis(name=f"{code_upper} 底盘系统故障", pct=70, cls="p"),
                Hypothesis(name="传感器故障", pct=20, cls="s"),
                Hypothesis(name="控制模块问题", pct=10, cls="t"),
            ],
            DTCCategory.BODY: [
                Hypothesis(name=f"{code_upper} 车身系统故障", pct=70, cls="p"),
                Hypothesis(name="线路问题", pct=20, cls="s"),
                Hypothesis(name="模块故障", pct=10, cls="t"),
            ],
        }
        return default_hypotheses.get(category, [])
    
    def parse(self, code: str) -> Optional[DTCParsedInfo]:
        """
        Parse a single DTC code into structured information.
        
        Args:
            code: DTC code string (e.g., "U0100")
            
        Returns:
            DTCParsedInfo object with parsed information, or None if invalid
        """
        code = self.normalize_dtc(code)
        
        if not self.is_valid_dtc(code):
            logger.warning(f"Invalid DTC format: {code}")
            return None
        
        category = self.get_category(code)
        severity = self.get_severity(code)
        hypotheses = self.get_hypotheses(code)
        
        # Check knowledge base for detailed info
        if code in self.knowledge_base:
            info = self.knowledge_base[code]
            return DTCParsedInfo(
                code=code,
                category=category,
                severity=severity,
                description=info.get("description", f"Unknown DTC: {code}"),
                description_zh=info.get("description_zh", f"未知故障码: {code}"),
                related_ecu=info.get("related_ecu", []),
                related_signals=info.get("related_signals", []),
                possible_causes=info.get("possible_causes", []),
                hypothesis=hypotheses,
            )
        
        # Unknown DTC - return basic info
        logger.info(f"DTC {code} not in knowledge base, using defaults")
        return DTCParsedInfo(
            code=code,
            category=category,
            severity=severity,
            description=f"Unknown DTC: {code}",
            description_zh=f"未知故障码: {code}",
            related_ecu=[],
            related_signals=[],
            possible_causes=[],
            hypothesis=hypotheses,
        )
    
    def parse_multiple(self, codes: List[str]) -> List[DTCParsedInfo]:
        """
        Parse multiple DTC codes.
        
        Args:
            codes: List of DTC code strings
            
        Returns:
            List of DTCParsedInfo objects (invalid codes are skipped)
        """
        results = []
        for code in codes:
            parsed = self.parse(code)
            if parsed:
                results.append(parsed)
        return results
    
    def get_related_scenarios(self, code: str) -> List[str]:
        """
        Get diagnosis scenarios related to a DTC code.
        
        Args:
            code: DTC code
            
        Returns:
            List of scenario names that may be relevant
        """
        code_upper = code.upper()
        if code_upper in self.knowledge_base:
            return self.knowledge_base[code_upper].get("scenarios", [])
        return []
    
    def get_related_signals(self, codes: List[str]) -> List[str]:
        """
        Get all related signals for a list of DTC codes.
        
        Args:
            codes: List of DTC codes
            
        Returns:
            Unique list of signal names
        """
        signals = set()
        for code in codes:
            code_upper = code.upper()
            if code_upper in self.knowledge_base:
                signals.update(self.knowledge_base[code_upper].get("related_signals", []))
        return list(signals)
    
    def get_related_ecus(self, codes: List[str]) -> List[str]:
        """
        Get all related ECUs for a list of DTC codes.
        
        Args:
            codes: List of DTC codes
            
        Returns:
            Unique list of ECU names
        """
        ecus = set()
        for code in codes:
            code_upper = code.upper()
            if code_upper in self.knowledge_base:
                ecus.update(self.knowledge_base[code_upper].get("related_ecu", []))
        return list(ecus)
    
    def get_max_severity(self, codes: List[str]) -> DTCSeverity:
        """
        Get the highest severity among multiple DTC codes.
        
        Args:
            codes: List of DTC codes
            
        Returns:
            Highest severity level found
        """
        if not codes:
            return DTCSeverity.LOW
        
        severity_order = {
            DTCSeverity.CRITICAL: 4,
            DTCSeverity.HIGH: 3,
            DTCSeverity.MEDIUM: 2,
            DTCSeverity.LOW: 1,
        }
        
        max_severity = DTCSeverity.LOW
        for code in codes:
            severity = self.get_severity(code)
            if severity_order[severity] > severity_order[max_severity]:
                max_severity = severity
        
        return max_severity
    
    def has_critical_dtc(self, codes: List[str]) -> bool:
        """
        Check if any DTC is critical severity.
        
        Args:
            codes: List of DTC codes
            
        Returns:
            True if any code is critical
        """
        return self.get_max_severity(codes) == DTCSeverity.CRITICAL


class OntologyDTCParser(DTCParser):
    """
    DTC parser that queries the TTL ontology first, falls back to knowledge base.
    
    This parser extends DTCParser to use the OWL ontology as the primary source
    of DTC information. If the ontology is unavailable or doesn't contain the
    requested DTC, it falls back to the parent class's DTC_KNOWLEDGE_BASE.
    
    Usage:
        parser = OntologyDTCParser()
        info = parser.parse('U0100')
    """
    
    def __init__(self, ontology_path: Optional[str] = None, knowledge_base: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize ontology-based DTC parser.
        
        Args:
            ontology_path: Path to the TTL ontology file. If None, uses default path.
            knowledge_base: Optional custom DTC knowledge base for fallback.
        """
        super().__init__(knowledge_base)
        
        self.ontology_parser: Optional["OntologyParser"] = None
        self._ontology_loaded = False
        
        # Determine ontology path
        if ontology_path is None:
            # Default path relative to this file
            default_path = Path(__file__).parent.parent / "vehicle_power_mode_ontology.ttl"
            ontology_path = str(default_path)
        
        # Try to load ontology
        try:
            from ontology.parser import OntologyParser
            self.ontology_parser = OntologyParser(ontology_path)
            if self.ontology_parser.load():
                self._ontology_loaded = True
                logger.info(f"OntologyDTCParser loaded ontology from {ontology_path}")
            else:
                logger.warning(f"OntologyDTCParser failed to load ontology from {ontology_path}, using fallback")
                self.ontology_parser = None
        except Exception as e:
            logger.warning(f"OntologyDTCParser initialization error: {e}, using fallback")
            self.ontology_parser = None
    
    def parse(self, code: str) -> Optional[DTCParsedInfo]:
        """
        Parse a single DTC code into structured information.
        
        Queries the ontology first. If not found in ontology, falls back
        to the parent class which uses DTC_KNOWLEDGE_BASE.
        
        Args:
            code: DTC code string (e.g., "U0100")
            
        Returns:
            DTCParsedInfo object with parsed information, or None if invalid
        """
        code = self.normalize_dtc(code)
        
        if not self.is_valid_dtc(code):
            logger.warning(f"Invalid DTC format: {code}")
            return None
        
        # Try ontology first
        if self._ontology_loaded and self.ontology_parser:
            dtc_info = self.ontology_parser.get_dtc_info(code)
            if dtc_info:
                return self._build_dtc_parsed_info(code, dtc_info)
        
        # Fall back to parent class (DTCParser which uses DTC_KNOWLEDGE_BASE)
        return super().parse(code)
    
    def _build_dtc_parsed_info(self, code: str, dtc_info: Dict[str, Any]) -> DTCParsedInfo:
        """
        Build DTCParsedInfo from ontology query result.
        
        Args:
            code: The DTC code
            dtc_info: Dictionary from ontology query
            
        Returns:
            DTCParsedInfo object
        """
        # Map category string to enum
        category_str = dtc_info.get("category", "powertrain")
        category_map = {
            "network": DTCCategory.NETWORK,
            "powertrain": DTCCategory.POWERTRAIN,
            "chassis": DTCCategory.CHASSIS,
            "body": DTCCategory.BODY,
        }
        category = category_map.get(category_str.lower(), DTCCategory.POWERTRAIN)
        
        # Map severity string to enum
        severity_str = dtc_info.get("severity", "medium")
        severity_map = {
            "critical": DTCSeverity.CRITICAL,
            "high": DTCSeverity.HIGH,
            "medium": DTCSeverity.MEDIUM,
            "low": DTCSeverity.LOW,
        }
        severity = severity_map.get(severity_str.lower(), DTCSeverity.MEDIUM)
        
        # Get hypotheses - try custom templates first, then use default based on category
        hypotheses = self.get_hypotheses(code)
        
        return DTCParsedInfo(
            code=code,
            category=category,
            severity=severity,
            description=dtc_info.get("description", f"Unknown DTC: {code}"),
            description_zh=dtc_info.get("description_zh", f"未知故障码: {code}"),
            related_ecu=dtc_info.get("related_ecu", []),
            related_signals=dtc_info.get("related_signals", []),
            possible_causes=dtc_info.get("possible_causes", []),
            hypothesis=hypotheses,
        )
    
    def get_all_dtcs(self) -> List[Dict[str, Any]]:
        """
        Get all DTCs from ontology or fallback knowledge base.
        
        Returns:
            List of DTC information dictionaries
        """
        if self._ontology_loaded and self.ontology_parser:
            return self.ontology_parser.get_all_dtcs()
        
        # Fallback to knowledge base
        return [
            {"code": code, **info}
            for code, info in self.knowledge_base.items()
        ]
    
    def get_dtcs_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get DTCs by category from ontology or fallback knowledge base.
        
        Args:
            category: DTC category (network, powertrain, chassis, body)
            
        Returns:
            List of DTC information dictionaries
        """
        if self._ontology_loaded and self.ontology_parser:
            return self.ontology_parser.get_dtcs_by_category(category)
        
        # Fallback: filter knowledge base by category
        category = category.lower()
        return [
            {"code": code, **info}
            for code, info in self.knowledge_base.items()
            if info.get("category", "").lower() == category
        ]
    
    def get_related_scenarios(self, code: str) -> List[str]:
        """
        Get diagnosis scenarios related to a DTC code.
        
        Queries ontology first, falls back to knowledge base.
        
        Args:
            code: DTC code
            
        Returns:
            List of scenario names that may be relevant
        """
        code_upper = code.upper()
        
        # Try ontology first
        if self._ontology_loaded and self.ontology_parser:
            dtc_info = self.ontology_parser.get_dtc_info(code_upper)
            if dtc_info:
                return dtc_info.get("scenarios", [])
        
        # Fallback to parent class
        return super().get_related_scenarios(code)


# Singleton instances
_parser: Optional[DTCParser] = None
_ontology_parser: Optional[OntologyDTCParser] = None


def get_dtc_parser(use_ontology: bool = False, ontology_path: Optional[str] = None) -> DTCParser:
    """
    Get or create the singleton DTC parser instance.
    
    Args:
        use_ontology: If True, returns OntologyDTCParser for ontology-based parsing
        ontology_path: Path to the TTL ontology file (only used when use_ontology=True)
        
    Returns:
        The global DTCParser or OntologyDTCParser instance
    """
    global _parser, _ontology_parser
    
    if use_ontology:
        if _ontology_parser is None:
            _ontology_parser = OntologyDTCParser(ontology_path)
        return _ontology_parser
    else:
        if _parser is None:
            _parser = DTCParser()
        return _parser


def parse_dtc_code(code: str) -> Optional[DTCParsedInfo]:
    """
    Convenience function to parse a single DTC code.
    
    Uses the singleton parser instance for efficiency.
    
    Args:
        code: DTC code string
        
    Returns:
        DTCParsedInfo object or None if invalid
    """
    return get_dtc_parser().parse(code)


def parse_dtc_codes(codes: List[str]) -> List[DTCParsedInfo]:
    """
    Convenience function to parse multiple DTC codes.
    
    Uses the singleton parser instance for efficiency.
    
    Args:
        codes: List of DTC code strings
        
    Returns:
        List of DTCParsedInfo objects
    """
    return get_dtc_parser().parse_multiple(codes)
