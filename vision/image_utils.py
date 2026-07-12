import cv2
import numpy as np

def get_similarity(img1, img2):
    """
    Computes a similarity score between two images of the same size.
    Uses normalized correlation on grayscale representations.
    """
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    
    # Check standard deviation to avoid division by zero in matchTemplate
    std1 = np.std(gray1)
    std2 = np.std(gray2)
    
    if std1 < 1.0 or std2 < 1.0:
        return 0.0  # One is flat, cannot correlate with a piece template
        
    res = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
    score = float(res[0][0])
    
    # Scale from [-1, 1] to [0, 1]
    return max(0.0, (score + 1.0) / 2.0)


def extract_piece_mask(piece_img, empty_bg_img, threshold=15):
    """
    Creates a binary mask of the piece by comparing it to the empty background.
    Returns a mask where 255 represents the piece and 0 represents the background.
    """
    if piece_img.shape != empty_bg_img.shape:
        empty_bg_img = cv2.resize(empty_bg_img, (piece_img.shape[1], piece_img.shape[0]))
        
    # Absolute difference
    diff = cv2.absdiff(piece_img, empty_bg_img)
    # Convert to grayscale
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    
    # Thresholding
    _, mask = cv2.threshold(gray_diff, threshold, 255, cv2.THRESH_BINARY)
    
    # Morphological clean up (close holes, slightly dilate to avoid border artifacts)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
    
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    mask = cv2.dilate(mask, kernel_dilate, iterations=1)
    
    return mask

def synthesize_piece_on_background(piece_img, source_bg_img, target_bg_img, threshold=15):
    """
    Extracts a piece from its source background and overlays it onto a target background.
    """
    if piece_img.shape != target_bg_img.shape:
        target_bg_img = cv2.resize(target_bg_img, (piece_img.shape[1], piece_img.shape[0]))
        
    mask = extract_piece_mask(piece_img, source_bg_img, threshold)
    
    # Synthesized image starts as target background
    synthesized = target_bg_img.copy()
    
    # Copy piece pixels where mask is active
    synthesized[mask == 255] = piece_img[mask == 255]
    
    return synthesized
