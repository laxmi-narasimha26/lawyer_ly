"""
Deduplication and Boilerplate Removal Service
Removes duplicate content and boilerplate text before embedding
"""
import re
import hashlib
from typing import List, Dict, Set, Optional, Tuple
import logging
from collections import Counter
from difflib import SequenceMatcher

from ..models.legal_models import StatuteChunk, JudgmentChunk
from ..database.connection import get_db_manager

logger = logging.getLogger(__name__)

class DeduplicationService:
    """Service for removing duplicates and boilerplate text"""
    
    def __init__(self):
        self.known_hashes: Set[str] = set()
        self.boilerplate_patterns = self._initialize_boilerplate_patterns()
        self.similarity_threshold = 0.85  # 85% similarity threshold for near-duplicates
        
    def _initialize_boilerplate_patterns(self) -> List[re.Pattern]:
        """Initialize common boilerplate patterns to remove"""
        patterns = [
            # Page headers and footers
            re.compile(r'^page\s+\d+\s*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\d+\s*$', re.MULTILINE),  # Standalone page numbers
            re.compile(r'^www\.[a-z0-9.-]+\.com.*$', re.IGNORECASE | re.MULTILINE),
            
            # Court boilerplate
            re.compile(r'^supreme court reports.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^supreme court cases.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^scc online.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^printed for.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^copyright.*$', re.IGNORECASE | re.MULTILINE),
            
            # Legal document boilerplate
            re.compile(r'^bharatiya nyaya sanhita.*act.*2023.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^act no\.?\s+\d+\s+of\s+\d{4}.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^gazette of india.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^extraordinary.*part\s+ii.*$', re.IGNORECASE | re.MULTILINE),
            
            # OCR artifacts
            re.compile(r'^[^\w\s]*$', re.MULTILINE),  # Lines with only special characters
            re.compile(r'^\s*[|\\/_\-=+*#@$%^&(){}[\]<>?~`]+\s*$', re.MULTILINE),
            
            # Repeated headers
            re.compile(r'^(chapter|section|part)\s+\d+\s*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^table of contents.*$', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^index.*$', re.IGNORECASE | re.MULTILINE),
        ]
        
        return patterns
    
    async def remove_boilerplate(self, text: str) -> str:
        """Remove boilerplate text from document"""
        cleaned_text = text
        
        # Apply boilerplate removal patterns
        for pattern in self.boilerplate_patterns:
            cleaned_text = pattern.sub('', cleaned_text)
        
        # Remove excessive whitespace
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
        cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)
        
        # Remove very short lines (likely artifacts)
        lines = cleaned_text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip very short lines unless they contain important legal markers
            if len(line) < 3 and not re.match(r'^\d+\.?$', line):
                continue
            
            # Skip lines that are mostly special characters
            if len(re.sub(r'[^\w\s]', '', line)) < len(line) * 0.3:
                continue
            
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()
    
    async def detect_duplicates(self, chunks: List[Dict]) -> List[Dict]:
        """Detect and remove duplicate chunks"""
        unique_chunks = []
        seen_hashes = set()
        near_duplicate_groups = []
        
        # First pass: exact duplicates by hash
        for chunk in chunks:
            content_hash = self._compute_content_hash(chunk['text'])
            
            if content_hash not in seen_hashes:
                chunk['content_hash'] = content_hash
                unique_chunks.append(chunk)
                seen_hashes.add(content_hash)
            else:
                logger.debug(f"Removed exact duplicate chunk: {chunk.get('id', 'unknown')}")
        
        # Second pass: near-duplicates by similarity
        final_chunks = []
        processed_indices = set()
        
        for i, chunk in enumerate(unique_chunks):
            if i in processed_indices:
                continue
            
            # Find similar chunks
            similar_chunks = [chunk]
            similar_indices = {i}
            
            for j, other_chunk in enumerate(unique_chunks[i+1:], i+1):
                if j in processed_indices:
                    continue
                
                similarity = self._calculate_similarity(chunk['text'], other_chunk['text'])
                if similarity > self.similarity_threshold:
                    similar_chunks.append(other_chunk)
                    similar_indices.add(j)
            
            # If we found similar chunks, keep the best one
            if len(similar_chunks) > 1:
                best_chunk = self._select_best_chunk(similar_chunks)
                final_chunks.append(best_chunk)
                logger.debug(f"Merged {len(similar_chunks)} similar chunks into one")
            else:
                final_chunks.append(chunk)
            
            processed_indices.update(similar_indices)
        
        logger.info(f"Deduplication: {len(chunks)} -> {len(final_chunks)} chunks")
        return final_chunks
    
    def _compute_content_hash(self, text: str) -> str:
        """Compute normalized hash for content comparison"""
        # Normalize text for hashing
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        # Normalize texts
        norm1 = re.sub(r'\s+', ' ', text1.lower().strip())
        norm2 = re.sub(r'\s+', ' ', text2.lower().strip())
        
        # Use sequence matcher for similarity
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()
    
    def _select_best_chunk(self, similar_chunks: List[Dict]) -> Dict:
        """Select the best chunk from a group of similar chunks"""
        # Scoring criteria:
        # 1. Longer text (more complete)
        # 2. Better formatting (fewer artifacts)
        # 3. More metadata
        
        best_chunk = similar_chunks[0]
        best_score = self._score_chunk_quality(best_chunk)
        
        for chunk in similar_chunks[1:]:
            score = self._score_chunk_quality(chunk)
            if score > best_score:
                best_chunk = chunk
                best_score = score
        
        return best_chunk
    
    def _score_chunk_quality(self, chunk: Dict) -> float:
        """Score chunk quality for deduplication selection"""
        text = chunk['text']
        score = 0.0
        
        # Length score (longer is generally better)
        score += len(text) * 0.001
        
        # Completeness score (fewer truncation indicators)
        truncation_indicators = ['...', '[truncated]', '[continued]', '(contd.)']
        for indicator in truncation_indicators:
            if indicator.lower() in text.lower():
                score -= 10
        
        # Formatting score (fewer artifacts)
        artifact_patterns = [r'[^\w\s]{3,}', r'\s{3,}', r'\n{3,}']
        for pattern in artifact_patterns:
            matches = len(re.findall(pattern, text))
            score -= matches * 2
        
        # Metadata completeness
        if chunk.get('title'):
            score += 5
        if chunk.get('section'):
            score += 3
        if chunk.get('citations'):
            score += len(chunk['citations']) * 2
        
        return score
    
    async def remove_identical_headnotes(self, judgment_chunks: List[JudgmentChunk]) -> List[JudgmentChunk]:
        """Remove identical headnotes that appear in multiple judgments"""
        headnote_hashes = {}
        filtered_chunks = []
        
        for chunk in judgment_chunks:
            if chunk.section == 'Headnote':
                content_hash = self._compute_content_hash(chunk.text)
                
                if content_hash in headnote_hashes:
                    # Skip this duplicate headnote
                    logger.debug(f"Removed duplicate headnote from {chunk.id}")
                    continue
                else:
                    headnote_hashes[content_hash] = chunk.id
            
            filtered_chunks.append(chunk)
        
        return filtered_chunks
    
    async def detect_ocr_noise(self, text: str) -> Tuple[str, float]:
        """Detect and clean OCR noise, return cleaned text and confidence score"""
        original_length = len(text)
        cleaned_text = text
        
        # Common OCR error patterns
        ocr_fixes = {
            r'\bl\b': 'I',  # lowercase l mistaken for I
            r'\b0\b': 'O',  # zero mistaken for O in words
            r'rn': 'm',     # rn mistaken for m
            r'cl': 'd',     # cl mistaken for d
            r'vv': 'w',     # vv mistaken for w
            r'(?<=[a-z])1(?=[a-z])': 'l',  # 1 mistaken for l in middle of words
        }
        
        noise_indicators = 0
        
        for pattern, replacement in ocr_fixes.items():
            matches = len(re.findall(pattern, cleaned_text))
            if matches > 0:
                cleaned_text = re.sub(pattern, replacement, cleaned_text)
                noise_indicators += matches
        
        # Check for excessive special characters (OCR artifacts)
        special_char_ratio = len(re.findall(r'[^\w\s]', cleaned_text)) / len(cleaned_text) if cleaned_text else 0
        if special_char_ratio > 0.15:  # More than 15% special characters
            noise_indicators += 10
        
        # Calculate confidence (lower noise = higher confidence)
        confidence = max(0.0, 1.0 - (noise_indicators / original_length * 10))
        
        return cleaned_text, confidence
    
    async def validate_chunk_quality(self, chunk_text: str) -> Dict[str, float]:
        """Validate chunk quality and return quality metrics"""
        metrics = {
            'length_score': 0.0,
            'completeness_score': 0.0,
            'readability_score': 0.0,
            'legal_content_score': 0.0,
            'overall_score': 0.0
        }
        
        if not chunk_text or len(chunk_text.strip()) < 10:
            return metrics
        
        text = chunk_text.strip()
        
        # Length score (optimal range: 100-2000 characters)
        length = len(text)
        if 100 <= length <= 2000:
            metrics['length_score'] = 1.0
        elif length < 100:
            metrics['length_score'] = length / 100.0
        else:
            metrics['length_score'] = max(0.3, 2000 / length)
        
        # Completeness score (check for truncation indicators)
        truncation_indicators = ['...', '[truncated]', '[continued]', '(contd.)', 'see page']
        truncation_count = sum(1 for indicator in truncation_indicators if indicator.lower() in text.lower())
        metrics['completeness_score'] = max(0.0, 1.0 - truncation_count * 0.3)
        
        # Readability score (sentence structure, punctuation)
        sentences = re.split(r'[.!?]+', text)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        
        if 10 <= avg_sentence_length <= 30:  # Optimal sentence length
            metrics['readability_score'] = 1.0
        else:
            metrics['readability_score'] = max(0.3, 1.0 - abs(avg_sentence_length - 20) / 20.0)
        
        # Legal content score (presence of legal terminology)
        legal_terms = [
            'section', 'article', 'clause', 'proviso', 'explanation', 'illustration',
            'court', 'judgment', 'held', 'decided', 'appeal', 'petition',
            'plaintiff', 'defendant', 'appellant', 'respondent'
        ]
        
        legal_term_count = sum(1 for term in legal_terms if term.lower() in text.lower())
        metrics['legal_content_score'] = min(1.0, legal_term_count / 5.0)  # Normalize to 0-1
        
        # Overall score (weighted average)
        weights = {
            'length_score': 0.2,
            'completeness_score': 0.3,
            'readability_score': 0.2,
            'legal_content_score': 0.3
        }
        
        metrics['overall_score'] = sum(metrics[key] * weight for key, weight in weights.items())
        
        return metrics
    
    async def should_skip_embedding(self, chunk_text: str) -> Tuple[bool, str]:
        """Determine if chunk should be skipped for embedding"""
        quality_metrics = await self.validate_chunk_quality(chunk_text)
        
        # Skip if overall quality is too low
        if quality_metrics['overall_score'] < 0.3:
            return True, f"Low quality score: {quality_metrics['overall_score']:.2f}"
        
        # Skip if text is too short
        if len(chunk_text.strip()) < 20:
            return True, "Text too short"
        
        # Skip if mostly non-alphabetic characters
        alpha_ratio = len(re.findall(r'[a-zA-Z]', chunk_text)) / len(chunk_text) if chunk_text else 0
        if alpha_ratio < 0.5:
            return True, f"Low alphabetic content ratio: {alpha_ratio:.2f}"
        
        return False, "Quality check passed"

# Global deduplication service instance
dedup_service: Optional[DeduplicationService] = None

async def get_deduplication_service() -> DeduplicationService:
    """Get the global deduplication service instance"""
    global dedup_service
    if dedup_service is None:
        dedup_service = DeduplicationService()
    return dedup_service