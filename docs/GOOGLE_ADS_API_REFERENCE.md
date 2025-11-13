# Google Ads API Reference

**Quick reference guide for Social Flood Google Ads API endpoints**

---

## 🚀 Quick Start

### 1. Setup (One Time)

Follow **[docs/GOOGLE_ADS_SETUP.md](./GOOGLE_ADS_SETUP.md)** to get your credentials.

### 2. Configure `.env`

```bash
GOOGLE_ADS_ENABLED=true
GOOGLE_ADS_DEVELOPER_TOKEN=your_token_here
GOOGLE_ADS_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
GOOGLE_ADS_CUSTOMER_ID=1234567890
```

### 3. Start API

```bash
uvicorn app.main:app --reload
```

### 4. Test

Visit: http://localhost:8000/docs

---

## 📊 Endpoints Overview

| Endpoint | Purpose | Creative? |
|----------|---------|-----------|
| `/keyword-ideas` | Generate keyword suggestions | ❌ |
| `/keyword-metrics` | Get volume, CPC, competition | ❌ |
| `/keyword-historical-metrics` | Monthly search history | ❌ |
| `/campaigns` | Campaign performance data | ❌ |
| `/account-info` | Account details | ❌ |
| `/keyword-opportunities` | 🔥 **Combined Ads+Trends+Autocomplete** | ✅ |
| `/health` | Configuration check | ❌ |

---

## 🔑 Keyword Research Endpoints

### GET `/keyword-ideas`

Generate keyword suggestions from seed keywords.

**Parameters:**
```
keywords*      string   Comma-separated seed keywords
customer_id    string   Google Ads customer ID (optional)
language_id    string   Language ID (default: 1000=English)
location_ids   string   Comma-separated location IDs
page_size      integer  Results limit (default: 500, max: 1000)
```

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/google-ads/keyword-ideas?keywords=python+programming" \
  -H "X-API-Key: your-api-key"
```

**Example Response:**
```json
{
  "success": true,
  "customer_id": "1234567890",
  "seed_keywords": ["python programming"],
  "keyword_ideas": [
    {
      "keyword": "python tutorial",
      "avg_monthly_searches": 74000,
      "competition": "MEDIUM",
      "competition_index": 45,
      "low_bid": 0.85,
      "high_bid": 3.50,
      "currency_code": "USD"
    },
    {
      "keyword": "learn python",
      "avg_monthly_searches": 90500,
      "competition": "HIGH",
      "competition_index": 78,
      "low_bid": 1.20,
      "high_bid": 4.80,
      "currency_code": "USD"
    }
  ],
  "total_ideas": 500
}
```

**Use Cases:**
- Keyword discovery for SEO
- Finding related terms
- Content ideation
- PPC campaign planning

---

### GET `/keyword-metrics`

Get detailed metrics for specific keywords.

**Parameters:**
```
keywords*      string   Keywords to analyze (comma-separated)
customer_id    string   Google Ads customer ID (optional)
language_id    string   Language ID (default: 1000)
location_ids   string   Location IDs
```

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/google-ads/keyword-metrics?keywords=python,javascript,java" \
  -H "X-API-Key: your-api-key"
```

**Example Response:**
```json
{
  "success": true,
  "customer_id": "1234567890",
  "keywords": [
    {
      "keyword": "python",
      "avg_monthly_searches": 1220000,
      "competition": "HIGH",
      "competition_index": 92,
      "low_top_of_page_bid": 0.45,
      "high_top_of_page_bid": 2.30,
      "currency_code": "USD"
    },
    {
      "keyword": "javascript",
      "avg_monthly_searches": 1830000,
      "competition": "HIGH",
      "competition_index": 88,
      "low_top_of_page_bid": 0.52,
      "high_top_of_page_bid": 2.80,
      "currency_code": "USD"
    }
  ],
  "total_keywords": 3
}
```

**Use Cases:**
- Validate specific keywords
- Compare multiple keywords
- Budget planning for PPC
- Prioritize content topics

---

### GET `/keyword-historical-metrics`

Get monthly search volume history for keywords.

**Parameters:**
```
keywords*      string   Keywords to analyze
customer_id    string   Customer ID (optional)
language_id    string   Language ID (default: 1000)
location_ids   string   Location IDs
```

**Example Response:**
```json
[
  {
    "keyword": "python",
    "monthly_search_volumes": [
      {"year": 2024, "month": 1, "monthly_searches": 1350000},
      {"year": 2024, "month": 2, "monthly_searches": 1280000},
      {"year": 2024, "month": 3, "monthly_searches": 1420000}
    ],
    "avg_monthly_searches": 1350000,
    "competition": "HIGH"
  }
]
```

**Use Cases:**
- Identify seasonal trends
- Historical analysis
- Forecast planning
- Content calendar planning

---

## 📈 Campaign Data Endpoints

### GET `/campaigns`

List campaigns with performance metrics.

**Parameters:**
```
customer_id    string   Customer ID (optional)
date_range     enum     LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH, etc.
```

**Example Response:**
```json
{
  "success": true,
  "customer_id": "1234567890",
  "campaigns": [
    {
      "campaign_id": "12345",
      "campaign_name": "Brand Campaign",
      "status": "ENABLED",
      "impressions": 125000,
      "clicks": 3500,
      "cost": 1250.50,
      "conversions": 45.0,
      "conversion_value": 4500.00,
      "ctr": 0.028,
      "average_cpc": 0.36,
      "average_cpm": 10.00,
      "currency_code": "USD"
    }
  ],
  "total_campaigns": 5,
  "date_range": "LAST_30_DAYS"
}
```

**Use Cases:**
- Campaign performance monitoring
- ROI analysis
- Budget allocation
- Client reporting

---

### GET `/account-info`

Get Google Ads account information.

**Parameters:**
```
customer_id    string   Customer ID (optional)
```

**Example Response:**
```json
{
  "customer_id": "1234567890",
  "descriptive_name": "My Company Ads",
  "currency_code": "USD",
  "time_zone": "America/New_York",
  "is_manager": false
}
```

---

## 🔥 Creative Combined Endpoint

### GET `/keyword-opportunities`

**The most powerful endpoint** - combines data from:
1. ✅ Google Ads API (search volume, CPC, competition)
2. ✅ Google Trends API (interest trends, momentum)
3. ✅ Google Autocomplete API (related suggestions)

**Parameters:**
```
keywords*           string   Seed keywords
customer_id         string   Customer ID (optional)
include_trends      boolean  Include Trends data (default: true)
include_autocomplete boolean Include Autocomplete (default: true)
language_id         string   Language ID
location_ids        string   Location IDs
timeframe           string   Trends timeframe (default: "today 3-m")
```

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/google-ads/keyword-opportunities?keywords=python+programming&include_trends=true&include_autocomplete=true" \
  -H "X-API-Key: your-api-key"
```

**Example Response:**
```json
{
  "success": true,
  "opportunities": [
    {
      "keyword": "python tutorial",

      // From Google Ads
      "avg_monthly_searches": 74000,
      "competition": "MEDIUM",
      "competition_index": 45,
      "cpc_low": 0.85,
      "cpc_high": 3.50,

      // From Google Trends
      "trend_interest": 68.5,
      "trend_growth": "rising",

      // From Google Autocomplete
      "autocomplete_suggestions": [
        "python tutorial for beginners",
        "python tutorial pdf",
        "python tutorial youtube"
      ],

      // Computed Scores
      "opportunity_score": 78.5,
      "difficulty_score": 45.0,
      "commercial_intent": 60.0
    }
  ],
  "total_opportunities": 20,
  "data_sources": {
    "google_ads": true,
    "google_trends": true,
    "google_autocomplete": true
  }
}
```

**Scoring Explained:**

**Opportunity Score (0-100):**
- 40% Search Volume (higher is better)
- 30% Competition (lower is better)
- 20% Trend Growth (rising > stable > declining)
- 10% CPC Value (higher indicates commercial value)

**Difficulty Score (0-100):**
- Based on competition index
- Higher = harder to rank/compete

**Commercial Intent (0-100):**
- Based on CPC values
- Higher CPC = higher buyer intent
- Scale:
  - $10+ CPC = 100 (very high intent)
  - $5-10 = 80 (high intent)
  - $2-5 = 60 (medium intent)
  - $1-2 = 40 (low intent)
  - <$1 = 20 (very low intent)

**Use Cases:**
- 🎯 Content strategy planning
- 🎯 Identify low-competition opportunities
- 🎯 Discover trending keywords
- 🎯 Prioritize SEO efforts
- 🎯 Find high-intent commercial keywords
- 🎯 Competitive gap analysis

**Pro Tips:**
- Sort by `opportunity_score` DESC for best keywords
- Filter by `difficulty_score` < 50 for quick wins
- Look for `trend_growth: "rising"` for momentum plays
- High `commercial_intent` = good for PPC/affiliates

---

## 🏥 Health Check

### GET `/health`

Check if Google Ads API is properly configured.

**Example Response:**
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

---

## 🌍 Location IDs (Common)

| Location | ID |
|----------|-----|
| United States | 2840 |
| United Kingdom | 2826 |
| Canada | 2124 |
| Australia | 2036 |
| Germany | 2276 |
| France | 2250 |
| India | 2356 |
| Japan | 2392 |
| Brazil | 2076 |
| Mexico | 2484 |

[Full list](https://developers.google.com/google-ads/api/data/geotargets)

---

## 🗣️ Language IDs (Common)

| Language | ID |
|----------|-----|
| English | 1000 |
| Spanish | 1003 |
| French | 1002 |
| German | 1001 |
| Italian | 1004 |
| Portuguese | 1014 |
| Russian | 1019 |
| Japanese | 1005 |
| Chinese (Simplified) | 1017 |
| Korean | 1012 |

---

## 🎨 Multi-Account Usage

### Method 1: Environment Variable

```bash
# .env
GOOGLE_ADS_CUSTOMER_IDS=1234567890,9876543210,5555555555
```

Then call any endpoint - it will use the first ID by default.

### Method 2: Per-Request Override

Add `customer_id` parameter to any request:

```bash
curl "http://localhost:8000/api/v1/google-ads/keyword-ideas?keywords=python&customer_id=9876543210"
```

### Method 3: MCC (Manager) Account

```bash
# .env
GOOGLE_ADS_LOGIN_CUSTOMER_ID=your_mcc_id
GOOGLE_ADS_CUSTOMER_ID=client_account_id
```

---

## 💡 Use Case Examples

### Example 1: Content Strategy

**Goal:** Find low-competition keywords with good search volume

```python
import requests

response = requests.get(
    "http://localhost:8000/api/v1/google-ads/keyword-opportunities",
    params={
        "keywords": "python programming,web development",
        "include_trends": True,
        "include_autocomplete": True
    },
    headers={"X-API-Key": "your-api-key"}
)

opportunities = response.json()["opportunities"]

# Filter for low difficulty, decent volume
good_keywords = [
    opp for opp in opportunities
    if opp["difficulty_score"] < 50 and opp["avg_monthly_searches"] > 5000
]

# Sort by opportunity score
good_keywords.sort(key=lambda x: x["opportunity_score"], reverse=True)

print("Top opportunities:")
for kw in good_keywords[:10]:
    print(f"{kw['keyword']}: {kw['opportunity_score']}/100")
```

### Example 2: PPC Budget Planning

**Goal:** Get CPC estimates for campaign planning

```python
keywords = "python course,learn python,python tutorial"

response = requests.get(
    f"http://localhost:8000/api/v1/google-ads/keyword-metrics",
    params={"keywords": keywords},
    headers={"X-API-Key": "your-api-key"}
)

total_budget = 0
for kw in response.json()["keywords"]:
    avg_cpc = (kw["low_top_of_page_bid"] + kw["high_top_of_page_bid"]) / 2
    monthly_clicks = 1000  # Target clicks
    monthly_cost = avg_cpc * monthly_clicks
    total_budget += monthly_cost

    print(f"{kw['keyword']}: ${monthly_cost:.2f}/month for 1000 clicks")

print(f"\nTotal monthly budget: ${total_budget:.2f}")
```

### Example 3: Seasonal Trends

**Goal:** Identify seasonal keywords

```python
response = requests.get(
    "http://localhost:8000/api/v1/google-ads/keyword-historical-metrics",
    params={"keywords": "christmas gifts,valentine gifts,halloween costumes"},
    headers={"X-API-Key": "your-api-key"}
)

for keyword_data in response.json():
    volumes = keyword_data["monthly_search_volumes"]

    # Find peak month
    peak = max(volumes, key=lambda x: x["monthly_searches"])
    print(f"{keyword_data['keyword']}: peaks in month {peak['month']}")
```

---

## ⚠️ Common Errors

### Error: "Google Ads API is not enabled"

**Solution:** Set `GOOGLE_ADS_ENABLED=true` in `.env`

### Error: "Developer token is invalid"

**Solutions:**
1. Check for spaces/line breaks in token
2. Verify you copied the entire token
3. For production use, ensure token is approved

### Error: "Customer ID not found"

**Solutions:**
1. Remove hyphens: use `1234567890`, not `123-456-7890`
2. Verify account access
3. Check that you're using the correct customer ID

### Error: "Quota exceeded"

**Solutions:**
1. Wait a few minutes
2. Enable caching (default: enabled)
3. Reduce request frequency
4. Apply for higher quotas in Google Cloud Console

---

## 🔒 Best Practices

1. **Use Caching**
   - Enabled by default via Redis
   - Reduces API calls and quota usage

2. **Rate Limiting**
   - Built-in via slowapi
   - Max 1,000 requests/100 seconds per account

3. **Error Handling**
   - Always check `response.status_code`
   - Handle 503 (service unavailable) gracefully

4. **Security**
   - Never commit `.env` file
   - Rotate credentials periodically
   - Use HTTPS in production

5. **Performance**
   - Use `/keyword-metrics` for specific keywords
   - Use `/keyword-ideas` for discovery
   - Use `/keyword-opportunities` for comprehensive analysis

---

## 📚 Additional Resources

- [Setup Guide](./GOOGLE_ADS_SETUP.md) - Get your credentials
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Google Ads API Docs](https://developers.google.com/google-ads/api/docs/start)

---

**Questions?** Check `/api/v1/google-ads/health` to verify your setup!

**Ready to start?** Follow [GOOGLE_ADS_SETUP.md](./GOOGLE_ADS_SETUP.md) to get your credentials.
