"""Optional click-wheel layout, drawn locally without external image assets."""
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from ui_icons import transport_icon

RETRO_THEMES = {
    "Retro · Ezüst": {
        "COLOR_DARK_BG": "#b8b5b1", "COLOR_MAIN_CONTAINER": "#dedbd7",
        "COLOR_PLAYLIST_BG": "#f0f3e9", "COLOR_BUTTON_NORMAL": "#c8c5c0",
        "COLOR_ACCENT": "#327ab5", "COLOR_NOW_PLAYING_TITLE": "#30363a",
        "COLOR_DRAG_BORDER_NORMAL": "#a9b4b5", "COLOR_GENERAL_FOREGROUND": "#26312d",
        "COLOR_TEXT_DARK": "#ffffff",
    },
    "Retro · Rózsaszín": {
        "COLOR_DARK_BG": "#9b3c67", "COLOR_MAIN_CONTAINER": "#d87ca7",
        "COLOR_PLAYLIST_BG": "#f2f3eb", "COLOR_BUTTON_NORMAL": "#e8aac7",
        "COLOR_ACCENT": "#913b69", "COLOR_NOW_PLAYING_TITLE": "#492336",
        "COLOR_DRAG_BORDER_NORMAL": "#b96189", "COLOR_GENERAL_FOREGROUND": "#392631",
        "COLOR_TEXT_DARK": "#ffffff",
    },
}


class RetroWheel(tk.Canvas):
    def __init__(self, master, app, background, center):
        super().__init__(master, width=144, height=132, bg=background,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.app = app
        colors = app.colors
        scale = 3
        image = Image.new("RGBA", (164*scale, 150*scale), background)
        draw = ImageDraw.Draw(image)
        def oval(box, fill, outline=None):
            draw.ellipse(tuple(int(v*scale) for v in box), fill=fill, outline=outline, width=scale)
        oval((9, 3, 157, 149), colors['WHEEL_BORDER'])
        oval((8, 1, 156, 147), colors['WHEEL_FACE'], colors['WHEEL_BORDER'])
        oval((53, 45, 111, 103), center, colors['WHEEL_BORDER'])
        self.art = ImageTk.PhotoImage(image.resize((144, 132), Image.Resampling.LANCZOS))
        self.create_image(0, 0, anchor="nw", image=self.art)
        self.create_text(72, 21, text="MENU", font=("Segoe UI Semibold", 10), fill=colors['WHEEL_TEXT'])
        self.icons = {}
        for kind, x, y in (("previous", 29, 75), ("next", 135, 75), ("stop", 82, 125)):
            self.icons[kind] = ImageTk.PhotoImage(transport_icon(kind, colors['WHEEL_TEXT'], 19))
            self.create_image(x*144/164, y*132/150, image=self.icons[kind])
        self.play_item = self.create_image(72, 66)
        self.set_playing(False)
        self.bind("<Button-1>", self.clicked)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(sequence, app.on_mousewheel)

    def set_playing(self, playing):
        self.icons['play'] = ImageTk.PhotoImage(transport_icon('pause' if playing else 'play', self.app.colors['WHEEL_CENTER_TEXT'], 21))
        self.itemconfigure(self.play_item, image=self.icons['play'])

    def clicked(self, event):
        x, y = event.x*164/144 - 82, event.y*150/132 - 75
        if x*x + y*y > 75*75:
            return
        if x*x + y*y < 30*30:
            self.app.toggle_play_pause()
        elif abs(x) > abs(y):
            (self.app.next_song if x > 0 else self.app.prev_song)()
        elif y < 0:
            self.app.toggle_navigation()
        else:
            self.app.stop_song()
