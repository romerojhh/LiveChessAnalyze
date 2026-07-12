import os
import cv2
import numpy as np
import chess
from vision.image_utils import get_similarity, synthesize_piece_on_background

class BoardDetector:
    def __init__(self, calibration_dir="calibration"):
        self.calibration_dir = calibration_dir
        self.templates = {}  # Map of (piece_char_or_empty, bg_color) -> image
        self.is_calibrated = False
        
        # Ensure calibration dir exists
        os.makedirs(self.calibration_dir, exist_ok=True)
        self.load_templates()

    def get_template_filename(self, piece_or_empty, bg_color):
        # 'empty' or piece symbol ('P', 'r', 'p', etc.)
        # Ensure filename is safe (case sensitive filesystems can sometimes be tricky with 'p' vs 'P'
        # so we prefix white pieces with 'W_' and black with 'B_')
        prefix = ""
        if piece_or_empty == "empty":
            name = "empty"
        elif piece_or_empty.isupper():
            name = f"W_{piece_or_empty.lower()}"
        else:
            name = f"B_{piece_or_empty.lower()}"
            
        return os.path.join(self.calibration_dir, f"{name}_{bg_color}.png")

    def load_templates(self):
        """Loads calibration templates from disk if they exist."""
        self.templates = {}
        bg_colors = ["light", "dark"]
        pieces = ["empty"] + list("PRNBQKprnbqk")
        
        missing = False
        for bg in bg_colors:
            for piece in pieces:
                filename = self.get_template_filename(piece, bg)
                if os.path.exists(filename):
                    img = cv2.imread(filename)
                    if img is not None:
                        self.templates[(piece, bg)] = img
                    else:
                        missing = True
                else:
                    missing = True
                    
        if not missing:
            self.is_calibrated = True
            print("Loaded calibration templates from disk.")
        else:
            self.is_calibrated = False

    def save_templates(self):
        """Saves current templates to disk."""
        for (piece_or_empty, bg), img in self.templates.items():
            filename = self.get_template_filename(piece_or_empty, bg)
            cv2.imwrite(filename, img)
        print("Saved calibration templates to disk.")

    def calibrate(self, board_image, perspective="white"):
        """
        Calibrates the board templates using a starting board image.
        """
        h, w, _ = board_image.shape
        sq_h = h / 8.0
        sq_w = w / 8.0
        
        raw_templates = {}
        empty_squares = {"light": [], "dark": []}
        
        # Helper to get standard starting piece type
        def get_starting_piece(r, c):
            if perspective == "white":
                if r == 0:
                    return ["r", "n", "b", "q", "k", "b", "n", "r"][c]
                elif r == 1:
                    return "p"
                elif r == 6:
                    return "P"
                elif r == 7:
                    return ["R", "N", "B", "Q", "K", "B", "N", "R"][c]
            else:  # black perspective
                if r == 0:
                    return ["R", "N", "B", "K", "Q", "B", "N", "R"][c]
                elif r == 1:
                    return "P"
                elif r == 6:
                    return "p"
                elif r == 7:
                    return ["r", "n", "b", "k", "q", "b", "n", "r"][c]
            return "empty"

        # Step 1: Extract all squares and group empty/pieces
        for r in range(8):
            for c in range(8):
                y1 = int(r * sq_h)
                y2 = int((r + 1) * sq_h)
                x1 = int(c * sq_w)
                x2 = int((c + 1) * sq_w)
                
                square = board_image[y1:y2, x1:x2]
                square = cv2.resize(square, (64, 64))
                bg_color = "dark" if (r + c) % 2 == 1 else "light"
                piece = get_starting_piece(r, c)
                
                if piece == "empty":
                    empty_squares[bg_color].append(square)
                else:
                    raw_templates[(piece, bg_color)] = square

        # Step 2: Average empty squares to reduce noise
        if empty_squares["light"] and empty_squares["dark"]:
            self.templates[("empty", "light")] = np.mean(empty_squares["light"], axis=0).astype(np.uint8)
            self.templates[("empty", "dark")] = np.mean(empty_squares["dark"], axis=0).astype(np.uint8)
        else:
            raise ValueError("Could not find empty squares for calibration.")

        # Step 3: Populate raw templates in self.templates
        for k, v in raw_templates.items():
            self.templates[k] = v

        # Step 4: Synthesize missing combinations (e.g. Queen/King on the opposite background)
        pieces = list("PRNBQKprnbqk")
        for piece in pieces:
            # Check light background
            has_light = (piece, "light") in self.templates
            has_dark = (piece, "dark") in self.templates
            
            if has_light and not has_dark:
                self.templates[(piece, "dark")] = synthesize_piece_on_background(
                    self.templates[(piece, "light")],
                    self.templates[("empty", "light")],
                    self.templates[("empty", "dark")]
                )
            elif has_dark and not has_light:
                self.templates[(piece, "light")] = synthesize_piece_on_background(
                    self.templates[(piece, "dark")],
                    self.templates[("empty", "dark")],
                    self.templates[("empty", "light")]
                )
                
        self.is_calibrated = True
        self.save_templates()
        return True

    def detect_board(self, board_image, perspective="white"):
        """
        Analyzes a captured board image and returns a chess.Board object.
        """
        if not self.is_calibrated:
            raise ValueError("Detector is not calibrated.")
            
        h, w, _ = board_image.shape
        sq_h = h / 8.0
        sq_w = w / 8.0
        
        detected_board = chess.Board(None)  # Start empty
        
        # We only test actual pieces. If a square is flat, it is empty.
        pieces_to_test = list("PRNBQKprnbqk")
        
        for r in range(8):
            for c in range(8):
                y1 = int(r * sq_h)
                y2 = int((r + 1) * sq_h)
                x1 = int(c * sq_w)
                x2 = int((c + 1) * sq_w)
                
                square = board_image[y1:y2, x1:x2]
                square = cv2.resize(square, (64, 64))
                
                # Check spatial standard deviation of grayscale square first.
                # Solid/flat color squares (even yellow/blue highlights) are empty.
                gray_square = cv2.cvtColor(square, cv2.COLOR_BGR2GRAY)
                std_val = np.std(gray_square)
                
                if std_val < 3.0:
                    continue  # Keep as empty
                    
                bg_color = "dark" if (r + c) % 2 == 1 else "light"
                
                # Compare non-flat square with piece templates
                best_piece = "empty"
                best_score = -1.0
                
                for piece in pieces_to_test:
                    template_key = (piece, bg_color)
                    if template_key in self.templates:
                        score = get_similarity(square, self.templates[template_key])
                        if score > best_score:
                            best_score = score
                            best_piece = piece
                
                # Confidence threshold: if correlation is below 80%, it is not a piece
                if best_piece != "empty" and best_score >= 0.80:
                    if perspective == "white":
                        file_idx = c
                        rank_idx = 7 - r
                    else:
                        file_idx = 7 - c
                        rank_idx = r
                        
                    square_idx = chess.square(file_idx, rank_idx)
                    detected_board.set_piece_at(square_idx, chess.Piece.from_symbol(best_piece))
                    
        return detected_board
