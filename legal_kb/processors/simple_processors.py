"""
Simplified processors for token-aware ingestion
"""
import re
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class SupremeCourtJudgmentProcessor:
    """Simplified Supreme Court judgment processor"""
    
    def process_judgment_text(self, text: str, source_file: str) -> Optional[Dict]:
        """Process judgment text and extract metadata"""
        try:
            # Clean the text
            cleaned_text = self._clean_judgment_text(text)
            
            # Extract basic metadata
            metadata = self._extract_metadata(cleaned_text, source_file)
            
            return {
                'content': cleaned_text,
                'title': metadata.get('title', 'Supreme Court Judgment'),
                'source_file': source_file,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process judgment: {e}")
            return None
    
    def _clean_judgment_text(self, text: str) -> str:
        """Clean judgment text"""
        # Remove common headers/footers
        text = re.sub(r'SUPREME COURT OF INDIA.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'\[.*?\]', '', text)  # Remove bracketed metadata
        
        # Fix hyphenated line breaks
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    def _extract_metadata(self, text: str, source_file: str) -> Dict:
        """Extract metadata from judgment text"""
        metadata = {
            'source_file': source_file,
            'document_type': 'judgment',
            'court': 'Supreme Court of India'
        }
        
        # Try to extract case title from filename or text
        filename = Path(source_file).stem
        if filename:
            metadata['filename'] = filename
        
        # Try to extract year from filename
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            metadata['year'] = int(year_match.group(1))
        
        # Try to extract case title from text (first few lines)
        lines = text.split('\n')[:10]
        for line in lines:
            if len(line.strip()) > 20 and not line.strip().isdigit():
                metadata['title'] = line.strip()[:200]  # First meaningful line as title
                break
        
        return metadata

class BNSProcessor:
    """Simplified BNS processor"""
    
    def process_bns_text(self, text: str, source_file: str) -> Optional[Dict]:
        """Process BNS text and extract metadata"""
        try:
            # Clean the text
            cleaned_text = self._clean_bns_text(text)
            
            # Extract basic metadata
            metadata = self._extract_metadata(cleaned_text, source_file)
            
            return {
                'content': cleaned_text,
                'title': metadata.get('title', 'Bharatiya Nyaya Sanhita'),
                'source_file': source_file,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process BNS text: {e}")
            return None
    
    def _clean_bns_text(self, text: str) -> str:
        """Clean BNS text"""
        # Remove page numbers and headers
        text = re.sub(r'Page \d+.*?\n', '', text)
        text = re.sub(r'THE GAZETTE OF INDIA.*?\n', '', text, flags=re.IGNORECASE)
        
        # Fix formatting
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_metadata(self, text: str, source_file: str) -> Dict:
        """Extract metadata from BNS text"""
        metadata = {
            'source_file': source_file,
            'document_type': 'statute',
            'act': 'BNS',
            'year': 2023
        }
        
        # Try to extract title
        lines = text.split('\n')[:5]
        for line in lines:
            if 'bharatiya nyaya sanhita' in line.lower() or 'bns' in line.lower():
                metadata['title'] = line.strip()[:200]
                break
        
        return metadata