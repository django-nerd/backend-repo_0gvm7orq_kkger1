"""
Database Schemas for Report Card App

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

class Student(BaseModel):
    full_name: str = Field(..., description="Nama lengkap siswa")
    student_number: str = Field(..., description="NIS/NISN atau nomor induk")
    class_name: str = Field(..., description="Kelas, misal: VIIA, IXB, X IPA 1")
    gender: Optional[str] = Field(None, description="L/P")
    birth_date: Optional[datetime] = Field(None, description="Tanggal lahir")

class Subject(BaseModel):
    name: str = Field(..., description="Nama mata pelajaran")
    kkm: float = Field(70, ge=0, le=100, description="Kriteria ketuntasan minimal")

class Weight(BaseModel):
    subject_id: str = Field(..., description="ID subject")
    class_name: Optional[str] = Field(None, description="Berlaku untuk kelas tertentu (opsional)")
    tugas: float = Field(30, ge=0, le=100, description="Bobot tugas dalam persen")
    kuis: float = Field(20, ge=0, le=100, description="Bobot kuis dalam persen")
    uts: float = Field(20, ge=0, le=100, description="Bobot UTS dalam persen")
    uas: float = Field(30, ge=0, le=100, description="Bobot UAS dalam persen")

class Score(BaseModel):
    student_id: str = Field(..., description="ID siswa")
    subject_id: str = Field(..., description="ID mata pelajaran")
    type: str = Field(..., description="tugas|kuis|uts|uas")
    value: float = Field(..., ge=0, le=100, description="Nilai 0-100")
    note: Optional[str] = Field(None, description="Catatan (opsional)")
    date: Optional[datetime] = Field(None, description="Tanggal penilaian")

# Note: The Flames database viewer may read schemas via /schema endpoint in backend.
