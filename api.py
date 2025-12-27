from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import shutil
import os
from eco_manager import ECO

app = FastAPI(title="ECO Manager API")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS (optional but good for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

eco_system = ECO()

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

# Dependencies
def get_current_user(x_api_token: str = Header(...)):
    user = eco_system.get_user_from_token(x_api_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Token")
    return user

# Models
class TokenRequest(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str

class ECOCreate(BaseModel):
    title: str
    description: str

class ECOAction(BaseModel):
    comment: Optional[str] = None

class ECOItem(BaseModel):
    id: int
    title: str
    status: str
    created_at: str

@app.post("/register", status_code=201)
def register(req: UserRegister):
    success = eco_system.register_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

@app.post("/token", response_model=TokenResponse)
def generate_token(req: TokenRequest):
    token = eco_system.generate_token(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token}

@app.post("/ecos", response_model=Dict[str, Any], status_code=201)
def create_eco(item: ECOCreate, username: str = Depends(get_current_user)):
    eco_id = eco_system.create_eco(item.title, item.description, username)
    return {"eco_id": eco_id, "message": "ECO created successfully"}

@app.get("/ecos", response_model=List[ECOItem])
def list_ecos(username: str = Depends(get_current_user)):
    ecos = eco_system.list_ecos()
    return [{"id": r[0], "title": r[1], "status": r[2], "created_at": r[3]} for r in ecos]

@app.get("/ecos/{eco_id}")
def get_eco(eco_id: int, username: str = Depends(get_current_user)):
    details = eco_system.get_eco_details(eco_id)
    if not details:
        raise HTTPException(status_code=404, detail="ECO not found")
    return details

@app.post("/ecos/{eco_id}/submit")
def submit_eco(eco_id: int, action: ECOAction, username: str = Depends(get_current_user)):
    success = eco_system.submit_eco(eco_id, username, action.comment)
    if not success:
         raise HTTPException(status_code=400, detail="Operation failed. Check ECO status or ID.")
    return {"message": "ECO submitted"}

@app.post("/ecos/{eco_id}/approve")
def approve_eco(eco_id: int, action: ECOAction, username: str = Depends(get_current_user)):
    success = eco_system.approve_eco(eco_id, username, action.comment)
    if not success:
         raise HTTPException(status_code=400, detail="Operation failed. Check ECO status.")
    return {"message": "ECO approved"}

@app.post("/ecos/{eco_id}/reject")
def reject_eco(eco_id: int, action: ECOAction, username: str = Depends(get_current_user)):
    if not action.comment:
        raise HTTPException(status_code=400, detail="Comment required for rejection")
    success = eco_system.reject_eco(eco_id, username, action.comment)
    if not success:
         raise HTTPException(status_code=400, detail="Operation failed. Check ECO status.")
    return {"message": "ECO rejected"}

@app.post("/ecos/{eco_id}/attachments")
def add_attachment(eco_id: int, file: UploadFile = File(...), username: str = Depends(get_current_user)):
    # Note: Using Depends on a route with UploadFile might require sending token in header, which is standard.
    # We replaced username=Form(...) with automatic detection.
    
    tmp_path = f"tmp_{file.filename}"
    try:
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        success = eco_system.add_attachment(eco_id, file.filename, tmp_path, username)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add attachment")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return {"message": "Attachment added"}

@app.get("/ecos/{eco_id}/attachments/{filename}")
def get_attachment(eco_id: int, filename: str, username: str = Depends(get_current_user)):
    file_path = eco_system.get_attachment_path(eco_id, filename)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(file_path, filename=filename)

@app.get("/ecos/{eco_id}/report")
def download_report(eco_id: int, background_tasks: BackgroundTasks, username: str = Depends(get_current_user)):
    details = eco_system.get_eco_details(eco_id)
    if not details:
        raise HTTPException(status_code=404, detail="ECO not found")
        
    filename = f"eco_{eco_id}_report.md"
    success = eco_system.generate_report(eco_id, filename)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate report")
        
    background_tasks.add_task(os.remove, filename)
    return FileResponse(filename, filename=filename)
