import cv2
import numpy as np
import time
from vision.board_detector import BoardDetector
import os

def test_performance():
    print("Running performance test for BoardDetector.detect_board...")

    # Create mock calibration data
    test_cal_dir = "perf_calibration"
    detector = BoardDetector(calibration_dir=test_cal_dir)

    # Setup some mock templates for testing
    bg_colors = ["light", "dark"]
    pieces = ["empty"] + list("PRNBQKprnbqk")
    for bg in bg_colors:
        for piece in pieces:
            # Random RGB image for template
            img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            detector.templates[(piece, bg)] = img

    detector.is_calibrated = True

    # Create a mock board image
    board_img = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)

    start_time = time.time()
    iterations = 100
    for _ in range(iterations):
        detector.detect_board(board_img)
    end_time = time.time()

    elapsed = end_time - start_time
    print(f"Elapsed time for {iterations} board detections: {elapsed:.4f} seconds")
    print(f"Average time per board detection: {(elapsed / iterations) * 1000:.4f} ms")

    # Cleanup
    for file in os.listdir(test_cal_dir):
        os.remove(os.path.join(test_cal_dir, file))
    os.rmdir(test_cal_dir)

if __name__ == "__main__":
    test_performance()
