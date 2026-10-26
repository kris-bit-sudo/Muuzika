"""Visual palette gallery and explicitly saved, named user palettes."""
import copy
import textwrap
import tkinter as tk
import customtkinter as ctk
from theme_system import THEMES, DEFAULT_THEME, palette, valid_color


class PaletteUI:
    def palette_swatch(self,parent,name,colors,command):
        card=ctk.CTkFrame(parent,fg_color=self.colors['COLOR_MAIN_CONTAINER'],corner_radius=8,
                         border_width=1,border_color=self.colors['BORDER'])
        preview=tk.Canvas(card,width=110,height=72,highlightthickness=0,bg=colors['COLOR_MAIN_CONTAINER'],cursor='hand2')
        preview.pack(fill='x',padx=6,pady=(6,0))
        def draw(event):
            w=event.width
            preview.delete('all')
            preview.create_rectangle(8,6,w-8,36,fill=colors['COLOR_PLAYLIST_BG'],outline=colors['BORDER'])
            preview.create_rectangle(11,9,w-11,19,fill=colors['SELECTION_BG'],outline='')
            preview.create_line(15,14,w-25,14,fill=colors['SELECTION_TEXT'],width=2)
            preview.create_line(15,26,w-35,26,fill=colors['LIST_TEXT'],width=2)
            preview.create_oval(w/2-15,40,w/2+15,70,fill=colors['WHEEL_FACE'],outline=colors['WHEEL_BORDER'])
            preview.create_oval(w/2-7,48,w/2+7,62,fill=colors['WHEEL_CENTER'],outline='')
            preview.create_polygon(w/2-2,51,w/2+4,55,w/2-2,59,fill=colors['WHEEL_CENTER_TEXT'])
            preview.create_line(14,55,28,55,fill=colors['COLOR_ACCENT'],width=4)
        preview.bind('<Configure>',draw)
        preview.bind('<Button-1>',lambda e:command())
        button=self.ui_button(card,textwrap.fill(name,18),command,width=1)
        button.configure(height=44)
        button.pack(fill='x',padx=5,pady=5)
        return card

    def choose_palette(self,name,custom=False):
        if custom:
            record=self.preferences.get('saved_palettes',{}).get(name)
            if not record: return
            self.appearance_draft().update(theme=record['theme'],custom_colors=copy.deepcopy(record['colors']))
        else:
            self.appearance_draft().update(theme=name,custom_colors={})
        self.rebuild_ui()

    def save_named_palette(self,name):
        name=name.strip()
        if not name or len(name)>32 or any(ord(c)<32 for c in name):
            return 'Use a name with 1–32 characters.'
        saved=self.preferences.setdefault('saved_palettes',{})
        if name.casefold() in {n.casefold() for n in (*THEMES,*saved)}:
            return 'That name already exists. Choose another name.'
        source=getattr(self,'_appearance_draft',None) or self.preferences
        saved[name]={'theme':source.get('theme',DEFAULT_THEME),'colors':palette(self.preferences,getattr(self,'_appearance_draft',None))}
        self.save_data()
        return None

    def build_palettes(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        parent.grid_rowconfigure(2,weight=1)
        self.ui_label(parent,'Palette gallery',17,True).grid(row=0,column=0,sticky='w')
        top=ctk.CTkFrame(parent,fg_color='transparent')
        top.grid(row=1,column=0,sticky='ew',pady=5)
        top.grid_columnconfigure(0,weight=1)
        entry=self.ui_entry(top,placeholder_text='Name your current colors',width=120)
        entry.grid(row=0,column=0,sticky='ew',padx=(0,5))
        message=self.ui_label(top,'Click a preview, then Save to apply.',12,secondary=True)
        message.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(4,0))
        def save_named():
            error=self.save_named_palette(entry.get())
            if error: message.configure(text=error)
            else: self.show_view('Palettes')
        self.ui_button(top,'Save as',save_named,width=68).grid(row=0,column=1)
        body=ctk.CTkScrollableFrame(parent,fg_color=self.colors['COLOR_MAIN_CONTAINER'])
        body.grid(row=2,column=0,sticky='nsew')
        body.grid_columnconfigure((0,1),weight=1,uniform='palettes')
        records=[(name,record['colors'],True) for name,record in self.preferences.get('saved_palettes',{}).items()]
        records += [(name,colors,False) for name,colors in THEMES.items()]
        for index,(name,colors,custom) in enumerate(records):
            card=self.palette_swatch(body,name,colors,lambda n=name,c=custom:self.choose_palette(n,c))
            card.grid(row=index//2,column=index%2,sticky='nsew',padx=3,pady=4)
        actions=ctk.CTkFrame(parent,fg_color='transparent')
        actions.grid(row=3,column=0,sticky='ew',pady=5)
        self.appearance_actions(actions)
