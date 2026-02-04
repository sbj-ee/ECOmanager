import logging
import os
import tempfile

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Header, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import shutil
from eco_manager import ECO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ECO Manager API")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS - configure via CORS_ORIGINS env var (comma-separated) for production
cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10MB default

eco_system = ECO(
    db_path=os.environ.get("DATABASE_PATH", "eco_system.db"),
    attachments_dir=os.environ.get("ATTACHMENTS_DIR", "attachments"),
)

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Models
class User(BaseModel):
    id: int
    username: str
    is_admin: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

class TokenRequest(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

class TokenResponse(BaseModel):
    token: str
    is_admin: bool

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

# Dependencies
def get_current_user(x_api_token: str = Header(...)) -> User:
    user_data = eco_system.get_user_from_token(x_api_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid API Token")
    return User(**user_data)

def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

@app.post("/register", status_code=201)
def register(req: UserRegister):
    success = eco_system.register_user(req.username, req.password, req.first_name, req.last_name, req.email)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

@app.post("/token", response_model=TokenResponse)
def generate_token(req: TokenRequest):
    token = eco_system.generate_token(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # helper to get admin status for response
    # We could query, or just assume checking token immediately is fast
    user_data = eco_system.get_user_from_token(token)
    is_admin = bool(user_data['is_admin']) if user_data else False
    
    return {"token": token, "is_admin": is_admin}

@app.post("/logout")
def logout(x_api_token: str = Header(...)):
    revoked = eco_system.revoke_token(x_api_token)
    if not revoked:
        raise HTTPException(status_code=401, detail="Invalid API Token")
    return {"message": "Logged out successfully"}

@app.post("/ecos", response_model=Dict[str, Any], status_code=201)
def create_eco(item: ECOCreate, user: User = Depends(get_current_user)):
    eco_id = eco_system.create_eco(item.title, item.description, user.username)
    return {"eco_id": eco_id, "message": "ECO created successfully"}

@app.get("/ecos", response_model=List[ECOItem])
def list_ecos(
    user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    ecos = eco_system.list_ecos(limit=limit, offset=offset, search=search, status=status)
    return [{"id": r[0], "title": r[1], "status": r[2], "created_at": r[3]} for r in ecos]

@app.get("/ecos/{eco_id}")
def get_eco(eco_id: int, user: User = Depends(get_current_user)):
    details = eco_system.get_eco_details(eco_id)
    if not details:
        raise HTTPException(status_code=404, detail="ECO not found")
    return details

@app.post("/ecos/{eco_id}/submit")
def submit_eco(eco_id: int, action: ECOAction, user: User = Depends(get_current_user)):
    success = eco_system.submit_eco(eco_id, user.username, action.comment)
    if not success:
         raise HTTPException(status_code=400, detail="Operation failed. Check ECO status or ID.")
    return {"message": "ECO submitted"}

@app.post("/ecos/{eco_id}/approve")
def approve_eco(eco_id: int, action: ECOAction, user: User = Depends(get_current_user)):
    success = eco_system.approve_eco(eco_id, user.username, action.comment)
    if not success:
         raise HTTPException(status_code=400, detail="Operation failed. Check ECO status.")
    return {"message": "ECO approved"}

@app.post("/ecos/{eco_id}/reject")
def reject_eco(eco_id: int, action: ECOAction, user: User = Depends(get_current_user)):
    if not action.comment:
        raise HTTPException(status_code=400, detail="Comment required for rejection")
    success = eco_system.reject_eco(eco_id, user.username, action.comment)
    if not success:
         raise HTTPException(status_code=400, detail="Operation failed. Check ECO status.")
    return {"message": "ECO rejected"}

@app.post("/ecos/{eco_id}/attachments")
def add_attachment(eco_id: int, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    # Read file content and enforce size limit
    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        success = eco_system.add_attachment(eco_id, file.filename, tmp_path, user.username)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to add attachment")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return {"message": "Attachment added"}

@app.get("/ecos/{eco_id}/attachments/{filename}")
def get_attachment(eco_id: int, filename: str, user: User = Depends(get_current_user)):
    file_path = eco_system.get_attachment_path(eco_id, filename)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(file_path, filename=filename)

@app.get("/ecos/{eco_id}/report")
def download_report(eco_id: int, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    details = eco_system.get_eco_details(eco_id)
    if not details:
        raise HTTPException(status_code=404, detail="ECO not found")
        
    filename = f"eco_{eco_id}_report.md"
    success = eco_system.generate_report(eco_id, filename)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate report")
        
    background_tasks.add_task(os.remove, filename)
    return FileResponse(filename, filename=filename)

# Admin Endpoints
@app.get("/admin/users", response_model=List[User])
def list_users(admin: User = Depends(get_current_admin)):
    users = eco_system.get_all_users()
    return [User(**u) for u in users]

@app.delete("/admin/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(get_current_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=403, detail="Cannot delete your own account")
    success = eco_system.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="User not found or is the last admin")
    return {"message": "User deleted"}
