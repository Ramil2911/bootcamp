import argparse
import json
from pathlib import Path


DEFAULT_FIELDS = [
    "title",
    "publication_datetime",
    "authors",
    "keywords",
    "source_url",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Просмотр собранных данных из JSONL-файла."
    )
    parser.add_argument(
        "--file",
        default="sample.jsonl",
        help="Путь к JSONL-файлу (по умолчанию: sample.jsonl).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Сколько записей показать (по умолчанию: 10).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Показать полный объект целиком.",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=DEFAULT_FIELDS,
        help="Список полей для компактного вывода.",
    )
    parser.add_argument(
        "--preview-len",
        type=int,
        default=220,
        help="Максимальная длина article_text_preview (по умолчанию: 220).",
    )
    return parser.parse_args()


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            raw = line.strip().lstrip("\x00")
            if not raw or not raw.startswith("{"):
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                continue


def compact_record(record: dict, fields: list[str], preview_len: int):
    data = {key: record.get(key) for key in fields}
    article_text = record.get("article_text") or ""
    data["article_text_preview"] = article_text[:preview_len]
    data["header_photo_base64_len"] = len(record.get("header_photo_base64") or "")
    return data


def main():
    args = parse_args()
    path = Path(args.file)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        raise SystemExit(f"Файл не найден: {path}")

    shown = 0
    for index, record in enumerate(iter_jsonl(path), start=1):
        if shown >= args.limit:
            break
        shown += 1
        print(f"\n--- Запись #{index} ---")
        if args.full:
            print(json.dumps(record, ensure_ascii=False, indent=2))
        else:
            print(
                json.dumps(
                    compact_record(record, args.fields, args.preview_len),
                    ensure_ascii=False,
                    indent=2,
                )
            )

    print(f"\nПоказано записей: {shown}")


if __name__ == "__main__":
    main()
