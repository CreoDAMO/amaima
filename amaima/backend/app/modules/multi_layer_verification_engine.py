"""
AMAIMA Part V - Multi-Layer Verification Engine
Comprehensive output validation with DARPA security integration
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any, Callable
from datetime import datetime
import re
import ast
import json
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class VerificationLevel(Enum):
    """Verification strictness levels"""
    NONE = 0
    BASIC = 1
    STANDARD = 2
    STRICT = 3
    PARANOID = 4


class ConfidenceLevel(Enum):
    """Confidence tiers for verification results"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ToolResult:
    """Tool execution result"""
    tool_name: str
    parameters: Dict[str, Any]
    success: bool
    output: Any
    error: Optional[str]
    timestamp: datetime
    duration_ms: float


@dataclass
class VerificationResult:
    """Complete verification result"""
    is_verified: bool
    confidence: float
    confidence_level: ConfidenceLevel
    layer_results: Dict[str, Dict[str, Any]]
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    cross_references: Dict[str, Any]
    security_scan: Optional[Dict[str, Any]]
    timestamp: datetime


@dataclass
class VerificationConfig:
    """Verification configuration"""
    level: VerificationLevel
    enabled_layers: List[str]
    confidence_threshold: float = 0.7
    enable_security_scan: bool = True
    enable_llm_critique: bool = True
    hallucination_threshold: float = 0.3
    repetition_threshold: float = 0.3
    code_execution_timeout: float = 5.0


class SchemaValidator:
    """Schema and type validation"""
    
    def __init__(self):
        self.type_mapping = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "list": list,
            "dict": dict
        }
    
    def validate(self, output: Any, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate output against schema
        
        Args:
            output: Output to validate
            schema: Expected schema definition
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if schema.get("required"):
            for field_name in schema["required"]:
                if field_name not in output:
                    errors.append(f"Missing required field: {field_name}")
        
        if "properties" in schema:
            for field_name, field_schema in schema["properties"].items():
                if field_name in output:
                    field_value = output[field_name]
                    field_errors = self._validate_field(field_value, field_schema)
                    errors.extend(field_errors)
        
        return len(errors) == 0, errors
    
    def _validate_field(self, value: Any, schema: Dict[str, Any]) -> List[str]:
        """Validate individual field"""
        errors = []
        
        if "type" in schema:
            expected_type = self.type_mapping.get(schema["type"])
            if expected_type and not isinstance(value, expected_type):
                errors.append(f"Field type mismatch: expected {schema['type']}, got {type(value).__name__}")
        
        if "min" in schema and isinstance(value, (int, float)):
            if value < schema["min"]:
                errors.append(f"Value {value} below minimum {schema['min']}")
        
        if "max" in schema and isinstance(value, (int, float)):
            if value > schema["max"]:
                errors.append(f"Value {value} above maximum {schema['max']}")
        
        if "pattern" in schema and isinstance(value, str):
            if not re.match(schema["pattern"], value):
                errors.append(f"Value '{value}' does not match pattern {schema['pattern']}")
        
        return errors


class PlausibilityChecker:
    """Plausibility and coherence validation"""
    
    def __init__(self):
        self.numeric_domains = {
            "temperature": {"min": -273.15, "max": 1000},
            "percentage": {"min": 0, "max": 100},
            "coordinates": {"min": -180, "max": 180},
            "date_year": {"min": 1900, "max": 2100},
            "currency": {"min": 0, "max": 1e12},
            "probability": {"min": 0, "max": 1},
            "file_size": {"min": 0, "max": 1e12},
            "memory_mb": {"min": 0, "max": 1e6},
            "latency_ms": {"min": 0, "max": 60000},
            "accuracy": {"min": 0, "max": 100}
        }
        
        self.hallucination_patterns = [
            r"as an ai( language model)?",
            r"my (knowledge|training cut-off|cutoff)",
            r"i (cannot|don't|can't) (access|provide|verify)",
            r"based on (my )?(training )?(data|knowledge)",
            r"(sorry|apologies)(,| )?(but|to say)",
            r"i (must|should) (inform|clarify|note)",
            r"please note that",
        ]
        
        self.dangerous_patterns = [
            r"import\s+os\b",
            r"import\s+sys\b",
            r"subprocess\.",
            r"os\.system",
            r"os\.popen",
            r"eval\s*\(",
            r"exec\s*\(",
            r"pickle\.loads",
            r"yaml\.load\s*\(",
            r"__import__\s*\(",
        ]
    
    def check(self, output: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Comprehensive plausibility checking
        
        Args:
            output: Text output to check
            context: Optional context for validation
            
        Returns:
            Dictionary with check results
        """
        results = {
            "is_plausible": True,
            "numeric_validations": [],
            "hallucination_flags": [],
            "repetition_issues": [],
            "code_safety": [],
            "confidence_impact": 0.0
        }
        
        numeric_results = self._check_numeric_values(output)
        results["numeric_validations"] = numeric_results
        
        hallucination_results = self._check_hallucinations(output)
        results["hallucination_flags"] = hallucination_results
        
        repetition_results = self._check_repetition(output)
        results["repetition_issues"] = repetition_results
        
        code_results = self._check_code_safety(output)
        results["code_safety"] = code_results
        
        confidence_impact = 0.0
        confidence_impact -= len([r for r in hallucination_results if r["detected"]]) * 0.15
        confidence_impact -= len([r for r in repetition_results if r["detected"]]) * 0.1
        confidence_impact -= len([r for r in code_results if r["detected"]]) * 0.2
        
        if not all(r["valid"] for r in numeric_results):
            confidence_impact -= 0.1
        
        results["confidence_impact"] = max(-0.5, min(0.0, confidence_impact))
        results["is_plausible"] = confidence_impact > -0.3
        
        return results
    
    def _check_numeric_values(self, output: str) -> List[Dict[str, Any]]:
        """Check numeric values for plausibility"""
        results = []
        number_pattern = r"(-?\d+\.?\d*)\s*(°[CFcfa-z]+|%|km|m|s|ms|°|USD|EUR|GBP|million|billion|trillion)?"
        
        for match in re.finditer(number_pattern, output):
            value = float(match.group(1))
            unit = match.group(2) or ""
            
            for domain, range_spec in self.numeric_domains.items():
                in_range = range_spec["min"] <= value <= range_spec["max"]
                results.append({
                    "value": value,
                    "unit": unit,
                    "domain": domain,
                    "valid": in_range,
                    "range": range_spec
                })
        
        return results
    
    def _check_hallucinations(self, output: str) -> List[Dict[str, Any]]:
        """Detect potential hallucination markers"""
        results = []
        output_lower = output.lower()
        
        for i, pattern in enumerate(self.hallucination_patterns):
            match = re.search(pattern, output_lower)
            results.append({
                "pattern": pattern,
                "detected": match is not None,
                "match": match.group(0) if match else None
            })
        
        return results
    
    def _check_repetition(self, output: str) -> List[Dict[str, Any]]:
        """Check for excessive repetition"""
        words = output.lower().split()
        if len(words) < 10:
            return []
        
        word_counts = Counter(words)
        total_words = len(words)
        
        repetitions = []
        for word, count in word_counts.items():
            if count > 1:
                ratio = count / total_words
                if ratio > 0.3:
                    repetitions.append({
                        "word": word,
                        "count": count,
                        "ratio": ratio,
                        "detected": ratio > 0.3
                    })
        
        return repetitions
    
    def _check_code_safety(self, output: str) -> List[Dict[str, Any]]:
        """Check for dangerous code patterns"""
        results = []
        
        for i, pattern in enumerate(self.dangerous_patterns):
            match = re.search(pattern, output)
            results.append({
                "pattern": pattern,
                "detected": match is not None,
                "match": match.group(0) if match else None,
                "severity": "high"
            })
        
        return results


class SecurityScanner:
    """DARPA-grade security scanning integration"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.scan_history: List[Dict] = []
        self.buttercup_available = False
        self.sweetbaby_available = False
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize DARPA security tools"""
        if not self.enabled:
            logger.info("Security scanner disabled")
            return
        
        try:
            from darpa_tools import buttercup, sweetbaby
            self.buttercup_available = True
            self.sweetbaby_available = True
            logger.info("DARPA security tools initialized")
        except ImportError:
            logger.warning("DARPA tools not available, using fallback security scanning")
    
    def scan(self, code: str, operation: str = "code_generation") -> Dict[str, Any]:
        """
        Security scan code for vulnerabilities
        
        Args:
            code: Code to scan
            operation: Type of operation
            
        Returns:
            Security scan results
        """
        result = {
            "vulnerabilities": [],
            "risk_score": 0.0,
            "scan_time": datetime.now().isoformat(),
            "tools_used": [],
            "auto_patches": []
        }
        
        if self.buttercup_available:
            try:
                from darpa_tools.buttercup import scan_code
                vulnerabilities = scan_code(code)
                result["vulnerabilities"] = vulnerabilities
                result["tools_used"].append("buttercup")
            except Exception as e:
                logger.error(f"Buttercup scan failed: {e}")
        
        fallback_scan = self._fallback_scan(code)
        result["vulnerabilities"].extend(fallback_scan)
        
        risk_score = 0.0
        for vuln in result["vulnerabilities"]:
            severity_map = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}
            risk_score += severity_map.get(vuln.get("severity", "low"), 0.3)
        
        result["risk_score"] = min(risk_score, 1.0)
        
        if self.sweetbaby_available and result["vulnerabilities"]:
            try:
                from darpa_tools.sweetbaby import auto_patch
                patched_code, patches = auto_patch(code, result["vulnerabilities"])
                result["auto_patches"] = patches
                result["patched_code"] = patched_code
            except Exception as e:
                logger.error(f"Auto-patch failed: {e}")
        
        self.scan_history.append(result)
        
        return result
    
    def _fallback_scan(self, code: str) -> List[Dict[str, Any]]:
        """Fallback security scan when DARPA tools unavailable"""
        vulnerabilities = []
        
        dangerous_patterns = [
            (r"os\.system\s*\(", "Command injection via os.system", "high"),
            (r"subprocess\.", "Command injection via subprocess", "high"),
            (r"eval\s*\(", "Code injection via eval", "critical"),
            (r"exec\s*\(", "Code injection via exec", "critical"),
            (r"pickle\.loads?", "Insecure deserialization", "high"),
            (r"yaml\.load\s*\(", "YAML deserialization vulnerability", "medium"),
            (r"sql\s+injection", "SQL injection vulnerability", "r"shellcritical"),
            (=True", "Shell injection vulnerability", "high"),
            (r"password\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password", "medium"),
            (r"api[_-]?key\s*=\s*[\"'][^\"']+[\"']", "Hardcoded API key", "high"),
        ]
        
        for pattern, description, severity in dangerous_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_no = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    "type": description,
                    "severity": severity,
                    "line": line_no,
                    "pattern": pattern,
                    "auto_patchable": True
                })
        
        return vulnerabilities


class CodeExecutionVerifier:
    """Safe code execution verification"""
    
    def __init__(self):
        self.allowed_functions = {
            'abs', 'min', 'max', 'sum', 'len', 'range', 'round', 'floor', 'ceil',
            'sqrt', 'log', 'exp', 'sin', 'cos', 'tan', 'pi', 'e', 'pow', 'gcd',
            'isqrt', 'factorial', 'degrees', 'radians'
        }
        self.math_execution_count = 0
    
    def verify_math(self, expression: str, expected_result: float,
                    tolerance: float = 0.01) -> Dict[str, Any]:
        """
        Verify mathematical expressions
        
        Args:
            expression: Mathematical expression
            expected_result: Expected result
            tolerance: Relative tolerance for comparison
            
        Returns:
            Verification result
        """
        self.math_execution_count += 1
        
        try:
            import math
            result = eval(expression, {"__builtins__": {}}, {k: getattr(math, k) 
                                                           for k in self.allowed_functions 
                                                           if hasattr(math, k)})
            
            abs_error = abs(result - expected_result)
            rel_error = abs_error / abs(expected_result) if expected_result != 0 else abs_error
            
            return {
                "verified": rel_error <= tolerance,
                "expression": expression,
                "computed": result,
                "expected": expected_result,
                "relative_error": rel_error,
                "tolerance": tolerance
            }
        except Exception as e:
            return {
                "verified": False,
                "expression": expression,
                "error": str(e)
            }
    
    def verify_syntax(self, code: str) -> Dict[str, Any]:
        """Verify Python syntax"""
        try:
            ast.parse(code)
            return {
                "valid": True,
                "error": None
            }
        except SyntaxError as e:
            return {
                "valid": False,
                "error": str(e),
                "line": e.lineno,
                "offset": e.offset
            }


class LLMCritic:
    """LLM-based output critique"""
    
    def __init__(self, baseline_confidence: float = 0.7):
        self.baseline_confidence = baseline_confidence
    
    def critique(self, output: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Critique output for quality issues
        
        Args:
            output: Text output to critique
            context: Optional context
            
        Returns:
            Critique results
        """
        confidence_adjustment = 0.0
        issues = []
        
        length = len(output)
        if length < 20:
            confidence_adjustment -= 0.1
            issues.append("Response too short")
        elif length > 10000:
            confidence_adjustment -= 0.05
            issues.append("Response excessively long")
        
        if output.isupper():
            confidence_adjustment -= 0.1
            issues.append("All caps detected - may indicate low quality")
        
        if "sorry" in output.lower() or "apologies" in output.lower():
            confidence_adjustment -= 0.05
            issues.append("Excessive apologetic language")
        
        if re.search(r'\b(is|are|was|were)\s+(not|never|no)\s+\w+ing\b', output.lower()):
            confidence_adjustment -= 0.02
            issues.append("Double negative detected")
        
        return {
            "confidence": self.baseline_confidence + confidence_adjustment,
            "adjustment": confidence_adjustment,
            "issues": issues,
            "length": length,
            "is_reasonable_length": 50 < length < 10000
        }


class CrossReferenceValidator:
    """Multi-source cross-reference validation"""
    
    def __init__(self):
        self.validation_history: List[Dict] = []
    
    def validate_consensus(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate consensus across multiple sources
        
        Args:
            sources: List of validation sources
            
        Returns:
            Consensus validation result
        """
        if len(sources) < 2:
            return {
                "consensus_reached": True,
                "agreement_ratio": 1.0,
                "confidence": 0.8,
                "disagreements": [],
                "voting_record": sources
            }
        
        categorical_sources = [s for s in sources if isinstance(s.get("value"), str)]
        numeric_sources = [s for s in sources if isinstance(s.get("value"), (int, float))]
        
        result = {
            "consensus_reached": False,
            "agreement_ratio": 0.0,
            "confidence": 0.0,
            "disagreements": [],
            "voting_record": sources
        }
        
        if categorical_sources:
            value_counts = Counter(s.get("value") for s in categorical_sources)
            most_common_count = max(value_counts.values())
            agreement = most_common_count / len(categorical_sources)
            result["categorical_agreement"] = agreement
            result["majority_vote"] = value_counts.most_common(1)[0][0]
        
        if numeric_sources:
            values = [s.get("value") for s in numeric_sources]
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            std_dev = variance ** 0.5
            
            outliers = []
            for s in numeric_sources:
                z_score = abs(s.get("value") - mean_val) / std_dev if std_dev > 0 else 0
                if z_score > 2.0:
                    outliers.append({
                        "value": s.get("value"),
                        "z_score": z_score
                    })
            
            result["numeric_mean"] = mean_val
            result["numeric_std_dev"] = std_dev
            result["outliers"] = outliers
        
        result["agreement_ratio"] = (result.get("categorical_agreement", 1.0) + 
                                     (1.0 - len(outliers) / len(numeric_sources) if numeric_sources else 1.0)) / 2
        result["consensus_reached"] = result["agreement_ratio"] >= 0.7
        result["confidence"] = min(result["agreement_ratio"] * 1.2, 1.0)
        
        return result


class IntegratedVerificationEngine:
    """
    Main verification engine coordinating all validation layers
    """
    
    def __init__(, config: Optional[VerificationConfig] = None):
        self.config = config or VerificationConfig(
            level=VerificationLevel.STANDARD,
            enabled_layers=["schema", "plausibility", "cross_reference", "llm_critique"],
            confidence_threshold=0.7,
            enable_security_scan=True
        )
        
        self.schema_validator = SchemaValidator()
        self.plausibility_checker = PlausibilityChecker()
        self.security_scanner = SecurityScanner(enabled=self.config.enable_security_scan)
        self.code_verifier = CodeExecutionVerifier()
        self.llm_critic = LLMCritic()
        self.cross_validator = CrossReferenceValidator()
    
    def verify(self, output: Any, context: Optional[Dict] = None,
               tool_results: Optional[List[ToolResult]] = None) -> VerificationResult:
        """
        Main verification entry point
        
        Args:
            output: Output to verify
            context: Optional context
            tool_results: Optional tool execution results
            
        Returns:
            Complete verification result
        """
        layer_results = {}
        total_confidence = 1.0
        all_issues = []
        
        if "schema" in self.config.enabled_layers:
            if isinstance(output, dict) and context and context.get("expected_schema"):
                schema_valid, schema_errors = self.schema_validator.validate(
                    output, context["expected_schema"]
                )
                layer_results["schema"] = {
                    "passed": schema_valid,
                    "errors": schema_errors,
                    "confidence_impact": 0.0 if schema_valid else -0.15
                }
                if not schema_valid:
                    total_confidence -= 0.15
                    all_issues.extend([{"layer": "schema", "error": e} for e in schema_errors])
        
        if "plausibility" in self.config.enabled_layers:
            if isinstance(output, str):
                plausibility_results = self.plausibility_checker.check(output, context)
                layer_results["plausibility"] = plausibility_results
                total_confidence += plausibility_results.get("confidence_impact", 0)
                if not plausibility_results.get("is_plausible"):
                    issues = plausibility_results.get("hallucination_flags", []) + \
                            plausibility_results.get("repetition_issues", [])
                    all_issues.extend([{"layer": "plausibility", "issue": i} for i in issues if i.get("detected")])
        
        if "security" in self.config.enabled_layers and self.config.enable_security_scan:
            if isinstance(output, str) and len(output) > 50:
                is_code = any(keyword in output for keyword in ["def ", "class ", "import ", "from "])
                if is_code:
                    security_result = self.security_scanner.scan(output)
                    layer_results["security"] = {
                        "passed": security_result["risk_score"] < 0.5,
                        "risk_score": security_result["risk_score"],
                        "vulnerabilities": security_result["vulnerabilities"],
                        "confidence_impact": -security_result["risk_score"] * 0.3
                    }
                    total_confidence += layer_results["security"]["confidence_impact"]
                    all_issues.extend([
                        {"layer": "security", "vulnerability": v}
                        for v in security_result["vulnerabilities"]
                    ])
        
        if "cross_reference" in self.config.enabled_layers and tool_results:
            cross_result = self.cross_validator.validate_consensus([
                {"value": tr.output, "tool": tr.tool_name}
                for tr in tool_results if tr.success
            ])
            layer_results["cross_reference"] = cross_result
            total_confidence += (cross_result["confidence"] - 0.7) * 0.2
        
        if "llm_critique" in self.config.enabled_layers and self.config.enable_llm_critique:
            if isinstance(output, str):
                critique_result = self.llm_critic.critique(output, context)
                layer_results["llm_critique"] = critique_result
                total_confidence += (critique_result["confidence"] - self.llm_critic.baseline_confidence)
        
        total_confidence = max(0.0, min(1.0, total_confidence))
        
        if tool_results:
            historical_accuracy = self._calculate_historical_accuracy(tool_results)
            layer_results["historical"] = {"accuracy": historical_accuracy}
            total_confidence = total_confidence * 0.7 + historical_accuracy * 0.3
        
        recommendations = self._generate_recommendations(layer_results)
        
        return VerificationResult(
            is_verified=total_confidence >= self.config.confidence_threshold,
            confidence=total_confidence,
            confidence_level=self._get_confidence_level(total_confidence),
            layer_results=layer_results,
            issues=all_issues,
            recommendations=recommendations,
            cross_references=layer_results.get("cross_reference", {}),
            security_scan=layer_results.get("security", {}),
            timestamp=datetime.now()
        )
    
    def _calculate_historical_accuracy(self, tool_results: List[ToolResult]) -> float:
        """Calculate historical accuracy from tool results"""
        successful = [tr for tr in tool_results if tr.success]
        if not tool_results:
            return 0.7
        return len(successful) / len(tool_results)
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert numeric confidence to enum level"""
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.75:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.4:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW
    
    def _generate_recommendations(self, layer_results: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if not layer_results.get("schema", {}).get("passed", True):
            recommendations.append("ACCEPT: Schema validation passed with minor issues")
        
        if layer_results.get("plausibility", {}).get("confidence_impact", 0) < -0.1:
            recommendations.append("REVIEW: Plausibility checks detected potential hallucinations")
        
        security_risk = layer_results.get("security", {}).get("risk_score", 0)
        if security_risk > 0.5:
            recommendations.append("REJECT: High security risk detected in output")
        elif security_risk > 0.2:
            recommendations.append("REVIEW: Moderate security concerns - manual review recommended")
        
        consensus = layer_results.get("cross_reference", {}).get("consensus_reached", True)
        if not consensus:
            recommendations.append("REVIEW: Cross-reference validation found disagreements")
        
        if not recommendations:
            recommendations.append("ACCEPT: All verification layers passed")
        
        return recommendations
