"""CustomTkinter GUI for InstaVideoSplitter."""

import logging
import os
import platform
import subprocess
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter
from PIL import Image

from .core import trim_video_to_parts
from .ffmpeg_config import get_ffmpeg_dir, set_ffmpeg_dir

customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("green")

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).parent.parent / "assets"


class VideoSplitterApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Video Trimmer for Instagram")
        self.geometry("900x500")
        self.file_path: str | None = None
        self.output_dir: str | None = None
        self.segment_duration: int = 60
        self.ffmpeg_dir: str = get_ffmpeg_dir()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(list(range(10)), weight=1)

        # ── Frames ────────────────────────────────────────────────────────────
        self.left_frame = customtkinter.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, rowspan=9, padx=10, pady=10, sticky="nsew")

        self.right_frame = customtkinter.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, rowspan=9, padx=10, pady=10, sticky="nsew")

        # ── Logo ──────────────────────────────────────────────────────────────
        try:
            icon = customtkinter.CTkImage(Image.open(_ASSETS_DIR / "icon.png"), size=(40, 40))
            self.logo = customtkinter.CTkLabel(self.left_frame, image=icon, text="")
            self.logo.grid(row=0, column=0, padx=10, pady=10)
        except Exception:
            pass

        # ── Left-panel controls ───────────────────────────────────────────────
        self.select_button = customtkinter.CTkButton(
            self.left_frame, text="Browse for Video", command=self.browse_video
        )
        self.select_button.grid(row=1, column=0, pady=5, padx=10, sticky="w")

        self.dir_button = customtkinter.CTkButton(
            self.left_frame, text="Select Output Directory", command=self.browse_output_dir
        )
        self.dir_button.grid(row=2, column=0, pady=5, padx=10, sticky="w")

        self.ffmpeg_button = customtkinter.CTkButton(
            self.left_frame, text="Select ffmpeg Folder", command=self.browse_ffmpeg
        )
        self.ffmpeg_button.grid(row=3, column=0, pady=5, padx=10, sticky="w")

        self.duration_menu = customtkinter.CTkComboBox(
            self.left_frame, values=["15", "30", "60", "90"], command=self.set_duration
        )
        self.duration_menu.set("60")
        self.duration_menu.grid(row=4, column=0, pady=5, padx=10, sticky="w")

        self.offset: float = 0.0
        self.offset_slider = customtkinter.CTkSlider(
            self.left_frame, from_=-5, to=5, command=self.set_offset
        )
        self.offset_slider.set(0)
        self.offset_slider.grid(row=5, column=0, pady=5, padx=10, sticky="we")

        self.offset_label = customtkinter.CTkLabel(self.left_frame, text="Offset: 0s")
        self.offset_label.grid(row=6, column=0, pady=5, padx=10, sticky="w")

        self.start_button = customtkinter.CTkButton(
            self.left_frame, text="Trim Video", command=self.start_trimming
        )
        self.start_button.grid(row=7, column=0, pady=10, padx=10, sticky="w")

        self.quit_button = customtkinter.CTkButton(
            self.left_frame, text="Close Program", command=self.destroy
        )
        self.quit_button.grid(row=8, column=0, pady=10, padx=10, sticky="w")

        self.theme_switch = customtkinter.CTkSwitch(
            self.left_frame, text="Dark Mode", command=self.toggle_theme
        )
        self.theme_switch.select()
        self.theme_switch.grid(row=9, column=0, padx=10, pady=10, sticky="w")

        # ── Right-panel widgets ───────────────────────────────────────────────
        self.thumbnail_label = customtkinter.CTkLabel(
            self.right_frame, text="Thumbnail preview will appear here"
        )
        self.thumbnail_label.grid(row=0, column=0, padx=10, pady=10)

        self.log_display = customtkinter.CTkTextbox(self.right_frame, width=400, height=80)
        self.log_display.grid(row=1, column=0, padx=10, pady=5)
        self.log_display.insert("0.0", "Waiting for file selection...")
        self.log_display.configure(state="disabled")

        self.progress = customtkinter.CTkProgressBar(self.right_frame)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.status_label = customtkinter.CTkLabel(self.right_frame, text="Ready", anchor="w")
        self.status_label.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

    # ── Event handlers ────────────────────────────────────────────────────────

    def set_duration(self, value: str) -> None:
        self.segment_duration = int(value)
        self._update_log()

    def set_offset(self, value: float) -> None:
        self.offset = float(value)
        self.offset_label.configure(text=f"Offset: {self.offset:+.1f}s")

    def browse_video(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv")]
        )
        if path:
            self.file_path = path
            self._update_log()
            self._show_thumbnail()

    def browse_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self._update_log()

    def browse_ffmpeg(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.ffmpeg_dir = path
            set_ffmpeg_dir(path)
            self._update_log()

    def toggle_theme(self) -> None:
        customtkinter.set_appearance_mode("dark" if self.theme_switch.get() else "light")

    # ── Trimming ──────────────────────────────────────────────────────────────

    def start_trimming(self) -> None:
        if not self.file_path:
            messagebox.showwarning("No File", "Please select a video file first.")
            return
        if not self.output_dir:
            self.output_dir = os.path.dirname(self.file_path)
            self._update_log()
        set_ffmpeg_dir(self.ffmpeg_dir)
        threading.Thread(target=self._run_trimming, daemon=True).start()

    def _run_trimming(self) -> None:
        try:
            self.progress.set(0)
            self.status_label.configure(text="Processing…")
            num_parts = trim_video_to_parts(
                self.file_path,
                output_dir=self.output_dir,
                progress_callback=self._update_progress,
                segment_duration=self.segment_duration,
                offset=self.offset,
                ask_allow_long_last_part=self._ask_allow_longer,
            )
            self.progress.set(1)
            self.status_label.configure(text=f"Done — {num_parts} parts.")
            messagebox.showinfo("Done", f"Trimmed into {num_parts} parts.")
            self._open_output_folder()
        except Exception as exc:
            self.status_label.configure(text="Error.")
            messagebox.showerror("Error", str(exc))
            logger.exception("Trimming failed")

    def _update_progress(self, completed: int, total: int) -> None:
        pct = completed / total
        self.progress.set(pct)
        self.status_label.configure(text=f"Progress: {int(pct * 100)}%")

    def _ask_allow_longer(self, length: float) -> bool:
        return messagebox.askyesno(
            "Allow longer last part?",
            f"The last segment will be {length:.1f}s. Keep it?",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_log(self) -> None:
        text = (
            f"Video:    {os.path.basename(self.file_path) if self.file_path else '—'}\n"
            f"Output:   {self.output_dir or '—'}\n"
            f"Segment:  {self.segment_duration}s\n"
            f"Offset:   {self.offset:+.1f}s\n"
            f"ffmpeg:   {self.ffmpeg_dir or 'auto'}"
        )
        self.log_display.configure(state="normal")
        self.log_display.delete("0.0", "end")
        self.log_display.insert("0.0", text)
        self.log_display.configure(state="disabled")

    def _show_thumbnail(self) -> None:
        try:
            import cv2
            from moviepy.editor import VideoFileClip

            clip = VideoFileClip(self.file_path)
            frame = clip.get_frame(0)
            clip.close()

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                cv2.imwrite(tmp_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                pil_img = Image.open(tmp_path)
                thumb = customtkinter.CTkImage(pil_img, size=(200, 120))
                self.thumbnail_label.configure(image=thumb, text="")
                self.thumbnail_label.image = thumb  # prevent GC
                pil_img.close()
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        except Exception as exc:
            self.thumbnail_label.configure(text=f"Preview unavailable: {exc}")
            logger.debug("Thumbnail error: %s", exc)

    def _open_output_folder(self) -> None:
        if not self.output_dir:
            return
        system = platform.system()
        if system == "Windows":
            os.startfile(self.output_dir)
        elif system == "Darwin":
            subprocess.run(["open", self.output_dir], check=False)
        else:
            subprocess.run(["xdg-open", self.output_dir], check=False)


def main() -> None:
    app = VideoSplitterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
