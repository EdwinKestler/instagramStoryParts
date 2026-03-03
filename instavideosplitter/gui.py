"""CustomTkinter GUI for InstaVideoSplitter."""

import logging
import os
import platform
import queue
import subprocess
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter
from PIL import Image

from .constants import MAX_WORKERS
from .core import trim_video_to_parts
from .ffmpeg_config import get_ffmpeg_dir, nvenc_available, set_ffmpeg_dir, set_use_cuda

customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("green")

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).parent.parent / "assets"


# ── Live-log handler ──────────────────────────────────────────────────────────

class _GUILogHandler(logging.Handler):
    """Append log records to a CTkTextbox safely from any thread."""

    def __init__(self, textbox: customtkinter.CTkTextbox) -> None:
        super().__init__()
        self._box = textbox
        self.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record) + "\n"
        # after() is safe to call from any thread
        self._box.after(0, self._append, msg)

    def _append(self, msg: str) -> None:
        self._box.configure(state="normal")
        self._box.insert("end", msg)
        self._box.see("end")
        self._box.configure(state="disabled")


# ── Application ───────────────────────────────────────────────────────────────

class VideoSplitterApp(customtkinter.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Video Trimmer for Instagram")
        self.geometry("940x640")
        self.minsize(720, 520)

        # Fonts — must be created after super().__init__() initialises Tk
        self._font_section = customtkinter.CTkFont(size=10, weight="bold")
        self._font_mono = customtkinter.CTkFont(family="Consolas", size=12)
        self._font_trim = customtkinter.CTkFont(size=14, weight="bold")

        # State
        self.file_path: str | None = None
        self.output_dir: str | None = None
        self.segment_duration: int = 60
        self.offset: float = 0.0
        self.workers: int = MAX_WORKERS
        self.ffmpeg_dir: str = get_ffmpeg_dir()
        self._trimming: bool = False
        self._video_meta: str = ""

        # Main grid: left panel | right panel
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = customtkinter.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.right_frame = customtkinter.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)  # log expands

        self._build_left_panel()
        self._build_right_panel()

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_left_panel(self) -> None:
        row = 0

        # Logo
        try:
            icon = customtkinter.CTkImage(Image.open(_ASSETS_DIR / "icon.png"), size=(40, 40))
            customtkinter.CTkLabel(self.left_frame, image=icon, text="").grid(
                row=row, column=0, padx=10, pady=(14, 6)
            )
        except Exception:
            pass
        row += 1

        # ── FILES ─────────────────────────────────────────────────────────────
        customtkinter.CTkLabel(
            self.left_frame, text="FILES",
            font=self._font_section, text_color=("gray40", "gray60"), anchor="w",
        ).grid(row=row, column=0, padx=14, pady=(8, 2), sticky="w")
        row += 1

        for text, cmd in [
            ("Browse for Video", self.browse_video),
            ("Select Output Directory", self.browse_output_dir),
            ("Select ffmpeg Folder", self.browse_ffmpeg),
        ]:
            customtkinter.CTkButton(
                self.left_frame, text=text, command=cmd
            ).grid(row=row, column=0, pady=4, padx=12, sticky="ew")
            row += 1

        # ── SETTINGS ──────────────────────────────────────────────────────────
        customtkinter.CTkLabel(
            self.left_frame, text="SETTINGS",
            font=self._font_section, text_color=("gray40", "gray60"), anchor="w",
        ).grid(row=row, column=0, padx=14, pady=(14, 2), sticky="w")
        row += 1

        customtkinter.CTkLabel(
            self.left_frame, text="Segment Duration (s)", anchor="w"
        ).grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
        row += 1

        self.duration_menu = customtkinter.CTkComboBox(
            self.left_frame, values=["15", "30", "60", "90"], command=self.set_duration
        )
        self.duration_menu.set("60")
        self.duration_menu.grid(row=row, column=0, pady=3, padx=12, sticky="ew")
        row += 1

        self.workers_label = customtkinter.CTkLabel(
            self.left_frame, text=f"Workers: {self.workers}", anchor="w"
        )
        self.workers_label.grid(row=row, column=0, padx=14, pady=(10, 0), sticky="w")
        row += 1

        self.workers_slider = customtkinter.CTkSlider(
            self.left_frame, from_=1, to=8, number_of_steps=7, command=self.set_workers
        )
        self.workers_slider.set(self.workers)
        self.workers_slider.grid(row=row, column=0, pady=3, padx=12, sticky="ew")
        row += 1

        self.offset_label = customtkinter.CTkLabel(
            self.left_frame, text="Offset: 0s", anchor="w"
        )
        self.offset_label.grid(row=row, column=0, padx=14, pady=(10, 0), sticky="w")
        row += 1

        self.offset_slider = customtkinter.CTkSlider(
            self.left_frame, from_=-5, to=5, command=self.set_offset
        )
        self.offset_slider.set(0)
        self.offset_slider.grid(row=row, column=0, pady=3, padx=12, sticky="ew")
        row += 1

        self.cuda_checkbox = customtkinter.CTkCheckBox(
            self.left_frame, text="Use CUDA / NVENC", command=self._toggle_cuda,
        )
        self.cuda_checkbox.grid(row=row, column=0, padx=14, pady=(10, 0), sticky="w")
        row += 1

        # ── ACTIONS ───────────────────────────────────────────────────────────
        self.start_button = customtkinter.CTkButton(
            self.left_frame,
            text="Trim Video",
            command=self.start_trimming,
            height=44,
            font=self._font_trim,
        )
        self.start_button.grid(row=row, column=0, pady=(16, 4), padx=12, sticky="ew")
        row += 1

        customtkinter.CTkButton(
            self.left_frame,
            text="Close",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
        ).grid(row=row, column=0, pady=4, padx=12, sticky="ew")
        row += 1

        self.theme_switch = customtkinter.CTkSwitch(
            self.left_frame, text="Dark Mode", command=self.toggle_theme
        )
        self.theme_switch.select()
        self.theme_switch.grid(row=row, column=0, padx=12, pady=(10, 14), sticky="w")

    def _build_right_panel(self) -> None:
        # Thumbnail — wrapped in a tinted frame so the preview area is always visible
        thumb_frame = customtkinter.CTkFrame(
            self.right_frame, fg_color=("gray85", "gray20"), corner_radius=8
        )
        thumb_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        thumb_frame.grid_columnconfigure(0, weight=1)

        self.thumbnail_label = customtkinter.CTkLabel(
            thumb_frame,
            text="Thumbnail preview will appear here",
            height=140,
            text_color=("gray50", "gray60"),
        )
        self.thumbnail_label.grid(row=0, column=0, padx=8, pady=8)

        # Live log — monospaced font for technical output
        self.log_display = customtkinter.CTkTextbox(
            self.right_frame, width=440, height=200, wrap="word",
            font=self._font_mono,
        )
        self.log_display.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
        self.log_display.insert("0.0", "Waiting for file selection…\n")
        self.log_display.configure(state="disabled")

        # Progress bar
        self.progress = customtkinter.CTkProgressBar(self.right_frame)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=12, pady=6, sticky="ew")

        # Status label
        self.status_label = customtkinter.CTkLabel(
            self.right_frame, text="Ready", anchor="w"
        )
        self.status_label.grid(row=3, column=0, padx=12, pady=2, sticky="ew")

        # Open output folder button — disabled until a trim succeeds
        self.open_output_btn = customtkinter.CTkButton(
            self.right_frame,
            text="Open Output Folder",
            command=self._open_output_folder,
            state="disabled",
        )
        self.open_output_btn.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="ew")

    # ── Event handlers ────────────────────────────────────────────────────────

    def set_duration(self, value: str) -> None:
        self.segment_duration = int(value)
        self._update_log()

    def set_workers(self, value: float) -> None:
        self.workers = max(1, int(round(value)))
        self.workers_label.configure(text=f"Workers: {self.workers}")
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
            self._video_meta = ""
            self._update_log()
            # Thumbnail and metadata both offloaded — keeps UI responsive
            self._show_thumbnail()
            threading.Thread(target=self._fetch_video_metadata, daemon=True).start()

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

    def _toggle_cuda(self) -> None:
        enabled = bool(self.cuda_checkbox.get())
        if enabled and not nvenc_available():
            messagebox.showwarning(
                "NVENC unavailable",
                "h264_nvenc was not found in the resolved ffmpeg binary.\n\n"
                "Install an NVENC-enabled ffmpeg build, or point to one via "
                "'Select ffmpeg Folder'.",
            )
            self.cuda_checkbox.deselect()
            return
        set_use_cuda(enabled)
        self._update_log()

    # ── Trimming ──────────────────────────────────────────────────────────────

    def start_trimming(self) -> None:
        if not self.file_path:
            messagebox.showwarning("No File", "Please select a video file first.")
            return
        if not self.output_dir:
            self.output_dir = os.path.dirname(self.file_path)
            self._update_log()
        set_ffmpeg_dir(self.ffmpeg_dir)

        # Disable button on main thread before spawning worker
        self.start_button.configure(state="disabled", text="Trimming…")
        self._trimming = True
        self._clear_log(f"Starting — {os.path.basename(self.file_path)}\n")

        threading.Thread(target=self._run_trimming, daemon=True).start()

    def _run_trimming(self) -> None:
        # Attach live-log handler for the duration of the trim
        pkg_logger = logging.getLogger("instavideosplitter")
        handler = _GUILogHandler(self.log_display)
        handler.setLevel(logging.INFO)
        pkg_logger.addHandler(handler)

        try:
            self.after(0, self.progress.set, 0)
            self.after(0, lambda: self.status_label.configure(text="Processing…"))

            num_parts = trim_video_to_parts(
                self.file_path,
                output_dir=self.output_dir,
                progress_callback=self._update_progress,
                segment_duration=self.segment_duration,
                offset=self.offset,
                workers=self.workers,
                ask_allow_long_last_part=self._ask_allow_longer,
            )

            self.after(0, self.progress.set, 1)
            self.after(0, lambda n=num_parts: self.status_label.configure(
                text=f"Done — {n} parts."
            ))
            self.after(0, lambda n=num_parts: messagebox.showinfo(
                "Done", f"Trimmed into {n} parts."
            ))
            self.after(0, self._enable_open_output_btn)
            self.after(0, self._open_output_folder)

        except Exception as exc:
            self.after(0, lambda: self.status_label.configure(text="Error."))
            self.after(0, lambda e=exc: messagebox.showerror("Error", str(e)))
            logger.exception("Trimming failed")

        finally:
            pkg_logger.removeHandler(handler)
            self._trimming = False
            self.after(0, lambda: self.start_button.configure(
                state="normal", text="Trim Video"
            ))

    def _update_progress(self, completed: int, total: int) -> None:
        pct = completed / total
        self.after(0, self.progress.set, pct)
        self.after(0, lambda p=pct: self.status_label.configure(
            text=f"Progress: {int(p * 100)}%"
        ))

    def _ask_allow_longer(self, length: float) -> bool:
        """Show a dialog from any thread via a queue round-trip to the main thread."""
        result: queue.Queue[bool] = queue.Queue()

        def _ask() -> None:
            ans = messagebox.askyesno(
                "Allow longer last part?",
                f"The last segment will be {length:.1f}s. Keep it?",
            )
            result.put(ans)

        self.after(0, _ask)
        return result.get()  # blocks the worker thread until the user answers

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_log(self) -> None:
        if self._trimming:
            return  # don't overwrite live output mid-trim
        fname = os.path.basename(self.file_path) if self.file_path else "—"
        meta = f"  {self._video_meta}" if self._video_meta else ""
        cuda_state = "h264_nvenc" if self.cuda_checkbox.get() else "libx264 (CPU)"
        text = (
            f"Video:    {fname}{meta}\n"
            f"Output:   {self.output_dir or '—'}\n"
            f"Segment:  {self.segment_duration}s  ·  Workers: {self.workers}\n"
            f"Offset:   {self.offset:+.1f}s\n"
            f"Encoder:  {cuda_state}\n"
            f"ffmpeg:   {self.ffmpeg_dir or 'auto'}\n"
        )
        self._set_log(text)

    def _set_log(self, text: str) -> None:
        self.log_display.configure(state="normal")
        self.log_display.delete("0.0", "end")
        self.log_display.insert("0.0", text)
        self.log_display.configure(state="disabled")

    def _clear_log(self, initial: str = "") -> None:
        self.log_display.configure(state="normal")
        self.log_display.delete("0.0", "end")
        if initial:
            self.log_display.insert("0.0", initial)
        self.log_display.configure(state="disabled")

    def _fetch_video_metadata(self) -> None:
        """Probe the selected video in the background and refresh the log."""
        from .ffprobe_utils import run_ffprobe

        data = run_ffprobe(["-show_streams", "-show_format"], self.file_path)
        if not data:
            return

        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        if not video_stream:
            return

        width = video_stream.get("width", "?")
        height = video_stream.get("height", "?")
        fps_raw = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = fps_raw.split("/")
            fps = f"{int(num) / int(den):.2f}"
        except (ValueError, ZeroDivisionError):
            fps = "?"

        duration_s = float(data.get("format", {}).get("duration", 0))
        m, s = divmod(int(duration_s), 60)
        h, m = divmod(m, 60)
        duration = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        self._video_meta = f"({width}×{height}  {fps}fps  {duration})"
        self.after(0, self._update_log)

    def _show_thumbnail(self) -> None:
        threading.Thread(target=self._load_thumbnail, daemon=True).start()

    def _load_thumbnail(self) -> None:
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
                thumb = customtkinter.CTkImage(pil_img, size=(220, 130))
                pil_img.close()
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            self.after(0, lambda t=thumb: self._set_thumbnail(t))
        except Exception as exc:
            self.after(
                0,
                lambda e=exc: self.thumbnail_label.configure(
                    text=f"Preview unavailable: {e}", image=None
                ),
            )
            logger.debug("Thumbnail error: %s", exc)

    def _set_thumbnail(self, thumb: customtkinter.CTkImage) -> None:
        self.thumbnail_label.configure(image=thumb, text="")
        self.thumbnail_label.image = thumb  # keep reference — prevents GC

    def _enable_open_output_btn(self) -> None:
        self.open_output_btn.configure(state="normal")

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
