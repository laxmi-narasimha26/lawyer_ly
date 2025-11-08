"""
Advanced hallucination detection system for Indian Legal AI Assistant
Implements sophisticated verification techniques to ensure legal accuracy
"""
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime

from config import settings

logger = structlog.get_logger(__name__)

class HallucinationRisk(Enum):
    """Risk levels for hallucination detection"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class VerificationResult:
    """Result of hallucination verification"""
    is_verified: bool
    risk_level: HallucinationRisk
    unsupported_claims: List[str]
    verification_notes: List[str]
    confidence_score: float

class HallucinationDetector:
    """
    Production-grade hallucination detection system
    
    Features:
    - Legal claim extraction and verification
    - Source-based fact checking
    - Legal keyword validation
    - Citation cross-verification
    - Risk assessment and scoring
    """
    
    def __init__(self):
        self.legal_claim_patterns = self._initialize_legal_patterns()
        self.verification_rules = self._initialize_verification_rules()
        self.legal_keywords = self._initialize_legal_keywords()
        
        logger.info("Hallucination detector initialized with legal verification rules")
    
    async def verify_response(
        self,
        response_text: str,
        citations: List[Dict[str, Any]],
        source_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Verify response for hallucinations and add appropriate disclaimers
        
        Args:
            response_text: Generated AI response
            citations: Extracted citations
            source_chunks: Source chunks used for generation
            
        Returns:
            Verified response with disclaimers if needed
        """
        try:
            # Extract legal claims from response
            legal_claims = self._extract_legal_claims(response_text)
            
            # Verify each claim against sources
            verification_result = await self._verify_claims_against_sources(
                legal_claims, source_chunks, citations
            )
            
            # Add disclaimers based on verification results
            verified_response = self._add_verification_disclaimers(
                response_text, verification_result
            )
            
            logger.info(
                "Hallucination verification completed",
                risk_level=verification_result.risk_level.value,
                unsupported_claims=len(verification_result.unsupported_claims),
                confidence_score=verification_result.confidence_score
            )
            
            return verified_response
            
        except Exception as e:
            logger.error("Hallucination verification failed", error=str(e), exc_info=True)
            # Add conservative disclaimer on error
            return self._add_conservative_disclaimer(response_text)
    
    def _extract_legal_claims(self, text: str) -> List[Dict[str, Any]]:
        """Extract legal claims that need verification"""
        claims = []
        
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            # Check if sentence contains legal claims
            claim_indicators = self._identify_claim_indicators(sentence)
            
            if claim_indicators:
                claims.append({
                    'text': sentence,
                    'position': i,
                    'indicators': claim_indicators,
                    'risk_factors': self._assess_claim_risk_factors(sentence)
                })
        
        return claims
    
    def _identify_claim_indicators(self, sentence: str) -> List[str]:
        """Identify indicators that suggest legal claims"""
        indicators = []
        sentence_lower = sentence.lower()
        
        # Definitive legal statements
        definitive_patterns = [
            r'\b(the|this)\s+(law|act|section|court|judgment)\s+(states?|holds?|provides?|establishes?)\b',
            r'\b(according\s+to|under|as\s+per)\s+(section|article|the\s+act)\b',
            r'\b(the\s+supreme\s+court|high\s+court)\s+(held|ruled|decided|observed)\b',
            r'\bis\s+(mandatory|prohibited|required|illegal|valid|invalid)\s+under\b',
            r'\b(shall|must|cannot|may\s+not)\s+.*(under|according\s+to)\b'
        ]
        
        for pattern in definitive_patterns:
            if re.search(pattern, sentence_lower):
                indicators.append('definitive_legal_statement')
                break
        
        # Case law references
        if re.search(r'\bin\s+the\s+case\s+of\b|\bthe\s+court\s+in\b', sentence_lower):
            indicators.append('case_law_reference')
        
        # Statutory references
        if re.search(r'\bsection\s+\d+|\barticle\s+\d+|\bunder\s+the\s+\w+\s+act\b', sentence_lower):
            indicators.append('statutory_reference')
        
        # Procedural claims
        if re.search(r'\bprocedure|process|filing|application|petition\b', sentence_lower):
            indicators.append('procedural_claim')
        
        # Quantitative claims
        if re.search(r'\b\d+\s+(days|months|years|percent|rupees)\b', sentence_lower):
            indicators.append('quantitative_claim')
        
        return indicators
    
    def _assess_claim_risk_factors(self, sentence: str) -> List[str]:
        """Assess risk factors for potential hallucination"""
        risk_factors = []
        sentence_lower = sentence.lower()
        
        # High-risk phrases
        high_risk_phrases = [
            'always', 'never', 'all cases', 'in every situation', 'without exception',
            'guaranteed', 'certainly', 'definitely will', 'impossible', 'absolutely'
        ]
        
        for phrase in high_risk_phrases:
            if phrase in sentence_lower:
                risk_factors.append('absolute_statement')
                break
        
        # Specific numbers without citations
        if re.search(r'\b\d+\s+(days|months|years|percent|rupees)\b', sentence_lower):
            if not re.search(r'\[doc\d+\]|\[\d+\]', sentence_lower):
                risk_factors.append('uncited_specific_number')
        
        # Recent developments claims
        recent_indicators = ['recently', 'latest', 'new', 'current', '2024', '2025']
        if any(indicator in sentence_lower for indicator in recent_indicators):
            risk_factors.append('recent_development_claim')
        
        # Complex legal interpretations
        complex_indicators = ['interpretation', 'implies', 'suggests', 'indicates', 'likely means']
        if any(indicator in sentence_lower for indicator in complex_indicators):
            risk_factors.append('complex_interpretation')
        
        return risk_factors
    
    async def _verify_claims_against_sources(
        self,
        claims: List[Dict[str, Any]],
        source_chunks: List[Dict[str, Any]],
        citations: List[Dict[str, Any]]
    ) -> VerificationResult:
        """Verify legal claims against provided sources"""
        
        unsupported_claims = []
        verification_notes = []
        total_risk_score = 0.0
        
        for claim in claims:
            claim_text = claim['text']
            risk_factors = claim['risk_factors']
            
            # Check if claim is supported by sources
            is_supported = await self._check_claim_support_enhanced(claim_text, source_chunks, citations)
            
            if not is_supported:
                unsupported_claims.append(claim_text)
                
                # Assess risk level based on claim characteristics
                claim_risk = self._calculate_claim_risk(claim, risk_factors)
                total_risk_score += claim_risk
                
                verification_notes.append(
                    f"Unsupported claim detected: {claim_text[:100]}..."
                )
                
                # Add specific legal keyword analysis
                legal_keywords_unsupported = self._analyze_legal_keywords_in_claim(claim_text, source_chunks)
                if legal_keywords_unsupported:
                    verification_notes.append(
                        f"Legal terms without source support: {', '.join(legal_keywords_unsupported)}"
                    )
        
        # Cross-check citations against knowledge base
        citation_verification_notes = await self._cross_check_citations(citations)
        verification_notes.extend(citation_verification_notes)
        
        # Calculate overall risk level
        if not claims:
            risk_level = HallucinationRisk.LOW
            confidence_score = 0.9
        else:
            avg_risk = total_risk_score / len(claims)
            risk_level = self._determine_risk_level(avg_risk, len(unsupported_claims), len(claims))
            confidence_score = max(0.1, 1.0 - (len(unsupported_claims) / len(claims)))
        
        return VerificationResult(
            is_verified=len(unsupported_claims) == 0,
            risk_level=risk_level,
            unsupported_claims=unsupported_claims,
            verification_notes=verification_notes,
            confidence_score=confidence_score
        )
    
    def _check_claim_support(
        self,
        claim_text: str,
        source_chunks: List[Dict[str, Any]],
        citations: List[Dict[str, Any]]
    ) -> bool:
        """Check if a claim is supported by source material"""
        
        # Extract key legal terms from claim
        claim_keywords = self._extract_legal_keywords(claim_text)
        
        # Check against source chunks
        for chunk in source_chunks:
            chunk_text = chunk.get('text', '').lower()
            
            # Simple keyword matching (can be enhanced with semantic similarity)
            keyword_matches = sum(1 for keyword in claim_keywords if keyword in chunk_text)
            
            # If significant keyword overlap, consider supported
            if keyword_matches >= len(claim_keywords) * 0.6:  # 60% keyword match threshold
                return True
        
        # Check if claim has proper citations
        claim_lower = claim_text.lower()
        has_citation = bool(re.search(r'\[doc\d+\]|\[\d+\]', claim_lower))
        
        if has_citation and citations:
            # If claim has citations and citations are verified, consider supported
            verified_citations = [c for c in citations if c.get('is_verified', False)]
            if verified_citations:
                return True
        
        return False
    
    async def _check_claim_support_enhanced(
        self,
        claim_text: str,
        source_chunks: List[Dict[str, Any]],
        citations: List[Dict[str, Any]]
    ) -> bool:
        """Enhanced claim verification with legal-specific analysis"""
        
        # Basic keyword matching
        if self._check_claim_support(claim_text, source_chunks, citations):
            return True
        
        # Enhanced legal term analysis
        legal_terms = self._extract_specific_legal_terms(claim_text)
        
        for chunk in source_chunks:
            chunk_text = chunk.get('text', '').lower()
            
            # Check for exact legal term matches
            exact_matches = sum(1 for term in legal_terms if term.lower() in chunk_text)
            
            # Check for case citation matches
            case_citations_in_claim = re.findall(r'\b\d{4}\s+\w+\s+\d+\b', claim_text)
            case_citations_in_chunk = re.findall(r'\b\d{4}\s+\w+\s+\d+\b', chunk_text)
            
            citation_matches = len(set(case_citations_in_claim) & set(case_citations_in_chunk))
            
            # Check for section references
            sections_in_claim = re.findall(r'\bsection\s+\d+[a-z]?\b', claim_text.lower())
            sections_in_chunk = re.findall(r'\bsection\s+\d+[a-z]?\b', chunk_text)
            
            section_matches = len(set(sections_in_claim) & set(sections_in_chunk))
            
            # If we have strong legal term matches, consider supported
            if exact_matches >= 2 or citation_matches >= 1 or section_matches >= 1:
                return True
        
        return False
    
    def _analyze_legal_keywords_in_claim(
        self,
        claim_text: str,
        source_chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """Analyze which legal keywords in claim lack source support"""
        
        legal_terms = self._extract_specific_legal_terms(claim_text)
        unsupported_terms = []
        
        for term in legal_terms:
            term_supported = False
            for chunk in source_chunks:
                if term.lower() in chunk.get('text', '').lower():
                    term_supported = True
                    break
            
            if not term_supported:
                unsupported_terms.append(term)
        
        return unsupported_terms
    
    async def _cross_check_citations(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Cross-check citations against knowledge base"""
        verification_notes = []
        
        for citation in citations:
            citation_text = citation.get('formatted_reference', '')
            source_name = citation.get('source_name', '')
            
            # Check for common citation format issues
            if not citation_text:
                verification_notes.append(f"Citation missing proper formatting: {source_name}")
                continue
            
            # Check for suspicious citation patterns
            if re.search(r'\b(unknown|untitled|document)\b', citation_text.lower()):
                verification_notes.append(f"Suspicious citation reference: {citation_text}")
            
            # Check for incomplete case citations
            if 'case' in citation.get('source_type', '').lower():
                if not re.search(r'\b\d{4}\b', citation_text):  # Missing year
                    verification_notes.append(f"Case citation missing year: {citation_text}")
                
                if not re.search(r'\bv\.?\s+\w+', citation_text.lower()):  # Missing versus
                    verification_notes.append(f"Case citation missing proper format: {citation_text}")
        
        return verification_notes
    
    def _extract_specific_legal_terms(self, text: str) -> List[str]:
        """Extract specific legal terms for enhanced verification"""
        legal_terms = []
        
        # Case names
        case_patterns = [
            r'\b[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+\b',
            r'\b[A-Z][a-z]+\s+vs\.?\s+[A-Z][a-z]+\b'
        ]
        
        for pattern in case_patterns:
            matches = re.findall(pattern, text)
            legal_terms.extend(matches)
        
        # Specific legal acts
        act_patterns = [
            r'\bIndian\s+Penal\s+Code\b',
            r'\bCode\s+of\s+Criminal\s+Procedure\b',
            r'\bIndian\s+Contract\s+Act\b',
            r'\bConstitution\s+of\s+India\b',
            r'\bIndian\s+Evidence\s+Act\b'
        ]
        
        for pattern in act_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            legal_terms.extend(matches)
        
        # Court names
        court_patterns = [
            r'\bSupreme\s+Court\s+of\s+India\b',
            r'\b\w+\s+High\s+Court\b',
            r'\bDistrict\s+Court\b'
        ]
        
        for pattern in court_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            legal_terms.extend(matches)
        
        # Legal procedures
        procedure_terms = [
            'writ petition', 'habeas corpus', 'mandamus', 'certiorari',
            'bail application', 'anticipatory bail', 'interim order',
            'stay order', 'injunction', 'appeal', 'revision'
        ]
        
        for term in procedure_terms:
            if term in text.lower():
                legal_terms.append(term)
        
        return list(set(legal_terms))  # Remove duplicates
    
    def _extract_legal_keywords(self, text: str) -> List[str]:
        """Extract legal keywords from text for matching"""
        keywords = []
        text_lower = text.lower()
        
        # Extract case names
        case_patterns = [
            r'\b[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+\b',
            r'\b[A-Z][a-z]+\s+vs\.?\s+[A-Z][a-z]+\b'
        ]
        
        for pattern in case_patterns:
            matches = re.findall(pattern, text)
            keywords.extend([match.lower() for match in matches])
        
        # Extract section/article references
        section_matches = re.findall(r'\bsection\s+\d+[a-z]?\b|\barticle\s+\d+[a-z]?\b', text_lower)
        keywords.extend(section_matches)
        
        # Extract act names
        act_matches = re.findall(r'\b\w+\s+act\b', text_lower)
        keywords.extend(act_matches)
        
        # Extract court names
        court_matches = re.findall(r'\bsupreme\s+court\b|\b\w+\s+high\s+court\b', text_lower)
        keywords.extend(court_matches)
        
        return list(set(keywords))  # Remove duplicates
    
    def _calculate_claim_risk(self, claim: Dict[str, Any], risk_factors: List[str]) -> float:
        """Calculate risk score for individual claim"""
        base_risk = 0.3  # Base risk for any legal claim
        
        # Add risk based on factors
        risk_multipliers = {
            'absolute_statement': 0.4,
            'uncited_specific_number': 0.3,
            'recent_development_claim': 0.2,
            'complex_interpretation': 0.2
        }
        
        for factor in risk_factors:
            base_risk += risk_multipliers.get(factor, 0.1)
        
        # Add risk based on claim indicators
        indicators = claim.get('indicators', [])
        if 'definitive_legal_statement' in indicators and not risk_factors:
            base_risk += 0.2  # Definitive statements without citations are risky
        
        return min(1.0, base_risk)  # Cap at 1.0
    
    def _determine_risk_level(
        self,
        avg_risk_score: float,
        unsupported_count: int,
        total_claims: int
    ) -> HallucinationRisk:
        """Determine overall risk level"""
        
        unsupported_ratio = unsupported_count / total_claims if total_claims > 0 else 0
        
        if avg_risk_score >= 0.8 or unsupported_ratio >= 0.5:
            return HallucinationRisk.CRITICAL
        elif avg_risk_score >= 0.6 or unsupported_ratio >= 0.3:
            return HallucinationRisk.HIGH
        elif avg_risk_score >= 0.4 or unsupported_ratio >= 0.1:
            return HallucinationRisk.MEDIUM
        else:
            return HallucinationRisk.LOW
    
    def _add_verification_disclaimers(
        self,
        response_text: str,
        verification_result: VerificationResult
    ) -> str:
        """Add appropriate disclaimers based on verification results"""
        
        # Build disclaimer based on risk level and specific issues
        disclaimer_parts = []
        
        if verification_result.risk_level == HallucinationRisk.LOW:
            # Low risk - minimal disclaimer
            disclaimer_parts.append("*Note: Please verify all legal information with current statutes and recent case law before relying on it for legal proceedings.*")
        
        elif verification_result.risk_level == HallucinationRisk.MEDIUM:
            # Medium risk - standard disclaimer
            disclaimer_parts.append("*Important: This response contains information that should be independently verified. Please consult current legal authorities and seek professional legal advice before making any legal decisions.*")
        
        elif verification_result.risk_level == HallucinationRisk.HIGH:
            # High risk - strong disclaimer
            disclaimer_parts.append("*⚠️ Caution: This response contains claims that could not be fully verified against the provided sources. Please independently verify all information with authoritative legal sources and consult qualified legal counsel.*")
        
        else:  # CRITICAL
            # Critical risk - very strong disclaimer
            disclaimer_parts.append("*🚨 Critical Notice: This response contains multiple unverified legal claims. Do not rely on this information for legal proceedings. Consult qualified legal counsel and verify all information against current, authoritative legal sources.*")
        
        # Add specific uncertainty indicators
        if verification_result.unsupported_claims:
            if len(verification_result.unsupported_claims) == 1:
                disclaimer_parts.append("*Uncertain Information: One claim in this response could not be verified against the provided sources.*")
            else:
                disclaimer_parts.append(f"*Uncertain Information: {len(verification_result.unsupported_claims)} claims in this response could not be verified against the provided sources.*")
        
        # Add confidence score if low
        if verification_result.confidence_score < 0.7:
            disclaimer_parts.append(f"*Confidence Level: {verification_result.confidence_score:.1%} - Consider seeking additional sources for verification.*")
        
        # Add specific verification notes for transparency
        if verification_result.verification_notes and verification_result.risk_level in [HallucinationRisk.HIGH, HallucinationRisk.CRITICAL]:
            disclaimer_parts.append("*Verification Issues Detected:*")
            for note in verification_result.verification_notes[:3]:  # Limit to first 3 notes
                disclaimer_parts.append(f"  - {note}")
        
        # Combine all disclaimer parts
        full_disclaimer = "\n\n" + "\n\n".join(disclaimer_parts)
        
        return response_text + full_disclaimer
    
    def _add_conservative_disclaimer(self, response_text: str) -> str:
        """Add conservative disclaimer when verification fails"""
        disclaimer = "\n\n*Note: The accuracy of this response could not be fully verified. Please consult current legal authorities and seek professional legal advice.*"
        return response_text + disclaimer
    
    def _initialize_legal_patterns(self) -> Dict[str, str]:
        """Initialize patterns for legal claim detection"""
        return {
            'definitive_statement': r'\b(is|are|must|shall|cannot|will|always|never)\s+',
            'case_reference': r'\bin\s+the\s+case\s+of\b|\bthe\s+court\s+held\b',
            'statutory_reference': r'\bunder\s+section\b|\baccording\s+to\s+the\s+act\b',
            'procedural_claim': r'\bthe\s+procedure\s+is\b|\bmust\s+file\b|\brequired\s+to\b',
            'quantitative_claim': r'\b\d+\s+(days|months|years|percent|rupees)\b'
        }
    
    def _initialize_verification_rules(self) -> Dict[str, Any]:
        """Initialize verification rules and thresholds"""
        return {
            'keyword_match_threshold': 0.6,
            'citation_required_for_specific_claims': True,
            'max_unsupported_ratio': 0.2,
            'confidence_threshold': 0.7
        }
    
    def _initialize_legal_keywords(self) -> Set[str]:
        """Initialize set of important legal keywords"""
        return {
            # Courts
            'supreme court', 'high court', 'district court', 'tribunal',
            
            # Legal concepts
            'jurisdiction', 'precedent', 'ratio decidendi', 'obiter dicta',
            'writ petition', 'habeas corpus', 'mandamus', 'certiorari',
            
            # Procedures
            'appeal', 'revision', 'review', 'bail', 'anticipatory bail',
            'interim order', 'stay order', 'injunction',
            
            # Acts and laws
            'constitution', 'ipc', 'crpc', 'cpc', 'contract act',
            'evidence act', 'limitation act', 'arbitration act',
            
            # Legal terms
            'plaintiff', 'defendant', 'petitioner', 'respondent',
            'appellant', 'appellee', 'judgment', 'order', 'decree'
        }
    
    def get_verification_statistics(
        self,
        verification_results: List[VerificationResult]
    ) -> Dict[str, Any]:
        """Get statistics about verification results"""
        if not verification_results:
            return {
                'total_verifications': 0,
                'average_confidence': 0.0,
                'risk_distribution': {},
                'verification_rate': 0.0
            }
        
        verified_count = sum(1 for r in verification_results if r.is_verified)
        avg_confidence = sum(r.confidence_score for r in verification_results) / len(verification_results)
        
        # Risk level distribution
        risk_distribution = {}
        for result in verification_results:
            risk_level = result.risk_level.value
            risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
        
        return {
            'total_verifications': len(verification_results),
            'verified_responses': verified_count,
            'verification_rate': verified_count / len(verification_results),
            'average_confidence': avg_confidence,
            'risk_distribution': risk_distribution
        }