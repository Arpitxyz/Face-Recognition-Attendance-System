# attendance_log.py
"""
Attendance Log Viewer
----------------------
Displays attendance marked by the camera (from attendance_face.py).
Features:
✅ Day-wise view (defaults to today)
✅ Date search (manual entry or calendar)
✅ Filter Present / Absent students
✅ Export to Excel
✅ Matches app dark theme
"""

import os
from datetime import datetime
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import pandas as pd
from tkcalendar import Calendar

from student_records import get_db_connection


class AttendanceLogFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#0E0E0E")
        self.parent = parent

        self.selected_date = datetime.now().strftime("%Y-%m-%d")

        # ---------- Header ----------
        header = ctk.CTkFrame(self, fg_color="#151515")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(header, text="Attendance Log",
                     font=("Helvetica", 20, "bold"),
                     text_color="#1E90FF").pack(side="left", padx=10)

        # Date search frame
        date_frame = ctk.CTkFrame(header, fg_color="#151515")
        date_frame.pack(side="left", padx=20)

        ctk.CTkLabel(date_frame, text="Select Date:",
                     font=("Helvetica", 13), text_color="white").pack(side="left", padx=(0, 8))
        self.date_entry = ctk.CTkEntry(date_frame, width=130,
                                       placeholder_text="YYYY-MM-DD",
                                       fg_color="#1E1E1E", text_color="white")
        self.date_entry.insert(0, self.selected_date)
        self.date_entry.pack(side="left")

        ctk.CTkButton(date_frame, text="📅", width=40, fg_color="#1E90FF",
                      command=self.open_calendar).pack(side="left", padx=6)
        ctk.CTkButton(date_frame, text="Show", width=80,
                      fg_color="#1E90FF", hover_color="#0A84FF",
                      command=self.load_attendance).pack(side="left", padx=6)

        # Filter Buttons
        filter_frame = ctk.CTkFrame(header, fg_color="#151515")
        filter_frame.pack(side="right", padx=20)

        self.show_all_btn = ctk.CTkButton(filter_frame, text="All", width=100,
                                          fg_color="#7B68EE",
                                          hover_color="#9370DB",
                                          command=self.show_all)
        self.show_all_btn.pack(side="left", padx=6)

        self.present_btn = ctk.CTkButton(filter_frame, text="Present", width=100,
                                         fg_color="#32CD32",
                                         hover_color="#28A745",
                                         command=self.show_present)
        self.present_btn.pack(side="left", padx=6)

        self.absent_btn = ctk.CTkButton(filter_frame, text="Absent", width=100,
                                        fg_color="#FF6347",
                                        hover_color="#E53935",
                                        command=self.show_absent)
        self.absent_btn.pack(side="left", padx=6)

        # Export Button
        self.export_btn = ctk.CTkButton(filter_frame, text="Export to Excel",
                                        fg_color="#00CED1", hover_color="#009FBF",
                                        width=140, command=self.export_excel)
        self.export_btn.pack(side="left", padx=6)

        # ---------- Table ----------
        table_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=12)
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ["Student ID", "Name", "Date", "Time", "Status"]
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140, anchor="center")

        # Treeview style for dark mode
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#151515",
            foreground="white",
            fieldbackground="#151515",
            rowheight=26,
            font=("Helvetica", 11)
        )
        style.configure(
            "Treeview.Heading",
            background="#1E90FF",
            foreground="white",
            font=("Helvetica", 12, "bold")
        )
        style.map("Treeview",
                  background=[("selected", "#1E90FF")],
                  foreground=[("selected", "white")])

        # ---------- Load initial data ----------
        self.load_attendance()

    # ------------------------------------------------------------------
    def open_calendar(self):
        """Open date picker popup."""
        root = self.winfo_toplevel()
        top = ctk.CTkToplevel(root)
        top.title("Select Date")
        top.geometry("300x320")
        top.configure(fg_color="#1A1A1A")
        top.grab_set()

        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd",
                       background="#151515", foreground="white",
                       headersbackground="#1E90FF", weekendbackground="#202020",
                       selectbackground="#00BFFF")
        cal.pack(padx=10, pady=10, fill="both", expand=True)

        def pick_date():
            self.date_entry.delete(0, "end")
            self.date_entry.insert(0, cal.get_date())
            top.destroy()
            self.load_attendance()

        ctk.CTkButton(top, text="Select Date", fg_color="#1E90FF",
                      command=pick_date).pack(pady=(6, 10))

    # ------------------------------------------------------------------
    def fetch_attendance(self, date):
        """Fetch attendance records for a specific date."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM attendance_records WHERE date=? ORDER BY time", (date,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def fetch_all_students(self):
        """Fetch all registered students (for absent comparison)."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT student_id, student_name FROM students ORDER BY student_id")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    def load_attendance(self):
        """Populate the table for the selected date."""
        date_str = self.date_entry.get().strip()
        if not date_str:
            messagebox.showwarning("Missing Date", "Please enter or select a date.")
            return

        self.selected_date = date_str
        rows = self.fetch_attendance(date_str)
        self.populate_table(rows)

    def populate_table(self, rows):
        """Clear and refill tree."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in rows:
            self.tree.insert("", "end", values=(r["student_id"], r["name"], r["date"], r["time"], r["status"]))

    # ------------------------------------------------------------------
    def show_all(self):
        rows = self.fetch_attendance(self.selected_date)
        self.populate_table(rows)

    def show_present(self):
        rows = [r for r in self.fetch_attendance(self.selected_date) if r["status"].lower() == "present"]
        self.populate_table(rows)

    def show_absent(self):
        """Show students who are in student DB but not marked present."""
        date = self.selected_date
        all_students = self.fetch_all_students()
        present = {r["student_id"] for r in self.fetch_attendance(date)}

        absent_rows = []
        for s in all_students:
            if s["student_id"] not in present:
                absent_rows.append({
                    "student_id": s["student_id"],
                    "name": s["student_name"],
                    "date": date,
                    "time": "-",
                    "status": "Absent"
                })
        self.populate_table(absent_rows)

    # ------------------------------------------------------------------
    def export_excel(self):
        """Export current table to Excel."""
        rows = [self.tree.item(i, "values") for i in self.tree.get_children()]
        if not rows:
            messagebox.showwarning("No Data", "No records to export.")
            return
        df = pd.DataFrame(rows, columns=["Student ID", "Name", "Date", "Time", "Status"])
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                            filetypes=[("Excel files", "*.xlsx")],
                                            title="Save Attendance Log")
        if not path:
            return
        try:
            df.to_excel(path, index=False)
            messagebox.showinfo("Exported", "Attendance exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
