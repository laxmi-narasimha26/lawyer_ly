# 🔍 Google Custom Search Engine (CSE) Setup Guide

Complete guide to enable web search capabilities in the Indian Legal AI Assistant, allowing it to search the internet for latest legal information just like ChatGPT with browsing.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Create Google Cloud Project](#step-1-create-google-cloud-project)
4. [Step 2: Enable Custom Search API](#step-2-enable-custom-search-api)
5. [Step 3: Get API Key](#step-3-get-api-key)
6. [Step 4: Create Custom Search Engine](#step-4-create-custom-search-engine)
7. [Step 5: Configure Application](#step-5-configure-application)
8. [Step 6: Test Integration](#step-6-test-integration)
9. [Pre-Configured Legal Sites](#pre-configured-legal-sites)
10. [Usage Examples](#usage-examples)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Indian Legal AI Assistant can now search the internet for latest legal updates, amendments, and case law using Google Custom Search Engine. This enables:

- **Real-time Legal Updates**: Search for latest amendments, notifications, and judgments
- **Hybrid Search**: Combine knowledge base with live web results
- **Smart Query Routing**: Automatically detects when web search is needed
- **Authoritative Sources**: Pre-configured to search 16+ trusted Indian legal websites

**Key Features:**
- ✅ Automatic detection of temporal queries (latest, recent, 2024, 2025, etc.)
- ✅ Restricted search to Indian legal websites for accuracy
- ✅ Citation tracking for web results
- ✅ Fallback to vector DB if web search fails
- ✅ Configurable hybrid or web-only modes

---

## Prerequisites

- Google account (Gmail)
- Credit card for Google Cloud (free tier available, 100 searches/day free)
- Application already deployed locally

---

## Step 1: Create Google Cloud Project

### 1.1 Go to Google Cloud Console
Visit: https://console.cloud.google.com/

### 1.2 Create New Project
1. Click the project dropdown at the top
2. Click "New Project"
3. Enter project name: **"Indian-Legal-AI-Search"**
4. Click "Create"
5. Wait for project creation (30 seconds)

### 1.3 Select Your Project
1. Click the project dropdown
2. Select "Indian-Legal-AI-Search"

---

## Step 2: Enable Custom Search API

### 2.1 Navigate to API Library
1. Click the hamburger menu (☰) → "APIs & Services" → "Library"
2. Or visit: https://console.cloud.google.com/apis/library

### 2.2 Search for Custom Search API
1. In the search box, type: **"Custom Search API"**
2. Click on "Custom Search API" (by Google)
3. Click the blue **"ENABLE"** button
4. Wait for activation (~10 seconds)

You should see "API enabled" confirmation.

---

## Step 3: Get API Key

### 3.1 Create API Credentials
1. Go to: https://console.cloud.google.com/apis/credentials
2. Click **"+ CREATE CREDENTIALS"** → "API key"
3. Your API key will be generated immediately

### 3.2 Secure Your API Key (Recommended)
1. Click "Edit API key" (pencil icon)
2. Under "API restrictions", select "Restrict key"
3. Choose **"Custom Search API"** from the dropdown
4. Click "Save"

### 3.3 Copy API Key
```
Example: AIzaSyDw8xK9L_Hx5JfT3pZ6mY4nRqV8wE2cK1o
```

**⚠️ IMPORTANT**: Keep this key safe! You'll need it for configuration.

---

## Step 4: Create Custom Search Engine

### 4.1 Go to Programmable Search Engine
Visit: https://programmablesearchengine.google.com/

### 4.2 Create New Search Engine
1. Click **"Get started"** or **"Add"**
2. Fill in the form:

**Search engine name:**
```
Indian Legal Knowledge Search
```

**What to search:**
- Select: **"Search the entire web"**

**OR for restricted search (recommended):**
- Select: **"Search specific sites"**
- Add initial site: `indiankanoon.org`

3. Click **"Create"**

### 4.3 Configure Search Engine

After creation, you'll see your Search Engine ID. Click "Customize" to configure:

#### 4.3.1 Basic Settings
- **Name**: Indian Legal Knowledge Search
- **Description**: Searches Indian legal websites for latest legal information

#### 4.3.2 Sites to Search (Important!)

Click "Sites to search" → "Add"

**Add all these Indian legal websites:**

```
indiankanoon.org
sci.gov.in
egazette.nic.in
legislative.gov.in
lawmin.gov.in
ncdrc.nic.in
delhihighcourt.nic.in
bombayhighcourt.nic.in
mhc.tn.gov.in
highcourtofkerala.nic.in
causelists.nic.in
latestlaws.com
livelaw.in
barandbench.com
scconline.com
manupatrafast.in
```

**Tip**: Add one per line in the textarea, then click "Include all"

#### 4.3.3 Search Features
- Enable: **"Search the entire web but emphasize included sites"** (recommended)
- OR: **"Search only included sites"** (more restrictive)

#### 4.3.4 Advanced Settings
- **SafeSearch**: Off (for legal content)
- **Language**: English
- **Country**: India

### 4.4 Get Search Engine ID

1. Go to: https://programmablesearchengine.google.com/
2. Click on your search engine
3. Click "Setup" → "Basic"
4. Copy the **"Search engine ID"**

```
Example: 01234567890abcdef:ghijklmnop
```

**Format**: Usually looks like `<numbers>:<letters>`

---

## Step 5: Configure Application

Now that you have:
- ✅ API Key: `AIzaSy...`
- ✅ Search Engine ID: `01234567...`

Let's configure the application!

### Option 1: Environment Variables (Recommended)

**Windows:**
```bash
set ENABLE_WEB_SEARCH=true
set GOOGLE_SEARCH_ENABLED=true
set GOOGLE_SEARCH_API_KEY=AIzaSyDw8xK9L_Hx5JfT3pZ6mY4nRqV8wE2cK1o
set GOOGLE_SEARCH_ENGINE_ID=01234567890abcdef:ghijklmnop
```

**Linux/Mac:**
```bash
export ENABLE_WEB_SEARCH=true
export GOOGLE_SEARCH_ENABLED=true
export GOOGLE_SEARCH_API_KEY=AIzaSyDw8xK9L_Hx5JfT3pZ6mY4nRqV8wE2cK1o
export GOOGLE_SEARCH_ENGINE_ID=01234567890abcdef:ghijklmnop
```

Then restart the application:
```bash
docker compose -f docker-compose.local.app.yml down
docker compose -f docker-compose.local.app.yml up -d
```

### Option 2: Configuration File

Create/edit `backend/.env.local`:

```env
# Web Search Configuration
ENABLE_WEB_SEARCH=true
GOOGLE_SEARCH_ENABLED=true
GOOGLE_SEARCH_API_KEY=AIzaSyDw8xK9L_Hx5JfT3pZ6mY4nRqV8wE2cK1o
GOOGLE_SEARCH_ENGINE_ID=01234567890abcdef:ghijklmnop

# Optional: Fine-tune search behavior
GOOGLE_SEARCH_MAX_RESULTS=5
GOOGLE_SEARCH_RESTRICT_LEGAL=true
GOOGLE_SEARCH_AUTO_DETECT=true
GOOGLE_SEARCH_COMBINE_VECTOR=true
GOOGLE_SEARCH_CACHE_TTL=3600
```

Then rebuild and restart:
```bash
docker compose -f docker-compose.local.app.yml down
docker compose -f docker-compose.local.app.yml up -d --build backend
```

### Verify Configuration

Check the backend logs:
```bash
docker logs legal-ai-backend-local --tail=20
```

You should see:
```
✅ Google Custom Search Engine enabled (16 legal sites configured)
```

---

## Step 6: Test Integration

### Test 1: Basic Web Search Query

Test with a query containing temporal keywords:

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the latest amendments to the Indian Penal Code in 2024?",
    "mode": "qa",
    "user_id": "test_user"
  }'
```

**Expected behavior:**
- Should trigger web search (query contains "latest" and "2024")
- Returns answer with web citations
- Citations include `"type": "web_search"`

### Test 2: Force Web Search

Add a note in your query to test:

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "recent Supreme Court judgments on data privacy",
    "mode": "qa",
    "user_id": "test_user"
  }'
```

### Test 3: Hybrid Search

Query that should use both knowledge base and web:

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is Article 21 and how has it been interpreted recently?",
    "mode": "qa",
    "user_id": "test_user"
  }'
```

**Expected behavior:**
- Uses knowledge base for Article 21 definition
- Uses web search for recent interpretations
- Combines both in answer

### Test 4: Vector-Only Query

Query without temporal keywords:

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the Indian Penal Code?",
    "mode": "qa",
    "user_id": "test_user"
  }'
```

**Expected behavior:**
- Should NOT trigger web search (no temporal keywords)
- Uses only vector database
- Faster response time

---

## Pre-Configured Legal Sites

The application comes pre-configured with 16 trusted Indian legal websites:

### Government & Official Sources
1. **sci.gov.in** - Supreme Court of India
2. **egazette.nic.in** - Official Gazette of India
3. **legislative.gov.in** - Legislative Department
4. **lawmin.gov.in** - Ministry of Law and Justice
5. **ncdrc.nic.in** - National Consumer Disputes Redressal Commission

### High Courts
6. **delhihighcourt.nic.in** - Delhi High Court
7. **bombayhighcourt.nic.in** - Bombay High Court
8. **mhc.tn.gov.in** - Madras High Court
9. **highcourtofkerala.nic.in** - Kerala High Court
10. **causelists.nic.in** - Court Cause Lists

### Legal Databases & News
11. **indiankanoon.org** - Comprehensive case law database
12. **latestlaws.com** - Latest legal updates
13. **livelaw.in** - Legal news and updates
14. **barandbench.com** - Legal news and analysis
15. **scconline.com** - Supreme Court cases
16. **manupatrafast.in** - Legal research platform

You can add more sites through the Google CSE console.

---

## Usage Examples

### Queries That Trigger Web Search Automatically

The system automatically detects these query patterns:

**Temporal Keywords:**
- "latest amendments to..."
- "recent judgment on..."
- "current status of..."
- "What's new in 2024..."
- "this year's updates..."
- "announced today..."
- "last month's notification..."

**Example Queries:**
```
1. "What are the latest amendments to the Motor Vehicles Act?"
2. "Recent Supreme Court judgment on environmental laws"
3. "Current guidelines for GST compliance"
4. "Latest gazette notifications from 2024"
5. "What amendments were announced this week?"
```

### Queries That Use Vector Database Only

**Foundational Legal Questions:**
```
1. "What is Section 302 IPC?"
2. "Explain the concept of res judicata"
3. "What are the fundamental rights in India?"
4. "Define consideration in contract law"
```

### Hybrid Queries (Both Sources)

```
1. "What is Article 19 and how has it been interpreted recently?"
2. "Explain defamation law and recent cases in 2024"
3. "What are the bail provisions and latest Supreme Court guidelines?"
```

---

## Configuration Options

### Advanced Settings

You can fine-tune web search behavior with environment variables:

```env
# Number of web results to fetch (1-10)
GOOGLE_SEARCH_MAX_RESULTS=5

# Restrict search to legal sites only (true/false)
GOOGLE_SEARCH_RESTRICT_LEGAL=true

# Auto-detect temporal queries (true/false)
GOOGLE_SEARCH_AUTO_DETECT=true

# Combine web results with vector DB (true/false)
GOOGLE_SEARCH_COMBINE_VECTOR=true

# Use web search as fallback if vector confidence is low (true/false)
GOOGLE_SEARCH_USE_FALLBACK=true

# Minimum vector confidence to skip web search (0.0-1.0)
GOOGLE_SEARCH_VECTOR_THRESHOLD=0.6

# Cache web results (true/false)
GOOGLE_SEARCH_CACHE_RESULTS=true

# Cache TTL in seconds
GOOGLE_SEARCH_CACHE_TTL=3600
```

### Search Strategies

The system uses these strategies automatically:

1. **vector_only**: Use only knowledge base (default for foundational queries)
2. **web_only**: Use only web search (for highly temporal queries)
3. **hybrid**: Combine both sources (for queries needing both context)
4. **vector_fallback**: Try web first, fall back to vector if web fails

---

## Troubleshooting

### Issue 1: "Google Search service disabled"

**Symptoms:**
```
ℹ️ Web search feature disabled in configuration
```

**Solution:**
1. Verify environment variables are set:
   ```bash
   echo $GOOGLE_SEARCH_ENABLED  # Should be "true"
   echo $ENABLE_WEB_SEARCH      # Should be "true"
   ```
2. Restart the application
3. Check logs for initialization message

### Issue 2: "API key not valid"

**Symptoms:**
```
❌ Error initializing Google Search: API key not valid
```

**Solution:**
1. Verify API key is correct (no extra spaces)
2. Check API key restrictions in Google Cloud Console
3. Ensure Custom Search API is enabled in your project
4. Regenerate API key if needed

### Issue 3: "Search engine not found"

**Symptoms:**
```
Invalid Value: Search engine ID is incorrect
```

**Solution:**
1. Verify Search Engine ID format: `numbers:letters`
2. Check you copied the entire ID
3. Ensure the search engine is active in Programmable Search Engine console

### Issue 4: No Web Results Returned

**Symptoms:**
- Query completes but no web citations

**Possible Causes:**
1. **Query doesn't match temporal keywords**
   - Solution: Use words like "latest", "recent", "current", "2024"

2. **Web search disabled**
   - Solution: Check `ENABLE_WEB_SEARCH=true` and `GOOGLE_SEARCH_ENABLED=true`

3. **No matching results**
   - Solution: Try broader query terms

4. **API quota exceeded** (100 free/day)
   - Solution: Wait 24 hours or upgrade to paid tier
   - Check quota: https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas

### Issue 5: Slow Response Times

**Symptoms:**
- Queries taking >15 seconds

**Solutions:**
1. Reduce `GOOGLE_SEARCH_MAX_RESULTS` to 3
2. Enable caching: `GOOGLE_SEARCH_CACHE_RESULTS=true`
3. Use `web_only` mode to skip vector search for temporal queries

### Issue 6: Incorrect Citations

**Symptoms:**
- Citations don't match query topic

**Solutions:**
1. Restrict search to legal sites only: `GOOGLE_SEARCH_RESTRICT_LEGAL=true`
2. Add more specific sites to your CSE
3. Use "Search only included sites" in CSE settings

---

## API Quotas and Pricing

### Free Tier
- **100 queries per day** - FREE
- Sufficient for development and testing

### Paid Tier
- First 100 queries/day: FREE
- Additional queries: $5 per 1000 queries
- Monthly cap available

**Check your usage:**
https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas

---

## Security Best Practices

1. **API Key Security**
   - Never commit API keys to Git
   - Use environment variables
   - Rotate keys periodically

2. **API Key Restrictions**
   - Restrict to Custom Search API only
   - Add IP restrictions if possible
   - Monitor usage regularly

3. **Search Engine Access**
   - Keep CSE private (not publicly embeddable)
   - Regular audit of configured sites

---

## Summary

You've now configured Google Custom Search Engine for your Indian Legal AI Assistant!

**What You Accomplished:**
✅ Created Google Cloud project
✅ Enabled Custom Search API
✅ Got API credentials
✅ Created Custom Search Engine with 16 legal sites
✅ Configured the application
✅ Tested web search integration

**The system now:**
- Automatically searches the web for latest legal information
- Combines knowledge base with real-time web results
- Intelligently routes queries to appropriate sources
- Provides citations for all web sources

**Next Steps:**
1. Test with various queries
2. Monitor API usage in Google Cloud Console
3. Fine-tune search behavior with configuration options
4. Add more legal sites to your CSE as needed

For questions or issues, check the logs:
```bash
docker logs legal-ai-backend-local --tail=100
```

---

**Setup Time**: ~15-20 minutes
**Cost**: Free (100 queries/day) or $5/1000 queries

Happy searching! 🚀🔍
