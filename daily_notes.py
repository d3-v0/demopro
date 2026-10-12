#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily Notes - local personal notes app using Tkinter + SQLite."""

import json
import re
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Daily Notes"
DB_PATH = Path.home() / ".daily_notes.sqlite3"

CATEGORIES = [
    "Tất cả", "Cá nhân", "Công việc", "Ý tưởng", "Mua sắm",
    "Kế hoạch", "Học tập", "Quan trọng", "Khác"
]


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def pretty_time(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except Exception:
        return value or ""


def word_count(text):
    return len(re.findall(r"\S+", text or ""))


class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Cá nhân',
                tags TEXT NOT NULL DEFAULT '',
                pinned INTEGER NOT NULL DEFAULT 0,
                favorite INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                checklist INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category);
        """)
        self.conn.commit()

    def create(self, title, content, category, tags, checklist=False):
        t = now_text()
        cur = self.conn.execute("""
            INSERT INTO notes
            (title, content, category, tags, checklist, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, content, category, tags, int(checklist), t, t))
        self.conn.commit()
        return cur.lastrowid

    def get(self, note_id):
        return self.conn.execute(
            "SELECT * FROM notes WHERE id=?", (note_id,)
        ).fetchone()

    def update(self, note_id, title, content, category, tags,
               pinned, favorite, archived, checklist):
        self.conn.execute("""
            UPDATE notes SET
            title=?, content=?, category=?, tags=?,
            pinned=?, favorite=?, archived=?, checklist=?, updated_at=?
            WHERE id=?
        """, (
            title, content, category, tags, int(pinned), int(favorite),
            int(archived), int(checklist), now_text(), note_id
        ))
        self.conn.commit()

    def delete(self, note_id):
        self.conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def list(self, search="", category="Tất cả", include_archived=False):
        clauses, params = [], []
        if not include_archived:
            clauses.append("archived=0")
        if category != "Tất cả":
            clauses.append("category=?")
            params.append(category)
        if search.strip():
            p = f"%{search.strip()}%"
            clauses.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
            params.extend([p, p, p])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self.conn.execute(
            f"SELECT * FROM notes{where} ORDER BY pinned DESC, updated_at DESC",
            params
        ).fetchall()

    def all(self):
        return self.conn.execute(
            "SELECT * FROM notes ORDER BY updated_at DESC"
        ).fetchall()

    def close(self):
        self.conn.close()


class DailyNotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Daily Notes")
        self.root.geometry("1200x760")
        self.root.minsize(900, 600)

        self.db = Database(DB_PATH)
        self.current_id = None
        self.loading = False
        self.dirty = False
        self.search_job = None
        self.theme = "light"

        self.colors = {
            "light": {
                "bg": "#f3f5f7", "panel": "#ffffff", "text": "#20242a",
                "muted": "#6b7280", "editor": "#ffffff",
                "selected": "#dbeafe", "accent": "#2563eb"
            },
            "dark": {
                "bg": "#171a21", "panel": "#20242d", "text": "#f1f5f9",
                "muted": "#a5adba", "editor": "#1d222b",
                "selected": "#2b4165", "accent": "#60a5fa"
            }
        }

        self.setup_style()
        self.build_ui()
        self.bind_shortcuts()
        self.refresh_notes()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.new_note()

    def setup_style(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.apply_style()

    def apply_style(self):
        c = self.colors[self.theme]
        self.root.configure(bg=c["bg"])
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("Panel.TFrame", background=c["panel"])
        self.style.configure("TLabel", background=c["bg"], foreground=c["text"])
        self.style.configure("Panel.TLabel", background=c["panel"], foreground=c["text"])
        self.style.configure("Title.TLabel", background=c["panel"],
                             foreground=c["text"], font=("TkDefaultFont", 16, "bold"))
        self.style.configure("Muted.TLabel", background=c["panel"], foreground=c["muted"])
        self.style.configure("TButton", padding=(9, 6))
        self.style.configure("Accent.TButton", padding=(11, 7),
                             font=("TkDefaultFont", 10, "bold"))
        self.style.configure("Treeview", background=c["panel"],
                             fieldbackground=c["panel"], foreground=c["text"],
                             rowheight=34)
        self.style.map("Treeview",
                       background=[("selected", c["selected"])],
                       foreground=[("selected", c["text"])])
        if hasattr(self, "editor"):
            self.editor.configure(bg=c["editor"], fg=c["text"],
                                  insertbackground=c["text"],
                                  selectbackground=c["accent"])

    def build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=(10, 5))
        ttk.Label(top, text="📝 Daily Notes", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Ghi chú cá nhân • lưu trên máy",
                  style="Muted.TLabel").pack(side="left", padx=12)

        ttk.Button(top, text="🌙 Giao diện", command=self.toggle_theme).pack(side="right", padx=3)
        ttk.Button(top, text="📦 Xuất tất cả", command=self.export_all).pack(side="right", padx=3)
        ttk.Button(top, text="📄 Xuất ghi chú", command=self.export_current).pack(side="right", padx=3)

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        left = ttk.Frame(main, style="Panel.TFrame", width=350)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        bar = ttk.Frame(left, style="Panel.TFrame")
        bar.pack(fill="x", padx=10, pady=10)
        ttk.Button(bar, text="+ Ghi chú mới", style="Accent.TButton",
                   command=self.new_note).pack(side="left")
        ttk.Button(bar, text="🗑", width=3, command=self.delete_current).pack(side="right")

        search = ttk.Frame(left, style="Panel.TFrame")
        search.pack(fill="x", padx=10, pady=(0, 7))
        ttk.Label(search, text="🔎", style="Panel.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        e = ttk.Entry(search, textvariable=self.search_var)
        e.pack(side="left", fill="x", expand=True, padx=(5, 0))
        e.bind("<KeyRelease>", self.on_search)
        self.search_entry = e

        filt = ttk.Frame(left, style="Panel.TFrame")
        filt.pack(fill="x", padx=10, pady=(0, 8))
        self.category_filter = tk.StringVar(value="Tất cả")
        box = ttk.Combobox(filt, textvariable=self.category_filter,
                           values=CATEGORIES, state="readonly")
        box.pack(side="left", fill="x", expand=True)
        box.bind("<<ComboboxSelected>>", lambda _: self.refresh_notes())
        ttk.Button(filt, text="↻", width=3, command=self.refresh_notes).pack(
            side="left", padx=(5, 0)
        )

        list_frame = ttk.Frame(left, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(
            list_frame, columns=("title", "category", "updated"),
            show="headings", selectmode="browse"
        )
        self.tree.heading("title", text="Ghi chú")
        self.tree.heading("category", text="Loại")
        self.tree.heading("updated", text="Cập nhật")
        self.tree.column("title", width=160)
        self.tree.column("category", width=80, anchor="center")
        self.tree.column("updated", width=95, anchor="center")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.select_note)

        self.count_label = ttk.Label(left, text="0 ghi chú", style="Muted.TLabel")
        self.count_label.pack(anchor="w", padx=12, pady=8)

        right = ttk.Frame(main, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)

        meta = ttk.Frame(right, style="Panel.TFrame")
        meta.pack(fill="x", padx=15, pady=(13, 7))
        self.title_var = tk.StringVar()
        title = ttk.Entry(meta, textvariable=self.title_var,
                          font=("TkDefaultFont", 15, "bold"))
        title.pack(side="left", fill="x", expand=True)
        title.bind("<KeyRelease>", self.mark_dirty)
        self.category_var = tk.StringVar(value="Cá nhân")
        ttk.Combobox(meta, textvariable=self.category_var,
                     values=CATEGORIES[1:], state="readonly", width=14).pack(
            side="left", padx=(8, 0)
        )

        opts = ttk.Frame(right, style="Panel.TFrame")
        opts.pack(fill="x", padx=15, pady=(0, 7))
        self.pinned = tk.BooleanVar()
        self.favorite = tk.BooleanVar()
        self.archived = tk.BooleanVar()
        self.checklist = tk.BooleanVar()

        for text, var in [
            ("📌 Ghim", self.pinned),
            ("★ Yêu thích", self.favorite),
            ("☐ Checklist", self.checklist),
            ("Lưu trữ", self.archived),
        ]:
            ttk.Checkbutton(opts, text=text, variable=var,
                            command=self.mark_dirty).pack(side="left", padx=(0, 12))

        self.status = ttk.Label(opts, text="", style="Muted.TLabel")
        self.status.pack(side="right", padx=10)
        ttk.Button(opts, text="Lưu", style="Accent.TButton",
                   command=self.save_current).pack(side="right")

        tags = ttk.Frame(right, style="Panel.TFrame")
        tags.pack(fill="x", padx=15, pady=(0, 7))
        ttk.Label(tags, text="Tags:", style="Panel.TLabel").pack(side="left")
        self.tags_var = tk.StringVar()
        ttk.Entry(tags, textvariable=self.tags_var).pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

        editor_frame = ttk.Frame(right, style="Panel.TFrame")
        editor_frame.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        self.editor = tk.Text(editor_frame, wrap="word", undo=True,
                              font=("TkDefaultFont", 11), relief="flat",
                              padx=12, pady=12)
        es = ttk.Scrollbar(editor_frame, orient="vertical",
                           command=self.editor.yview)
        self.editor.configure(yscrollcommand=es.set)
        self.editor.pack(side="left", fill="both", expand=True)
        es.pack(side="right", fill="y")
        self.editor.bind("<<Modified>>", self.editor_modified)

        bottom = ttk.Frame(right, style="Panel.TFrame")
        bottom.pack(fill="x", padx=15, pady=(0, 12))
        self.stats = ttk.Label(bottom, text="0 từ • 0 ký tự", style="Muted.TLabel")
        self.stats.pack(side="left")
        self.date_label = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.date_label.pack(side="right")

        self.apply_style()

    def bind_shortcuts(self):
        self.root.bind_all("<Control-n>", lambda _: self.new_note())
        self.root.bind_all("<Control-s>", lambda _: self.save_current())
        self.root.bind_all("<Control-f>", lambda _: self.focus_search())
        self.root.bind_all("<Control-e>", lambda _: self.export_current())
        self.root.bind_all("<Control-Shift-D>", lambda _: self.duplicate_current())

    def focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")

    def new_note(self):
        if self.dirty and not self.confirm_discard():
            return
        self.loading = True
        self.current_id = None
        self.title_var.set("Ghi chú mới")
        self.category_var.set("Cá nhân")
        self.tags_var.set("")
        self.pinned.set(False)
        self.favorite.set(False)
        self.archived.set(False)
        self.checklist.set(False)
        self.editor.delete("1.0", "end")
        self.editor.edit_modified(False)
        self.loading = False
        self.dirty = False
        self.status.config(text="Ghi chú mới")
        self.date_label.config(text="")
        self.update_stats()
        self.tree.selection_remove(self.tree.selection())
        self.editor.focus_set()

    def save_current(self):
        title = self.title_var.get().strip()
        content = self.editor.get("1.0", "end-1c")
        if not title and not content.strip():
            messagebox.showinfo("Ghi chú trống", "Hãy nhập tiêu đề hoặc nội dung.")
            return
        if not title:
            title = next((x.strip() for x in content.splitlines() if x.strip()),
                         "Ghi chú không tên")
            self.title_var.set(title)

        values = (
            title, content, self.category_var.get(), self.tags_var.get().strip(),
            self.pinned.get(), self.favorite.get(), self.archived.get(),
            self.checklist.get()
        )
        if self.current_id is None:
            self.current_id = self.db.create(
                values[0], values[1], values[2], values[3], values[7]
            )
        self.db.update(self.current_id, *values)

        self.dirty = False
        self.status.config(text="✓ Đã lưu")
        self.editor.edit_modified(False)
        self.refresh_notes(select_id=self.current_id)

    def load_note(self, note_id):
        row = self.db.get(note_id)
        if not row:
            return
        self.loading = True
        self.current_id = row["id"]
        self.title_var.set(row["title"])
        self.category_var.set(row["category"])
        self.tags_var.set(row["tags"])
        self.pinned.set(bool(row["pinned"]))
        self.favorite.set(bool(row["favorite"]))
        self.archived.set(bool(row["archived"]))
        self.checklist.set(bool(row["checklist"]))
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", row["content"])
        self.editor.edit_modified(False)
        self.loading = False
        self.dirty = False
        self.status.config(text="Đã tải")
        self.date_label.config(
            text=f"Tạo: {pretty_time(row['created_at'])} • "
                 f"Sửa: {pretty_time(row['updated_at'])}"
        )
        self.update_stats()

    def delete_current(self):
        if self.current_id is None:
            return
        row = self.db.get(self.current_id)
        if not row:
            return
        if not messagebox.askyesno(
            "Xóa ghi chú",
            f"Xóa ghi chú:\n\n{row['title'] or 'Không có tiêu đề'}\n\nKhông thể hoàn tác."
        ):
            return
        self.db.delete(self.current_id)
        self.current_id = None
        self.dirty = False
        self.refresh_notes()
        self.new_note()

    def duplicate_current(self):
        if self.current_id is None:
            return
        row = self.db.get(self.current_id)
        if not row:
            return
        new_id = self.db.create(
            f"{row['title']} - bản sao", row["content"], row["category"],
            row["tags"], row["checklist"]
        )
        self.db.update(
            new_id, f"{row['title']} - bản sao", row["content"],
            row["category"], row["tags"], row["pinned"],
            row["favorite"], row["archived"], row["checklist"]
        )
        self.refresh_notes(select_id=new_id)

    def refresh_notes(self, select_id=None):
        rows = self.db.list(self.search_var.get(), self.category_filter.get())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            title = row["title"] or "Không có tiêu đề"
            if row["pinned"]:
                title = "📌 " + title
            if row["favorite"]:
                title = "★ " + title
            self.tree.insert("", "end", iid=str(row["id"]),
                             values=(title[:38], row["category"],
                                     pretty_time(row["updated_at"])))
        self.count_label.config(text=f"{len(rows)} ghi chú")
        if select_id is not None and str(select_id) in self.tree.get_children():
            self.tree.selection_set(str(select_id))
            self.tree.see(str(select_id))
            self.load_note(select_id)

    def select_note(self, _=None):
        selected = self.tree.selection()
        if not selected:
            return
        note_id = int(selected[0])
        if note_id == self.current_id and not self.dirty:
            return
        if self.dirty and not self.confirm_discard():
            if self.current_id and str(self.current_id) in self.tree.get_children():
                self.tree.selection_set(str(self.current_id))
            return
        self.load_note(note_id)

    def on_search(self, _=None):
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.search_job = self.root.after(120, self.refresh_notes)

    def mark_dirty(self, _=None):
        if self.loading:
            return
        self.dirty = True
        self.status.config(text="● Chưa lưu")
        self.update_stats()

    def editor_modified(self, _=None):
        if self.editor.edit_modified():
            if not self.loading:
                self.mark_dirty()
            self.editor.edit_modified(False)
        self.update_stats()

    def confirm_discard(self):
        return messagebox.askyesno(
            "Thay đổi chưa lưu",
            "Ghi chú hiện tại có thay đổi chưa lưu.\n\n"
            "Bỏ thay đổi và chuyển sang ghi chú khác?"
        )

    def update_stats(self):
        text = self.editor.get("1.0", "end-1c")
        self.stats.config(text=f"{word_count(text):,} từ • {len(text):,} ký tự")

    def export_current(self):
        if self.current_id is None:
            messagebox.showinfo("Chưa có ghi chú", "Hãy lưu ghi chú trước khi xuất.")
            return
        title = self.title_var.get().strip() or "note"
        safe = re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "note"
        path = filedialog.asksaveasfilename(
            title="Xuất ghi chú", initialfile=safe + ".md",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")]
        )
        if not path:
            return
        content = self.editor.get("1.0", "end-1c")
        if Path(path).suffix.lower() == ".txt":
            text = f"{title}\n{'=' * max(3, len(title))}\n\n{content}\n"
        else:
            text = (f"# {title}\n\n{content}\n\n---\n"
                    f"**Danh mục:** {self.category_var.get()}\n\n"
                    f"**Tags:** {self.tags_var.get().strip()}\n")
        try:
            Path(path).write_text(text, encoding="utf-8")
            self.status.config(text="✓ Đã xuất")
        except OSError as exc:
            messagebox.showerror("Lỗi xuất file", str(exc))

    def export_all(self):
        rows = self.db.all()
        if not rows:
            messagebox.showinfo("Chưa có dữ liệu", "Chưa có ghi chú để xuất.")
            return
        path = filedialog.asksaveasfilename(
            title="Sao lưu toàn bộ ghi chú",
            initialfile="daily_notes_backup.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps([dict(r) for r in rows],
                           ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            messagebox.showinfo("Thành công", f"Đã xuất {len(rows)} ghi chú.")
        except OSError as exc:
            messagebox.showerror("Lỗi xuất file", str(exc))

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.apply_style()

    def close(self):
        if self.dirty:
            ans = messagebox.askyesnocancel(
                "Thoát", "Ghi chú hiện tại chưa lưu. Lưu trước khi thoát?"
            )
            if ans is None:
                return
            if ans:
                self.save_current()
        self.db.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    DailyNotesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
