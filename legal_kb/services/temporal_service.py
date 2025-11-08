"""
Temporal Validity Service for Legal Knowledge Base

Handles temporal filtering, as-on date extraction, and BNS ⇄ legacy IPC/CrPC mapping.
"""

import re
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TemporalContext:
    """Represents temporal context extracted from a query"""
    as_on_date: date
    is_explicit: bool  # True if user explicitly mentioned a date
    original_query: str
    temporal_keywords: List[str]


@dataclass
class LegacyMapping:
    """Represents mapping between BNS and legacy IPC/CrPC sections"""
    bns_section: str
    legacy_section: str
    legacy_act: str  # 'IPC' or 'CrPC'
    description: str
    effective_from: date
    notes: Optional[str] = None


class TemporalService:
    """Service for handling temporal validity and as-on date reasoning"""
    
    def __init__(self):
        self.bns_effective_date = date(2024, 7, 1)
        self.legacy_mappings = self._initialize_legacy_mappings()
        
        # Temporal keywords for date extraction
        self.temporal_patterns = [
            (r'as\s+on\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})', 'as_on'),
            (r'as\s+of\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})', 'as_of'),
            (r'on\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})', 'on_date'),
            (r'in\s+(\d{4})', 'year_only'),
            (r'during\s+(\d{4})', 'year_only'),
            (r'before\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})', 'before'),
            (r'after\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})', 'after'),
        ]
        
        # Relative date keywords
        self.relative_keywords = {
            'current': 0,
            'today': 0,
            'now': 0,
            'present': 0,
            'latest': 0,
            'recent': 0,
        }
    
    def _initialize_legacy_mappings(self) -> Dict[str, LegacyMapping]:
        """Initialize BNS to IPC/CrPC mappings"""
        mappings = {}
        
        # Key BNS to IPC mappings (sample - expand as needed)
        legacy_map = [
            ("147", "392", "IPC", "Robbery"),
            ("303", "378", "IPC", "Theft"),
            ("318", "420", "IPC", "Cheating"),
            ("103", "302", "IPC", "Murder"),
            ("101", "300", "IPC", "Murder (definition)"),
            ("115", "304", "IPC", "Culpable homicide not amounting to murder"),
            ("64", "354", "IPC", "Assault or criminal force to woman with intent to outrage her modesty"),
            ("70", "376", "IPC", "Rape"),
        ]
        
        for bns_sec, ipc_sec, act, desc in legacy_map:
            key = f"BNS:{bns_sec}"
            mappings[key] = LegacyMapping(
                bns_section=f"BNS:2023:Sec:{bns_sec}",
                legacy_section=f"{act}:1860:Sec:{ipc_sec}" if act == "IPC" else f"{act}:1973:Sec:{ipc_sec}",
                legacy_act=act,
                description=desc,
                effective_from=self.bns_effective_date,
                notes=f"BNS Section {bns_sec} replaces {act} Section {ipc_sec}"
            )
            
            # Reverse mapping
            reverse_key = f"{act}:{ipc_sec}"
            mappings[reverse_key] = LegacyMapping(
                bns_section=f"BNS:2023:Sec:{bns_sec}",
                legacy_section=f"{act}:1860:Sec:{ipc_sec}" if act == "IPC" else f"{act}:1973:Sec:{ipc_sec}",
                legacy_act=act,
                description=desc,
                effective_from=self.bns_effective_date,
                notes=f"{act} Section {ipc_sec} replaced by BNS Section {bns_sec} from July 1, 2024"
            )
        
        return mappings
    
    def extract_temporal_context(self, query: str) -> TemporalContext:
        """
        Extract temporal context from user query
        
        Args:
            query: User's legal query
            
        Returns:
            TemporalContext with as-on date and metadata
        """
        query_lower = query.lower()
        temporal_keywords = []
        as_on_date = date.today()  # Default to current date
        is_explicit = False
        
        # Check for explicit date patterns
        for pattern, keyword_type in self.temporal_patterns:
            match = re.search(pattern, query_lower)
            if match:
                date_str = match.group(1)
                temporal_keywords.append(keyword_type)
                
                try:
                    # Parse date
                    if keyword_type == 'year_only':
                        # For year-only, use December 31 of that year
                        year = int(date_str)
                        as_on_date = date(year, 12, 31)
                    else:
                        # Try different date formats
                        for fmt in ['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d']:
                            try:
                                as_on_date = datetime.strptime(date_str, fmt).date()
                                break
                            except ValueError:
                                continue
                    
                    is_explicit = True
                    logger.info(f"Extracted explicit date: {as_on_date} from query")
                    break
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse date '{date_str}': {e}")
        
        # Check for relative keywords
        if not is_explicit:
            for keyword in self.relative_keywords:
                if keyword in query_lower:
                    temporal_keywords.append(keyword)
                    # All relative keywords map to current date
                    as_on_date = date.today()
                    break
        
        return TemporalContext(
            as_on_date=as_on_date,
            is_explicit=is_explicit,
            original_query=query,
            temporal_keywords=temporal_keywords
        )
    
    def should_use_bns(self, as_on_date: date) -> bool:
        """
        Determine if BNS should be used based on as-on date
        
        Args:
            as_on_date: Reference date for legal query
            
        Returns:
            True if BNS is applicable, False if legacy IPC/CrPC should be used
        """
        return as_on_date >= self.bns_effective_date
    
    def map_legacy_to_bns(self, legacy_reference: str) -> Optional[LegacyMapping]:
        """
        Map legacy IPC/CrPC reference to BNS equivalent
        
        Args:
            legacy_reference: Legacy section reference (e.g., "IPC 378", "Section 378 IPC")
            
        Returns:
            LegacyMapping if found, None otherwise
        """
        # Normalize reference
        legacy_reference = legacy_reference.upper().strip()
        
        # Extract section number and act
        patterns = [
            r'(IPC|CRPC)\s+(\d+)',
            r'SECTION\s+(\d+)\s+(IPC|CRPC)',
            r'SEC\.?\s+(\d+)\s+(IPC|CRPC)',
            r'(\d+)\s+(IPC|CRPC)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, legacy_reference)
            if match:
                groups = match.groups()
                if groups[0].isdigit():
                    section, act = groups[0], groups[1]
                else:
                    act, section = groups[0], groups[1]
                
                key = f"{act}:{section}"
                mapping = self.legacy_mappings.get(key)
                
                if mapping:
                    logger.info(f"Mapped {legacy_reference} to {mapping.bns_section}")
                    return mapping
        
        logger.warning(f"No mapping found for legacy reference: {legacy_reference}")
        return None
    
    def map_bns_to_legacy(self, bns_section: str) -> Optional[LegacyMapping]:
        """
        Map BNS section to legacy IPC/CrPC equivalent
        
        Args:
            bns_section: BNS section reference (e.g., "BNS 147", "Section 147 BNS")
            
        Returns:
            LegacyMapping if found, None otherwise
        """
        # Normalize reference
        bns_section = bns_section.upper().strip()
        
        # Extract section number
        patterns = [
            r'BNS\s+(\d+)',
            r'SECTION\s+(\d+)\s+BNS',
            r'SEC\.?\s+(\d+)\s+BNS',
            r'(\d+)\s+BNS',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, bns_section)
            if match:
                section = match.group(1)
                key = f"BNS:{section}"
                mapping = self.legacy_mappings.get(key)
                
                if mapping:
                    logger.info(f"Mapped {bns_section} to {mapping.legacy_section}")
                    return mapping
        
        logger.warning(f"No mapping found for BNS section: {bns_section}")
        return None
    
    def get_applicable_sections(self, query: str, temporal_context: TemporalContext) -> Dict[str, any]:
        """
        Determine which legal sections are applicable based on temporal context
        
        Args:
            query: User's legal query
            temporal_context: Extracted temporal context
            
        Returns:
            Dictionary with applicable sections and routing information
        """
        use_bns = self.should_use_bns(temporal_context.as_on_date)
        
        result = {
            'as_on_date': temporal_context.as_on_date.isoformat(),
            'use_bns': use_bns,
            'applicable_act': 'BNS' if use_bns else 'IPC',
            'mappings': [],
            'routing_notes': []
        }
        
        # Check for legacy references in query
        if not use_bns:
            # Before BNS effective date - use IPC/CrPC
            result['routing_notes'].append(
                f"Query date {temporal_context.as_on_date} is before BNS effective date "
                f"({self.bns_effective_date}). Using IPC/CrPC provisions."
            )
        else:
            # After BNS effective date - check for legacy references
            legacy_patterns = [r'IPC\s+\d+', r'SECTION\s+\d+\s+IPC', r'\d+\s+IPC']
            for pattern in legacy_patterns:
                if re.search(pattern, query.upper()):
                    result['routing_notes'].append(
                        "Query contains legacy IPC reference. Mapping to BNS equivalent."
                    )
                    break
        
        return result
    
    def create_temporal_filter_sql(self, as_on_date: date, table_alias: str = 'd') -> Tuple[str, List]:
        """
        Create SQL WHERE clause for temporal filtering
        
        Args:
            as_on_date: Reference date for filtering
            table_alias: Table alias in SQL query
            
        Returns:
            Tuple of (SQL WHERE clause, parameters list)
        """
        # For statutes: effective_from <= as_on_date AND (effective_to IS NULL OR effective_to > as_on_date)
        # For cases: decision_date <= as_on_date
        
        sql_clause = f"""
            (
                ({table_alias}.document_type = 'statute' AND 
                 ({table_alias}.metadata->>'effective_from')::date <= %s AND
                 (({table_alias}.metadata->>'effective_to') IS NULL OR 
                  ({table_alias}.metadata->>'effective_to')::date > %s))
                OR
                ({table_alias}.document_type IN ('judgment', 'bns') AND
                 ({table_alias}.metadata->>'decision_date')::date <= %s)
            )
        """
        
        params = [as_on_date, as_on_date, as_on_date]
        
        return sql_clause, params
    
    def format_temporal_disclaimer(self, temporal_context: TemporalContext) -> str:
        """
        Create disclaimer text for temporal context
        
        Args:
            temporal_context: Temporal context from query
            
        Returns:
            Formatted disclaimer string
        """
        if temporal_context.is_explicit:
            return (
                f"**Legal analysis as on {temporal_context.as_on_date.strftime('%B %d, %Y')}**\n\n"
                f"This answer reflects the law as it stood on the specified date. "
                f"Legal provisions may have changed since then."
            )
        else:
            return (
                f"**Legal analysis as on {temporal_context.as_on_date.strftime('%B %d, %Y')}** (current date)\n\n"
                f"This answer reflects the current state of the law."
            )


# Singleton instance
_temporal_service = None


def get_temporal_service() -> TemporalService:
    """Get singleton instance of TemporalService"""
    global _temporal_service
    if _temporal_service is None:
        _temporal_service = TemporalService()
    return _temporal_service
