from html import escape
import json
import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse


def _mongo_collection():
    from pymongo import MongoClient

    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DATABASE", "kp_news")
    coll_name = os.getenv("MONGO_COLLECTION", "articles")
    client = MongoClient(uri, serverSelectionTimeoutMS=4000)
    db = client[db_name]
    return client, db[coll_name]


def _sample_docs(limit):
    sample_path = Path(__file__).resolve().parent / "sample.jsonl"
    if not sample_path.exists():
        return []
    docs = []
    with sample_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))
            if len(docs) >= limit:
                break
    return docs


app = FastAPI(title="KP News Viewer")


@app.get("/", response_class=HTMLResponse)
def render_articles(n: int = Query(default=10, ge=1, le=500)):
    source_label = "MongoDB"
    try:
        client, collection = _mongo_collection()
        docs = list(
            collection.find({}, {"_id": 0})
            .sort("publication_datetime", -1)
            .limit(n)
        )
    except Exception as exc:
        docs = _sample_docs(n)
        source_label = f"sample.jsonl fallback ({escape(str(exc))})"
    finally:
        if "client" in locals():
            client.close()

    blocks = []
    for idx, doc in enumerate(docs, start=1):
        title = escape(str(doc.get("title", "")))
        description = escape(str(doc.get("description", "")))
        article_text = escape(str(doc.get("article_text", "")))
        publication_datetime = escape(str(doc.get("publication_datetime", "")))
        source_url = escape(str(doc.get("source_url", "")))
        authors = ", ".join(doc.get("authors", []))
        keywords = ", ".join(doc.get("keywords", []))
        authors = escape(authors)
        keywords = escape(keywords)
        photo_url = doc.get("header_photo_url", "")
        photo_html = ""
        if photo_url:
            photo_html = (
                f"<img src='{escape(str(photo_url))}' alt='cover' "
                "style='max-width:420px;display:block;margin:8px 0;'>"
            )

        blocks.append(
            "<article style='border:1px solid #ddd;padding:12px;margin:12px 0;'>"
            f"<h3>{idx}. {title}</h3>"
            f"<p><b>Дата публикации:</b> {publication_datetime}</p>"
            f"<p><b>Авторы:</b> {authors}</p>"
            f"<p><b>Ключевые слова:</b> {keywords}</p>"
            f"<p>{description}</p>"
            f"{photo_html}"
            f"<p>{article_text[:1200]}...</p>"
            f"<p><a href='{source_url}' target='_blank'>{source_url}</a></p>"
            "</article>"
        )

    body = (
        "<html><head><meta charset='utf-8'><title>KP News</title></head><body>"
        f"<h1>KP News (N={n})</h1><p><b>Source:</b> {source_label}</p>"
        + "".join(blocks)
        + "</body></html>"
    )
    return HTMLResponse(content=body)
