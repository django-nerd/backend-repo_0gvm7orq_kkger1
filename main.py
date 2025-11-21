import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime

from database import db, create_document, get_documents, get_document_by_id

app = FastAPI(title="Raport Otomatis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudentIn(BaseModel):
    full_name: str
    student_number: str
    class_name: str
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None

class SubjectIn(BaseModel):
    name: str
    kkm: float = Field(70, ge=0, le=100)

class WeightIn(BaseModel):
    subject_id: str
    class_name: Optional[str] = None
    tugas: float = 30
    kuis: float = 20
    uts: float = 20
    uas: float = 30

class ScoreIn(BaseModel):
    student_id: str
    subject_id: str
    type: str  # tugas|kuis|uts|uas
    value: float = Field(..., ge=0, le=100)
    note: Optional[str] = None
    date: Optional[datetime] = None


@app.get("/")
def root():
    return {"message": "Raport Otomatis API"}


@app.get("/test")
def test_database():
    resp = {
        "backend": "✅ Running",
        "database": "❌ Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            resp["database"] = "✅ Connected"
            resp["collections"] = db.list_collection_names()
    except Exception as e:
        resp["error"] = str(e)
    return resp


# Students CRUD (minimal: create + list)
@app.post("/students")
def create_student(payload: StudentIn):
    data = payload.model_dump()
    student_id = create_document("student", data)
    return {"id": student_id, **data}


@app.get("/students")
def list_students(q: Optional[str] = None) -> List[Dict[str, Any]]:
    flt = {}
    if q:
        flt = {"$or": [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"student_number": {"$regex": q, "$options": "i"}},
            {"class_name": {"$regex": q, "$options": "i"}},
        ]}
    return get_documents("student", flt, limit=200)


# Subjects
@app.post("/subjects")
def create_subject(payload: SubjectIn):
    data = payload.model_dump()
    subject_id = create_document("subject", data)
    return {"id": subject_id, **data}


@app.get("/subjects")
def list_subjects() -> List[Dict[str, Any]]:
    return get_documents("subject", {}, limit=200)


# Weights (per subject per class)
@app.post("/weights")
def set_weight(payload: WeightIn):
    data = payload.model_dump()
    # Upsert behavior: find existing weight for subject_id + class_name
    existing = db["weight"].find_one({
        "subject_id": data["subject_id"],
        "class_name": data.get("class_name")
    })
    now = datetime.utcnow()
    data["updated_at"] = now
    if existing:
        db["weight"].update_one({"_id": existing["_id"]}, {"$set": data})
        weight_id = str(existing["_id"])
    else:
        data["created_at"] = now
        weight_id = create_document("weight", data)
    return {"id": weight_id, **data}


@app.get("/weights")
def list_weights(subject_id: Optional[str] = None, class_name: Optional[str] = None):
    flt: Dict[str, Any] = {}
    if subject_id:
        flt["subject_id"] = subject_id
    if class_name is not None:
        flt["class_name"] = class_name
    return get_documents("weight", flt, limit=200)


# Scores: teachers input raw scores (tugas, kuis, uts, uas)
@app.post("/scores")
def add_score(payload: ScoreIn):
    data = payload.model_dump()
    if data.get("date") is None:
        data["date"] = datetime.utcnow()
    score_id = create_document("score", data)
    return {"id": score_id, **data}


@app.get("/scores")
def list_scores(student_id: Optional[str] = None, subject_id: Optional[str] = None, type: Optional[str] = None):
    flt: Dict[str, Any] = {}
    if student_id:
        flt["student_id"] = student_id
    if subject_id:
        flt["subject_id"] = subject_id
    if type:
        flt["type"] = type
    return get_documents("score", flt, limit=500)


# Compute final grade per student per subject
@app.get("/report")
def generate_report(student_id: str, subject_id: str):
    student = get_document_by_id("student", student_id)
    subject = get_document_by_id("subject", subject_id)
    if not student or not subject:
        raise HTTPException(status_code=404, detail="Siswa atau mapel tidak ditemukan")

    # Get weight for this subject and student's class if exists, else default subject weight not mandatory
    class_name = student.get("class_name")
    weight = db["weight"].find_one({"subject_id": subject_id, "class_name": class_name})
    if not weight:
        weight = db["weight"].find_one({"subject_id": subject_id, "class_name": None})
    # Defaults
    tugas_w = (weight or {}).get("tugas", 30)
    kuis_w = (weight or {}).get("kuis", 20)
    uts_w = (weight or {}).get("uts", 20)
    uas_w = (weight or {}).get("uas", 30)
    total_w = tugas_w + kuis_w + uts_w + uas_w
    if total_w == 0:
        raise HTTPException(status_code=400, detail="Semua bobot 0")

    # Aggregate average per type
    from statistics import mean

    def avg_of(t: str) -> Optional[float]:
        docs = list(db["score"].find({"student_id": student_id, "subject_id": subject_id, "type": t}))
        if not docs:
            return None
        return float(mean([doc.get("value", 0) for doc in docs]))

    tugas_avg = avg_of("tugas")
    kuis_avg = avg_of("kuis")
    uts_avg = avg_of("uts")
    uas_avg = avg_of("uas")

    # Calculate final considering missing parts as 0 but report missing
    components = []
    final = 0.0

    for name, avg_val, w in [
        ("tugas", tugas_avg, tugas_w),
        ("kuis", kuis_avg, kuis_w),
        ("uts", uts_avg, uts_w),
        ("uas", uas_avg, uas_w),
    ]:
        comp_score = (avg_val if avg_val is not None else 0.0) * (w / 100.0)
        final += comp_score
        components.append({
            "type": name,
            "average": avg_val,
            "weight": w,
            "weighted_score": comp_score
        })

    kkm = float(subject.get("kkm", 70))
    status = "Tuntas" if final >= kkm else "Belum Tuntas"

    return {
        "student": {"id": student["id"], "full_name": student["full_name"], "class_name": student.get("class_name")},
        "subject": {"id": subject["id"], "name": subject["name"], "kkm": kkm},
        "weights": {"tugas": tugas_w, "kuis": kuis_w, "uts": uts_w, "uas": uas_w},
        "components": components,
        "final_score": round(final, 2),
        "status": status
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
