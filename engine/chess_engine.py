import sys
import os
import subprocess
import chess
import chess.engine

class IllegalInstructionError(Exception):
    """Exception raised when Stockfish crashes due to CPU instruction set mismatch (e.g. BMI2 on non-BMI2 CPU)."""
    pass

class ChessEngine:
    def __init__(self, stockfish_path=None, depth=20, threads=None, hash_size=256, time_limit=0.5, log_callback=None):
        self.stockfish_path = stockfish_path
        self.depth = depth
        self.threads = threads if threads else (os.cpu_count() if os.cpu_count() else 1)
        self.hash_size = hash_size
        self.time_limit = time_limit
        self.log_callback = log_callback
        self.local_engine = None

    def _log(self, message):
        """Helper to send engine logs to the GUI log or stdout."""
        if self.log_callback:
            self.log_callback(f"[Engine] {message}")
        else:
            try:
                print(f"[Engine] {message}")
            except Exception:
                pass

    def set_stockfish_path(self, path):
        if self.stockfish_path != path:
            self.stockfish_path = path
            # Stop the existing local engine process so it relaunches with the new path
            self.stop_local_engine()

    def set_depth(self, depth):
        self.depth = depth

    def set_threads(self, threads):
        if self.threads != threads:
            self.threads = threads
            # Restart engine to apply threads change
            self.stop_local_engine()

    def set_hash_size(self, hash_size):
        if self.hash_size != hash_size:
            self.hash_size = hash_size
            # Restart engine to apply hash change
            self.stop_local_engine()

    def set_time_limit(self, time_limit):
        self.time_limit = time_limit

    def get_best_move(self, board: chess.Board):
        """
        Computes the best move for the given board using local Stockfish.
        Returns a chess.Move object, or None if no move could be determined.
        """
        if board.is_game_over():
            return None
            
        if not board.is_valid():
            self._log("Warning: Chess board state is invalid (e.g., missing kings). Cannot calculate moves.")
            return None
            
        if self.stockfish_path:
            return self._get_local_move(board)
            
        return None

    def _ensure_local_engine(self):
        """Ensures that a persistent Stockfish process is running."""
        if self.local_engine is not None:
            # Check if process is still alive and responsive
            try:
                if self.local_engine.subprocess and self.local_engine.subprocess.poll() is None:
                    return True
            except Exception:
                self.stop_local_engine()

        if not self.stockfish_path or not os.path.exists(self.stockfish_path):
            self._log("Local Stockfish path is empty or does not exist.")
            return False

        try:
            # On Windows, suppress the black console window popup (CREATE_NO_WINDOW = 0x08000000)
            popen_args = {}
            if sys.platform == "win32":
                popen_args["creationflags"] = 0x08000000
                
            self.local_engine = chess.engine.SimpleEngine.popen_uci(
                self.stockfish_path, 
                **popen_args
            )
            
            # Configure engine with user-selected Threads and Hash size
            try:
                self.local_engine.configure({
                    "Threads": self.threads,
                    "Hash": self.hash_size
                })
                self._log(f"Started Stockfish from: {self.stockfish_path} (Using {self.threads} CPU threads, {self.hash_size}MB hash)")
            except Exception as opt_err:
                self._log(f"Started Stockfish from: {self.stockfish_path} (Options configuration skipped: {opt_err})")
                
            return True
        except Exception as e:
            err_str = str(e)
            # Detect STATUS_ILLEGAL_INSTRUCTION (0xC000001D / 3221225477 / -1073741795)
            if "3221225477" in err_str or "0xC000001D" in err_str or "0xc000001d" in err_str or "-1073741795" in err_str:
                self._log("CRITICAL: Stockfish crashed with exit code 3221225477 (Illegal Instruction).")
                raise IllegalInstructionError(
                    "Stockfish crashed due to an Illegal Instruction (0xC000001D). "
                    "This usually means you are running a BMI2 build on a CPU that doesn't support BMI2 instructions. "
                    "Please download the standard x86-64 or modern version of Stockfish instead."
                ) from e
                
            self._log(f"Failed to start local Stockfish: {e}")
            self.local_engine = None
            return False

    def _get_local_move(self, board: chess.Board):
        """Uses the persistent local Stockfish process to get best move."""
        if not self._ensure_local_engine():
            return None
            
        try:
            # Apply both user-configured time limit and depth limit dynamically
            result = self.local_engine.play(board, chess.engine.Limit(time=self.time_limit, depth=self.depth))
            return result.move
        except Exception as e:
            err_str = str(e)
            if "3221225477" in err_str or "0xC000001D" in err_str or "0xc000001d" in err_str or "-1073741795" in err_str:
                raise IllegalInstructionError(
                    "Stockfish crashed due to an Illegal Instruction (0xC000001D) during calculation. "
                    "Please select a compatible Stockfish build."
                ) from e
                
            self._log(f"Local Stockfish calculation error: {e}")
            # If the engine crashed, shut down and clean up
            self.stop_local_engine()
            
        return None

    def stop_local_engine(self):
        """Cleanly stops the persistent Stockfish process."""
        if self.local_engine is not None:
            try:
                self._log("Stopping persistent Stockfish process...")
                self.local_engine.quit()
            except Exception as e:
                self._log(f"Error stopping Stockfish: {e}")
                # Force kill if needed
                try:
                    if self.local_engine.subprocess:
                        self.local_engine.subprocess.kill()
                except Exception:
                    pass
            finally:
                self.local_engine = None

    def __del__(self):
        self.stop_local_engine()
