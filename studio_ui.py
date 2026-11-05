"""Muuzika 3: single-window views and appearance/size editing.

UI state is separate from persisted preferences: appearance and size previews
are committed only by their Save actions. Playback is owned by MuuzikaApp.
"""
from __future__ import annotations
import copy
import os
import tkinter as tk
from datetime import datetime
import customtkinter as ctk
from tkinterdnd2 import DND_FILES
from theme_system import THEMES, DEFAULT_THEME, ALIASES, COLOR_GROUPS, palette, valid_color, saved_size, MIN_WIDTH, MIN_HEIGHT, FINISHES, blend
from retro_ui import RetroWheel
from beta_core import VERSION, friendly_error, search_text
from customtkinter.windows.widgets.scaling import CTkScalingBaseClass
from palette_ui import PaletteUI
from ui_icons import transport_icon


class ManagedOptionMenu(ctk.CTkOptionMenu):
    def destroy(self):
        # CTk's dropdown unregisters appearance callbacks but omits scaling.
        CTkScalingBaseClass.destroy(self._dropdown_menu)
        super().destroy()


class StudioUI(PaletteUI):
    def _apply_palette(self):
        self.colors = palette(self.preferences, getattr(self, '_appearance_draft', None))
        source = getattr(self, '_appearance_draft', None) or self.preferences
        self.is_retro = source.get('layout') == 'Retro'

    def ui_button(self, parent, text, command, width=110, accent=False, icon=None, hint=None, press_effect=True):
        c = self.colors
        button = ctk.CTkButton(parent, text=text, command=command, width=width, height=30,
            corner_radius=15 if self.is_retro else 8, border_width=2 if self.is_retro else 0,
            border_color=c['WHEEL_BORDER'] if self.is_retro else c['BORDER'], fg_color=c['COLOR_ACCENT'] if accent else c['WHEEL_FACE' if self.is_retro else 'COLOR_BUTTON_NORMAL'],
            hover_color=blend(c['COLOR_ACCENT'],c['COLOR_TEXT_DARK'],.12) if accent else (blend(c['WHEEL_FACE'],c['WHEEL_CENTER'],.15) if self.is_retro else c['COLOR_DRAG_BORDER_NORMAL']),
            text_color=c['COLOR_TEXT_DARK'] if accent else c['WHEEL_TEXT' if self.is_retro else 'BUTTON_TEXT'],
            font=('Segoe UI Semibold', 12))
        if icon:
            button.configure(corner_radius=4 if width<=24 else 6,border_spacing=0)
            self.set_button_icon(button, icon, c['COLOR_TEXT_DARK'] if accent else c['WHEEL_TEXT' if self.is_retro else 'ICON'])
        if hint:
            self.add_tooltip(button, hint)
        # Pressed colors use the same fixed widget dimensions.
        button._base_fill = button.cget('fg_color')
        if press_effect:
            button.bind('<ButtonPress-1>', lambda e: button.configure(fg_color=blend(button._base_fill,c['WHEEL_BORDER'],.22) if self.is_retro else c['BUTTON_PRESSED']) if button.winfo_exists() and button.cget('state') != 'disabled' else None, add='+')
            button.bind('<ButtonRelease-1>', lambda e: button.configure(fg_color=button._base_fill) if button.winfo_exists() else None, add='+')
            button.bind('<Leave>', lambda e: button.configure(fg_color=button._base_fill) if button.winfo_exists() else None, add='+')
        return button

    def search_field(self, parent, previous, following, **entry_options):
        """Shared, fixed-height search chrome; arrows never draw button tiles."""
        c=self.colors
        shell=ctk.CTkFrame(parent,fg_color=c['FIELD_BG'],border_width=1,
            border_color=c['FIELD_BORDER'],corner_radius=8,height=34,width=1)
        shell.grid_propagate(False)
        shell.grid_columnconfigure(1,weight=1)
        shell.grid_rowconfigure(0,weight=1)
        art=transport_icon('search',c['FIELD_TEXT'])
        glyph=ctk.CTkLabel(shell,text='',width=24,height=30,
            image=ctk.CTkImage(art,size=(18,18)))
        glyph.grid(row=0,column=0,padx=(5,0))
        entry=self.ui_entry(shell,placeholder_text='Search…',width=60,**entry_options)
        entry.configure(border_width=0)
        entry.grid(row=0,column=1,sticky='ew',padx=(0,4),pady=1)
        glyph.bind('<Button-1>',lambda e:entry.focus_set())
        count=ctk.CTkLabel(shell,text='',width=35,height=30,font=('Segoe UI',11),text_color=c['FIELD_TEXT'])
        count.grid(row=0,column=2)
        arrows=ctk.CTkFrame(shell,width=52,height=30,fg_color='transparent')
        arrows.grid(row=0,column=3,padx=(2,4))
        buttons=[]
        for i,(kind,command) in enumerate((('up',previous),('down',following))):
            art=transport_icon(kind,c['FIELD_TEXT'])
            button=ctk.CTkButton(arrows,text='',image=ctk.CTkImage(art,size=(16,16)),
                width=24,height=30,fg_color='transparent',hover=False,
                border_width=0,border_spacing=0,corner_radius=0,command=command)
            button.place(x=i*28,y=0)
            buttons.append(button)
        return shell,entry,glyph,count,*buttons

    def ui_label(self, parent, text, size=12, bold=False, secondary=False, **kwargs):
        kwargs['wraplength'] = min(kwargs.get('wraplength',1000),max(250,self.winfo_width()-100))
        return ctk.CTkLabel(parent, text=text, text_color=self.colors['SECONDARY' if secondary else 'COLOR_GENERAL_FOREGROUND'],
                            font=('Segoe UI Semibold' if bold or size < 12 else 'Segoe UI', max(12,size)), **kwargs)

    def ui_entry(self, parent, **kwargs):
        return ctk.CTkEntry(parent, fg_color=self.colors['FIELD_BG'], text_color=self.colors['FIELD_TEXT'],
            border_color=self.colors['FIELD_BORDER'], corner_radius=6, height=30, font=('Segoe UI',13), **kwargs)

    def ui_menu(self, parent, values, value, command):
        return ManagedOptionMenu(parent, values=values, variable=value, command=command,
            fg_color=self.colors['COLOR_BUTTON_NORMAL'], button_color=self.colors['BORDER'],
            button_hover_color=self.colors['COLOR_DRAG_BORDER_NORMAL'], text_color=self.colors['BUTTON_TEXT'],
            dropdown_fg_color=self.colors['FIELD_BG'], dropdown_text_color=self.colors['FIELD_TEXT'],
            dropdown_hover_color=blend(self.colors['FIELD_BG'],self.colors['FIELD_TEXT'],.08), dynamic_resizing=False, height=30, font=('Segoe UI Semibold',12), dropdown_font=('Segoe UI',13))

    def create_widgets(self):
        self._apply_palette()
        c = self.colors
        self._button_images = {}
        self.retro_wheel = None
        self._tooltip_window = None
        self._tooltip_after = None
        self._view = getattr(self, '_view', 'Player')
        self.main_container = ctk.CTkFrame(self, fg_color=c['COLOR_MAIN_CONTAINER'], corner_radius=14,
                                          border_width=1, border_color=c['BORDER'])
        self.main_container.pack(fill='both', expand=True, padx=6, pady=6)
        main = self.main_container
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(main, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=14, pady=(9, 5))
        header.grid_columnconfigure(0, weight=1)
        self.brand_label=self.ui_label(header,'Muuzika',18,True)
        self.brand_label.grid(row=0,column=0,columnspan=3,sticky='ew',pady=(0,5))
        self.back_button=self.ui_button(header,'',self.go_back,30,icon='back',hint='Back · Escape')
        self.back_button.grid(row=0,column=0,sticky='w',pady=(0,5))
        (self.search_shell,self.list_search,self.search_glyph,self.search_count,
         self.search_previous,self.search_next)=self.search_field(header,
            lambda:self.find_in_queue(direction=-1),self.find_in_queue)
        self.search_shell.grid(row=1,column=0,sticky='ew',padx=(0,8))
        self.search_button = self.search_shell
        self.list_search.bind('<Return>',self.search_from_header)
        self.list_search.bind('<Escape>',lambda e:self.hide_list_search())
        self.list_search.bind('<Shift-Return>',lambda e:self.find_in_queue(direction=-1))
        self.list_search.bind('<KeyRelease>',self.update_search_results)
        self._search_query=''
        self._search_index=None
        self.header_actions=ctk.CTkFrame(header,width=74,height=34,fg_color='transparent')
        self.header_actions.grid(row=1,column=1,columnspan=2)
        self.add_files_button=self.ui_button(self.header_actions,'',self.add_files,34,icon='add',hint='Add files · Ctrl+O',press_effect=False)
        self.add_files_button.place(x=0,y=2)
        self.sync_button=self.ui_button(self.header_actions,'',self.sync_library,34,icon='cloud',hint='Server sync · manual refresh',press_effect=False)
        self.sync_button.place(x=40,y=2)
        self.tabs = ctk.CTkFrame(main, fg_color=c['COLOR_MAIN_CONTAINER'], border_width=1, border_color=c['BORDER'], corner_radius=12)
        self.tabs.grid_columnconfigure(0,weight=1)
        self.ui_label(self.tabs,'Where to?',20,True).grid(row=0,column=0,pady=(24,12))
        self.tab_buttons = {}
        for i, (name, icon) in enumerate((('Player','play'), ('Library','library'), ('Settings','settings'))):
            button = self.ui_button(self.tabs, '', lambda n=name: self.show_view(n), width=1, icon=icon, hint=name)
            button.configure(text=name,height=52,compound='left',font=('Segoe UI Semibold',15))
            button.grid(row=i+1, column=0, sticky='ew', padx=22, pady=6)
            self.tab_buttons[name] = button
        self._navigation_open = False
        self.page_host = ctk.CTkFrame(main, fg_color='transparent')
        self.page_host.grid(row=2, column=0, sticky='nsew', padx=14)
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)
        self.player_page = ctk.CTkFrame(self.page_host, fg_color=c['COLOR_PLAYLIST_BG'], corner_radius=9,
                                        border_width=2 if self.is_retro else 1, border_color=c['BORDER'])
        self.player_page.grid(row=0, column=0, sticky='nsew')
        self.player_page.grid_columnconfigure(0, weight=1)
        self.player_page.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollbar(self.player_page, width=12, fg_color=c['COLOR_PLAYLIST_BG'],
                                 button_color=c['COLOR_BUTTON_NORMAL'], button_hover_color=c['COLOR_DRAG_BORDER_NORMAL'])
        scroll.grid(row=0, column=1, sticky='ns', padx=(0, 5), pady=8)
        self.playlist_box = tk.Listbox(self.player_page, bg=c['COLOR_PLAYLIST_BG'], fg=c['LIST_TEXT'],
            selectbackground=c['SELECTION_BG'], selectforeground=c['SELECTION_TEXT'], font=('Segoe UI', 10),
            bd=0, highlightthickness=0, activestyle='none', exportselection=False,
            selectmode=tk.EXTENDED, height=3, yscrollcommand=scroll.set)
        self.playlist_box.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=10)
        scroll.configure(command=self.playlist_box.yview)
        for event, callback in (('<Shift-Up>', lambda e:self.move_selected(-1)), ('<Shift-Down>',lambda e:self.move_selected(1)),
                                ('<Delete>',self.delete_selected), ('<Return>',lambda e:self.play_selected()),
                                ('<Button-1>',self.on_press), ('<B1-Motion>',self.on_drag),
                                ('<ButtonRelease-1>',self.on_drop_reorder), ('<Button-3>',self.queue_menu)):
            self.playlist_box.bind(event, callback)
        self.playlist_box.drop_target_register(DND_FILES)
        self.playlist_box.dnd_bind('<<Drop>>', self.drop_files)
        self.other_page = None
        self._reload_library = None
        self.playback_panel = ctk.CTkFrame(main, fg_color='transparent')
        self.playback_panel.grid(row=3, column=0, sticky='ew', padx=18, pady=(5, 0))
        self.playback_panel.grid_columnconfigure(0, weight=1)
        self.song_label = ctk.CTkLabel(self.playback_panel, text='Choose a track', text_color=c['COLOR_NOW_PLAYING_TITLE'],
                                      font=('Segoe UI', 12, 'bold'), height=24, wraplength=300)
        self.song_label.grid(row=0, column=0, sticky='ew')
        self.add_tooltip(self.song_label, self._full_track_name)
        self.seek_bar = ctk.CTkSlider(self.playback_panel, from_=0, to=1, height=12,
            fg_color=c['SLIDER_TRACK'], progress_color=c['SLIDER_FILL'], button_color=c['SLIDER_KNOB'],
            button_hover_color=c['COLOR_ACCENT'], command=self.on_seek_drag)
        self.seek_bar.set(0)
        self.seek_bar.grid(row=1, column=0, sticky='ew', pady=(2, 0))
        self.seek_bar.bind('<ButtonPress-1>', self.start_seeking)
        self.seek_bar.bind('<ButtonRelease-1>', self.finish_seeking)
        self.time_frame = ctk.CTkFrame(self.playback_panel, fg_color='transparent', height=20)
        self.time_frame.grid(row=2, column=0, sticky='ew')
        self.time_frame.grid_columnconfigure(1, weight=1)
        self.time_label_start = self.ui_label(self.time_frame,'0:00',10,secondary=True,height=20)
        self.time_label_start.grid(row=0,column=0)
        self.time_label_end = self.ui_label(self.time_frame,'0:00',10,secondary=True,height=20)
        self.time_label_end.grid(row=0,column=2)
        self.transport = ctk.CTkFrame(self.playback_panel, fg_color='transparent')
        self.transport.grid(row=3,column=0,pady=3)
        self.menu_button=self.ui_button(self.transport,'',self.toggle_navigation,30,icon='menu',hint='Menu')
        self.page_menu_button=self.menu_button
        self.stop_button=self.ui_button(self.transport,'',self.stop_song,30,icon='stop',hint='Stop')
        self.shuffle_button = self.ui_button(self.transport,'',self.toggle_shuffle,36,icon='shuffle',hint='Shuffle')
        self.prev_button = self.ui_button(self.transport,'',self.prev_song,36,icon='previous',hint='Previous track')
        self.play_pause_btn = self.ui_button(self.transport,'',self.toggle_play_pause,44,True,'play','Play / pause · Space')
        self.next_button = self.ui_button(self.transport,'',self.next_song,36,icon='next',hint='Next track')
        self.repeat_button = self.ui_button(self.transport,'',self.cycle_repeat,36,icon='repeat',hint='Repeat: off / all / one')
        for i, button in enumerate((self.menu_button,self.shuffle_button,self.prev_button,self.play_pause_btn,self.next_button,self.repeat_button,self.stop_button)):
            button.configure(height=36,width=36 if i==3 else 30)
            button.grid(row=0,column=i,padx=4)
        if self.is_retro:
            self.wheel_frame = ctk.CTkFrame(self.playback_panel, fg_color='transparent')
            self.wheel_frame.grid(row=3,column=0,sticky='ew',pady=0)
            self.wheel_frame.grid_columnconfigure(0,weight=1)
            self.wheel_frame.grid_columnconfigure(2,weight=1)
            self.retro_wheel = RetroWheel(self.wheel_frame,self,c['COLOR_MAIN_CONTAINER'],c['WHEEL_CENTER'])
            self.retro_wheel.grid(row=0,column=1)
            self.retro_shuffle = self.ui_button(self.wheel_frame,'',self.toggle_shuffle,30,icon='shuffle',hint='Shuffle')
            self.retro_shuffle.grid(row=0,column=0)
            self.retro_repeat = self.ui_button(self.wheel_frame,'',self.cycle_repeat,30,icon='repeat',hint='Repeat: off / all / one')
            self.retro_repeat.grid(row=0,column=2)
        self.volume_frame = ctk.CTkFrame(self.playback_panel,fg_color='transparent')
        self.volume_frame.grid(row=4,column=0,sticky='ew',pady=(2,0))
        self.volume_frame.grid_columnconfigure(1,weight=1)
        volume_icon = self.ui_label(self.volume_frame,'VOL',9,secondary=True,width=30)
        volume_icon.grid(row=0,column=0,padx=(0,8))
        self.volume_slider = ctk.CTkSlider(self.volume_frame,from_=0,to=1,height=12,command=self.set_volume,
            fg_color=c['SLIDER_TRACK'],progress_color=c['SLIDER_FILL'],button_color=c['SLIDER_KNOB'],button_hover_color=c['COLOR_ACCENT'])
        self.volume_slider.grid(row=0,column=1,sticky='ew')
        self.volume_slider.bind('<ButtonRelease-1>',lambda e:self.save_data())
        self.volume_label = self.ui_label(self.volume_frame,'0%',10,secondary=True,width=40)
        self.volume_label.grid(row=0,column=2,padx=(8,0))
        self._bind_volume_wheel(self.volume_frame,volume_icon,self.volume_label)
        self.footer = ctk.CTkFrame(main,fg_color='transparent')
        self.cloud_button = self.tab_buttons['Library']
        if self._syncing: self.sync_button.configure(state='disabled')
        self.status_host=ctk.CTkFrame(main,fg_color='transparent',height=25,width=1)
        self.status_host.grid(row=5,column=0,sticky='ew',padx=12)
        self.status_host.grid_propagate(False)
        self.status_host.grid_columnconfigure(0,weight=1)
        self.status_label = self.ui_label(self.status_host,'',12,secondary=True,height=22,wraplength=300)
        self.status_label.grid(row=0,column=0,sticky='ew')
        self._status_text = ''
        self.update_mode_buttons()
        self.update_play_button()
        self.refresh_rows()
        self.show_view(self._view)
        self.bind('<Configure>', self._on_window_configure)
        if not getattr(self,'_navigation_bound',False):
            self.bind('<Button-1>',self.dismiss_navigation,add='+')
            self.bind('<Escape>',self.escape_view,add='+')
            self._navigation_bound=True

    def toggle_mute(self):
        volume=self.volume_slider.get()
        if volume > 0:
            self._unmuted_volume=volume
            volume=0
        else:
            volume=getattr(self,'_unmuted_volume',.25)
        self.volume_slider.set(volume)
        self.set_volume(volume)
        self.save_data()

    def close_navigation(self):
        was_open = self._navigation_open
        self.tabs.place_forget()
        self._navigation_open=False
        if was_open: self.show_view(getattr(self,'_navigation_return','Player'))

    def go_back(self):
        if self._navigation_open:
            self.close_navigation()
            return
        self.show_view('Settings' if self._view in ('Colors','Palettes') else 'Player')

    def escape_view(self,event=None):
        if self._navigation_open: self.close_navigation()
        elif self._view != 'Player': self.go_back()
        else: self.hide_list_search()
        return 'break'

    def toggle_navigation(self):
        if self._navigation_open:
            self.close_navigation()
        else:
            self._navigation_return=self._view
            self.show_view('Navigation')
            self._navigation_open=True

    def dismiss_navigation(self,event):
        widget=event.widget
        while widget is not None:
            if widget in (self.menu_button,self.page_menu_button,self.retro_wheel,self.tabs): return
            widget=getattr(widget,'master',None)
        self.close_navigation()

    def _full_track_name(self):
        return self.tracks[self.current_index].display_name() if 0 <= self.current_index < len(self.tracks) else 'No track selected'

    def show_view(self, name):
        self.tabs.place_forget()
        self._navigation_open=False
        if getattr(self,'_resize_original',None) is not None and name != 'Notice':
            name = 'Settings'
            self._settings_section = 'Window'
        self._view = name
        if name != 'Player': self.hide_list_search(False)
        self.hide_tooltip()
        self.player_page.grid_remove()
        if self.other_page is not None:
            self.other_page.destroy()
            self.other_page = None
        self._reload_library = None
        for tab, button in self.tab_buttons.items():
            active = tab == name or tab == 'Settings' and name in ('Colors','Palettes','Notice')
            button.configure(fg_color=self.colors['COLOR_ACCENT' if active else ('WHEEL_FACE' if self.is_retro else 'COLOR_BUTTON_NORMAL')])
            self.set_button_icon(button,{'Player':'play','Library':'library','Settings':'settings'}[tab],
                self.colors['COLOR_TEXT_DARK' if active else ('WHEEL_TEXT' if self.is_retro else 'ICON')])
            button.configure(text=tab,text_color=self.colors['COLOR_TEXT_DARK' if active else ('WHEEL_TEXT' if self.is_retro else 'BUTTON_TEXT')])
            button._base_fill = button.cget('fg_color')
            button.configure(hover_color=blend(button._base_fill,self.colors['WHEEL_BORDER'],.18) if self.is_retro else self.colors['COLOR_DRAG_BORDER_NORMAL'])
        full = name == 'Player'
        focused_page=name != 'Player'
        for widget in (self.search_shell,self.header_actions):
            widget.grid_remove() if focused_page else widget.grid()
        self.playback_panel.grid_remove() if focused_page else self.playback_panel.grid()
        self.status_host.grid_remove() if focused_page else self.status_host.grid()
        self.back_button.grid_remove() if full else self.back_button.grid()
        for widget in (self.seek_bar,self.time_frame,self.volume_frame):
            widget.grid() if full else widget.grid_remove()
        for button in (self.shuffle_button,self.repeat_button):
            button.grid() if full else button.grid_remove()
        self.transport.grid()
        if self.is_retro:
            self.wheel_frame.grid() if full else self.wheel_frame.grid_remove()
            if full: self.transport.grid_remove()
        if full:
            self.player_page.grid()
            return
        self.other_page = ctk.CTkFrame(self.page_host,fg_color='transparent')
        self.other_page.grid(row=0,column=0,sticky='nsew')
        if name == 'Navigation':
            self.tabs.place(in_=self.other_page,x=0,y=0,relwidth=1,relheight=1)
            self.tabs.lift()
        elif name == 'Library': self.build_library(self.other_page)
        elif name == 'Colors': self.build_colors(self.other_page)
        elif name == 'Palettes': self.build_palettes(self.other_page)
        elif name == 'Notice': self.build_notice(self.other_page)
        else: self.build_settings(self.other_page)

    def open_settings(self): self.show_view('Settings')
    def open_nextcloud_browser(self): self.show_view('Library')

    def show_list_search(self):
        if self._view != 'Player': self.show_view('Player')
        self.list_search.focus_set()
        return 'break'

    def search_from_header(self,event=None):
        if self._view != 'Player': self.show_view('Player')
        return self.find_in_queue(event)

    def hide_list_search(self, restore_focus=True):
        self.list_search.delete(0,'end')
        self._search_query=''
        self._search_index=None
        self.search_count.configure(text='')
        if restore_focus: self.focus_set()
        return 'break'

    def update_search_results(self,event=None):
        if event is not None and event.keysym in ('Return','Escape'): return
        self.find_in_queue(direction=0)

    def toggle_list_search(self):
        if self._view == 'Player' and self.list_search.winfo_ismapped(): self.hide_list_search()
        else: self.show_list_search()

    def hide_tooltip(self):
        if getattr(self, '_tooltip_after', None) is not None:
            self.after_cancel(self._tooltip_after)
            self._tooltip_after = None
        if hasattr(self, 'status_label'): self.status_label.configure(text='')

    def add_tooltip(self, widget, text):
        def enter(event=None):
            self.hide_tooltip()
            def show():
                self._tooltip_after = None
                value = text() if callable(text) else text
                self.status_label.configure(text=value[:85])
            self._tooltip_after = self.after(450, show)
        widget.bind('<Enter>',enter,add='+')
        widget.bind('<Leave>',lambda e:self.hide_tooltip(),add='+')
        widget.bind('<ButtonPress-1>',lambda e:self.hide_tooltip(),add='+')

    def update_mode_buttons(self):
        c = self.colors
        for button,kind,active in ((self.shuffle_button,'shuffle',self.shuffle),(self.repeat_button,'repeat_one' if self.repeat_mode == 2 else 'repeat',self.repeat_mode)):
            button.configure(fg_color=c['COLOR_ACCENT' if active else ('WHEEL_FACE' if self.is_retro else 'COLOR_BUTTON_NORMAL')])
            button._base_fill=button.cget('fg_color')
            self.set_button_icon(button,kind,c['COLOR_TEXT_DARK' if active else ('WHEEL_TEXT' if self.is_retro else 'ICON')])
        if self.retro_wheel is not None:
            for button,kind,active in ((self.retro_shuffle,'shuffle',self.shuffle),(self.retro_repeat,'repeat_one' if self.repeat_mode == 2 else 'repeat',self.repeat_mode)):
                button.configure(fg_color=c['COLOR_ACCENT' if active else 'WHEEL_FACE'])
                button._base_fill=button.cget('fg_color')
                button.configure(hover_color=blend(button._base_fill,c['WHEEL_BORDER'],.18))
                self.set_button_icon(button,kind,c['COLOR_TEXT_DARK' if active else 'WHEEL_TEXT'])

    def update_play_button(self):
        active = self.playing and not self.paused
        self.set_button_icon(self.play_pause_btn,'pause' if active else 'play',self.colors['COLOR_TEXT_DARK'])
        if self.retro_wheel is not None: self.retro_wheel.set_playing(active)

    def rebuild_ui(self, theme_name=None):
        self._rebuilding_ui = True
        try:
            self._rebuild_widgets(theme_name)
        finally:
            self._rebuilding_ui = False

    def _rebuild_widgets(self, theme_name=None):
        if theme_name is not None:
            name = ALIASES.get(theme_name, theme_name)
            self.preferences.update(theme=name if name in THEMES else DEFAULT_THEME,
                layout='Retro' if name.startswith('Retro') else 'Original',custom_colors={})
            self._appearance_draft = None
        volume = self.volume_slider.get()
        self.hide_tooltip()
        self.main_container.destroy()
        self.configure = tk.Tk.configure.__get__(self,type(self))
        self.config = self.configure
        self._apply_palette()
        tk.Tk.configure(self,bg=self.colors['COLOR_DARK_BG'])
        self._apply_header_color()
        self.create_widgets()
        self.volume_slider.set(volume)
        self.set_volume(volume)
        if 0 <= self.current_index < len(self.tracks):
            self.show_track_info(self.tracks[self.current_index])
            position = self.current_position() if self.playing else self._resume_position
            self.seek_bar.set(min(position,max(1,self.song_length)))
        self.update_play_button()
        if theme_name is not None: self.save_data()

    def set_status(self, text=''):
        # Routine progress is silent; errors stay inside the same window.
        starts = ('Cannot ', 'No audio', 'Configure ', 'This track belongs', 'The server', 'Server error',
                  'The file', 'The operation failed', 'The password is only', 'Certificate', 'Connection failed')
        if text.startswith(starts): self.show_notice(text)

    def show_notice(self, text):
        if self._view != 'Notice': self._notice_return = self._view
        self._notice_text = text
        self.show_view('Notice')

    def build_notice(self, parent):
        card = ctk.CTkFrame(parent,fg_color=self.colors['ERROR_BG'],corner_radius=10)
        card.pack(fill='both',expand=True,pady=4)
        ctk.CTkLabel(card,text='Something needs attention',text_color=self.colors['ERROR_TEXT'],
                    font=('Segoe UI',16,'bold')).pack(padx=16,pady=(18,10))
        ctk.CTkLabel(card,text=getattr(self,'_notice_text',''),wraplength=max(330,self.winfo_width()-100),
                    justify='left',text_color=self.colors['ERROR_TEXT']).pack(padx=16,pady=8)
        self.ui_button(card,'Back',lambda:self.show_view(getattr(self,'_notice_return','Player'))).pack(pady=8)
        self.ui_button(card,'Connection settings',lambda:self.settings_section('Connection'),width=160).pack(pady=(0,14))

    def build_library(self, parent):
        parent.grid_columnconfigure(0,weight=1)
        parent.grid_rowconfigure(2,weight=1)
        search_variable = tk.StringVar()
        (self.library_search_shell,entry,self.library_search_glyph,self.library_search_count,
         self.library_previous,self.library_next)=self.search_field(parent,
            lambda:step(-1),lambda:step(1),textvariable=search_variable)
        self.library_search_shell.grid(row=0,column=0,sticky='ew',pady=(0,6))
        status = self.ui_label(parent,'Local library · manual sync only',10,secondary=True,wraplength=400)
        status.grid(row=1,column=0,sticky='ew',pady=(0,5))
        frame = ctk.CTkFrame(parent,fg_color=self.colors['COLOR_PLAYLIST_BG'],corner_radius=8)
        frame.grid(row=2,column=0,sticky='nsew')
        scroll = ctk.CTkScrollbar(frame,fg_color=self.colors['COLOR_PLAYLIST_BG'],button_color=self.colors['COLOR_BUTTON_NORMAL'])
        scroll.pack(side='right',fill='y')
        box = tk.Listbox(frame,bg=self.colors['COLOR_PLAYLIST_BG'],fg=self.colors['LIST_TEXT'],
             selectbackground=self.colors['SELECTION_BG'],selectforeground=self.colors['SELECTION_TEXT'],
             bd=0,highlightthickness=0,exportselection=False,selectmode=tk.EXTENDED,font=('Segoe UI',10),yscrollcommand=scroll.set,height=3)
        box.pack(fill='both',expand=True,padx=8,pady=8)
        scroll.configure(command=box.yview)
        results, tracks = [], []
        info = {'date':''}
        def step(direction):
            if not results: return 'break'
            selected=box.curselection()
            index=((selected[0]+direction)%len(results)) if selected else 0
            box.selection_clear(0,tk.END);box.selection_set(index);box.see(index)
            self.library_search_count.configure(text=f'{index+1}/{len(results)}')
            return 'break'
        def fill(event=None):
            words = search_text(entry.get()).split()
            results[:] = [t for t in tracks if all(w in search_text(f'{t.title} {t.artist} {t.album}') for w in words)]
            box.delete(0,tk.END)
            for t in results: box.insert(tk.END,f'{t.display_name()}  ·  {self.format_time(t.duration)}')
            self.library_search_count.configure(text='0/0' if words and not results else '')
            if words and results: step(0)
            status.configure(text=f"{len(results)} tracks · Last sync: {info['date']}" if info['date'] else 'No local library yet. Use Server sync to fetch it.')
        def reload_library():
            if not parent.winfo_exists(): return
            try:
                data = self.library_store.load(self.active_profile())
                tracks[:] = [t for d in data['tracks'] if (t := self.track_from_dict(d)) is not None]
                date = data.get('synced_at','')
                info['date'] = datetime.fromisoformat(date).strftime('%Y-%m-%d %H:%M') if date else ''
                fill()
            except (OSError,ValueError,TypeError,AttributeError):
                status.configure(text='Cannot read the local library. Sync again to rebuild it.')
        self._reload_library = reload_library
        entry.bind('<Return>',lambda e:step(1))
        entry.bind('<Shift-Return>',lambda e:step(-1))
        search_variable.trace_add('write',lambda *_:fill())
        row = ctk.CTkFrame(parent,fg_color='transparent')
        row.grid(row=3,column=0,sticky='ew',pady=7)
        for i in range(2): row.grid_columnconfigure(i,weight=1,uniform='actions')
        def add(all_tracks=False):
            chosen = list(results) if all_tracks else [results[i] for i in box.curselection()]
            self.add_tracks(chosen,announce=False)
            if chosen: self.show_view('Player')
            else: status.configure(text='Select tracks first. Ctrl/Shift selects more than one.')
        self.ui_button(row,'Add selected',add,width=1,accent=True).grid(row=0,column=0,sticky='ew',padx=(0,4))
        self.ui_button(row,'Add all',lambda:add(True),width=1).grid(row=0,column=1,sticky='ew',padx=4)
        self.library_sync_button=self.ui_button(row,'Server sync',self.sync_library,width=1)
        self.library_sync_button.grid(row=1,column=0,sticky='ew',padx=(0,4),pady=(6,0))
        self.library_missing_button=self.ui_button(row,'Add missing',lambda:self.sync_library(add_missing=True),width=1)
        self.library_missing_button.grid(row=1,column=1,sticky='ew',padx=(4,0),pady=(6,0))
        self.library_status=status
        if self._syncing:
            self.library_sync_button.configure(state='disabled')
            self.library_missing_button.configure(state='disabled')
        box.bind('<Double-1>',lambda e:add())
        self.library_box, self.library_search = box, entry
        reload_library()

    def settings_section(self, name):
        self._settings_section = name
        self.show_view('Settings')

    def build_settings(self, parent):
        parent.grid_columnconfigure(0,weight=1)
        parent.grid_rowconfigure(1,weight=1)
        nav = ctk.CTkFrame(parent,fg_color='transparent')
        nav.grid(row=0,column=0,sticky='ew',pady=(0,7))
        section = getattr(self,'_settings_section','Appearance')
        for i,name in enumerate(('Appearance','Window','Connection','About')):
            nav.grid_columnconfigure(i,weight=1,uniform='settings')
            self.ui_button(nav,{'Appearance':'Style','Connection':'Server'}.get(name,name),lambda n=name:self.settings_section(n),width=1,accent=name==section).grid(row=0,column=i,sticky='ew',padx=2)
        body = ctk.CTkScrollableFrame(parent,fg_color=self.colors['COLOR_MAIN_CONTAINER'],corner_radius=9,
            scrollbar_button_color=self.colors['COLOR_BUTTON_NORMAL'],scrollbar_button_hover_color=self.colors['COLOR_DRAG_BORDER_NORMAL'])
        body.grid(row=1,column=0,sticky='nsew')
        self.settings_body = body
        if section == 'Appearance':
            self.build_appearance(body)
            self.appearance_actions(parent, grid=True)
        elif section == 'Window': self.build_window_settings(body)
        elif section == 'Connection': self.build_connection(body)
        else:
            self.ui_label(body,'Muuzika',24,True).pack(pady=(16,2))
            self.ui_label(body,f'Version {VERSION}',12,secondary=True).pack(pady=2)
            self.ui_label(body,'Vibe-coded by kris',15,True).pack(pady=(12,10))
            self.ui_label(body,'Your music. Your colors.\nLocal files and optional Nextcloud Music.',12,justify='center').pack(pady=8)
            self.ui_label(body,'Space  Play / pause\nCtrl+O  Add files\nCtrl+F  Search playlist\nMouse wheel on volume  5% steps',11,justify='left').pack(pady=14)
            self.ui_label(body,'Library updates only when you request Server sync.\nUncached tracks download when played.',11,secondary=True,wraplength=340).pack(pady=10)

    def appearance_draft(self):
        if getattr(self,'_appearance_draft',None) is None:
            self._appearance_draft = {key:copy.deepcopy(self.preferences.get(key,default)) for key,default in
                                     (('theme',DEFAULT_THEME),('layout','Original'),('custom_colors',{}))}
        return self._appearance_draft

    def build_appearance(self, body):
        source = getattr(self,'_appearance_draft',None) or self.preferences
        self.ui_label(body,'Make it yours',17,True).pack(anchor='w',padx=8,pady=(8,4))
        self.ui_label(body,'Preview changes, then Save or Cancel.',11,secondary=True).pack(anchor='w',padx=8,pady=(0,10))
        self.ui_label(body,'Style',12,True).pack(anchor='w',padx=8)
        def layout(choice):
            self.appearance_draft()['layout'] = choice
            self.rebuild_ui()
        self.ui_menu(body,['Original','Retro'],tk.StringVar(value=source.get('layout','Original')),layout).pack(fill='x',padx=8,pady=(3,12))
        self.ui_button(body,'Choose a color palette',lambda:self.show_view('Palettes'),width=180).pack(fill='x',padx=8,pady=8)
        self.palette_swatch(body,'Current palette',self.colors,lambda:self.show_view('Palettes')).pack(fill='x',padx=8,pady=(0,8))
        self.ui_button(body,'Edit every color',lambda:(self.appearance_draft(),self.show_view('Colors')),width=180).pack(fill='x',padx=8,pady=4)
        self.ui_button(body,'Restore Original Green',self.restore_green,width=180).pack(fill='x',padx=8,pady=4)

    def appearance_actions(self, body, grid=False):
        row = ctk.CTkFrame(body,fg_color='transparent')
        if grid: row.grid(row=2,column=0,sticky='ew',pady=7)
        else: row.pack(fill='x',padx=8,pady=12)
        row.grid_columnconfigure((0,1),weight=1)
        self.ui_button(row,'Save',self.save_appearance,width=1,accent=True).grid(row=0,column=0,sticky='ew',padx=(0,4))
        self.ui_button(row,'Cancel',self.cancel_appearance,width=1).grid(row=0,column=1,sticky='ew',padx=(4,0))

    def save_appearance(self):
        if getattr(self,'_appearance_draft',None) is not None:
            self.preferences.update(copy.deepcopy(self._appearance_draft))
        self._appearance_draft = None
        self.save_data()
        self._view = 'Settings'
        self._settings_section = 'Appearance'
        self.rebuild_ui()

    def cancel_appearance(self):
        self._appearance_draft = None
        self._view = 'Settings'
        self._settings_section = 'Appearance'
        self.rebuild_ui()

    def restore_green(self):
        self.appearance_draft().update(theme=DEFAULT_THEME,layout='Original',custom_colors={})
        self.rebuild_ui()

    def build_colors(self, parent):
        parent.grid_columnconfigure(0,weight=1)
        parent.grid_rowconfigure(1,weight=1)
        self.ui_label(parent,'Color studio',17,True).grid(row=0,column=0,sticky='w',pady=(0,4))
        body = ctk.CTkScrollableFrame(parent,fg_color=self.colors['COLOR_MAIN_CONTAINER'],corner_radius=9,
            scrollbar_button_color=self.colors['COLOR_BUTTON_NORMAL'],scrollbar_button_hover_color=self.colors['COLOR_DRAG_BORDER_NORMAL'])
        body.grid(row=1,column=0,sticky='nsew')
        group = getattr(self,'_color_group','Window')
        def select_group(value):
            self._color_group = value
            self._color_role = COLOR_GROUPS[value][0][0]
            self.show_view('Colors')
        self.ui_menu(body,list(COLOR_GROUPS),tk.StringVar(value=group),select_group).pack(fill='x',padx=8,pady=(8,6))
        roles = dict(COLOR_GROUPS[group])
        role = getattr(self,'_color_role',next(iter(roles)))
        if role not in roles: role = next(iter(roles))
        self._color_role = role
        def select_role(label):
            self._color_role = next(key for key,value in roles.items() if value == label)
            self.show_view('Colors')
        self.ui_menu(body,list(roles.values()),tk.StringVar(value=roles[role]),select_role).pack(fill='x',padx=8,pady=4)
        value = self.colors[role]
        swatch = ctk.CTkFrame(body,fg_color=value,height=32,corner_radius=7)
        swatch.pack(fill='x',padx=8,pady=6)
        entry = self.ui_entry(body)
        entry.insert(0,value.upper())
        entry.pack(fill='x',padx=8,pady=4)
        error = self.ui_label(body,'HEX: #RRGGBB · release a slider to preview',10,secondary=True)
        error.pack(padx=8)
        sliders = []
        def moved(_=None):
            value = '#' + ''.join(f'{int(round(slider.get())):02X}' for slider in sliders)
            entry.delete(0,'end'); entry.insert(0,value)
            swatch.configure(fg_color=value)
        def apply(event=None):
            value = entry.get().strip()
            if not valid_color(value):
                error.configure(text='Enter six hexadecimal digits, for example #5FD685.')
                return 'break'
            self.appearance_draft()['custom_colors'][role] = value.upper()
            self.rebuild_ui()
            return 'break'
        for i,channel in enumerate(('R','G','B')):
            row = ctk.CTkFrame(body,fg_color='transparent')
            row.pack(fill='x',padx=8,pady=2)
            self.ui_label(row,channel,10,width=20).pack(side='left')
            slider = ctk.CTkSlider(row,from_=0,to=255,number_of_steps=255,command=moved,
                fg_color=self.colors['SLIDER_TRACK'],progress_color=self.colors['SLIDER_FILL'],button_color=self.colors['SLIDER_KNOB'])
            slider.set(int(value[1+i*2:3+i*2],16))
            slider.pack(side='left',fill='x',expand=True)
            slider.bind('<ButtonRelease-1>',apply)
            sliders.append(slider)
        entry.bind('<Return>',apply)
        self.ui_button(body,'Preview HEX color',apply,width=180).pack(fill='x',padx=8,pady=6)
        def reset():
            draft = self.appearance_draft()
            for key in roles: draft['custom_colors'].pop(key,None)
            self.rebuild_ui()
        self.ui_button(body,'Reset this section',reset,width=180).pack(fill='x',padx=8,pady=4)
        self.appearance_actions(parent,grid=True)

    def build_window_settings(self, body):
        editing = getattr(self,'_resize_original',None) is not None
        self.ui_label(body,'Window size',17,True).pack(anchor='w',padx=8,pady=(8,5))
        self.size_label = self.ui_label(body,f'{self.winfo_width()} × {self.winfo_height()} · '+('Unlocked' if editing else 'Locked'),14)
        self.size_label.pack(anchor='w',padx=8,pady=5)
        self.ui_label(body,'Resize only when you choose to. Save locks the\nwindow again; Cancel restores the previous size.',11,justify='left').pack(anchor='w',padx=8,pady=10)
        if not editing:
            self.ui_button(body,'Adjust window size',self.begin_resize,width=180,accent=True).pack(fill='x',padx=8,pady=8)
        else:
            self.ui_button(body,'Save size',self.save_window_size,width=180,accent=True).pack(fill='x',padx=8,pady=4)
            self.ui_button(body,'Cancel',self.cancel_resize,width=180).pack(fill='x',padx=8,pady=4)
        start = tk.BooleanVar(value=bool(self.preferences.get('start_minimized',False)))
        def save_start():
            self.preferences['start_minimized'] = start.get()
            self.save_data()
        ctk.CTkSwitch(body,text='Start hidden in tray',variable=start,command=save_start,
            text_color=self.colors['COLOR_GENERAL_FOREGROUND'],progress_color=self.colors['COLOR_ACCENT'],
            button_color=self.colors['SLIDER_KNOB']).pack(anchor='w',padx=8,pady=18)
        self.ui_label(body,'Minimum size: 360 × 440. Larger sizes give\nmore room to the playlist, not larger buttons.',11,secondary=True,justify='left').pack(anchor='w',padx=8,pady=8)

    def begin_resize(self):
        if getattr(self,'_resize_original',None) is None:
            self._resize_original = (self.winfo_width(),self.winfo_height())
        self.minsize(MIN_WIDTH,MIN_HEIGHT)
        self.maxsize(1920,1440)
        self.resizable(True,True)
        self.settings_section('Window')

    def save_window_size(self):
        self.preferences['window_size'] = {'width':self.winfo_width(),'height':self.winfo_height()}
        self._resize_original = None
        self.resizable(False,False)
        self.save_data()
        self.settings_section('Window')

    def cancel_resize(self):
        size = getattr(self,'_resize_original',None)
        if size: self.geometry(f'{size[0]}x{size[1]}')
        self._resize_original = None
        self.resizable(False,False)
        self.after_idle(lambda:self.settings_section('Window'))

    def _on_window_configure(self, event):
        if event.widget is not self: return
        if getattr(self,'_view','') == 'Settings' and getattr(self,'_settings_section','') == 'Window':
            label = getattr(self,'size_label',None)
            if label is not None and label.winfo_exists():
                label.configure(text=f'{self.winfo_width()} × {self.winfo_height()} · '+('Unlocked' if getattr(self,'_resize_original',None) else 'Locked'))

    def build_connection(self, body):
        self.ui_label(body,'Nextcloud Music',17,True).pack(anchor='w',padx=8,pady=(8,4))
        self.ui_label(body,'Use the API password generated by the Music app.\nSaving settings does not contact your server.',11,justify='left').pack(anchor='w',padx=8,pady=(0,10))
        if not hasattr(self,'_connection_vars'):
            self._connection_vars = {'url':tk.StringVar(value=self.preferences.get('nc_url','')),
                'user':tk.StringVar(value=self.preferences.get('nc_user','')), 'password':tk.StringVar(value=self._get_secret()),
                'tls':tk.BooleanVar(value=bool(self.preferences.get('nc_verify_tls',True)))}
        variables = self._connection_vars
        for key,label in (('url','Server URL'),('user','Username'),('password','API password')):
            self.ui_label(body,label,11,True).pack(anchor='w',padx=8)
            self.ui_entry(body,textvariable=variables[key],show='•' if key=='password' else '').pack(fill='x',padx=8,pady=(2,7))
        ctk.CTkSwitch(body,text='Verify TLS certificate',variable=variables['tls'],text_color=self.colors['COLOR_GENERAL_FOREGROUND'],
            progress_color=self.colors['COLOR_ACCENT'],button_color=self.colors['SLIDER_KNOB']).pack(anchor='w',padx=8,pady=7)
        status = self.ui_label(body,'',11,wraplength=340,justify='left')
        status.pack(fill='x',padx=8,pady=4)
        def save():
            old = self.active_profile()
            self.preferences.update(nc_url=variables['url'].get().strip(),nc_user=variables['user'].get().strip(),nc_verify_tls=variables['tls'].get())
            stored = self._set_secret(variables['password'].get())
            self.invalidate_client()
            self.save_data()
            if old != self.active_profile() and self.loading: self.stop_song()
            if status.winfo_exists(): status.configure(text='Connection saved.' if stored else 'Password kept for this session only.')
        def test():
            save()
            client = self.get_client()
            if client is None:
                if status.winfo_exists(): status.configure(text='Enter a valid URL, username and API password.')
                return
            if status.winfo_exists(): status.configure(text='Testing connection…')
            import threading
            def worker():
                try:
                    client.ping(); text='Connection successful. Library sync remains manual.'
                except Exception as error: text=friendly_error(error)
                self.ui_call(lambda:status.configure(text=text) if status.winfo_exists() else None)
            threading.Thread(target=worker,daemon=True).start()
        self.ui_button(body,'Save connection',save,accent=True).pack(fill='x',padx=8,pady=4)
        self.ui_button(body,'Test connection',test).pack(fill='x',padx=8,pady=4)
        self.ui_label(body,self._cache_info(),11,secondary=True).pack(anchor='w',padx=8,pady=12)
        self.ui_label(body,'Downloaded audio is cached locally.\nLibrary browsing and search work without a connection.',11,secondary=True,wraplength=340,justify='left').pack(anchor='w',padx=8,pady=4)
