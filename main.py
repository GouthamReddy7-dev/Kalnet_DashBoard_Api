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

app = FastAPI(title="Kalnet AI Dashboard API")

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
    district: Optional[str] = None
    state: Optional[str] = None
    type: Optional[str] = None
    icp_tier: Optional[str] = None
    email: Optional[str] = None

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

    # Case 1: CSV or Excel File Upload
    if file is not None:
        try:
            contents = await file.read()
            filename = file.filename.lower() if file.filename else ""
            
            # Read CSV or Excel depending on extension/content-type
            if filename.endswith(('.xlsx', '.xls')) or file.content_type in [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel"
            ]:
                # Note: requires openpyxl package to read xlsx
                df = pd.read_excel(io.BytesIO(contents))
            else:
                df = pd.read_csv(io.BytesIO(contents))
            
            # Map common headers to DB columns (using normalized lowercase keys)
            column_mapping = {
                # Name mapping
                'school_name': 'name',
                'institution_name': 'name',
                'aishe code name': 'name',
                'name': 'name',
                'search': 'name',
                
                # State mapping
                'state': 'state',
                
                # District mapping
                'district': 'district',
                
                # Type mapping
                'college type': 'type',
                'school_type': 'type',
                'schooltype': 'type',
                'type': 'type',
                
                # Board / affiliation mapping
                'manegement': 'board',
                'management': 'board',
                'university name': 'board',
                'board': 'board',
                
                # Website mapping
                'website': 'website',
                
                # Student count mapping
                'student_count': 'student_count',
                'student count': 'student_count',
                
                # Company size mapping
                'company_size_category': 'company_size_category',
                'company size': 'company_size_category',
                
                # Principal name mapping
                'principal_name': 'principal_name',
                'principal name': 'principal_name',
                
                # Email mapping
                'email': 'email',
                
                # Phone mapping
                'phone': 'phone',
                'phone number': 'phone',
                
                # ICP Score mapping
                'icp_score': 'icp_score',
                
                # ICP Tier mapping
                'icp_tier': 'icp_tier',
                'tier': 'icp_tier'
            }
            
            # Normalize df columns to strip whitespace
            df.columns = [str(col).strip() for col in df.columns]
            
            # Map columns case-insensitively, avoiding duplicate destination columns
            lowercase_cols = {col.lower(): col for col in df.columns}
            rename_dict = {}
            for key_variant, db_col in column_mapping.items():
                if key_variant in lowercase_cols and db_col not in rename_dict.values():
                    rename_dict[lowercase_cols[key_variant]] = db_col
            
            df = df.rename(columns=rename_dict)
            
            # Keep only the valid database columns that exist in the DataFrame
            valid_cols = [
                'name', 'state', 'district', 'type', 'board', 
                'student_count', 'company_size_category', 'website', 
                'principal_name', 'email', 'phone', 'icp_score', 'icp_tier'
            ]
            cols_to_keep = [col for col in valid_cols if col in df.columns]
            df_filtered = df[cols_to_keep]
            
            # Convert NaN to None for SQL database insertion
            df_filtered = df_filtered.where(pd.notnull(df_filtered), None)
            records_to_insert = df_filtered.to_dict(orient="records")
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Case 2: JSON Payload
    elif leads_json is not None:
        records_to_insert = [
            item.dict(exclude_none=True) for item in leads_json
        ]
    
    else:
        raise HTTPException(status_code=400, detail="Either a CSV file or a JSON payload must be provided")

    if not records_to_insert:
        return {"message": "No valid records to insert"}

    # Insert records into database
    try:
        # Prepare insert statement dynamic query or use pandas.to_sql
        # Let's insert using SQL connection to avoid table replacement issues
        inserted_count = 0
        with engine.begin() as conn:
            for record in records_to_insert:
                # Build columns and values dynamically
                cols = list(record.keys())
                if not cols:
                    continue
                # Exclude id if it's auto-incrementing and not passed, or passed as None
                if 'id' in cols and record['id'] is None:
                    cols.remove('id')
                    
                columns_str = ", ".join(cols)
                placeholders_str = ", ".join([f":{col}" for col in cols])
                
                query_str = f"INSERT INTO institutions ({columns_str}) VALUES ({placeholders_str})"
                conn.execute(text(query_str), record)
                inserted_count += 1
                
        return {
            "success": True,
            "message": f"Successfully uploaded and inserted {inserted_count} records into the database"
        }
        
    except Exception as e:
        print(f"Database insertion error: {e}")
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {str(e)}")
