import sys
import os
# Add Tools directory to PATH before importing yt_dlp
TOOLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Tools')
os.environ["PATH"] += os.pathsep + TOOLS_PATH
import threading
import yt_dlp
import requests
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QFileDialog, QHBoxLayout, QVBoxLayout, QMenuBar, QMessageBox, QCheckBox,
    QProgressBar, QFrame, QGridLayout, QSizePolicy, QScrollArea, QToolButton,
    QDialog
)
from PyQt6.QtGui import QIcon, QPixmap, QFont, QAction
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent
import json
import subprocess

class DownloadRow(QWidget):
    update_progress_signal = pyqtSignal(int, str, str, str, str)
    update_status_signal = pyqtSignal(str, str)
    retry_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(object)

    def __init__(self, thumb_pixmap, title, fmt, res_or_bitrate, time_started, parent=None):
        super().__init__(parent)
        self.main_app = parent
        self.setFixedHeight(110)
        
        # Internal status tracking
        self.current_status = "Queued"
        self.current_color = "#FFD600"
        
        # Main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        
        # The Card Container
        self.card = QFrame()
        self.card.setObjectName("DownloadCard")
        self.card.setStyleSheet("""
            #DownloadCard {
                background-color: #2b2e33;
                border-radius: 12px;
                border: 1px solid #3e4247;
            }
            #DownloadCard:hover {
                background-color: #32363b;
                border: 1px solid #50555c;
            }
        """)
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(15)
        
        # Thumbnail (Section 1)
        self.thumb_label = QLabel()
        if thumb_pixmap:
            self.thumb_label.setPixmap(thumb_pixmap.scaled(110, 62, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.thumb_label.setFixedSize(110, 62)
            self.thumb_label.setStyleSheet("background-color: #1e2023; border-radius: 6px;")
        card_layout.addWidget(self.thumb_label)
        
        # Info & Progress (Section 2 - Middle)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # Title and Resolution
        title_row = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
        self.title_label.setMaximumHeight(45) # Increased to fit 2 lines comfortably
        title_row.addWidget(self.title_label)
        
        self.res_label = QLabel(f"[{res_or_bitrate}]")
        self.res_label.setStyleSheet("color: #aaa; font-size: 11px;")
        title_row.addWidget(self.res_label)
        title_row.addStretch()
        
        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet("font-weight: bold; color: #FFD600;")
        title_row.addWidget(self.percent_label)
        info_layout.addLayout(title_row)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e2023;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #FFD600;
                border-radius: 3px;
            }
        """)
        info_layout.addWidget(self.progress)
        
        # Stats Row (Speed, Size, ETA, Status)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(15)
        
        self.status_label = QLabel("Queued")
        self.status_label.setStyleSheet("color: #FFD600; font-size: 12px; font-weight: bold;")
        stats_row.addWidget(self.status_label)
        
        self.speed_label = QLabel("0 KB/s")
        self.speed_label.setStyleSheet("color: #aaa; font-size: 11px;")
        stats_row.addWidget(self.speed_label)
        
        self.size_label = QLabel("0 MB / 0 MB")
        self.size_label.setStyleSheet("color: #aaa; font-size: 11px;")
        stats_row.addWidget(self.size_label)
        
        self.eta_label = QLabel("ETA: -")
        self.eta_label.setStyleSheet("color: #aaa; font-size: 11px;")
        stats_row.addWidget(self.eta_label)
        
        stats_row.addStretch()
        
        self.time_label = QLabel(time_started)
        self.time_label.setStyleSheet("color: #666; font-size: 10px;")
        stats_row.addWidget(self.time_label)
        
        info_layout.addLayout(stats_row)
        card_layout.addLayout(info_layout, stretch=1)
        
        # Action Buttons (Section 3 - Right)
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        
        self.open_btn = QToolButton()
        self.open_btn.setIcon(QIcon(os.path.join(icon_dir, 'folder_gray.svg')))
        self.open_btn.setToolTip("Open Folder")
        self.open_btn.setFixedSize(32, 32)
        self.open_btn.setEnabled(False)
        
        self.retry_btn = QToolButton()
        self.retry_btn.setIcon(QIcon(os.path.join(icon_dir, 'retry_gray.svg')))
        self.retry_btn.setToolTip("Retry")
        self.retry_btn.setFixedSize(32, 32)
        self.retry_btn.setEnabled(False)

        self.delete_btn = QToolButton()
        self.delete_btn.setIcon(QIcon(os.path.join(icon_dir, 'cancel_gray.svg')))
        self.delete_btn.setToolTip("Delete")
        self.delete_btn.setFixedSize(32, 32)
        
        buttons_layout.addWidget(self.open_btn)
        buttons_layout.addWidget(self.retry_btn)
        buttons_layout.addWidget(self.delete_btn)
        card_layout.addLayout(buttons_layout)
        
        main_layout.addWidget(self.card)
        self.setLayout(main_layout)

        # Apply initial theme
        self.apply_theme(self.main_app.theme_switch.isChecked())

        # Signals and Events
        self.update_progress_signal.connect(self.update_progress)
        self.update_status_signal.connect(self.update_status)
        self.delete_btn.clicked.connect(self.delete_download)
        self.retry_btn.clicked.connect(self.retry_download)
        self.open_btn.clicked.connect(self.open_folder)
        self.cancel_event = threading.Event()
        self.download_path = None
        
        # Install event filter for hover icons
        self.delete_btn.installEventFilter(self)
        self.retry_btn.installEventFilter(self)
        self.open_btn.installEventFilter(self)

    def apply_theme(self, is_dark):
        if is_dark:
            card_bg = "#2b2e33"
            card_hover = "#32363b"
            card_border = "#3e4247"
            text_color = "#ffffff"
            subtext_color = "#aaa"
            progress_bg = "#1e2023"
            btn_hover = "#444"
        else:
            card_bg = "#ffffff"
            card_hover = "#f9f9f9"
            card_border = "#dddddd"
            text_color = "#333333"
            subtext_color = "#666"
            progress_bg = "#eeeeee"
            btn_hover = "#eee"

        self.card.setStyleSheet(f"""
            #DownloadCard {{
                background-color: {card_bg};
                border-radius: 12px;
                border: 1px solid {card_border};
            }}
            #DownloadCard:hover {{
                background-color: {card_hover};
            }}
        """)
        
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {text_color}; background: transparent;")
        self.res_label.setStyleSheet(f"color: {subtext_color}; font-size: 11px; background: transparent;")
        self.speed_label.setStyleSheet(f"color: {subtext_color}; font-size: 11px; background: transparent;")
        self.size_label.setStyleSheet(f"color: {subtext_color}; font-size: 11px; background: transparent;")
        self.eta_label.setStyleSheet(f"color: {subtext_color}; font-size: 11px; background: transparent;")
        self.time_label.setStyleSheet(f"color: {subtext_color}; font-size: 10px; background: transparent;")
        self.percent_label.setStyleSheet(f"font-weight: bold; color: #FFD600; background: transparent;")
        
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {progress_bg};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: #FFD600;
                border-radius: 3px;
            }}
        """)
        
        btn_style = "QToolButton { border: none; background: transparent; border-radius: 4px; }"
        self.open_btn.setStyleSheet(btn_style + f" QToolButton:hover {{ background: {btn_hover}; border: 1px solid #00E676; }}")
        self.retry_btn.setStyleSheet(btn_style + f" QToolButton:hover {{ background: {btn_hover}; border: 1px solid #FFD600; }}")
        self.delete_btn.setStyleSheet(btn_style + f" QToolButton:hover {{ background: {btn_hover}; border: 1px solid #FF5252; }}")
        
        # Re-apply status color which is dynamic
        self.update_status(self.current_status, self.current_color)

    def update_progress(self, percent, percent_text, speed_str, size_str, eta_str):
        if self.current_status == "Complete":
            return
            
        if speed_str.startswith("Speed: "):
            speed_str = speed_str.replace("Speed: ", "")
        self.progress.setValue(percent)
        self.percent_label.setText(percent_text)
        self.speed_label.setText(speed_str)
        self.size_label.setText(size_str)
        self.eta_label.setText(eta_str)
        
        # Only switch to 'Downloading' if we are in a starting state
        if self.current_status in ["Queued", "Retrying...", ""]:
            self.update_status("Downloading", "#FFD600")

    def update_status(self, status, color="#FFD600"):
        print(f"Status Change: {self.current_status} -> {status}")
        self.current_status = status
        self.current_color = color
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; background: transparent;")
        
        # Adjust other labels based on status
        if status == "Complete":
            self.speed_label.setText("")
            self.eta_label.setText("")
            self.progress.hide()
            self.percent_label.hide()
            self.open_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.retry_btn.setEnabled(True)
            
            # Schedule final size check in the UI thread
            QTimer.singleShot(1000, self.final_size_check)
        elif status in ["Canceled", "Error"]:
            self.speed_label.setText("")
            self.eta_label.setText("")
            self.open_btn.setEnabled(False)
            self.retry_btn.setEnabled(True)
        elif status in ["Downloading", "Merging", "Queued", "Retrying..."]:
            self.progress.show()
            self.percent_label.show()
            self.open_btn.setEnabled(False)
            self.retry_btn.setEnabled(False)

    def final_size_check(self):
        print(f"final_size_check started for: {self.title_label.text()}")
        try:
            filename = None
            if hasattr(self, 'final_download_info'):
                # Try _filename first
                filename = self.final_download_info.get('_filename')
                if not filename or not os.path.exists(filename):
                    # Try requested_downloads
                    req = self.final_download_info.get('requested_downloads')
                    if req and len(req) > 0:
                        filename = req[0].get('filepath')
            
            if filename and os.path.exists(filename):
                self.download_path = filename
            
            if self.download_path and os.path.exists(self.download_path):
                size_bytes = os.path.getsize(self.download_path)
                if size_bytes > 1024 * 1024 * 1024:
                    size_str = f"{size_bytes / (1024*1024*1024):.2f} GB"
                else:
                    size_str = f"{size_bytes / (1024*1024):.2f} MB"
                self.size_label.setText(f"Size: {size_str}")
                print(f"final_size_check: Successfully set size to {size_str}")
            else:
                print("final_size_check: Could not find final file on disk.")
        except Exception as e:
            print(f"Error in final_size_check: {e}")

    def eventFilter(self, obj, event):
        import os
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        is_dark = self.main_app.theme_switch.isChecked()
        suffix = 'white.svg' if is_dark else 'gray.svg'
        
        if event.type() == QEvent.Type.Enter:
            if obj == self.open_btn:
                self.open_btn.setIcon(QIcon(os.path.join(icon_dir, f'folder_{suffix}')))
            elif obj == self.retry_btn:
                self.retry_btn.setIcon(QIcon(os.path.join(icon_dir, f'retry_{suffix}')))
            elif obj == self.delete_btn:
                self.delete_btn.setIcon(QIcon(os.path.join(icon_dir, f'cancel_{suffix}')))
        elif event.type() == QEvent.Type.Leave:
            if obj == self.open_btn:
                self.open_btn.setIcon(QIcon(os.path.join(icon_dir, 'folder_gray.svg')))
            elif obj == self.retry_btn:
                self.retry_btn.setIcon(QIcon(os.path.join(icon_dir, 'retry_gray.svg')))
            elif obj == self.delete_btn:
                self.delete_btn.setIcon(QIcon(os.path.join(icon_dir, 'cancel_gray.svg')))
        return super().eventFilter(obj, event)

    def delete_download(self):
        print("Delete button clicked")
        # If active, cancel first
        if self.current_status in ["Downloading", "Merging", "Queued", "Retrying..."]:
            self.cancel_event.set()
            
        # Optional: Actually delete the file if it exists? 
        # For now, let's just remove from UI to be safe.
        self.remove_requested.emit(self)

    def retry_download(self):
        print(f"DownloadRow: Retry button clicked for {self.title_label.text()}")
        self.update_status("Retrying...", "#FFD600")
        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.retry_btn.setEnabled(False)
        self.cancel_event.clear()
        print("DownloadRow: Emitting retry_requested signal")
        self.retry_requested.emit(self)

    def open_folder(self):
        if self.download_path and os.path.exists(self.download_path):
            folder = os.path.dirname(self.download_path)
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        else:
            QMessageBox.information(self, "Info", "File not found yet.")

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 200)
        
        layout = QVBoxLayout(self)
        
        # Download Folder Section
        folder_label = QLabel("Download Folder:")
        layout.addWidget(folder_label)
        
        folder_layout = QHBoxLayout()
        self.folder_entry = QLineEdit(self.main_app.download_folder)
        folder_layout.addWidget(self.folder_entry)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_folder)
        self.main_app.set_button_style(self.browse_btn)
        folder_layout.addWidget(self.browse_btn)
        layout.addLayout(folder_layout)
        
        layout.addSpacing(10)
        
        # Theme Section
        self.theme_switch = QCheckBox("Dark Mode")
        self.theme_switch.setChecked(self.main_app.theme_switch.isChecked())
        self.theme_switch.stateChanged.connect(self.toggle_mode)
        layout.addWidget(self.theme_switch)
        
        layout.addStretch()
        
        # Close Button
        self.close_btn = QPushButton("Done")
        self.close_btn.clicked.connect(self.accept)
        self.main_app.set_button_style(self.close_btn)
        layout.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.main_app.download_folder)
        if folder:
            self.main_app.download_folder = folder
            self.folder_entry.setText(folder)
            self.main_app.save_download_folder(folder)

    def toggle_mode(self):
        self.main_app.theme_switch.setChecked(self.theme_switch.isChecked())
        # The parent's toggle_mode will handle the rest via the signal connection

class GuidesDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("User Guides")
        self.setFixedSize(550, 450)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 10, 0)
        scroll_layout.setSpacing(15)
        
        self.titles = []
        self.descs = []
        
        # Main Header
        header = QLabel("How to Use YTV Downloader")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFD600;")
        scroll_layout.addWidget(header)
        
        # Guide 1
        t1 = QLabel("1. Downloading a Video or Audio")
        d1 = QLabel(
            "• Copy the URL of the YouTube video from your web browser.\n"
            "• Paste the link into the URL input box at the top.\n"
            "• Select the format (e.g., MP4 for Video, MP3/M4A for Audio).\n"
            "• Click the 'Download' button.\n"
            "• Track progress, speed, size, and remaining time in the download cards list below."
        )
        self.titles.append(t1)
        self.descs.append(d1)
        
        # Guide 2
        t2 = QLabel("2. Download Directory & Appearance")
        d2 = QLabel(
            "• Click 'Settings' in the top-left menu bar.\n"
            "• Click 'Browse' to set the folder where downloads will be saved.\n"
            "• Toggle the 'Dark Mode' checkbox to switch application themes."
        )
        self.titles.append(t2)
        self.descs.append(d2)
        
        # Guide 3
        t3 = QLabel("3. Common Questions & Troubleshooting")
        d3 = QLabel(
            "• **Status: Merging...**: High-resolution video downloads (1080p+) download video and audio separately, then merge them using FFmpeg. This takes a brief moment.\n"
            "• **Status: Error**: Make sure your internet is active and that the video is not private, region-blocked, or age-restricted.\n"
            "• **Cancel/Retry**: Use the control buttons on the right side of the download card to open the folder, retry a failed download, or remove it."
        )
        self.titles.append(t3)
        self.descs.append(d3)
        
        for t, d in zip(self.titles, self.descs):
            d.setWordWrap(True)
            scroll_layout.addWidget(t)
            scroll_layout.addWidget(d)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Close Button
        close_btn = QPushButton("Done")
        close_btn.clicked.connect(self.accept)
        parent.set_button_style(close_btn)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.apply_theme(parent.theme_switch.isChecked())
        
    def apply_theme(self, is_dark):
        bg_color = "#232629" if is_dark else "#fafafa"
        text_color = "#ffffff" if is_dark else "#222222"
        desc_color = "#a1a1aa" if is_dark else "#555555"
        
        self.setStyleSheet(f"QDialog {{ background-color: {bg_color}; }}")
        for t in self.titles:
            t.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_color}; background: transparent;")
        for d in self.descs:
            d.setStyleSheet(f"color: {desc_color}; line-height: 1.5; font-size: 12px; background: transparent;")

class YouTubeDownloaderApp(QMainWindow):
    download_row_requested = pyqtSignal(object, str, str, str, str, str, str, str, object)
    # args: thumb_pixmap, title, fmt, res_or_bitrate, time_started, url, folder, format_text, info
    CONFIG_FILE = 'config.json'

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTV Downloader v1.0.2")
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ytdownloadlogo.ico')
        self.setWindowIcon(QIcon(logo_path))
        self.resize(700, 600)
        self.download_folder = self.load_download_folder()
        self.active_download_rows = []
        self.init_ui()
        self.set_dark_mode(True)  # Set dark mode by default
        self.download_row_requested.connect(self._add_download_row)

    def load_download_folder(self):
        import os
        default_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                folder = config.get('download_folder', default_folder)
                if os.path.isdir(folder):
                    return folder
        except Exception:
            pass
        return default_folder

    def save_download_folder(self, folder):
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({'download_folder': folder}, f)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def init_ui(self):
        menubar = self.menuBar()
        if menubar is not None:
            settings_action = menubar.addAction("Settings")
            settings_action.triggered.connect(self.show_settings_dialog)

            # Add Help menu
            help_menu = menubar.addMenu("Help")
            guides_action = QAction("Guides", self)
            guides_action.triggered.connect(self.show_guides_dialog)
            about_action = QAction("About", self)
            about_action.triggered.connect(self.show_about_dialog)
            if help_menu is not None:
                help_menu.addAction(guides_action)
                help_menu.addAction(about_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(20, 15, 20, 10)
        self.title_label = QLabel("YTV Downloader")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()
        
        # Hidden checkbox to keep the logic working for now
        self.theme_switch = QCheckBox("Dark Mode")
        self.theme_switch.setChecked(True)
        self.theme_switch.stateChanged.connect(self.toggle_mode)
        self.theme_switch.hide() 
        
        main_layout.addLayout(top_layout)

        # Controls area
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)
        
        controls_layout.addStretch(1)
        
        center_widget = QWidget()
        center_widget.setFixedWidth(500)  # Fixed width for a clean look
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 20, 0, 20)
        center_layout.setSpacing(10)
        
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Paste YouTube video URL here...")
        self.url_entry.setFixedHeight(35)
        center_layout.addWidget(self.url_entry)

        self.format_options = [
            "Audio: MP3", "Audio: M4A", "Audio: WEBM", "Audio: AAC", "Audio: FLAC", "Audio: OPUS", "Audio: OGG", "Audio: WAV",
            "SEPARATOR",
            "Video: MP4 (144p)",
            "Video: MP4 (240p)",
            "Video: MP4 (360p)",
            "Video: MP4 (480p)",
            "Video: MP4 (720p)",
            "Video: MP4 (1080p)",
            "Video: MP4 (1440p)"
        ]
        self.format_menu = QComboBox()
        for opt in self.format_options:
            if opt == "SEPARATOR":
                self.format_menu.insertSeparator(self.format_menu.count())
            else:
                self.format_menu.addItem(opt)
        self.format_menu.setCurrentText("Video: MP4 (720p)")
        self.format_menu.setFixedHeight(35)
        center_layout.addWidget(self.format_menu)

        self.download_btn = QPushButton("Download")
        self.download_btn.setEnabled(True)
        self.download_btn.clicked.connect(self.download_video)
        self.download_btn.setFixedHeight(40)
        self.set_button_style(self.download_btn)
        center_layout.addWidget(self.download_btn)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.status_label)
        
        controls_layout.addWidget(center_widget)
        controls_layout.addStretch(1)

        # Add QScrollArea for download rows below the columns_layout, spanning full width
        self.active_downloads_scroll = QScrollArea()
        self.active_downloads_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.active_downloads_scroll.setWidgetResizable(True)
        self.active_downloads_widget = QWidget()
        self.active_downloads_layout = QVBoxLayout(self.active_downloads_widget)
        self.active_downloads_layout.setContentsMargins(0, 0, 0, 0)
        self.active_downloads_layout.setSpacing(2)
        self.active_downloads_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.active_downloads_scroll.setWidget(self.active_downloads_widget)
        self.active_downloads_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.active_downloads_scroll.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Add the scroll area directly after the columns layout
        main_layout.addWidget(self.active_downloads_scroll)

        # self.active_downloads_layout.addStretch()  # Removed to make download cards start from the top

    def set_button_style(self, button):
        button.setStyleSheet("""
            QPushButton {
                background-color: #FFD600;
                color: #333333;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #FFEA00;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #888888;
                border-radius: 8px;
            }
        """)

    def set_dark_mode(self, enabled):
        import os
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        yellow_arrow = os.path.join(icon_dir, 'down_arrow_yellow.svg').replace('\\', '/')
        dark_arrow = os.path.join(icon_dir, 'down_arrow_dark.svg').replace('\\', '/')

        if enabled:
            self.setStyleSheet(f"""
                QMainWindow, QWidget {{ background: #232629; color: #f0f0f0; }}
                QScrollBar:vertical {{
                    border: none;
                    background: #232629;
                    width: 10px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: #4f5358;
                    min-height: 20px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: #FFD600;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    border: none;
                    background: none;
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
                QLabel, QLineEdit, QComboBox, QPushButton {{
                    color: #f0f0f0;
                    background: #232629;
                }}
                QPushButton {{ background: #FFD600; color: #333333; border-radius: 6px; font-weight: bold; padding: 6px 14px; min-width: 70px; min-height: 20px; }}
                QPushButton:hover {{ background: #FFEA00; }}
                QPushButton:disabled {{ background: #e0e0e0; color: #888888; border-radius: 8px; }}
                QLineEdit {{ background: #333; border: 1px solid #555; border-radius: 8px; padding: 5px; }}
                QComboBox {{ 
                    background: #333; 
                    border: 1px solid #555; 
                    border-radius: 8px; 
                    padding: 5px 15px;
                    min-width: 200px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url("{yellow_arrow}");
                    width: 12px;
                    height: 12px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #333;
                    color: #f0f0f0;
                    selection-background-color: #FFD600;
                    selection-color: #333;
                    border: 1px solid #555;
                    border-radius: 8px;
                    outline: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QMainWindow, QWidget {{ background: #fafafa; color: #222; }}
                QScrollBar:vertical {{
                    border: none;
                    background: #fafafa;
                    width: 10px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: #ccc;
                    min-height: 20px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: #FFD600;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    border: none;
                    background: none;
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
                QLabel, QLineEdit, QComboBox, QPushButton {{
                    color: #222;
                    background: #fafafa;
                }}
                QPushButton {{ background: #FFD600; color: #333333; border-radius: 6px; font-weight: bold; padding: 6px 14px; min-width: 70px; min-height: 20px; }}
                QPushButton:hover {{ background: #FFEA00; }}
                QPushButton:disabled {{ background: #e0e0e0; color: #888888; border-radius: 8px; }}
                QLineEdit {{ background: #fff; border: 1px solid #ccc; border-radius: 8px; padding: 5px; }}
                QComboBox {{ 
                    background: #fff; 
                    border: 1px solid #ccc; 
                    border-radius: 8px; 
                    padding: 5px 15px;
                    min-width: 200px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url("{dark_arrow}");
                    width: 12px;
                    height: 12px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #fff;
                    color: #222;
                    selection-background-color: #FFD600;
                    selection-color: #333;
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    outline: none;
                }}
            """)
        
        # Update existing download rows
        for row in self.active_download_rows:
            row.apply_theme(enabled)

    def toggle_mode(self):
        self.set_dark_mode(self.theme_switch.isChecked())

    def download_video(self):
        url = self.url_entry.text().strip()
        folder = self.download_folder
        format_text = self.format_menu.currentText()
        if not url:
            self.status_label.setText("Please enter a YouTube URL.")
            return
        if not folder or not os.path.isdir(folder):
            self.status_label.setText("Please select a valid download folder.")
            return
        self.status_label.setText("")
        self.url_entry.clear()
        threading.Thread(target=self._prepare_download_row, args=(url, folder, format_text), daemon=True).start()

    def _prepare_download_row(self, url, folder, format_text):
        print("_prepare_download_row called with:", url, folder, format_text)
        ydl_opts = {"quiet": True, "skip_download": True}
        info = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            print("Video info fetched:", (info or {}).get('title', 'N/A'))
        except Exception as e:
            print("Exception in _prepare_download_row:", e)
            def update():
                self.status_label.setText(f"Error: {e}")
                self.download_btn.setEnabled(True)
                QMessageBox.critical(self, "Error", f"Failed to fetch video info.\n{e}")
            QTimer.singleShot(0, update)
            return
        info = info or {}
        title = info.get('title', 'N/A')
        fmt = format_text
        res_or_bitrate = self._get_res_or_bitrate(info, format_text)
        thumb_url = info.get('thumbnail')
        thumb_pixmap = None
        if thumb_url:
            try:
                resp = requests.get(thumb_url)
                img_data = resp.content
                thumb_pixmap = QPixmap()
                thumb_pixmap.loadFromData(img_data)
            except Exception:
                thumb_pixmap = None
        time_started = datetime.datetime.now().strftime("%H:%M:%S")
        self.download_row_requested.emit(thumb_pixmap, title, fmt, res_or_bitrate, time_started, url, folder, format_text, info)

    def _add_download_row(self, thumb_pixmap, title, fmt, res_or_bitrate, time_started, url, folder, format_text, info):
        print("_add_download_row called: creating DownloadRow and starting download thread")
        row = DownloadRow(thumb_pixmap, title, fmt, res_or_bitrate, time_started, parent=self)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.retry_requested.connect(lambda rw, u=url, f=folder, ft=format_text, i=info: self._retry_download(rw, u, f, ft, i))
        row.remove_requested.connect(self._remove_download_row)
        self.active_download_rows.append(row)
        self.active_downloads_layout.addWidget(row)
        self.active_downloads_widget.adjustSize()
        self._start_download_thread(url, folder, format_text, row, info)

    def _remove_download_row(self, row_widget):
        print(f"Removing download row: {row_widget.title_label.text()}")
        if row_widget in self.active_download_rows:
            self.active_download_rows.remove(row_widget)
        self.active_downloads_layout.removeWidget(row_widget)
        row_widget.deleteLater()

    def _get_res_or_bitrate(self, info, format_text):
        if format_text.startswith("Audio: "):
            audio_format = format_text.replace("Audio: ", "")
            return f"{audio_format}"
        elif format_text.startswith("Video: "):
            if "(" in format_text and ")" in format_text:
                resolution = format_text.split("(")[-1].replace(")", "")
                return f"{resolution}"
            return "-"
        return "-"

    def _retry_download(self, row_widget, url, folder, format_text, info):
        print(f"_retry_download called for: {url}")
        self._start_download_thread(url, folder, format_text, row_widget, info)

    def _start_download_thread(self, url, folder, format_text, row_widget, info):
        print("_start_download_thread called")
        threading.Thread(target=self._download_thread, args=(url, folder, format_text, row_widget, info), daemon=True).start()

    def _download_thread(self, url, folder, format_text, row_widget, info):
        print("_download_thread called")
        format_map = {
            "Audio: MP3": "bestaudio[ext=mp3]",
            "Audio: M4A": "bestaudio[ext=m4a]",
            "Audio: WEBM": "bestaudio[ext=webm]",
            "Audio: AAC": "bestaudio[ext=aac]",
            "Audio: FLAC": "bestaudio[ext=flac]",
            "Audio: OPUS": "bestaudio[ext=opus]",
            "Audio: OGG": "bestaudio[ext=ogg]",
            "Audio: WAV": "bestaudio[ext=wav]",
            "Video: MP4 (144p)": "bestvideo[ext=mp4][height<=144]+bestaudio[ext=m4a]/best[ext=mp4][height<=144]",
            "Video: MP4 (240p)": "bestvideo[ext=mp4][height<=240]+bestaudio[ext=m4a]/best[ext=mp4][height<=240]",
            "Video: MP4 (360p)": "bestvideo[ext=mp4][height<=360]+bestaudio[ext=m4a]/best[ext=mp4][height<=360]",
            "Video: MP4 (480p)": "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]",
            "Video: MP4 (720p)": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]",
            "Video: MP4 (1080p)": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
            "Video: MP4 (1440p)": "bestvideo[ext=mp4][height<=1440]+bestaudio[ext=m4a]/best[ext=mp4][height<=1440]",
        }
        ydl_format = format_map.get(format_text, "best")
        outtmpl = os.path.join(folder, "%(title)s.%(ext)s")
        ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Tools', 'ffmpeg.exe')
        print("FFmpeg path used:", ffmpeg_path)  # Debug print
        
        # Store the ydl instance for potential cancellation
        ydl_instance = None
        
        try:
            print("_download_thread: starting yt_dlp download")
            def progress_hook(d):
                if row_widget.cancel_event.is_set():
                    print("Cancel event detected in progress hook")
                    raise Exception("Download canceled by user.")
                print("Progress hook called:", d.get('status'), d.get('downloaded_bytes', 0), d.get('total_bytes', 0))
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                    downloaded = d.get('downloaded_bytes', 0)
                    percent = downloaded / total
                    speed = d.get('speed', 0)
                    speed_str = f"{speed/1024:.1f} KB/s" if speed else "Speed: -"
                    size_str = f"{downloaded/1024/1024:.2f} MB / {total/1024/1024:.2f} MB"
                    eta = d.get('eta', None)
                    print(f"Progress: {int(percent*100)}%, Speed: {speed_str}, Size: {size_str}")
                    # Use signal to update UI
                    row_widget.update_progress_signal.emit(
                        int(percent*100),
                        f"{int(percent*100)}%",
                        speed_str,
                        size_str,
                        f"ETA: {eta}s" if eta is not None else "ETA: -"
                    )
                elif d['status'] == 'finished':
                    print("Download finished logic triggered in hook")
                    row_widget.update_status_signal.emit("Merging", "#00B0FF")
            
            ydl_opts = {
                'format': ydl_format,
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'quiet': True,
                'noplaylist': True,
                'merge_output_format': None,
                'ffmpeg_location': ffmpeg_path,
                'socket_timeout': 30,
                'retries': 10,
            }
            
            ydl_instance = yt_dlp.YoutubeDL(ydl_opts)
            # Use extract_info with download=True to get the final info_dict which contains the merged filename
            final_info = ydl_instance.extract_info(url, download=True)
            
            # Store the final info in the row widget so the UI thread can access it
            row_widget.final_download_info = final_info
            
            print("Download loop finished, setting to Complete")
            row_widget.update_status_signal.emit("Complete", "#00E676")
            
        except Exception as e:
            print(f"Exception in _download_thread: {e}")
            def update_err():
                if str(e) == "Download canceled by user.":
                    row_widget.update_status("Canceled", "#FF5252")
                    row_widget.progress.setValue(0)
                    row_widget.percent_label.setText("0%")
                else:
                    row_widget.update_status("Error", "#FF5252")
                row_widget.retry_btn.setEnabled(True)
                row_widget.open_btn.setEnabled(False)
                row_widget.delete_btn.setEnabled(True)
            QTimer.singleShot(0, update_err)

    def show_about_dialog(self):
        QMessageBox.information(self, "About YTV Downloader", "YTV Downloader \nA work in progress modern YouTube video downloader built for easy use and an array of features.")

    def show_guides_dialog(self):
        dialog = GuidesDialog(self)
        dialog.exec()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        self.save_download_folder(self.download_folder)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec()) 