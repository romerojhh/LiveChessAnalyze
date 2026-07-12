# Live Chess Analyzer ♟️

A real-time, non-intrusive chess assistant overlay written in Python using PySide6, OpenCV, and Stockfish. The application captures your screen, detects the chess board state using computer vision template matching, analyzes the board using a local Stockfish engine, and overlays recommended move arrows directly on top of your chess board in real time.

---

## 🚀 Features

- **Translucent UI Overlay**: A frameless, translucent overlay window that can be dragged, resized, and aligned over any web/desktop chess board (Chess.com, Lichess, desktop chess app, etc.).
- **Click-Through Analysis Mode**: Once configured, the overlay becomes transparent to mouse events, allowing you to click and play your game directly through it without interference.
- **Visual Move Recommendations**: Renders recommended move arrows directly on the chess board, with configurable fading.
- **Custom Template-Matching Computer Vision**: Dynamically calibrates to any board theme (light/dark square colors and piece designs) using the starting board position, extracting template images for light/dark squares and individual pieces.
- **Stockfish UCI Engine Integration**: Configure your local Stockfish executable with customized search depth, CPU thread allocation, hash size, and time limits.
- **Perspective Support**: Toggle between White perspective (White at Bottom) and Black perspective (Black at Bottom).

---

## 🛠️ Tech Stack & Dependencies

The project is built with:
- **PySide6**: High-performance UI framework for the Control Panel and custom-drawn Overlay.
- **OpenCV & Numpy**: Fast pixel-similarity analysis and template matching for square-state recognition.
- **MSS**: High-performance, cross-platform screen capture library for minimal latency.
- **Python-Chess**: Robust library for move generation, move validation, and game state (FEN) tracking.

---

## 📋 Prerequisites

1. **Python 3.9+** installed.
2. **Stockfish Chess Engine**: You must download the Stockfish UCI engine executable for your OS (e.g., Stockfish 15 or 16) from [Stockfish's official website](https://stockfishchess.org/download/).

---

## 💻 Installation

1. **Clone the Repository**:
   ```bash
   git clone <your-repo-url>
   cd LiveChessAnalyze
   ```

2. **Install Dependencies**:
   Install the required libraries listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

---

## 📖 How to Use

Follow these steps to configure and run the chess assistant:

### Step 1: Run the Application
Start the program by running `main.py`:
```bash
python main.py
```
This launches two windows:
1. **Control Panel**: Controls all settings, calibration, engine path, and runs/stops analysis.
2. **Overlay Guide**: A green grid that shows the screen area being captured.

---

### Step 2: Position the Overlay Guide
1. Open your target chess game (e.g., in a browser or desktop app).
2. Drag and resize the green **Overlay Guide** until it matches the borders of the chess board exactly. Make sure the grid lines align with the grid lines of the game board.

---

### Step 3: Calibrate the Board Theme
1. Set the target chess game to its **standard starting position** (with all 32 pieces on the board).
2. In the **Control Panel**, click **Calibrate Theme**.
3. The board detector will extract light/dark square colors and individual piece graphics, saving them to a local `calibration/` folder for template matching.
   - *Note: You only need to calibrate once unless the board theme, board size, or piece styles change.*

---

### Step 4: Configure Settings & Start Analysis
1. Select your perspective using the **Your Perspective** dropdown (e.g., "White at Bottom" or "Black at Bottom").
2. Set the path to your Stockfish executable under **Stockfish Path**.
3. Configure the engine settings (Depth, Threads, Hash size, Time limit) in the control panel.
4. Click **Start Analysis**. The green grid lines will disappear, the overlay will become click-through, and the app will continuously scan the board for move updates.
5. Make your moves, and watch the overlay draw recommended move arrows on the board!

---

## 📂 Project Structure

```
LiveChessAnalyze/
│
├── main.py                    # Application entrypoint
├── requirements.txt           # Python dependency specifications
├── LiveChessAnalyzer.spec     # PyInstaller bundle specification file
├── .gitignore                 # Excluded directories (caches, builds, config)
│
├── gui/
│   ├── control_panel.py       # Control panel window UI and configuration logic
│   └── overlay_window.py      # Translucent overlay window drawing recommended move arrows
│
├── engine/
│   └── chess_engine.py        # Local Stockfish engine wrapper (UCI protocol)
│
├── vision/
│   ├── board_detector.py      # Vision-based square detection, template loading & calibration
│   └── image_utils.py         # Image similarity analysis helper functions
│
├── calibration/               # Saved template assets (auto-generated on calibration)
└── test_images/               # Board screenshots used for offline testing/validation
```

---

## ⚠️ Disclaimer
This application is designed for **offline analysis, training, and study purposes only**. Using automated chess assistance in online multiplayer matches violates the terms of service of platforms like Chess.com and Lichess.org and will result in account suspension. Play fair!
