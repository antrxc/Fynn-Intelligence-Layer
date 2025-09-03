#!/usr/bin/env python3
"""
Intelligence Layer - Procurement Analysis Tool
This script is the main entry point for the procurement analysis tool.
"""

import argparse
import json
import time
import sys
import os

def main():
    """
    Main entry point for the procurement analysis tool.
    Delegates to the optimized advanced_main.py for procurement insights.
    """
    start_time = time.time()
    
    print("🚀 Intelligence Layer - Procurement Analysis Tool")
    print("=================================================")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Run optimized procurement analysis on a file URL or raw text.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file-url", help="HTTP(S) URL of a file to analyze (e.g., CSV)")
    group.add_argument("--text", help="Raw text to analyze")
    parser.add_argument("--mime", help="Optional MIME type for file (e.g., text/csv)")
    parser.add_argument("--output", choices=["pretty", "json"], default="pretty", 
                        help="Output format (pretty or json)")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache for fresh results")
    args = parser.parse_args()

    # Import and use the optimized version
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from advanced_main import main as advanced_main
        
        # Pass our arguments to advanced_main by updating sys.argv
        if args.no_cache:
            sys.argv.append("--no-cache")
        
        # Run advanced main
        advanced_main()
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        return
    # Print execution time at the end
    elapsed = time.time() - start_time
    print(f"\n⏱️ Total execution time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    main()