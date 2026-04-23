"""
Startup Lead Finder
====================
A single-file Python application that:
- Scrapes startup/company data from the web
- Cleans data using pandas
- Stores leads in a SQLite database (leads.db)
- Exposes a FastAPI REST API
- Runs a background scheduler every 24 hours
"""

import time
import logging
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import uvicorn

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────
DATABASE_URL = "sqlite:///leads.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    industry = Column(String(100), default="Unknown")
    location = Column(String(150), default="Unknown")
    description = Column(Text, default="")
    website = Column(String(255), default="")
    source = Column(String(100), default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)
log.info("Database ready → leads.db")

# ─────────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────────
SCRAPE_TARGETS = [
    {
        "url": "https://news.ycombinator.com/",
        "source": "Hacker News",
        "location": "San Francisco, CA",
        "industry": "Tech",
    },
    {
        "url": "https://github.com/trending",
        "source": "GitHub Trending",
        "location": "Global",
        "industry": "Open Source / Tech",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

FALLBACK_LEADS = [
    {"company_name": "OpenAI", "industry": "AI / ML", "location": "San Francisco, CA",
     "description": "Artificial intelligence research lab", "website": "https://openai.com", "source": "Fallback"},
    {"company_name": "Stripe", "industry": "FinTech", "location": "San Francisco, CA",
     "description": "Online payment processing platform", "website": "https://stripe.com", "source": "Fallback"},
    {"company_name": "Vercel", "industry": "DevTools / Cloud", "location": "San Francisco, CA",
     "description": "Frontend cloud and deployment platform", "website": "https://vercel.com", "source": "Fallback"},
    {"company_name": "Notion", "industry": "Productivity / SaaS", "location": "San Francisco, CA",
     "description": "All-in-one workspace for notes and collaboration", "website": "https://notion.so", "source": "Fallback"},
    {"company_name": "Linear", "industry": "DevTools / SaaS", "location": "San Francisco, CA",
     "description": "Issue tracking tool built for modern software teams", "website": "https://linear.app", "source": "Fallback"},
    {"company_name": "Figma", "industry": "Design / SaaS", "location": "San Francisco, CA",
     "description": "Collaborative design and prototyping tool", "website": "https://figma.com", "source": "Fallback"},
    {"company_name": "Supabase", "industry": "Backend / DevTools", "location": "Global (Remote)",
     "description": "Open-source Firebase alternative with Postgres", "website": "https://supabase.com", "source": "Fallback"},
    {"company_name": "Clerk", "industry": "Auth / SaaS", "location": "New York, NY",
     "description": "Authentication and user management for modern apps", "website": "https://clerk.com", "source": "Fallback"},
    {"company_name": "Railway", "industry": "Cloud / DevTools", "location": "San Francisco, CA",
     "description": "Deployment platform for modern apps", "website": "https://railway.app", "source": "Fallback"},
    {"company_name": "PlanetScale", "industry": "Database / SaaS", "location": "San Francisco, CA",
     "description": "Serverless MySQL database platform", "website": "https://planetscale.com", "source": "Fallback"},
    {"company_name": "Resend", "industry": "Email / DevTools", "location": "Global (Remote)",
     "description": "Email API for developers", "website": "https://resend.com", "source": "Fallback"},
    {"company_name": "Loom", "industry": "Communication / SaaS", "location": "San Francisco, CA",
     "description": "Async video messaging for remote teams", "website": "https://loom.com", "source": "Fallback"},
]


def scrape_hackernews(url: str, meta: dict) -> list[dict]:
    """Scrape top story titles from Hacker News."""
    leads = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        titles = soup.select(".titleline > a")
        for t in titles[:15]:
            text = t.get_text(strip=True)
            href = t.get("href", "")
            if text and len(text) > 5:
                leads.append({
                    "company_name": text[:120],
                    "industry": meta["industry"],
                    "location": meta["location"],
                    "description": f"Trending on {meta['source']}",
                    "website": href if href.startswith("http") else "",
                    "source": meta["source"],
                })
        log.info("Scraped %d items from %s", len(leads), meta["source"])
    except Exception as exc:
        log.warning("Failed to scrape %s → %s", url, exc)
    return leads


def scrape_github_trending(url: str, meta: dict) -> list[dict]:
    """Scrape trending repositories from GitHub."""
    leads = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        repos = soup.select("article.Box-row")
        for repo in repos[:15]:
            name_tag = repo.select_one("h2 a")
            desc_tag = repo.select_one("p")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True).replace("\n", "").replace(" ", "")
            desc = desc_tag.get_text(strip=True) if desc_tag else "Open-source project"
            href = "https://github.com" + (name_tag.get("href", ""))
            leads.append({
                "company_name": name[:120],
                "industry": meta["industry"],
                "location": meta["location"],
                "description": desc[:300],
                "website": href,
                "source": meta["source"],
            })
        log.info("Scraped %d items from %s", len(leads), meta["source"])
    except Exception as exc:
        log.warning("Failed to scrape %s → %s", url, exc)
    return leads


def run_scraper() -> list[dict]:
    """Run all scrapers and return combined raw data."""
    raw = []
    for target in SCRAPE_TARGETS:
        if "ycombinator" in target["url"]:
            raw.extend(scrape_hackernews(target["url"], target))
        elif "github" in target["url"]:
            raw.extend(scrape_github_trending(target["url"], target))

    # Always blend in the curated fallback leads
    raw.extend(FALLBACK_LEADS)
    log.info("Total raw leads collected: %d", len(raw))
    return raw


# ─────────────────────────────────────────────
# DATA CLEANING
# ─────────────────────────────────────────────

def clean_data(raw: list[dict]) -> pd.DataFrame:
    """Clean and deduplicate raw lead data."""
    df = pd.DataFrame(raw)

    # Fill missing values
    df["company_name"] = df["company_name"].fillna("Unknown Company").str.strip()
    df["industry"] = df["industry"].fillna("Unknown")
    df["location"] = df["location"].fillna("Unknown")
    df["description"] = df["description"].fillna("")
    df["website"] = df["website"].fillna("")
    df["source"] = df["source"].fillna("Unknown")

    # Drop rows with no meaningful company name
    df = df[df["company_name"].str.len() > 2]

    # Deduplicate on company_name (keep first occurrence)
    df = df.drop_duplicates(subset=["company_name"], keep="first")

    # Truncate long fields
    df["company_name"] = df["company_name"].str[:255]
    df["description"] = df["description"].str[:500]
    df["website"] = df["website"].str[:255]

    df = df.reset_index(drop=True)
    log.info("Clean leads ready: %d rows", len(df))
    return df


# ─────────────────────────────────────────────
# DATABASE OPERATIONS
# ─────────────────────────────────────────────

def save_leads(df: pd.DataFrame):
    """Persist cleaned leads to the SQLite database (skip duplicates)."""
    session = SessionLocal()
    added = 0
    try:
        existing = {r.company_name for r in session.query(Lead.company_name).all()}
        for _, row in df.iterrows():
            if row["company_name"] in existing:
                continue
            lead = Lead(
                company_name=row["company_name"],
                industry=row["industry"],
                location=row["location"],
                description=row["description"],
                website=row["website"],
                source=row["source"],
            )
            session.add(lead)
            added += 1
        session.commit()
        log.info("Saved %d new leads to database", added)
    except Exception as exc:
        session.rollback()
        log.error("DB save error: %s", exc)
    finally:
        session.close()


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────

def run_pipeline():
    """Full ETL pipeline: scrape → clean → store."""
    log.info("━━━ Pipeline started ━━━")
    raw = run_scraper()
    df = clean_data(raw)
    save_leads(df)
    log.info("━━━ Pipeline complete ━━━")


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────
INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


def scheduler():
    """Background thread: run pipeline every 24 hours."""
    while True:
        log.info("Scheduler sleeping for 24 hours…")
        time.sleep(INTERVAL_SECONDS)
        log.info("Scheduler waking up — running pipeline")
        run_pipeline()


# ─────────────────────────────────────────────
# FASTAPI APPLICATION
# ─────────────────────────────────────────────
app = FastAPI(
    title="Startup Lead Finder",
    description="Scrapes, cleans and serves startup leads via REST API.",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse, tags=["Home"])
def home():
    """Landing page with project overview and quick links."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <title>Startup Lead Finder</title>
      <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .card { background: #1e293b; border-radius: 16px; padding: 48px 56px; max-width: 680px; width: 100%; box-shadow: 0 25px 60px rgba(0,0,0,0.5); }
        h1 { font-size: 2rem; font-weight: 700; color: #38bdf8; margin-bottom: 8px; }
        .badge { display: inline-block; background: #0ea5e9; color: #fff; font-size: 0.7rem; font-weight: 700; padding: 2px 10px; border-radius: 20px; letter-spacing: 1px; margin-bottom: 24px; }
        p { color: #94a3b8; line-height: 1.7; margin-bottom: 28px; }
        .endpoints { list-style: none; }
        .endpoints li { margin-bottom: 14px; }
        .endpoints a { display: flex; align-items: center; gap: 12px; background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 14px 20px; color: #e2e8f0; text-decoration: none; transition: border-color .2s, background .2s; }
        .endpoints a:hover { border-color: #38bdf8; background: #162032; }
        .method { background: #0ea5e9; color: #fff; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 6px; letter-spacing: .5px; }
        .path { font-family: monospace; font-size: 0.95rem; color: #7dd3fc; }
        .desc { font-size: 0.82rem; color: #64748b; margin-left: auto; }
        .footer { margin-top: 32px; font-size: 0.78rem; color: #475569; text-align: center; }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="badge">LIVE</div>
        <h1>🚀 Startup Lead Finder</h1>
        <p>Automatically scrapes, cleans, and stores startup leads from across the web. Browse leads directly or filter by location using the API below.</p>
        <ul class="endpoints">
          <li><a href="/leads"><span class="method">GET</span><span class="path">/leads</span><span class="desc">All leads</span></a></li>
          <li><a href="/leads/filter?location=San Francisco, CA"><span class="method">GET</span><span class="path">/leads/filter?location=...</span><span class="desc">Filter by location</span></a></li>
          <li><a href="/docs"><span class="method">GET</span><span class="path">/docs</span><span class="desc">Swagger UI</span></a></li>
          <li><a href="/redoc"><span class="method">GET</span><span class="path">/redoc</span><span class="desc">ReDoc</span></a></li>
        </ul>
        <div class="footer">Powered by FastAPI · SQLite · BeautifulSoup · pandas</div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/leads", tags=["Leads"])
def get_leads(skip: int = 0, limit: int = Query(default=50, le=500)):
    """Return all leads with optional pagination."""
    session = SessionLocal()
    try:
        total = session.query(Lead).count()
        leads = session.query(Lead).offset(skip).limit(limit).all()
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "results": [
                {
                    "id": l.id,
                    "company_name": l.company_name,
                    "industry": l.industry,
                    "location": l.location,
                    "description": l.description,
                    "website": l.website,
                    "source": l.source,
                    "scraped_at": l.scraped_at.isoformat() if l.scraped_at else None,
                }
                for l in leads
            ],
        }
    finally:
        session.close()


@app.get("/leads/filter", tags=["Leads"])
def filter_leads(
    location: str = Query(None, description="Filter leads by location (partial match)"),
    industry: str = Query(None, description="Filter leads by industry (partial match)"),
    skip: int = 0,
    limit: int = Query(default=50, le=500),
):
    """Filter leads by location and/or industry."""
    session = SessionLocal()
    try:
        query = session.query(Lead)
        if location:
            query = query.filter(Lead.location.ilike(f"%{location}%"))
        if industry:
            query = query.filter(Lead.industry.ilike(f"%{industry}%"))
        total = query.count()
        leads = query.offset(skip).limit(limit).all()
        if not leads:
            raise HTTPException(status_code=404, detail="No leads found matching the given filters.")
        return {
            "total": total,
            "filters": {"location": location, "industry": industry},
            "skip": skip,
            "limit": limit,
            "results": [
                {
                    "id": l.id,
                    "company_name": l.company_name,
                    "industry": l.industry,
                    "location": l.location,
                    "description": l.description,
                    "website": l.website,
                    "source": l.source,
                    "scraped_at": l.scraped_at.isoformat() if l.scraped_at else None,
                }
                for l in leads
            ],
        }
    finally:
        session.close()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os

    # 1. Run the pipeline immediately on startup
    run_pipeline()

    # 2. Start background scheduler thread
    scheduler_thread = threading.Thread(target=scheduler, daemon=True, name="Scheduler")
    scheduler_thread.start()
    log.info("Background scheduler started (interval: 24 h)")

    # 3. Launch the API server (PORT env var is set by Render automatically)
    port = int(os.environ.get("PORT", 8000))
    log.info("Starting API server at http://0.0.0.0:%d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
