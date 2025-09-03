import argparse
import json
from structuredOutput.orchestrator import IntelligenceOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Run intelligence layer analysis on a file URL or raw text.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file-url", help="HTTP(S) URL of a file to analyze (e.g., PDF)")
    group.add_argument("--text", help="Raw text to analyze")
    parser.add_argument("--mime", help="Optional MIME type for file (e.g., application/pdf)")
    parser.add_argument("--output", choices=["pretty", "json"], default="pretty", 
                        help="Output format (pretty or json)")
    args = parser.parse_args()

    orch = IntelligenceOrchestrator()
    try:
        results = orch.analyze(file_url=args.file_url, content=args.text, mime_type=args.mime)
    except Exception as e:
        print("Error during analysis:", str(e))
        return
    
    if args.output == "json":
        # Convert results to JSON (handles Pydantic models)
        json_results = {}
        for service, result in results.items():
            if result.success:
                if hasattr(result.data, "model_dump"):
                    json_results[service] = result.data.model_dump()
                elif hasattr(result.data, "dict"):
                    json_results[service] = result.data.dict()
                elif isinstance(result.data, list):
                    # Handle list of Pydantic models (like ChartSpec)
                    list_data = []
                    for item in result.data:
                        if hasattr(item, "model_dump"):
                            list_data.append(item.model_dump())
                        elif hasattr(item, "dict"):
                            list_data.append(item.dict())
                        else:
                            list_data.append(str(item))
                    json_results[service] = list_data
                else:
                    json_results[service] = str(result.data)
            else:
                json_results[service] = {"error": result.error_message}
                
        print(json.dumps(json_results, indent=2))
    else:
        # Pretty print results
        for service, result in results.items():
            print(f"\n--- {service.upper()} ---")
            if result.success:
                # For visuals, print a more readable format
                if service == "visuals":
                    for i, chart in enumerate(result.data):
                        print(f"Chart {i+1}: {chart.chart_type}")
                        if chart.purpose:
                            print(f"Purpose: {chart.purpose}")
                        if chart.x_axis:
                            print(f"X-axis: {chart.x_axis}")
                        if chart.y_axis:
                            print(f"Y-axis: {chart.y_axis}")
                        print()
                else:
                    print(result.data)

if __name__ == "__main__":
    main()