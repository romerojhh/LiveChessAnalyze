import cv2
import numpy as np
import mss

def get_iou(rect1, rect2):
    """
    Computes Intersection over Union (IoU) of two rectangles.
    Rect format: (x, y, w, h)
    """
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2

    # Calculate intersection coordinates
    ix = max(x1, x2)
    iy = max(y1, y2)
    iw = min(x1 + w1, x2 + w2) - ix
    ih = min(y1 + h1, y2 + h2) - iy

    if iw <= 0 or ih <= 0:
        return 0.0

    intersection = iw * ih
    union = (w1 * h1) + (w2 * h2) - intersection
    return intersection / union

def evaluate_chessboard_score(img, x, y, w, h):
    """
    Evaluates how likely a region is a chessboard.
    Samples the top-left region of each of the 8x8 grid squares.
    """
    sq_w = w / 8.0
    sq_h = h / 8.0

    # Sample offset from top-left of each square (e.g. 15%)
    # to avoid pieces typically centered in the middle 70% of the square.
    offset_x = int(sq_w * 0.15)
    offset_y = int(sq_h * 0.15)

    colors_light = []
    colors_dark = []

    img_h, img_w = img.shape[:2]

    for r in range(8):
        for c in range(8):
            sp_x = int(x + c * sq_w + offset_x)
            sp_y = int(y + r * sq_h + offset_y)

            # Check boundaries
            if sp_x < 0 or sp_x >= img_w or sp_y < 0 or sp_y >= img_h:
                return 0.0

            # Sample a 3x3 patch around the point and take the average color
            y1 = max(0, sp_y - 1)
            y2 = min(img_h, sp_y + 2)
            x1 = max(0, sp_x - 1)
            x2 = min(img_w, sp_x + 2)

            patch = img[y1:y2, x1:x2]
            if patch.size == 0:
                continue
            avg_color = np.mean(patch, axis=(0, 1)) # BGR values

            if (r + c) % 2 == 0:
                colors_light.append(avg_color)
            else:
                colors_dark.append(avg_color)

    if len(colors_light) < 32 or len(colors_dark) < 32:
        return 0.0

    colors_light = np.array(colors_light)
    colors_dark = np.array(colors_dark)

    # Compute mean and standard dev of each channel (B, G, R)
    mean_light = np.mean(colors_light, axis=0)
    mean_dark = np.mean(colors_dark, axis=0)

    std_light = np.mean(np.std(colors_light, axis=0))
    std_dark = np.mean(np.std(colors_dark, axis=0))

    # Euclidean distance between means in color space
    dist = np.linalg.norm(mean_light - mean_dark)

    # Score is: contrast distance divided by average standard deviation of colors within groups.
    # Higher score = clearer checkerboard pattern.
    score = dist / (std_light + std_dark + 1.0)
    return float(score)

def find_chessboard_on_screen(screen_img):
    """
    Finds the bounding box of a chessboard on the screen image.
    Returns (x, y, w, h) of the board in screen_img coordinates, or None if not found.
    """
    gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)

    # Apply bilateral filter to preserve edges while smoothing noise
    blurred = cv2.bilateralFilter(gray, 9, 75, 75)

    # Edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Find all contours on the edge image
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    screen_h, screen_w = screen_img.shape[:2]
    min_board_size = 200
    max_board_size = min(screen_h, screen_w)

    for contour in contours:
        # Approximate contour to polygon
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        # Bounding rect
        x, y, w, h = cv2.boundingRect(approx)

        # Must be within reasonable size limits and roughly square aspect ratio
        if min_board_size <= w <= max_board_size and min_board_size <= h <= max_board_size:
            aspect_ratio = float(w) / h
            if 0.95 <= aspect_ratio <= 1.05:
                candidates.append((x, y, w, h))

    if not candidates:
        return None

    # Evaluate checkerboard score for all candidates
    scored_candidates = []
    for rect in candidates:
        score = evaluate_chessboard_score(screen_img, *rect)
        if score >= 1.5:  # Confident chessboard score threshold
            scored_candidates.append((rect, score))

    if not scored_candidates:
        return None

    # Sort by score descending
    scored_candidates = sorted(scored_candidates, key=lambda pair: pair[1], reverse=True)

    # Deduplicate overlapping candidates (keeping the one with the higher score)
    unique_candidates = []
    for rect, score in scored_candidates:
        overlap = False
        for u_rect, _ in unique_candidates:
            if get_iou(rect, u_rect) > 0.5:
                overlap = True
                break
        if not overlap:
            unique_candidates.append((rect, score))

    if unique_candidates:
        # Return the highest-scoring candidate rect
        return unique_candidates[0][0]

    return None
