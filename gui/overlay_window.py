import math
from PySide6 import QtCore, QtGui, QtWidgets

class OverlayWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set window flags: frameless, stay on top, tool window (doesn't show in taskbar)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint | 
            QtCore.Qt.WindowType.WindowStaysOnTopHint | 
            QtCore.Qt.WindowType.Tool
        )
        
        # Support translucent background
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Set initial size and position
        self.setGeometry(100, 100, 600, 600)
        
        # Overlay States
        self.setup_mode = True  # True = Resizable/Draggable, False = Click-through
        self.perspective = "white"  # "white" or "black"
        self.best_move = None  # chess.Move object
        
        # Timer to automatically clear/fade the recommendation arrow
        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self.clear_best_move)
        
        # Drag and Resize handling state
        self.is_dragging = False
        self.is_resizing = False
        self.drag_offset = QtCore.QPoint()
        self.resize_edges = 0  # Bitmask: 1=Left, 2=Right, 4=Top, 8=Bottom
        self.resize_margin = 10
        
        # Enable mouse tracking to change cursor shapes when hovering borders
        self.setMouseTracking(True)

    def set_setup_mode(self, enabled):
        """Toggles between Setup Mode (interactive) and Analyze Mode (click-through)."""
        self.setup_mode = enabled
        
        # Update window flags to enable/disable input transparency
        flags = (
            QtCore.Qt.WindowType.FramelessWindowHint | 
            QtCore.Qt.WindowType.WindowStaysOnTopHint | 
            QtCore.Qt.WindowType.Tool
        )
        
        if not self.setup_mode:
            # Click-through flag
            flags |= QtCore.Qt.WindowType.WindowTransparentForInput
            
        self.setWindowFlags(flags)
        
        # Restore normal cursor if exiting setup mode
        if not self.setup_mode:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            
        # Re-show window to apply flags (required in Qt)
        self.show()
        self.update()

    def set_perspective(self, perspective):
        self.perspective = perspective
        self.update()

    def set_best_move(self, move):
        self.best_move = move
        self.fade_timer.stop()
        self.update()
        if move is not None:
            # Automatically clear/hide the arrow after 5 seconds
            self.fade_timer.start(5000)

    def clear_best_move(self):
        self.best_move = None
        self.update()

    # --- Mouse Events for Dragging & Resizing ---
    
    def _get_resize_edges(self, pos):
        """Returns a bitmask of which edges the cursor is over."""
        edges = 0
        w, h = self.width(), self.height()
        
        if pos.x() < self.resize_margin:
            edges |= 1  # Left
        elif pos.x() > w - self.resize_margin:
            edges |= 2  # Right
            
        if pos.y() < self.resize_margin:
            edges |= 4  # Top
        elif pos.y() > h - self.resize_margin:
            edges |= 8  # Bottom
            
        return edges

    def _update_cursor_shape(self, edges):
        """Sets the appropriate cursor shape based on edge proximity."""
        if edges == 0:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            return
            
        # Standard Qt cursor mapping
        if (edges & 1 and edges & 4) or (edges & 2 and edges & 8):  # TopLeft or BottomRight
            self.setCursor(QtCore.Qt.CursorShape.SizeFDiagCursor)
        elif (edges & 2 and edges & 4) or (edges & 1 and edges & 8):  # TopRight or BottomLeft
            self.setCursor(QtCore.Qt.CursorShape.SizeBDiagCursor)
        elif edges & 1 or edges & 2:  # Left or Right
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        elif edges & 4 or edges & 8:  # Top or Bottom
            self.setCursor(QtCore.Qt.CursorShape.SizeVerCursor)

    def mousePressEvent(self, event):
        if not self.setup_mode:
            super().mousePressEvent(event)
            return
            
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            edges = self._get_resize_edges(event.position().toPoint())
            if edges != 0:
                self.is_resizing = True
                self.resize_edges = edges
                self.resize_start_geometry = self.geometry()
                self.resize_start_global = event.globalPosition().toPoint()
            else:
                self.is_dragging = True
                self.drag_offset = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.setup_mode:
            super().mouseMoveEvent(event)
            return
            
        global_pos = event.globalPosition().toPoint()
        
        if self.is_resizing:
            # Resizing logic (locked to 1:1 aspect ratio)
            geom = self.resize_start_geometry
            diff = global_pos - self.resize_start_global
            
            x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
            min_size = 200
            
            # Determine size based on dominant change (to maintain 1:1 aspect ratio)
            if self.resize_edges & (1 | 2):  # Left or Right dragging
                size = max(min_size, w + (diff.x() if self.resize_edges & 2 else -diff.x()))
            elif self.resize_edges & (4 | 8):  # Top or Bottom dragging
                size = max(min_size, h + (diff.y() if self.resize_edges & 8 else -diff.y()))
            else:
                # Diagonal dragging: average the changes
                size = max(min_size, (w + h) // 2)
                
            # If resizing Left or Top, adjust x and y coordinates so the opposite corner remains anchored
            if self.resize_edges & 1:  # Left
                x = geom.x() + geom.width() - size
            if self.resize_edges & 4:  # Top
                y = geom.y() + geom.height() - size
                
            self.setGeometry(x, y, size, size)
            event.accept()
            
        elif self.is_dragging:
            # Dragging logic
            self.move(global_pos - self.drag_offset)
            event.accept()
            
        else:
            # Not clicking: update cursors
            edges = self._get_resize_edges(event.position().toPoint())
            self._update_cursor_shape(edges)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.is_resizing = False
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    # --- Drawing Logic ---
    
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 1. Setup Mode Grid & Borders
        if self.setup_mode:
            # Fill with subtle semi-transparent black overlay
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 40))
            
            # Draw outer border
            border_pen = QtGui.QPen(QtGui.QColor(0, 120, 215, 200), 3)
            painter.setPen(border_pen)
            painter.drawRect(0, 0, w - 1, h - 1)
            
            # Draw 8x8 Grid guide lines
            grid_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 100), 1, QtCore.Qt.PenStyle.DashLine)
            painter.setPen(grid_pen)
            
            sq_w = w / 8.0
            sq_h = h / 8.0
            
            for i in range(1, 8):
                # Vertical lines
                painter.drawLine(QtCore.QLineF(i * sq_w, 0, i * sq_w, h))
                # Horizontal lines
                painter.drawLine(QtCore.QLineF(0, i * sq_h, w, i * sq_h))
                
            # Draw indicator text in the center
            font = painter.font()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220)))
            painter.drawText(
                self.rect(), 
                QtCore.Qt.AlignmentFlag.AlignCenter, 
                "ALIGN OVER CHESS BOARD\n(Drag center to move, edges to resize)"
            )
            
        else:
            # Analyze Mode: Draw subtle active border (very thin, semi-transparent)
            active_pen = QtGui.QPen(QtGui.QColor(0, 255, 0, 80), 1)
            painter.setPen(active_pen)
            painter.drawRect(0, 0, w - 1, h - 1)
            
            # Draw recommended best move arrow
            if self.best_move:
                self._draw_best_move_arrow(painter)

    def _draw_best_move_arrow(self, painter):
        """Draws a beautiful semi-transparent arrow representing the best move."""
        w, h = self.width(), self.height()
        sq_w = w / 8.0
        sq_h = h / 8.0
        
        # Extract squares from move
        from_sq = self.best_move.from_square
        to_sq = self.best_move.to_square
        
        # Get rank/file (0-7)
        from_file = from_sq % 8
        from_rank = from_sq // 8
        
        to_file = to_sq % 8
        to_rank = to_sq // 8
        
        # Map to screen coordinates based on perspective
        if self.perspective == "white":
            # White at bottom: rank 0 is Row 7, rank 7 is Row 0
            from_row = 7 - from_rank
            from_col = from_file
            to_row = 7 - to_rank
            to_col = to_file
        else:
            # Black at bottom: rank 0 is Row 0, rank 7 is Row 7
            # file 0 is Col 7, file 7 is Col 0
            from_row = from_rank
            from_col = 7 - from_file
            to_row = to_rank
            to_col = 7 - to_file
            
        # Calculate screen center coordinates
        x1 = (from_col + 0.5) * sq_w
        y1 = (from_row + 0.5) * sq_h
        x2 = (to_col + 0.5) * sq_w
        y2 = (to_row + 0.5) * sq_h
        
        p1 = QtCore.QPointF(x1, y1)
        p2 = QtCore.QPointF(x2, y2)
        
        # Draw square highlights
        # Start square: subtle orange highlight
        start_highlight_color = QtGui.QColor(255, 165, 0, 80)
        painter.fillRect(
            QtCore.QRectF(from_col * sq_w, from_row * sq_h, sq_w, sq_h), 
            start_highlight_color
        )
        
        # End square: subtle green highlight
        end_highlight_color = QtGui.QColor(0, 255, 0, 80)
        painter.fillRect(
            QtCore.QRectF(to_col * sq_w, to_row * sq_h, sq_w, sq_h), 
            end_highlight_color
        )
        
        # Compute line parameters
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 10:
            return
            
        ux = dx / length
        uy = dy / length
        
        # Vector perpendicular to direction
        vx = -uy
        vy = ux
        
        # Design parameters
        shaft_width = max(6.0, sq_w * 0.1)  # Scale with square width
        arrowhead_len = max(20.0, sq_w * 0.3)
        arrowhead_width = max(15.0, sq_w * 0.22)
        
        # Subtract arrowhead length from line drawing
        p_base = QtCore.QPointF(x2 - ux * arrowhead_len, y2 - uy * arrowhead_len)
        
        # Arrow shaft pen
        arrow_color = QtGui.QColor(0, 200, 80, 200) # Nice solid green
        shaft_pen = QtGui.QPen(arrow_color, shaft_width, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(shaft_pen)
        painter.drawLine(p1, p_base)
        
        # Draw arrowhead polygon
        p_left = QtCore.QPointF(p_base.x() + vx * arrowhead_width, p_base.y() + vy * arrowhead_width)
        p_right = QtCore.QPointF(p_base.x() - vx * arrowhead_width, p_base.y() - vy * arrowhead_width)
        
        arrowhead_polygon = QtGui.QPolygonF([p2, p_left, p_right])
        
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(arrow_color))
        painter.drawPolygon(arrowhead_polygon)
