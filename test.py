#!/usr/bin/env python3
"""
Test script for Intelligence Layer services with URL or local file input.

Usage:
    python test.py <URL or local file path> [service]

Examples:
    python test.py "https://example.com/file.csv"
    python test.py "https://example.com/file.pdf" summary
    python test.py "https://example.com/file.csv" recommendations
    python test.py "https://example.com/file.pdf" visuals
    python test.py "https://example.com/file.csv" orchestrator
    python test.py "/path/to/local/file.csv"
    python test.py "/path/to/local/file.pdf" summary
"""

import sys
import os
import requests
import time
import traceback

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def download_file(path: str, timeout: int = 30):
    """Download file from URL or load from local file and return content + inferred MIME type."""
    # Check if the path is a URL or a local file path
    if path.startswith(('http://', 'https://')):
        print(f"📥 Downloading from URL: {path}")
        
        try:
            response = requests.get(path, timeout=timeout)
            response.raise_for_status()
            content = response.content
            
            # Infer MIME type from URL or Content-Type header
            mime_type = response.headers.get('content-type', '')
            if not mime_type:
                if path.lower().endswith('.pdf'):
                    mime_type = 'application/pdf'
                elif path.lower().endswith('.csv'):
                    mime_type = 'text/csv'
                elif path.lower().endswith(('.txt', '.md')):
                    mime_type = 'text/plain'
                else:
                    mime_type = 'application/octet-stream'
            
            print(f"✅ Downloaded {len(content):,} bytes (MIME: {mime_type})")
            return content, mime_type
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            raise
    else:
        # Local file path
        print(f"📂 Loading local file: {path}")
        try:
            with open(path, 'rb') as f:
                content = f.read()
            
            # Infer MIME type from file extension
            if path.lower().endswith('.pdf'):
                mime_type = 'application/pdf'
            elif path.lower().endswith('.csv'):
                mime_type = 'text/csv'
            elif path.lower().endswith(('.txt', '.md')):
                mime_type = 'text/plain'
            else:
                mime_type = 'application/octet-stream'
                
            print(f"✅ Loaded {len(content):,} bytes (MIME: {mime_type})")
            return content, mime_type
            
        except Exception as e:
            print(f"❌ File loading failed: {e}")
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


def test_orchestrator(path, mime_type=None):
    """Test all services together using the orchestrator."""
    print("\n" + "="*50)
    print("🎼 TESTING ORCHESTRATOR (ALL SERVICES)")
    print("="*50)
    
    try:
        from structuredOutput.orchestrator import IntelligenceOrchestrator
        
        # Check if the path is a URL or a local file path
        if path.startswith(('http://', 'https://')):
            # URL: use file_url parameter
            start_time = time.time()
            orchestrator = IntelligenceOrchestrator()
            results = orchestrator.analyze(file_url=path, mime_type=mime_type)
        else:
            # Local file: load the content and use content parameter
            with open(path, 'rb') as f:
                content = f.read()
            
            # For text files, decode the binary content
            if path.lower().endswith(('.txt', '.csv', '.md', '.json')):
                content = content.decode('utf-8')
                
            start_time = time.time()
            orchestrator = IntelligenceOrchestrator()
            results = orchestrator.analyze(content=content, mime_type=mime_type)
            
        elapsed = time.time() - start_time
        
        print(f"⏱️  Total execution time: {elapsed:.2f}s")
        
        for service_name, result in results.items():
            print(f"\n--- {service_name.upper()} ---")
            if not result.success:
                print(f"❌ Error: {result.error_message}")
                continue
                
            print(f"✅ Success: Execution time: {result.execution_time:.2f}s")
            
            if service_name == 'summary':
                title = getattr(result.data, 'title', 'None')
                summary = getattr(result.data, 'summary', '')
                key_points = getattr(result.data, 'key_points', [])
                
                print(f"   Title: {title}")
                print(f"   Summary: {summary[:100]}...")
                print(f"   Key Points: {len(key_points)} items")
                
            elif service_name == 'recommendations':
                recs = getattr(result.data, 'recommendations', [])
                print(f"   Recommendations: {len(recs)} items")
                for i, rec in enumerate(recs[:3], 1):
                    print(f"      {i}. {rec}")
                if len(recs) > 3:
                    print(f"      ... and {len(recs) - 3} more")
                    
            elif service_name == 'visuals':
                charts = result.data
                print(f"   Charts: {len(charts)} items")
                for i, chart in enumerate(charts[:2], 1):
                    print(f"      {i}. {chart.chart_type}")
                    if chart.purpose:
                        print(f"         Purpose: {chart.purpose[:50]}...")
                if len(charts) > 2:
                    print(f"      ... and {len(charts) - 2} more")
                    
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
    
    path = sys.argv[1]
    service = sys.argv[2] if len(sys.argv) > 2 else 'all'
    
    print("🚀 Intelligence Layer Service Tester")
    print("=" * 50)
    print(f"Path/URL: {path}")
    print(f"Service: {service}")
    
    try:
        # Download file or load local file for individual service tests
        if service != 'orchestrator':
            content, detected_mime = download_file(path)
            print(f"🔧 Using MIME type: {detected_mime}")
        
        # Run tests based on service selection
        if service == "orchestrator":
            test_orchestrator(path)
            
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
            test_orchestrator(path, detected_mime)
            
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
