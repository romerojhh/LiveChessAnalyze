import os
import cv2
import numpy as np
import mss
import chess
from PySide6 import QtCore, QtGui, QtWidgets
from vision.board_detector import BoardDetector
from vision.board_locator import find_chessboard_on_screen
from engine.chess_engine import ChessEngine, IllegalInstructionError

class MiniBoardWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.perspective = "white"
        self.best_move = None
        self.setMinimumSize(220, 220)
        self.setMaximumSize(220, 220)

    def set_board(self, board, perspective, best_move=None):
        self.board = board.copy()
        self.perspective = perspective
        self.best_move = best_move
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h)

        offset_x = (w - size) // 2
        offset_y = (h - size) // 2

        sq_size = size / 8.0

        # Premium palette
        light_color = QtGui.QColor("#E2E6EC")
        dark_color = QtGui.QColor("#5C768D")

        start_highlight = QtGui.QColor(255, 165, 0, 120)  # Orange highlight
        end_highlight = QtGui.QColor(0, 200, 80, 120)     # Green highlight

        UNICODE_PIECES = {
            'P': '♟', 'R': '♜', 'N': '♞', 'B': '♝', 'Q': '♛', 'K': '♚',
            'p': '♟', 'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚'
        }

        font = painter.font()
        font.setPointSize(max(10, int(sq_size * 0.65)))
        font.setBold(True)
        painter.setFont(font)

        for r in range(8):
            for c in range(8):
                sx = offset_x + c * sq_size
                sy = offset_y + r * sq_size
                rect = QtCore.QRectF(sx, sy, sq_size, sq_size)

                if self.perspective == "white":
                    file_idx = c
                    rank_idx = 7 - r
                else:
                    file_idx = 7 - c
                    rank_idx = r

                square_idx = chess.square(file_idx, rank_idx)

                bg_color = dark_color if (r + c) % 2 == 1 else light_color
                painter.fillRect(rect, bg_color)

                if self.best_move:
                    if square_idx == self.best_move.from_square:
                        painter.fillRect(rect, start_highlight)
                    elif square_idx == self.best_move.to_square:
                        painter.fillRect(rect, end_highlight)

                piece = self.board.piece_at(square_idx)
                if piece:
                    symbol = UNICODE_PIECES.get(piece.symbol(), '')
                    if piece.color == chess.WHITE:
                        # White piece: Gold/Cream body with dark gray shadow
                        shadow_rect = QtCore.QRectF(rect.x() + 1, rect.y() + 1, rect.width(), rect.height())
                        painter.setPen(QtGui.QColor(30, 30, 30, 100))
                        painter.drawText(shadow_rect, QtCore.Qt.AlignmentFlag.AlignCenter, symbol)

                        painter.setPen(QtGui.QColor(255, 255, 255))
                        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, symbol)
                    else:
                        # Black piece: Slate black/charcoal with light shadow
                        shadow_rect = QtCore.QRectF(rect.x() - 0.5, rect.y() - 0.5, rect.width(), rect.height())
                        painter.setPen(QtGui.QColor(255, 255, 255, 80))
                        painter.drawText(shadow_rect, QtCore.Qt.AlignmentFlag.AlignCenter, symbol)

                        painter.setPen(QtGui.QColor(25, 25, 25))
                        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, symbol)

        border_pen = QtGui.QPen(QtGui.QColor("#2C3E50"), 2)
        painter.setPen(border_pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(QtCore.QRectF(offset_x, offset_y, size, size))

class ControlPanel(QtWidgets.QWidget):
    # Signals to communicate status updates or board changes
    status_changed = QtCore.Signal(str)
    move_recommended = QtCore.Signal(object)  # Emits chess.Move
    
    def __init__(self, overlay_window, parent=None):
        super().__init__(parent)
        self.overlay = overlay_window
        
        # Core instances
        self.detector = BoardDetector()
        self.engine = ChessEngine(log_callback=self.log)
        
        # Game state tracking
        self.current_board = chess.Board()
        self.analysis_active = False
        self.first_analysis_scan = True
        self.move_history = []
        
        # Debouncing variables to filter noise
        self.last_detected_pieces = None
        self.stable_frames_count = 0
        
        # Engine crash tracking
        self.consecutive_crashes = 0
        
        # Capture timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.run_analysis_step)
        
        # Set up GUI layout and styling
        self.setWindowTitle("Live Chess Analyzer - Controls")
        self.setMinimumSize(720, 600)
        self.setup_ui()
        self.apply_stylesheet()
        
        # Load saved settings if any
        self.load_settings()
        self.update_calibration_status()

    def setup_ui(self):
        # We split the UI into a side-by-side dashboard
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Left Panel (Controls & Settings)
        left_widget = QtWidgets.QWidget(self)
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # --- Group 1: Alignment & Calibration ---
        calibration_group = QtWidgets.QGroupBox("1. Setup & Calibration", left_widget)
        cal_layout = QtWidgets.QVBoxLayout(calibration_group)
        
        cal_desc = QtWidgets.QLabel(
            "Align the grid overlay exactly over your chess board or click "
            "Auto-Align to scan the screen automatically.",
            calibration_group
        )
        cal_desc.setWordWrap(True)
        cal_desc.setStyleSheet("color: #AAAAAA;")
        cal_layout.addWidget(cal_desc)
        
        btn_layout = QtWidgets.QGridLayout()
        btn_layout.setSpacing(8)
        self.btn_toggle_overlay = QtWidgets.QPushButton("Hide Overlay Guide", calibration_group)
        self.btn_toggle_overlay.setCheckable(True)
        self.btn_toggle_overlay.clicked.connect(self.toggle_overlay_visibility)
        
        self.btn_auto_align = QtWidgets.QPushButton("Auto-Align Board", calibration_group)
        self.btn_auto_align.setObjectName("actionButton")
        self.btn_auto_align.clicked.connect(self.find_chessboard_on_screen_action)

        self.btn_calibrate = QtWidgets.QPushButton("Calibrate Theme", calibration_group)
        self.btn_calibrate.clicked.connect(self.calibrate_board)
        
        btn_layout.addWidget(self.btn_toggle_overlay, 0, 0)
        btn_layout.addWidget(self.btn_auto_align, 0, 1)
        btn_layout.addWidget(self.btn_calibrate, 1, 0, 1, 2)
        cal_layout.addLayout(btn_layout)
        
        self.lbl_cal_status = QtWidgets.QLabel("Status: Checking calibration...", calibration_group)
        self.lbl_cal_status.setObjectName("statusLabel")
        cal_layout.addWidget(self.lbl_cal_status)
        
        left_layout.addWidget(calibration_group)
        
        # --- Group 2: Game Settings ---
        settings_group = QtWidgets.QGroupBox("2. Match Settings", left_widget)
        settings_layout = QtWidgets.QGridLayout(settings_group)
        settings_layout.setSpacing(10)
        
        # Perspective
        settings_layout.addWidget(QtWidgets.QLabel("Your Perspective:", settings_group), 0, 0)
        self.combo_perspective = QtWidgets.QComboBox(settings_group)
        self.combo_perspective.addItems(["White at Bottom", "Black at Bottom"])
        self.combo_perspective.currentIndexChanged.connect(self.change_perspective)
        settings_layout.addWidget(self.combo_perspective, 0, 1)
        
        # Stockfish Path
        settings_layout.addWidget(QtWidgets.QLabel("Stockfish Path:", settings_group), 1, 0)
        
        sf_path_layout = QtWidgets.QHBoxLayout()
        self.txt_sf_path = QtWidgets.QLineEdit(settings_group)
        self.txt_sf_path.setPlaceholderText("Select Stockfish .exe...")
        self.txt_sf_path.textChanged.connect(self.update_stockfish_path)
        
        self.btn_browse_sf = QtWidgets.QPushButton("Browse...", settings_group)
        self.btn_browse_sf.clicked.connect(self.browse_stockfish)
        
        sf_path_layout.addWidget(self.txt_sf_path)
        sf_path_layout.addWidget(self.btn_browse_sf)
        settings_layout.addLayout(sf_path_layout, 1, 1)
        
        # Depth
        settings_layout.addWidget(QtWidgets.QLabel("Analysis Depth:", settings_group), 2, 0)
        self.spin_depth = QtWidgets.QSpinBox(settings_group)
        self.spin_depth.setRange(5, 25)
        self.spin_depth.setValue(20)
        self.spin_depth.valueChanged.connect(self.update_engine_depth)
        settings_layout.addWidget(self.spin_depth, 2, 1)
        
        # CPU Cores Selection
        settings_layout.addWidget(QtWidgets.QLabel("CPU Cores:", settings_group), 3, 0)
        self.spin_threads = QtWidgets.QSpinBox(settings_group)
        max_cores = os.cpu_count() if os.cpu_count() else 1
        self.spin_threads.setRange(1, max_cores)
        self.spin_threads.setValue(max_cores)
        self.spin_threads.valueChanged.connect(self.update_cpu_threads)
        settings_layout.addWidget(self.spin_threads, 3, 1)
        
        # Hash Size Selection (RAM)
        settings_layout.addWidget(QtWidgets.QLabel("Hash Size (MB):", settings_group), 4, 0)
        self.spin_hash = QtWidgets.QSpinBox(settings_group)
        self.spin_hash.setRange(16, 2048)
        self.spin_hash.setSingleStep(16)
        self.spin_hash.setValue(256)
        self.spin_hash.valueChanged.connect(self.update_hash_size)
        settings_layout.addWidget(self.spin_hash, 4, 1)
        
        # Max Calculation Time
        settings_layout.addWidget(QtWidgets.QLabel("Max Time (seconds):", settings_group), 5, 0)
        self.spin_time_limit = QtWidgets.QDoubleSpinBox(settings_group)
        self.spin_time_limit.setRange(0.1, 5.0)
        self.spin_time_limit.setSingleStep(0.1)
        self.spin_time_limit.setValue(0.5)
        self.spin_time_limit.valueChanged.connect(self.update_time_limit)
        settings_layout.addWidget(self.spin_time_limit, 5, 1)
        
        # Interval
        self.lbl_scan_rate = QtWidgets.QLabel("Scan Rate (seconds):", settings_group)
        settings_layout.addWidget(self.lbl_scan_rate, 6, 0)
        self.spin_interval = QtWidgets.QDoubleSpinBox(settings_group)
        self.spin_interval.setRange(0.2, 5.0)
        self.spin_interval.setSingleStep(0.2)
        self.spin_interval.setValue(1.0)
        settings_layout.addWidget(self.spin_interval, 6, 1)
        
        # Running Mode
        settings_layout.addWidget(QtWidgets.QLabel("Running Mode:", settings_group), 7, 0)
        self.combo_mode = QtWidgets.QComboBox(settings_group)
        self.combo_mode.addItems(["On Demand (Click Button)", "Auto Scan (Periodic)"])
        self.combo_mode.currentIndexChanged.connect(self.change_analysis_mode)
        settings_layout.addWidget(self.combo_mode, 7, 1)
        
        left_layout.addWidget(settings_group)
        
        # --- Group 3: Game Controls & Tools ---
        controls_group = QtWidgets.QGroupBox("3. Game Controls", left_widget)
        cnt_layout = QtWidgets.QVBoxLayout(controls_group)
        
        btn_game_layout = QtWidgets.QHBoxLayout()
        self.btn_toggle_turn = QtWidgets.QPushButton("Toggle Active Turn", controls_group)
        self.btn_toggle_turn.clicked.connect(self.toggle_active_turn)
        
        self.btn_reset_board = QtWidgets.QPushButton("Reset Game State", controls_group)
        self.btn_reset_board.clicked.connect(self.reset_game_state)
        
        self.btn_adjust_grid = QtWidgets.QPushButton("Adjust/Unlock Grid", controls_group)
        self.btn_adjust_grid.clicked.connect(self.unlock_grid)
        
        btn_game_layout.addWidget(self.btn_toggle_turn)
        btn_game_layout.addWidget(self.btn_reset_board)
        btn_game_layout.addWidget(self.btn_adjust_grid)
        cnt_layout.addLayout(btn_game_layout)
        
        self.lbl_game_info = QtWidgets.QLabel("Turn: White | Moves played: 0", controls_group)
        self.lbl_game_info.setStyleSheet("color: #0078D7; font-weight: bold;")
        cnt_layout.addWidget(self.lbl_game_info)
        
        left_layout.addWidget(controls_group)
        
        # --- Main Run Button ---
        self.btn_run = QtWidgets.QPushButton("START ANALYSIS", left_widget)
        self.btn_run.setMinimumHeight(42)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #00CC66;
                color: black;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #00E673;
            }
            QPushButton:pressed {
                background-color: #00994D;
            }
            QPushButton:disabled {
                background-color: #334D3D;
                color: #888888;
            }
        """)
        self.btn_run.clicked.connect(self.toggle_analysis)
        left_layout.addWidget(self.btn_run)
        
        # Log view
        self.log_view = QtWidgets.QTextEdit(left_widget)
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(80)
        self.log_view.setPlaceholderText("Logs will appear here...")
        left_layout.addWidget(self.log_view)

        main_layout.addWidget(left_widget, stretch=4)

        # Right Panel (Mini-Board & Move History Dashboard)
        right_widget = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Title Card
        title_box = QtWidgets.QGroupBox("Live Visual Monitor", right_widget)
        title_layout = QtWidgets.QVBoxLayout(title_box)
        title_layout.setSpacing(10)

        self.mini_board = MiniBoardWidget(title_box)
        title_layout.addWidget(self.mini_board, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        right_layout.addWidget(title_box)

        # History Card
        history_box = QtWidgets.QGroupBox("PGN Game History", right_widget)
        history_layout = QtWidgets.QVBoxLayout(history_box)
        history_layout.setSpacing(8)

        history_buttons = QtWidgets.QHBoxLayout()
        history_lbl = QtWidgets.QLabel("Recorded Moves:", history_box)
        history_lbl.setStyleSheet("color: #AAAAAA;")
        history_buttons.addWidget(history_lbl)

        self.btn_copy_pgn = QtWidgets.QPushButton("Copy PGN", history_box)
        self.btn_copy_pgn.setObjectName("actionButton")
        self.btn_copy_pgn.clicked.connect(self.copy_pgn_to_clipboard)
        history_buttons.addWidget(self.btn_copy_pgn)

        history_layout.addLayout(history_buttons)

        self.table_history = QtWidgets.QTableWidget(history_box)
        self.table_history.setColumnCount(2)
        self.table_history.setHorizontalHeaderLabels(["White", "Black"])
        self.table_history.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_history.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_history.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.table_history.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        history_layout.addWidget(self.table_history)

        right_layout.addWidget(history_box)

        main_layout.addWidget(right_widget, stretch=3)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #E0E0E0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #262626;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #161616;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 8px;
                color: #0078D7;
            }
            QPushButton {
                background-color: #1F1F1F;
                border: 1px solid #333333;
                border-radius: 5px;
                padding: 6px 12px;
                min-height: 22px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2D2D2D;
                border-color: #0078D7;
            }
            QPushButton:pressed {
                background-color: #0F0F0F;
            }
            QPushButton#actionButton {
                background-color: #0078D7;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton#actionButton:hover {
                background-color: #0086F0;
            }
            QPushButton#actionButton:pressed {
                background-color: #005A9E;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #1F1F1F;
                border: 1px solid #333333;
                border-radius: 5px;
                padding: 5px;
                color: #E0E0E0;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #0078D7;
            }
            QLabel#statusLabel {
                font-size: 13px;
                font-weight: bold;
                color: #FFB300;
            }
            QTextEdit {
                background-color: #0A0A0A;
                border: 1px solid #222222;
                border-radius: 5px;
                color: #00CC66;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
            QTableWidget {
                background-color: #0A0A0A;
                border: 1px solid #222222;
                border-radius: 5px;
                color: #E0E0E0;
                gridline-color: #1F1F1F;
            }
            QHeaderView::section {
                background-color: #1F1F1F;
                color: #0078D7;
                padding: 5px;
                border: 1px solid #222222;
                font-weight: bold;
            }
        """)

    def log(self, message):
        if "\n" in message:
            # Wrap in HTML <pre> to preserve text-grid layout and spacing in monospaced font
            self.log_view.append(f"<pre style='font-family: Consolas, monospace; margin: 0; color: #00CC66;'>{message}</pre>")
        else:
            self.log_view.append(message)
        # Scroll to bottom
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def load_settings(self):
        # Default local settings
        settings = QtCore.QSettings("LiveChessAnalyze", "Config")
        sf_path = settings.value("stockfish_path", "")
        self.txt_sf_path.setText(sf_path)
        
        perspective = int(settings.value("perspective", 0))
        self.combo_perspective.setCurrentIndex(perspective)
        self.change_perspective(perspective)
        
        depth = int(settings.value("depth", 20))
        self.spin_depth.setValue(depth)
        
        max_cores = os.cpu_count() if os.cpu_count() else 1
        threads = int(settings.value("threads", max_cores))
        self.spin_threads.setValue(threads)
        self.update_cpu_threads(threads)
        
        hash_size = int(settings.value("hash_size", 256))
        self.spin_hash.setValue(hash_size)
        self.update_hash_size(hash_size)
        
        time_limit = float(settings.value("time_limit", 0.5))
        self.spin_time_limit.setValue(time_limit)
        self.update_time_limit(time_limit)
        
        interval = float(settings.value("interval", 1.0))
        self.spin_interval.setValue(interval)
        
        mode = int(settings.value("analysis_mode", 0))  # Default: On Demand
        self.combo_mode.setCurrentIndex(mode)
        self.change_analysis_mode(mode)

    def save_settings(self):
        settings = QtCore.QSettings("LiveChessAnalyze", "Config")
        settings.setValue("stockfish_path", self.txt_sf_path.text())
        settings.setValue("perspective", self.combo_perspective.currentIndex())
        settings.setValue("depth", self.spin_depth.value())
        settings.setValue("threads", self.spin_threads.value())
        settings.setValue("hash_size", self.spin_hash.value())
        settings.setValue("time_limit", self.spin_time_limit.value())
        settings.setValue("interval", self.spin_interval.value())
        settings.setValue("analysis_mode", self.combo_mode.currentIndex())

    def update_calibration_status(self):
        if self.detector.is_calibrated:
            self.lbl_cal_status.setText("Status: Calibrated (Theme Saved)")
            self.lbl_cal_status.setStyleSheet("color: #00CC66; font-weight: bold;")
            self.btn_run.setEnabled(True)
        else:
            self.lbl_cal_status.setText("Status: NOT CALIBRATED")
            self.lbl_cal_status.setStyleSheet("color: #FF3333; font-weight: bold;")
            self.btn_run.setEnabled(False)

    def toggle_overlay_visibility(self, checked):
        if checked:
            self.overlay.hide()
            self.btn_toggle_overlay.setText("Show Overlay Guide")
        else:
            self.overlay.show()
            self.btn_toggle_overlay.setText("Hide Overlay Guide")

    def calibrate_board(self):
        self.log("Capturing board for calibration...")
        try:
            img = self.capture_overlay_rect()
            if img is None:
                self.log("Error: Screen capture failed.")
                return
                
            perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
            self.detector.calibrate(img, perspective)
            self.update_calibration_status()
            self.log("Calibration successful! Saved templates to disk.")
            
            # Reset internal chess.Board to initial setup
            self.reset_game_state()
            
        except Exception as e:
            self.log(f"Calibration failed: {e}")
            QtWidgets.QMessageBox.critical(self, "Calibration Error", f"Failed to calibrate: {e}")

    def capture_overlay_rect(self):
        geom = self.overlay.geometry()
        
        # Grab using mss
        with mss.mss() as sct:
            monitor = {
                "top": geom.y(),
                "left": geom.x(),
                "width": geom.width(),
                "height": geom.height()
            }
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            # Convert BGRA to BGR
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def change_perspective(self, index):
        perspective = "white" if index == 0 else "black"
        self.overlay.set_perspective(perspective)
        self.log(f"Perspective set to: {perspective.capitalize()} at bottom.")
        self.save_settings()

        # Update mini-board
        self.mini_board.set_board(self.current_board, perspective, self.overlay.best_move)

    def find_chessboard_on_screen_action(self):
        self.log("Scanning screen for chessboard...")
        self.hide()
        self.overlay.hide()

        QtCore.QCoreApplication.processEvents()
        QtCore.QThread.msleep(300)

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                screen_img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            board_rect = find_chessboard_on_screen(screen_img)

            if board_rect is not None:
                bx, by, bw, bh = board_rect
                self.log(f"Found chessboard at: X={bx}, Y={by}, W={bw}, H={bh}")

                screen = QtWidgets.QApplication.primaryScreen()
                dpr = screen.devicePixelRatio()

                lx = int(bx / dpr)
                ly = int(by / dpr)
                lw = int(bw / dpr)
                lh = int(bh / dpr)

                self.log(f"Setting overlay (DPR={dpr}): X={lx}, Y={ly}, W={lw}, H={lh}")
                self.overlay.setGeometry(lx, ly, lw, lh)
                self.overlay.set_setup_mode(False)

                # Check option 0 (White perspective) vs 1 (Black perspective)
                perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
                self.mini_board.set_board(self.current_board, perspective, None)

                QtWidgets.QMessageBox.information(
                    self,
                    "Auto-Align Success",
                    f"Chessboard auto-detected and aligned!\nLogical coordinates: {lx}, {ly}, {lw}x{lh}"
                )
            else:
                self.log("Chessboard not found on screen.")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Chessboard Not Found",
                    "Could not find any chessboard on the screen. Please ensure the board is fully visible and not blocked."
                )
        except Exception as e:
            self.log(f"Auto-alignment error: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Auto-Align Error",
                f"An error occurred: {e}"
            )
        finally:
            self.overlay.show()
            self.show()

    def add_move_to_history(self, san_str):
        self.move_history.append(san_str)
        move_idx = len(self.move_history) - 1
        row = move_idx // 2

        if move_idx % 2 == 0:
            self.table_history.insertRow(row)
            self.table_history.setItem(row, 0, QtWidgets.QTableWidgetItem(san_str))
            self.table_history.setItem(row, 1, QtWidgets.QTableWidgetItem(""))
        else:
            self.table_history.setItem(row, 1, QtWidgets.QTableWidgetItem(san_str))

        self.table_history.scrollToBottom()
        perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
        self.mini_board.set_board(self.current_board, perspective, self.overlay.best_move)

    def clear_move_history(self):
        self.move_history = []
        self.table_history.setRowCount(0)
        perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
        self.mini_board.set_board(self.current_board, perspective, self.overlay.best_move)

    def get_pgn_string(self):
        pgn_parts = []
        for i in range(0, len(self.move_history), 2):
            move_num = (i // 2) + 1
            w_move = self.move_history[i]
            b_move = self.move_history[i+1] if (i+1) < len(self.move_history) else ""
            if b_move:
                pgn_parts.append(f"{move_num}. {w_move} {b_move}")
            else:
                pgn_parts.append(f"{move_num}. {w_move}")
        return " ".join(pgn_parts)

    def copy_pgn_to_clipboard(self):
        pgn = self.get_pgn_string()
        if pgn:
            QtWidgets.QApplication.clipboard().setText(pgn)
            self.log(f"PGN copied to clipboard: {pgn}")
        else:
            self.log("No moves in history to copy.")

    def toggle_active_turn(self):
        self.current_board.turn = not self.current_board.turn
        self.update_game_info_label()
        self.log(f"Manually toggled turn. Now active: {'White' if self.current_board.turn == chess.WHITE else 'Black'}")

        best_move = None
        if self.analysis_active:
            best_move = self.engine.get_best_move(self.current_board)
            self.overlay.set_best_move(best_move)
            if best_move:
                self.log(f"Recommended Move: {best_move.uci()}")

        perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
        self.mini_board.set_board(self.current_board, perspective, best_move)

    def reset_game_state(self):
        self.current_board = chess.Board()
        self.overlay.set_best_move(None)
        self.clear_move_history()
        self.update_game_info_label()
        self.log("Game state reset to starting position.")

        best_move = None
        if self.analysis_active:
            best_move = self.engine.get_best_move(self.current_board)
            self.overlay.set_best_move(best_move)
            if best_move:
                self.log(f"Recommended Move: {best_move.uci()}")

        perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
        self.mini_board.set_board(self.current_board, perspective, best_move)

    def update_game_info_label(self):
        turn_str = "White" if self.current_board.turn == chess.WHITE else "Black"
        move_count = len(self.current_board.move_stack)
        self.lbl_game_info.setText(f"Turn: {turn_str} | Moves played: {move_count}")



    def browse_stockfish(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Stockfish Executable", "", "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.txt_sf_path.setText(file_path)
            self.save_settings()

    def update_stockfish_path(self, text):
        self.engine.set_stockfish_path(text)
        self.save_settings()

    def update_engine_depth(self, value):
        self.engine.set_depth(value)
        self.save_settings()

    def update_cpu_threads(self, value):
        self.engine.set_threads(value)
        self.save_settings()

    def update_hash_size(self, value):
        self.engine.set_hash_size(value)
        self.save_settings()

    def update_time_limit(self, value):
        self.engine.set_time_limit(value)
        self.save_settings()

    def toggle_active_turn(self):
        self.current_board.turn = not self.current_board.turn
        self.update_game_info_label()
        self.log(f"Manually toggled turn. Now active: {'White' if self.current_board.turn == chess.WHITE else 'Black'}")
        if self.analysis_active:
            # Update recommendation immediately
            best_move = self.engine.get_best_move(self.current_board)
            self.overlay.set_best_move(best_move)
            if best_move:
                self.log(f"Recommended Move: {best_move.uci()}")

    def reset_game_state(self):
        self.current_board = chess.Board()
        self.overlay.set_best_move(None)
        self.update_game_info_label()
        self.log("Game state reset to starting position.")
        if self.analysis_active:
            # Update recommendation immediately
            best_move = self.engine.get_best_move(self.current_board)
            self.overlay.set_best_move(best_move)
            if best_move:
                self.log(f"Recommended Move: {best_move.uci()}")

    def update_game_info_label(self):
        turn_str = "White" if self.current_board.turn == chess.WHITE else "Black"
        move_count = len(self.current_board.move_stack)
        self.lbl_game_info.setText(f"Turn: {turn_str} | Moves played: {move_count}")

    def change_analysis_mode(self, index):
        is_auto = (index == 1)
        self.lbl_scan_rate.setEnabled(is_auto)
        self.spin_interval.setEnabled(is_auto)
        
        # Stop auto scan if it was active
        if self.analysis_active and not is_auto:
            self.stop_auto_analysis()
            
        self.update_run_button_style()
        self.save_settings()

    def toggle_analysis(self):
        is_auto = (self.combo_mode.currentIndex() == 1)
        if is_auto:
            if self.analysis_active:
                self.stop_auto_analysis()
            else:
                self.start_auto_analysis()
        else:
            self.run_on_demand_step()

    def start_auto_analysis(self):
        if not os.path.exists(self.txt_sf_path.text()):
            QtWidgets.QMessageBox.warning(
                self, "Configuration Error", 
                "Stockfish executable path is invalid. Please select a valid Stockfish .exe."
            )
            return
            
        self.analysis_active = True
        self.update_run_button_style()
        self.overlay.set_setup_mode(False)
        
        interval_ms = int(self.spin_interval.value() * 1000)
        self.timer.start(interval_ms)
        self.log(f"Auto scan started. Scanning every {self.spin_interval.value()}s. Click-through enabled.")
        
        self.first_analysis_scan = True
        self.consecutive_crashes = 0
        self.run_analysis_step()

    def stop_auto_analysis(self):
        self.timer.stop()
        self.analysis_active = False
        self.update_run_button_style()
        self.overlay.set_setup_mode(True)
        self.overlay.set_best_move(None)
        self.engine.stop_local_engine()
        self.log("Auto scan stopped. Grid is adjustable. Stockfish process stopped.")

    def update_run_button_style(self):
        is_auto = (self.combo_mode.currentIndex() == 1)
        if is_auto:
            if self.analysis_active:
                self.btn_run.setText("STOP AUTO SCAN")
                self.btn_run.setStyleSheet("""
                    QPushButton {
                        background-color: #FF3333;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 6px;
                    }
                    QPushButton:hover { background-color: #FF4D4D; }
                    QPushButton:pressed { background-color: #CC0000; }
                """)
            else:
                self.btn_run.setText("START AUTO SCAN")
                self.btn_run.setStyleSheet("""
                    QPushButton {
                        background-color: #00CC66;
                        color: black;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 6px;
                    }
                    QPushButton:hover { background-color: #00E673; }
                    QPushButton:pressed { background-color: #00994D; }
                """)
        else:
            self.btn_run.setText("SUGGEST BEST MOVE")
            self.btn_run.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #0086F0; }
                QPushButton:pressed { background-color: #005A9E; }
            """)

    def unlock_grid(self):
        if self.analysis_active:
            self.stop_auto_analysis()
        self.overlay.set_setup_mode(True)
        self.overlay.set_best_move(None)
        self.log("Grid unlocked. Drag and resize overlay to align with board.")

    def run_on_demand_step(self):
        if not os.path.exists(self.txt_sf_path.text()):
            QtWidgets.QMessageBox.warning(
                self, "Configuration Error", 
                "Stockfish executable path is invalid. Please select a valid Stockfish .exe."
            )
            return
            
        self.overlay.set_setup_mode(False)
        self.log("Capturing board for on-demand move recommendation...")
        self.clear_move_history()
        
        try:
            # 1. Capture screen
            img = self.capture_overlay_rect()
            if img is None:
                self.log("Error: Screen capture failed.")
                return
                
            # 2. Detect board pieces on screen
            perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
            detected_board = self.detector.detect_board(img, perspective)
            detected_pieces = detected_board.piece_map()
            
            # 3. Rebuild board statelessly
            self.current_board.clear()
            for sq, pc in detected_pieces.items():
                self.current_board.set_piece_at(sq, pc)
                
            # Set turn to player's turn
            player_color = chess.WHITE if self.combo_perspective.currentIndex() == 0 else chess.BLACK
            self.current_board.turn = player_color
            
            # Set standard castling rights if King and Rook are still on their initial squares
            # Check White
            if self.current_board.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE):
                if self.current_board.piece_at(chess.A1) == chess.Piece(chess.ROOK, chess.WHITE):
                    self.current_board.castling_rights |= chess.BB_A1
                if self.current_board.piece_at(chess.H1) == chess.Piece(chess.ROOK, chess.WHITE):
                    self.current_board.castling_rights |= chess.BB_H1
            # Check Black
            if self.current_board.piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK):
                if self.current_board.piece_at(chess.A8) == chess.Piece(chess.ROOK, chess.BLACK):
                    self.current_board.castling_rights |= chess.BB_A8
                if self.current_board.piece_at(chess.H8) == chess.Piece(chess.ROOK, chess.BLACK):
                    self.current_board.castling_rights |= chess.BB_H8
                    
            self.update_game_info_label()
            
            # Log the visual representation of the board layout
            self.log(self.current_board.unicode())
            
            # 4. Get recommended best move
            best_move = self.engine.get_best_move(self.current_board)
            if best_move:
                self.overlay.set_best_move(best_move)
                self.log(f"On-Demand Recommended Move: {best_move.uci()}")
            else:
                self.overlay.set_best_move(None)
                self.log("No recommendation found (checkmate/draw/invalid board state).")
                
            # Update mini-board
            self.mini_board.set_board(self.current_board, perspective, best_move)

        except IllegalInstructionError as e:
            self.log(f"On-demand error: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "Stockfish CPU Compatibility Error", 
                str(e)
            )
        except Exception as e:
            self.log(f"On-demand error: {e}")

    def run_analysis_step(self):
        """Timer callback that captures, classifies, updates board state, and calculates best move."""
        if not self.analysis_active:
            return
            
        try:
            # 1. Capture screen
            img = self.capture_overlay_rect()
            if img is None:
                return
                
            # 2. Detect board pieces on screen
            perspective = "white" if self.combo_perspective.currentIndex() == 0 else "black"
            detected_board = self.detector.detect_board(img, perspective)
            
            # 3. Handle board state tracking / transition logic
            # Compare detected layout with internal board state
            detected_pieces = detected_board.piece_map()
            current_pieces = self.current_board.piece_map()
            
            if detected_pieces == current_pieces:
                # No change on screen. Reset debounce tracker.
                self.last_detected_pieces = None
                self.stable_frames_count = 0
                
                # If it's the very first scan, calculate and show the recommendation once
                if self.first_analysis_scan:
                    self.first_analysis_scan = False
                    self.log(self.current_board.unicode())
                    best_move = self.engine.get_best_move(self.current_board)
                    if best_move:
                        self.overlay.set_best_move(best_move)
                        self.log(f"Initial Recommended Move: {best_move.uci()}")

                    # Update mini-board
                    self.mini_board.set_board(self.current_board, perspective, best_move)
                return
                
            # Layout is different from current board! Let's check stability
            if detected_pieces != self.last_detected_pieces:
                # First frame we see this new layout, save it and wait for next frame
                self.last_detected_pieces = detected_pieces
                self.stable_frames_count = 1
                return
            else:
                # Consecutive frame with the same new layout, increment count
                self.stable_frames_count += 1
                if self.stable_frames_count < 2:  # Must be stable for 2 frames
                    return
            
            # The change is stable! Now reset tracker for future changes and apply the move
            self.last_detected_pieces = None
            self.stable_frames_count = 0
                
            # Piece layout changed! Check if it corresponds to a legal move from current turn
            move_found = False
            
            # Calculate changed squares between current internal board and detected board
            changed_squares = set()
            for sq in chess.SQUARES:
                if current_pieces.get(sq) != detected_pieces.get(sq):
                    changed_squares.add(sq)

            # Try current turn first
            for move in self.current_board.legal_moves:
                if move.from_square in changed_squares and move.to_square in changed_squares:
                    self.current_board.push(move)
                    match = (self.current_board.piece_map() == detected_pieces)
                    self.current_board.pop()
                    if match:
                        san_str = self.current_board.san(move)
                        self.current_board.push(move)
                        self.log(f"Detected Move: {san_str} ({move.uci()})")
                        self.add_move_to_history(san_str)
                        move_found = True
                        break
                    
            # If not matching, check if opponent moved twice or we missed active turn syncing
            if not move_found:
                # Temporarily toggle turn to see if the other player made a move
                self.current_board.turn = not self.current_board.turn
                for move in self.current_board.legal_moves:
                    if move.from_square in changed_squares and move.to_square in changed_squares:
                        self.current_board.push(move)
                        match = (self.current_board.piece_map() == detected_pieces)
                        self.current_board.pop()
                        if match:
                            san_str = self.current_board.san(move)
                            self.current_board.push(move)
                            self.log(f"Detected Move (Turn-corrected): {san_str} ({move.uci()})")
                            self.add_move_to_history(san_str)
                            move_found = True
                            break
                # If still not found, revert turn
                if not move_found:
                    self.current_board.turn = not self.current_board.turn
                    
            # If still not matching any legal move, force-update state to screen layout
            if not move_found:
                self.log("Screen layout changed but doesn't match legal moves. Syncing board state to screen...")
                turn = self.current_board.turn
                
                # Copy pieces
                self.current_board.clear()
                for sq, pc in detected_pieces.items():
                    self.current_board.set_piece_at(sq, pc)
                    
                self.current_board.turn = turn
                self.log("State synchronized.")
                self.clear_move_history()
                
            # Update turn indicator label
            self.update_game_info_label()
            
            # Log the visual representation of the board layout
            self.log(self.current_board.unicode())
            
            # 4. Get recommended best move (Only recommend for player's turn to prevent distractions)
            player_color = chess.WHITE if self.combo_perspective.currentIndex() == 0 else "black"
            player_color_val = chess.WHITE if player_color == chess.WHITE else chess.BLACK

            best_move = None
            if self.current_board.turn == player_color_val:
                best_move = self.engine.get_best_move(self.current_board)
                if best_move:
                    self.overlay.set_best_move(best_move)
                    self.log(f"Recommended Move: {best_move.uci()}")
                    self.consecutive_crashes = 0
                else:
                    self.overlay.set_best_move(None)
            else:
                self.overlay.set_best_move(None)
                
            # Update mini-board
            self.mini_board.set_board(self.current_board, perspective, best_move)

        except IllegalInstructionError as e:
            self.log(f"Analysis halted: {e}")
            self.toggle_analysis()
            QtWidgets.QMessageBox.critical(
                self,
                "Stockfish CPU Compatibility Error",
                str(e)
            )
        except Exception as e:
            self.log(f"Analysis error: {e}")
            self.consecutive_crashes += 1
            if self.consecutive_crashes >= 3:
                self.log("Analysis halted: Engine is crashing repeatedly.")
                self.toggle_analysis()
                QtWidgets.QMessageBox.warning(
                    self,
                    "Repeated Engine Crashes",
                    "The Stockfish engine has crashed repeatedly. Please check your path and version compatibility."
                )

        except IllegalInstructionError as e:
            self.log(f"Analysis halted: {e}")
            # Stop analysis loop immediately
            self.toggle_analysis()
            QtWidgets.QMessageBox.critical(
                self, 
                "Stockfish CPU Compatibility Error", 
                str(e)
            )
        except Exception as e:
            self.log(f"Analysis error: {e}")
            self.consecutive_crashes += 1
            if self.consecutive_crashes >= 3:
                self.log("Analysis halted: Engine is crashing repeatedly.")
                self.toggle_analysis()
                QtWidgets.QMessageBox.warning(
                    self,
                    "Repeated Engine Crashes",
                    "The Stockfish engine has crashed repeatedly. Please check your path and version compatibility."
                )
    def closeEvent(self, event):
        # Make sure timer is stopped and settings are saved on close
        self.timer.stop()
        self.engine.stop_local_engine()
        self.save_settings()
        self.overlay.close()
        super().closeEvent(event)
