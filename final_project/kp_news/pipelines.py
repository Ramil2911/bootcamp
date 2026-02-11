import base64
import urllib.request
from datetime import datetime, timezone

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


REQUIRED_FIELDS = (
    "title",
    "description",
    "article_text",
    "publication_datetime",
    "keywords",
    "authors",
    "source_url",
)


def _clean_string(value):
    if value is None:
        return ""
    return " ".join(str(value).split())


def _clean_list(values):
    if not values:
        return []
    result = []
    seen = set()
    for value in values:
        cleaned = _clean_string(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _normalize_datetime(raw_value):
    value = _clean_string(raw_value)
    if not value:
        return ""

    # Normalize common ISO formats to UTC-aware ISO 8601.
    candidate = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return value


class ValidationAndNormalizePipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        adapter["title"] = _clean_string(adapter.get("title"))
        adapter["description"] = _clean_string(adapter.get("description"))
        adapter["article_text"] = _clean_string(adapter.get("article_text"))
        adapter["publication_datetime"] = _normalize_datetime(
            adapter.get("publication_datetime")
        )
        adapter["keywords"] = _clean_list(adapter.get("keywords"))
        adapter["authors"] = _clean_list(adapter.get("authors"))
        adapter["source_url"] = _clean_string(adapter.get("source_url"))
        adapter["header_photo_url"] = _clean_string(adapter.get("header_photo_url"))
        adapter["header_photo_base64"] = _clean_string(adapter.get("header_photo_base64"))

        for field in REQUIRED_FIELDS:
            value = adapter.get(field)
            if isinstance(value, list):
                if not value:
                    raise DropItem(f"Missing required list field: {field}")
            elif not value:
                raise DropItem(f"Missing required field: {field}")

        return item


class PhotoDownloaderPipeline:
    def __init__(self, timeout_seconds, max_bytes):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            timeout_seconds=crawler.settings.getint("PHOTO_DOWNLOAD_TIMEOUT_SECONDS", 8),
            max_bytes=crawler.settings.getint("PHOTO_DOWNLOAD_MAX_BYTES", 5_000_000),
        )

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        photo_url = adapter.get("header_photo_url")
        if not photo_url:
            return item

        try:
            request = urllib.request.Request(
                photo_url,
                headers={"User-Agent": spider.settings.get("USER_AGENT", "Scrapy")},
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read(self.max_bytes + 1)
                if len(content) > self.max_bytes:
                    spider.logger.debug(
                        "Photo exceeds max size (%s bytes), skipping base64: %s",
                        self.max_bytes,
                        photo_url,
                    )
                    return item
                adapter["header_photo_base64"] = base64.b64encode(content).decode("ascii")
        except Exception as exc:
            spider.logger.debug("Photo download failed for %s: %s", photo_url, exc)

        return item


class MongoPipeline:
    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.client = None
        self.collection = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "kp_news"),
            mongo_collection=crawler.settings.get("MONGO_COLLECTION", "articles"),
        )

    def open_spider(self, spider):
        try:
            from pymongo import MongoClient
        except ImportError:
            spider.logger.warning("pymongo not installed, MongoPipeline disabled")
            return

        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")
            db = self.client[self.mongo_db]
            self.collection = db[self.mongo_collection]
            self.collection.create_index("source_url", unique=True)
            self.collection.create_index("publication_datetime")
        except Exception as exc:
            spider.logger.warning("MongoDB unavailable, writes disabled: %s", exc)
            self.collection = None

    def close_spider(self, spider):
        if self.client is not None:
            self.client.close()

    def process_item(self, item, spider):
        if self.collection is None:
            return item

        data = dict(ItemAdapter(item))
        source_url = data.get("source_url")
        if not source_url:
            return item

        try:
            self.collection.replace_one({"source_url": source_url}, data, upsert=True)
        except Exception as exc:
            spider.logger.warning("Mongo write error for %s: %s", source_url, exc)
        return item
