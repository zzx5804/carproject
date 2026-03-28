"""
Scenario detection for vehicle power diagnosis.

Centralizes the logic for detecting diagnosis scenarios from symptom text and DTC codes.
"""

import re
from typing import Optional, Dict, List, TYPE_CHECKING

from loguru import logger

from diagnosis_knowledge import SYMPTOM_PATTERNS, DTC_TO_SCENARIO_MAP

if TYPE_CHECKING:
    from models import DiagnosisContext


__all__ = [
    "ScenarioDetector",
    "get_scenario_detector",
    "detect_scenario",
    "detect_scenario_from_dtc",
]


class ScenarioDetector:
    """
    Detects diagnosis scenarios from symptom text.
    
    Scenarios are matched using keyword patterns defined in diagnosis_knowledge.py.
    
    Supported scenarios:
    - ble_auth: Bluetooth authentication failures
    - key_timeout: Key search timeout issues
    - forced_off: Forced power off scenarios
    - auto_poweroff: Auto power-off after inactivity
    - remote_on: Remote/OTA power on issues
    - alcohol_lock: Alcohol interlock related issues
    - bms_charging: Battery management/charging issues
    """
    
    DEFAULT_SCENARIO = "ble_auth"
    
    def __init__(self, patterns: Optional[Dict[str, List[str]]] = None):
        """
        Initialize scenario detector.
        
        Args:
            patterns: Optional custom patterns dict. Defaults to SYMPTOM_PATTERNS.
        """
        self.patterns = patterns or SYMPTOM_PATTERNS
    
    def detect(self, symptom: str) -> str:
        """
        Detect scenario from symptom text.
        
        Uses regex pattern matching to identify the most appropriate
        diagnosis scenario based on keywords in the symptom description.
        
        Args:
            symptom: The symptom text to analyze
            
        Returns:
            Detected scenario name (e.g., "ble_auth", "key_timeout").
            Returns DEFAULT_SCENARIO if no patterns match.
        """
        if not symptom:
            logger.warning("Empty symptom provided, defaulting to %s", self.DEFAULT_SCENARIO)
            return self.DEFAULT_SCENARIO
        
        symptom_lower = symptom.lower()
        
        # Check each scenario's patterns
        for scenario, patterns in self.patterns.items():
            for pattern in patterns:
                try:
                    if re.search(pattern, symptom_lower, re.IGNORECASE):
                        logger.debug(f"Detected scenario: {scenario} (matched: {pattern})")
                        return scenario
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                    continue
        
        # Default scenario
        logger.warning(
            f"No scenario matched for: {symptom[:50]}..., defaulting to {self.DEFAULT_SCENARIO}"
        )
        return self.DEFAULT_SCENARIO
    
    def detect_from_context(self, context: "DiagnosisContext") -> str:
        """
        Detect scenario from DiagnosisContext.
        
        Convenience method that extracts the symptom from the context
        and delegates to detect().
        
        Args:
            context: DiagnosisContext with symptom field
            
        Returns:
            Detected scenario name
        """
        return self.detect(context.symptom)
    
    def get_all_scenarios(self) -> List[str]:
        """
        Get list of all supported scenarios.
        
        Returns:
            List of scenario names that can be detected.
        """
        return list(self.patterns.keys())
    
    def add_pattern(self, scenario: str, pattern: str) -> None:
        """
        Add a new pattern for a scenario.
        
        Allows runtime extension of detection patterns.
        
        Args:
            scenario: Scenario name (will be created if doesn't exist)
            pattern: Regex pattern to match
        """
        if scenario not in self.patterns:
            self.patterns[scenario] = []
        self.patterns[scenario].append(pattern)
        logger.debug(f"Added pattern '{pattern}' to scenario '{scenario}'")
    
    def has_scenario(self, scenario: str) -> bool:
        """
        Check if a scenario is supported.
        
        Args:
            scenario: Scenario name to check
            
        Returns:
            True if scenario has patterns defined
        """
        return scenario in self.patterns
    
    def detect_from_dtc(self, dtc_codes: List[str]) -> List[str]:
        """
        Detect scenarios from DTC codes.
        
        Looks up DTC codes in the DTC_TO_SCENARIO_MAP and returns
        all related scenarios.
        
        Args:
            dtc_codes: List of DTC code strings
            
        Returns:
            List of scenario names related to the DTCs
        """
        scenarios = set()
        
        for code in dtc_codes:
            code_upper = code.upper().strip()
            if code_upper in DTC_TO_SCENARIO_MAP:
                scenarios.update(DTC_TO_SCENARIO_MAP[code_upper])
        
        if scenarios:
            logger.debug(f"Detected scenarios from DTC: {scenarios}")
        
        return list(scenarios)
    
    def detect_from_context_with_dtc(self, context: "DiagnosisContext") -> str:
        """
        Detect scenario from DiagnosisContext, considering both symptom and DTC codes.
        
        Priority:
        1. If DTC codes are present, use DTC-based scenario detection
        2. Otherwise, fall back to symptom-based detection
        
        Args:
            context: DiagnosisContext with symptom and dtc_codes fields
            
        Returns:
            Detected scenario name
        """
        # If DTC codes are present, prioritize DTC-based detection
        if context.dtc_codes:
            dtc_scenarios = self.detect_from_dtc(context.dtc_codes)
            if dtc_scenarios:
                # Return the first matched scenario
                return dtc_scenarios[0]
        
        # Fall back to symptom-based detection
        return self.detect(context.symptom)


# Singleton instance
_detector: Optional[ScenarioDetector] = None


def get_scenario_detector() -> ScenarioDetector:
    """
    Get or create the singleton scenario detector instance.
    
    Returns:
        The global ScenarioDetector instance
    """
    global _detector
    if _detector is None:
        _detector = ScenarioDetector()
    return _detector


def detect_scenario(symptom: str) -> str:
    """
    Convenience function to detect scenario from symptom text.
    
    Uses the singleton detector instance for efficiency.
    
    Args:
        symptom: Symptom text to analyze
        
    Returns:
        Detected scenario name
    """
    return get_scenario_detector().detect(symptom)


def detect_scenario_from_dtc(dtc_codes: List[str]) -> List[str]:
    """
    Convenience function to detect scenarios from DTC codes.
    
    Uses the singleton detector instance for efficiency.
    
    Args:
        dtc_codes: List of DTC code strings
        
    Returns:
        List of scenario names related to the DTCs
    """
    return get_scenario_detector().detect_from_dtc(dtc_codes)
