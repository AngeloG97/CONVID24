#!/usr/bin/env python3

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from threading import Thread
import os
import time
import subprocess
import re

# Import backend functions
from video_converter.converter import (
    convert_file,
    batch_convert,
    build_ffmpeg_command,
    VIDEO_EXTENSIONS,
)


class VideoConverterGUI:
    def __init__(self, master):
        self.master = master
        master.title("CONVID24")
        master.geometry("1200x800")
        master.configure(bg="#f0f0f0")

        # Fonts
        self.large_font = ("Arial", 12)
        self.header_font = ("Arial", 16, "bold")
        self.button_font = ("Arial", 11, "bold")

        # File tracking
        self.selected_files = []
        self.file_progress_vars = {}
        self.file_progress_bars = {}
        self.file_status_labels = {}
        self.file_percent_labels = {}

        # Conversion control
        self.conversion_paused = False
        self.conversion_cancelled = False
        self.current_process = None
        self.conversion_thread = None

        # Build UI
        self.setup_ui()
        self.setup_close_protocol()


    # FFmpeg conversion with pause/cancel support
    def convert_file_with_control(self, input_file, output_file, progress_callback=None):
        input_file = Path(input_file)
        output_file = Path(output_file)

        if output_file.exists():
            print(f"Skipping {input_file}, output already exists.")
            return

        cmd = build_ffmpeg_command(input_file, output_file)

        process = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, universal_newlines=True
        )
        self.current_process = process

        if progress_callback:
            duration = None
            for line in process.stderr:
                if self.conversion_cancelled:
                    process.terminate()
                    break

                while self.conversion_paused and not self.conversion_cancelled:
                    time.sleep(0.5)

                if self.conversion_cancelled:
                    process.terminate()
                    break

                # Parse duration
                if "Duration" in line and duration is None:
                    match = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", line)
                    if match:
                        h, m, s, ms = map(int, match.groups())
                        duration = h * 3600 + m * 60 + s + ms / 100.0

                # Parse progress
                elif "time=" in line and duration:
                    match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
                    if match:
                        h, m, s, ms = map(int, match.groups())
                        elapsed = h * 3600 + m * 60 + s + ms / 100.0
                        percent = min(elapsed / duration * 100, 100)
                        progress_callback(percent)

        process.wait()
        self.current_process = None

        if process.returncode != 0 and not self.conversion_cancelled:
            print(f"FFmpeg failed for {input_file}")
        elif not self.conversion_cancelled and progress_callback:
            progress_callback(100)


    # GUI setup
    def setup_ui(self):
        main_frame = tk.Frame(self.master, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header_label = tk.Label(
            main_frame,
            text="Convert Videos to mp4",
            font=self.header_font,
            bg="#f0f0f0",
            fg="#2c3e50",
        )
        header_label.pack(pady=(0, 20))

        # Instructions
        instructions = tk.Label(
            main_frame,
            text="Select video files or folders with videos you wish to convert to mp4.",
            font=self.large_font,
            bg="#f0f0f0",
            fg="#34495e",
        )
        instructions.pack(pady=(0, 20))

        # Buttons: select files, select folder, clear
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(pady=(0, 20))

        tk.Button(
            button_frame,
            text="📁 Select Files",
            font=self.button_font,
            width=20,
            height=2,
            bg="#3498db",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.select_files,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            button_frame,
            text="📂 Select Folder",
            font=self.button_font,
            width=20,
            height=2,
            bg="#2ecc71",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.select_folder,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            button_frame,
            text="🗑️ Clear Selection",
            font=self.button_font,
            width=20,
            height=2,
            bg="#e74c3c",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.clear_selection,
        ).pack(side=tk.LEFT)

        # Files display with scrollable canvas
        files_frame = tk.LabelFrame(
            main_frame,
            text="Selected Videos",
            font=self.large_font,
            bg="#f0f0f0",
            fg="#2c3e50",
        )
        files_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.files_canvas = tk.Canvas(files_frame, bg="white", height=200)
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_canvas.yview)
        self.scrollable_frame = tk.Frame(self.files_canvas, bg="white")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.files_canvas.configure(scrollregion=self.files_canvas.bbox("all")),
        )

        self.files_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.files_canvas.configure(yscrollcommand=scrollbar.set)
        self.files_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Overall progress
        progress_frame = tk.LabelFrame(
            main_frame,
            text="Overall Progress",
            font=self.large_font,
            bg="#f0f0f0",
            fg="#2c3e50",
        )
        progress_frame.pack(fill=tk.X, pady=(0, 20))

        self.overall_progress_var = tk.DoubleVar()
        ttk.Progressbar(
            progress_frame,
            variable=self.overall_progress_var,
            maximum=100,
            length=600,
            style="TProgressbar",
        ).pack(pady=10, padx=10)

        self.overall_percent_label = tk.Label(
            progress_frame,
            text="0%",
            font=self.large_font,
            bg="#f0f0f0",
            fg="#2c3e50",
        )
        self.overall_percent_label.pack(pady=(0, 10))

        self.status_label = tk.Label(
            progress_frame,
            text="Ready to convert",
            font=self.large_font,
            bg="#f0f0f0",
            fg="#27ae60",
        )
        self.status_label.pack(pady=(0, 10))

        # Control buttons: start, pause, cancel
        control_frame = tk.Frame(main_frame, bg="#f0f0f0")
        control_frame.pack(pady=10)

        self.convert_btn = tk.Button(
            control_frame,
            text="🎬 START CONVERSION",
            font=("Arial", 14, "bold"),
            width=25,
            height=2,
            bg="#f39c12",
            fg="white",
            relief="flat",
            cursor="hand2",
            state="disabled",
            command=self.start_conversion,
        )
        self.convert_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.pause_btn = tk.Button(
            control_frame,
            text="⏸️ PAUSE",
            font=("Arial", 12, "bold"),
            width=15,
            height=2,
            bg="#f1c40f",
            fg="white",
            relief="flat",
            cursor="hand2",
            state="disabled",
            command=self.pause_conversion,
        )
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.cancel_btn = tk.Button(
            control_frame,
            text="⏹️ CANCEL",
            font=("Arial", 12, "bold"),
            width=15,
            height=2,
            bg="#e74c3c",
            fg="white",
            relief="flat",
            cursor="hand2",
            state="disabled",
            command=self.cancel_conversion,
        )
        self.cancel_btn.pack(side=tk.LEFT)

        # Style for progress bars
        style = ttk.Style()
        style.configure(
            "TProgressbar",
            background="#3498db",
            troughcolor="#ecf0f1",
            borderwidth=1,
            lightcolor="#3498db",
            darkcolor="#3498db",
        )


    # Window close protocol
    def setup_close_protocol(self):
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)


    def on_closing(self):
        if self.conversion_thread and self.conversion_thread.is_alive():
            result = messagebox.askyesno(
                "Cancel Conversion?",
                "A conversion is in progress. Cancel and exit?",
            )
            if result:
                self.conversion_cancelled = True
                if self.current_process:
                    try:
                        self.current_process.terminate()
                    except Exception:
                        pass
                self.master.after(500, self.master.destroy)
        else:
            self.master.destroy()


    # File management
    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[
                ("Video files", " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS)),
                ("All files", "*.*"),
            ],
        )
        for file in files:
            if file not in self.selected_files:
                self.selected_files.append(file)
        self.update_file_display()


    def select_folder(self):
        folder = filedialog.askdirectory(title="Select a folder containing video files")
        if folder:
            folder_path = Path(folder)
            video_files = [
                str(f)
                for f in folder_path.rglob("*")
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
            ]
            for file in video_files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
            self.update_file_display()
            if video_files:
                messagebox.showinfo("Files Found", f"Found {len(video_files)} video files.")
            else:
                messagebox.showwarning("No Videos", "No supported video files found.")


    def clear_selection(self):
        if self.conversion_thread and self.conversion_thread.is_alive():
            messagebox.showwarning(
                "Conversion Active",
                "Cannot clear selection while conversion is running.",
            )
            return
        self.selected_files.clear()
        self.file_progress_vars.clear()
        self.file_progress_bars.clear()
        self.file_status_labels.clear()
        self.file_percent_labels.clear()
        self.update_file_display()


    def remove_single_file(self, file_path):
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self.file_progress_vars.pop(file_path, None)
            self.file_progress_bars.pop(file_path, None)
            self.file_status_labels.pop(file_path, None)
            self.file_percent_labels.pop(file_path, None)
            self.update_file_display()


    def open_output_folder(self, file_path):
        path = Path(file_path).with_suffix(".mp4")
        folder = path.parent
        if folder.exists():
            import subprocess, platform
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{folder}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        else:
            messagebox.showwarning("Folder not found", "Output folder does not exist yet.")


    # File display and progress
    def update_file_display(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.selected_files:
            tk.Label(
                self.scrollable_frame,
                text="No files selected. Use the buttons above to select video files.",
                font=self.large_font,
                bg="white",
                fg="#95a5a6",
            ).pack(pady=20)
            self.convert_btn.config(state="disabled")
            return

        for i, file_path in enumerate(self.selected_files):
            file_frame = tk.Frame(self.scrollable_frame, bg="white", relief="solid", borderwidth=1)
            file_frame.pack(fill=tk.X, padx=5, pady=2)

            file_info_frame = tk.Frame(file_frame, bg="white")
            file_info_frame.pack(fill=tk.X, padx=10, pady=5)

            # File size (leftmost)
            try:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                size_label = tk.Label(
                    file_info_frame,
                    text=f"{size_mb:.1f} MB",
                    font=("Arial", 10),
                    bg="white",
                    fg="#7f8c8d",
                )
                size_label.pack(side=tk.LEFT, padx=(0, 10))
            except Exception:
                pass

            filename = os.path.basename(file_path)
            tk.Label(
                file_info_frame,
                text=f"{i+1}. {filename}",
                font=self.large_font,
                bg="white",
                fg="#2c3e50",
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Remove button (rightmost)
            remove_btn = tk.Button(
                file_info_frame,
                text="✕",
                font=("Arial", 10, "bold"),
                width=2,
                height=1,
                bg="#e74c3c",
                fg="white",
                relief="flat",
                cursor="hand2",
                command=lambda fp=file_path: self.remove_single_file(fp)
            )
            remove_btn.pack(side=tk.RIGHT)

            # Open folder button (middle)
            open_btn = tk.Button(
                file_info_frame,
                text="📂",
                font=("Arial", 10, "bold"),
                width=2,
                height=1,
                bg="#3498db",
                fg="white",
                relief="flat",
                cursor="hand2",
                command=lambda fp=file_path: self.open_output_folder(fp)
            )
            open_btn.pack(side=tk.RIGHT, padx=(5, 5))

            # Progress container
            progress_container = tk.Frame(file_frame, bg="white")
            progress_container.pack(fill=tk.X, pady=(0, 5), padx=10)

            progress_var = tk.DoubleVar()
            ttk.Progressbar(
                progress_container,
                variable=progress_var,
                maximum=100,
                length=350,
                style="TProgressbar",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

            percent_label = tk.Label(
                progress_container,
                text="0%",
                font=("Arial", 10),
                bg="white",
                fg="#2c3e50",
                width=5
            )
            percent_label.pack(side=tk.LEFT, padx=(5, 0))

            status_label = tk.Label(
                progress_container,
                text="",
                font=("Arial", 12, "bold"),
                bg="white",
                fg="#27ae60",
            )

            # Store references
            self.file_progress_vars[file_path] = progress_var
            self.file_progress_bars[file_path] = progress_var  # Progressbar object
            self.file_status_labels[file_path] = status_label
            self.file_percent_labels[file_path] = percent_label

        self.status_label.config(text=f"{len(self.selected_files)} files ready.")
        self.convert_btn.config(state="normal")
        self.scrollable_frame.update_idletasks()
        self.files_canvas.configure(scrollregion=self.files_canvas.bbox("all"))


    def update_file_progress(self, file_path, percent):
        if file_path in self.file_progress_vars:
            self.file_progress_vars[file_path].set(percent)
            self.file_percent_labels[file_path].config(text=f"{percent:.1f}%")

            if percent >= 100:
                self.file_progress_bars[file_path].pack_forget()
                self.file_percent_labels[file_path].pack_forget()
                self.file_status_labels[file_path].config(text="✅ Done!")
                self.file_status_labels[file_path].pack(side=tk.LEFT, padx=(10, 0))

            self.master.update_idletasks()


    def update_overall_progress(self, percent):
        self.overall_progress_var.set(percent)
        self.overall_percent_label.config(text=f"{percent:.1f}%")
        self.master.update_idletasks()


    # Conversion controls
    def start_conversion(self):
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please select files to convert first.")
            return

        self.conversion_paused = False
        self.conversion_cancelled = False

        self.convert_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text="⏸️ PAUSE")
        self.cancel_btn.config(state="normal")

        self.status_label.config(text="Converting files...", fg="#e67e22")
        self.conversion_thread = Thread(target=self.process_conversion, daemon=True)
        self.conversion_thread.start()


    def pause_conversion(self):
        if self.conversion_paused:
            self.conversion_paused = False
            self.pause_btn.config(text="⏸️ PAUSE")
            self.status_label.config(text="Conversion resumed...", fg="#e67e22")
        else:
            self.conversion_paused = True
            self.pause_btn.config(text="▶️ RESUME")
            self.status_label.config(text="Paused. Click Resume to continue.", fg="#f39c12")


    def cancel_conversion(self):
        result = messagebox.askyesno("Cancel Conversion", "Cancel conversion?")
        if result:
            self.conversion_cancelled = True
            self.conversion_paused = False
            if self.current_process:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass
            self.convert_btn.config(state="normal")
            self.pause_btn.config(state="disabled", text="⏸️ PAUSE")
            self.cancel_btn.config(state="disabled")
            self.status_label.config(text="Conversion cancelled.", fg="#e74c3c")


    # Conversion loop
    def process_conversion(self):
        total_files = len(self.selected_files)
        converted_count = 0

        for i, file_path in enumerate(self.selected_files, start=1):
            if self.conversion_cancelled:
                break

            while self.conversion_paused and not self.conversion_cancelled:
                time.sleep(0.5)

            if self.conversion_cancelled:
                break

            path = Path(file_path)
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                output_file = path.with_suffix(".mp4")
                self.master.after(0, lambda n=path.name, i=i: self.status_label.config(
                    text=f"Converting {i}/{total_files}: {n}"
                ))

                def progress_callback(percent):
                    if self.conversion_cancelled:
                        return
                    self.master.after(0, lambda: self.update_file_progress(file_path, percent))
                    overall_percent = (converted_count + percent / 100) / total_files * 100
                    self.master.after(0, lambda: self.update_overall_progress(overall_percent))

                try:
                    self.convert_file_with_control(path, output_file, progress_callback)
                    if not self.conversion_cancelled:
                        self.master.after(0, lambda: self.update_file_progress(file_path, 100))
                        converted_count += 1
                except Exception as e:
                    if not self.conversion_cancelled:
                        print(f"Error converting {file_path}: {e}")
                        converted_count += 1

        if not self.conversion_cancelled:
            self.master.after(0, lambda: self.update_overall_progress(100))
            self.master.after(
                0,
                lambda: self.status_label.config(
                    text=f"Done! {converted_count}/{total_files} files processed.", fg="#27ae60"
                ),
            )
            self.master.after(
                0,
                lambda: messagebox.showinfo(
                    "Conversion Complete",
                    f"Successfully processed {converted_count}/{total_files} files."
                ),
            )

        self.master.after(0, lambda: self.convert_btn.config(state="normal"))
        self.master.after(0, lambda: self.pause_btn.config(state="disabled", text="⏸️ PAUSE"))
        self.master.after(0, lambda: self.cancel_btn.config(state="disabled"))
        self.current_process = None


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterGUI(root)
    root.mainloop()
