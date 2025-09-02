import argparse
from structuredOutput.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(description="Run intelligence layer analysis on a file URL or raw text.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file-url", help="HTTP(S) URL of a file to analyze (e.g., PDF)")
    group.add_argument("--text", help="Raw text to analyze")
    parser.add_argument("--mime", help="Optional MIME type for file (e.g., application/pdf)")
    args = parser.parse_args()

    orch = Orchestrator()
    try:
        results = orch.analyze(file_url=args.file_url, text=args.text, mime_type=args.mime)
    except Exception as e:
        print("Error during analysis:", str(e))
        return

    # Print results simply; these are Pydantic models or dicts
    for k, v in results.items():
        print(f"--- {k.upper()} ---")
        print(v)


if __name__ == "__main__":
    main()