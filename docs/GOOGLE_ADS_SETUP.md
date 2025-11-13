# Google Ads API Setup Guide

**Complete step-by-step guide to get your Google Ads API credentials**

This guide will walk you through obtaining all the credentials needed to use the Google Ads API integration in Social Flood.

---

## 📋 Prerequisites

Before you begin, make sure you have:

1. ✅ A Google Ads account (if you don't have one, create it at [ads.google.com](https://ads.google.com))
2. ✅ A Google Cloud Project (we'll create this in Step 1)
3. ✅ Basic access to your Google Ads account (you need to be able to view campaigns)

**Note:** You do NOT need to have active campaigns to use the Keyword Planner API!

---

## 🎯 What You'll Get

By the end of this guide, you'll have these 5 credentials:

1. **Developer Token** - Identifies your application to Google
2. **Client ID** - OAuth 2.0 client identifier
3. **Client Secret** - OAuth 2.0 client secret
4. **Refresh Token** - Long-lived token for API access
5. **Customer ID** - Your Google Ads account ID

---

## 📝 Step 1: Create a Google Cloud Project

### 1.1 Go to Google Cloud Console

Visit: https://console.cloud.google.com/

### 1.2 Create New Project

1. Click the project dropdown at the top of the page
2. Click "New Project"
3. Enter project name: `social-flood-ads-api` (or any name you prefer)
4. Click "Create"
5. Wait for the project to be created (about 30 seconds)
6. **Select your new project** from the dropdown

---

## 🔑 Step 2: Enable Google Ads API

### 2.1 Enable the API

1. In Google Cloud Console, go to: https://console.cloud.google.com/apis/library
2. Search for "Google Ads API"
3. Click on "Google Ads API"
4. Click "Enable"
5. Wait for it to enable (about 10 seconds)

---

## 🎫 Step 3: Create OAuth 2.0 Credentials

### 3.1 Go to Credentials Page

1. Navigate to: https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" button
3. Select "OAuth client ID"

### 3.2 Configure OAuth Consent Screen

If this is your first time, you'll be prompted to configure the consent screen:

1. Click "Configure Consent Screen"
2. Select "External" (unless you have a Google Workspace organization)
3. Click "Create"

**Fill in the required fields:**
- **App name:** Social Flood API
- **User support email:** Your email address
- **Developer contact:** Your email address
4. Click "Save and Continue"
5. On "Scopes" page, click "Save and Continue" (we don't need additional scopes)
6. On "Test users" page, **add your email address as a test user**
7. Click "Save and Continue"
8. Review and click "Back to Dashboard"

### 3.3 Create OAuth Client ID

Now that consent screen is configured:

1. Go back to: https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" → "OAuth client ID"
3. **Application type:** Select "Desktop app"
4. **Name:** Enter "Social Flood Desktop Client"
5. Click "Create"

### 3.4 Save Your Credentials

You'll see a popup with:
- **Client ID** (looks like: `123456789-abcdefg.apps.googleusercontent.com`)
- **Client Secret** (looks like: `GOCSPX-abcdefghijklmnop`)

**✅ SAVE THESE!** You'll need them later.

You can also download them as JSON, but we only need these two values.

---

## 🎟️ Step 4: Get Your Developer Token

### 4.1 Go to Google Ads

1. Visit: https://ads.google.com/
2. Log in with the same Google account

### 4.2 Navigate to API Center

1. Click the **Tools & Settings** icon (wrench icon) in the top right
2. Under "Setup", click "API Center"

**If you don't see API Center:**
- Make sure you're logged into the correct Google Ads account
- You may need to accept Google Ads terms if this is a new account

### 4.3 Request Developer Token

You'll see a section for "Developer token":

**For Development/Testing:**
1. Your account will have a **test developer token** automatically
2. This looks like: `ABcdEFghIJklMNopQRstUVwx`
3. You can copy this token immediately

**For Production:**
1. Click "Request developer token"
2. Fill out the application form:
   - **Company/Organization name**
   - **Description of how you'll use the API**
   - **Website** (can be your company site)
3. Submit the application
4. Google typically approves within 1-2 business days

**⚠️ IMPORTANT:**
- The **test token works for basic keyword research** (which is what you need!)
- You only need production approval if you're managing campaigns programmatically
- For keyword research and read-only data, the test token is sufficient

**✅ SAVE YOUR DEVELOPER TOKEN!**

---

## 🔄 Step 5: Generate Refresh Token

This is the most technical step, but we'll make it easy!

### 5.1 Install Google Ads API Python Library (if not already)

```bash
pip install google-ads
```

### 5.2 Create Authentication Script

Create a file called `generate_refresh_token.py`:

```python
#!/usr/bin/env python3
"""Generate Google Ads API refresh token."""

from google_auth_oauthlib.flow import InstalledAppFlow

# Replace these with your Client ID and Client Secret from Step 3
CLIENT_ID = "YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"

# Google Ads API scope
SCOPES = ["https://www.googleapis.com/auth/adwords"]

def main():
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://accounts.google.com/o/oauth2/token",
            }
        },
        scopes=SCOPES,
    )

    # This will open a browser window
    flow.run_local_server(port=8080, prompt="consent")

    print("\n" + "="*50)
    print("SUCCESS! Here's your refresh token:")
    print("="*50)
    print(f"\nREFRESH_TOKEN: {flow.credentials.refresh_token}\n")
    print("="*50)
    print("\nCopy this token and save it in your .env file!")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
```

### 5.3 Run the Script

```bash
python generate_refresh_token.py
```

**What happens:**
1. A browser window will open
2. Sign in with your Google account (the one with Google Ads access)
3. You'll see a consent screen saying "Social Flood API wants to access your Google Ads account"
4. Click "Allow"
5. You might see a warning "Google hasn't verified this app" - click "Advanced" → "Go to Social Flood API (unsafe)"
   - This is normal for apps in development
6. The script will print your **refresh token**

**✅ SAVE YOUR REFRESH TOKEN!** It looks like: `1//abcdefghijklmnopqrstuvwxyz`

---

## 🆔 Step 6: Get Your Customer ID

### 6.1 Find Your Customer ID

1. Go to https://ads.google.com/
2. Look at the top right corner
3. You'll see a number like `123-456-7890`
4. **Remove the hyphens:** `1234567890`

**That's your Customer ID!**

**✅ SAVE YOUR CUSTOMER ID!** (10 digits, no hyphens)

---

## 🔧 Step 7: Configure Social Flood

### 7.1 Create/Update .env File

In your Social Flood project root, create or edit `.env`:

```bash
# Google Ads API Configuration
GOOGLE_ADS_ENABLED=true
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here
GOOGLE_ADS_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=your_client_secret_here
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token_here
GOOGLE_ADS_CUSTOMER_ID=1234567890

# Optional: For MCC (Manager) accounts
# GOOGLE_ADS_LOGIN_CUSTOMER_ID=9876543210

# For multiple accounts (comma-separated)
# GOOGLE_ADS_CUSTOMER_IDS=1234567890,9876543210,5555555555
```

### 7.2 Example .env Configuration

```bash
# Example (replace with your actual values)
GOOGLE_ADS_ENABLED=true
GOOGLE_ADS_DEVELOPER_TOKEN=ABcdEFghIJklMNopQRstUVwx
GOOGLE_ADS_CLIENT_ID=123456789-abc123def456.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=GOCSPX-abcdefghijklmnop
GOOGLE_ADS_REFRESH_TOKEN=1//0abcdefghijklmnopqrstuvwxyz
GOOGLE_ADS_CUSTOMER_ID=1234567890
```

---

## ✅ Step 8: Test Your Setup

### 8.1 Start the API

```bash
uvicorn app.main:app --reload
```

### 8.2 Test Health Endpoint

Visit: http://localhost:8000/api/v1/google-ads/health

You should see:
```json
{
  "status": "healthy",
  "google_ads_enabled": true,
  "configuration": {
    "developer_token": true,
    "client_id": true,
    "client_secret": true,
    "refresh_token": true,
    "customer_id": true,
    "enabled": true
  },
  "account_accessible": true,
  "message": "Google Ads API is properly configured"
}
```

### 8.3 Test Keyword Ideas

Visit: http://localhost:8000/docs

Try the `/api/v1/google-ads/keyword-ideas` endpoint with:
```
keywords: python programming
```

You should get keyword suggestions with search volumes!

---

## 🎯 Multiple Accounts Setup

If you manage multiple Google Ads accounts:

### Method 1: Environment Variable (Recommended)

```bash
GOOGLE_ADS_CUSTOMER_IDS=1234567890,9876543210,5555555555
```

### Method 2: Pass in API Request

Add `?customer_id=1234567890` to any endpoint.

### Method 3: MCC (Manager) Account

If you have an MCC account:

```bash
GOOGLE_ADS_LOGIN_CUSTOMER_ID=your_mcc_customer_id
GOOGLE_ADS_CUSTOMER_ID=client_account_id
```

---

## 🐛 Troubleshooting

### Issue: "Developer token is invalid"

**Solution:**
- Make sure you copied the entire token
- Remove any spaces or line breaks
- For production use, ensure your token application is approved

### Issue: "Authentication failed"

**Solutions:**
1. Regenerate your refresh token (Step 5)
2. Make sure the Google account you authenticated with has access to the Google Ads account
3. Check that your Client ID and Client Secret are correct

### Issue: "Customer ID not found"

**Solutions:**
- Remove hyphens from Customer ID (use `1234567890`, not `123-456-7890`)
- Ensure the Google account you authenticated with has access to this customer ID
- Try using the full customer ID path

### Issue: "Test account" warning

**This is normal!**
- Test developer tokens work fine for keyword research
- You only need production approval for managing campaigns
- All read-only features work with test tokens

### Issue: "Quota exceeded"

**Solution:**
- Google Ads API has rate limits
- Enable caching (should be enabled by default)
- Wait a few minutes between large requests
- For high-volume usage, apply for higher quotas

---

## 📊 API Limits

### Test Developer Token

- **15,000 operations per day**
- Perfect for keyword research and development
- Enough for most use cases

### Production Developer Token

- **Unlimited operations** (subject to rate limits)
- Required for campaign management
- Takes 1-2 business days to approve

### Rate Limits

- **Max 1,000 requests per 100 seconds** per account
- Social Flood has built-in caching to help with this

---

## 🔒 Security Best Practices

1. **Never commit .env to git**
   - Already in `.gitignore`

2. **Use environment variables**
   - Don't hardcode credentials

3. **Rotate tokens periodically**
   - Regenerate refresh token every 6-12 months

4. **Limit token scope**
   - Only use the adwords scope (read-only for keyword research)

5. **Monitor usage**
   - Check Google Cloud Console for unusual activity

---

## 📚 Additional Resources

### Official Documentation

- [Google Ads API Documentation](https://developers.google.com/google-ads/api/docs/start)
- [Google Ads API Python Client](https://github.com/googleads/google-ads-python)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)

### Google Ads Help

- [API Center](https://ads.google.com/aw/apicenter)
- [Developer Token](https://developers.google.com/google-ads/api/docs/get-started/dev-token)
- [OAuth Setup](https://developers.google.com/google-ads/api/docs/oauth/overview)

### Social Flood Documentation

- [API Documentation](http://localhost:8000/docs)
- [Google Ads API Endpoints](/docs/API_REFERENCE.md)

---

## 🎉 Success!

You're now ready to use the Google Ads API integration!

**Try these endpoints:**

1. **Keyword Ideas** - `/api/v1/google-ads/keyword-ideas?keywords=python`
2. **Keyword Metrics** - `/api/v1/google-ads/keyword-metrics?keywords=python,javascript`
3. **Combined Analysis** - `/api/v1/google-ads/keyword-opportunities?keywords=python`

The combined endpoint merges:
- ✅ Google Ads keyword data
- ✅ Google Trends interest
- ✅ Google Autocomplete suggestions

For the ultimate keyword research experience! 🚀

---

## 💬 Need Help?

If you encounter issues not covered in troubleshooting:

1. Check the API health endpoint: `/api/v1/google-ads/health`
2. Review logs for detailed error messages
3. Verify all 5 credentials are correctly set in `.env`
4. Ensure you're using the correct Google Ads account

---

**Last Updated:** 2025-11-13
**Version:** 1.0.0
