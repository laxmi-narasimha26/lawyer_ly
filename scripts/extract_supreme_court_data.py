#!/usr/bin/env python3
"""
Extract Supreme Court ZIP files for optimal vectorization processing
"""

import zipfile
import json
from pathlib import Path
import shutil
import logging
from typing import Dict, List
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SupremeCourtExtractor:
    """Extract Supreme Court ZIP files efficiently"""
    
    def __init__(self, data_dir: str = "./data/supreme_court_judgments"):
        self.data_dir = Path(data_dir)
        self.extracted_dir = self.data_dir / "extracted"
        self.stats = {
            "years_processed": [],
            "total_pdfs_extracted": 0,
            "total_metadata_extracted": 0,
            "total_size_mb": 0,
            "extraction_errors": []
        }
    
    def create_extraction_structure(self):
        """Create organized directory structure for extracted files"""
        logger.info("Creating extraction directory structure...")
        
        # Create main extracted directory
        self.extracted_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.extracted_dir / "judgments").mkdir(exist_ok=True)
        (self.extracted_dir / "metadata").mkdir(exist_ok=True)
        (self.extracted_dir / "indexes").mkdir(exist_ok=True)
        
        logger.info(f"✅ Created extraction structure at: {self.extracted_dir}")
    
    def extract_year_data(self, year: str) -> bool:
        """Extract data for a specific year"""
        logger.info(f"📅 Extracting data for year {year}...")
        
        year_dir = self.data_dir / year
        english_zip = year_dir / "english.zip"
        metadata_zip = year_dir / "metadata.zip"
        english_index = year_dir / "english.index.json"
        metadata_index = year_dir / "metadata.index.json"
        
        if not all([english_zip.exists(), metadata_zip.exists()]):
            logger.error(f"Missing ZIP files for year {year}")
            return False
        
        try:
            # Create year-specific directories
            year_judgments_dir = self.extracted_dir / "judgments" / year
            year_metadata_dir = self.extracted_dir / "metadata" / year
            year_indexes_dir = self.extracted_dir / "indexes" / year
            
            year_judgments_dir.mkdir(parents=True, exist_ok=True)
            year_metadata_dir.mkdir(parents=True, exist_ok=True)
            year_indexes_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract English judgments (PDFs)
            logger.info(f"  📄 Extracting PDF judgments...")
            with zipfile.ZipFile(english_zip, 'r') as zip_ref:
                pdf_files = [f for f in zip_ref.namelist() if f.endswith('.pdf')]
                
                for i, pdf_file in enumerate(pdf_files):
                    zip_ref.extract(pdf_file, year_judgments_dir)
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"    Extracted {i + 1}/{len(pdf_files)} PDFs...")
                
                self.stats["total_pdfs_extracted"] += len(pdf_files)
                logger.info(f"  ✅ Extracted {len(pdf_files)} PDF files")
            
            # Extract metadata (JSON files)
            logger.info(f"  📋 Extracting metadata...")
            with zipfile.ZipFile(metadata_zip, 'r') as zip_ref:
                json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
                
                for i, json_file in enumerate(json_files):
                    zip_ref.extract(json_file, year_metadata_dir)
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"    Extracted {i + 1}/{len(json_files)} metadata files...")
                
                self.stats["total_metadata_extracted"] += len(json_files)
                logger.info(f"  ✅ Extracted {len(json_files)} metadata files")
            
            # Copy index files
            if english_index.exists():
                shutil.copy2(english_index, year_indexes_dir / "english.index.json")
            if metadata_index.exists():
                shutil.copy2(metadata_index, year_indexes_dir / "metadata.index.json")
            
            # Calculate extracted size
            year_size = sum(f.stat().st_size for f in year_judgments_dir.rglob('*') if f.is_file())
            year_size += sum(f.stat().st_size for f in year_metadata_dir.rglob('*') if f.is_file())
            year_size_mb = year_size / (1024 * 1024)
            
            self.stats["total_size_mb"] += year_size_mb
            self.stats["years_processed"].append(year)
            
            logger.info(f"✅ Completed extraction for {year}: {year_size_mb:.1f} MB")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error extracting year {year}: {e}")
            self.stats["extraction_errors"].append(f"{year}: {str(e)}")
            return False
    
    def extract_all_years(self) -> bool:
        """Extract all available years"""
        logger.info("🚀 Starting extraction of all Supreme Court data...")
        
        # Create extraction structure
        self.create_extraction_structure()
        
        # Find available years
        available_years = []
        for year_dir in self.data_dir.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                if (year_dir / "english.zip").exists() and (year_dir / "metadata.zip").exists():
                    available_years.append(year_dir.name)
        
        available_years.sort()
        logger.info(f"Found {len(available_years)} years to extract: {available_years}")
        
        # Extract each year
        success = True
        for i, year in enumerate(available_years, 1):
            logger.info(f"📅 Processing year {year} ({i}/{len(available_years)})")
            year_success = self.extract_year_data(year)
            success &= year_success
            
            # Progress update
            progress = (i / len(available_years)) * 100
            logger.info(f"📈 Overall progress: {progress:.1f}% ({i}/{len(available_years)} years)")
        
        return success
    
    def create_extraction_summary(self):
        """Create summary of extraction process"""
        summary = {
            "extraction_stats": self.stats,
            "directory_structure": {
                "extracted_root": str(self.extracted_dir),
                "judgments_dir": str(self.extracted_dir / "judgments"),
                "metadata_dir": str(self.extracted_dir / "metadata"),
                "indexes_dir": str(self.extracted_dir / "indexes")
            },
            "file_organization": {
                "judgments": "extracted/judgments/{year}/*.pdf",
                "metadata": "extracted/metadata/{year}/*.json",
                "indexes": "extracted/indexes/{year}/*.json"
            },
            "vectorization_ready": True,
            "next_steps": [
                "Run optimized ingestion pipeline on extracted files",
                "Files are now organized for efficient processing",
                "No need to handle ZIP streaming during vectorization"
            ]
        }
        
        summary_file = self.extracted_dir / "extraction_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📄 Extraction summary saved to: {summary_file}")
        return summary
    
    def cleanup_zips(self, confirm: bool = False):
        """Optionally remove ZIP files after successful extraction"""
        if not confirm:
            logger.info("💡 To save space, you can remove ZIP files after extraction:")
            logger.info("   python scripts/extract_supreme_court_data.py --cleanup-zips")
            return
        
        logger.info("🗑️ Cleaning up ZIP files...")
        total_saved = 0
        
        for year in self.stats["years_processed"]:
            year_dir = self.data_dir / year
            for zip_file in ["english.zip", "metadata.zip"]:
                zip_path = year_dir / zip_file
                if zip_path.exists():
                    size_mb = zip_path.stat().st_size / (1024 * 1024)
                    zip_path.unlink()
                    total_saved += size_mb
                    logger.info(f"  Removed {zip_file} ({size_mb:.1f} MB)")
        
        logger.info(f"✅ Cleanup complete. Saved {total_saved:.1f} MB of disk space")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract Supreme Court ZIP files for vectorization")
    parser.add_argument("--data-dir", default="./data/supreme_court_judgments",
                       help="Directory containing Supreme Court ZIP files")
    parser.add_argument("--year", type=str,
                       help="Extract specific year only")
    parser.add_argument("--cleanup-zips", action="store_true",
                       help="Remove ZIP files after successful extraction")
    
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = SupremeCourtExtractor(args.data_dir)
    
    try:
        if args.year:
            # Extract specific year
            success = extractor.extract_year_data(args.year)
        else:
            # Extract all years
            success = extractor.extract_all_years()
        
        # Create summary
        summary = extractor.create_extraction_summary()
        
        if success:
            logger.info("🎉 Extraction completed successfully!")
            logger.info(f"📊 Extracted {summary['extraction_stats']['total_pdfs_extracted']} PDF judgments")
            logger.info(f"📊 Extracted {summary['extraction_stats']['total_metadata_extracted']} metadata files")
            logger.info(f"📊 Total size: {summary['extraction_stats']['total_size_mb']:.1f} MB")
            logger.info(f"📁 Files organized in: {summary['directory_structure']['extracted_root']}")
            
            # Cleanup option
            if args.cleanup_zips:
                extractor.cleanup_zips(confirm=True)
            else:
                extractor.cleanup_zips(confirm=False)
        else:
            logger.error("❌ Extraction completed with errors")
            if extractor.stats["extraction_errors"]:
                logger.error("Errors encountered:")
                for error in extractor.stats["extraction_errors"]:
                    logger.error(f"  • {error}")
    
    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise

if __name__ == "__main__":
    main()