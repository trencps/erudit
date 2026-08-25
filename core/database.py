"""
数据库操作模块
"""
import sqlite3
import json
from datetime import datetime
from core.config import get_db, generate_slug


def get_articles(category_id: int = None, tag: str = None, 
                 public_only: bool = True, page: int = 1, page_size: int = 20) -> dict:
    """获取文章列表"""
    with get_db() as conn:
        # 总数
        if category_id:
            total = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE category_id = ?", 
                (category_id,)
            ).fetchone()[0]
        elif tag:
            total = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE tags LIKE ?", 
                (f'%"{tag}"%',)
            ).fetchone()[0]
        else:
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        
        # 列表
        offset = (page - 1) * page_size
        if category_id:
            rows = conn.execute(
                "SELECT * FROM articles WHERE category_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (category_id, page_size, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM articles ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset)
            ).fetchall()
        
        articles = [dict(r) for r in rows]
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "has_next": page < (total + page_size - 1) // page_size
    }


def get_article(slug: str) -> dict:
    """获取单篇文章"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
        if not row:
            return None
        return dict(row)


def create_article(title: str, content: str, category_id: int = None, 
                   tags: list = None, is_public: bool = True, 
                   is_encrypted: bool = False, encryption_key: str = None) -> dict:
    """创建文章"""
    slug = generate_slug(title)
    tags_json = json.dumps(tags) if tags else None
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO articles (title, slug, content, category_id, tags, is_public, is_encrypted, encryption_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, slug, content, category_id, tags_json, 
             1 if is_public else 0, 1 if is_encrypted else 0, encryption_key)
        )
        
        # 保存版本历史
        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM article_versions WHERE article_id = last_insert_rowid()"
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO article_versions (article_id, version, title, content)
               VALUES (last_insert_rowid(), ?, ?, ?)""",
            (version, title, content)
        )
    
    return {"message": "文章创建成功", "slug": slug}


def update_article(slug: str, title: str, content: str) -> dict:
    """更新文章"""
    with get_db() as conn:
        # 保存旧版本
        article = conn.execute("SELECT id, title, content FROM articles WHERE slug = ?", (slug,)).fetchone()
        if article:
            version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM article_versions WHERE article_id = ?",
                (article["id"],)
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO article_versions (article_id, version, title, content)
                   VALUES (?, ?, ?, ?)""",
                (article["id"], version, article["title"], article["content"])
            )
        
        conn.execute(
            "UPDATE articles SET title = ?, content = ?, updated_at = ? WHERE slug = ?",
            (title, content, datetime.utcnow().isoformat(), slug)
        )
    
    return {"message": "文章更新成功"}


def delete_article(slug: str) -> dict:
    """删除文章"""
    with get_db() as conn:
        conn.execute("DELETE FROM articles WHERE slug = ?", (slug,))
        conn.execute("DELETE FROM article_versions WHERE article_id = (SELECT id FROM articles WHERE slug = ?)", (slug,))
    
    return {"message": "文章删除成功"}


def search_articles(keyword: str) -> list:
    """全文搜索（支持前缀匹配）"""
    with get_db() as conn:
        # 使用通配符进行前缀匹配
        search_query = f"{keyword}*"
        rows = conn.execute(
            "SELECT * FROM articles_fts WHERE articles_fts MATCH ?",
            (search_query,)
        ).fetchall()
        # 获取完整文章信息
        results = []
        for row in rows:
            article = conn.execute("SELECT * FROM articles WHERE id = ?", (row["rowid"],)).fetchone()
            if article:
                results.append(dict(article))
        return results


def get_categories() -> list:
    """获取分类列表"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def create_category(name: str, description: str = None) -> dict:
    """创建分类"""
    slug = name.lower().replace(" ", "-")
    with get_db() as conn:
        conn.execute(
            "INSERT INTO categories (name, slug, description) VALUES (?, ?, ?)",
            (name, slug, description)
        )
    return {"message": "分类创建成功"}


def delete_category(category_id: int) -> dict:
    """删除分类"""
    with get_db() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return {"message": "分类删除成功"}


def get_tags() -> list:
    """获取所有标签"""
    with get_db() as conn:
        rows = conn.execute("SELECT tags FROM articles WHERE tags IS NOT NULL").fetchall()
        tags = set()
        for row in rows:
            if row["tags"]:
                try:
                    tags.update(json.loads(row["tags"]))
                except:
                    pass
        return sorted(list(tags))


def get_stats() -> dict:
    """获取统计信息"""
    with get_db() as conn:
        articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        return {"articles": articles, "categories": categories}