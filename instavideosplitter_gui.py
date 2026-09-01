# instavideosplitter_gui.py
import customtkinter
from tkinter import filedialog, messagebox
from instavideosplitter import trim_video_to_parts
from ffmpeg_config import set_ffmpeg_dir, get_ffmpeg_path, get_ffmpeg_dir
from io import BytesIO
import os
import threading
import subprocess
import platform
from PIL import Image

customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("green")

class VideoSplitterApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Video Trimmer for Instagram")
        self.geometry("900x500")
        self.file_path = None
        self.output_dir = None
        self.segment_duration = 60
        self.ffmpeg_dir = get_ffmpeg_dir()
        self.trimming_thread = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), weight=1)

        # Frames
        self.left_frame = customtkinter.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, rowspan=9, padx=10, pady=10, sticky="nsew")

        self.right_frame = customtkinter.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, rowspan=9, padx=10, pady=10, sticky="nsew")

        # Logo
        try:
            image = customtkinter.CTkImage(Image.open("icon.png"), size=(40, 40))
            self.logo = customtkinter.CTkLabel(self.left_frame, image=image, text="")
            self.logo.grid(row=0, column=0, padx=10, pady=10)
        except (FileNotFoundError, OSError):
            pass

        # Buttons
        self.select_button = customtkinter.CTkButton(self.left_frame, text="Browse for Video", command=self.browse_video)
        self.select_button.grid(row=1, column=0, pady=5, padx=10, sticky="w")

        self.dir_button = customtkinter.CTkButton(self.left_frame, text="Select Output Directory", command=self.browse_output_dir)
        self.dir_button.grid(row=2, column=0, pady=5, padx=10, sticky="w")

        self.ffmpeg_button = customtkinter.CTkButton(self.left_frame, text="Select ffmpeg Folder", command=self.browse_ffmpeg)
        self.ffmpeg_button.grid(row=3, column=0, pady=5, padx=10, sticky="w")

        self.duration_menu = customtkinter.CTkComboBox(self.left_frame, values=["15", "30", "60", "90"], command=self.set_duration)
        self.duration_menu.set("60")
        self.duration_menu.grid(row=4, column=0, pady=5, padx=10, sticky="w")

        self.offset = 0.0
        self.offset_slider = customtkinter.CTkSlider(self.left_frame, from_=-5, to=5, command=self.set_offset)
        self.offset_slider.set(0)
        self.offset_slider.grid(row=5, column=0, pady=5, padx=10, sticky="we")

        self.offset_label = customtkinter.CTkLabel(self.left_frame, text="Offset: 0s")
        self.offset_label.grid(row=6, column=0, pady=5, padx=10, sticky="w")

        self.start_button = customtkinter.CTkButton(self.left_frame, text="Trim Video", command=self.start_trimming)
        self.start_button.grid(row=7, column=0, pady=10, padx=10, sticky="w")

        self.quit_button = customtkinter.CTkButton(self.left_frame, text="Close Program", command=self.quit_app)
        self.quit_button.grid(row=8, column=0, pady=10, padx=10, sticky="w")

        self.theme_switch = customtkinter.CTkSwitch(self.left_frame, text="Dark Mode", command=self.toggle_theme)
        self.theme_switch.select()
        self.theme_switch.grid(row=9, column=0, padx=10, pady=10, sticky="w")

        # Thumbnail Preview
        self.thumbnail_label = customtkinter.CTkLabel(self.right_frame, text="Thumbnail preview will appear here")
        self.thumbnail_label.grid(row=0, column=0, padx=10, pady=10)

        # Info Display
        self.log_display = customtkinter.CTkTextbox(self.right_frame, width=400, height=80)
        self.log_display.grid(row=1, column=0, padx=10, pady=5)
        self.log_display.insert("0.0", "Waiting for file selection...")
        self.log_display.configure(state="disabled")

        # Progress Bar
        self.progress = customtkinter.CTkProgressBar(self.right_frame)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        # Status Bar
        self.status_label = customtkinter.CTkLabel(self.right_frame, text="Ready", anchor="w")
        self.status_label.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

    def set_duration(self, value):
        self.segment_duration = int(value)
        self.update_log()

    def set_offset(self, value):
        self.offset = float(value)
        self.offset_label.configure(text=f"Offset: {self.offset:+.1f}s")

    def browse_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv")])
        if path:
            self.file_path = path
            self.update_log()
            self.show_thumbnail()

    def browse_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self.update_log()

    def browse_ffmpeg(self):
        path = filedialog.askdirectory()
        if path:
            try:
                set_ffmpeg_dir(path)
            except FileNotFoundError as exc:
                messagebox.showerror("Invalid FFmpeg folder", str(exc))
            else:
                self.ffmpeg_dir = path
                self.update_log()

    def update_log(self):
        self.log_display.configure(state="normal")
        self.log_display.delete("0.0", "end")
        log_text = (
            f"Video: {os.path.basename(self.file_path) if self.file_path else 'None'}\n"
            f"Output: {self.output_dir if self.output_dir else 'None'}\n"
            f"Segment Duration: {self.segment_duration} seconds\n"
            f"Offset: {self.offset:+.1f}s\n"
            f"ffmpeg dir: {self.ffmpeg_dir if self.ffmpeg_dir else 'Default'}"
        )
        self.log_display.insert("0.0", log_text)
        self.log_display.configure(state="disabled")

    def start_trimming(self):
        if not self.file_path:
            messagebox.showwarning("No File", "Please select a video file first.")
            return

        if not self.output_dir:
            self.output_dir = os.path.dirname(self.file_path)
            self.update_log()

        if self.trimming_thread and self.trimming_thread.is_alive():
            return

        self.start_button.configure(state="disabled")
        self.trimming_thread = threading.Thread(target=self.run_trimming, daemon=True)
        self.trimming_thread.start()

    def run_trimming(self):
        try:
            self.after(0, self._mark_processing)
            completed_parts = trim_video_to_parts(
                self.file_path,
                self.output_dir,
                self.update_progress,
                self.segment_duration,
                offset=self.offset,
                ask_allow_long_last_part=self.ask_allow_longer
            )
            self.after(0, self._finish_success, completed_parts)
        except Exception as e:
            self.after(0, self._finish_error, str(e))
        finally:
            self.trimming_thread = None

    def _mark_processing(self):
        self.progress.set(0)
        self.status_label.configure(text="Processing...")

    def _finish_success(self, completed_parts):
        self.progress.set(1)
        self.status_label.configure(text=f"Done: Trimmed into {completed_parts} parts.")
        self.start_button.configure(state="normal")
        messagebox.showinfo("Success", f"Trimmed into {completed_parts} parts.")
        self.open_output_folder()

    def _finish_error(self, message):
        self.status_label.configure(text="Error occurred.")
        self.start_button.configure(state="normal")
        messagebox.showerror("Error", message)

    def update_progress(self, completed, total):
        self.after(0, self._apply_progress, completed, total)

    def _apply_progress(self, completed, total):
        percent = completed / total
        self.progress.set(percent)
        self.status_label.configure(text=f"Progress: {int(percent * 100)}%")

    def open_output_folder(self):
        if platform.system() == "Windows":
            os.startfile(self.output_dir)
        elif platform.system() == "Darwin":
            subprocess.run(["open", self.output_dir])
        else:
            subprocess.run(["xdg-open", self.output_dir])

    def show_thumbnail(self):
        try:
            result = subprocess.run(
                [
                    get_ffmpeg_path(), "-hide_banner", "-loglevel", "error",
                    "-ss", "0", "-i", self.file_path,
                    "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1",
                ],
                check=True,
                capture_output=True,
            )
            with Image.open(BytesIO(result.stdout)) as image:
                pil_img = image.copy()
            thumb_image = customtkinter.CTkImage(pil_img, size=(200, 120))
            self.thumbnail_label.configure(image=thumb_image, text="")
            self.thumbnail_label.image = thumb_image
        except Exception as e:
            self.thumbnail_label.configure(text=f"Thumbnail error: {str(e)}")

    def ask_allow_longer(self, length):
        completed = threading.Event()
        answer = {"value": False}

        def ask_on_ui_thread():
            answer["value"] = messagebox.askyesno(
                "Allow longer last part?",
                f"The last part will be {length:.1f}s. Allow this length?",
            )
            completed.set()

        self.after(0, ask_on_ui_thread)
        completed.wait()
        return answer["value"]

    def quit_app(self):
        self.destroy()

    def toggle_theme(self):
        mode = "dark" if self.theme_switch.get() else "light"
        customtkinter.set_appearance_mode(mode)

def main():
    VideoSplitterApp().mainloop()


if __name__ == "__main__":
    main()

