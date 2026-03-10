# main.py
"""
Face Recognition Dashboard — Single Window Version
Sidebar + Topbar stay fixed. Pages (Dashboard / Student Records) switch inside main area.
"""

import customtkinter as ctk
import datetime
import random
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from attendance_face import TakeAttendanceFrame
from attendance_log import AttendanceLogFrame
import subprocess
from attendees_page import AttendeesFrame
from absentees_page import AbsenteesFrame
from help_desk_page import HelpDeskFrame

# import the page frame defined in student_records.py
from student_records import StudentRecordsFrame


# ---------- Glow Pulse ----------
def add_glow_pulse(widget: ctk.CTkButton):
    original_color = widget.cget("fg_color")
    pulse_active = {"run": False}
    brightness = {"val": 0.0, "dir": 1}

    def pulse():
        if not pulse_active["run"] or not widget.winfo_exists():
            try:
                widget.configure(fg_color=original_color)
            except Exception:
                pass
            return
        brightness["val"] += 0.03 * brightness["dir"]
        if brightness["val"] >= 0.5:
            brightness["dir"] = -1
        elif brightness["val"] <= 0.0:
            brightness["dir"] = 1
        mix = brightness["val"]
        color = "#%02x%02x%02x" % (
            int((1 - mix) * 30 + mix * 30),
            int((1 - mix) * 30 + mix * 136),
            int((1 - mix) * 30 + mix * 229),
        )
        try:
            widget.configure(fg_color=color)
        except Exception:
            pass
        widget.after(70, pulse)

    def on_enter(_=None):
        pulse_active["run"] = True
        pulse()

    def on_leave(_=None):
        pulse_active["run"] = False
        try:
            widget.configure(fg_color=original_color)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")


# ---------- Main App ----------
class FaceRecognitionApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Face Recognition Dashboard")
        self.state("zoomed")
        self.geometry("1500x850")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Layout frames
        self.create_topbar()
        self.create_sidebar()

        # Container for dynamic content
        self.main_container = ctk.CTkFrame(self, fg_color="#0E0E0E")
        self.main_container.pack(side="left", fill="both", expand=True)

        self.dashboard_frame = None
        self.student_records_frame = None
        self.current_frame = None

        self.show_dashboard()

        self.protocol("WM_DELETE_WINDOW", self.safe_exit)

    # ---------- Top Bar ----------
    def create_topbar(self):
        # --- Create Topbar Frame ---
        self.topbar = ctk.CTkFrame(self, fg_color="#111111", height=50)
        self.topbar.pack(fill="x", side="top")

        # --- Title ---
        self.title_label = ctk.CTkLabel(
            self.topbar, text="Face Recognition", font=("Helvetica", 20, "bold")
        )
        self.title_label.pack(side="left", padx=20)

        # --- Search Bar with Autocomplete ---
        self.search_var = ctk.StringVar()
        self.search = ctk.CTkEntry(
            self.topbar,
            textvariable=self.search_var,
            placeholder_text="Quick Search...",
            width=400,
        )
        self.search.pack(side="left", padx=10, pady=10)

        # Suggestions dropdown (hidden initially)
        self.suggestion_box = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=10)
        self.suggestion_labels = []

        # Bindings
        self.search.bind("<KeyRelease>", self.update_suggestions)
        self.search.bind("<Return>", self.quick_search)

        # --- Mode Toggle (Dark / Light) ---
        self.theme_mode = "dark"
        self.theme_toggle = ctk.CTkButton(
            self.topbar,
            text="🌙 Dark Mode",
            fg_color="#1E90FF",
            hover_color="#0A84FF",
            width=130,
            command=self.toggle_theme
        )
        self.theme_toggle.pack(side="right", padx=10)

        # --- Refresh Button ---
        self.refresh_btn = ctk.CTkButton(
            self.topbar, text="⟳", width=40, fg_color="#1E90FF", command=self.refresh
        )
        self.refresh_btn.pack(side="right", padx=10)
        add_glow_pulse(self.refresh_btn)


    # ---------- Sidebar ----------
    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color="#151515", width=200)
        self.sidebar.pack(side="left", fill="y")

        # New order & renamed buttons (per user instructions)
        buttons = [
            ("🏠  Dashboard", self.show_dashboard),
            ("👤  Student Records", self.show_student_records),
            ("📝  Take Attendance", self.show_take_attendance),
            ("🕒  Attendance Log", self.show_attendance_log),
            ("✅  Attendees", self.show_attendees),
            ("🚫  Absentees", self.show_absentees),
            ("❓  Help Desk", self.show_help_desk)
        ]

        # store sidebar buttons if you want to highlight active page later
        self.sidebar_buttons = {}
        for text, cmd in buttons:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                corner_radius=8,
                fg_color="#1E90FF",
                hover_color="#0A84FF",
                font=("Helvetica", 14),
                height=40,
                command=cmd,
            )
            btn.pack(padx=10, pady=6, fill="x")
            add_glow_pulse(btn)
            self.sidebar_buttons[text] = btn

        # --- Logout Button (same style as Exit) ---
        self.logout_btn = ctk.CTkButton(
            self.sidebar,
            text="Logout",
            fg_color="#B22222",
            hover_color="#FF0000",
            command=self.logout_to_login,
        )
        self.logout_btn.pack(side="bottom", pady=(0, 10), padx=10, fill="x")
        add_glow_pulse(self.logout_btn)

        # --- Exit Button ---
        self.exit_btn = ctk.CTkButton(
            self.sidebar,
            text="Exit",
            fg_color="#B22222",
            hover_color="#FF0000",
            command=self.safe_exit,
        )
        self.exit_btn.pack(side="bottom", pady=(0, 15), padx=10, fill="x")
        add_glow_pulse(self.exit_btn)



    # ---------- Dashboard ----------
    def build_dashboard(self):
        frame = ctk.CTkScrollableFrame(self.main_container, fg_color="#0E0E0E")
        frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Weather card
        weather = ctk.CTkFrame(frame, fg_color="#1A1A1A", corner_radius=15)
        weather.grid(row=0, column=0, rowspan=2, padx=30, pady=20, sticky="nsew")

        # Dynamic day/night icon
        current_hour = datetime.datetime.now().hour
        icon = "☀️" if 6 <= current_hour < 18 else "🌙"
        self.icon_label = ctk.CTkLabel(weather, text=icon, font=("Helvetica", 50))
        self.icon_label.pack(pady=(20, 10))

        self.time_label = ctk.CTkLabel(weather, text="", font=("Helvetica", 18, "bold"))
        self.time_label.pack()
        self.update_time()

        self.date_label = ctk.CTkLabel(
            weather, text="Today: " + datetime.datetime.now().strftime("%d %B %Y")
        )

        self.date_label.pack(pady=5)

        ctk.CTkLabel(weather, text="Realtime Insight").pack()

        # Advanced Configuration button
        adv_btn = ctk.CTkButton(
            weather,
            text="Advanced Configuration",
            fg_color="#1E90FF",
            hover_color="#0A84FF",
            command=self.open_datetime_config,
        )
        adv_btn.pack(pady=15)
        add_glow_pulse(adv_btn)

        # Cards (names updated to match new sidebar labels)
        cards = [
            ("👤 Student Records", self.show_student_records),
            ("📝  Take Attendance", self.show_take_attendance),
            ("🕒  Attendance Log", self.show_attendance_log),
            ("✅ Attendees", self.show_attendees),
            ("🚫 Absentees", self.show_absentees),
            ("❓ Help Desk", self.show_help_desk)
        ]

        r, c = 0, 1
        for name, cmd in cards:
            card = ctk.CTkButton(
                frame,
                text=name,
                fg_color="#1A1A1A",
                hover_color="#101010",
                corner_radius=15,
                font=("Helvetica", 16, "bold"),
                height=120,
                command=cmd,
            )
            card.grid(row=r, column=c, padx=20, pady=20, sticky="nsew")
            add_glow_pulse(card)
            c += 1
            if c > 3:
                c = 1
                r += 1

        # Chart moved to bottom, full width
        # Chart moved to bottom, full width
        chart_frame = ctk.CTkFrame(frame, fg_color="#151515", corner_radius=15)
        chart_frame.grid(row=r + 1, column=0, columnspan=4, padx=25, pady=20, sticky="nsew")

        # --- Import needed libs ---
        import sqlite3
        import matplotlib.dates as mdates

        # --- Fetch attendance data from DB ---
        def get_daywise_attendance():
            try:
                from student_records import get_db_connection
                conn = get_db_connection()
            except Exception:
                conn = sqlite3.connect("attendance.db")
            cur = conn.cursor()
            cur.execute("""
                SELECT date, COUNT(CASE WHEN status='Present' THEN 1 END) AS present_count
                FROM attendance_records
                GROUP BY date
                ORDER BY date ASC
            """)
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return [], []
            dates = [datetime.datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
            counts = [r[1] for r in rows]
            return dates, counts

        # --- Get data ---
        dates, counts = get_daywise_attendance()
        if not dates:
            ctk.CTkLabel(chart_frame, text="No attendance data available", text_color="white").pack(pady=30)
            return frame

        # --- Group by week ---
        weekly_data = []
        current_week = []
        for i, d in enumerate(dates):
            if not current_week or d.isocalendar()[1] == current_week[-1][0].isocalendar()[1]:
                current_week.append((d, counts[i]))
            else:
                weekly_data.append(current_week)
                current_week = [(d, counts[i])]
        if current_week:
            weekly_data.append(current_week)

        self.current_week_index = len(weekly_data) - 1

        # --- Navigation buttons ---
        nav_frame = ctk.CTkFrame(chart_frame, fg_color="#151515")
        nav_frame.pack(fill="x", pady=(10, 5))

        prev_btn = ctk.CTkButton(
            nav_frame, text="⬅ Previous Week",
            fg_color="#1E90FF", hover_color="#0A84FF", width=160,
            command=lambda: update_chart(self.current_week_index - 1)
        )
        prev_btn.pack(side="left", padx=25, pady=5)

        next_btn = ctk.CTkButton(
            nav_frame, text="Next Week ➡",
            fg_color="#1E90FF", hover_color="#0A84FF", width=160,
            command=lambda: update_chart(self.current_week_index + 1)
        )
        next_btn.pack(side="right", padx=25, pady=5)

        # --- Create Matplotlib chart ---
        fig, ax = plt.subplots(figsize=(14, 4), dpi=120, facecolor="#151515")
        ax.set_facecolor("#151515")
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True)

        def update_chart(index):
            if not weekly_data or index < 0 or index >= len(weekly_data):
                return
            self.current_week_index = index

            ax.clear()
            week = weekly_data[index]
            x = [w[0] for w in week]
            y = [w[1] for w in week]

            ax.plot(
                x, y, color="#00BFFF", linewidth=3, marker="o",
                markersize=7, markerfacecolor="#00BFFF", markeredgecolor="white"
            )
            ax.set_title("Weekly Attendance Trend", color="white", fontsize=12, pad=10)
            ax.set_xlabel("Date", color="white", fontsize=10)
            ax.set_ylabel("Present Count", color="white", fontsize=10)

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
            ax.tick_params(colors="white", labelsize=9, rotation=45)
            ax.spines["bottom"].set_color("#00BFFF")
            ax.spines["left"].set_color("#00BFFF")
            ax.grid(color="#1E90FF", alpha=0.3, linestyle="--", linewidth=0.8)

            fig.tight_layout(pad=2)
            canvas.draw()

        # Initial render
        update_chart(self.current_week_index)

        return frame





    # ---------- Page Control ----------
    def show_dashboard(self):
        self.title_label.configure(text="Face Recognition")
        if self.current_frame:
            self.current_frame.pack_forget()
        if not self.dashboard_frame:
            self.dashboard_frame = self.build_dashboard()
        self.dashboard_frame.pack(fill="both", expand=True)
        self.current_frame = self.dashboard_frame

    def show_student_records(self):
        self.title_label.configure(text="STUDENT RECORDS")
        if self.current_frame:
            self.current_frame.pack_forget()
        if not self.student_records_frame:
            self.student_records_frame = StudentRecordsFrame(self.main_container)
        self.student_records_frame.pack(fill="both", expand=True)
        self.current_frame = self.student_records_frame

    # ---------- Time & Icon Update ----------
    def update_time(self):
        """Update real-time clock and switch icon for day/night safely."""
        try:
            if hasattr(self, "date_label") and hasattr(self, "time_label"):
                now = datetime.now()
                # Update time
                self.time_label.configure(text=now.strftime("%I:%M:%S %p"))
                # Update date
                self.date_label.configure(text="Today: " + now.strftime("%d %B %Y"))
                # Switch icon
                icon = "☀️" if 6 <= now.hour < 18 else "🌙"
                self.icon_label.configure(text=icon)
        except Exception as e:
            print("update_time skipped (not ready yet):", e)

        # Schedule next update safely
        self.after(1000, self.update_time)

    # ---------- Advanced Configuration Popup ----------
    def open_datetime_config(self):
        """Popup to manually adjust date and time display."""
        popup = ctk.CTkToplevel(self)
        popup.title("Advanced Configuration")
        popup.geometry("400x300")
        popup.grab_set()
        popup.configure(fg_color="#1A1A1A")

        ctk.CTkLabel(popup, text="Modify Date & Time", font=("Helvetica", 16, "bold")).pack(
            pady=15
        )

        # Date Entry
        date_entry = ctk.CTkEntry(popup, placeholder_text="Enter Date (DD-MM-YYYY)", width=250)
        date_entry.pack(pady=10)

        # Time Entry
        time_entry = ctk.CTkEntry(popup, placeholder_text="Enter Time (HH:MM AM/PM)", width=250)
        time_entry.pack(pady=10)

        def apply_changes():
            d_text = date_entry.get().strip()
            t_text = time_entry.get().strip()
            if d_text:
                self.date_label.configure(text="Today: " + d_text)
            if t_text:
                self.time_label.configure(text=t_text)
            popup.destroy()

        apply_btn = ctk.CTkButton(
            popup, text="Apply Changes", fg_color="#1E90FF", hover_color="#0A84FF", command=apply_changes
        )
        apply_btn.pack(pady=20)
        add_glow_pulse(apply_btn)

    def refresh(self):
        print("Refreshing dashboard...")
    
    def show_take_attendance(self):
        from attendance_face import TakeAttendanceFrame
        self.title_label.configure(text="TAKE ATTENDANCE")
        if self.current_frame:
            self.current_frame.pack_forget()
        if not hasattr(self, "take_attendance_frame"):
            self.take_attendance_frame = TakeAttendanceFrame(self.main_container)

        self.title_label.configure(text="TAKE ATTENDANCE")
        if self.current_frame:
            self.current_frame.pack_forget()

        self.take_attendance_frame.pack(fill="both", expand=True)
        self.current_frame = self.take_attendance_frame




    def safe_exit(self):
        # try to stop repeating tasks and close figures gracefully
        try:
            # cancel the repeating update_time() callback if scheduled
            self.after_cancel(self.update_time)
        except Exception:
            pass
        try:
            import matplotlib.pyplot as plt
            plt.close("all")           # close any open matplotlib windows
        except Exception:
            pass
        try:
            self.destroy()             # destroy all Tkinter widgets
        except Exception:
            pass
        try:
            self.quit()                # end the mainloop cleanly
        except Exception:
            pass

    
    def show_attendance_log(self):
        self.title_label.configure(text="ATTENDANCE LOG")
        if self.current_frame:
            self.current_frame.pack_forget()
        self.attendance_log_frame = AttendanceLogFrame(self.main_container)
        self.attendance_log_frame.pack(fill="both", expand=True)
        self.current_frame = self.attendance_log_frame
    

    def logout_to_login(self):
        """Closes dashboard and reopens login.py."""
        try:
            import matplotlib.pyplot as plt
            plt.close("all")
        except Exception:
            pass
        try:
            self.destroy()
            self.quit()
        except Exception:
            pass
        # Relaunch login window
        try:
            subprocess.Popen(["python", "login.py"])
        except Exception as e:
            print(f"Failed to reopen login: {e}")

    def show_attendees(self):
        self.title_label.configure(text="ATTENDEES")
        if self.current_frame:
            self.current_frame.pack_forget()
        self.attendees_frame = AttendeesFrame(self.main_container)
        self.attendees_frame.pack(fill="both", expand=True)
        self.current_frame = self.attendees_frame

    def show_absentees(self):
        self.title_label.configure(text="ABSENTEES")
        if self.current_frame:
            self.current_frame.pack_forget()
        self.absentees_frame = AbsenteesFrame(self.main_container)
        self.absentees_frame.pack(fill="both", expand=True)
        self.current_frame = self.absentees_frame
    
    def show_help_desk(self):
        self.title_label.configure(text="HELP DESK")
        if self.current_frame:
            self.current_frame.pack_forget()
        self.help_desk_frame = HelpDeskFrame(self.main_container)
        self.help_desk_frame.pack(fill="both", expand=True)
        self.current_frame = self.help_desk_frame

    def toggle_theme(self):
        """Toggle between light and dark mode with professional transitions."""
        if self.theme_mode == "dark":
            self.theme_mode = "light"
            ctk.set_appearance_mode("light")
            self.theme_toggle.configure(text="☀️ Light Mode", fg_color="#FFA500", hover_color="#FF8C00")
        else:
            self.theme_mode = "dark"
            ctk.set_appearance_mode("dark")
            self.theme_toggle.configure(text="🌙 Dark Mode", fg_color="#1E90FF", hover_color="#0A84FF")
    
    def quick_search(self, event=None):
        """Open pages based on user search keywords."""
        query = self.search.get().strip().lower()
        if not query:
            return

        pages = {
            "dashboard": self.show_dashboard,
            "home": self.show_dashboard,
            "student": self.show_student_records,
            "record": self.show_student_records,
            "attendance": self.show_take_attendance,
            "take": self.show_take_attendance,
            "log": self.show_attendance_log,
            "attendee": self.show_attendees,
            "present": self.show_attendees,
            "absentee": self.show_absentees,
            "absent": self.show_absentees,
            "help": self.show_help_desk,
            "desk": self.show_help_desk,
        }

        for key, func in pages.items():
            if key in query:
                func()
                self.suggestion_box.place_forget()
                self.search.delete(0, "end")
                return

        matched = None
        for key, func in pages.items():
            if key in query:
                matched = func
                break

        if matched:
            matched()
            self.search.delete(0, "end")
        else:
            from tkinter import messagebox
            messagebox.showinfo("Not Found", f"No matching page found for: {query}")
    
    def update_suggestions(self, event=None):
        """Show live suggestions as user types."""
        query = self.search_var.get().strip().lower()
        for label in self.suggestion_labels:
            label.destroy()
        self.suggestion_labels.clear()

        if not query:
            self.suggestion_box.place_forget()
            return

        # Suggestible keywords
        options = {
            "Dashboard": self.show_dashboard,
            "Student Records": self.show_student_records,
            "Take Attendance": self.show_take_attendance,
            "Attendance Log": self.show_attendance_log,
            "Attendees": self.show_attendees,
            "Absentees": self.show_absentees,
            "Help Desk": self.show_help_desk,
        }

        matches = [name for name in options.keys() if query in name.lower()]
        if not matches:
            self.suggestion_box.place_forget()
            return

        # Position suggestions below search box
        x = self.search.winfo_rootx() - self.winfo_rootx()
        y = self.search.winfo_y() + self.search.winfo_height() + 45
        # ✅ Correct:
        self.suggestion_box.place(x=x + 220, y=y)
        self.suggestion_box.configure(width=400, height=len(matches) * 30 + 10)


        for match in matches:
            lbl = ctk.CTkLabel(
                self.suggestion_box,
                text=match,
                text_color="white",
                fg_color="#2B2B2B",
                corner_radius=6,
                font=("Helvetica", 13),
            )
            lbl.pack(fill="x", padx=4, pady=2)
            lbl.bind("<Button-1>", lambda e, m=match: self.select_suggestion(m, options))
            lbl.bind("<Enter>", lambda e, l=lbl: l.configure(fg_color="#1E90FF"))
            lbl.bind("<Leave>", lambda e, l=lbl: l.configure(fg_color="#2B2B2B"))
            self.suggestion_labels.append(lbl)


    def select_suggestion(self, match, options):
        """Handle suggestion click."""
        self.search.delete(0, "end")
        self.suggestion_box.place_forget()
        options[match]()  # open the corresponding page



# ---------- Run ----------
if __name__ == "__main__":
    app = FaceRecognitionApp()
    app.mainloop()
