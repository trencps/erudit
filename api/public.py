"""
公共 API 路由 - 无需认证
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from core.database import get_articles, get_article, search_articles, get_categories, get_stats
from core.backup import get_backups
import json
import os
from fastapi import Depends

router = APIRouter(tags=["public"])


def get_db():
    """获取数据库连接"""
    from core.config import get_db as _get_db
    return _get_db()


@router.get("/health")
def health_check():
    """健康检查"""
    try:
        stats = get_stats()
        return {"status": "ok", "articles": stats["articles"], "categories": stats["categories"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/")
def serve_frontend():
    """提供前端页面"""
    ui_path = "/app/static/index.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Erudit - 知识管理系统</h1><p>前端页面未找到</p>")


@router.get("/admin")
def serve_admin():
    """提供管理后台页面"""
    ui_path = "/app/static/admin.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Erudit 管理后台</h1><p>管理页面未找到</p>")


@router.get("/articles")
def list_articles(
    category_id: int = Query(None),
    tag: str = Query(None),
    public_only: bool = Query(True),
    page: int = Query(1),
    page_size: int = Query(20)
):
    """获取文章列表"""
    return get_articles(category_id=category_id, tag=tag, 
                       public_only=public_only, page=page, page_size=page_size)


@router.get("/articles/{slug}")
def get_article_by_slug(slug: str):
    """获取单篇文章"""
    article = get_article(slug)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return article


@router.get("/categories")
def list_categories():
    """获取分类列表"""
    return get_categories()


@router.get("/tags")
def list_tags():
    """获取所有标签"""
    from core.database import get_tags
    return get_tags()


@router.get("/stats")
def get_statistics():
    """获取统计信息"""
    return get_stats()


@router.get("/search")
def search(keyword: str = Query(...)):
    """全文搜索"""
    results = search_articles(keyword)
    return {"articles": results, "total": len(results), "keyword": keyword}


@router.get("/backups")
def list_backups():
    """获取备份列表"""
    return get_backups()


# 友情链接设置 API
@router.get("/api/settings")
def get_settings():
    """获取设置（包含友情链接）"""
    from core.config import get_db
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", ('links',)).fetchone()
            if row:
                links = json.loads(row[0])
            else:
                links = []
    except:
        links = []
    return {"settings": {"links": links}}


@router.put("/api/settings")
def update_settings(data: dict):
    """更新设置（友情链接）"""
    from core.config import get_db
    links = data.get('links', [])
    with get_db() as conn:
        conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', 
                    ('links', json.dumps(links)))
    return {"message": "更新成功"}


@router.get("/rss")
def get_rss(category: str = Query(None)):
    """获取 RSS feed"""
    articles = get_articles(public_only=True) if not category else get_articles(category_id=category)
    
    rss_items = []
    for article in articles.get("articles", []):
        rss_items.append(f"""
            <item>
                <title>{article['title']}</title>
                <link>/articles/{article['slug']}</link>
                <description>{article['content'][:200]}...</description>
                <pubDate>{article['created_at']}</pubDate>
            </item>
        """)
    
    rss_channel = f"""
    <channel>
        <title>Erudit 知识库</title>
        <link>http://localhost:8000</link>
        <description>个人知识管理系统</description>
        {''.join(rss_items)}
    </channel>
    """
    
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    {rss_channel}
</rss>"""
    
    return Response(content=rss_xml, media_type="application/rss+xml")


@router.get("/metrics")
def get_metrics():
    """获取系统指标"""
    stats = get_stats()
    backups = get_backups()
    total_backup_size = sum(b["size"] for b in backups)
    
    return {
        "articles": stats["articles"],
        "categories": stats["categories"],
        "backups": len(backups),
        "backup_size_bytes": total_backup_size,
        "backup_size_readable": format_size(total_backup_size),
        "version": "3.0.0"
    }


# ========== 新增路由 ==========

@router.get("/login")
def serve_login():
    """登录页面"""
    ui_path = "/app/static/login.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>登录</h1>")


@router.get("/links")
def serve_links():
    """友情链接页面"""
    ui_path = "/app/static/links.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>友情链接</h1>")


@router.get("/article/{slug}")
def serve_article(slug: str):
    """文章详情页"""
    ui_path = "/app/static/article.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>文章详情</h1>")


@router.get("/admin/create")
def serve_admin_create():
    """新建文章页面"""
    ui_path = "/app/static/admin_create.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>新建文章</h1>")


@router.get("/admin/articles")
def serve_admin_articles():
    """文章管理页面"""
    ui_path = "/app/static/admin_articles.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>文章管理</h1>")


@router.get("/admin/categories")
def serve_admin_categories():
    """分类管理页面"""
    ui_path = "/app/static/admin_categories.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>分类管理</h1>")


@router.get("/admin/tags")
def serve_admin_tags():
    """标签管理页面"""
    ui_path = "/app/static/admin_tags.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>标签管理</h1>")


@router.get("/admin/settings")
def serve_admin_settings():
    """站点管理页面"""
    ui_path = "/app/static/admin_settings.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>站点管理</h1>")


@router.get("/admin/links")
def serve_admin_links():
    """友情链接管理页面"""
    ui_path = "/app/static/admin_links.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>友情链接管理</h1>")


def format_size(bytes_size: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

@router.get("/category/{category_id}")
def serve_category_page(category_id: int):
    """分类文章列表页面"""
    import os
    ui_path = "/app/static/index.html"
    if os.path.exists(ui_path):
        with open(ui_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>分类文章</h1>")
