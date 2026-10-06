#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EOP2MID Converter GUI
A modern graphical interface for converting EveryonePiano (.EOP) files to MIDI (.MID).
Features: Theme switching (Light/Dark), console output, and drag-and-drop support.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QTextEdit, QComboBox, QFrame,
        QProgressBar
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QThread, QUrl
    from PyQt6.QtGui import QPixmap, QFont, QTextCursor
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
except ImportError:
    print("PyQt6 is required. Install it with: pip install PyQt6 PyQt6-multimedia")
    sys.exit(1)

from eop_to_midi import convert_file


class ConversionWorker(QThread):
    """Worker thread for file conversion to prevent UI freezing."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, file_path, output_dir=None):
        super().__init__()
        self.file_path = file_path
        self.output_dir = output_dir

    def run(self):
        try:
            self.progress.emit(f"Converting: {Path(self.file_path).name}...\n")
            result = convert_file(self.file_path, self.output_dir)
            self.finished.emit(True, f"Successfully converted: {result}\n")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}\n")


class ThemeManager:
    """Manages light and dark themes."""

    LIGHT_THEME = {
        "bg_primary": "#FFFFFF",
        "bg_secondary": "#F5F5F5",
        "fg_primary": "#000000",
        "fg_secondary": "#555555",
        "accent": "#0078D4",
        "accent_hover": "#005A9E",
        "border": "#CCCCCC",
        "console_bg": "#FFFFFF",
        "console_fg": "#000000",
    }

    DARK_THEME = {
        "bg_primary": "#1E1E1E",
        "bg_secondary": "#2D2D2D",
        "fg_primary": "#FFFFFF",
        "fg_secondary": "#B0B0B0",
        "accent": "#0078D4",
        "accent_hover": "#005A9E",
        "border": "#3D3D3D",
        "console_bg": "#1E1E1E",
        "console_fg": "#FFFFFF",
    }

    THEMES = {
        "Light": LIGHT_THEME,
        "Dark": DARK_THEME,
    }

    @staticmethod
    def get_stylesheet(theme_dict):
        return f"""
            QMainWindow, QWidget {{
                background-color: {theme_dict['bg_primary']};
                color: {theme_dict['fg_primary']};
            }}

            QFrame {{
                background-color: {theme_dict['bg_secondary']};
                border: 1px solid {theme_dict['border']};
                border-radius: 8px;
            }}

            QPushButton {{
                background-color: {theme_dict['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }}

            QPushButton:hover {{
                background-color: {theme_dict['accent_hover']};
            }}

            QPushButton:pressed {{
                background-color: #004578;
            }}

            QTextEdit {{
                background-color: {theme_dict['console_bg']};
                color: {theme_dict['console_fg']};
                border: 1px solid {theme_dict['border']};
                border-radius: 6px;
                padding: 10px;
                font-family: Courier New;
                font-size: 11px;
            }}

            QComboBox {{
                background-color: {theme_dict['bg_secondary']};
                color: {theme_dict['fg_primary']};
                border: 1px solid {theme_dict['border']};
                border-radius: 6px;
                padding: 8px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {theme_dict['bg_secondary']};
                color: {theme_dict['fg_primary']};
                selection-background-color: {theme_dict['accent']};
            }}

            QLabel {{
                color: {theme_dict['fg_primary']};
            }}

            QProgressBar {{
                border: 1px solid {theme_dict['border']};
                border-radius: 6px;
                background-color: {theme_dict['bg_secondary']};
                text-align: center;
            }}

            QProgressBar::chunk {{
                background-color: {theme_dict['accent']};
                border-radius: 4px;
            }}
        """


class EOPConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EOP2MID Converter")
        self.setGeometry(100, 100, 900, 700)

        self.current_theme = "Light"
        self.config_file = Path.home() / ".eop2mid_config.json"
        self.load_config()

        # MP3 is the primary format. WAV is supported as an optional fallback.
        # When packaged with PyInstaller --onefile, bundled files are extracted
        # to sys._MEIPASS at runtime.  Looking only beside __file__ makes the
        # bundled MP3 invisible, which is why the previous build reported
        # "No music file found".  For a normal .py run, use the source folder.
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            music_dir = Path(sys._MEIPASS)
        else:
            music_dir = Path(__file__).resolve().parent

        self.music_candidates = [
            music_dir / "relaxing_music.mp3",
            music_dir / "relaxing_music.MP3",
            music_dir / "relaxing_music.wav",
            music_dir / "relaxing_music.WAV",
        ]
        self.music_candidates = [
            path for path in self.music_candidates if path.is_file()
        ]
        self.music_index = 0
        self.music_path = (
            self.music_candidates[self.music_index]
            if self.music_candidates else None
        )

        self.music_file_ok = False
        self.music_playing = False
        self.music_start_pending = False

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(getattr(self, "saved_volume", 0.3))

        # setSource() is asynchronous; decoder/backend failures arrive via
        # these signals instead of Python exceptions.
        self.media_player.errorOccurred.connect(self.on_media_error)
        self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)

        self.setup_ui()
        self.apply_theme(self.current_theme)
        self.setup_audio()

        self.worker = None

    def setup_audio(self):
        """Load the primary MP3, with WAV available as a real fallback."""
        if not self.music_candidates:
            self.music_file_ok = False
            self.music_btn.setEnabled(False)
            self.log_console(
                "No bundled music file was found. The build must include "
                "relaxing_music.mp3 (preferred) or relaxing_music.wav.\n"
            )
            return

        self.load_current_audio()

    def load_current_audio(self):
        self.music_path = self.music_candidates[self.music_index]
        self.media_player.stop()
        self.media_player.setSource(
            QUrl.fromLocalFile(str(self.music_path.resolve()))
        )
        self.music_file_ok = True
        self.music_playing = False
        self.music_start_pending = False
        self.music_btn.setEnabled(True)
        self.music_btn.setText("🎵 Play Music")
        self.log_console(
            f"Music file selected: {self.music_path.name} "
            f"({self.music_path.suffix.lower()[1:]}).\n"
        )
        self.statusBar().showMessage(f"Music ready: {self.music_path.name}")

    def try_next_audio_file(self):
        """Switch from a failed MP3 to an available WAV fallback, if present."""
        if self.music_index + 1 >= len(self.music_candidates):
            return False

        self.music_index += 1
        self.log_console(
            f"Trying audio fallback: "
            f"{self.music_candidates[self.music_index].name}\n"
        )
        self.load_current_audio()
        return True

    def on_media_error(self, error, error_string):
        """Report decoder failures and automatically try the optional WAV."""
        error_name = getattr(error, "name", str(error))
        message = error_string or "Unknown multimedia backend error"
        self.music_playing = False
        self.music_start_pending = False
        self.music_btn.setText("🎵 Play Music")
        self.log_console(
            f"Audio playback error ({error_name}): {message}\n"
        )

        if self.try_next_audio_file():
            self.log_console(
                "The previous audio format could not be decoded; "
                "the fallback file is ready.\n"
            )
            return

        self.statusBar().showMessage("Music failed to play")

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.music_playing = False
            self.music_start_pending = False
            self.music_btn.setText("🎵 Play Music")
            self.log_console(
                "The multimedia backend rejected the selected audio file.\n"
            )
            if not self.try_next_audio_file():
                self.statusBar().showMessage("Invalid/unsupported audio file")

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.music_playing = True
            self.music_start_pending = False
            self.music_btn.setText("⏸ Stop Music")
            self.log_console("▶ Music is actually playing.\n")
            self.statusBar().showMessage("Music playing")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            was_active = self.music_playing or self.music_start_pending
            self.music_playing = False
            self.music_start_pending = False
            self.music_btn.setText("🎵 Play Music")
            if was_active:
                self.statusBar().showMessage("Music stopped")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()

        logo_path = Path(__file__).parent / "converter.png"
        if logo_path.exists():
            logo = QLabel()
            pixmap = QPixmap(str(logo_path))
            pixmap = pixmap.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation)
            logo.setPixmap(pixmap)
            header_layout.addWidget(logo)

        title = QLabel("EOP2MID Converter")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()

        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.theme_combo.setMaximumWidth(120)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)

        self.music_btn = QPushButton("🎵 Play Music")
        self.music_btn.clicked.connect(self.toggle_music)
        self.music_btn.setMaximumWidth(150)
        theme_layout.addWidget(self.music_btn)

        header_layout.addLayout(theme_layout)
        main_layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(separator)

        content_layout = QHBoxLayout()

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)

        instructions = QLabel(
            "Select EOP Files to Convert\n\n"
            "1. Click 'Select Input Files' to choose .EOP files\n"
            "2. Click 'Select Output Folder' to set MIDI destination\n"
            "3. Click 'Convert' to start\n"
            "4. Monitor progress in the console"
        )
        instructions_font = QFont()
        instructions_font.setPointSize(10)
        instructions.setFont(instructions_font)
        instructions.setStyleSheet("padding: 15px; border-radius: 6px;")
        left_layout.addWidget(instructions)

        left_layout.addWidget(QLabel("📥 Input Files:"))
        self.file_list_label = QLabel("No files selected")
        self.file_list_label.setWordWrap(True)
        left_layout.addWidget(self.file_list_label)

        left_layout.addWidget(QLabel("📤 Output Folder:"))
        self.output_folder_label = QLabel("Not selected (default: same as input)")
        self.output_folder_label.setWordWrap(True)
        left_layout.addWidget(self.output_folder_label)

        button_layout = QVBoxLayout()

        self.select_input_btn = QPushButton("📁 Select Input Files")
        self.select_input_btn.clicked.connect(self.select_files)
        button_layout.addWidget(self.select_input_btn)

        self.select_output_btn = QPushButton("📂 Select Output Folder")
        self.select_output_btn.clicked.connect(self.select_output_folder)
        button_layout.addWidget(self.select_output_btn)

        self.convert_btn = QPushButton("▶ Convert")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        button_layout.addWidget(self.convert_btn)

        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.clicked.connect(self.clear_files)
        button_layout.addWidget(self.clear_btn)

        left_layout.addLayout(button_layout)
        left_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        left_layout.addWidget(QLabel("Progress:"))
        left_layout.addWidget(self.progress_bar)

        content_layout.addWidget(left_panel, 1)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        console_label = QLabel("Console Output")
        console_font = QFont()
        console_font.setBold(True)
        console_label.setFont(console_font)
        right_layout.addWidget(console_label)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        right_layout.addWidget(self.console)

        console_button_layout = QHBoxLayout()
        clear_console_btn = QPushButton("Clear Console")
        clear_console_btn.clicked.connect(self.clear_console)
        console_button_layout.addWidget(clear_console_btn)
        console_button_layout.addStretch()
        right_layout.addLayout(console_button_layout)

        content_layout.addWidget(right_panel, 1)
        main_layout.addLayout(content_layout)

        self.statusBar().showMessage("Ready")

        self.selected_files = []
        self.output_folder = None

    def toggle_music(self):
        if not self.music_file_ok:
            self.statusBar().showMessage("Music not available")
            self.log_console("Music not available.\n")
            return

        if self.music_playing or self.music_start_pending:
            self.media_player.stop()
            self.music_playing = False
            self.music_start_pending = False
            self.music_btn.setText("🎵 Play Music")
            self.log_console("⏹ Stopped playing the music.\n")
            self.statusBar().showMessage("Music stopped")
            return

        if self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)

        self.music_start_pending = True
        self.media_player.play()
        self.log_console(f"▶ Starting {self.music_path.name}...\n")
        self.statusBar().showMessage("Starting music...")

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select EOP Files",
            "",
            "EOP Files (*.eop);;All Files (*)"
        )

        if files:
            self.selected_files = files
            self.update_file_list_display()
            self.convert_btn.setEnabled(True)
            self.statusBar().showMessage(f"{len(files)} file(s) selected")
            self.log_console(f"Selected {len(files)} file(s) for conversion\n")

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            ""
        )
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(folder)
            self.statusBar().showMessage("Output folder selected")
            self.log_console(f"Output folder selected: {folder}\n")

    def update_file_list_display(self):
        if not self.selected_files:
            self.file_list_label.setText("No files selected")
        else:
            file_names = "\n".join(Path(f).name for f in self.selected_files)
            self.file_list_label.setText(file_names)

    def clear_files(self):
        self.selected_files = []
        self.output_folder = None
        self.update_file_list_display()
        self.output_folder_label.setText("Not selected (default: same as input)")
        self.convert_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("File selection cleared")
        self.log_console("File selection cleared\n")

    def start_conversion(self):
        if not self.selected_files:
            self.log_console("No files selected for conversion\n")
            return

        self.convert_btn.setEnabled(False)
        self.select_input_btn.setEnabled(False)
        self.select_output_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self.log_console(f"\n{'='*60}\n")
        self.log_console(f"Starting conversion at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_console(f"{'='*60}\n\n")

        total_files = len(self.selected_files)
        for index, file_path in enumerate(self.selected_files):
            self.worker = ConversionWorker(file_path, self.output_folder)
            self.worker.progress.connect(self.log_console)
            self.worker.finished.connect(lambda success, msg: self.on_conversion_finished(success, msg))
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()
            self.worker.wait()

            progress = int(((index + 1) / total_files) * 100)
            self.progress_bar.setValue(progress)

        self.log_console(f"\n{'='*60}\n")
        self.log_console(f"Conversion completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_console(f"{'='*60}\n")

        self.convert_btn.setEnabled(True)
        self.select_input_btn.setEnabled(True)
        self.select_output_btn.setEnabled(True)
        self.statusBar().showMessage("Conversion completed")

    def on_conversion_finished(self, success, message):
        self.log_console(message)

    def log_console(self, message):
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(message)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def clear_console(self):
        self.console.clear()
        self.log_console("Console cleared\n")

    def on_theme_changed(self, theme_name):
        self.current_theme = theme_name
        self.apply_theme(theme_name)
        self.save_config()

    def apply_theme(self, theme_name):
        theme = ThemeManager.THEMES.get(theme_name, ThemeManager.LIGHT_THEME)
        stylesheet = ThemeManager.get_stylesheet(theme)
        self.setStyleSheet(stylesheet)

    def save_config(self):
        config = {
            "theme": self.current_theme,
            "volume": self.audio_output.volume(),
        }
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Could not save config: {e}")

    def load_config(self):
        self.saved_volume = 0.3
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.current_theme = config.get("theme", "Light")
                    self.saved_volume = max(
                        0.0, min(1.0, float(config.get("volume", 0.3)))
                    )
            except Exception as e:
                print(f"Could not load config: {e}")

    def closeEvent(self, event):
        self.media_player.stop()
        self.save_config()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EOP2MID Converter")
    app.setApplicationVersion("2.0")
    window = EOPConverterGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()