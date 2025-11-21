import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables if present
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "appdb")

client = None
_db = None

try:
    client = MongoClient(DATABASE_URL)
    _db = client[DATABASE_NAME]
except Exception:
    client = None
    _db = None

# Expose db for other modules
db = _db


def _to_str_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc = dict(doc)
    if doc.get("_id"):
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


def create_document(collection_name: str, data: Dict[str, Any]) -> str:
    if db is None:
        raise RuntimeError("Database not initialized")
    data = dict(data)
    now = datetime.utcnow()
    if "created_at" not in data:
        data["created_at"] = now
    data["updated_at"] = now
    result = db[collection_name].insert_one(data)
    return str(result.inserted_id)


def get_documents(collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
    if db is None:
        raise RuntimeError("Database not initialized")
    filter_dict = filter_dict or {}
    cursor = db[collection_name].find(filter_dict).limit(int(limit))
    return [_to_str_id(doc) for doc in cursor]


def get_document_by_id(collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
    if db is None:
        raise RuntimeError("Database not initialized")
    try:
        doc = db[collection_name].find_one({"_id": ObjectId(doc_id)})
        return _to_str_id(doc) if doc else None
    except Exception:
        return None


def update_document(collection_name: str, doc_id: str, updates: Dict[str, Any]) -> bool:
    if db is None:
        raise RuntimeError("Database not initialized")
    updates = dict(updates)
    updates["updated_at"] = datetime.utcnow()
    result = db[collection_name].update_one({"_id": ObjectId(doc_id)}, {"$set": updates})
    return result.modified_count > 0


def delete_document(collection_name: str, doc_id: str) -> bool:
    if db is None:
        raise RuntimeError("Database not initialized")
    result = db[collection_name].delete_one({"_id": ObjectId(doc_id)})
    return result.deleted_count > 0
