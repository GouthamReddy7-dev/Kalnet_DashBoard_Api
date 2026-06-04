from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from typing import Optional, List
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os
import io

load_dotenv()

EXPECTED_COLUMNS = [
    "name",
    "state",
    "district",
    "type",
    "board",
    "student_count",
    "company_size_category",
    "website",
    "principal_name",
    "email",
    "phone",
    "icp_score",
    "icp_tier"
]

REQUIRED_COLUMNS = ["name", "state", "district"]

app = FastAPI(title="Kalnet AI Dashboard API")

@app.get("/")
def root():
    return{
        "status": "Backend Running",
        "database": "Connected"
    }

def get_engine():
    try:
        DATABASE_URL = os.getenv("DB_Connection")
        engine = create_engine(DATABASE_URL)
        return engine
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

class LeadItem(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    type: Optional[str] = None
    board: Optional[str] = None
    student_count: Optional[int] = None
    company_size_category: Optional[str] = None
    website: Optional[str] = None
    principal_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    icp_score: Optional[float] = None
    icp_tier: Optional[str] = None

def validate_columns(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )
    uploaded_columns = set(df.columns)
    expected_columns = set(EXPECTED_COLUMNS)
    unexpected_columns = uploaded_columns - expected_columns
    if unexpected_columns:
        print(
            f"Ignoring unexpected columns: "
            f"{list(unexpected_columns)}"
        )
    missing_columns = expected_columns - uploaded_columns
    missing_required = set(REQUIRED_COLUMNS) - uploaded_columns
    if missing_required:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {list(missing_required)}"
        )
    for col in (missing_columns - set(REQUIRED_COLUMNS)):
        df[col] = None
    return df[EXPECTED_COLUMNS]

@app.get("/leads")
def get_leads(
    id: Optional[int] = None,
    search: Optional[str] = None,
    state: Optional[str] = None,
    school_type: Optional[str] = None,
    tier: Optional[str] = None,
    has_email: Optional[bool] = None
):
    try:
        engine = get_engine()
        if engine is None:
            return {"error": "Database connection failed"}
        query = "SELECT * FROM institutions WHERE 1=1"
        params = {}
        if id:
            query += " AND id = :id"
            params["id"] = id
        if search:
            query += " AND (name LIKE :search OR district LIKE :search OR state LIKE :search)"
            params["search"] = f"%{search}%"
        if state and state != "None":
            query += " AND state = :state"
            params["state"] = state
        if school_type and school_type != "None":
            query += " AND type = :school_type"
            params["school_type"] = school_type
        if tier and tier != "None":
            query += " AND icp_tier = :tier"
            params["tier"] = tier
        if has_email:
            query += " AND email IS NOT NULL AND email != ''"
        print("Executing query:", query)
        print("Params:", params)
        ans = pd.read_sql(
            text(query),
            engine,
            params=params
        )
        return {
            "message": ans.to_dict(orient="records")
        }
    except Exception as e:
        print(e)
        return {
            "error": str(e)
        }
@app.get("/leads/{id}")
def get_lead(id: int):
    try:
        engine = get_engine()
        if engine is None:
            return {"error": "Database connection failed"}
        query = "SELECT * FROM institutions WHERE id = :id"
        params = {"id": id}
        ans = pd.read_sql(
            text(query),
            engine,
            params=params
        )
        if ans.empty:
            return {
                "message": "No Record Found"
            }
        return {
            "message": ans.to_dict(orient="records")
        }
    except Exception as e:
        print(e)
        return {
            "error": str(e)
        }
        
@app.post("/leads")
async def upload_leads(
    file: Optional[UploadFile] = File(None),
    leads_json: Optional[List[LeadItem]] = None
):
    """
    Accepts CSV file upload or JSON payload and inserts records into the database.
    """
    engine = get_engine()
    if engine is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    records_to_insert = []
    
    if file is not None:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        df = validate_columns(df)
        df = df.dropna(how="all")
        df = df.where(pd.notnull(df), None)
        records_to_insert = df.to_dict(orient="records")
        
    elif leads_json is not None:
        df = pd.DataFrame([
            item.dict(exclude_none=True)
            for item in leads_json
        ])
        df = validate_columns(df)
        records_to_insert = df.to_dict(orient="records")
    else:
        raise HTTPException(
            status_code=400,
            detail="Either a CSV file or a JSON payload must be provided"
        )
    try:
        inserted_count = 0
        with engine.begin() as conn:
            df.to_sql(
                "institutions",
                con=conn,
                if_exists="append",
                index=False
            )
            inserted_count = len(df)    
        return {
            "success": True,
            "message": f"Successfully uploaded and inserted {inserted_count} records into the database"
        }
    except Exception as e:
        print(f"Database insertion error: {e}")
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {str(e)}")
