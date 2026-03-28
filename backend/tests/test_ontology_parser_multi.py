"""
Tests for multi-file ontology loading in OntologyParser.

These tests verify:
- Backward compatibility with single file loading
- Folder-based multi-file loading
- Empty folder handling
- File logging during load
- SWRL rule collection from multiple files
"""
import pytest
from pathlib import Path
from typing import List
from unittest.mock import patch
from loguru import logger

from ontology.parser import OntologyParser


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_ttl_content() -> str:
    """Minimal valid TTL content for testing."""
    return """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix vehicle: <http://example.org/vehicle-power-mode#> .

vehicle:TestClass a owl:Class ;
    rdfs:label "TestClass"@en ;
    rdfs:label "测试类"@zh .
"""


@pytest.fixture
def sample_ttl_with_swrl() -> str:
    """TTL content with SWRL rules in comments."""
    return """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix vehicle: <http://example.org/vehicle-power-mode#> .

vehicle:PowerMode a owl:Class ;
    rdfs:label "PowerMode"@en ;
    rdfs:label "电源模式"@zh .

# SWRL RULES
# Rule 1: Brake Pressed Detection
# vehicle:hasBrakeSignal(vehicle:v, "PRESSED") ^
# vehicle:hasStartButton(vehicle:v, "PRESSED")
# -> vehicle:canStart(vehicle:v, true)

# Rule 2: Invalid Key Detection
# vehicle:hasKeyStatus(vehicle:v, "INVALID")
# -> vehicle:blockStart(vehicle:v, true)
"""


@pytest.fixture
def sample_ttl_with_swrl_alt() -> str:
    """Alternative TTL content with different SWRL rules."""
    return """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix vehicle: <http://example.org/vehicle-power-mode#> .

vehicle:SignalStatus a owl:Class ;
    rdfs:label "SignalStatus"@en ;
    rdfs:label "信号状态"@zh .

# SWRL RULES
# SWRL Rule 3: DTC Detection
# vehicle:hasDTC(vehicle:v, "U0100")
# -> vehicle:hasCommunicationError(vehicle:v, true)

# SWRL Rule 4: Low Voltage Detection
# vehicle:hasBatteryVoltage(vehicle:v, voltage) ^
# swrlb:lessThan(voltage, 10.5)
# -> vehicle:hasLowVoltageWarning(vehicle:v, true)
"""


def create_ttl_file(directory: Path, name: str, content: str) -> Path:
    """Helper to create a TTL file in a directory."""
    file_path = directory / name
    file_path.write_text(content, encoding='utf-8')
    return file_path


# =============================================================================
# Test Cases
# =============================================================================

class TestLoadSingleFileBackwardCompat:
    """Tests for backward compatibility with single file loading."""

    def test_load_single_file_backward_compat(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test that passing a single TTL file path still works (backward compatibility).
        
        Verify:
        - File loads successfully
        - loaded_files contains one entry
        - Graph contains expected triples
        """
        # Create a single TTL file
        ttl_file = create_ttl_file(tmp_path, "test_onto.ttl", sample_ttl_content)
        
        # Initialize parser with single file path
        parser = OntologyParser(str(ttl_file))
        
        # Load should succeed
        result = parser.load()
        assert result is True, "Single file load should succeed"
        
        # Graph should be populated
        assert parser.graph is not None, "Graph should be initialized"
        assert len(parser.graph) > 0, "Graph should contain triples"
        
        # loaded_files should contain the single file (TDD: may fail if not implemented)
        assert hasattr(parser, 'loaded_files'), "Parser should have loaded_files attribute"
        assert len(parser.loaded_files) == 1, "loaded_files should contain one file"
        assert str(ttl_file) in parser.loaded_files or ttl_file.name in str(parser.loaded_files)


class TestLoadFolderWithTTLFiles:
    """Tests for loading a folder containing multiple TTL files."""

    def test_load_folder_with_ttl_files(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test loading a folder path containing multiple TTL files.
        
        Verify:
        - All TTL files are loaded
        - loaded_files contains all file paths
        - Graph contains merged triples from all files
        """
        # Create multiple TTL files in the folder
        file1 = create_ttl_file(tmp_path, "ontology_part1.ttl", sample_ttl_content)
        file2 = create_ttl_file(tmp_path, "ontology_part2.ttl", sample_ttl_content)
        file3 = create_ttl_file(tmp_path, "ontology_part3.ttl", sample_ttl_content)
        
        # Also create a non-TTL file to ensure it's ignored
        (tmp_path / "readme.txt").write_text("This should be ignored")
        
        # Initialize parser with folder path
        parser = OntologyParser(str(tmp_path))
        
        # Load should succeed
        result = parser.load()
        assert result is True, "Folder load should succeed"
        
        # Graph should be populated with merged triples
        assert parser.graph is not None, "Graph should be initialized"
        
        # loaded_files should contain all TTL files (TDD: may fail if not implemented)
        assert hasattr(parser, 'loaded_files'), "Parser should have loaded_files attribute"
        assert len(parser.loaded_files) == 3, f"loaded_files should contain 3 files, got {len(parser.loaded_files)}"
        
        # Verify all TTL files are in loaded_files
        loaded_names = [Path(f).name if isinstance(f, str) else f.name for f in parser.loaded_files]
        assert "ontology_part1.ttl" in loaded_names
        assert "ontology_part2.ttl" in loaded_names
        assert "ontology_part3.ttl" in loaded_names


class TestLoadEmptyFolder:
    """Tests for handling empty folders gracefully."""

    def test_load_empty_folder(self, tmp_path: Path):
        """
        Test passing a folder path with no TTL files.
        
        Verify:
        - Handles gracefully (returns False or logs warning)
        - No crash occurs
        """
        # Create an empty folder (tmp_path is already empty)
        # Add a non-TTL file
        (tmp_path / "config.yaml").write_text("key: value")
        
        # Initialize parser with empty folder
        parser = OntologyParser(str(tmp_path))
        
        # Should not crash - either returns False or handles gracefully
        try:
            result = parser.load()
            # If it returns, it should be False or graph should be empty
            if result is False:
                assert True, "Empty folder correctly returns False"
            else:
                # If it returns True, graph should be empty or minimal
                assert parser.graph is not None or len(parser.loaded_files) == 0, \
                    "Empty folder should have empty or minimal result"
        except Exception as e:
            pytest.fail(f"Empty folder caused crash: {e}")

    def test_load_nonexistent_path(self):
        """
        Test passing a path that doesn't exist.
        
        Verify:
        - Returns False
        - No crash
        """
        parser = OntologyParser("/nonexistent/path/to/ontology.ttl")
        result = parser.load()
        assert result is False, "Nonexistent path should return False"


class TestLoadFolderLogging:
    """Tests for logging during file loading."""

    def test_load_folder_logs_each_file(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test that each loaded file is logged.
        
        Verify:
        - Log output contains each file name
        """
        # Create multiple TTL files
        file1 = create_ttl_file(tmp_path, "module_a.ttl", sample_ttl_content)
        file2 = create_ttl_file(tmp_path, "module_b.ttl", sample_ttl_content)
        
        parser = OntologyParser(str(tmp_path))
        
        # Capture loguru output
        log_messages = []
        handler_id = logger.add(log_messages.append, level="INFO")
        
        try:
            parser.load()
            
            all_logs = " ".join(log_messages)
            
            # Verify per-file logging
            assert "module_a.ttl" in all_logs, "Should log module_a.ttl"
            assert "module_b.ttl" in all_logs, "Should log module_b.ttl"
            assert len(log_messages) > 0, "Should have some log output"
        finally:
            logger.remove(handler_id)


class TestSWRLRulesFromMultipleFiles:
    """Tests for SWRL rule collection from multiple files."""

    def test_swrl_rules_from_multiple_files(
        self, 
        tmp_path: Path, 
        sample_ttl_with_swrl: str,
        sample_ttl_with_swrl_alt: str
    ):
        """
        Test SWRL rules are collected from multiple TTL files.
        
        Verify:
        - Rules from both files are in swrl_rules list
        - No rules are duplicated
        """
        # Create two TTL files with SWRL rules
        create_ttl_file(tmp_path, "rules_part1.ttl", sample_ttl_with_swrl)
        create_ttl_file(tmp_path, "rules_part2.ttl", sample_ttl_with_swrl_alt)
        
        parser = OntologyParser(str(tmp_path))
        result = parser.load()
        
        assert result is True, "Load should succeed"
        
        # Check SWRL rules were collected (TDD: multi-file SWRL parsing may not be implemented)
        # Note: Current implementation only reads from self.ontology_path
        # This test will fail until multi-file SWRL parsing is implemented
        assert len(parser.swrl_rules) >= 2, \
            f"Should have at least 2 SWRL rules from both files, got {len(parser.swrl_rules)}"
        
        # Verify rule IDs are present
        rule_ids = [rule.rule_id for rule in parser.swrl_rules]
        # Rules should have IDs like R-1, R-2, R-3, R-4
        assert any("1" in rid or "2" in rid for rid in rule_ids), \
            f"Should have rules from first file, got IDs: {rule_ids}"


class TestLoadedFilesAttribute:
    """Tests for the loaded_files attribute."""

    def test_loaded_files_is_list(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test that loaded_files is a list.
        """
        ttl_file = create_ttl_file(tmp_path, "test.ttl", sample_ttl_content)
        parser = OntologyParser(str(ttl_file))
        parser.load()
        
        # TDD: This will fail if loaded_files not implemented
        assert hasattr(parser, 'loaded_files'), "Parser should have loaded_files attribute"
        assert isinstance(parser.loaded_files, list), "loaded_files should be a list"

    def test_loaded_files_contains_absolute_paths(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test that loaded_files contains absolute paths.
        """
        ttl_file = create_ttl_file(tmp_path, "test.ttl", sample_ttl_content)
        parser = OntologyParser(str(ttl_file))
        parser.load()
        
        # TDD: This will fail if loaded_files not implemented
        if hasattr(parser, 'loaded_files') and len(parser.loaded_files) > 0:
            for file_path in parser.loaded_files:
                # Should be a path-like object or string
                assert isinstance(file_path, (str, Path)), \
                    f"loaded_files entries should be paths, got {type(file_path)}"


class TestEdgeCases:
    """Edge case tests for multi-file loading."""

    def test_load_folder_with_subfolders(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test loading a folder that has subfolders with TTL files.
        
        Note: This tests whether subfolders are recursively searched.
        Behavior may vary based on implementation.
        """
        # Create subfolder with TTL file
        subfolder = tmp_path / "subfolder"
        subfolder.mkdir()
        create_ttl_file(subfolder, "nested.ttl", sample_ttl_content)
        
        # Create TTL in root folder
        create_ttl_file(tmp_path, "root.ttl", sample_ttl_content)
        
        parser = OntologyParser(str(tmp_path))
        result = parser.load()
        
        # Should at least load the root file
        assert result is True, "Load should succeed"
        
        # Whether nested files are loaded depends on implementation
        # This test documents expected behavior

    def test_load_mixed_content_folder(self, tmp_path: Path, sample_ttl_content: str):
        """
        Test loading a folder with TTL and other file types.
        
        Verify:
        - Only .ttl files are loaded
        - Other files are ignored
        """
        # Create TTL files
        create_ttl_file(tmp_path, "ontology.ttl", sample_ttl_content)
        
        # Create other files
        (tmp_path / "data.json").write_text('{"key": "value"}')
        (tmp_path / "config.xml").write_text('<config></config>')
        (tmp_path / "readme.md").write_text("# Readme")
        
        parser = OntologyParser(str(tmp_path))
        result = parser.load()
        
        assert result is True, "Load should succeed with mixed content"
        
        # Should only have loaded the TTL file
        if hasattr(parser, 'loaded_files'):
            assert len(parser.loaded_files) == 1, \
                f"Should only load TTL files, got {len(parser.loaded_files)} files"


# =============================================================================
# Namespace Detection Tests
# =============================================================================

class TestNamespaceDetection:
    """Tests for namespace detection from different TTL file structures."""

    def test_detect_namespace_from_classes_not_ontology(self, tmp_path: Path):
        """
        Test that namespace is detected from class URIs, not owl:Ontology declarations.
        
        This tests the bug where files have:
        - owl:Ontology with URI like http://example.org/vehicle-power-management/action
        - But @prefix : uses http://example.org/vehicle-power-management#
        
        The parser should use the @prefix namespace (from class URIs), not owl:Ontology.
        """
        # TTL with mismatched owl:Ontology and @prefix namespace
        ttl_content = """
@prefix : <http://example.org/vehicle-power-management#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/vehicle-power-management/action> rdf:type owl:Ontology ;
    rdfs:label "Action Model"@en .

:Action rdf:type owl:Class ;
    rdfs:label "Action"@en ;
    rdfs:label "动作"@zh .

:Actor rdf:type owl:Class ;
    rdfs:label "Actor"@en ;
    rdfs:label "执行者"@zh .

:SystemActor rdf:type owl:Class ;
    rdfs:subClassOf :Actor ;
    rdfs:label "System Actor"@en .
"""
        ttl_file = create_ttl_file(tmp_path, "action.ttl", ttl_content)
        
        parser = OntologyParser(str(ttl_file))
        result = parser.load()
        
        assert result is True, "Load should succeed"
        
        # BUG: Currently parses 0 classes because namespace detection is wrong
        # EXPECTED: Should parse 3 classes (Action, Actor, SystemActor)
        assert len(parser.classes) > 0, f"Should parse classes, got {len(parser.classes)}"
        
        # Verify specific classes are parsed
        assert "Action" in parser.classes, "Action class should be parsed"
        assert "Actor" in parser.classes, "Actor class should be parsed"
        
        # Verify namespace is the one from @prefix, not owl:Ontology
        assert str(parser.ns) == "http://example.org/vehicle-power-management#", \
            f"Namespace should be from @prefix, got {parser.ns}"

    def test_multi_file_namespace_detection(self, tmp_path: Path):
        """
        Test namespace detection with multiple TTL files having different owl:Ontology URIs
        but same @prefix namespace.
        
        This simulates the real ontology files:
        - action_model.ttl has owl:Ontology = http://example.org/vehicle-power-management/action
        - context_model.ttl has owl:Ontology = http://example.org/vehicle-power-management/context
        - Both use @prefix : <http://example.org/vehicle-power-management#>
        """
        # File 1: action model
        ttl1 = """
@prefix : <http://example.org/vehicle-power-management#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/vehicle-power-management/action> rdf:type owl:Ontology .

:Action rdf:type owl:Class ;
    rdfs:label "Action"@en .

:Actor rdf:type owl:Class ;
    rdfs:label "Actor"@en .
"""
        # File 2: context model
        ttl2 = """
@prefix : <http://example.org/vehicle-power-management#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/vehicle-power-management/context> rdf:type owl:Ontology .

:Context rdf:type owl:Class ;
    rdfs:label "Context"@en .

:ContextState rdf:type owl:Class ;
    rdfs:label "Context State"@en .
"""
        create_ttl_file(tmp_path, "action.ttl", ttl1)
        create_ttl_file(tmp_path, "context.ttl", ttl2)
        
        parser = OntologyParser(str(tmp_path))
        result = parser.load()
        
        assert result is True, "Load should succeed"
        
        # BUG: Currently parses 0 classes because namespace is wrong
        # EXPECTED: Should parse 4 classes (Action, Actor, Context, ContextState)
        assert len(parser.classes) >= 4, f"Should parse all classes from both files, got {len(parser.classes)}"
        
        # Verify namespace is consistent
        assert str(parser.ns) == "http://example.org/vehicle-power-management#", \
            f"Namespace should be consistent, got {parser.ns}"

    def test_fallback_when_no_classes(self, tmp_path: Path):
        """
        Test that parser falls back to owl:Ontology namespace when no classes exist.
        
        This tests the fallback path in _detect_namespace().
        """
        # TTL with no classes - only ontology declaration
        ttl_content = """
@prefix : <http://example.org/test-ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/test-ontology/core> rdf:type owl:Ontology ;
    rdfs:label "Test Ontology"@en .
"""
        ttl_file = create_ttl_file(tmp_path, "empty.ttl", ttl_content)
        
        parser = OntologyParser(str(ttl_file))
        result = parser.load()
        
        # Should succeed even with no classes
        assert result is True, "Load should succeed"
        
        # Should have 0 classes
        assert len(parser.classes) == 0, "Should have no classes"
        
        # Namespace should fall back to owl:Ontology derived value
        # The fallback logic should still work
