# student_records.py
"""
Complete student records UI with SQLite persistence and photo handling.

Features:
- Form with required fields (star appended).
- Save / Reset buttons.
- View Records in-place (Treeview) with vertical & horizontal scrollbars.
- Search by Student ID (preferred) and Name (optional).
- Update selects one row -> loads into form for editing -> Save updates the DB (Student ID locked during update).
- Delete supports multi-selection.
- Upload Photo required; images copied to data/photos/{student_id}{ext} and DB stores the path.
- DOB uses tkcalendar with DD/MM/YYYY.
- Tooltip (bright blue) appears when Student ID is locked.
- Cancel Update button centered below Save/Reset during update mode.
"""

import os
import shutil
import sqlite3
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import customtkinter as ctk
import pandas as pd
from PIL import Image, ImageTk
from tkcalendar import Calendar

# -------------------------- Config / DB dirs --------------------------
DATA_DIR = Path("data")
PHOTOS_DIR = DATA_DIR / "photos"
DB_PATH = DATA_DIR / "students.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------- DB helpers --------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH.as_posix())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        student_name TEXT,
        department TEXT,
        course TEXT,
        year TEXT,
        father_name TEXT,
        father_occupation TEXT,
        mother_name TEXT,
        mother_occupation TEXT,
        dob TEXT,
        gender TEXT,
        email TEXT,
        phone TEXT,
        guardian_phone TEXT,
        category TEXT,
        religion TEXT,
        residential_address TEXT,
        permanent_address TEXT,
        nationality TEXT,
        photo_path TEXT
    )
    """)
    conn.commit()
    conn.close()

# Initialize DB now
init_db()

# -------------------------- Tooltip helper (CTk, bright-blue) --------------------------
class ToolTip:
    """
    Minimal tooltip using CTkToplevel (CustomTkinter v5).
    Bright-blue background to match dashboard highlight.
    Automatically unbinds handlers on hide to avoid leftover callbacks.
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        # store binding ids so we can unbind later
        self._enter_id = widget.bind("<Enter>", self.show_tip, add="+")
        self._leave_id = widget.bind("<Leave>", self.hide_tip, add="+")
        self._motion_id = widget.bind("<Motion>", lambda e: None, add="+")  # keep motion if needed

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # compute position (slightly offset)
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tw = ctk.CTkToplevel(self.widget)
        tw.overrideredirect(True)
        # make sure tooltip above everything
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass
        tw.geometry(f"+{x}+{y}")
        # bright-blue bubble with white text
        label = ctk.CTkLabel(tw,
                             text=self.text,
                             fg_color="#1E90FF",
                             text_color="white",
                             corner_radius=8,
                             font=("Helvetica", 10, "bold"),
                             padx=8, pady=5)
        label.pack()
        self.tipwindow = tw

    def hide_tip(self, event=None):
        if self.tipwindow:
            try:
                self.tipwindow.destroy()
            except Exception:
                pass
            self.tipwindow = None
        # unbind events to avoid lingering callbacks
        try:
            if self._enter_id:
                self.widget.unbind("<Enter>", self._enter_id)
        except Exception:
            try:
                self.widget.unbind("<Enter>")
            except Exception:
                pass
        try:
            if self._leave_id:
                self.widget.unbind("<Leave>", self._leave_id)
        except Exception:
            try:
                self.widget.unbind("<Leave>")
            except Exception:
                pass

# -------------------------- Main UI Class --------------------------
class StudentRecordsFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#0E0E0E")
        self.parent = parent

        # state
        self.photo_path = None              # currently chosen photo (temporary until save)
        self.current_update_id = None       # student_id being edited (when updating)
        self.cancel_btn = None
        self.sid_tooltip = None

        # fields - order used in table/export
        self.fields = [
            "Student ID", "Student Name", "Department", "Course", "Year",
            "Father's Name", "Father's Occupation", "Mother's Name", "Mother's Occupation",
            "DOB", "Gender", "Email", "Phone", "Guardian's Phone",
            "Category", "Religion", "Residential Address", "Permanent Address", "Nationality"
        ]

        # required fields
        self.required_fields = {
            "Student ID", "Student Name", "Course", "Department", "Year",
            "Father's Name", "Mother's Name", "Father's Occupation",
            "DOB", "Gender", "Email", "Phone", "Residential Address", "Nationality", "Photo"
        }

        # layout: form and photo side-by-side
        self.form_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=12)
        self.form_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        self.photo_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=12)
        self.photo_frame.pack(side="right", fill="y", padx=20, pady=20)

        ctk.CTkLabel(self.form_frame, text="Student Information",
                     font=("Helvetica", 18, "bold"), text_color="#1E90FF").grid(
                     row=0, column=0, columnspan=4, pady=(12, 18))

        # prepare entries dictionary
        self.entries = {}
        self._build_form()

        # records frame placeholder
        self.records_frame = None

    # ---------------- build form ----------------
    def _build_form(self):
        options = {
            "Course": ["AI & DS", "AI & ML", "CSE", "CSE AI", "Mechanical", "Civil", "IT", "Electrical", "Cyber Security", "Robotics"],
            "Department": ["BTech", "MTech", "BCA", "MCA", "BBA", "MBA", "BSc", "MSc"],
            "Year": ["First", "Second", "Third", "Fourth"],
            "Gender": ["Male", "Female", "Other"],
            "Nationality": ["Indian", "American", "Canadian", "Other"],
            "Category": ["General", "OBC", "SC", "ST", "EWS"]
        }

        r, c = 1, 0
        for field in self.fields:
            label_text = field + (" *" if field in self.required_fields else "")
            lbl = ctk.CTkLabel(self.form_frame, text=label_text, font=("Helvetica", 13))
            lbl.grid(row=r, column=c * 2, padx=12, pady=8, sticky="w")

            if field in options:
                w = ctk.CTkOptionMenu(self.form_frame, values=options[field],
                                      fg_color="#1E1E1E", button_color="#1E90FF",
                                      text_color="white", width=300)
                w.set(f"Select {field}")
            elif field == "DOB":
                w = ctk.CTkEntry(self.form_frame, placeholder_text="DD/MM/YYYY",
                                 width=300, fg_color="#1E1E1E", text_color="white")
                w.bind("<Button-1>", lambda e, ent=w: self.open_calendar(ent))
            else:
                w = ctk.CTkEntry(self.form_frame, placeholder_text=field,
                                 width=300, fg_color="#1E1E1E", text_color="white")
            w.grid(row=r, column=c * 2 + 1, padx=12, pady=8, sticky="w")
            self.entries[field] = w

            if c == 1:
                c = 0
                r += 1
            else:
                c = 1

        # View Records button (spans full width)
        self.view_btn = ctk.CTkButton(self.form_frame, text="View Records", fg_color="#00CED1",
                                      hover_color="#009FBF", width=650, height=44,
                                      font=("Helvetica", 15, "bold"),
                                      command=self.show_view_record_inplace)
        self.view_btn.grid(row=r + 1, column=0, columnspan=4, pady=(18, 12))

        # Buttons frame (Save, Reset)
        self.btn_frame = ctk.CTkFrame(self.form_frame, fg_color="#151515")
        self.btn_frame.grid(row=r + 2, column=0, columnspan=4, pady=(6, 6))

        self.save_btn = ctk.CTkButton(self.btn_frame, text="Save", fg_color="#1E90FF",
                                      hover_color="#00BFFF", width=230, height=40,
                                      font=("Helvetica", 13, "bold"),
                                      command=lambda: self.save_or_update_record("Save"))
        self.save_btn.pack(side="left", padx=36, pady=6)

        self.reset_btn = ctk.CTkButton(self.btn_frame, text="Reset", fg_color="#7B68EE",
                                       hover_color="#9370DB", width=230, height=40,
                                       font=("Helvetica", 13, "bold"),
                                       command=self.reset_form)
        self.reset_btn.pack(side="left", padx=36, pady=6)

        # Photo frame contents
        ctk.CTkLabel(self.photo_frame, text="Student Photo", font=("Helvetica", 16, "bold"),
                     text_color="#1E90FF").pack(pady=(12, 6))
        self.img_label = ctk.CTkLabel(self.photo_frame, text="No Image Uploaded",
                                      width=250, height=250, fg_color="#0E0E0E", corner_radius=10)
        self.img_label.pack(pady=(6, 12))
        ctk.CTkButton(self.photo_frame, text="Upload Photo", fg_color="#00BFFF",
                      width=180, height=36, command=self.upload_photo).pack(pady=(6, 16))

    # ---------------- calendar popup ----------------
    def open_calendar(self, entry_widget):
        root = self.winfo_toplevel()
        top = ctk.CTkToplevel(root)
        top.title("Select Date of Birth")
        w, h = 360, 320
        root.update_idletasks()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()
        x = max(rx + (rw - w) // 2, 50)
        y = max(ry + (rh - h) // 2, 50)
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.transient(root)
        top.grab_set()
        cal = Calendar(top, selectmode="day", year=2000, month=1, day=1,
                       background="#151515", foreground="white",
                       headersbackground="#1E90FF", weekendbackground="#202020",
                       selectbackground="#00BFFF", date_pattern='dd/mm/yyyy')
        cal.pack(padx=10, pady=10, fill="both", expand=True)

        def pick_date():
            entry_widget.delete(0, "end")
            entry_widget.insert(0, cal.get_date())
            top.destroy()

        ctk.CTkButton(top, text="Select Date", fg_color="#00BFFF", command=pick_date).pack(pady=(4, 10))

    # ---------------- upload photo ----------------
    def upload_photo(self):
        file_path = filedialog.askopenfilename(title="Select Photo",
                                               filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")])
        if not file_path:
            return
        try:
            # open, copy to memory, then close to release lock
            with Image.open(file_path) as img:
                img_resized = img.resize((250, 250))
                img_tk = ImageTk.PhotoImage(img_resized.copy())
            self.img_label.configure(image=img_tk, text="")
            self.img_label.image = img_tk
            self.photo_path = file_path

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")

    # ---------------- db wrappers ----------------
    def db_insert_student(self, record):
        conn = get_db_connection()
        cur = conn.cursor()
        cols = ",".join(record.keys())
        placeholders = ",".join("?" for _ in record)
        sql = f"INSERT INTO students ({cols}) VALUES ({placeholders})"
        cur.execute(sql, tuple(record.values()))
        conn.commit()
        conn.close()

    def db_update_student(self, student_id_old, record):
        conn = get_db_connection()
        cur = conn.cursor()
        assignments = ",".join(f"{col}=?" for col in record.keys())
        sql = f"UPDATE students SET {assignments} WHERE student_id=?"
        params = list(record.values()) + [student_id_old]
        cur.execute(sql, tuple(params))
        conn.commit()
        conn.close()

    def db_delete_students(self, student_ids):
        conn = get_db_connection()
        cur = conn.cursor()
        qmarks = ",".join("?" for _ in student_ids)
        sql = f"DELETE FROM students WHERE student_id IN ({qmarks})"
        cur.execute(sql, tuple(student_ids))
        conn.commit()
        conn.close()

    def db_get_all(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students ORDER BY student_id")
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def db_get_by_id(self, sid):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE student_id=?", (sid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    # ---------------- save / update logic ----------------
    def save_or_update_record(self, action="Save"):
        # ensure Student ID is unlocked to read value
        sid_entry = self.entries.get("Student ID")
        if sid_entry:
            try:
                sid_entry.configure(state="normal")
            except Exception:
                pass
        # remove tooltip if present
        if self.sid_tooltip:
            try:
                self.sid_tooltip.hide_tip()
            except Exception:
                pass
            self.sid_tooltip = None

        # validate required fields
        missing = []
        for f in self.fields:
            if f in self.required_fields and f != "Photo":
                val = self._get_widget_value(self.entries.get(f))
                if not val or val.startswith("Select "):
                    missing.append(f)
        if "Photo" in self.required_fields and not self.photo_path:
            missing.append("Photo")

        if missing:
            messagebox.showerror("Missing Fields", "Required fields missing:\n - " + "\n - ".join(missing))
            return

        # Build DB record (column names)
        record = {
            "student_id": self._get_widget_value(self.entries["Student ID"]),
            "student_name": self._get_widget_value(self.entries["Student Name"]),
            "department": self._get_widget_value(self.entries["Department"]),
            "course": self._get_widget_value(self.entries["Course"]),
            "year": self._get_widget_value(self.entries["Year"]),
            "father_name": self._get_widget_value(self.entries["Father's Name"]),
            "father_occupation": self._get_widget_value(self.entries["Father's Occupation"]),
            "mother_name": self._get_widget_value(self.entries["Mother's Name"]),
            "mother_occupation": self._get_widget_value(self.entries["Mother's Occupation"]),
            "dob": self._get_widget_value(self.entries["DOB"]),
            "gender": self._get_widget_value(self.entries["Gender"]),
            "email": self._get_widget_value(self.entries["Email"]),
            "phone": self._get_widget_value(self.entries["Phone"]),
            "guardian_phone": self._get_widget_value(self.entries["Guardian's Phone"]),
            "category": self._get_widget_value(self.entries["Category"]),
            "religion": self._get_widget_value(self.entries["Religion"]),
            "residential_address": self._get_widget_value(self.entries["Residential Address"]),
            "permanent_address": self._get_widget_value(self.entries["Permanent Address"]),
            "nationality": self._get_widget_value(self.entries["Nationality"]),
            "photo_path": ""  # set after copying image
        }

        new_sid = record["student_id"]

        # handle photo copying into data/photos using student id
        if self.photo_path:
            src = Path(self.photo_path)
            ext = src.suffix or ".jpg"
            dest = PHOTOS_DIR / f"{new_sid}{ext}"
            try:
                # explicitly close any open image handles before copying
                try:
                    if hasattr(self, "photo_preview") and self.photo_preview:
                        self.photo_preview = None
                except Exception:
                    pass
                # retry copy a few times in case the file is temporarily locked
                for _ in range(3):
                    try:
                        shutil.copy2(src.as_posix(), dest.as_posix())
                        record["photo_path"] = dest.as_posix()
                        break
                    except PermissionError:
                        time.sleep(0.2)
                else:
                    raise
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Failed to copy photo:\n{e}\n\n(Please close any viewer using this image and try again.)"
                )
                return


        # perform DB insert or update
        if self.current_update_id:
            # update path
            # if student id changed and conflicts with existing -> disallow
            if new_sid != self.current_update_id and self.db_get_by_id(new_sid):
                messagebox.showerror("Duplicate", "Student ID already exists.")
                return
            try:
                self.db_update_student(self.current_update_id, record)
            except Exception as e:
                messagebox.showerror("DB Error", f"Failed to update record: {e}")
                return

            messagebox.showinfo("Updated", "Record updated successfully.")

            # remove Cancel button after save/update (if present)
            if getattr(self, "cancel_btn", None):
                try:
                    self.cancel_btn.grid_forget()
                    self.cancel_btn.destroy()
                except Exception:
                    pass
                self.cancel_btn = None

            # clear update id (exit update mode)
            self.current_update_id = None

        else:
            # insert path
            if self.db_get_by_id(new_sid):
                messagebox.showerror("Duplicate", "Student ID already exists.")
                return
            try:
                self.db_insert_student(record)
            except Exception as e:
                messagebox.showerror("DB Error", f"Failed to save record: {e}")
                return
            messagebox.showinfo("Saved", "Record saved to database.")

            # remove Cancel (if somehow present) — safe-guard
            if getattr(self, "cancel_btn", None):
                try:
                    self.cancel_btn.grid_forget()
                    self.cancel_btn.destroy()
                except Exception:
                    pass
                self.cancel_btn = None

        # refresh view if open
        if self.records_frame and getattr(self, "tree", None):
            self._populate_table()

        # clear the form (also unlock ID)
        self.reset_form()


    # ---------------- reset form ----------------
    def reset_form(self):
        # unlock Student ID if it was disabled
        sid_entry = self.entries.get("Student ID")
        if sid_entry:
            try:
                sid_entry.configure(state="normal")
            except Exception:
                pass
        # hide tooltip if present
        if self.sid_tooltip:
            try:
                self.sid_tooltip.hide_tip()
            except Exception:
                pass
            self.sid_tooltip = None
        
        # hide Cancel button if visible (safe-guard)
        if getattr(self, "cancel_btn", None):
            try:
                self.cancel_btn.grid_forget()
                self.cancel_btn.destroy()
            except Exception:
                pass
            self.cancel_btn = None

        # clear each widget (entries and option menus)
        for k, w in self.entries.items():
            try:
                w.delete(0, "end")
            except Exception:
                try:
                    w.set(f"Select {k}")
                except Exception:
                    pass

        # photo preview reset
        try:
            self.img_label.configure(image=None, text="No Image Uploaded")
            self.img_label.image = None
        except Exception:
            pass
        self.photo_path = None

        # remove cancel button if visible
        if self.cancel_btn:
            try:
                self.cancel_btn.destroy()
            except Exception:
                pass
            self.cancel_btn = None

        self.current_update_id = None

    # ---------------- view records in-place ----------------
    def show_view_record_inplace(self):
        # if already showing, toggle back to form
        if self.records_frame and self.records_frame.winfo_exists():
            self._show_form()
            return

        # hide form & photo frames
        self.form_frame.forget()
        self.photo_frame.forget()

        # build records frame
        self.records_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=12)
        self.records_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        header = ctk.CTkFrame(self.records_frame, fg_color="#151515")
        header.pack(fill="x", padx=10, pady=(8, 6))
        ctk.CTkLabel(header, text="Saved Student Records", font=("Helvetica", 17, "bold"),
                     text_color="#1E90FF").pack(side="left", padx=8)

        btns_right = ctk.CTkFrame(header, fg_color="#151515")
        btns_right.pack(side="right", padx=8)
        ctk.CTkButton(btns_right, text="Update Record", fg_color="#32CD32",
                      hover_color="#28A745", command=self.update_selected_record, width=130).pack(side="left", padx=6)
        ctk.CTkButton(btns_right, text="Delete Record", fg_color="#FF6347",
                      hover_color="#E53935", command=self.delete_selected_record, width=130).pack(side="left", padx=6)
        ctk.CTkButton(btns_right, text="Back to Form", fg_color="#7B68EE",
                      hover_color="#9370DB", command=self._show_form, width=130).pack(side="left", padx=6)
        ctk.CTkButton(btns_right, text="Export to Excel", fg_color="#00CED1",
                      hover_color="#009FBF", command=self.export_to_excel, width=140).pack(side="left", padx=6)

        # search frame
        search_frame = ctk.CTkFrame(self.records_frame, fg_color="#151515")
        search_frame.pack(fill="x", padx=10, pady=(6, 8))
        ctk.CTkLabel(search_frame, text="Search Student:", font=("Helvetica", 13), text_color="white").pack(side="left", padx=(6, 6))
        self.search_id = ctk.CTkEntry(search_frame, placeholder_text="Student ID (preferred)", width=180,
                                      fg_color="#1E1E1E", text_color="white")
        self.search_id.pack(side="left", padx=5)
        self.search_name = ctk.CTkEntry(search_frame, placeholder_text="Name (optional)", width=220,
                                        fg_color="#1E1E1E", text_color="white")
        self.search_name.pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Search", fg_color="#1E90FF", command=self.search_record, width=100).pack(side="left", padx=6)
        ctk.CTkButton(search_frame, text="Clear Search", fg_color="#7B68EE", command=self._populate_table, width=110).pack(side="left", padx=6)

        # table container with scrollbars
        table_container = ctk.CTkFrame(self.records_frame, fg_color="#151515")
        table_container.pack(fill="both", expand=True, padx=10, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1A1A1A", foreground="white",
                        fieldbackground="#1A1A1A", rowheight=26, font=("Helvetica", 11))
        style.configure("Treeview.Heading", background="#151515", foreground="#00CED1",
                        font=("Helvetica", 12, "bold"))
        style.map('Treeview', background=[('selected', '#00BFFF')], foreground=[('selected', 'white')])

        cols = self.fields + ["Photo"]
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # set sensible widths
        for col in cols:
            self.tree.heading(col, text=col)
            if col in ("Student ID", "Year"):
                self.tree.column(col, width=90, anchor="center")
            elif col in ("Student Name", "Residential Address", "Permanent Address"):
                self.tree.column(col, width=220, anchor="w")
            elif col == "Photo":
                self.tree.column(col, width=120, anchor="center")
            else:
                self.tree.column(col, width=140, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        self._populate_table()

    # ---------------- populate table ----------------
    def _populate_table(self):
        rows = self.db_get_all()
        # clear
        for r in self.tree.get_children():
            self.tree.delete(r)
        # insert
        for rec in rows:
            photo_fname = Path(rec.get("photo_path") or "").name or "NULL"
            row = [rec.get(self._db_col_for_field(f), "NULL") for f in self.fields] + [photo_fname]
            self.tree.insert("", "end", values=row)

    # ---------------- show form ----------------
    def _show_form(self):
        if self.records_frame:
            try:
                self.records_frame.destroy()
            except Exception:
                pass
            self.records_frame = None
        self.form_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        self.photo_frame.pack(side="right", fill="y", padx=20, pady=20)

    # ---------------- export to excel ----------------
    def export_to_excel(self):
        rows = self.db_get_all()
        if not rows:
            messagebox.showwarning("No data", "No records to export.")
            return
        df = pd.DataFrame(rows)
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if not path:
            return
        try:
            df.to_excel(path, index=False)
            messagebox.showinfo("Exported", "Records exported to Excel successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    # ---------------- update selected (load into form) ----------------
    def update_selected_record(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select one record to update.")
            return
        if len(selected) > 1:
            messagebox.showwarning("Warning", "Please select only one record to update.")
            return
        sid = self.tree.item(selected[0], "values")[0]
        db_rec = self.db_get_by_id(sid)
        if not db_rec:
            messagebox.showerror("Error", "Record not found.")
            return

        # show form view
        self._show_form()

        # populate form
        for f in self.fields:
            w = self.entries.get(f)
            val = db_rec.get(self._db_col_for_field(f), "")
            try:
                w.configure(state="normal")
                w.delete(0, "end")
                w.insert(0, val if val != "NULL" else "")
            except Exception:
                try:
                    w.set(val if val != "NULL" else f"Select {f}")
                except Exception:
                    pass

        # load photo preview
        photo_path = db_rec.get("photo_path")
        if photo_path and os.path.isfile(photo_path):
            try:
                img = Image.open(photo_path).resize((250, 250))
                img_tk = ImageTk.PhotoImage(img)
                self.img_label.configure(image=img_tk, text="")
                self.img_label.image = img_tk
                self.photo_path = photo_path
            except Exception:
                self.img_label.configure(image=None, text="No Image Uploaded")
                self.photo_path = None
        else:
            self.img_label.configure(image=None, text="No Image Uploaded")
            self.photo_path = None

        # set update id and lock Student ID
        self.current_update_id = sid
        sid_entry = self.entries.get("Student ID")
        if sid_entry:
            try:
                sid_entry.configure(state="disabled")
                # add bright-blue tooltip
                try:
                    self.sid_tooltip = ToolTip(sid_entry, "Student ID is locked during update mode")
                except Exception:
                    self.sid_tooltip = None
            except Exception:
                pass

        # --- create/show Cancel button (centered below Save/Reset) ---
        # We place the Cancel button in the form_frame grid centered under the packed Save/Reset buttons.
        # It will have same width as one Save/Reset button (120/230 area); adjust width to 230 to match one button.
        try:
            if not getattr(self, "cancel_btn", None):
                self.cancel_btn = ctk.CTkButton(
                    self.form_frame,
                    text="Cancel",
                    fg_color="#3A3F47",        # soft blue-gray base
                    hover_color="#5A6A8A",     # glowing hover
                    corner_radius=10,
                    font=("Helvetica", 13, "bold"),
                    width=230,                 # same as one Save/Reset button
                    height=36,
                    command=self.cancel_update
                )
            # place cancel button centered across the middle two columns (1 and 2)
            # form has 4 columns (0..3) for layout; center it using column=1 columnspan=2
            # compute row just below btn_frame
            btn_row = self.btn_frame.grid_info().get("row", None)
            place_row = (btn_row + 1) if btn_row is not None else None
            if place_row is not None:
                self.cancel_btn.grid(row=place_row, column=1, columnspan=2, pady=(12, 8))
            else:
                # fallback: place at a safe row near the bottom
                self.cancel_btn.grid(row=999, column=1, columnspan=2, pady=(12, 8))
        except Exception:
            # if anything fails, ensure no crash — silently ignore
            pass


    # ---------------- cancel update ----------------
    def cancel_update(self):
        # hide Cancel immediately
        if getattr(self, "cancel_btn", None):
            try:
                self.cancel_btn.grid_forget()
                self.cancel_btn.destroy()
            except Exception:
                pass
            self.cancel_btn = None

        self.reset_form()
        messagebox.showinfo("Cancelled", "Update cancelled.")

    # ---------------- delete ----------------
    def delete_selected_record(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select record(s) to delete.")
            return
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {len(selected)} record(s)?")
        if not confirm:
            return
        sids = [self.tree.item(i, "values")[0] for i in selected]
        try:
            self.db_delete_students(sids)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to delete: {e}")
            return
        # Optionally remove photo files? currently not removing files to avoid accidental permanent delete
        self._populate_table()
        messagebox.showinfo("Deleted", f"{len(sids)} record(s) deleted.")

    # ---------------- search ----------------
    def search_record(self):
        sid = self.search_id.get().strip()
        name = self.search_name.get().strip().lower()
        results = []
        if sid:
            rec = self.db_get_by_id(sid)
            if rec and (not name or name in (rec.get("student_name") or "").lower()):
                results.append(rec)
        elif name:
            all_rows = self.db_get_all()
            for r in all_rows:
                if name in (r.get("student_name") or "").lower():
                    results.append(r)
        else:
            messagebox.showwarning("Input Required", "Please enter Student ID or Name to search.")
            return

        # populate tree with results
        for r in self.tree.get_children():
            self.tree.delete(r)
        if not results:
            messagebox.showinfo("No Match", "No records found.")
            return
        for rec in results:
            photo_fname = Path(rec.get("photo_path") or "").name or "NULL"
            row = [rec.get(self._db_col_for_field(f), "NULL") for f in self.fields] + [photo_fname]
            self.tree.insert("", "end", values=row)

    # ---------------- helpers ----------------
    def _get_widget_value(self, widget):
        if widget is None:
            return ""
        try:
            return widget.get().strip()
        except Exception:
            try:
                return str(widget.get()).strip()
            except Exception:
                return ""

    @staticmethod
    def _db_col_for_field(field_label):
        mapping = {
            "Student ID": "student_id",
            "Student Name": "student_name",
            "Department": "department",
            "Course": "course",
            "Year": "year",
            "Father's Name": "father_name",
            "Father's Occupation": "father_occupation",
            "Mother's Name": "mother_name",
            "Mother's Occupation": "mother_occupation",
            "DOB": "dob",
            "Gender": "gender",
            "Email": "email",
            "Phone": "phone",
            "Guardian's Phone": "guardian_phone",
            "Category": "category",
            "Religion": "religion",
            "Residential Address": "residential_address",
            "Permanent Address": "permanent_address",
            "Nationality": "nationality",
        }
        return mapping.get(field_label, field_label.lower())

# -------------------- End of Class --------------------

# Optional: quick test runner when this file is executed directly
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    root = ctk.CTk()
    root.geometry("1200x780")
    root.title("Student Records")
    app = StudentRecordsFrame(root)
    app.pack(fill="both", expand=True)
    root.mainloop()
