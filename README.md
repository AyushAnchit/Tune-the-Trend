# 🎵 Tune the Trend 2.0
> **High-Tech Cyberpunk Audio Intelligence Engine & Trend Synthesis System**

[![Vercel Deployment](https://img.shields.io/badge/Vercel-Live%20App-00f0ff?style=for-the-badge&logo=vercel)](https://frontend-five-nu-84.vercel.app)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Source%20Code-181717?style=for-the-badge&logo=github)](https://github.com/AyushAnchit/Tune-the-Trend)
[![Python FastAPI](https://img.shields.io/badge/FastAPI-v0.110.0-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-v19.0.0-61DAFB?style=for-the-badge&logo=react)](https://react.dev)

---

## 📌 Submission Checklist

- [x] **Public Source-Code Repository**: [https://github.com/AyushAnchit/Tune-the-Trend](https://github.com/AyushAnchit/Tune-the-Trend)
- [x] **Live Deployed Application**: [https://frontend-five-nu-84.vercel.app](https://frontend-five-nu-84.vercel.app)
- [x] **Bright Data Scraper Studio Integration**: Detailed in [Scraper & Self-Healing Architecture](#-bright-data-scraper-studio-integration)
- [x] **Example Structured Output**: Detailed in [Example Structured Output Payload](#-example-structured-output-payload)
- [x] **Demo Video**: Embedded in hero section & available at `https://frontend-five-nu-84.vercel.app`

---

## ⚡ Overview

**Tune the Trend 2.0** is an AI-powered audio intelligence engine that parses creator video profiles against real-time **Shazam**, **Hype Machine**, and social media signals (TikTok, Instagram Reels, YouTube Shorts). 

It dynamically predicts and matches high-retention audio tracks for content creators based on:
1. **Audio Texture & Genre Similarity** ($P_{\text{music}}$)
2. **Real-time Virality Potential** ($P_{\text{virality}}$)
3. **Niche & Concept Relevance** ($P_{\text{concept}}$)

---

## 🕷️ Bright Data Scraper Studio Integration

Tune the Trend leverages **Bright Data Web Scraper API & Scraper Studio** to continuously collect, audit, and self-heal trend intelligence feeds across web platforms without hitting rate limits or captcha blocks.

```
┌────────────────────────────────┐      ┌──────────────────────────────┐      ┌──────────────────────────────┐
│  Bright Data Scraper Studio    │ ───► │  Health Checker & Audits     │ ───► │  Self-Healing Controller     │
│  (Custom Collectors & DCA API) │      │  (Field Coverage & Freshness)│      │  (Diagnostic Prompt & Repair)│
└────────────────────────────────┘      └──────────────────────────────┘      └──────────────────────────────┘
```

### 1. Web Data Collector Pipeline (`tune_the_trend/services/scraper.py`)
- **Real-Time Data Extraction**: Invokes Bright Data Data Collector API (`https://api.brightdata.com/dca/trigger`) to scrape trend articles, viral social media posts, Shazam Top 200 US charts, and Hype Machine popular tracks.
- **Proxy Network**: Routes traffic through Bright Data's residential proxy network, bypassing anti-bot measures and geographical restrictions.

### 2. Automated Scrape Health Checker (`ScrapeHealthChecker`)
Evaluates dataset quality before ingestion:
- **Field Coverage Threshold**: Enforces a minimum **80% field coverage** on critical attributes (`trend_title`, `trend_description`, `article_url`, `platform`).
- **Freshness Audit**: Calculates time elapsed since publication ($T_{\text{stale}} \le 48\text{ hours}$).

### 3. Self-Healing Controller (`SelfHealingController`)
When a target website changes DOM layout and field coverage collapses below threshold:
1. **Diagnostic Prompt Generation**: Automatically generates a structured failure report:
   ```text
   Collector later_instagram failed validation.
   Observed: trend_title coverage: 0%, date coverage: 20%.
   Reasons for failure: Critical field 'trend_title' coverage is below threshold 80%.
   Repair the scraper so these fields are extracted from current page structure.
   ```
2. **Self-Healing API Trigger**: Sends the prompt to Bright Data's Self-Healing API (`https://api.brightdata.com/dca/self_heal`).
3. **Validation Run**: Executes a test run on the repaired collector to ensure 100% schema compliance before activating production feeds.

---

## 📊 Example Structured Output Payload

The system returns compact, strictly typed JSON validated via **Pydantic**:

```json
{
  "request_id": "req_88f91a42",
  "niche": "solo trip to spain",
  "music_genre": "flamenco guitar",
  "total_candidates_retrieved": 15,
  "top_k_reranked": 3,
  "recommendations": [
    {
      "rank": 1,
      "track": "Spanish Flamenco Guitar",
      "artist": "Spanish Acoustic Ensemble",
      "trend_name": "Solo Travel Spain & Scenic Flamenco Reel",
      "platform": "instagram",
      "content_type": "reels",
      "creator_match_score": 0.94,
      "p_music_similarity": 0.96,
      "p_virality_potential": 0.88,
      "p_concept_relevance": 0.98,
      "virality_tier": "Explosive Growth",
      "why_it_matches": "Direct match for travel video concept with requested acoustic flamenco guitar audio texture. Provides authentic high-retention atmosphere.",
      "why_now": "Currently in peak freshness window with active public signals on Instagram Reels.",
      "source_url": "https://later.com/blog/instagram-reels-trends/travel-spain",
      "evidence_confidence": 0.92,
      "candidate": {
        "trend_signal": {
          "source_id": "later_instagram",
          "platform": "instagram",
          "scraped_at": "2026-08-23T18:00:00Z"
        },
        "music_evidence": {
          "spotify_url": "https://www.deezer.com/track/2539912471",
          "preview_url": "https://cdnt-preview.dzcdn.net/preview/b22037704.mp3",
          "genres": ["flamenco", "acoustic", "guitar"],
          "energy": 0.45,
          "tempo": 84,
          "valence": 0.70
        }
      }
    }
  ]
}
```

---

## 🛠️ Architecture & Tech Stack

```
   ┌───────────────────────┐
   │ React 19 + Vite UI    │
   │ (Cyberpunk Theme)     │
   └───────────┬───────────┘
               │ HTTP API
   ┌───────────▼───────────┐
   │ FastAPI Backend       │
   │ (Python 3.11)         │
   └───────────┬───────────┘
               ├──────────────────────────┬──────────────────────────┐
   ┌───────────▼───────────┐  ┌───────────▼───────────┐  ┌───────────▼───────────┐
   │ Bright Data Scraper   │  │ Gemini 1.5/3.1 LLM    │  │ Deezer / Shazam API   │
   │ Studio + Self-Healing │  │ Probabilistic Reranker│  │ Real-time Audio Stream│
   └───────────────────────┘  └───────────────────────┘  └───────────────────────┘
```

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons
- **Backend**: FastAPI, Pydantic v2, HTTPX, SQLite, Uvicorn
- **AI Reranker**: Google Gemini API (`gemini-1.5-flash` / `gemini-3.1-flash`)
- **Data Collectors**: Bright Data Scraper Studio & Proxy Network
- **Audio Intelligence**: Shazam Chart API & Deezer Music API

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.10+
- Node.js 18+

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/AyushAnchit/Tune-the-Trend.git
cd Tune-the-Trend

# Create & activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI Server
PYTHONPATH=. uvicorn tune_the_trend.api.main:app --reload --port 8080
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev -- --port 3000
```
Open **`http://localhost:3000`** in your browser.

---

## 🎥 Demo Video

Watch the full working demo video showing real-time audio recon search, Shazam chart matching, 30s preview streams, and trend synthesis:

📹 **[Watch Demo Video](https://frontend-five-nu-84.vercel.app)** *(Embedded directly in the live app hero banner)*

---

## 📄 License

MIT License © 2026 Ayush Anchit
