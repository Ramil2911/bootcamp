import argparse
import base64
import io
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request

try:
    from PIL import Image, ImageTk
except ImportError as exc:
    raise SystemExit(
        "Pillow is required for GUI image rendering. Install it in .venv: "
        "uv pip install --python /home/ramil/bootcamp/.venv/bin/python pillow"
    ) from exc


DISPLAY_FIELDS = [
    "title",
    "description",
    "publication_datetime",
    "authors",
    "keywords",
    "source_url",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="GUI viewer for collected JSONL records."
    )
    parser.add_argument(
        "--file",
        default="sample.jsonl",
        help="Path to JSONL file (default: sample.jsonl).",
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


class DataViewerApp:
    def __init__(self, root: tk.Tk, records: list[dict]):
        self.root = root
        self.records = records
        self.image_cache = {}
        self.photo_ref = None

        self.root.title("Collected Data Viewer")
        self.root.geometry("1280x760")

        self._build_ui()
        self._fill_list()
        if self.records:
            self.listbox.selection_set(0)
            self.on_select(None)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=3)
        self.root.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(self.root, padding=8)
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)

        ttk.Label(left_frame, text="Articles").grid(row=0, column=0, sticky="w")

        self.listbox = tk.Listbox(left_frame, exportselection=False)
        self.listbox.grid(row=1, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        controls = ttk.Frame(left_frame)
        controls.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        ttk.Button(controls, text="Prev", command=self.select_prev).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(controls, text="Next", command=self.select_next).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        right_frame = ttk.Frame(self.root, padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=3)
        right_frame.rowconfigure(3, weight=2)

        self.title_var = tk.StringVar(value="")
        title_label = ttk.Label(
            right_frame,
            textvariable=self.title_var,
            wraplength=860,
            font=("TkDefaultFont", 11, "bold"),
            justify="left",
        )
        title_label.grid(row=0, column=0, sticky="w")

        self.image_label = ttk.Label(right_frame, anchor="center")
        self.image_label.grid(row=1, column=0, sticky="nsew", pady=(8, 8))

        self.meta_text = tk.Text(right_frame, height=10, wrap="word")
        self.meta_text.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        self.meta_text.configure(state="disabled")

        self.article_text = tk.Text(right_frame, wrap="word")
        self.article_text.grid(row=3, column=0, sticky="nsew")
        self.article_text.configure(state="disabled")

    def _fill_list(self):
        for idx, record in enumerate(self.records, start=1):
            title = str(record.get("title", "")).strip() or "(no title)"
            self.listbox.insert("end", f"{idx:04d} | {title[:120]}")

    def _current_index(self):
        selected = self.listbox.curselection()
        if not selected:
            return None
        return selected[0]

    def select_prev(self):
        idx = self._current_index()
        if idx is None:
            return
        if idx > 0:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx - 1)
            self.listbox.see(idx - 1)
            self.on_select(None)

    def select_next(self):
        idx = self._current_index()
        if idx is None:
            return
        if idx < len(self.records) - 1:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx + 1)
            self.listbox.see(idx + 1)
            self.on_select(None)

    def _set_text(self, widget: tk.Text, value: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _meta_block(self, record: dict):
        parts = []
        for key in DISPLAY_FIELDS:
            value = record.get(key)
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            parts.append(f"{key}: {value}")
        b64_len = len(record.get("header_photo_base64") or "")
        parts.append(f"header_photo_base64_len: {b64_len}")
        return "\n".join(parts)

    def _image_from_bytes(self, content: bytes, max_size=(860, 360)):
        image = Image.open(io.BytesIO(content))
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    def _load_image(self, record: dict):
        source_url = str(record.get("source_url", ""))
        if source_url in self.image_cache:
            return self.image_cache[source_url]

        content = None
        b64 = record.get("header_photo_base64")
        if b64:
            try:
                content = base64.b64decode(b64)
            except Exception:
                content = None

        if content is None:
            photo_url = record.get("header_photo_url")
            if photo_url:
                try:
                    req = urllib.request.Request(
                        str(photo_url),
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        content = response.read(6_000_000)
                except Exception:
                    content = None

        if not content:
            self.image_cache[source_url] = None
            return None

        try:
            image = self._image_from_bytes(content)
        except Exception:
            image = None
        self.image_cache[source_url] = image
        return image

    def on_select(self, _event):
        idx = self._current_index()
        if idx is None:
            return
        record = self.records[idx]

        self.title_var.set(str(record.get("title", "")))
        self._set_text(self.meta_text, self._meta_block(record))
        self._set_text(self.article_text, str(record.get("article_text", "")))

        image = self._load_image(record)
        if image is None:
            self.image_label.configure(image="", text="No image")
            self.photo_ref = None
        else:
            self.image_label.configure(image=image, text="")
            self.photo_ref = image


def main():
    args = parse_args()
    data_file = Path(args.file)
    if not data_file.is_absolute():
        data_file = Path.cwd() / data_file
    if not data_file.exists():
        raise SystemExit(f"File not found: {data_file}")

    records = list(iter_jsonl(data_file))
    if not records:
        raise SystemExit("No readable JSON records found in file.")

    root = tk.Tk()
    app = DataViewerApp(root, records)
    # Keep reference to avoid garbage collection in some Tk implementations.
    root.app = app
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        messagebox.showerror("Viewer error", str(exc))
        raise
