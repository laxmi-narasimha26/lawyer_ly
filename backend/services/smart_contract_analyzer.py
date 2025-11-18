"""
Smart Contract Analysis and Blockchain Legal Tools
Analyzes Solidity contracts for legal compliance and security issues
"""
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SecurityIssue:
    """Security issue found in smart contract"""
    severity: str  # critical, high, medium, low
    title: str
    description: str
    line_number: Optional[int]
    recommendation: str


@dataclass
class LegalCompliance:
    """Legal compliance check result"""
    aspect: str
    compliant: bool
    details: str
    recommendations: List[str]


@dataclass
class ContractAnalysisResult:
    """Complete smart contract analysis result"""
    contract_name: str
    language: str
    security_issues: List[SecurityIssue]
    legal_compliance: List[LegalCompliance]
    gas_optimization: List[str]
    best_practices: List[str]
    overall_score: float
    summary: str


class SmartContractAnalyzer:
    """
    Analyzes smart contracts for:
    - Security vulnerabilities
    - Legal compliance issues
    - Gas optimization opportunities
    - Best practice violations
    """

    def __init__(self):
        # Common vulnerability patterns
        self.vulnerability_patterns = {
            "reentrancy": r"\.call\.value\(|\.transfer\(|\.send\(",
            "unchecked_send": r"\.send\([^)]+\)(?!\s*require)",
            "tx_origin": r"tx\.origin",
            "delegatecall": r"delegatecall\(",
            "selfdestruct": r"selfdestruct\(",
            "timestamp_dependency": r"block\.timestamp|now",
            "integer_overflow": r"(?<!Safe)Math\s*\+|-|\*",
        }

    async def analyze_solidity_contract(
        self,
        contract_code: str,
        contract_name: Optional[str] = None
    ) -> ContractAnalysisResult:
        """
        Analyze Solidity smart contract

        Args:
            contract_code: Solidity source code
            contract_name: Optional contract name

        Returns:
            Comprehensive analysis result
        """
        logger.info(f"Analyzing smart contract: {contract_name or 'unnamed'}")

        # Extract contract name if not provided
        if not contract_name:
            match = re.search(r'contract\s+(\w+)', contract_code)
            contract_name = match.group(1) if match else "UnnamedContract"

        # Run analysis tasks
        security_issues = await self._check_security(contract_code)
        legal_compliance = await self._check_legal_compliance(contract_code)
        gas_optimization = await self._check_gas_optimization(contract_code)
        best_practices = await self._check_best_practices(contract_code)

        # Calculate overall score
        overall_score = self._calculate_score(
            security_issues,
            legal_compliance,
            gas_optimization,
            best_practices
        )

        # Generate summary
        summary = self._generate_summary(
            contract_name,
            security_issues,
            legal_compliance,
            overall_score
        )

        logger.info(f"Contract analysis complete. Score: {overall_score:.1f}/100")

        return ContractAnalysisResult(
            contract_name=contract_name,
            language="Solidity",
            security_issues=security_issues,
            legal_compliance=legal_compliance,
            gas_optimization=gas_optimization,
            best_practices=best_practices,
            overall_score=overall_score,
            summary=summary
        )

    async def _check_security(self, code: str) -> List[SecurityIssue]:
        """Check for security vulnerabilities"""

        issues = []

        # Check for reentrancy
        if re.search(self.vulnerability_patterns["reentrancy"], code):
            # Check if proper reentrancy guard exists
            if "ReentrancyGuard" not in code and "nonReentrant" not in code:
                issues.append(SecurityIssue(
                    severity="critical",
                    title="Potential Reentrancy Vulnerability",
                    description="Contract uses external calls without reentrancy protection",
                    line_number=None,
                    recommendation="Implement ReentrancyGuard or use Checks-Effects-Interactions pattern"
                ))

        # Check for tx.origin usage
        if re.search(self.vulnerability_patterns["tx_origin"], code):
            issues.append(SecurityIssue(
                severity="high",
                title="tx.origin Used for Authentication",
                description="Using tx.origin for authentication can be exploited",
                line_number=None,
                recommendation="Use msg.sender instead of tx.origin"
            ))

        # Check for unchecked send
        if re.search(self.vulnerability_patterns["unchecked_send"], code):
            issues.append(SecurityIssue(
                severity="high",
                title="Unchecked Send Return Value",
                description="send() return value not checked",
                line_number=None,
                recommendation="Always check return value or use transfer() instead"
            ))

        # Check for delegatecall
        if re.search(self.vulnerability_patterns["delegatecall"], code):
            issues.append(SecurityIssue(
                severity="medium",
                title="Delegatecall Usage",
                description="delegatecall can be dangerous if not properly controlled",
                line_number=None,
                recommendation="Ensure delegatecall target is trusted and cannot be changed"
            ))

        # Check for timestamp dependency
        if re.search(self.vulnerability_patterns["timestamp_dependency"], code):
            issues.append(SecurityIssue(
                severity="medium",
                title="Timestamp Dependency",
                description="Contract relies on block.timestamp which miners can manipulate",
                line_number=None,
                recommendation="Avoid using timestamp for critical logic or add safety margins"
            ))

        # Check for integer overflow (if not using SafeMath)
        if re.search(r'\+|-|\*', code) and "SafeMath" not in code and "pragma solidity \^0\.[0-7]" in code:
            issues.append(SecurityIssue(
                severity="high",
                title="Potential Integer Overflow",
                description="Arithmetic operations without SafeMath in Solidity <0.8",
                line_number=None,
                recommendation="Use SafeMath library or upgrade to Solidity 0.8+"
            ))

        return issues

    async def _check_legal_compliance(self, code: str) -> List[LegalCompliance]:
        """Check legal compliance aspects"""

        compliance_checks = []

        # Check for access control
        has_access_control = any(pattern in code for pattern in ["onlyOwner", "AccessControl", "Ownable"])
        compliance_checks.append(LegalCompliance(
            aspect="Access Control",
            compliant=has_access_control,
            details="Contract should have proper access control for regulatory compliance",
            recommendations=[] if has_access_control else [
                "Implement role-based access control",
                "Use OpenZeppelin's AccessControl or Ownable"
            ]
        ))

        # Check for pause mechanism
        has_pause = "pause" in code.lower() or "Pausable" in code
        compliance_checks.append(LegalCompliance(
            aspect="Emergency Controls",
            compliant=has_pause,
            details="Ability to pause contract in emergencies",
            recommendations=[] if has_pause else [
                "Implement pausable pattern for emergency situations",
                "Use OpenZeppelin's Pausable"
            ]
        ))

        # Check for upgrade capability
        has_upgradeable = any(pattern in code for pattern in ["Proxy", "upgradeable", "UUPSUpgradeable"])
        compliance_checks.append(LegalCompliance(
            aspect="Upgradeability",
            compliant=True,  # Optional feature
            details="Contract upgradeability for bug fixes and compliance updates",
            recommendations=[] if has_upgradeable else [
                "Consider using upgradeable proxy pattern",
                "Use OpenZeppelin's UUPS or Transparent Proxy"
            ]
        ))

        # Check for events/logging
        has_events = "event " in code and "emit " in code
        compliance_checks.append(LegalCompliance(
            aspect="Audit Trail",
            compliant=has_events,
            details="Events for transaction logging and compliance auditing",
            recommendations=[] if has_events else [
                "Add events for all state-changing operations",
                "Emit events for audit trail compliance"
            ]
        ))

        # Check for KYC/AML considerations (for financial contracts)
        is_financial = any(pattern in code for pattern in ["transfer", "Token", "ERC20"])
        if is_financial:
            has_kyc = any(pattern in code for pattern in ["whitelist", "blacklist", "KYC", "accredited"])
            compliance_checks.append(LegalCompliance(
                aspect="KYC/AML Compliance",
                compliant=has_kyc,
                details="KYC/AML controls for financial contracts",
                recommendations=[] if has_kyc else [
                    "Implement whitelist/blacklist for KYC compliance",
                    "Add checks for accredited investors if required",
                    "Consider jurisdiction-specific requirements"
                ]
            ))

        return compliance_checks

    async def _check_gas_optimization(self, code: str) -> List[str]:
        """Check for gas optimization opportunities"""

        optimizations = []

        # Check for storage optimization
        if "uint256" in code and ("uint8" not in code and "uint16" not in code):
            optimizations.append("Consider using smaller uint types (uint8, uint16) where possible to save gas")

        # Check for constant/immutable
        if "public" in code and "constant" not in code and "immutable" not in code:
            optimizations.append("Use 'constant' or 'immutable' for variables that don't change")

        # Check for uncached array length
        if re.search(r'for\s*\([^)]*\.length', code):
            optimizations.append("Cache array length in loops to save gas")

        # Check for memory vs calldata
        if re.search(r'function\s+\w+\([^)]*memory\s+\w+\[\]', code):
            optimizations.append("Use 'calldata' instead of 'memory' for external function parameters")

        # Check for ++i vs i++
        if "i++" in code or "j++" in code:
            optimizations.append("Use ++i instead of i++ in loops to save gas")

        return optimizations

    async def _check_best_practices(self, code: str) -> List[str]:
        """Check for best practice violations"""

        violations = []

        # Check for Solidity version
        if not re.search(r'pragma solidity \^0\.[8-9]', code):
            violations.append("Update to Solidity 0.8+ for built-in overflow protection")

        # Check for license identifier
        if "SPDX-License-Identifier" not in code:
            violations.append("Add SPDX license identifier")

        # Check for NatSpec comments
        if not re.search(r'///|/\*\*', code):
            violations.append("Add NatSpec documentation for functions and contracts")

        # Check for constructor
        if "contract " in code and "constructor(" not in code:
            violations.append("Consider adding constructor for initialization")

        # Check for interface usage
        if "function " in code and "interface " not in code and "is " not in code:
            violations.append("Consider defining interfaces for better code organization")

        return violations

    def _calculate_score(
        self,
        security_issues: List[SecurityIssue],
        legal_compliance: List[LegalCompliance],
        gas_optimization: List[str],
        best_practices: List[str]
    ) -> float:
        """Calculate overall contract score (0-100)"""

        score = 100.0

        # Deduct for security issues
        for issue in security_issues:
            if issue.severity == "critical":
                score -= 20
            elif issue.severity == "high":
                score -= 10
            elif issue.severity == "medium":
                score -= 5
            else:
                score -= 2

        # Deduct for legal non-compliance
        non_compliant = sum(1 for c in legal_compliance if not c.compliant)
        score -= non_compliant * 5

        # Minor deductions for optimizations and best practices
        score -= len(gas_optimization) * 1
        score -= len(best_practices) * 1

        return max(0.0, min(100.0, score))

    def _generate_summary(
        self,
        contract_name: str,
        security_issues: List[SecurityIssue],
        legal_compliance: List[LegalCompliance],
        score: float
    ) -> str:
        """Generate analysis summary"""

        critical_count = sum(1 for i in security_issues if i.severity == "critical")
        high_count = sum(1 for i in security_issues if i.severity == "high")
        non_compliant = sum(1 for c in legal_compliance if not c.compliant)

        summary = f"Smart Contract Analysis for {contract_name}:\n"
        summary += f"Overall Score: {score:.1f}/100\n"
        summary += f"Security: {critical_count} critical, {high_count} high severity issues\n"
        summary += f"Legal Compliance: {len(legal_compliance) - non_compliant}/{len(legal_compliance)} aspects compliant"

        return summary


# Global instance
smart_contract_analyzer = SmartContractAnalyzer()
