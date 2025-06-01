# Google Ads API OAuth Setup Guide

This guide explains how to set up OAuth authentication for the Google Ads API in the Social Flood application.

## Prerequisites

1. A Google Ads account with administrative access
2. A Google Cloud Platform (GCP) project
3. Google Ads API access

## Step 1: Apply for a Google Ads Developer Token

1. Go to the [Google Ads API Center](https://ads.google.com/home/tools/manager-accounts/)
2. Sign in with your Google Ads account
3. Click on "API Center" in the left navigation menu
4. Click "Apply for a developer token"
5. Fill out the application form with your use case details
6. Submit the application and wait for approval (this can take a few days)

## Step 2: Create OAuth Credentials in Google Cloud Console

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Ads API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Ads API"
   - Click on it and click "Enable"
4. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Web application" as the application type
   - Add a name for your OAuth client
   - Add authorized redirect URIs (e.g., `http://localhost:8080/oauth2callback`)
   - Click "Create"
5. Note down the Client ID and Client Secret

## Step 3: Generate a Refresh Token

### Option 1: Using the OAuth Playground

1. Go to the [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the gear icon in the top right corner
3. Check "Use your own OAuth credentials"
4. Enter your Client ID and Client Secret
5. Close the settings
6. In the left panel, scroll down and select "Google Ads API v15" (or the latest version)
7. Select the scopes you need (at minimum, select `https://www.googleapis.com/auth/adwords`)
8. Click "Authorize APIs"
9. Sign in with your Google account and grant permissions
10. Click "Exchange authorization code for tokens"
11. Note down the Refresh Token

### Option 2: Using a Custom Script

You can also use a Python script to generate a refresh token:

```python
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/adwords']

# Path to your client secrets file
CLIENT_SECRETS_FILE = 'client_secrets.json'

# Create the flow
flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_SECRETS_FILE, 
    scopes=SCOPES
)

# Run the flow
credentials = flow.run_local_server(port=8080)

# Print the refresh token
print(f"Refresh token: {credentials.refresh_token}")
```

Save this as `generate_refresh_token.py` and create a `client_secrets.json` file with your OAuth credentials:

```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost:8080"],
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

Run the script with `python generate_refresh_token.py` and follow the prompts.

## Step 4: Configure Environment Variables

Add the following environment variables to your `.env` file:

```
GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token-here
GOOGLE_ADS_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=your-oauth-client-secret
GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token-here
GOOGLE_ADS_CUSTOMER_ID=1234567890  # without hyphens
```

## Step 5: Using with Docker

When using Docker, these environment variables are automatically passed to the container through the `env_file: .env` directive in the `docker-compose.yml` file.

Additionally, the variables are explicitly set in the environment section:

```yaml
environment:
  # Google Ads API OAuth credentials
  - GOOGLE_ADS_DEVELOPER_TOKEN=${GOOGLE_ADS_DEVELOPER_TOKEN}
  - GOOGLE_ADS_CLIENT_ID=${GOOGLE_ADS_CLIENT_ID}
  - GOOGLE_ADS_CLIENT_SECRET=${GOOGLE_ADS_CLIENT_SECRET}
  - GOOGLE_ADS_REFRESH_TOKEN=${GOOGLE_ADS_REFRESH_TOKEN}
  - GOOGLE_ADS_CUSTOMER_ID=${GOOGLE_ADS_CUSTOMER_ID}
```

## Troubleshooting

### Token Expiration

Refresh tokens don't expire unless:
- The user revokes access
- The token hasn't been used for 6 months
- The user changes their password

If you need to generate a new refresh token, repeat Step 3.

### API Access Issues

If you encounter API access issues:
1. Verify your developer token is approved and active
2. Check that your OAuth client has the Google Ads API enabled
3. Ensure your refresh token is valid
4. Verify you're using the correct customer ID

### Rate Limiting

The Google Ads API has rate limits. If you exceed these limits, your requests will be throttled. Implement retry logic with exponential backoff for production applications.

## Security Considerations

- Never commit your OAuth credentials to version control
- Use environment variables or a secure secrets manager
- Restrict access to your OAuth client in the Google Cloud Console
- Regularly audit who has access to your credentials
