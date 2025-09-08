import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGODB_DB")

if not MONGO_URI or not MONGO_DB:
    print("⚠️ MongoDB configuration missing - features will be unavailable")

_client: Optional[AsyncIOMotorClient] = AsyncIOMotorClient(MONGO_URI) if MONGO_URI else None
_db = _client[MONGO_DB] if (_client and MONGO_DB) else None

# ------------------------
# SOS contacts collection
# ------------------------
def _contacts():
    if _db is None:
        raise RuntimeError("MongoDB not configured")
    return _db["contacts"]

async def add_contact(user_id: str, contact: dict):
    """Add emergency contact for user."""
    col = _contacts()
    await col.update_one(
        {"user_id": user_id},
        {"$push": {"contacts": contact}},
        upsert=True
    )

async def list_contacts(user_id: str):
    """Get all emergency contacts for user."""
    col = _contacts()
    doc = await col.find_one({"user_id": user_id})
    return (doc or {}).get("contacts", [])

# ------------------------
# Live locations collection
# ------------------------
def _locations():
    if _db is None:
        raise RuntimeError("MongoDB not configured")
    return _db["locations"]

async def upsert_user_location(user_id: str, lat: float, lon: float, city_hint: str = None):
    """Save or update user's live location."""
    col = _locations()
    await col.update_one(
        {"user_id": user_id},
        {"$set": {"lat": lat, "lon": lon, "city_hint": city_hint}},
        upsert=True
    )

async def get_user_location(user_id: str):
    """Get user's saved location."""
    col = _locations()
    return await col.find_one({"user_id": user_id})