# attendance_face.py
"""
Simplified and stable version (OpenCV LBPH)
-------------------------------------------
✅ Always shows UI.
✅ Camera starts manually.
✅ Handles missing photos gracefully.
✅ Works even if cv2.face or webcam not found.
"""

import os
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
import customtkinter as ctk
from PIL import Image, ImageTk

from student_records import get_db_connection, PHOTOS_DIR


# ---------- Ensure attendance table ----------
def init_attendance_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            student_id TEXT,
            name TEXT,
            date TEXT,
            time TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()


init_attendance_db()


class TakeAttendanceFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#0E0E0E")
        self.parent = parent

        # -------- UI --------
        title = ctk.CTkLabel(self, text="FACE RECOGNITION ATTENDANCE",
                             font=("Helvetica", 20, "bold"),
                             text_color="#1E90FF")
        title.pack(pady=(20, 10))

        self.video_label = ctk.CTkLabel(self, text="Camera not started",
                                        width=640, height=480,
                                        fg_color="#151515", corner_radius=10)
        self.video_label.pack(pady=10)

        btn_frame = ctk.CTkFrame(self, fg_color="#151515")
        btn_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(btn_frame, text="▶ Start Camera", fg_color="#1E90FF", command=self.start_camera)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹ Stop Camera", fg_color="#FF6347", command=self.stop_camera)
        self.stop_btn.pack(side="left", padx=10)

        self.train_btn = ctk.CTkButton(btn_frame, text="🔄 Train Recognizer", fg_color="#32CD32", command=self.train_recognizer)
        self.train_btn.pack(side="left", padx=10)

        # Attendance Table
        self.tree_frame = ctk.CTkFrame(self, fg_color="#151515")
        self.tree_frame.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        cols = ["Student ID", "Name", "Date", "Time", "Status"]
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        # -------- Style Treeview for dark mode --------
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

        # -------- State --------
        self.cap = None
        self.running = False
        self.recognizer = None
        self.label_map = {}
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        # Fill today's attendance table
        self.populate_today_attendance()

    # -------- Train recognizer using DeepFace embeddings --------
    def train_recognizer(self):
        if getattr(self, "recognizer", None) == "deepface":
            messagebox.showinfo("Already Trained", "Recognizer is already trained.")
            return

        """
        Use DeepFace to compute embeddings for each student image once.
        Later, we'll compare face embeddings for faster and more reliable recognition.
        """
        try:
            from deepface import DeepFace
        except Exception as e:
            messagebox.showerror(
                "DeepFace Import Error",
                "DeepFace (or TensorFlow) failed to import.\nRun:\n\npip install deepface tf-keras\n\n"
                f"Details: {str(e)}"
            )
            self.recognizer = None
            return

        self.embeddings = []
        self.known_labels = []

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT student_id, student_name, photo_path FROM students")
        students = cur.fetchall()
        conn.close()

        loaded = 0
        for sid, name, path in students:
            if path and os.path.exists(path):
                try:
                    # Compute embedding once per image
                    embedding = DeepFace.represent(
                        img_path=path,
                        model_name="Facenet",
                        enforce_detection=False
                    )[0]["embedding"]
                    self.embeddings.append(np.array(embedding))
                    self.known_labels.append((sid, name))
                    loaded += 1
                except Exception as e:
                    print(f"Embedding error for {name}: {e}")

        if loaded == 0:
            messagebox.showwarning("No Photos", "No valid student photos found.")
            self.recognizer = None
            return

        messagebox.showinfo("Training Complete", f"Loaded {loaded} student embeddings.\nRecognition ready!")
        self.recognizer = "deepface"
        self._DeepFace = DeepFace  # store reference



    # -------- Start camera (non-blocking) --------
    def start_camera(self):
        import threading
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera Error", "Could not open webcam.")
            return
        self.running = True
        # run frame update in a separate thread to avoid UI freeze
        threading.Thread(target=self.update_frame, daemon=True).start()

    # -------- Stop camera --------
    def stop_camera(self):
        self.running = False

        # wait 80ms for update_frame thread to exit
        import time
        time.sleep(0.08)

        if self.cap and self.cap.isOpened():
            self.cap.release()

        self.cap = None
        self.video_label.configure(image=None, text="Camera stopped")


    # -------- Faster frame loop (real-time feel) --------
    def update_frame(self):
        import cv2, time, threading, numpy as np
        from PIL import Image, ImageTk
        from scipy.spatial.distance import cosine
        from deepface import DeepFace

        last_recognition_time = 0
        recognition_interval = 2.0  # seconds between DeepFace runs
        recognized_label = "..."

        def recognize_face_async(face_roi):
            """Run heavy DeepFace embedding match in background thread."""
            nonlocal recognized_label
            try:
                emb = DeepFace.represent(face_roi, model_name="Facenet", enforce_detection=False)[0]["embedding"]
                emb = np.array(emb)
                min_dist, best_idx = 1e6, -1
                for idx, known_emb in enumerate(self.embeddings):
                    dist = cosine(emb, known_emb)
                    if dist < min_dist:
                        min_dist, best_idx = dist, idx
                if min_dist < 0.35:
                    sid, name = self.known_labels[best_idx]
                    recognized_label = name
                    self.mark_attendance(sid, name)
                else:
                    recognized_label = "Unknown"
            except Exception as e:
                print("Async recognition error:", e)

        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

            now = time.time()
            for (x, y, w, h) in faces:
                roi = frame[y:y+h, x:x+w]
                color = (0, 255, 0) if recognized_label != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, recognized_label, (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                # run recognition asynchronously every few seconds
                if (now - last_recognition_time > recognition_interval and
                        getattr(self, "recognizer", None) == "deepface"):
                    last_recognition_time = now
                    threading.Thread(target=recognize_face_async, args=(roi.copy(),), daemon=True).start()

            # show frame quickly (non-blocking)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            if not self.running or not self.video_label.winfo_exists():
                break

            self.video_label.after(
                0, lambda imgtk=imgtk: self.video_label.configure(image=imgtk)
            )

            self.video_label.imgtk = imgtk

            time.sleep(0.03)  # ~33 fps (fast display)

        if self.cap:
            self.cap.release()


    # -------- Mark attendance --------
    def mark_attendance(self, student_id, name):
        date_today = datetime.now().strftime("%Y-%m-%d")
        time_now = datetime.now().strftime("%H:%M:%S")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM attendance_records WHERE student_id=? AND date=?", (student_id, date_today))
        exists = cur.fetchone()
        if not exists:
            cur.execute("INSERT INTO attendance_records VALUES (?, ?, ?, ?, ?)",
                        (student_id, name, date_today, time_now, "Present"))
            conn.commit()
            self.tree.insert("", "end", values=(student_id, name, date_today, time_now, "Present"))
        conn.close()

    # -------- Show today's attendance --------
    def populate_today_attendance(self):
        self.tree.delete(*self.tree.get_children())
        date_today = datetime.now().strftime("%Y-%m-%d")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM attendance_records WHERE date=?", (date_today,))
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", "end", values=(r["student_id"], r["name"], r["date"], r["time"], r["status"]))

    def destroy(self):
        self.stop_camera()
        super().destroy()
