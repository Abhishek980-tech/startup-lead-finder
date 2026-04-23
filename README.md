# 🚀 Startup Lead Finder

> Automatically scrape, clean, store, and serve startup leads via a REST API — all in a single Python file.

---

## Problem Statement

Sales and business-development teams spend hours manually hunting for startup leads across dozens of sources. There is no lightweight, self-hosted tool that automates the full pipeline — from discovery to a queryable API — without requiring heavy infrastructure.

---

## Solution

**Startup Lead Finder** is a single-file Python application that:

1. **Scrapes** startup and company data from public sources (Hacker News, GitHub Trending, and a curated seed list).
2. **Cleans** the raw data with pandas — deduplicates, fills missing values, and normalises strings.
3. **Stores** leads in a local SQLite database (`leads.db`) via SQLAlchemy.
4. **Serves** leads through a FastAPI REST API with filtering capabilities.
5. **Automates** the full pipeline on startup and re-runs it every 24 hours via a background scheduler.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      app.py  (single file)              │
│                                                         │
│  ┌───────────┐   ┌───────────┐   ┌──────────────────┐  │
│  │  Scraper  │──▶│  Cleaner  │──▶│  SQLite Database │  │
│  │ requests  │   │  pandas   │   │   (leads.db)     │  │
│  │    BS4    │   └───────────┘   └────────┬─────────┘  │
│  └───────────┘                            │             │
│                                           ▼             │
│  ┌─────────────────────────────────────────────────┐   │
│  │              FastAPI REST API                   │   │
│  │  GET /          → Landing page (HTML)           │   │
│  │  GET /leads     → All leads (JSON, paginated)   │   │
│  │  GET /leads/filter?location=&industry=  (JSON)  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │     Background Scheduler (daemon thread)        │   │
│  │     Runs full pipeline every 24 hours           │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Tech stack:** Python 3.10+ · FastAPI · SQLAlchemy · SQLite · pandas · requests · BeautifulSoup4 · uvicorn

---

## Project Structure

```
startup-lead-finder/
├── app.py            # Entire application (scraper + cleaner + DB + API + scheduler)
├── requirements.txt  # Python dependencies
├── README.md         # This file
└── .gitignore        # Excludes __pycache__, *.db, .env
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/startup-lead-finder.git
cd startup-lead-finder
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
python app.py
```

The app will:
- Run the scraping pipeline immediately
- Start the API server at **http://localhost:8000**
- Schedule the next pipeline run in 24 hours

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | HTML landing page with quick links |
| `GET` | `/leads` | Returns all leads (paginated, JSON) |
| `GET` | `/leads?skip=0&limit=20` | Paginate through leads |
| `GET` | `/leads/filter?location=XYZ` | Filter by location (partial match) |
| `GET` | `/leads/filter?industry=FinTech` | Filter by industry (partial match) |
| `GET` | `/leads/filter?location=SF&industry=AI` | Combined filter |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

### Example responses

**GET /leads**
```json
{
  "total": 42,
  "skip": 0,
  "limit": 50,
  "results": [
    {
      "id": 1,
      "company_name": "OpenAI",
      "industry": "AI / ML",
      "location": "San Francisco, CA",
      "description": "Artificial intelligence research lab",
      "website": "https://openai.com",
      "source": "Fallback",
      "scraped_at": "2024-01-15T10:30:00"
    }
  ]
}
```

**GET /leads/filter?location=San Francisco**
```json
{
  "total": 8,
  "filters": { "location": "San Francisco", "industry": null },
  "results": [ ... ]
}
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///leads.db` | SQLAlchemy database URL |
| `INTERVAL_SECONDS` | `86400` (24 h) | Scheduler interval in seconds |
| Port | `8000` | uvicorn bind port |

---

## License

MIT — free to use, modify, and distribute.
