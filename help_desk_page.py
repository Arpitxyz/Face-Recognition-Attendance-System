# help_desk_page.py
"""
Help Desk Page
--------------
Users can input social media platforms and their respective links.
Initially shows 3 editable rows. Users can add more rows dynamically.
A Save button stores entries in the database.
"""

import customtkinter as ctk
from tkinter import messagebox
from student_records import get_db_connection


class HelpDeskFrame(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#0E0E0E")
        self.parent = parent

        # ---------- Header ----------
        header = ctk.CTkFrame(self, fg_color="#151515")
        header.pack(fill="x", padx=20, pady=(20, 10))

        title = ctk.CTkLabel(header,
                             text="Help Desk (Social Media Links)",
                             font=("Helvetica", 20, "bold"),
                             text_color="#1E90FF")
        title.pack(side="left", padx=10)

        # Add & Save Buttons
        self.add_btn = ctk.CTkButton(
            header,
            text="+ ADD",
            width=120,
            fg_color="#1E90FF",
            hover_color="#0A84FF",
            font=("Helvetica", 14, "bold"),
            command=self.add_row
        )
        self.add_btn.pack(side="right", padx=10)

        self.save_btn = ctk.CTkButton(
            header,
            text="💾 SAVE",
            width=120,
            fg_color="#32CD32",
            hover_color="#28A745",
            font=("Helvetica", 14, "bold"),
            command=self.save_entries
        )
        self.save_btn.pack(side="right", padx=10)

        # ---------- Table container ----------
        self.table_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=12)
        self.table_frame.pack(fill="x", padx=30, pady=20)
        self.table_frame.grid_columnconfigure((0, 1), weight=1, uniform="equal")

        # Column titles
        ctk.CTkLabel(self.table_frame, text="Platform", font=("Helvetica", 15, "bold"),
                     text_color="white").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkLabel(self.table_frame, text="Link", font=("Helvetica", 15, "bold"),
                     text_color="white").grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Storage for entry fields
        self.rows = []
        for _ in range(3):
            self.add_row()

        # Create table if not exists
        self.create_table()
        self.load_existing_links()

    # ------------------------------------------------------------------
    def create_table(self):
        """Ensure the helpdesk_links table exists."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS helpdesk_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                link TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def add_row(self, platform="", link=""):
        """Add a new editable row."""
        row_index = len(self.rows) + 1  # row 0 is header
        row_frame = {}

        row_frame["platform_entry"] = ctk.CTkEntry(
            self.table_frame,
            placeholder_text="Social Media Platform",
            width=250,
            fg_color="#1E1E1E",
            text_color="white"
        )
        row_frame["platform_entry"].grid(row=row_index, column=0, padx=10, pady=8, sticky="ew")
        row_frame["platform_entry"].insert(0, platform)

        row_frame["link_entry"] = ctk.CTkEntry(
            self.table_frame,
            placeholder_text="Profile / Contact Link",
            width=400,
            fg_color="#1E1E1E",
            text_color="white"
        )
        row_frame["link_entry"].grid(row=row_index, column=1, padx=10, pady=8, sticky="ew")
        row_frame["link_entry"].insert(0, link)

        self.rows.append(row_frame)

    def load_existing_links(self):
        """Load existing links from DB."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform, link FROM helpdesk_links ORDER BY id")
        rows = cur.fetchall()
        conn.close()

        # Clear any pre-filled rows, recreate for consistency
        for i, r in enumerate(rows):
            if i < len(self.rows):
                self.rows[i]["platform_entry"].delete(0, "end")
                self.rows[i]["platform_entry"].insert(0, r["platform"])
                self.rows[i]["link_entry"].delete(0, "end")
                self.rows[i]["link_entry"].insert(0, r["link"])
            else:
                self.add_row(r["platform"], r["link"])

    def save_entries(self):
        """Save all entered links into the database."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM helpdesk_links")  # overwrite with current entries

        for row in self.rows:
            platform = row["platform_entry"].get().strip()
            link = row["link_entry"].get().strip()
            if platform and link:
                cur.execute("INSERT INTO helpdesk_links (platform, link) VALUES (?, ?)", (platform, link))

        conn.commit()
        conn.close()
        messagebox.showinfo("Saved", "Help Desk links have been saved successfully!")
