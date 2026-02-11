import json
import os
import sys


def main():
    try:
        from pymongo import MongoClient
    except ImportError:
        print("Install pymongo in .venv first", file=sys.stderr)
        sys.exit(1)

    sample_path = os.path.join(os.path.dirname(__file__), "sample.jsonl")
    if not os.path.isfile(sample_path):
        print(f"sample.jsonl not found: {sample_path}", file=sys.stderr)
        sys.exit(1)

    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGO_DATABASE", "kp_news")
    coll_name = os.environ.get("MONGO_COLLECTION", "articles")

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"MongoDB unavailable: {exc}", file=sys.stderr)
        sys.exit(1)

    collection = client[db_name][coll_name]

    loaded = 0
    with open(sample_path, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            doc = json.loads(line)
            source_url = doc.get("source_url")
            if not source_url:
                continue
            collection.replace_one({"source_url": source_url}, doc, upsert=True)
            loaded += 1

    print(f"Loaded into MongoDB: {loaded} documents")
    client.close()


if __name__ == "__main__":
    main()
