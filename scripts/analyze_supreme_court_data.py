#!/usr/bin/env python3
"""
Analyze Supreme Court Data Structure
Examines downloaded Supreme Court judgments to understand structure for optimal chunking
"""

import os
import json
import zipfile
from pathlib import Path
from typing import List, Dict, Any
import PyPDF2
from io import BytesIO
import re

class SupremeCourtDataAnalyzer:
    def __init__(self, data_dir: str = "./data/supreme_court_judgments"):
        self.data_dir = Path(data_dir)
    
    def analyze_year_data(self, year: int, num_samples: int = 5) -> Dict[str, Any]:
        """Analyze data structure for a specific year"""
        year_dir = self.data_dir / str(year)
        english_zip = year_dir / "english.zip"
        metadata_zip = year_dir / "metadata.zip"
        
        analysis = {
            "year": year,
            "total_judgments": 0,
            "sample_judgments": [],
            "metadata_structure": {},
            "text_characteristics": {},
            "legal_structure_patterns": []
        }
        
        if not english_zip.exists() or not metadata_zip.exists():
            print(f"Required files not found for year {year}")
            return analysis
        
        try:
            # Get list of files
            with zipfile.ZipFile(english_zip, 'r') as eng_zip:
                pdf_files = [f for f in eng_zip.namelist() if f.endswith('.pdf')]
                analysis["total_judgments"] = len(pdf_files)
                
                print(f"Found {len(pdf_files)} judgments in {year}")
                
                # Analyze sample files
                sample_files = pdf_files[:num_samples]
                
                with zipfile.ZipFile(metadata_zip, 'r') as meta_zip:
                    for i, pdf_file in enumerate(sample_files):
                        print(f"Analyzing sample {i+1}: {pdf_file}")
                        
                        # Get metadata
                        base_name = pdf_file.replace('_EN.pdf', '')
                        metadata_file = f"{base_name}.json"
                        
                        metadata = {}
                        if metadata_file in meta_zip.namelist():
                            with meta_zip.open(metadata_file) as f:
                                metadata = json.load(f)
                        
                        # Extract PDF text
                        with eng_zip.open(pdf_file) as pdf_f:
                            pdf_content = pdf_f.read()
                            text = self.extract_text_from_pdf(pdf_content)
                        
                        # Analyze this judgment
                        judgment_analysis = self.analyze_judgment_structure(text, metadata)
                        judgment_analysis["pdf_file"] = pdf_file
                        judgment_analysis["metadata_file"] = metadata_file
                        
                        analysis["sample_judgments"].append(judgment_analysis)
                
                # Aggregate analysis
                analysis["metadata_structure"] = self.analyze_metadata_structure(analysis["sample_judgments"])
                analysis["text_characteristics"] = self.analyze_text_characteristics(analysis["sample_judgments"])
                analysis["legal_structure_patterns"] = self.identify_legal_patterns(analysis["sample_judgments"])
        
        except Exception as e:
            print(f"Error analyzing year {year}: {e}")
        
        return analysis
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text from PDF content"""
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                except Exception:
                    continue
            
            return text.strip()
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""
    
    def analyze_judgment_structure(self, text: str, metadata: Dict) -> Dict[str, Any]:
        """Analyze the structure of a single judgment"""
        analysis = {
            "text_length": len(text),
            "word_count": len(text.split()) if text else 0,
            "paragraph_count": len([p for p in text.split('\n\n') if p.strip()]) if text else 0,
            "has_legal_sections": False,
            "section_markers": [],
            "legal_elements": {},
            "metadata_fields": list(metadata.keys()) if metadata else []
        }
        
        if not text:
            return analysis
        
        # Look for legal section markers
        section_patterns = [
            (r'\bJUDGMENT\b', 'JUDGMENT'),
            (r'\bORDER\b', 'ORDER'),
            (r'\bHELD\s*:', 'HELD'),
            (r'\bRATIO\s*:', 'RATIO'),
            (r'\bFACTS\s*:', 'FACTS'),
            (r'\bISSUES?\s*:', 'ISSUES'),
            (r'\bDISCUSSION\s*:', 'DISCUSSION'),
            (r'\bCONCLUSION\s*:', 'CONCLUSION'),
            (r'\bDISPOSAL\s*:', 'DISPOSAL'),
            (r'\d+\.\s+', 'NUMBERED_SECTION'),
            (r'\([a-z]\)\s+', 'LETTERED_SUBSECTION')
        ]
        
        for pattern, name in section_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                analysis["section_markers"].append({
                    "type": name,
                    "count": len(matches),
                    "pattern": pattern
                })
                analysis["has_legal_sections"] = True
        
        # Look for legal elements
        legal_elements = {
            "case_citations": len(re.findall(r'\b\d{4}\s+\d+\s+SCC\s+\d+', text)),
            "section_references": len(re.findall(r'[Ss]ection\s+\d+', text)),
            "article_references": len(re.findall(r'[Aa]rticle\s+\d+', text)),
            "act_references": len(re.findall(r'\b\w+\s+Act,?\s+\d{4}', text)),
            "court_references": len(re.findall(r'Supreme Court|High Court|District Court', text, re.IGNORECASE)),
            "judge_names": len(re.findall(r'\bJ\.\b|\bCJI\b|Justice', text)),
            "legal_maxims": len(re.findall(r'\b(res judicata|stare decisis|ratio decidendi|obiter dicta)\b', text, re.IGNORECASE))
        }
        
        analysis["legal_elements"] = legal_elements
        
        return analysis
    
    def analyze_metadata_structure(self, sample_judgments: List[Dict]) -> Dict[str, Any]:
        """Analyze metadata structure across samples"""
        all_fields = set()
        field_frequency = {}
        
        for judgment in sample_judgments:
            for field in judgment["metadata_fields"]:
                all_fields.add(field)
                field_frequency[field] = field_frequency.get(field, 0) + 1
        
        return {
            "total_unique_fields": len(all_fields),
            "common_fields": [field for field, freq in field_frequency.items() if freq >= len(sample_judgments) * 0.8],
            "field_frequency": field_frequency,
            "all_fields": sorted(list(all_fields))
        }
    
    def analyze_text_characteristics(self, sample_judgments: List[Dict]) -> Dict[str, Any]:
        """Analyze text characteristics for chunking strategy"""
        lengths = [j["text_length"] for j in sample_judgments if j["text_length"] > 0]
        word_counts = [j["word_count"] for j in sample_judgments if j["word_count"] > 0]
        paragraph_counts = [j["paragraph_count"] for j in sample_judgments if j["paragraph_count"] > 0]
        
        if not lengths:
            return {"error": "No valid text found"}
        
        return {
            "avg_text_length": sum(lengths) / len(lengths),
            "min_text_length": min(lengths),
            "max_text_length": max(lengths),
            "avg_word_count": sum(word_counts) / len(word_counts),
            "avg_paragraph_count": sum(paragraph_counts) / len(paragraph_counts),
            "estimated_pages": sum(lengths) / len(lengths) / 2000,  # Rough estimate
            "has_legal_structure_pct": sum(1 for j in sample_judgments if j["has_legal_sections"]) / len(sample_judgments) * 100
        }
    
    def identify_legal_patterns(self, sample_judgments: List[Dict]) -> List[Dict[str, Any]]:
        """Identify common legal document patterns for chunking"""
        patterns = []
        
        # Aggregate section markers
        all_markers = {}
        for judgment in sample_judgments:
            for marker in judgment["section_markers"]:
                marker_type = marker["type"]
                if marker_type not in all_markers:
                    all_markers[marker_type] = {"count": 0, "judgments": 0}
                all_markers[marker_type]["count"] += marker["count"]
                all_markers[marker_type]["judgments"] += 1
        
        # Convert to patterns
        for marker_type, data in all_markers.items():
            patterns.append({
                "pattern_type": marker_type,
                "frequency": data["judgments"] / len(sample_judgments),
                "avg_occurrences": data["count"] / data["judgments"],
                "chunking_potential": "high" if data["judgments"] / len(sample_judgments) > 0.5 else "medium"
            })
        
        return sorted(patterns, key=lambda x: x["frequency"], reverse=True)
    
    def generate_chunking_strategy(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate optimal chunking strategy based on analysis"""
        text_chars = analysis.get("text_characteristics", {})
        patterns = analysis.get("legal_structure_patterns", [])
        
        strategy = {
            "recommended_chunk_size": min(8000, max(2000, int(text_chars.get("avg_text_length", 4000) / 10))),
            "chunk_overlap": 200,
            "chunking_method": "hybrid",
            "section_aware": True,
            "legal_structure_priority": [p["pattern_type"] for p in patterns[:3]],
            "metadata_enrichment": True,
            "reasoning": {
                "chunk_size": f"Based on avg text length of {text_chars.get('avg_text_length', 0):.0f} chars",
                "method": "Hybrid approach combining semantic and structural chunking",
                "section_awareness": f"{text_chars.get('has_legal_structure_pct', 0):.1f}% of documents have clear legal structure"
            }
        }
        
        return strategy
    
    def save_analysis(self, analysis: Dict[str, Any], output_file: str = "supreme_court_analysis.json"):
        """Save analysis results to file"""
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"Analysis saved to: {output_path}")

def main():
    analyzer = SupremeCourtDataAnalyzer()
    
    # Analyze 2023 data with 5 samples
    print("Analyzing Supreme Court data structure...")
    analysis = analyzer.analyze_year_data(2023, num_samples=5)
    
    # Generate chunking strategy
    strategy = analyzer.generate_chunking_strategy(analysis)
    analysis["chunking_strategy"] = strategy
    
    # Save results
    analyzer.save_analysis(analysis)
    
    # Print summary
    print("\n" + "="*60)
    print("SUPREME COURT DATA ANALYSIS SUMMARY")
    print("="*60)
    
    print(f"Year: {analysis['year']}")
    print(f"Total Judgments: {analysis['total_judgments']}")
    print(f"Samples Analyzed: {len(analysis['sample_judgments'])}")
    
    if analysis['text_characteristics']:
        tc = analysis['text_characteristics']
        print(f"\nText Characteristics:")
        print(f"  Average Length: {tc.get('avg_text_length', 0):.0f} characters")
        print(f"  Average Words: {tc.get('avg_word_count', 0):.0f}")
        print(f"  Estimated Pages: {tc.get('estimated_pages', 0):.1f}")
        print(f"  Legal Structure: {tc.get('has_legal_structure_pct', 0):.1f}%")
    
    if analysis['legal_structure_patterns']:
        print(f"\nTop Legal Patterns:")
        for pattern in analysis['legal_structure_patterns'][:5]:
            print(f"  {pattern['pattern_type']}: {pattern['frequency']:.1%} frequency")
    
    if analysis['chunking_strategy']:
        cs = analysis['chunking_strategy']
        print(f"\nRecommended Chunking Strategy:")
        print(f"  Chunk Size: {cs['recommended_chunk_size']} characters")
        print(f"  Overlap: {cs['chunk_overlap']} characters")
        print(f"  Method: {cs['chunking_method']}")
        print(f"  Section Aware: {cs['section_aware']}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()