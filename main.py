import sys
from PySide6 import QtWidgets, QtCore
from gui.overlay_window import OverlayWindow
from gui.control_panel import ControlPanel

def main():
    # Enable High DPI scaling
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')  # Standard clean style
    
    # 1. Create overlay window (capturing and rendering)
    overlay = OverlayWindow()
    
    # 2. Create control panel (pass overlay reference)
    panel = ControlPanel(overlay)
    
    # 3. Position control panel nicely relative to overlay
    # Put overlay at center of screen, and control panel to the right of it
    screen = QtWidgets.QApplication.primaryScreen().geometry()
    
    overlay_width, overlay_height = 500, 500
    panel_width, panel_height = 420, 520
    
    # Calculate positions
    overlay_x = (screen.width() - overlay_width - panel_width) // 2
    overlay_y = (screen.height() - overlay_height) // 2
    
    panel_x = overlay_x + overlay_width + 20
    panel_y = overlay_y - (panel_height - overlay_height) // 2
    
    overlay.setGeometry(overlay_x, overlay_y, overlay_width, overlay_height)
    panel.setGeometry(panel_x, panel_y, panel_width, panel_height)
    
    # 4. Show both windows
    overlay.show()
    panel.show()
    
    # 5. Clean exit
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
