# cli.py
import argparse

def main():
    parser = argparse.ArgumentParser(description="Social Flood CLI")
    parser.add_argument("--google-trends", help="Get Google Trends data for a keyword")
    args = parser.parse_args()

    if args.google_trends:
        keywords = args.google_trends.split(",")
        data = get_interest_over_time(keywords)
        print(data)

if __name__ == "__main__":
    main()
