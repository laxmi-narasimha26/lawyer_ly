"""
Text processing utilities for legal documents
"""
import re
import unicodedata
from typing import List, Dict, Optional

def normalize_unicode(text: str) -> str:
    """Normalize Unicode characters and fix broken ligatures"""
    # Normalize Unicode to NFC form
    text = unicodedata.normalize('NFC', text)
    
    # Fix common ligatures that may be broken in OCR
    ligature_fixes = {
        'ﬁ': 'fi',
        'ﬂ': 'fl',
        'ﬀ': 'ff',
        'ﬃ': 'ffi',
        'ﬄ': 'ffl',
        '–': '-',  # en dash to hyphen
        '—': '-',  # em dash to hyphen
        ''': "'",  # smart quote to straight quote
        ''': "'",
        '"': '"',
        '"': '"'
    }
    
    for ligature, replacement in ligature_fixes.items():
        text = text.replace(ligature, replacement)
    
    return text

def clean_legal_text(text: str) -> str:
    """Clean and standardize legal text"""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Fix common spacing issues around punctuation
    text = re.sub(r'\s+([,.;:])', r'\1', text)
    text = re.sub(r'([,.;:])\s*', r'\1 ', text)
    
    # Standardize section references
    text = re.sub(r'Sec\.\s*(\d+)', r'Section \1', text)
    text = re.sub(r'S\.\s*(\d+)', r'Section \1', text)
    
    # Fix paragraph numbering
    text = re.sub(r'^\s*\((\d+)\)\s*', r'(\1) ', text, flags=re.MULTILINE)
    
    # Remove multiple consecutive newlines
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    return text.strip()

def extract_legal_terms(text: str) -> List[str]:
    """Extract legal terminology from text"""
    legal_terms = []
    
    # Common legal term patterns
    patterns = [
        r'\b(?:section|sec\.?)\s+\d+\b',
        r'\b(?:article|art\.?)\s+\d+\b',
        r'\b(?:rule|r\.?)\s+\d+\b',
        r'\b(?:order|o\.?)\s+\d+\b',
        r'\bchapter\s+\d+\b',
        r'\bschedule\s+\d+\b',
        r'\b(?:sub-section|subsection)\s+\(\d+\)\b',
        r'\b(?:clause|cl\.?)\s+\([a-z]\)\b',
        r'\bproviso\b',
        r'\billustration\b',
        r'\bexplanation\b'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        legal_terms.extend(matches)
    
    return list(set(legal_terms))

def detect_citation_format(text: str) -> Dict[str, List[str]]:
    """Detect and extract different citation formats"""
    citations = {
        'case_citations': [],
        'statute_citations': [],
        'neutral_citations': []
    }
    
    # Case citation patterns
    case_patterns = [
        r'\b\d{4}\s+SCC\s+\d+',
        r'\b\d{4}\s+SCR\s+\(\d+\)\s+\d+',
        r'\bAIR\s+\d{4}\s+SC\s+\d+',
        r'\b\d{4}\s+\d+\s+SCC\s+\d+',
        r'\(\d{4}\)\s+\d+\s+SCC\s+\d+'
    ]
    
    for pattern in case_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        citations['case_citations'].extend(matches)
    
    # Neutral citation pattern
    neutral_pattern = r'\b\d{4}\s+SCC\s+OnLine\s+\w+\s+\d+'
    neutral_matches = re.findall(neutral_pattern, text, re.IGNORECASE)
    citations['neutral_citations'].extend(neutral_matches)
    
    # Statute citation patterns
    statute_patterns = [
        r'\bSection\s+\d+\s+of\s+[^.]+Act',
        r'\bArticle\s+\d+\s+of\s+the\s+Constitution',
        r'\bRule\s+\d+\s+of\s+[^.]+Rules'
    ]
    
    for pattern in statute_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        citations['statute_citations'].extend(matches)
    
    return citations

def chunk_by_sentences(text: str, max_chunk_size: int = 500) -> List[str]:
    """Chunk text by sentences while respecting max size"""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed max size
        if len(current_chunk) + len(sentence) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Sentence itself is too long, split it
                words = sentence.split()
                for word in words:
                    if len(current_chunk) + len(word) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = word
                        else:
                            # Single word too long, just add it
                            chunks.append(word)
                    else:
                        current_chunk += " " + word if current_chunk else word
        else:
            current_chunk += " " + sentence if current_chunk else sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def extract_section_title(text: str) -> Optional[str]:
    """Extract section title from legal text"""
    # Pattern for section titles in Indian legal documents
    patterns = [
        r'^\d+\.\s*(.+?)\.?\s*—\s*(.+)',  # "147. Robbery.—Definition"
        r'^\d+\.\s*(.+?)\.?\s*$',         # "147. Robbery."
        r'^Section\s+\d+\.\s*(.+?)\.?\s*—\s*(.+)',  # "Section 147. Robbery.—Definition"
    ]
    
    for pattern in patterns:
        match = re.match(pattern, text.strip(), re.MULTILINE)
        if match:
            if len(match.groups()) > 1:
                return match.group(2).strip()  # Return the part after —
            else:
                return match.group(1).strip()
    
    return None

def standardize_legal_language(text: str) -> str:
    """Standardize legal language and terminology"""
    # Common legal term standardizations
    standardizations = {
        r'\bwhoever\b': 'Whoever',
        r'\bwherever\b': 'Wherever',
        r'\bwhenever\b': 'Whenever',
        r'\bshall\b': 'shall',
        r'\bmay\b': 'may',
        r'\bprovided that\b': 'Provided that',
        r'\bprovided further that\b': 'Provided further that',
        r'\bnotwithstanding anything\b': 'Notwithstanding anything',
        r'\bsubject to\b': 'Subject to',
        r'\bin respect of\b': 'in respect of',
        r'\bwith respect to\b': 'with respect to'
    }
    
    for pattern, replacement in standardizations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text