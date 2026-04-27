"""Housing Edge API - FastAPI backend."""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
import uuid
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime as dt
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DB_PATH = Path(__file__).parent / "housing_edge.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PropertyDB(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True)
    source = Column(String)
    url = Column(String)
    reference_id = Column(String)
    property_type = Column(String)
    title = Column(String)
    address = Column(String)
    location = Column(String)
    province = Column(String)
    price = Column(Float)
    deposit_required = Column(Float)
    estimated_market_value = Column(Float, nullable=True)
    sqm = Column(String, nullable=True)
    occupation_risk_percent = Column(Float, default=50.0)
    occupation_risk = Column(Float, default=5.0)
    legal_complexity = Column(Float, default=5.0)
    location_score = Column(Float, default=5.0)
    opportunity_score = Column(Float, default=5.0)
    llm_reasoning = Column(Text, nullable=True)
    data_confidence = Column(String, default="media")
    charges = Column(String, nullable=True)
    visitable = Column(Boolean, default=False)
    scheduled_closing = Column(DateTime, nullable=True)
    full_description = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)


class UserProfileDB(Base):
    __tablename__ = "user_profile"

    id = Column(String, primary_key=True, default="default")
    budget_min = Column(Float, default=0)
    budget_max = Column(Float, default=500000)
    risk_tolerance = Column(Float, default=5.0)
    email = Column(String, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Housing Edge API", version="0.1.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Models for API
class PropertyResponse(BaseModel):
    id: str
    source: str
    url: str
    reference_id: str
    property_type: str
    title: str
    address: str
    location: str
    province: str
    price: float
    deposit_required: float
    estimated_market_value: Optional[float]
    occupation_risk_percent: float
    occupation_risk: float
    legal_complexity: float
    location_score: float
    opportunity_score: float
    llm_reasoning: Optional[str]
    data_confidence: str
    charges: Optional[str]
    visitable: bool
    scheduled_closing: Optional[str]
    full_description: Optional[str]
    discovered_at: str
    last_updated: str

    class Config:
        from_attributes = True


class PropertyListResponse(BaseModel):
    properties: list[PropertyResponse]
    total: int
    last_updated: str


class UserProfileRequest(BaseModel):
    budget_min: float = 0
    budget_max: float = 500000
    risk_tolerance: float = 5.0
    email: Optional[str] = None


@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/properties", response_model=PropertyListResponse)
def get_properties(
    source: Optional[str] = Query(None, description="Filter by source: boe, sareb, all"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_score: Optional[float] = Query(None, description="Minimum opportunity score"),
    search: Optional[str] = Query(None, description="Search in title/address/location"),
):
    db = SessionLocal()
    try:
        query = db.query(PropertyDB)

        if source and source != "all":
            query = query.filter(PropertyDB.source == source)

        if min_price is not None:
            query = query.filter(PropertyDB.price >= min_price)

        if max_price is not None:
            query = query.filter(PropertyDB.price <= max_price)

        if min_score is not None:
            query = query.filter(PropertyDB.opportunity_score >= min_score)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (PropertyDB.title.like(search_term)) |
                (PropertyDB.address.like(search_term)) |
                (PropertyDB.location.like(search_term))
            )

        # Order by opportunity score desc
        query = query.order_by(PropertyDB.opportunity_score.desc())

        properties = query.all()

        # Convert PropertyDB objects to dicts with ISO string dates for Pydantic
        def prop_to_dict(p):
            d = {
                "id": p.id,
                "source": p.source,
                "url": p.url,
                "reference_id": p.reference_id,
                "property_type": p.property_type,
                "title": p.title,
                "address": p.address or "",
                "location": p.location or "",
                "province": p.province or "",
                "price": p.price or 0,
                "deposit_required": p.deposit_required or 0,
                "estimated_market_value": p.estimated_market_value,
                "occupation_risk_percent": p.occupation_risk_percent or 0,
                "occupation_risk": p.occupation_risk or 0,
                "legal_complexity": p.legal_complexity or 0,
                "location_score": p.location_score or 0,
                "opportunity_score": p.opportunity_score or 0,
                "llm_reasoning": p.llm_reasoning,
                "data_confidence": p.data_confidence or "",
                "charges": p.charges,
                "visitable": p.visitable or False,
                "scheduled_closing": p.scheduled_closing.isoformat() if p.scheduled_closing else None,
                "full_description": p.full_description or "",
                "discovered_at": p.discovered_at.isoformat() if p.discovered_at else datetime.utcnow().isoformat(),
                "last_updated": p.last_updated.isoformat() if p.last_updated else datetime.utcnow().isoformat(),
            }
            return d

        last_updated = max((p.last_updated for p in properties), default=None)
        last_updated_str = last_updated.isoformat() if last_updated else datetime.utcnow().isoformat()

        return PropertyListResponse(
            properties=[PropertyResponse.model_validate(prop_to_dict(p)) for p in properties],
            total=len(properties),
            last_updated=last_updated_str,
        )
    finally:
        db.close()


@app.get("/api/properties/{property_id}", response_model=PropertyResponse)
def get_property(property_id: str):
    db = SessionLocal()
    try:
        prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        return PropertyResponse.model_validate(prop)
    finally:
        db.close()


@app.post("/api/profile")
def save_profile(profile: UserProfileRequest):
    db = SessionLocal()
    try:
        existing = db.query(UserProfileDB).filter(UserProfileDB.id == "default").first()

        if existing:
            existing.budget_min = profile.budget_min
            existing.budget_max = profile.budget_max
            existing.risk_tolerance = profile.risk_tolerance
            existing.email = profile.email
        else:
            db_profile = UserProfileDB(
                id="default",
                budget_min=profile.budget_min,
                budget_max=profile.budget_max,
                risk_tolerance=profile.risk_tolerance,
                email=profile.email,
            )
            db.add(db_profile)

        db.commit()
        return {"saved": True}
    finally:
        db.close()


@app.get("/api/profile")
def get_profile():
    db = SessionLocal()
    try:
        profile = db.query(UserProfileDB).filter(UserProfileDB.id == "default").first()
        if not profile:
            return UserProfileRequest().model_dump()
        return UserProfileRequest(
            budget_min=profile.budget_min,
            budget_max=profile.budget_max,
            risk_tolerance=profile.risk_tolerance,
            email=profile.email,
        ).model_dump()
    finally:
        db.close()


class RefreshResponse(BaseModel):
    job_id: str
    status: str
    properties_found: int


@app.post("/api/properties/refresh", response_model=RefreshResponse)
def refresh_properties():
    """Trigger a full refresh of BOE auctions from all provinces."""
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    job_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting refresh job {job_id}")

    PROVINCES = [
        "Almería", "Cádiz", "Córdoba", "Granada", "Huelva", "Jaén", "Málaga", "Sevilla",
        "Huesca", "Teruel", "Zaragoza", "Asturias", "Balears", "Barcelona", "Girona", "Lleida", "Tarragona",
        "Ávila", "Burgos", "León", "Palencia", "Salamanca", "Segovia", "Soria", "Valladolid", "Zamora",
        "Soria", "Barcelona", "Madrid", "Navarra", "La Rioja", "Tenerife", "Las Palmas",
    ]

    BASE_URL = "https://subastas.boe.es"
    SEARCH_URL = "https://subastas.boe.es/subastas_ava.php"

    client = httpx.Client(timeout=30, follow_redirects=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    properties_found = 0

    db = SessionLocal()
    try:
        for province in PROVINCES:
            try:
                data = {
                    "campo[0]": "SUBASTA.ORIGEN", "dato[0]": "",
                    "campo[2]": "SUBASTA.ESTADO.CODIGO", "dato[2]": "",
                    "campo[3]": "BIEN.TIPO", "dato[3]": "I",
                    "campo[4]": "BIEN.SUBTIPO", "dato[4]": "",
                    "campo[5]": "BIEN.PROVINCIA", "dato[5]": province,
                    "accion": "Buscar",
                }
                resp = client.post(SEARCH_URL, data=data, headers=headers)
                soup = BeautifulSoup(resp.text, "lxml")

                links = soup.find_all("a", href=True)
                for link in links:
                    href = link.get("href", "")
                    m = re.search(r"idSub=([^&]+)", href)
                    if not m:
                        continue
                    auction_id = m.group(1)
                    text = link.get_text(strip=True)
                    if not text or len(text) < 5:
                        continue

                    prop_id = f"boe-{auction_id}"
                    existing = db.query(PropertyDB).filter(PropertyDB.id == prop_id).first()
                    if existing:
                        continue

                    price_text = link.find_parent("td").get_text() if link.find_parent("td") else ""
                    price = None
                    price_match = re.search(r"(\d{1,3}(?:\.\d{3})+(?:,\d{2})?)\s*€?", price_text)
                    if price_match:
                        try:
                            price = float(price_match.group(1).replace(".", "").replace(",", "."))
                        except ValueError:
                            pass

                    url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    prop = PropertyDB(
                        id=prop_id,
                        source="boe",
                        url=url,
                        reference_id=auction_id,
                        property_type="Vivienda",
                        title=text[:300],
                        address="",
                        location=province,
                        province=province,
                        price=price or 0,
                        deposit_required=0,
                        opportunity_score=5.0,
                        last_updated=dt.utcnow(),
                    )
                    db.add(prop)
                    properties_found += 1

            except Exception as e:
                logger.warning(f"Failed province {province}: {e}")
                continue

        db.commit()
        logger.info(f"Job {job_id}: added {properties_found} properties")
        return RefreshResponse(job_id=job_id, status="completed", properties_found=properties_found)
    finally:
        db.close()


@app.get("/api/stats")
def get_stats():
    """Return overall statistics."""
    db = SessionLocal()
    try:
        total = db.query(PropertyDB).count()
        high_opp = db.query(PropertyDB).filter(PropertyDB.opportunity_score >= 7).count()
        avg_price = db.query(PropertyDB).all()
        avg_price_value = sum(p.price for p in avg_price) / len(avg_price) if avg_price else 0
        last_updated = max((p.last_updated for p in avg_price), default=None)

        return {
            "total_properties": total,
            "high_opportunity_count": high_opp,
            "average_price": avg_price_value,
            "last_updated": last_updated.isoformat() if last_updated else None,
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)