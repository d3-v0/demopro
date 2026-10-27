#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Home Inventory - Quản lý đồ đạc trong nhà
Chỉ cần Python 3 + Tkinter. Dữ liệu lưu cục bộ bằng SQLite.
"""
import csv
import json
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Home Inventory"
DB_PATH = Path.home() / ".home_inventory.sqlite3"

CATEGORIES = ["Điện tử","Đồ bếp","Đồ gia dụng","Nội thất","Quần áo",
              "Sách & tài liệu","Công cụ","Đồ cá nhân","Đồ trẻ em","Khác"]
LOCATIONS = ["Phòng khách","Phòng ngủ","Nhà bếp","Phòng tắm","Kho",
             "Ban công","Phòng làm việc","Khác"]
CONDITIONS = ["Mới","Tốt","Đã sử dụng","Cũ","Hỏng"]


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def money(value):
    try:
        return f"{float(value or 0):,.0f} đ"
    except (TypeError, ValueError):
        return "0 đ"


def safe_float(value):
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    return float(text)


class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Khác',
            location TEXT NOT NULL DEFAULT 'Khác',
            quantity REAL NOT NULL DEFAULT 1,
            unit TEXT NOT NULL DEFAULT 'cái',
            purchase_price REAL NOT NULL DEFAULT 0,
            current_value REAL NOT NULL DEFAULT 0,
            purchase_date TEXT DEFAULT '',
            warranty_until TEXT DEFAULT '',
            condition TEXT NOT NULL DEFAULT 'Tốt',
            serial_number TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
        CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
        CREATE INDEX IF NOT EXISTS idx_items_location ON items(location);
        """)
        self.conn.commit()

    def add(self, d):
        stamp = now_text()
        cur = self.conn.execute("""
        INSERT INTO items
        (name,category,location,quantity,unit,purchase_price,current_value,
         purchase_date,warranty_until,condition,serial_number,notes,image_path,
         created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (d["name"],d["category"],d["location"],d["quantity"],d["unit"],
              d["purchase_price"],d["current_value"],d["purchase_date"],
              d["warranty_until"],d["condition"],d["serial_number"],
              d["notes"],d["image_path"],stamp,stamp))
        self.conn.commit()
        return cur.lastrowid

    def update(self, item_id, d):
        self.conn.execute("""
        UPDATE items SET name=?,category=?,location=?,quantity=?,unit=?,
        purchase_price=?,current_value=?,purchase_date=?,warranty_until=?,
        condition=?,serial_number=?,notes=?,image_path=?,updated_at=?
        WHERE id=?
        """, (d["name"],d["category"],d["location"],d["quantity"],d["unit"],
              d["purchase_price"],d["current_value"],d["purchase_date"],
              d["warranty_until"],d["condition"],d["serial_number"],
              d["notes"],d["image_path"],now_text(),item_id))
        self.conn.commit()

    def delete(self, item_id):
        self.conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.conn.commit()

    def get(self, item_id):
        return self.conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()

    def search(self, text="", category="Tất cả", location="Tất cả",
               condition="Tất cả", warranty="Tất cả"):
        sql = "SELECT * FROM items WHERE 1=1"
        args = []
        if text.strip():
            like = "%" + text.strip() + "%"
            sql += """ AND (name LIKE ? OR category LIKE ? OR location LIKE ?
                       OR serial_number LIKE ? OR notes LIKE ?)"""
            args += [like] * 5
        if category != "Tất cả":
            sql += " AND category=?"; args.append(category)
        if location != "Tất cả":
            sql += " AND location=?"; args.append(location)
        if condition != "Tất cả":
            sql += " AND condition=?"; args.append(condition)
        if warranty == "Có bảo hành":
            sql += " AND warranty_until <> ''"
        elif warranty == "Không bảo hành":
            sql += " AND (warranty_until='' OR warranty_until IS NULL)"
        sql += " ORDER BY name COLLATE NOCASE, id DESC"
        return self.conn.execute(sql, args).fetchall()

    def all_items(self):
        return self.conn.execute(
            "SELECT * FROM items ORDER BY name COLLATE NOCASE"
        ).fetchall()

    def stats(self):
        row = self.conn.execute("""
        SELECT COUNT(*) item_count, COALESCE(SUM(quantity),0) quantity_total,
        COALESCE(SUM(purchase_price*quantity),0) purchase_total,
        COALESCE(SUM(current_value*quantity),0) current_total
        FROM items
        """).fetchone()
        categories = self.conn.execute(
            "SELECT category,COUNT(*) count FROM items GROUP BY category"
        ).fetchall()
        locations = self.conn.execute(
            "SELECT location,COUNT(*) count FROM items GROUP BY location"
        ).fetchall()
        return row, categories, locations

    def close(self):
        self.conn.close()


class ItemDialog(tk.Toplevel):
    def __init__(self, parent, item=None):
        super().__init__(parent)
        self.result = None
        self.title("Thêm đồ dùng" if item is None else "Chỉnh sửa đồ dùng")
        self.geometry("620x700")
        self.minsize(560, 620)
        self.transient(parent)
        self.grab_set()

        self.v = {
            "name": tk.StringVar(value=item["name"] if item else ""),
            "category": tk.StringVar(value=item["category"] if item else "Khác"),
            "location": tk.StringVar(value=item["location"] if item else "Khác"),
            "quantity": tk.StringVar(value=str(item["quantity"]) if item else "1"),
            "unit": tk.StringVar(value=item["unit"] if item else "cái"),
            "purchase_price": tk.StringVar(value=str(item["purchase_price"]) if item else "0"),
            "current_value": tk.StringVar(value=str(item["current_value"]) if item else "0"),
            "purchase_date": tk.StringVar(value=item["purchase_date"] if item else ""),
            "warranty_until": tk.StringVar(value=item["warranty_until"] if item else ""),
            "condition": tk.StringVar(value=item["condition"] if item else "Tốt"),
            "serial_number": tk.StringVar(value=item["serial_number"] if item else ""),
            "image_path": tk.StringVar(value=item["image_path"] if item else "")
        }
        self.build(item)

    def build(self, item):
        box = ttk.Frame(self, padding=18)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Thông tin đồ dùng",
                  font=("TkDefaultFont",16,"bold")).pack(anchor="w", pady=(0,12))
        form = ttk.Frame(box)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)
        r = 0

        def entry(label, key):
            nonlocal r
            ttk.Label(form,text=label).grid(row=r,column=0,sticky="w",padx=(0,10),pady=6)
            e = ttk.Entry(form,textvariable=self.v[key])
            e.grid(row=r,column=1,sticky="ew",pady=6)
            r += 1
            return e

        name_entry = entry("Tên đồ dùng *","name")

        for label,key,values in [
            ("Danh mục","category",CATEGORIES),
            ("Vị trí","location",LOCATIONS),
        ]:
            ttk.Label(form,text=label).grid(row=r,column=0,sticky="w",padx=(0,10),pady=6)
            ttk.Combobox(form,textvariable=self.v[key],values=values,
                         state="readonly").grid(row=r,column=1,sticky="ew",pady=6)
            r += 1

        ttk.Label(form,text="Số lượng / đơn vị").grid(row=r,column=0,sticky="w",padx=(0,10),pady=6)
        q = ttk.Frame(form); q.grid(row=r,column=1,sticky="ew",pady=6)
        q.columnconfigure(0,weight=1)
        ttk.Entry(q,textvariable=self.v["quantity"]).grid(row=0,column=0,sticky="ew")
        ttk.Entry(q,textvariable=self.v["unit"],width=12).grid(row=0,column=1,padx=(8,0))
        r += 1

        entry("Giá mua / đơn vị","purchase_price")
        entry("Giá trị hiện tại / đơn vị","current_value")
        entry("Ngày mua","purchase_date")
        entry("Bảo hành đến","warranty_until")

        ttk.Label(form,text="Tình trạng").grid(row=r,column=0,sticky="w",padx=(0,10),pady=6)
        ttk.Combobox(form,textvariable=self.v["condition"],values=CONDITIONS,
                     state="readonly").grid(row=r,column=1,sticky="ew",pady=6)
        r += 1
        entry("Serial / mã sản phẩm","serial_number")

        ttk.Label(form,text="Ảnh / file tham chiếu").grid(row=r,column=0,sticky="w",padx=(0,10),pady=6)
        img = ttk.Frame(form); img.grid(row=r,column=1,sticky="ew",pady=6)
        img.columnconfigure(0,weight=1)
        ttk.Entry(img,textvariable=self.v["image_path"]).grid(row=0,column=0,sticky="ew")
        ttk.Button(img,text="Chọn...",command=self.browse).grid(row=0,column=1,padx=(8,0))
        r += 1

        ttk.Label(form,text="Ghi chú").grid(row=r,column=0,sticky="nw",padx=(0,10),pady=6)
        self.notes = tk.Text(form,height=6,wrap="word")
        self.notes.grid(row=r,column=1,sticky="nsew",pady=6)
        form.rowconfigure(r,weight=1)
        if item:
            self.notes.insert("1.0",item["notes"] or "")

        buttons = ttk.Frame(box); buttons.pack(fill="x",pady=(14,0))
        ttk.Button(buttons,text="Hủy",command=self.cancel).pack(side="right")
        ttk.Button(buttons,text="Lưu",command=self.save).pack(side="right",padx=(0,8))
        name_entry.focus_set()
        self.protocol("WM_DELETE_WINDOW",self.cancel)

    def browse(self):
        p = filedialog.askopenfilename(parent=self,title="Chọn ảnh hoặc file")
        if p: self.v["image_path"].set(p)

    def save(self):
        if not self.v["name"].get().strip():
            messagebox.showwarning("Thiếu thông tin","Vui lòng nhập tên đồ dùng.",parent=self); return
        try:
            quantity=safe_float(self.v["quantity"].get())
            purchase=safe_float(self.v["purchase_price"].get())
            current=safe_float(self.v["current_value"].get())
            if quantity<=0: raise ValueError("Số lượng phải lớn hơn 0.")
            if purchase<0 or current<0: raise ValueError("Giá trị không được âm.")
        except ValueError as e:
            messagebox.showwarning("Dữ liệu không hợp lệ",str(e),parent=self); return
        self.result={
            "name":self.v["name"].get().strip(),"category":self.v["category"].get(),
            "location":self.v["location"].get(),"quantity":quantity,
            "unit":self.v["unit"].get().strip() or "cái","purchase_price":purchase,
            "current_value":current,"purchase_date":self.v["purchase_date"].get().strip(),
            "warranty_until":self.v["warranty_until"].get().strip(),
            "condition":self.v["condition"].get(),
            "serial_number":self.v["serial_number"].get().strip(),
            "notes":self.notes.get("1.0","end-1c").strip(),
            "image_path":self.v["image_path"].get().strip()
        }
        self.destroy()

    def cancel(self):
        self.result=None
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🏠 Home Inventory")
        self.geometry("1260x780")
        self.minsize(1050,650)
        self.db=Database()
        self.selected_id=None
        self.search_var=tk.StringVar()
        self.category_var=tk.StringVar(value="Tất cả")
        self.location_var=tk.StringVar(value="Tất cả")
        self.condition_var=tk.StringVar(value="Tất cả")
        self.warranty_var=tk.StringVar(value="Tất cả")
        self.build()
        self.refresh()
        self.protocol("WM_DELETE_WINDOW",self.close)
        self.bind("<Control-n>",lambda e:self.add_item())
        self.bind("<Control-e>",lambda e:self.edit_item())
        self.bind("<Delete>",lambda e:self.delete_item())
        self.bind("<Control-f>",lambda e:self.focus_search())
        self.bind("<Control-s>",lambda e:self.export_json())

    def build(self):
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Title.TLabel",font=("TkDefaultFont",20,"bold"))
        style.configure("Treeview",rowheight=30)
        style.configure("Treeview.Heading",font=("TkDefaultFont",10,"bold"))
        root=ttk.Frame(self,padding=14); root.pack(fill="both",expand=True)

        head=ttk.Frame(root); head.pack(fill="x",pady=(0,12))
        ttk.Label(head,text="🏠 Home Inventory",style="Title.TLabel").pack(side="left")
        ttk.Label(head,text="Quản lý đồ đạc, giá trị, vị trí và bảo hành").pack(side="left",padx=14,pady=7)
        ttk.Button(head,text="Xuất JSON",command=self.export_json).pack(side="right",padx=4)
        ttk.Button(head,text="Xuất CSV",command=self.export_csv).pack(side="right",padx=4)

        stats=ttk.Frame(root); stats.pack(fill="x",pady=(0,12))
        self.stat={}
        for key,label in [("items","Số loại đồ dùng"),("quantity","Tổng số lượng"),
                          ("purchase","Tổng tiền mua"),("current","Giá trị hiện tại")]:
            card=ttk.Frame(stats,relief="solid",borderwidth=1,padding=12)
            card.pack(side="left",fill="x",expand=True,padx=(0,8))
            ttk.Label(card,text=label).pack(anchor="w")
            self.stat[key]=ttk.Label(card,text="0",font=("TkDefaultFont",16,"bold"))
            self.stat[key].pack(anchor="w",pady=(5,0))

        filt=ttk.LabelFrame(root,text="Tìm kiếm & bộ lọc",padding=10); filt.pack(fill="x",pady=(0,10))
        ttk.Label(filt,text="Tìm:").grid(row=0,column=0,padx=5)
        search=ttk.Entry(filt,textvariable=self.search_var,width=28)
        search.grid(row=0,column=1,sticky="ew",padx=5); search.bind("<KeyRelease>",lambda e:self.refresh())
        self.add_combo(filt,2,"Danh mục:",self.category_var,["Tất cả"]+CATEGORIES)
        self.add_combo(filt,4,"Vị trí:",self.location_var,["Tất cả"]+LOCATIONS)
        self.add_combo(filt,6,"Tình trạng:",self.condition_var,["Tất cả"]+CONDITIONS)
        self.add_combo(filt,8,"Bảo hành:",self.warranty_var,["Tất cả","Có bảo hành","Không bảo hành"])
        ttk.Button(filt,text="Xóa lọc",command=self.clear_filters).grid(row=0,column=10,padx=8)
        filt.columnconfigure(1,weight=1)

        actions=ttk.Frame(root); actions.pack(fill="x",pady=(0,8))
        ttk.Button(actions,text="＋ Thêm đồ dùng",command=self.add_item).pack(side="left")
        ttk.Button(actions,text="Chỉnh sửa",command=self.edit_item).pack(side="left",padx=6)
        ttk.Button(actions,text="Xóa",command=self.delete_item).pack(side="left")
        ttk.Button(actions,text="Làm mới",command=self.refresh).pack(side="left",padx=6)
        self.status=ttk.Label(actions,text=""); self.status.pack(side="right")

        tf=ttk.Frame(root); tf.pack(fill="both",expand=True)
        cols=("name","category","location","quantity","purchase","current","condition","warranty")
        self.tree=ttk.Treeview(tf,columns=cols,show="headings",selectmode="browse")
        heads={"name":"Đồ dùng","category":"Danh mục","location":"Vị trí","quantity":"SL",
               "purchase":"Giá mua","current":"Giá trị hiện tại","condition":"Tình trạng","warranty":"Bảo hành đến"}
        widths={"name":220,"category":130,"location":130,"quantity":65,"purchase":120,
                "current":130,"condition":110,"warranty":120}
        for c in cols:
            self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],
                anchor="w" if c=="name" else "center")
        vs=ttk.Scrollbar(tf,orient="vertical",command=self.tree.yview)
        hs=ttk.Scrollbar(tf,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        self.tree.grid(row=0,column=0,sticky="nsew"); vs.grid(row=0,column=1,sticky="ns")
        hs.grid(row=1,column=0,sticky="ew"); tf.rowconfigure(0,weight=1); tf.columnconfigure(0,weight=1)
        self.tree.bind("<<TreeviewSelect>>",self.on_select)
        self.tree.bind("<Double-1>",lambda e:self.edit_item())

        detail=ttk.LabelFrame(root,text="Chi tiết",padding=10); detail.pack(fill="x",pady=(10,0))
        self.detail=ttk.Label(detail,text="Chọn một đồ dùng để xem chi tiết.",justify="left",wraplength=1100)
        self.detail.pack(fill="x")

    def add_combo(self,parent,col,label,var,values):
        ttk.Label(parent,text=label).grid(row=0,column=col,padx=5)
        cb=ttk.Combobox(parent,textvariable=var,values=values,state="readonly",width=15)
        cb.grid(row=0,column=col+1,padx=5); cb.bind("<<ComboboxSelected>>",lambda e:self.refresh())

    def focus_search(self):
        # The first Entry is the search box.
        for widget in self._walk(self):
            if isinstance(widget,(tk.Entry,ttk.Entry)) and widget.cget("textvariable")==str(self.search_var):
                widget.focus_set(); widget.selection_range(0,"end"); return

    def _walk(self,parent):
        for child in parent.winfo_children():
            yield child
            yield from self._walk(child)

    def clear_filters(self):
        self.search_var.set(""); self.category_var.set("Tất cả")
        self.location_var.set("Tất cả"); self.condition_var.set("Tất cả")
        self.warranty_var.set("Tất cả"); self.refresh()

    def refresh(self):
        rows=self.db.search(self.search_var.get(),self.category_var.get(),
                            self.location_var.get(),self.condition_var.get(),self.warranty_var.get())
        for iid in self.tree.get_children(): self.tree.delete(iid)
        for x in rows:
            self.tree.insert("", "end",iid=str(x["id"]),values=(
                x["name"],x["category"],x["location"],f'{x["quantity"]:g} {x["unit"]}',
                money(x["purchase_price"]*x["quantity"]),
                money(x["current_value"]*x["quantity"]),x["condition"],x["warranty_until"] or "—"))
        row,cats,locs=self.db.stats()
        self.stat["items"].configure(text=str(row["item_count"]))
        self.stat["quantity"].configure(text=f'{row["quantity_total"]:g}')
        self.stat["purchase"].configure(text=money(row["purchase_total"]))
        self.stat["current"].configure(text=money(row["current_total"]))
        self.status.configure(text=f"{len(rows)} mục đang hiển thị")
        if self.selected_id and self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))
        else:
            self.selected_id=None; self.detail.configure(text="Chọn một đồ dùng để xem chi tiết.")

    def on_select(self,event=None):
        sel=self.tree.selection()
        if not sel:return
        self.selected_id=int(sel[0]); x=self.db.get(self.selected_id)
        if not x:return
        self.detail.configure(text=(
            f"📦 {x['name']} • {x['quantity']:g} {x['unit']} • {x['category']} • {x['location']}\n"
            f"💰 Giá mua: {money(x['purchase_price'])}/đơn vị ({money(x['purchase_price']*x['quantity'])} tổng) • "
            f"Giá trị hiện tại: {money(x['current_value'])}/đơn vị ({money(x['current_value']*x['quantity'])} tổng)\n"
            f"🛠 Tình trạng: {x['condition']} • Ngày mua: {x['purchase_date'] or '—'} • "
            f"Bảo hành: {x['warranty_until'] or '—'} • Serial: {x['serial_number'] or '—'}\n"
            f"📝 Ghi chú: {x['notes'] or '—'}"
        ))

    def add_item(self):
        d=ItemDialog(self); self.wait_window(d)
        if d.result:self.db.add(d.result); self.refresh()

    def edit_item(self):
        if not self.selected_id:
            messagebox.showinfo("Chưa chọn","Hãy chọn một đồ dùng để chỉnh sửa."); return
        x=self.db.get(self.selected_id)
        if not x:return
        d=ItemDialog(self,x); self.wait_window(d)
        if d.result:self.db.update(self.selected_id,d.result); self.refresh()

    def delete_item(self):
        if not self.selected_id:
            messagebox.showinfo("Chưa chọn","Hãy chọn một đồ dùng để xóa."); return
        x=self.db.get(self.selected_id)
        if x and messagebox.askyesno("Xác nhận",f'Xóa "{x["name"]}" khỏi kho đồ dùng?'):
            self.db.delete(self.selected_id); self.selected_id=None; self.refresh()

    def export_json(self):
        p=filedialog.asksaveasfilename(parent=self,title="Xuất JSON",defaultextension=".json",
          filetypes=[("JSON","*.json")],initialfile=f"home_inventory_{datetime.now():%Y%m%d_%H%M%S}.json")
        if not p:return
        payload={"app":APP_NAME,"exported_at":now_text(),"items":[dict(x) for x in self.db.all_items()]}
        try:
            Path(p).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            messagebox.showinfo("Đã xuất",f"Đã lưu {len(payload['items'])} mục vào:\n{p}")
        except OSError as e: messagebox.showerror("Lỗi",str(e))

    def export_csv(self):
        p=filedialog.asksaveasfilename(parent=self,title="Xuất CSV",defaultextension=".csv",
          filetypes=[("CSV","*.csv")],initialfile=f"home_inventory_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if not p:return
        rows=self.db.all_items()
        fields=["id","name","category","location","quantity","unit","purchase_price","current_value",
                "purchase_date","warranty_until","condition","serial_number","notes","image_path","created_at","updated_at"]
        try:
            with open(p,"w",newline="",encoding="utf-8-sig") as f:
                w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
                for x in rows:w.writerow({k:x[k] for k in fields})
            messagebox.showinfo("Đã xuất",f"Đã lưu {len(rows)} mục vào:\n{p}")
        except OSError as e: messagebox.showerror("Lỗi",str(e))

    def close(self):
        self.db.close(); self.destroy()


if __name__=="__main__":
    App().mainloop()
