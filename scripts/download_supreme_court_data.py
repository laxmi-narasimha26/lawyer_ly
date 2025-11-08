#!/usr/bin/env python3
"""
Supreme Court Data Download Script
Downloads the 52GB Indian Supreme Court judgments dataset from AWS S3
"""

import os
import sys
import boto3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import zipfile
from botocore import UNSIGNED
from botocore.client import Config
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SupremeCourtDataDownloader:
    """
    Downloads Indian Supreme Court judgments from AWS S3
    Dataset: ~52GB of legal documents from 1950-2025
    """
    
    def __init__(self, local_data_dir: str = "./data/supreme_court_judgments"):
        self.s3_bucket = "indian-supreme-court-judgments"
        self.local_dir = Path(local_data_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        
        # S3 client with no authentication (public bucket)
        self.s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        
        # Track download progress
        self.download_stats = {
            "total_files": 0,
            "downloaded_files": 0,
            "total_size_gb": 0,
            "downloaded_size_gb": 0,
            "years_processed": []
        }
    
    def list_available_years(self) -> List[int]:
        """List all available years in the dataset"""
        logger.info("Fetching available years from S3...")
        
        years = set()
        
        # List data directory
        paginator = self.s3.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix="data/zip/", Delimiter="/"):
            if 'CommonPrefixes' in page:
                for prefix in page['CommonPrefixes']:
                    # Extract year from path like "data/zip/year=2023/"
                    prefix_path = prefix['Prefix']
                    if 'year=' in prefix_path:
                        year_str = prefix_path.split('year=')[1].rstrip('/')
                        if year_str.isdigit():
                            years.add(int(year_str))
        
        sorted_years = sorted(list(years))
        logger.info(f"Found {len(sorted_years)} years: {sorted_years[0]}-{sorted_years[-1]}")
        return sorted_years
    
    def get_year_info(self, year: int) -> Dict[str, Any]:
        """Get information about files available for a specific year"""
        year_info = {
            "year": year,
            "english_zip": None,
            "regional_zip": None,
            "metadata_zip": None,
            "english_index": None,
            "regional_index": None,
            "metadata_index": None,
            "total_size_mb": 0
        }
        
        # Check data files
        data_prefix = f"data/zip/year={year}/"
        metadata_prefix = f"metadata/zip/year={year}/"
        
        try:
            # List objects in year directory
            response = self.s3.list_objects_v2(Bucket=self.s3_bucket, Prefix=data_prefix)
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    size_mb = obj['Size'] / (1024 * 1024)
                    year_info["total_size_mb"] += size_mb
                    
                    if key.endswith('english.zip'):
                        year_info["english_zip"] = {"key": key, "size_mb": size_mb}
                    elif key.endswith('english.index.json'):
                        year_info["english_index"] = {"key": key, "size_mb": size_mb}
                    elif key.endswith('regional.zip'):
                        year_info["regional_zip"] = {"key": key, "size_mb": size_mb}
                    elif key.endswith('regional.index.json'):
                        year_info["regional_index"] = {"key": key, "size_mb": size_mb}
            
            # Check metadata files
            response = self.s3.list_objects_v2(Bucket=self.s3_bucket, Prefix=metadata_prefix)
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    size_mb = obj['Size'] / (1024 * 1024)
                    year_info["total_size_mb"] += size_mb
                    
                    if key.endswith('metadata.zip'):
                        year_info["metadata_zip"] = {"key": key, "size_mb": size_mb}
                    elif key.endswith('metadata.index.json'):
                        year_info["metadata_index"] = {"key": key, "size_mb": size_mb}
        
        except Exception as e:
            logger.error(f"Error getting info for year {year}: {e}")
        
        return year_info
    
    def download_file(self, s3_key: str, local_path: Path, description: str = "") -> bool:
        """Download a single file from S3 with progress tracking"""
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file already exists and has content
            if local_path.exists() and local_path.stat().st_size > 0:
                logger.info(f"File already exists: {local_path.name}")
                return True
            
            logger.info(f"Downloading {description}: {s3_key}")
            
            # Get file size for progress tracking
            response = self.s3.head_object(Bucket=self.s3_bucket, Key=s3_key)
            file_size = response['ContentLength']
            
            # Download with progress callback
            def progress_callback(bytes_transferred):
                percent = (bytes_transferred / file_size) * 100
                if bytes_transferred % (10 * 1024 * 1024) == 0:  # Log every 10MB
                    logger.info(f"  Progress: {percent:.1f}% ({bytes_transferred / (1024*1024):.1f}MB)")
            
            self.s3.download_file(
                self.s3_bucket, 
                s3_key, 
                str(local_path),
                Callback=progress_callback
            )
            
            logger.info(f"✅ Downloaded: {local_path.name} ({file_size / (1024*1024):.1f}MB)")
            self.download_stats["downloaded_files"] += 1
            self.download_stats["downloaded_size_gb"] += file_size / (1024*1024*1024)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error downloading {s3_key}: {e}")
            return False
    
    def download_year_data(self, year: int, include_regional: bool = True, include_metadata: bool = True) -> bool:
        """Download all data for a specific year"""
        logger.info(f"📅 Downloading data for year {year}")
        
        year_info = self.get_year_info(year)
        year_dir = self.local_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        
        success = True
        
        # Download English judgments (always included)
        if year_info["english_zip"]:
            english_path = year_dir / "english.zip"
            success &= self.download_file(
                year_info["english_zip"]["key"], 
                english_path, 
                f"English judgments for {year}"
            )
            
            # Download English index
            if year_info["english_index"]:
                index_path = year_dir / "english.index.json"
                success &= self.download_file(
                    year_info["english_index"]["key"], 
                    index_path, 
                    f"English index for {year}"
                )
        
        # Download Regional judgments (optional)
        if include_regional and year_info["regional_zip"]:
            regional_path = year_dir / "regional.zip"
            success &= self.download_file(
                year_info["regional_zip"]["key"], 
                regional_path, 
                f"Regional judgments for {year}"
            )
            
            # Download Regional index
            if year_info["regional_index"]:
                index_path = year_dir / "regional.index.json"
                success &= self.download_file(
                    year_info["regional_index"]["key"], 
                    index_path, 
                    f"Regional index for {year}"
                )
        
        # Download Metadata (optional)
        if include_metadata and year_info["metadata_zip"]:
            metadata_path = year_dir / "metadata.zip"
            success &= self.download_file(
                year_info["metadata_zip"]["key"], 
                metadata_path, 
                f"Metadata for {year}"
            )
            
            # Download Metadata index
            if year_info["metadata_index"]:
                index_path = year_dir / "metadata.index.json"
                success &= self.download_file(
                    year_info["metadata_index"]["key"], 
                    index_path, 
                    f"Metadata index for {year}"
                )
        
        if success:
            self.download_stats["years_processed"].append(year)
            logger.info(f"✅ Completed downloading year {year}")
        else:
            logger.error(f"❌ Failed to download some files for year {year}")
        
        return success
    
    def download_recent_years(self, num_years: int = 5, include_regional: bool = False) -> bool:
        """Download data for the most recent N years (for faster setup)"""
        logger.info(f"📥 Downloading data for the most recent {num_years} years")
        
        available_years = self.list_available_years()
        recent_years = available_years[-num_years:]
        
        logger.info(f"Will download years: {recent_years}")
        
        success = True
        for year in recent_years:
            success &= self.download_year_data(year, include_regional=include_regional)
        
        return success
    
    def download_all_data(self, include_regional: bool = True, include_metadata: bool = True) -> bool:
        """Download the complete 52GB dataset"""
        logger.info("📥 Starting download of complete Supreme Court dataset (~52GB)")
        logger.warning("⚠️  This will download ~52GB of data. Ensure you have sufficient disk space and bandwidth.")
        
        available_years = self.list_available_years()
        
        # Calculate total size
        total_size_gb = 0
        for year in available_years:
            year_info = self.get_year_info(year)
            total_size_gb += year_info["total_size_mb"] / 1024
        
        self.download_stats["total_size_gb"] = total_size_gb
        logger.info(f"📊 Total dataset size: {total_size_gb:.2f} GB across {len(available_years)} years")
        
        # Download year by year
        success = True
        for i, year in enumerate(available_years, 1):
            logger.info(f"📅 Processing year {year} ({i}/{len(available_years)})")
            success &= self.download_year_data(year, include_regional, include_metadata)
            
            # Progress update
            progress = (i / len(available_years)) * 100
            logger.info(f"📈 Overall progress: {progress:.1f}% ({i}/{len(available_years)} years)")
        
        return success
    
    def extract_sample_documents(self, year: int, num_samples: int = 10) -> List[Dict[str, Any]]:
        """Extract sample documents from a year's data for testing"""
        year_dir = self.local_dir / str(year)
        english_zip = year_dir / "english.zip"
        metadata_zip = year_dir / "metadata.zip"
        
        samples = []
        
        if not english_zip.exists() or not metadata_zip.exists():
            logger.error(f"Required files not found for year {year}")
            return samples
        
        try:
            # Get list of files from English zip
            with zipfile.ZipFile(english_zip, 'r') as eng_zip:
                pdf_files = [f for f in eng_zip.namelist() if f.endswith('.pdf')][:num_samples]
            
            # Get corresponding metadata
            with zipfile.ZipFile(metadata_zip, 'r') as meta_zip:
                for pdf_file in pdf_files:
                    # Get base name without extension and language suffix
                    base_name = pdf_file.replace('_EN.pdf', '')
                    metadata_file = f"{base_name}.json"
                    
                    if metadata_file in meta_zip.namelist():
                        # Extract metadata
                        with meta_zip.open(metadata_file) as f:
                            metadata = json.load(f)
                        
                        # Extract PDF content (first few KB for preview)
                        with zipfile.ZipFile(english_zip, 'r') as eng_zip:
                            with eng_zip.open(pdf_file) as pdf_f:
                                pdf_preview = pdf_f.read(1024)  # First 1KB
                        
                        samples.append({
                            "pdf_file": pdf_file,
                            "metadata_file": metadata_file,
                            "metadata": metadata,
                            "pdf_size": len(pdf_preview),
                            "year": year
                        })
            
            logger.info(f"Extracted {len(samples)} sample documents from year {year}")
            
        except Exception as e:
            logger.error(f"Error extracting samples from year {year}: {e}")
        
        return samples
    
    def get_download_summary(self) -> Dict[str, Any]:
        """Get summary of download progress"""
        return {
            "download_stats": self.download_stats,
            "local_directory": str(self.local_dir),
            "timestamp": datetime.now().isoformat()
        }
    
    def save_download_summary(self):
        """Save download summary to file"""
        summary = self.get_download_summary()
        summary_file = self.local_dir / "download_summary.json"
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📄 Download summary saved to: {summary_file}")

def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download Indian Supreme Court Judgments Dataset")
    parser.add_argument("--data-dir", default="./data/supreme_court_judgments", 
                       help="Local directory to store downloaded data")
    parser.add_argument("--recent-years", type=int, default=0,
                       help="Download only the most recent N years (0 = download all)")
    parser.add_argument("--include-regional", action="store_true",
                       help="Include regional language judgments")
    parser.add_argument("--include-metadata", action="store_true", default=True,
                       help="Include metadata files")
    parser.add_argument("--list-years", action="store_true",
                       help="List available years and exit")
    parser.add_argument("--year", type=int,
                       help="Download data for a specific year only")
    parser.add_argument("--extract-samples", type=int, default=0,
                       help="Extract N sample documents for testing")
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = SupremeCourtDataDownloader(args.data_dir)
    
    try:
        if args.list_years:
            # List available years
            years = downloader.list_available_years()
            print(f"\nAvailable years: {len(years)} years from {years[0]} to {years[-1]}")
            for year in years:
                year_info = downloader.get_year_info(year)
                print(f"  {year}: {year_info['total_size_mb']:.1f} MB")
            return
        
        if args.year:
            # Download specific year
            logger.info(f"Downloading data for year {args.year}")
            success = downloader.download_year_data(
                args.year, 
                include_regional=args.include_regional,
                include_metadata=args.include_metadata
            )
            
            if args.extract_samples > 0:
                samples = downloader.extract_sample_documents(args.year, args.extract_samples)
                logger.info(f"Extracted {len(samples)} samples")
        
        elif args.recent_years > 0:
            # Download recent years
            success = downloader.download_recent_years(
                args.recent_years, 
                include_regional=args.include_regional
            )
        
        else:
            # Download all data
            logger.warning("⚠️  You are about to download the complete 52GB dataset!")
            response = input("Continue? (y/N): ")
            if response.lower() != 'y':
                logger.info("Download cancelled")
                return
            
            success = downloader.download_all_data(
                include_regional=args.include_regional,
                include_metadata=args.include_metadata
            )
        
        # Save summary
        downloader.save_download_summary()
        
        if success:
            logger.info("🎉 Download completed successfully!")
            summary = downloader.get_download_summary()
            logger.info(f"📊 Downloaded {summary['download_stats']['downloaded_files']} files")
            logger.info(f"📊 Total size: {summary['download_stats']['downloaded_size_gb']:.2f} GB")
        else:
            logger.error("❌ Download completed with errors")
            
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise

if __name__ == "__main__":
    main()