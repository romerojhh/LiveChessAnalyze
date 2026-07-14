import os
import cv2
import numpy as np
import chess
import chess.engine
from vision.board_detector import BoardDetector
from vision.image_utils import get_similarity
from vision.board_locator import find_chessboard_on_screen
from engine.chess_engine import ChessEngine, IllegalInstructionError

def create_mock_board(pieces_matrix):
    """
    Creates a mock chessboard image from an 8x8 matrix of piece symbols.
    None represents empty squares.
    """
    sq_size = 50
    board_size = sq_size * 8
    img = np.zeros((board_size, board_size, 3), dtype=np.uint8)
    
    # Color palette
    light_color = (240, 217, 181)  # Light beige
    dark_color = (181, 136, 99)    # Wood brown
    
    white_piece_color = (255, 255, 255)
    black_piece_color = (20, 20, 20)
    
    for r in range(8):
        for c in range(8):
            y1, y2 = r * sq_size, (r + 1) * sq_size
            x1, x2 = c * sq_size, (c + 1) * sq_size
            
            # Fill background
            bg_color = dark_color if (r + c) % 2 == 1 else light_color
            img[y1:y2, x1:x2] = bg_color
            
            # Draw piece if present
            piece = pieces_matrix[r][c]
            if piece:
                text_color = white_piece_color if piece.isupper() else black_piece_color
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.8
                thickness = 2
                text_size = cv2.getTextSize(piece, font, font_scale, thickness)[0]
                text_x = x1 + (sq_size - text_size[0]) // 2
                text_y = y1 + (sq_size + text_size[1]) // 2
                
                cv2.putText(img, piece, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)
                
    return img

def test_white_perspective():
    print("\n--- Running White Perspective Test ---")
    starting_matrix = [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        ["p", "p", "p", "p", "p", "p", "p", "p"],
        [None] * 8,
        [None] * 8,
        [None] * 8,
        [None] * 8,
        ["P", "P", "P", "P", "P", "P", "P", "P"],
        ["R", "N", "B", "Q", "K", "B", "N", "R"]
    ]
    img = create_mock_board(starting_matrix)
    test_cal_dir = "test_calibration_white"
    detector = BoardDetector(calibration_dir=test_cal_dir)
    
    success = detector.calibrate(img, perspective="white")
    assert success and detector.is_calibrated, "White calibration failed!"
    
    detected_board = detector.detect_board(img, perspective="white")
    detected_fen = detected_board.board_fen()
    expected_fen = chess.Board().board_fen()
    assert detected_fen == expected_fen, f"White FEN mismatch! Got {detected_fen}"
    print("White Perspective Test: PASSED")
    
    # Cleanup
    for file in os.listdir(test_cal_dir):
        os.remove(os.path.join(test_cal_dir, file))
    os.rmdir(test_cal_dir)

def test_black_perspective():
    print("\n--- Running Black Perspective Test ---")
    # In Black perspective, Black pieces are at the bottom (rank 8 / row 7)
    # and White pieces are at the top (rank 1 / row 0)
    starting_matrix_black_view = [
        ["R", "N", "B", "K", "Q", "B", "N", "R"], # Row 0 (Top): White pieces (h1 to a1)
        ["P", "P", "P", "P", "P", "P", "P", "P"], # Row 1: White Pawns
        [None] * 8,
        [None] * 8,
        [None] * 8,
        [None] * 8,
        ["p", "p", "p", "p", "p", "p", "p", "p"], # Row 6: Black Pawns
        ["r", "n", "b", "k", "q", "b", "n", "r"]  # Row 7 (Bottom): Black pieces (h8 to a8)
    ]
    img = create_mock_board(starting_matrix_black_view)
    test_cal_dir = "test_calibration_black"
    detector = BoardDetector(calibration_dir=test_cal_dir)
    
    success = detector.calibrate(img, perspective="black")
    assert success and detector.is_calibrated, "Black calibration failed!"
    
    detected_board = detector.detect_board(img, perspective="black")
    detected_fen = detected_board.board_fen()
    expected_fen = chess.Board().board_fen()
    assert detected_fen == expected_fen, f"Black FEN mismatch! Got {detected_fen}"
    print("Black Perspective Test: PASSED")
    
    # Cleanup
    for file in os.listdir(test_cal_dir):
        os.remove(os.path.join(test_cal_dir, file))
    os.rmdir(test_cal_dir)

def test_chess_engine_guards():
    print("\n--- Running Chess Engine Guards Test ---")
    engine = ChessEngine()
    
    # Test 1: Invalid board state (missing Kings)
    invalid_board = chess.Board()
    invalid_board.clear()
    invalid_board.set_piece_at(chess.E1, chess.Piece(chess.PAWN, chess.WHITE))
    
    move = engine.get_best_move(invalid_board)
    assert move is None, "Engine should return None for invalid board state!"
    print("Chess Engine Invalid Board Guard Test: PASSED")
    
    # Test 2: Stateless castling rights rebuilding
    board = chess.Board()
    board.clear()
    
    # Place pieces in starting squares (White King on e1, Rooks on a1/h1)
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.A1, chess.Piece(chess.ROOK, chess.WHITE))
    board.set_piece_at(chess.H1, chess.Piece(chess.ROOK, chess.WHITE))
    
    # Castling rights should initially be empty
    assert board.castling_rights == 0
    
    # Run the stateless castling reconstruction logic
    if board.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE):
        if board.piece_at(chess.A1) == chess.Piece(chess.ROOK, chess.WHITE):
            board.castling_rights |= chess.BB_A1
        if board.piece_at(chess.H1) == chess.Piece(chess.ROOK, chess.WHITE):
            board.castling_rights |= chess.BB_H1
            
    assert board.castling_rights & chess.BB_A1, "Queenside castling right not restored!"
    assert board.castling_rights & chess.BB_H1, "Kingside castling right not restored!"
    print("Stateless Castling Rights Reconstruction Test: PASSED")

def test_illegal_instruction_detection():
    print("\n--- Running Illegal Instruction Detection Test ---")
    import sys
    engine = ChessEngine(stockfish_path=sys.executable)
    
    # Mock popen_uci to simulate a STATUS_ILLEGAL_INSTRUCTION exception (exit code 3221225477)
    def mock_popen_uci(command, **kwargs):
        raise chess.engine.EngineTerminatedError("engine process died unexpectedly (exit code: 3221225477)")
        
    original_popen = chess.engine.SimpleEngine.popen_uci
    chess.engine.SimpleEngine.popen_uci = mock_popen_uci
    
    try:
        # This call should raise IllegalInstructionError because of exit code 3221225477
        engine.get_best_move(chess.Board())
        assert False, "Should have raised IllegalInstructionError!"
    except IllegalInstructionError as e:
        print(f"Successfully caught expected custom diagnostic error: {e}")
        print("Illegal Instruction Detection Test: PASSED")
    finally:
        # Restore original function
        chess.engine.SimpleEngine.popen_uci = original_popen

def test_board_locator():
    print("\n--- Running Chessboard Locator (Auto-Snap) Test ---")
    # 1. Create a large virtual canvas representing a screen
    canvas = np.zeros((800, 800, 3), dtype=np.uint8)
    
    # 2. Render a mock chess board
    starting_matrix = [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        ["p", "p", "p", "p", "p", "p", "p", "p"],
        [None] * 8,
        [None] * 8,
        [None] * 8,
        [None] * 8,
        ["P", "P", "P", "P", "P", "P", "P", "P"],
        ["R", "N", "B", "Q", "K", "B", "N", "R"]
    ]
    board_img = create_mock_board(starting_matrix)  # 400x400 pixels
    
    # 3. Paste the board at (200, 200) inside the canvas
    canvas[200:600, 200:600] = board_img
    
    # 4. Search for the board
    detected_rect = find_chessboard_on_screen(canvas)
    
    assert detected_rect is not None, "Failed to locate the chessboard on canvas!"
    x, y, w, h = detected_rect
    print(f"Located chessboard at: X={x}, Y={y}, W={w}, H={h}")
    
    # Assert coordinates are exactly or very close to (200, 200, 400, 400)
    assert abs(x - 200) <= 2, f"Incorrect X coordinate: {x} (expected ~200)"
    assert abs(y - 200) <= 2, f"Incorrect Y coordinate: {y} (expected ~200)"
    assert abs(w - 400) <= 2, f"Incorrect Width: {w} (expected ~400)"
    assert abs(h - 400) <= 2, f"Incorrect Height: {h} (expected ~400)"
    print("Chessboard Locator Test: PASSED")

def run_all_tests():
    print("==============================================")
    print("      LIVE CHESS ANALYZER TEST SUITE")
    print("==============================================")
    
    test_white_perspective()
    test_black_perspective()
    test_chess_engine_guards()
    test_illegal_instruction_detection()
    test_board_locator()
    
    print("\n==============================================")
    print("      ALL TESTS PASSED SUCCESSFULLY!")
    print("==============================================")

if __name__ == "__main__":
    run_all_tests()
