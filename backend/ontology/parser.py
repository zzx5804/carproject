"""
Ontology parser for TTL/RDF files.
Parses the vehicle power management ontology and provides query interfaces.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, Node
from rdflib.namespace import XSD
from loguru import logger


# =============================================================================
# Namespaces
# =============================================================================

# Match the ontology file namespace
VEHICLE = Namespace("http://example.org/vehicle-power-mode#")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class OntologyClass:
    """Represents an OWL class."""
    uri: str
    label: str
    label_zh: str = ""
    comment: str = ""
    comment_zh: str = ""
    parent_classes: List[str] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)


@dataclass
class OntologyProperty:
    """Represents an OWL property."""
    uri: str
    label: str
    label_zh: str = ""
    comment: str = ""
    comment_zh: str = ""
    domain: List[str] = field(default_factory=list)
    range: List[str] = field(default_factory=list)
    property_type: str = "object"  # "object" or "datatype"


@dataclass
class OntologyIndividual:
    """Represents an OWL individual."""
    uri: str
    label: str
    label_zh: str = ""
    class_type: str = ""
    property_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SWRLRule:
    """Represents a SWRL rule (parsed from comments)."""
    rule_id: str
    conditions: List[str]
    actions: List[str]
    source: str = ""
    confidence: float = 0.95


@dataclass
class TransitionRule:
    """Represents a transition rule instance from ontology."""
    uri: str
    rule_id: str
    label: str = ""
    label_zh: str = ""
    comment: str = ""
    comment_zh: str = ""


# =============================================================================
# Ontology Parser
# =============================================================================

class OntologyParser:
    """
    Parser for vehicle power management ontology.
    Loads TTL file(s) and provides query interfaces for agents.
    """
    
    def __init__(self, ontology_source: str):
        """
        Initialize the ontology parser.
        
        Args:
            ontology_source: Path to a TTL file OR a folder containing TTL files.
                            If folder, all *.ttl files will be loaded.
        """
        self.ontology_source = ontology_source
        self.graph: Optional[Graph] = None
        
        # Track loaded files
        self.loaded_files: List[str] = []
        
        # Parsed data
        self.classes: Dict[str, OntologyClass] = {}
        self.object_properties: Dict[str, OntologyProperty] = {}
        self.datatype_properties: Dict[str, OntologyProperty] = {}
        self.individuals: Dict[str, OntologyIndividual] = {}
        self.swrl_rules: List[SWRLRule] = []
        self.transition_rules: Dict[str, TransitionRule] = {}
        
        # Namespace
        self.ns = VEHICLE
        
        logger.info(f"OntologyParser initialized with source: {ontology_source}")
    
    def _require_graph(self) -> Graph:
        """Get the graph, raising an error if not loaded."""
        if self.graph is None:
            raise RuntimeError("Ontology not loaded. Call load() first.")
        return self.graph
    
    def load(self) -> bool:
        """Load and parse ontology file(s) from the source path."""
        try:
            # Determine if source is file or folder
            source_path = Path(self.ontology_source)
            
            if source_path.is_dir():
                # Folder mode: find all .ttl files
                ttl_files = sorted(source_path.glob("*.ttl"))
                
                if not ttl_files:
                    logger.warning(f"No TTL files found in folder: {self.ontology_source}")
                    return False
                
                # Load each file and merge into single graph
                self.graph = Graph()
                self.loaded_files = []
                
                for ttl_file in ttl_files:
                    try:
                        temp_graph = Graph()
                        temp_graph.parse(str(ttl_file), format="turtle")
                        self.graph += temp_graph
                        self.loaded_files.append(str(ttl_file.resolve()))
                        logger.info(f"Loaded ontology file: {ttl_file.name} ({len(temp_graph)} triples)")
                    except Exception as e:
                        logger.error(f"Failed to load {ttl_file}: {e}")
                
                logger.info(f"Loaded {len(self.loaded_files)} ontology files with {len(self.graph)} total triples")
                
            elif source_path.is_file():
                # Single file mode (backward compatible)
                self.graph = Graph()
                self.graph.parse(self.ontology_source, format="turtle")
                self.loaded_files = [str(source_path.resolve())]
                logger.info(f"Loaded ontology with {len(self.graph)} triples from {self.ontology_source}")
                
            else:
                logger.error(f"Ontology source not found: {self.ontology_source}")
                return False
            
            # Auto-detect namespace from loaded ontology
            self._detect_namespace()
            
            # Parse components
            self._parse_classes()
            self._parse_object_properties()
            self._parse_datatype_properties()
            self._parse_individuals()
            self._parse_swrl_rules()
            self._parse_transition_rules()
            
            logger.info(f"Parsed {len(self.classes)} classes, "
                       f"{len(self.object_properties)} object properties, "
                       f"{len(self.datatype_properties)} datatype properties, "
                       f"{len(self.individuals)} individuals, "
                       f"{len(self.swrl_rules)} SWRL rules, "
                       f"{len(self.transition_rules)} transition rules")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load ontology: {e}")
            return False
    
    def _detect_namespace(self) -> None:
        """
        Auto-detect the primary namespace from the loaded ontology.
        
        Strategy:
        1. FIRST: Scan all OWL class URIs to find most common namespace prefix
        2. FALLBACK: Check owl:Ontology declaration if no classes exist
        3. FINAL: Use default VEHICLE namespace
        
        This order is important because multi-file ontologies may have:
        - owl:Ontology declarations with different URIs (e.g., /action, /context)
        - But @prefix : declarations using the SAME base namespace
        """
        graph = self._require_graph()
        
        # PRIORITY 1: Find most common namespace from actual class URIs
        namespace_counts: Dict[str, int] = {}
        for class_uri in graph.subjects(RDF.type, OWL.Class):
            uri_str = str(class_uri)
            if "#" in uri_str:
                ns = uri_str.rsplit("#", 1)[0] + "#"
            elif "/" in uri_str:
                ns = "/".join(uri_str.split("/")[:-1]) + "/"
            else:
                continue
            namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
        
        if namespace_counts:
            most_common = max(namespace_counts.items(), key=lambda x: x[1])[0]
            self.ns = Namespace(most_common)
            logger.info(f"Auto-detected namespace from classes: {most_common} ({namespace_counts[most_common]} classes)")
            return
        
        # PRIORITY 2: Fall back to owl:Ontology declaration (for ontologies with no classes)
        for ontology_uri in graph.subjects(RDF.type, OWL.Ontology):
            uri_str = str(ontology_uri)
            base_uri = uri_str.rstrip("#")
            
            # Use the base URI + # as namespace
            if "#" in uri_str:
                ns_uri = uri_str.rsplit("#", 1)[0] + "#"
            else:
                ns_uri = base_uri + "#"
            
            self.ns = Namespace(ns_uri)
            logger.info(f"Auto-detected namespace from owl:Ontology: {ns_uri}")
            return
        
        # PRIORITY 3: Default fallback
        self.ns = VEHICLE
        logger.warning(f"Could not detect namespace, using default: {VEHICLE}")
    
    def _get_label(self, subject: Union[URIRef, Node], lang: str = "en") -> str:
        """Get label for a subject."""
        graph = self._require_graph()
        for label in graph.objects(subject, RDFS.label):
            if isinstance(label, Literal) and label.language == lang:
                return str(label)
        for label in graph.objects(subject, RDFS.label):
            return str(label)
        return str(subject).split("#")[-1]
    
    def _get_comment(self, subject: Union[URIRef, Node], lang: str = "en") -> str:
        """Get comment for a subject."""
        graph = self._require_graph()
        for comment in graph.objects(subject, RDFS.comment):
            if isinstance(comment, Literal) and comment.language == lang:
                return str(comment)
        for comment in graph.objects(subject, RDFS.comment):
            return str(comment)
        return ""
    
    def _parse_classes(self):
        """Parse all OWL classes."""
        graph = self._require_graph()
        for class_uri in graph.subjects(RDF.type, OWL.Class):
            class_uri_str = str(class_uri)
            if not class_uri_str.startswith(str(self.ns)):
                continue
            
            local_name = class_uri_str.split("#")[-1]
            
            # Get labels
            label_en = self._get_label(class_uri, "en")
            label_zh = self._get_label(class_uri, "zh")
            
            # Get comments
            comment_en = self._get_comment(class_uri, "en")
            comment_zh = self._get_comment(class_uri, "zh")
            
            # Get parent classes
            parent_classes = []
            for parent in graph.objects(class_uri, RDFS.subClassOf):
                parent_str = str(parent)
                if parent_str.startswith(str(self.ns)):
                    parent_classes.append(parent_str.split("#")[-1])
            
            self.classes[local_name] = OntologyClass(
                uri=class_uri_str,
                label=label_en,
                label_zh=label_zh,
                comment=comment_en,
                comment_zh=comment_zh,
                parent_classes=parent_classes
            )
    
    def _parse_object_properties(self):
        """Parse all OWL object properties."""
        graph = self._require_graph()
        for prop_uri in graph.subjects(RDF.type, OWL.ObjectProperty):
            prop_uri_str = str(prop_uri)
            if not prop_uri_str.startswith(str(self.ns)):
                continue
            
            local_name = prop_uri_str.split("#")[-1]
            
            label_en = self._get_label(prop_uri, "en")
            label_zh = self._get_label(prop_uri, "zh")
            comment_en = self._get_comment(prop_uri, "en")
            comment_zh = self._get_comment(prop_uri, "zh")
            
            domains = [str(d).split("#")[-1] for d in graph.objects(prop_uri, RDFS.domain)
                      if str(d).startswith(str(self.ns))]
            ranges = [str(r).split("#")[-1] for r in graph.objects(prop_uri, RDFS.range)
                     if str(r).startswith(str(self.ns))]
            
            self.object_properties[local_name] = OntologyProperty(
                uri=prop_uri_str,
                label=label_en,
                label_zh=label_zh,
                comment=comment_en,
                comment_zh=comment_zh,
                domain=domains,
                range=ranges,
                property_type="object"
            )
    
    def _parse_datatype_properties(self):
        """Parse all OWL datatype properties."""
        graph = self._require_graph()
        for prop_uri in graph.subjects(RDF.type, OWL.DatatypeProperty):
            prop_uri_str = str(prop_uri)
            if not prop_uri_str.startswith(str(self.ns)):
                continue
            
            local_name = prop_uri_str.split("#")[-1]
            
            label_en = self._get_label(prop_uri, "en")
            label_zh = self._get_label(prop_uri, "zh")
            comment_en = self._get_comment(prop_uri, "en")
            comment_zh = self._get_comment(prop_uri, "zh")
            
            domains = [str(d).split("#")[-1] for d in graph.objects(prop_uri, RDFS.domain)
                      if str(d).startswith(str(self.ns))]
            
            # Get range (xsd type)
            ranges = []
            for r in graph.objects(prop_uri, RDFS.range):
                r_str = str(r)
                if "XMLSchema" in r_str or "xsd" in r_str:
                    ranges.append(r_str.split("#")[-1])
                elif r_str.startswith(str(self.ns)):
                    ranges.append(r_str.split("#")[-1])
            
            self.datatype_properties[local_name] = OntologyProperty(
                uri=prop_uri_str,
                label=label_en,
                label_zh=label_zh,
                comment=comment_en,
                comment_zh=comment_zh,
                domain=domains,
                range=ranges,
                property_type="datatype"
            )
    
    def _parse_individuals(self):
        """
        Parse all OWL individuals.
        
        Captures individuals in two forms:
        1. Explicit owl:NamedIndividual declarations
        2. Resources typed as user-defined classes (e.g., :powerModeOff rdf:type :OffMode)
        
        Excludes:
        - OWL classes, properties (already parsed separately)
        - Resources outside the ontology namespace
        """
        graph = self._require_graph()
        
        # OWL meta-types to exclude (these are schema definitions, not individuals)
        excluded_types = {
            OWL.Class, OWL.NamedIndividual, OWL.ObjectProperty, 
            OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.Ontology,
            OWL.Restriction, OWL.AllDisjointClasses
        }
        
        # Also exclude by URI (some OWL types may be referenced differently)
        excluded_type_uris = {
            str(OWL.Class), str(OWL.NamedIndividual), str(OWL.ObjectProperty),
            str(OWL.DatatypeProperty), str(OWL.AnnotationProperty), str(OWL.Ontology),
            str(OWL.Restriction), str(OWL.AllDisjointClasses),
            str(RDFS.Class), str(RDFS.Datatype)
        }
        
        # Track seen URIs to avoid duplicates
        seen_uris = set()
        
        # Find all subjects that have rdf:type in the namespace
        for subject in graph.subjects(RDF.type, None):
            uri_str = str(subject)
            
            # Skip if not in namespace
            if not uri_str.startswith(str(self.ns)):
                continue
            
            # Skip if already processed
            if uri_str in seen_uris:
                continue
            
            # Get all types for this subject
            types = list(self.graph.objects(subject, RDF.type))
            
            # Check if any type is a user-defined class (not OWL meta-type)
            is_individual = False
            class_type = ""
            
            for t in types:
                t_str = str(t)
                
                # Skip OWL meta-types
                if t in excluded_types or t_str in excluded_type_uris:
                    continue
                
                # Check if it's a class defined in our ontology
                if t_str.startswith(str(self.ns)):
                    # This is typed as a user-defined class -> it's an individual
                    local_type = t_str.split("#")[-1]
                    
                    # Verify this type is actually a class we parsed
                    if local_type in self.classes:
                        is_individual = True
                        if not class_type:
                            class_type = local_type
            
            if not is_individual:
                continue
            
            seen_uris.add(uri_str)
            local_name = uri_str.split("#")[-1]
            
            # Skip if this is already parsed as a class or property
            if local_name in self.classes:
                continue
            if local_name in self.object_properties or local_name in self.datatype_properties:
                continue
            
            label_en = self._get_label(subject, "en")
            label_zh = self._get_label(subject, "zh")
            
            # Get property values
            property_values = {}
            for pred, obj in self.graph.predicate_objects(subject):
                pred_str = str(pred)
                # Include both namespace properties and standard properties like rdfs:label
                if pred_str.startswith(str(self.ns)):
                    pred_name = pred_str.split("#")[-1]
                    if isinstance(obj, Literal):
                        property_values[pred_name] = str(obj)
                    else:
                        property_values[pred_name] = str(obj).split("#")[-1]
            
            self.individuals[local_name] = OntologyIndividual(
                uri=uri_str,
                label=label_en,
                label_zh=label_zh,
                class_type=class_type,
                property_values=property_values
            )
    
    def _parse_swrl_rules(self):
        """Parse SWRL rules from all loaded TTL files (from comments)."""
        # Determine which files to parse
        files_to_parse = self.loaded_files if self.loaded_files else []
        
        # Fallback: if no loaded_files yet, try ontology_source if it's a file
        if not files_to_parse and hasattr(self, 'ontology_source'):
            if os.path.isfile(self.ontology_source):
                files_to_parse = [self.ontology_source]
        
        for file_path in files_to_parse:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find the SWRL rules section
                if "# SWRL RULES" not in content:
                    continue
                
                # Extract the rules section
                lines = content.split('\n')
                in_rules_section = False
                current_rule_lines = []
                
                for line in lines:
                    if "# SWRL RULES" in line:
                        in_rules_section = True
                        continue
                    if in_rules_section:
                        if line.strip().startswith('# SWRL Rule') or line.strip().startswith('# Rule'):
                            if current_rule_lines:
                                # Process previous rule
                                self._parse_rule_block(current_rule_lines)
                                current_rule_lines = []
                            current_rule_lines.append(line)
                        elif line.strip().startswith('# ') and in_rules_section:
                            current_rule_lines.append(line)
                        elif line.strip() and not line.strip().startswith('#'):
                            # End of rules section
                            if current_rule_lines:
                                self._parse_rule_block(current_rule_lines)
                            break
                
            except Exception as e:
                logger.warning(f"Could not parse SWRL rules from {file_path}: {e}")
        
        logger.debug(f"Parsed {len(self.swrl_rules)} SWRL rules from file comments")
    
    def _parse_rule_block(self, lines: list):
        """Parse a block of rule lines into a SWRLRule."""
        if not lines:
            return
        
        # First line has Rule ID and name
        first_line = lines[0].strip()
        match = re.search(r'#\s*(?:SWRL\s+)?Rule\s*(\d+):\s*(.+)', first_line)
        if not match:
            return
        
        rule_id = f"R-{match.group(1)}"
        rule_name = match.group(2).strip()
        
        # Collect all rule text (remove # prefix)
        rule_text = ""
        for line in lines[1:]:
            clean_line = line.strip().lstrip('#').strip()
            if clean_line:
                rule_text += clean_line + " "
        
        # Split into conditions and actions by ->
        if '->' in rule_text:
            parts = rule_text.split('->')
            conditions_part = parts[0].strip()
            actions_part = parts[1].strip() if len(parts) > 1 else ""
            
            # Parse conditions (split by ^)
            conditions = []
            for cond in conditions_part.split('^'):
                cond = cond.strip()
                if cond:
                    conditions.append(cond)
            
            # Parse actions (split by ^)
            actions = []
            for act in actions_part.split('^'):
                act = act.strip()
                if act:
                    actions.append(act)
        else:
            # No arrow, treat all as conditions
            conditions = [rule_text.strip()]
            actions = []
        
        if conditions or actions:
            self.swrl_rules.append(SWRLRule(
                rule_id=rule_id,
                conditions=conditions,
                actions=actions,
                source=rule_name,
                confidence=0.95
            ))
    
    def _parse_swrl_comment(self, comment: str):
        """Parse a SWRL rule from comment text."""
        lines = comment.strip().split("\n")
        current_rule = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("# Rule") or line.startswith("Rule"):
                # New rule
                if current_rule:
                    self.swrl_rules.append(current_rule)
                parts = line.split(":", 1)
                rule_id = parts[0].replace("#", "").strip()
                current_rule = SWRLRule(
                    rule_id=rule_id,
                    conditions=[],
                    actions=[],
                    source="Ontology Comment"
                )
            elif "->" in line and current_rule:
                # Rule body
                parts = line.split("->")
                if len(parts) == 2:
                    conditions = parts[0].strip()
                    actions = parts[1].strip()
                    current_rule.conditions.append(conditions)
                    current_rule.actions.append(actions)
            elif line.startswith("#") and current_rule:
                # Comment about the rule
                pass
        
        if current_rule:
            self.swrl_rules.append(current_rule)
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    def get_class(self, name: str) -> Optional[OntologyClass]:
        """Get a class by name."""
        return self.classes.get(name)
    
    def get_class_hierarchy(self, name: str) -> List[str]:
        """Get all parent classes for a class."""
        result = []
        current = self.classes.get(name)
        while current:
            result.append(current.label)
            if current.parent_classes:
                parent_name = current.parent_classes[0]
                current = self.classes.get(parent_name)
            else:
                break
        return result
    
    def get_property(self, name: str) -> Optional[OntologyProperty]:
        """Get a property by name (checks both object and datatype properties)."""
        if name in self.object_properties:
            return self.object_properties[name]
        return self.datatype_properties.get(name)
    
    def get_signal_info(self, signal_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a signal/datatype property."""
        prop = self.datatype_properties.get(signal_name)
        if prop:
            return {
                "name": signal_name,
                "label": prop.label,
                "label_zh": prop.label_zh,
                "comment": prop.comment,
                "comment_zh": prop.comment_zh,
                "domain": prop.domain,
                "range": prop.range
            }
        return None
    
    def get_power_mode_info(self) -> Dict[str, Any]:
        """Get information about power modes."""
        modes = {}
        for name in ["OffMode", "LocalOnMode", "RemoteOnMode"]:
            cls = self.classes.get(name)
            if cls:
                modes[name] = {
                    "label": cls.label,
                    "label_zh": cls.label_zh,
                    "comment": cls.comment,
                    "comment_zh": cls.comment_zh
                }
        return modes
    
    def get_transition_rules(self) -> List[Dict[str, Any]]:
        """Get all power transition rules."""
        rules = []
        for name, cls in self.classes.items():
            if "Rule" in name and "Transition" in cls.comment:
                rules.append({
                    "name": name,
                    "label": cls.label,
                    "label_zh": cls.label_zh,
                    "comment": cls.comment,
                    "comment_zh": cls.comment_zh
                })
        return rules
    
    def get_key_types(self) -> Dict[str, Any]:
        """Get information about key types."""
        keys = {}
        for name in ["BLEKey", "RKEKey", "NFCKey", "UWBKey", "DigitalKey"]:
            cls = self.classes.get(name)
            if cls:
                keys[name] = {
                    "label": cls.label,
                    "label_zh": cls.label_zh,
                    "comment": cls.comment,
                    "comment_zh": cls.comment_zh
                }
        return keys
    
    def get_ecu_info(self) -> Dict[str, Any]:
        """Get information about ECUs."""
        ecus = {}
        for name in ["LDCU", "RDCU", "CCU", "TBOX", "XPU"]:
            cls = self.classes.get(name)
            if cls:
                ecus[name] = {
                    "label": cls.label,
                    "label_zh": cls.label_zh,
                    "comment": cls.comment,
                    "comment_zh": cls.comment_zh
                }
        return ecus
    
    def search_by_keyword(self, keyword: str) -> Dict[str, List[str]]:
        """Search ontology by keyword (in labels and comments)."""
        keyword_lower = keyword.lower()
        results = {
            "classes": [],
            "properties": [],
            "individuals": []
        }
        
        for name, cls in self.classes.items():
            if (keyword_lower in cls.label.lower() or 
                keyword_lower in cls.label_zh.lower() or
                keyword_lower in cls.comment.lower()):
                results["classes"].append(name)
        
        for name, prop in {**self.object_properties, **self.datatype_properties}.items():
            if (keyword_lower in prop.label.lower() or 
                keyword_lower in prop.label_zh.lower() or
                keyword_lower in prop.comment.lower()):
                results["properties"].append(name)
        
        for name, ind in self.individuals.items():
            if (keyword_lower in ind.label.lower() or 
                keyword_lower in ind.label_zh.lower()):
                results["individuals"].append(name)
        
        return results
    
    def get_ontology_summary_html(self, context: Dict[str, Any]) -> str:
        """Generate HTML summary of relevant ontology information."""
        # Build HTML based on context
        html_parts = [
            '<div style="font-family:var(--mono);font-size:11px;line-height:2;color:var(--tx)">',
            '<div style="color:var(--txd);font-size:10px;margin-bottom:4px">// CEA Vehicle Ontology v1.0</div>',
        ]
        
        # Add power mode info
        power_modes = self.get_power_mode_info()
        if power_modes:
            html_parts.append('<div style="color:var(--acc);margin-bottom:6px">// Power Modes</div>')
            for name, info in power_modes.items():
                html_parts.append(f'<div><span style="color:var(--txd)">{name}:</span> <span>{info["label_zh"]}</span></div>')
        
        # Add key types
        key_types = self.get_key_types()
        if key_types:
            html_parts.append('<div style="color:var(--ylw);margin-top:6px">// Key Types</div>')
            for name, info in key_types.items():
                html_parts.append(f'<div><span style="color:var(--txd)">{name}:</span> <span>{info["label_zh"]}</span></div>')
        
        # Add ECU info
        ecus = self.get_ecu_info()
        if ecus:
            html_parts.append('<div style="color:var(--grn);margin-top:6px">// ECUs</div>')
            for name, info in ecus.items():
                html_parts.append(f'<div><span style="color:var(--txd)">{name}:</span> <span>{info["label_zh"]}</span></div>')
        
        html_parts.append('</div>')
        return "".join(html_parts)
    
    # =========================================================================
    # DTC Query Methods
    # =========================================================================
    
    def get_dtc_info(self, dtc_code: str) -> Optional[Dict[str, Any]]:
        """
        Get DTC information by code (e.g., 'U0100').
        
        Args:
            dtc_code: The DTC code to look up (e.g., 'U0100', 'P0562')
            
        Returns:
            Dictionary with DTC information, or None if not found
        """
        if not self.graph:
            return None
        
        dtc_code = dtc_code.upper().strip()
        
        # Find individual with dtcCode matching the input
        dtc_uri = None
        for subject in self.graph.subjects(self.ns.dtcCode, Literal(dtc_code)):
            dtc_uri = subject
            break
        
        if not dtc_uri:
            return None
        
        return self._extract_dtc_info(dtc_uri)
    
    def _extract_dtc_info(self, dtc_uri: URIRef) -> Dict[str, Any]:
        """Extract DTC information from a DTC individual URI."""
        result: Dict[str, Any] = {
            "code": "",
            "category": "",
            "severity": "",
            "description": "",
            "description_zh": "",
            "related_ecu": [],
            "related_signals": [],
            "possible_causes": [],
            "scenarios": [],
        }
        
        # Get DTC code
        for code in self.graph.objects(dtc_uri, self.ns.dtcCode):
            result["code"] = str(code)
            break
        
        # Get description
        for desc in self.graph.objects(dtc_uri, self.ns.hasDescription):
            result["description"] = str(desc)
            break
        
        for desc_zh in self.graph.objects(dtc_uri, self.ns.hasDescriptionZh):
            result["description_zh"] = str(desc_zh)
            break
        
        # Get category from hasDTCCategory property
        for category_uri in self.graph.objects(dtc_uri, self.ns.hasDTCCategory):
            category_name = str(category_uri).split("#")[-1]
            # Map to lowercase category name
            category_map = {
                "categoryNetwork": "network",
                "categoryPowertrain": "powertrain", 
                "categoryChassis": "chassis",
                "categoryBody": "body",
            }
            result["category"] = category_map.get(category_name, category_name.lower().replace("category", ""))
            break
        
        # If category not found via property, infer from rdf:type
        if not result["category"]:
            for type_uri in self.graph.objects(dtc_uri, RDF.type):
                type_name = str(type_uri).split("#")[-1]
                if type_name == "NetworkDTC":
                    result["category"] = "network"
                    break
                elif type_name == "PowertrainDTC":
                    result["category"] = "powertrain"
                    break
                elif type_name == "ChassisDTC":
                    result["category"] = "chassis"
                    break
                elif type_name == "BodyDTC":
                    result["category"] = "body"
                    break
        
        # Get severity from hasDTCSeverity property
        for severity_uri in self.graph.objects(dtc_uri, self.ns.hasDTCSeverity):
            severity_name = str(severity_uri).split("#")[-1]
            # Map to lowercase severity name
            severity_map = {
                "severityCritical": "critical",
                "severityHigh": "high",
                "severityMedium": "medium",
                "severityLow": "low",
            }
            result["severity"] = severity_map.get(severity_name, severity_name.lower().replace("severity", ""))
            break
        
        # Get multi-valued properties
        result["related_ecu"] = [str(ecu) for ecu in self.graph.objects(dtc_uri, self.ns.hasRelatedECUName)]
        result["related_signals"] = [str(sig) for sig in self.graph.objects(dtc_uri, self.ns.hasRelatedSignalName)]
        result["possible_causes"] = [str(cause) for cause in self.graph.objects(dtc_uri, self.ns.hasPossibleCause)]
        result["scenarios"] = [str(scenario) for scenario in self.graph.objects(dtc_uri, self.ns.triggersScenarioName)]
        
        return result
    
    def get_all_dtcs(self) -> List[Dict[str, Any]]:
        """
        Get all DTC individuals from ontology.
        
        Returns:
            List of dictionaries with DTC information
        """
        if not self.graph:
            return []
        
        dtcs = []
        seen_codes = set()
        
        # Query for all DTC types
        dtc_types = [
            self.ns.NetworkDTC,
            self.ns.PowertrainDTC,
            self.ns.ChassisDTC,
            self.ns.BodyDTC,
            self.ns.DiagnosticTroubleCode,
        ]
        
        for dtc_type in dtc_types:
            for dtc_uri in self.graph.subjects(RDF.type, dtc_type):
                info = self._extract_dtc_info(dtc_uri)
                if info and info.get("code") and info["code"] not in seen_codes:
                    seen_codes.add(info["code"])
                    dtcs.append(info)
        
        return dtcs
    
    def get_dtcs_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get DTCs by category (network, powertrain, chassis, body).
        
        Args:
            category: The DTC category to filter by
            
        Returns:
            List of dictionaries with DTC information for the given category
        """
        category = category.lower().strip()
        
        # Map category name to class URI
        category_class_map = {
            "network": self.ns.NetworkDTC,
            "powertrain": self.ns.PowertrainDTC,
            "chassis": self.ns.ChassisDTC,
            "body": self.ns.BodyDTC,
        }
        
        dtc_class = category_class_map.get(category)
        if not dtc_class or not self.graph:
            return []
        
        dtcs = []
        seen_codes = set()
        
        for dtc_uri in self.graph.subjects(RDF.type, dtc_class):
            info = self._extract_dtc_info(dtc_uri)
            if info and info.get("code") and info["code"] not in seen_codes:
                seen_codes.add(info["code"])
                dtcs.append(info)
        
        return dtcs
    
    # =========================================================================
    # Transition Rules Parsing
    # =========================================================================
    
    def _parse_transition_rules(self) -> None:
        """
        Parse TransitionRule individuals from the ontology.
        
        Transition rules are stored as owl:NamedIndividual with type :TransitionRule.
        """
        # Find the TransitionRule class
        transition_rule_class = self.ns.TransitionRule
        rule_id_property = self.ns.ruleId
        
        count = 0
        for rule_uri in self.graph.subjects(RDF.type, transition_rule_class):
            uri_str = str(rule_uri)
            local_name = uri_str.split("#")[-1] if "#" in uri_str else uri_str
            
            # Get labels
            label_en = self._get_label(rule_uri, "en")
            label_zh = self._get_label(rule_uri, "zh")
            
            # Get comments
            comment_en = self._get_comment(rule_uri, "en")
            comment_zh = self._get_comment(rule_uri, "zh")
            
            # Get rule ID
            rule_id = local_name  # Default to local name
            for rid in self.graph.objects(rule_uri, rule_id_property):
                rule_id = str(rid)
                break
            
            self.transition_rules[local_name] = TransitionRule(
                uri=uri_str,
                rule_id=rule_id,
                label=label_en,
                label_zh=label_zh,
                comment=comment_en,
                comment_zh=comment_zh
            )
            count += 1
        
        if count > 0:
            logger.info(f"Parsed {count} transition rules from ontology individuals")
    
    def get_transition_rules_info(self) -> Dict[str, Any]:
        """Get information about transition rules."""
        return {
            name: {
                "rule_id": tr.rule_id,
                "label": tr.label,
                "label_zh": tr.label_zh,
                "comment": tr.comment,
                "comment_zh": tr.comment_zh
            }
            for name, tr in self.transition_rules.items()
        }

    # =========================================================================
    # SPARQL Query Methods (Ontology-as-Evidence)
    # =========================================================================

    def query_matching_rules(self, keywords: List[str]) -> List[Any]:
        """
        Query TransitionRule individuals whose labels or comments match keywords.

        Returns ActivatedNode list sorted by confidence descending.
        Confidence is computed as: matched_keywords / total_keywords, floored at 0.5
        if the rule has any match at all.
        """
        from models import ActivatedNode

        graph = self._require_graph()
        ns = self.ns

        # SPARQL: fetch all TransitionRule individuals with their metadata.
        # :faultScenario has multiple values per rule, so OPTIONAL expansion
        # produces multiple rows per rule — we merge in Python below.
        sparql = """
        SELECT ?rule ?ruleId ?labelZh ?commentZh ?fromState ?toState ?faultScenario
        WHERE {
            ?rule rdf:type :TransitionRule .
            OPTIONAL { ?rule :ruleId ?ruleId . }
            OPTIONAL { ?rule rdfs:label ?labelZh FILTER(lang(?labelZh) = "zh") . }
            OPTIONAL { ?rule rdfs:comment ?commentZh FILTER(lang(?commentZh) = "zh") . }
            OPTIONAL { ?rule :fromState ?fromState . }
            OPTIONAL { ?rule :toState ?toState . }
            OPTIONAL { ?rule :faultScenario ?faultScenario FILTER(lang(?faultScenario) = "zh") . }
        }
        """
        results = graph.query(
            sparql,
            initNs={"rdf": RDF, "rdfs": RDFS, "": ns},
        )

        # Step 1: merge multi-row results (one row per faultScenario value) by rule URI
        rule_map: Dict[str, Dict] = {}
        for row in results:
            rule_uri = str(row.rule) if row.rule else ""
            if not rule_uri:
                continue
            if rule_uri not in rule_map:
                rule_map[rule_uri] = {
                    "ruleId": str(row.ruleId) if row.ruleId else rule_uri.split("#")[-1],
                    "labelZh": str(row.labelZh) if row.labelZh else "",
                    "commentZh": str(row.commentZh) if row.commentZh else "",
                    "fromState": str(row.fromState).split("#")[-1] if row.fromState else "",
                    "toState": str(row.toState).split("#")[-1] if row.toState else "",
                    "faultScenarios": [],
                }
            entry = rule_map[rule_uri]
            if not entry["labelZh"] and row.labelZh:
                entry["labelZh"] = str(row.labelZh)
            if not entry["commentZh"] and row.commentZh:
                entry["commentZh"] = str(row.commentZh)
            if not entry["fromState"] and row.fromState:
                entry["fromState"] = str(row.fromState).split("#")[-1]
            if not entry["toState"] and row.toState:
                entry["toState"] = str(row.toState).split("#")[-1]
            if row.faultScenario:
                fs = str(row.faultScenario)
                if fs not in entry["faultScenarios"]:
                    entry["faultScenarios"].append(fs)

        # Step 2: score each rule with fault phrase hits weighted ×2 vs base text hits
        activated: List[Any] = []
        keywords_lower = [k.lower() for k in keywords]

        for rule_uri, data in rule_map.items():
            rule_id = data["ruleId"]
            label_zh = data["labelZh"] or rule_id
            comment_zh = data["commentZh"]
            from_state = data["fromState"]
            to_state = data["toState"]

            base_searchable = f"{label_zh} {comment_zh} {from_state} {to_state}".lower()
            fault_searchable = " ".join(data["faultScenarios"]).lower()

            base_hits = sum(1 for kw in keywords_lower if kw in base_searchable)
            fault_hits = sum(1 for kw in keywords_lower if kw in fault_searchable)

            # Fault scenario phrases carry double weight (more semantically precise)
            total_hits = base_hits + fault_hits * 2
            if total_hits == 0:
                continue

            total_kw = max(len(keywords_lower), 1)
            confidence = min(0.5 + (total_hits / (total_kw * 3)) * 0.5, 1.0)

            local_name = rule_uri.split("#")[-1] if "#" in rule_uri else rule_id
            activated.append(
                ActivatedNode(
                    node_id=rule_id,
                    node_type="rule",
                    label_zh=label_zh,
                    confidence=round(confidence, 2),
                    source_triple=f"rules_model.ttl#{local_name}",
                )
            )

        # Sort by confidence descending, limit to top 5
        activated.sort(key=lambda n: n.confidence, reverse=True)
        return activated[:5]

    def query_signal_individuals(self, signals: Dict[str, str]) -> Dict[str, str]:
        """
        Map frontend signal key-values to Ontology individual local names.

        Mapping table:
        - sv-pm with "Off"    → ":OffMode"
        - sv-pm with "Remote" → ":RemoteOnMode"
        - sv-pm with "Local"  → ":LocalOnMode"
        - sv-pm with "Conv"   → ":ConvenienceMode"
        - sv-kv "VALID"       → ":ReadyEnableEnable"
        - sv-kv "INVALID"     → ":ReadyEnableDisable"
        """
        mappings: Dict[str, str] = {}

        sv_pm = signals.get("sv-pm", "")
        if "Off" in sv_pm:
            mappings["sv-pm"] = ":OffMode"
        elif "Remote" in sv_pm:
            mappings["sv-pm"] = ":RemoteOnMode"
        elif "Local" in sv_pm or "On" in sv_pm:
            mappings["sv-pm"] = ":LocalOnMode"
        elif "Conv" in sv_pm:
            mappings["sv-pm"] = ":ConvenienceMode"

        sv_kv = signals.get("sv-kv", "")
        if "VALID" in sv_kv and "INVALID" not in sv_kv:
            mappings["sv-kv"] = ":ReadyEnableEnable"
        elif "INVALID" in sv_kv:
            mappings["sv-kv"] = ":ReadyEnableDisable"

        sv_ble = signals.get("sv-ble", "")
        if sv_ble == "1":
            mappings["sv-ble"] = ":BLEKeyDetected"
        elif sv_ble == "0":
            mappings["sv-ble"] = ":BLEKeyNotDetected"

        return mappings

    def query_rule_chain(self, rule_id: str) -> str:
        """
        Return a human-readable rule chain string for the given ruleId.

        Format:
            [T_1_2] Disable跳转至Enable
              前提: :ReadyEnableDisable
              结论: → :ReadyEnableEnable
              来源: rules_model.ttl#ruleT_1_2
        """
        graph = self._require_graph()
        ns = self.ns

        sparql = """
        SELECT ?rule ?labelZh ?commentZh ?fromState ?toState
        WHERE {
            ?rule rdf:type :TransitionRule .
            ?rule :ruleId ?id .
            FILTER(str(?id) = ?targetId)
            OPTIONAL { ?rule rdfs:label ?labelZh FILTER(lang(?labelZh) = "zh") . }
            OPTIONAL { ?rule rdfs:comment ?commentZh FILTER(lang(?commentZh) = "zh") . }
            OPTIONAL { ?rule :fromState ?fromState . }
            OPTIONAL { ?rule :toState ?toState . }
        }
        """
        from rdflib import Literal as RDFLiteral
        results = list(graph.query(
            sparql,
            initNs={"rdf": RDF, "rdfs": RDFS, "": ns},
            initBindings={"targetId": RDFLiteral(rule_id)},
        ))

        if not results:
            return f"[{rule_id}] 规则未找到"

        row = results[0]
        label_zh = str(row.labelZh) if row.labelZh else rule_id
        comment_zh = str(row.commentZh) if row.commentZh else ""
        from_state = str(row.fromState).split("#")[-1] if row.fromState else "?"
        to_state = str(row.toState).split("#")[-1] if row.toState else "?"
        rule_uri = str(row.rule) if row.rule else ""
        local_name = rule_uri.split("#")[-1] if "#" in rule_uri else f"rule{rule_id}"

        lines = [
            f"[{rule_id}] {label_zh}",
            f"  前提: :{from_state}",
            f"  结论: → :{to_state}",
        ]
        if comment_zh:
            lines.append(f"  说明: {comment_zh}")
        lines.append(f"  来源: rules_model.ttl#{local_name}")
        return "\n".join(lines)
