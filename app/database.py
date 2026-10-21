"""
StyleVision — MongoDB Database Module
Uses the Motor async driver to provide database connections, lifecycle management,
collections, and automatic index setup matching the project specification.
"""
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import pymongo

from app.config import get_settings
from app.utils.security import hash_password

settings = get_settings()


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


db_manager = DatabaseManager()


def get_database() -> AsyncIOMotorDatabase:
    """Return the active MongoDB database instance, auto-connecting on demand if needed."""
    if db_manager.db is None:
        db_manager.client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000,
        )
        db_manager.db = db_manager.client[settings.mongodb_db_name]
    return db_manager.db


async def connect_to_mongo():
    """
    Establish connection to MongoDB, verify connectivity via ping,
    and initialize collections and unique indexes.
    If external MongoDB is not reachable, seamlessly activates embedded AsyncMongoMockClient.
    """
    print(f"[StyleVision DB] Connecting to MongoDB at {settings.mongodb_url}...")
    try:
        db_manager.client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=2000,
        )
        db_manager.db = db_manager.client[settings.mongodb_db_name]
        # Verify connectivity
        await db_manager.client.admin.command("ping")
        print(f"[StyleVision DB] Connected to database: '{settings.mongodb_db_name}'")
    except Exception as exc:
        print(f"[StyleVision DB] External MongoDB at {settings.mongodb_url} unavailable. Initializing embedded zero-setup database...")
        from mongomock_motor import AsyncMongoMockClient
        db_manager.client = AsyncMongoMockClient()
        db_manager.db = db_manager.client[settings.mongodb_db_name]
        print(f"[StyleVision DB] Embedded in-memory database ready: '{settings.mongodb_db_name}'")

    # Initialize collections and indexes
    await _init_indexes(db_manager.db)

    # Seed demo and admin accounts if not already present
    await _seed_initial_users(db_manager.db)


async def close_mongo_connection():
    """Gracefully close the MongoDB client connection on shutdown."""
    if db_manager.client is not None:
        print("[StyleVision DB] Closing MongoDB connection...")
        db_manager.client.close()
        db_manager.client = None
        db_manager.db = None
        print("[StyleVision DB] MongoDB connection closed.")


async def _init_indexes(db: AsyncIOMotorDatabase):
    """
    Create MongoDB indexes according to the database design requirements:
    - USER: unique index on email, unique index on user_id
    - OUTFIT: index on user_id, outfit_id
    - ACCESSORY: index on user_id, accessory_id
    - MAKEUP: index on user_id, makeup_id
    - HAIRSTYLE: index on user_id, hairstyle_id
    - SAVED_LOOKS: index on user_id, look_id
    """
    try:
        # Users
        await db["users"].create_index([("email", pymongo.ASCENDING)], unique=True)
        await db["users"].create_index([("user_id", pymongo.ASCENDING)], unique=True)

        # Outfits (PPT schema)
        await db["outfits"].create_index([("user_id", pymongo.ASCENDING)])
        await db["outfits"].create_index([("outfit_id", pymongo.ASCENDING)], unique=True)

        # Accessories (PPT schema)
        await db["accessories"].create_index([("user_id", pymongo.ASCENDING)])
        await db["accessories"].create_index([("accessory_id", pymongo.ASCENDING)], unique=True)

        # Makeup (PPT schema)
        await db["makeup"].create_index([("user_id", pymongo.ASCENDING)])
        await db["makeup"].create_index([("makeup_id", pymongo.ASCENDING)], unique=True)

        # Hairstyles (PPT schema)
        await db["hairstyles"].create_index([("user_id", pymongo.ASCENDING)])
        await db["hairstyles"].create_index([("hairstyle_id", pymongo.ASCENDING)], unique=True)

        # Saved looks / History
        await db["saved_looks"].create_index([("user_id", pymongo.ASCENDING)])
        await db["saved_looks"].create_index([("look_id", pymongo.ASCENDING)], unique=True)

        # Try-on job records (persistent, replaces in-memory registry)
        await db["tryons"].create_index([("tryon_id", pymongo.ASCENDING)], unique=True)
        await db["tryons"].create_index([("user_id", pymongo.ASCENDING)])
        await db["tryons"].create_index([("created_at", pymongo.DESCENDING)])

        # Unified image registry (original uploads + stage results for chaining)
        await db["images"].create_index([("image_id", pymongo.ASCENDING)], unique=True)
        await db["images"].create_index([("user_id", pymongo.ASCENDING), ("kind", pymongo.ASCENDING)])
        await db["images"].create_index([("root_image_id", pymongo.ASCENDING)])
        await db["images"].create_index([("user_id", pymongo.ASCENDING), ("stage", pymongo.ASCENDING)])

        # Catalogue items
        await db["catalogue"].create_index([("item_id", pymongo.ASCENDING)], unique=True)
        await db["catalogue"].create_index([("category", pymongo.ASCENDING)])

        print("[StyleVision DB] Indexes successfully verified/created.")
    except Exception as exc:
        print(f"[StyleVision DB] Warning during index creation: {exc}")


async def _seed_initial_users(db: AsyncIOMotorDatabase):
    """Ensure baseline demonstration accounts exist in the database."""
    users_col = db["users"]

    demo_email = "demo@stylevision.com"
    existing_demo = await users_col.find_one({"email": demo_email})
    if not existing_demo:
        demo_user = {
            "user_id": "usr-demo-001",
            "name": "Demo User",
            "email": demo_email,
            "password_hash": hash_password("DemoPassword123"),
            "profile_photo": None,
            "is_admin": False,
            "created_at": datetime.now(timezone.utc),
        }
        await users_col.insert_one(demo_user)
        print(f"[StyleVision DB] Seeded demo user: {demo_email}")

    admin_email = "admin@stylevision.com"
    existing_admin = await users_col.find_one({"email": admin_email})
    if not existing_admin:
        admin_user = {
            "user_id": "usr-admin-001",
            "name": "System Administrator",
            "email": admin_email,
            "password_hash": hash_password("AdminPassword123"),
            "profile_photo": None,
            "is_admin": True,
            "created_at": datetime.now(timezone.utc),
        }
        await users_col.insert_one(admin_user)
        print(f"[StyleVision DB] Seeded admin user: {admin_email}")
