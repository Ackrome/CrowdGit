import tkinter as tk
from PIL import Image, ImageTk
import os
import sys
from typing import List
import logging


class LoadingWindow(tk.Tk):
    """
    A window that displays a loading GIF animation.
    """

    def __init__(self):
        super().__init__()
        self.title("Loading...")
        self.resizable(False, False)

        self.gif_path: str = self._get_gif_path()
        self.frames: List[ImageTk.PhotoImage] = []
        self.current_image: ImageTk.PhotoImage | None = None

        self.loading_label: tk.Label = tk.Label(self)
        self.loading_label.pack()

        self._load_gif()

        self._set_window_size()
        self._center_window()

        if self.frames:
            self._display_first_frame()
            self._start_animation()

    def _get_gif_path(self) -> str:
        """Constructs the path to the loading GIF."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, 'icons', 'loading.gif')

    def _load_gif(self) -> None:
        """Loads the GIF frames and stores them as PhotoImage objects."""
        try:
            with Image.open(self.gif_path) as gif:
                for i in range(gif.n_frames):
                    gif.seek(i)
                    photo = ImageTk.PhotoImage(gif.copy())
                    self.frames.append(photo)
        except Exception as e:
            logging.error(f"Error loading GIF: {e}")
            raise

    def _set_window_size(self) -> None:
        """Sets the window size to match the GIF dimensions."""
        try:
            with Image.open(self.gif_path) as gif:
                self.gif_width, self.gif_height = gif.size
            self.geometry(f"{self.gif_width}x{self.gif_height}")
        except Exception as e:
            logging.error(f"Error setting window size: {e}")
            raise

    def _center_window(self) -> None:
        """Centers the window on the screen."""
        self.update_idletasks()
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"+{x}+{y}")

    def _display_first_frame(self) -> None:
        """Displays the first frame of the GIF."""
        if self.frames:
            self.loading_label.config(image=self.frames[0])
            self.current_image = self.frames[0]

    def _start_animation(self) -> None:
        """Starts the GIF animation."""
        if len(self.frames) > 1:
            self.after(100, self._animate, 1)
        else:
            self.after(100, self._animate, 0)

    def _animate(self, frame_index: int) -> None:
        """Animates the GIF."""
        if self.frames:
            frame = self.frames[frame_index]
            self.loading_label.config(image=frame)
            self.current_image = frame
            frame_index += 1
            if frame_index == len(self.frames):
                frame_index = 0
            self.after(10, self._animate, frame_index)

if __name__ == "__main__":
    app = LoadingWindow()
    app.after(10000, app.destroy)  # Close the window after 10 seconds
    app.mainloop()