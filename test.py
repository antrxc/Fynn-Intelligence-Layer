#!/usr/bin/env python3
"""
Test script for Intelligence Layer services with URL input.

Usage:
    python test.py <URL> [service]

Examples:
    python test.py "https://example.com/file.csv"
    python test.py "https://example.com/file.pdf" summary
    python test.py "https://example.com/file.csv" recommendations
    python test.py "https://example.com/file.pdf" visuals
    python test.py "https://example.com/file.csv" orchestrator
"""

import sys
import os
import requests
import time
import traceback

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def download_file(url: str, timeout: int = 30):
    """Download file from URL and return content + inferred MIME type."""
    print(f"📥 Downloading: {url}")
    
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.content
        
        # Infer MIME type from URL or Content-Type header
        mime_type = response.headers.get('content-type', '')
        if not mime_type:
            if url.lower().endswith('.pdf'):
                mime_type = 'application/pdf'
            elif url.lower().endswith('.csv'):
                mime_type = 'text/csv'
            elif url.lower().endswith(('.txt', '.md')):
                mime_type = 'text/plain'
            else:
                mime_type = 'application/octet-stream'
        
        print(f"✅ Downloaded {len(content):,} bytes (MIME: {mime_type})")
        return content, mime_type
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise


def test_summary_service(content, mime_type):
    """Test SummaryService individually."""
    print("\n" + "="*50)
    print("🔍 TESTING SUMMARY SERVICE")
    print("="*50)
    
    try:
        from structuredOutput.summary import SummaryService
        
        start_time = time.time()
        service = SummaryService()
        result = service.generate_summary(content, mime_type=mime_type)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Execution time: {elapsed:.2f}s")
        print(f"📋 Title: {getattr(result, 'title', 'None')}")
        
        summary = getattr(result, 'summary', 'No summary')
        print(f"📝 Summary: {summary[:200]}{'...' if len(summary) > 200 else ''}")
        
        key_points = getattr(result, 'key_points', [])
        print(f"🔑 Key Points ({len(key_points)}):")
        for i, point in enumerate(key_points, 1):
            print(f"   {i}. {point}")
            
        charts = getattr(result, 'recommended_charts', [])
        print(f"📊 Recommended Charts ({len(charts)}):")
        for i, chart in enumerate(charts, 1):
            print(f"   {i}. {chart}")
            
        return result
        
    except Exception as e:
        print(f"❌ Summary service failed: {e}")
        traceback.print_exc()
        return None


def test_recommendations_service(content, mime_type):
    """Test RecommendationService individually."""
    print("\n" + "="*50)
    print("💡 TESTING RECOMMENDATIONS SERVICE")
    print("="*50)
    
    try:
        from structuredOutput.recommendations import RecommendationService
        
        start_time = time.time()
        service = RecommendationService()
        result = service.generate_recommendations(content, mime_type=mime_type)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Execution time: {elapsed:.2f}s")
        
        recommendations = getattr(result, 'recommendations', [])
        print(f"📋 Recommendations ({len(recommendations)}):")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
            
        return result
        
    except Exception as e:
        print(f"❌ Recommendations service failed: {e}")
        traceback.print_exc()
        return None


def test_visuals_service(content, mime_type):
    """Test VisualsService individually."""
    print("\n" + "="*50)
    print("📈 TESTING VISUALS SERVICE")
    print("="*50)
    
    try:
        from structuredOutput.visuals import VisualsService
        
        start_time = time.time()
        service = VisualsService()
        result = service.recommend_charts(content, mime_type=mime_type)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Execution time: {elapsed:.2f}s")
        print(f"📊 Chart Recommendations ({len(result)}):")
        for i, chart in enumerate(result, 1):
            chart_type = getattr(chart, 'chart_type', 'Unknown')
            purpose = getattr(chart, 'purpose', '')
            x_axis = getattr(chart, 'x_axis', '')
            y_axis = getattr(chart, 'y_axis', '')
            notes = getattr(chart, 'notes', '')
            
            print(f"   {i}. {chart_type}")
            if purpose:
                print(f"      Purpose: {purpose}")
            if x_axis or y_axis:
                print(f"      Axes: x={x_axis}, y={y_axis}")
            if notes:
                print(f"      Notes: {notes}")
            print()
            
        return result
        
    except Exception as e:
        print(f"❌ Visuals service failed: {e}")
        traceback.print_exc()
        return None


def test_orchestrator(url, mime_type=None):
    """Test all services together using the orchestrator."""
    print("\n" + "="*50)
    print("🎼 TESTING ORCHESTRATOR (ALL SERVICES)")
    print("="*50)
    
    try:
        from structuredOutput.orchestrator import Orchestrator
        
        start_time = time.time()
        orchestrator = Orchestrator()
        results = orchestrator.analyze(file_url=url, mime_type=mime_type)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Total execution time: {elapsed:.2f}s")
        
        for service_name, result in results.items():
            print(f"\n--- {service_name.upper()} ---")
            if isinstance(result, dict) and 'error' in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ Success: {type(result).__name__}")
                if hasattr(result, 'summary'):
                    summary = getattr(result, 'summary', '')
                    print(f"   Summary: {summary[:100]}...")
                elif hasattr(result, 'recommendations'):
                    recs = getattr(result, 'recommendations', [])
                    print(f"   Recommendations: {len(recs)} items")
                elif isinstance(result, list):
                    print(f"   Charts: {len(result)} items")
                    
        return results
        
    except Exception as e:
        print(f"❌ Orchestrator failed: {e}")
        traceback.print_exc()
        return None


def show_help():
    """Show usage help."""
    print(__doc__)
    print("\nAvailable services:")
    print("  summary        - Test only SummaryService")
    print("  recommendations - Test only RecommendationService") 
    print("  visuals        - Test only VisualsService")
    print("  orchestrator   - Test orchestrator (all services concurrently)")
    print("  all            - Test individual services + orchestrator (default)")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        show_help()
        return
    
    url = sys.argv[1]
    service = sys.argv[2] if len(sys.argv) > 2 else 'all'
    
    print("🚀 Intelligence Layer Service Tester")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"Service: {service}")
    
    try:
        # Download file for individual service tests
        if service != 'orchestrator':
            content, detected_mime = download_file(url)
            print(f"🔧 Using MIME type: {detected_mime}")
        
        # Run tests based on service selection
        if service == "orchestrator":
            test_orchestrator(url)
            
        elif service == "summary":
            test_summary_service(content, detected_mime)
            
        elif service == "recommendations":
            test_recommendations_service(content, detected_mime)
            
        elif service == "visuals":
            test_visuals_service(content, detected_mime)
            
        elif service == "all":
            # Test individual services first
            test_summary_service(content, detected_mime)
            test_recommendations_service(content, detected_mime)
            test_visuals_service(content, detected_mime)
            
            # Then test orchestrator
            test_orchestrator(url, detected_mime)
            
        else:
            print(f"❌ Unknown service: {service}")
            show_help()
            return
            
        print("\n" + "="*50)
        print("✅ Testing completed!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
