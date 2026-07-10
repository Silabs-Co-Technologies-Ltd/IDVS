"""Touch-friendly offline Tkinter kiosk shell."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from src.config.settings import AppSettings
from src.database.repository import Database
from src.ocr.pipeline import OCRService
from src.security.auth import AuthService
from src.verification.engine import PendingVerification, VerificationEngine


class KioskApp(tk.Tk):
    """Fullscreen kiosk UI; business rules remain in services and engines."""

    def __init__(self, settings: AppSettings, db: Database) -> None:
        super().__init__()
        self.settings = settings
        self.db = db
        self.ocr = OCRService(settings)
        self.engine = VerificationEngine(db, settings)
        self.auth = AuthService(db)
        self.title("NAUB Automated Student ID Card Verification System")
        self.configure(bg="#0f172a")
        self.protocol("WM_DELETE_WINDOW", self._blocked_close)
        self.bind("<Escape>", lambda _event: "break")
        self.bind("<Alt-F4>", lambda _event: "break")
        if settings.fullscreen_enabled:
            self.attributes("-fullscreen", True)
        self.resizable(False, False)
        self._home()

    def _home(self) -> None:
        self._clear()
        tk.Label(self, text="NAUB Student ID Verification", bg="#0f172a", fg="white", font=("Arial", 30, "bold")).pack(pady=48)
        for text, command in (("Upload Image", self._upload), ("Capture Webcam", self._capture), ("Administrator Login", self._admin_login)):
            tk.Button(self, text=text, command=command, font=("Arial", 20, "bold"), width=24, height=2, bg="#1d4ed8", fg="white", activebackground="#2563eb").pack(pady=14)

    def _upload(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if not path:
            return
        image = self.ocr.load_image(__import__("pathlib").Path(path))
        self._handle_ocr(self.ocr.run(image))

    def _capture(self) -> None:
        try:
            self._handle_ocr(self.ocr.run(self.ocr.capture_webcam()))
        except Exception as exc:  # GUI boundary reports operational errors to user
            messagebox.showerror("Camera Error", str(exc))

    def _handle_ocr(self, ocr_result) -> None:
        step = self.engine.begin(ocr_result)
        if isinstance(step, PendingVerification):
            answer = simpledialog.askstring("KBI Question", step.question.question, show="*") or ""
            result = self.engine.complete_kbi(step, answer)
        else:
            result = step
        self.db.log_verification(result)
        self._result_screen(result.success, result.reason)

    def _result_screen(self, success: bool, reason: str) -> None:
        self._clear()
        color = "#15803d" if success else "#b91c1c"
        text = "ACCESS GRANTED" if success else "ACCESS DENIED"
        tk.Label(self, text=text, bg=color, fg="white", font=("Arial", 42, "bold")).pack(expand=True, fill="both")
        tk.Label(self, text=reason, bg=color, fg="white", font=("Arial", 18)).pack(pady=24)
        self.after(4000, self._home)

    def _admin_login(self) -> None:
        username = simpledialog.askstring("Administrator Login", "Username") or ""
        password = simpledialog.askstring("Administrator Login", "Password", show="*") or ""
        if self.auth.login(username, password):
            if messagebox.askyesno("Admin", "Exit kiosk application?"):
                self.destroy()
        else:
            messagebox.showerror("Login Failed", "Invalid administrator credentials")

    def _blocked_close(self) -> None:
        messagebox.showwarning("Kiosk Mode", "Administrator authentication is required to exit.")

    def _clear(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()
