import tkinter as tk
from tkinter import ttk



class ToolTip:
    """
    Creates a tooltip for a given widget.
    """

    def __init__(self, widget, text="widget info"):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(100, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self, event=None):
        if self.widget.winfo_exists():
            x = y = 0
            if isinstance(self.widget, (tk.Entry, tk.Text, ttk.Treeview)):
                # Handle Entry, Text, and Treeview widgets differently
                x, y = self.widget.winfo_rootx(), self.widget.winfo_rooty()
                cx, cy = self.widget.winfo_width(), self.widget.winfo_height()
                x += 25
                y += 20
            else:
                bbox = self.widget.bbox()  # Get the bounding box of the entire widget
                if bbox is not None:
                    x, y, cx, cy = bbox
                    x += self.widget.winfo_rootx() + 25
                    y += self.widget.winfo_rooty() + 20
            # creates a toplevel window
            self.tw = tk.Toplevel(self.widget)
            # Leaves only the label and removes the app window
            self.tw.wm_overrideredirect(True)
            self.tw.wm_geometry("+%d+%d" % (x, y))
            label = tk.Label(
                self.tw,
                text=self.text,
                justify="left",
                background="#ffffff",
                relief="solid",
                borderwidth=1,
                font=("tahoma", "8", "normal"),
            )
            label.pack(ipadx=1)




    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()