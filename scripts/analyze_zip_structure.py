#!/usr/bin/env python3
"""
Analyze ZIP file structure to determine optimal extraction strategy
"""

import zipfile
import json
from pathlib import Path
import os

def analyze_zip_structure():
    """Analyze the structure of downloaded zip files"""
    data_dir = Path("./data/supreme_court_judgments")
    
    analysis = {
        "years_analyzed": [],
        "file_counts": {},
        "file_sizes": {},
        "sample_files": {},
        "extraction_recommendations": {}
    }
    
    # Analyze each year
    for year_dir in data_dir.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            year = year_dir.name
            print(f"\n📅 Analyzing {year}...")
            
            english_zip = year_dir / "english.zip"
            metadata_zip = year_dir / "metadata.zip"
            
            if english_zip.exists() and metadata_zip.exists():
                analysis["years_analyzed"].append(year)
                
                # Analyze English judgments zip
                with zipfile.ZipFile(english_zip, 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    pdf_files = [f for f in file_list if f.endswith('.pdf')]
                    
                    analysis["file_counts"][year] = {
                        "total_files": len(file_list),
                        "pdf_files": len(pdf_files),
                        "other_files": len(file_list) - len(pdf_files)
                    }
                    
                    # Get file sizes
                    total_uncompressed = sum(zip_ref.getinfo(f).file_size for f in file_list)
                    analysis["file_sizes"][year] = {
                        "compressed_mb": round(english_zip.stat().st_size / (1024*1024), 2),
                        "uncompressed_mb": round(total_uncompressed / (1024*1024), 2),
                        "compression_ratio": round(english_zip.stat().st_size / total_uncompressed, 2)
                    }
                    
                    # Sample file names
                    analysis["sample_files"][year] = {
                        "first_5_pdfs": pdf_files[:5],
                        "total_pdfs": len(pdf_files)
                    }
                    
                    print(f"  📄 PDF files: {len(pdf_files)}")
                    print(f"  💾 Compressed: {analysis['file_sizes'][year]['compressed_mb']} MB")
                    print(f"  📦 Uncompressed: {analysis['file_sizes'][year]['uncompressed_mb']} MB")
                    print(f"  🗜️ Compression ratio: {analysis['file_sizes'][year]['compression_ratio']}")
                
                # Analyze metadata zip
                with zipfile.ZipFile(metadata_zip, 'r') as zip_ref:
                    metadata_files = zip_ref.namelist()
                    json_files = [f for f in metadata_files if f.endswith('.json')]
                    
                    analysis["file_counts"][year]["metadata_files"] = len(json_files)
                    
                    print(f"  📋 Metadata files: {len(json_files)}")
    
    # Generate recommendations
    total_compressed = sum(analysis["file_sizes"][year]["compressed_mb"] for year in analysis["years_analyzed"])
    total_uncompressed = sum(analysis["file_sizes"][year]["uncompressed_mb"] for year in analysis["years_analyzed"])
    
    analysis["extraction_recommendations"] = {
        "total_compressed_mb": round(total_compressed, 2),
        "total_uncompressed_mb": round(total_uncompressed, 2),
        "space_savings_mb": round(total_uncompressed - total_compressed, 2),
        "recommendation": "KEEP_COMPRESSED" if total_uncompressed > total_compressed * 2 else "EXTRACT_ALL",
        "reasoning": []
    }
    
    if total_uncompressed > total_compressed * 2:
        analysis["extraction_recommendations"]["reasoning"].append("Significant compression savings (>50%)")
        analysis["extraction_recommendations"]["reasoning"].append("Stream processing from ZIP is efficient")
        analysis["extraction_recommendations"]["reasoning"].append("Saves disk space")
    else:
        analysis["extraction_recommendations"]["reasoning"].append("Low compression ratio")
        analysis["extraction_recommendations"]["reasoning"].append("Extraction may improve processing speed")
    
    return analysis

def main():
    print("🔍 Analyzing ZIP file structure for optimal vectorization strategy...")
    
    analysis = analyze_zip_structure()
    
    # Save analysis
    with open("zip_structure_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n📊 ANALYSIS SUMMARY")
    print("=" * 50)
    print(f"Years analyzed: {len(analysis['years_analyzed'])}")
    print(f"Total compressed size: {analysis['extraction_recommendations']['total_compressed_mb']} MB")
    print(f"Total uncompressed size: {analysis['extraction_recommendations']['total_uncompressed_mb']} MB")
    print(f"Space savings: {analysis['extraction_recommendations']['space_savings_mb']} MB")
    print(f"Recommendation: {analysis['extraction_recommendations']['recommendation']}")
    
    print(f"\nReasons:")
    for reason in analysis['extraction_recommendations']['reasoning']:
        print(f"  • {reason}")
    
    # Detailed breakdown
    print(f"\n📋 YEAR-BY-YEAR BREAKDOWN")
    print("-" * 50)
    for year in sorted(analysis['years_analyzed']):
        fc = analysis['file_counts'][year]
        fs = analysis['file_sizes'][year]
        print(f"{year}: {fc['pdf_files']} PDFs, {fs['compressed_mb']}MB → {fs['uncompressed_mb']}MB")
    
    print(f"\n💡 VECTORIZATION STRATEGY RECOMMENDATIONS")
    print("-" * 50)
    
    if analysis['extraction_recommendations']['recommendation'] == "KEEP_COMPRESSED":
        print("✅ RECOMMENDED: Keep files compressed, stream during processing")
        print("   • Our ingestion pipeline already handles ZIP streaming")
        print("   • Saves significant disk space")
        print("   • Processing speed is comparable")
        print("   • Easy to manage and backup")
    else:
        print("✅ RECOMMENDED: Extract files for faster processing")
        print("   • Low compression ratio makes extraction worthwhile")
        print("   • Faster file access during processing")
        print("   • Easier debugging and manual inspection")
    
    print(f"\n📄 Analysis saved to: zip_structure_analysis.json")

if __name__ == "__main__":
    main()