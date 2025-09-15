# cli.py
import argparse

def main():
    parser = argparse.ArgumentParser(description="Social Flood CLI")
    parser.add_argument("--version", action="store_true", help="Show version information")
    parser.add_argument("--google-trends", help="Get Google Trends data for a keyword")
    args = parser.parse_args()

    if args.version:
        try:
            from app.__version__ import __version__, __author__, __description__
            print(f"Social Flood v{__version__}")
            print(f"Author: {__author__}")
            print(f"Description: {__description__}")
        except ImportError:
            print("Social Flood v0.1.0 (version info not available)")
        return

    if args.google_trends:
        keywords = args.google_trends.split(",")
        data = get_interest_over_time(keywords)
        print(data)

if __name__ == "__main__":
    main()
