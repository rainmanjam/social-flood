#!/usr/bin/env python
"""
Generate a refresh token for Google Ads API OAuth authentication.

This script helps you generate a refresh token for Google Ads API OAuth
authentication. It uses the Google Auth Library to create an OAuth flow
and obtain a refresh token.

Usage:
    python generate_google_ads_refresh_token.py

Requirements:
    - google-auth-oauthlib
    - google-auth
"""
import os
import json
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/adwords']

def create_client_secrets_file(client_id, client_secret, output_file='client_secrets.json'):
    """
    Create a client secrets file for OAuth authentication.
    
    Args:
        client_id: The OAuth client ID
        client_secret: The OAuth client secret
        output_file: The output file path
    """
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost:8080", "urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(client_config, f, indent=2)
    
    print(f"Created client secrets file: {output_file}")
    return output_file

def generate_refresh_token(client_secrets_file):
    """
    Generate a refresh token using the OAuth flow.
    
    Args:
        client_secrets_file: Path to the client secrets file
        
    Returns:
        str: The refresh token
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, 
        scopes=SCOPES
    )
    
    credentials = flow.run_local_server(port=8080)
    
    return credentials.refresh_token

def main():
    """Main function to generate a refresh token."""
    parser = argparse.ArgumentParser(description='Generate a refresh token for Google Ads API OAuth authentication')
    parser.add_argument('--client-id', help='OAuth client ID')
    parser.add_argument('--client-secret', help='OAuth client secret')
    parser.add_argument('--client-secrets-file', help='Path to client secrets file')
    
    args = parser.parse_args()
    
    # Check if client secrets file is provided
    if args.client_secrets_file:
        client_secrets_file = args.client_secrets_file
    # Check if client ID and client secret are provided
    elif args.client_id and args.client_secret:
        client_secrets_file = create_client_secrets_file(args.client_id, args.client_secret)
    # Check if client ID and client secret are in environment variables
    elif os.environ.get('GOOGLE_ADS_CLIENT_ID') and os.environ.get('GOOGLE_ADS_CLIENT_SECRET'):
        client_secrets_file = create_client_secrets_file(
            os.environ.get('GOOGLE_ADS_CLIENT_ID'),
            os.environ.get('GOOGLE_ADS_CLIENT_SECRET')
        )
    # Prompt for client ID and client secret
    else:
        print("No client secrets file or client ID and client secret provided.")
        client_id = input("Enter your OAuth client ID: ")
        client_secret = input("Enter your OAuth client secret: ")
        client_secrets_file = create_client_secrets_file(client_id, client_secret)
    
    # Generate the refresh token
    refresh_token = generate_refresh_token(client_secrets_file)
    
    print("\n" + "="*50)
    print("Refresh token generated successfully!")
    print("="*50)
    print(f"Refresh token: {refresh_token}")
    print("="*50)
    print("\nAdd this to your .env file:")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    print("="*50)

if __name__ == "__main__":
    main()
