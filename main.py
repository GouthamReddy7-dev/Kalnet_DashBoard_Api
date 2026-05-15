from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

load_dotenv()

app = FastAPI()

def get_engine():

    try:

        DATABASE_URL = os.getenv("DATABASE_URL")

        engine = create_engine(
            DATABASE_URL
        )

        return engine

    except Exception as e:

        print(e)

        return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

class Data(BaseModel):

    id: Optional[int] = None
    search: Optional[str] = None
    state: Optional[str] = None
    school_type: Optional[str] = None
    tier: Optional[str] = None
    has_email: Optional[bool] = None

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

        print(query)
        print(params)

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

        params = {
            "id": id
        }

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