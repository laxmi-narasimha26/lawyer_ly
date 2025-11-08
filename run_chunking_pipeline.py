#!/usr/bin/env python3
"""
Runner script for Chunking & Pre-Embedding Pipeline
Executes the complete pipeline and runs acceptance tests
"""

import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fitz
        import pytesseract
        import tiktoken
        import numpy
        from PIL import Image
        logger.info("✅ All dependencies are available")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.error("Install dependencies with: pip install -r chunking_requirements.txt")
        return False

def check_tesseract():
    """Check if Tesseract OCR is available"""
    try:
        import pytesseract
        # Try to get Tesseract version
        version = pytesseract.get_tesseract_version()
        logger.info(f"✅ Tesseract OCR available: {version}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Tesseract OCR not available: {e}")
        logger.warning("OCR fallback will not work. Install Tesseract OCR if needed.")
        return False

def check_input_data():
    """Check if input data is available"""
    # Check Supreme Court judgments
    judgment_dir = Path('data/supreme_court_judgments/extracted/judgments')
    if not judgment_dir.exists():
        logger.error(f"❌ Supreme Court judgments directory not found: {judgment_dir}")
        return False
    
    # Count 2020 PDFs
    pdf_count = len([f for f in judgment_dir.rglob('*.pdf') if '2020' in f.name or '2020' in str(f.parent)])
    if pdf_count == 0:
        logger.error("❌ No 2020 Supreme Court judgment PDFs found")
        return False
    
    logger.info(f"✅ Found {pdf_count} 2020 Supreme Court judgment PDFs")
    
    # Check BNS PDF
    bns_path = Path(r'C:\Users\user\lawyer_ly\data\BNS.pdf.pdf')
    if not bns_path.exists():
        logger.error(f"❌ BNS PDF not found: {bns_path}")
        return False
    
    logger.info(f"✅ BNS PDF found: {bns_path}")
    return True

def run_chunking_pipeline():
    """Run the chunking pipeline"""
    logger.info("🚀 Starting Chunking & Pre-Embedding Pipeline")
    
    try:
        # Import and run pipeline
        from chunking_pipeline import main as pipeline_main
        result = pipeline_main()
        
        if result == 0:
            logger.info("✅ Chunking pipeline completed successfully")
            return True
        else:
            logger.error("❌ Chunking pipeline failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Pipeline execution failed: {e}")
        return False

def run_acceptance_tests():
    """Run acceptance tests"""
    logger.info("🧪 Running Acceptance Tests")
    
    try:
        # Import and run tests
        from test_chunking_pipeline import main as test_main
        result = test_main()
        
        if result == 0:
            logger.info("✅ All acceptance tests passed")
            return True
        else:
            logger.error("❌ Some acceptance tests failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        return False

def print_checklist():
    """Print implementation checklist"""
    logger.info("\n" + "="*80)
    logger.info("📋 IMPLEMENTATION CHECKLIST")
    logger.info("="*80)
    
    checklist_items = [
        "✅ Extraction: Use PyMuPDF; fall back to Tesseract only if text density < 60%",
        "✅ Extraction: Strip headers/footers, page numbers, mastheads, hyphen breaks",
        "✅ Extraction: Preserve paragraph/¶ numbering and legal numbering",
        "✅ Judgment chunking: Paragraph windows ~400–600 tokens, cap 800",
        "✅ Judgment chunking: Overlap 80 tokens between consecutive windows",
        "✅ Judgment chunking: Each chunk includes para_range if detectable",
        "✅ BNS chunking: One legal unit per chunk (Section/Sub/Illustration/Explanation/Proviso)",
        "✅ BNS chunking: If unit > 800 tokens, split into :part:N",
        "✅ BNS chunking: Include section_no, unit_type, effective_from = 2024-07-01, effective_to = null",
        "✅ Token gate & validation: Tokenize every chunk (cl100k_base)",
        "✅ Token gate & validation: Enforce 80 ≤ tokens ≤ 800",
        "✅ Token gate & validation: Drop too-small chunks (<80) unless statute title; re-split too-large",
        "✅ Token gate & validation: Deduplicate by sha256; drop near-duplicates (Jaccard ≥ 0.95)",
        "✅ IDs & Paths: Chunk IDs follow {DOC_ID}:chunk:{SEQUENTIAL_INDEX} (or :part:N for splits)",
        "✅ IDs & Paths: Outputs written exactly to out/chunks/... and out/reports/chunking_summary.json",
        "✅ No creativity: No extra fields beyond the schemas above",
        "✅ No creativity: No changes to thresholds, overlaps, or limits",
        "✅ No creativity: No embedding/API calls in this step"
    ]
    
    for item in checklist_items:
        logger.info(item)
    
    logger.info("="*80)

def main():
    """Main execution function"""
    logger.info("🎯 Chunking & Pre-Embedding Pipeline Runner")
    
    # Pre-flight checks
    logger.info("🔍 Running pre-flight checks...")
    
    if not check_dependencies():
        return 1
    
    check_tesseract()  # Warning only
    
    if not check_input_data():
        return 1
    
    # Run pipeline
    if not run_chunking_pipeline():
        return 1
    
    # Run tests
    if not run_acceptance_tests():
        return 1
    
    # Print checklist
    print_checklist()
    
    logger.info("🎉 Chunking & Pre-Embedding Pipeline completed successfully!")
    logger.info("📁 Output files:")
    logger.info("  - out/chunks/2020/*.jsonl (Supreme Court judgment chunks)")
    logger.info("  - out/chunks/BNS/BNS_2023.jsonl (BNS statute chunks)")
    logger.info("  - out/reports/chunking_summary.json (Summary report)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())