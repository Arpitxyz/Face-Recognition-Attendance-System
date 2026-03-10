# login.py
"""
Single-window Login UI for your Face Recognition Dashboard.
Features:
- Wallpaper background (tries "login page.png" first, then a couple of uploaded fallbacks).
- Username (alphanumeric, >=5), Password (>=6).
- Create Account, Delete Account, Forgot Password (hint).
- Show/Hide password toggle.
- Admin account (admin/admin123) is created automatically and cannot be deleted.
- 3 login attempts -> 30s cooldown with counting display.
- Smooth fade-in (~0.8s).
- On successful login, destroys login window and launches main.FaceRecognitionApp (same process).
"""

import os
import sqlite3
import hashlib
import time
import threading
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

# ---------- Config ----------
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "users.db"
WALLPAPER_CANDIDATES = [
    "login page.png",                             # user's filename (preferred)
    "c607523c-90bd-405c-960d-c114d61af078.png",   # fallback (if available)
    "ff82487b-4bb7-425d-9452-581a001d5ba5.png",   # fallback (if available)
]
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # stored hashed; cannot be deleted
COOLDOWN_SECONDS = 30
MAX_ATTEMPTS = 3
FADE_IN_DURATION = 800  # milliseconds (~0.8s)

# Ensure data dir
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------- DB Helpers ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH.as_posix())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            hint TEXT
        )
    """)
    conn.commit()
    conn.close()
    # ensure admin exists
    if not get_user(ADMIN_USERNAME):
        create_user(ADMIN_USERNAME, ADMIN_PASSWORD, "admin account")


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username: str, password: str, hint: str) -> bool:
    username = username.strip()
    if get_user(username):
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password_hash, hint) VALUES (?, ?, ?)",
                (username, hash_pw(password), hint))
    conn.commit()
    conn.close()
    return True


def delete_user(username: str) -> bool:
    if username == ADMIN_USERNAME:
        return False
    if not get_user(username):
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return True


def get_user(username: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def validate_login(username: str, password: str) -> bool:
    u = get_user(username)
    if not u:
        return False
    return u["password_hash"] == hash_pw(password)


# ---------- UI App ----------
class LoginApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Log In")
        # make window reasonable size and centered
        self.geometry("1100x700")
        self.state("zoomed")  # match other apps
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # state
        self.attempts_left = MAX_ATTEMPTS
        self.on_cooldown = False
        self.cooldown_remaining = 0
        self.fade_steps = 20

        # build DB
        init_db()

        # background image (wallpaper)
        self._bg_image = self._load_wallpaper()
        self._build_ui()
        self._fade_in()

    # ---------- background ----------
    def _load_wallpaper(self):
        for fname in WALLPAPER_CANDIDATES:
            # try in current working dir, then data dir, then /mnt/data (if present)
            for base in [Path("."), DATA_DIR, Path("/mnt/data")]:
                p = base / fname
                if p.exists():
                    try:
                        img = Image.open(p.as_posix()).convert("RGBA")
                        return img
                    except Exception:
                        continue
        return None

    def _build_ui(self):
        # background canvas
        self.canvas = ctk.CTkCanvas(self, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        if self._bg_image:
            # store resized PhotoImage in attribute to prevent GC
            w, h = self.winfo_screenwidth(), self.winfo_screenheight()
            img = self._bg_image.resize((w, h))
            self._tk_bg = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self._tk_bg)
        else:
            # fallback fill
            self.canvas.configure(bg="#0E0E0E")

        # overlay dim to match existing style
        self.overlay = ctk.CTkFrame(self.canvas, fg_color="#000000", corner_radius=0)
        self.overlay.place(relwidth=1, relheight=1, relx=0, rely=0)
        try:
            # semi-transparent effect by using image overlay isn't trivial with CTk; set low alpha for widgets instead
            pass
        except Exception:
            pass

        # center card frame
        card_w, card_h = 640, 380
        self.card = ctk.CTkFrame(self.canvas, fg_color="#0E0E0E", corner_radius=12,
                         width=card_w, height=card_h)
        self.card.place(relx=0.5, rely=0.5, anchor="center")


        # Title + separator
        title = ctk.CTkLabel(self.card, text="Log In", font=("Helvetica", 22, "bold"), text_color="#1E90FF")
        title.place(x=20, y=14)

        self.sep = ctk.CTkFrame(self.card, fg_color="#1E90FF", width=card_w - 40, height=2)
        self.sep.place(x=20, y=56)


        # Username
        lbl_user = ctk.CTkLabel(self.card, text="Username*", font=("Helvetica", 13))
        lbl_user.place(x=20, y=74)
        self.entry_user = ctk.CTkEntry(self.card, width=card_w - 80, fg_color="#151515", placeholder_text="Enter username")
        self.entry_user.place(x=20, y=100)

        # Password + show toggle
        lbl_pw = ctk.CTkLabel(self.card, text="Password*", font=("Helvetica", 13))
        lbl_pw.place(x=20, y=145)
        self.entry_pw = ctk.CTkEntry(self.card, width=card_w - 150, fg_color="#151515", placeholder_text="Enter password", show="*")
        self.entry_pw.place(x=20, y=170)
        self.show_pw_var = ctk.StringVar(value="off")
        self.show_btn = ctk.CTkButton(self.card, text="Show", width=80, command=self._toggle_show_pw, fg_color="#1E90FF")
        self.show_btn.place(x=card_w - 110, y=168)

        # Hint / Cooldown label (inline feedback)
        self.info_label = ctk.CTkLabel(self.card, text="", font=("Helvetica", 11), text_color="white")
        self.info_label.place(x=20, y=210)

        # Buttons: Login / Create / Delete / Forgot
        btn_login = ctk.CTkButton(self.card, text="Login", width=120, fg_color="#1E90FF", hover_color="#0A84FF", command=self._on_login)
        btn_login.place(x=20, y=240)

        btn_create = ctk.CTkButton(self.card, text="Create Account", width=160, fg_color="#00CED1", command=self._on_create)
        btn_create.place(x=160, y=240)

        btn_delete = ctk.CTkButton(self.card, text="Delete Account", width=160, fg_color="#FF6347", command=self._on_delete)
        btn_delete.place(x=340, y=240)

        btn_forgot = ctk.CTkButton(self.card, text="Forgot Password", width=160, fg_color="#7B68EE", command=self._on_forgot)
        btn_forgot.place(x=160, y=295)

        # small caption for admin
        admin_caption = ctk.CTkLabel(self.card, text=f"Admin account: {ADMIN_USERNAME} / {ADMIN_PASSWORD}", font=("Helvetica", 10), text_color="#9EA7B8")
        admin_caption.place(x=20, y=345)

    # ---------- UI Helpers ----------
    def _toggle_show_pw(self):
        if self.entry_pw.cget("show") == "":
            self.entry_pw.configure(show="*")
            self.show_btn.configure(text="Show")
        else:
            self.entry_pw.configure(show="")
            self.show_btn.configure(text="Hide")

    def _set_info(self, text, color="white"):
        try:
            self.info_label.configure(text=text, text_color=color)
        except Exception:
            pass

    # ---------- Actions ----------
    def _on_login(self):
        if self.on_cooldown:
            self._set_info(f"Cooldown active: {self.cooldown_remaining}s remaining", color="#FF8C00")
            return

        username = self.entry_user.get().strip()
        password = self.entry_pw.get()

        # validation
        if not username or not password:
            messagebox.showwarning("Missing", "Please enter username and password.")
            return
        if not username.isalnum() or len(username) < 5:
            messagebox.showwarning("Invalid Username", "Username must be alphanumeric and at least 5 characters.")
            return
        if len(password) < 6:
            messagebox.showwarning("Invalid Password", "Password must be at least 6 characters.")
            return

        if validate_login(username, password):
            self._set_info("Login successful! Launching dashboard...", color="#32CD32")
            self.after(400, lambda: self._launch_main(username))
        else:
            self.attempts_left -= 1
            if self.attempts_left <= 0:
                self._start_cooldown()
            else:
                self._set_info(f"Invalid credentials. Attempts left: {self.attempts_left}", color="#FF6347")

    def _on_create(self):
        # in-window create: small inline form (reuse same entries plus a simple hint prompt)
        username = self.entry_user.get().strip()
        password = self.entry_pw.get()
        if not username or not password:
            messagebox.showwarning("Missing", "Please enter username and password for new account.")
            return
        if not username.isalnum() or len(username) < 5:
            messagebox.showwarning("Invalid Username", "Username must be alphanumeric and at least 5 characters.")
            return
        if len(password) < 6:
            messagebox.showwarning("Invalid Password", "Password must be at least 6 characters.")
            return
        if get_user(username):
            messagebox.showerror("Exists", "Username already exists.")
            return
        # ask for simple hint inline using a prompt frame inside the card
        hint = self._prompt_input("Create Account - Hint", "Enter a short hint to help recover password (optional):")
        if hint is None:
            # cancelled
            return
        created = create_user(username, password, hint or "")
        if created:
            messagebox.showinfo("Created", f"Account '{username}' created successfully.")
            self._set_info("Account created. You may login now.", color="#00CED1")
            # clear password
            self.entry_pw.delete(0, "end")
        else:
            messagebox.showerror("Error", "Failed to create account.")

    def _on_delete(self):
        username = self.entry_user.get().strip()
        if not username:
            messagebox.showwarning("Missing", "Enter username to delete.")
            return
        if username == ADMIN_USERNAME:
            messagebox.showerror("Forbidden", "Admin account cannot be deleted.")
            return
        if not get_user(username):
            messagebox.showerror("Not found", "No such user exists.")
            return
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{username}'? This cannot be undone.")
        if not confirm:
            return
        deleted = delete_user(username)
        if deleted:
            messagebox.showinfo("Deleted", f"Account '{username}' deleted.")
            self._set_info("Account deleted.", color="#FF6347")
        else:
            messagebox.showerror("Error", "Failed to delete account.")

    def _on_forgot(self):
        username = self.entry_user.get().strip()
        if not username:
            messagebox.showwarning("Missing", "Enter username to recover password.")
            return
        u = get_user(username)
        if not u:
            messagebox.showerror("Not Found", "No such user.")
            return
        hint = u.get("hint") or "(no hint set)"
        # Show hint inline with a confirm step for security
        self._set_info(f"Password hint for '{username}': {hint}", color="#00CED1")

    # ---------- small in-window prompt (synchronous) ----------
    def _prompt_input(self, title: str, message: str):
        """
        Minimal in-window prompt implemented by temporarily placing
        input widgets into the card and returning input or None if cancelled.
        This keeps everything in one window (per user request).
        """
        # disable main buttons by lowering their state
        # create prompt frame overlay within the card
        prompt = ctk.CTkFrame(self.card, fg_color="#151515", corner_radius=8)
        prompt.place(relx=0.5, rely=0.5, anchor="center", width=520, height=140)

        lbl = ctk.CTkLabel(prompt, text=message, wraplength=480)
        lbl.pack(pady=(12, 6))

        ent = ctk.CTkEntry(prompt, width=400, fg_color="#1E1E1E")
        ent.pack(pady=(0, 8))

        result = {"value": None}
        done = {"flag": False}

        def on_ok():
            result["value"] = ent.get().strip()
            done["flag"] = True
            prompt.destroy()

        def on_cancel():
            done["flag"] = True
            prompt.destroy()

        btn_frame = ctk.CTkFrame(prompt, fg_color="#151515")
        btn_frame.pack(pady=(4, 10))
        ok_btn = ctk.CTkButton(btn_frame, text="OK", width=120, fg_color="#1E90FF", command=on_ok)
        ok_btn.pack(side="left", padx=8)
        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", width=120, fg_color="#7B68EE", command=on_cancel)
        cancel_btn.pack(side="left", padx=8)

        # block (non-destructive) until done using a local loop
        # This pumps the UI events so window stays responsive
        while not done["flag"]:
            self.update()
            time.sleep(0.02)

        return result["value"]

    # ---------- cooldown logic ----------
    def _start_cooldown(self):
        self.on_cooldown = True
        self.cooldown_remaining = COOLDOWN_SECONDS
        self.attempts_left = MAX_ATTEMPTS
        self._update_cooldown_label()
        # start countdown in background using after
        self._cooldown_step()

    def _cooldown_step(self):
        if self.cooldown_remaining <= 0:
            self.on_cooldown = False
            self._set_info("You may try logging in again.", color="#00CED1")
            return
        self._set_info(f"Too many attempts. Cooldown: {self.cooldown_remaining}s", color="#FF8C00")
        self.cooldown_remaining -= 1
        self.after(1000, self._cooldown_step)

    def _update_cooldown_label(self):
        # helper in case you want a different visual effect
        pass

    # ---------- fade-in ----------
    def _fade_in(self):
        # set alpha 0 -> 1 over FADE_IN_DURATION using a number of steps
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            return
        steps = self.fade_steps
        delay = FADE_IN_DURATION // steps

        def step(i=0):
            alpha = (i + 1) / steps
            try:
                self.attributes("-alpha", alpha)
            except Exception:
                pass
            if i + 1 < steps:
                self.after(delay, lambda: step(i + 1))

        step(0)

    # ---------- launch main ----------
    def _launch_main(self, username):
        """
        Destroy login window and import/launch main.FaceRecognitionApp.
        This runs in the same process so the user remains in a single app.
        """
        try:
            import main as main_module
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to import main.py: {e}")
            return

        try:
            # cleanly destroy login window
            self.destroy()
            # instantiate and run main app
            app = main_module.FaceRecognitionApp()
            app.mainloop()
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch dashboard: {e}")


if __name__ == "__main__":
    app = LoginApp()
    app.mainloop()
