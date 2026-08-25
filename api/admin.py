"""
管理 API 路由 - 需要认证
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends
from datetime import datetime, timedelta
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from core.auth import get_current_user
from core.database import (
    create_article, update_article, delete_article,
    create_category, delete_category
)
from core.backup import create_backup, download_backup, delete_backup, clean_old_backups
from core.config import verify_password, get_db, ADMIN_PASSWORD_HASH, BACKUP_RETENTION_DAYS, UPLOAD_DIR
import os
import json
import secrets
import uuid
import bcrypt
import core.config

router = APIRouter(prefix="/api", tags=["admin"])


class ArticleCreate(BaseModel):
    title: str
    content: str
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = True
    is_encrypted: Optional[bool] = False
    encryption_key: Optional[str] = None


class ArticleUpdate(BaseModel):
    title: str
    content: str


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


@router.post("/auth/login")
@router.get("/auth/login")
def login(request: Request, password: str = Form(None)):
    """登录获取 Token"""
    
    # 支持 query parameter
    if password is None:
        password = request.query_params.get("password")
    
    if not password:
        raise HTTPException(status_code=422, detail="密码不能为空")
    
    if not verify_password(password):
        raise HTTPException(status_code=401, detail="密码错误")
    
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    
    with get_db() as conn:
        conn.execute("DELETE FROM tokens WHERE username = ?", ("admin",))
        conn.execute(
            "INSERT INTO tokens (token, username, expires_at) VALUES (?, ?, ?)",
            (token, "admin", expires_at)
        )
    
    return {"token": token, "username": "admin"}


@router.post("/auth/change-password")
def change_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """修改密码"""
    
    if not verify_password(old_password):
        raise HTTPException(status_code=401, detail="旧密码错误")
    
    if len(new_password) < 4:
        raise HTTPException(status_code=422, detail="新密码至少4位")
    
    # 更新密码哈希
    core.config.ADMIN_PASSWORD_HASH = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    
    # 清除所有旧 token
    with get_db() as conn:
        conn.execute("DELETE FROM tokens")
    
    return {"message": "密码修改成功，请重新登录"}


@router.post("/articles")
def create_article_api(article: ArticleCreate, user: dict = Depends(get_current_user)):
    """创建文章"""
    return create_article(
        title=article.title,
        content=article.content,
        category_id=article.category_id,
        tags=article.tags,
        is_public=article.is_public,
        is_encrypted=article.is_encrypted,
        encryption_key=article.encryption_key
    )


@router.put("/articles/{slug}")
def update_article_api(slug: str, article: ArticleUpdate, user: dict = Depends(get_current_user)):
    """更新文章"""
    return update_article(slug=slug, title=article.title, content=article.content)


@router.delete("/articles/{slug}")
def delete_article_api(slug: str, user: dict = Depends(get_current_user)):
    """删除文章"""
    return delete_article(slug=slug)


@router.post("/categories")
def create_category_api(category: CategoryCreate, user: dict = Depends(get_current_user)):
    """创建分类"""
    return create_category(name=category.name, description=category.description)


@router.delete("/categories/{category_id}")
def delete_category_api(category_id: int, user: dict = Depends(get_current_user)):
    """删除分类"""
    return delete_category(category_id=category_id)


@router.post("/backup")
def create_backup_api(user: dict = Depends(get_current_user)):
    """创建备份"""
    return create_backup()


@router.get("/backups/{filename}")
def download_backup_api(filename: str, user: dict = Depends(get_current_user)):
    """下载备份"""
    content, status = download_backup(filename)
    if status == 404:
        raise HTTPException(status_code=404, detail="备份不存在")
    return Response(content=content, media_type="application/gzip", 
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.delete("/backups/{filename}")
def delete_backup_api(filename: str, user: dict = Depends(get_current_user)):
    """删除备份"""
    return delete_backup(filename)


@router.post("/backup/cleanup")
def cleanup_backups_api(user: dict = Depends(get_current_user)):
    """清理旧备份"""
    return clean_old_backups(BACKUP_RETENTION_DAYS)


@router.post("/uploads")
def upload_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """上传图片"""
    
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as f:
        content = file.file.read()
        f.write(content)
    
    return {
        "message": "上传成功",
        "filename": unique_filename,
        "url": f"/api/uploads/{unique_filename}"
    }

