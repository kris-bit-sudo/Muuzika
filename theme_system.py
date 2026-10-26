"""Named color roles, migration and appearance validation for Muuzika 3."""
import re

DEFAULT_THEME = 'Original Green'
MIN_WIDTH, MIN_HEIGHT = 360, 440
ALIASES = {'Zöld (alapértelmezett)': DEFAULT_THEME, 'Kék': 'Blue', 'Narancs': 'Amber',
           'Vörös Acél': 'Red Steel', 'Retro · Ezüst': 'Retro Silver', 'Retro · Rózsaszín': 'Retro Pink'}

def base(bg, surface, list_bg, button, accent, title, hover, text, on_accent):
    return dict(COLOR_DARK_BG=bg, COLOR_MAIN_CONTAINER=surface, COLOR_PLAYLIST_BG=list_bg,
                COLOR_BUTTON_NORMAL=button, COLOR_ACCENT=accent, COLOR_NOW_PLAYING_TITLE=title,
                COLOR_DRAG_BORDER_NORMAL=hover, COLOR_GENERAL_FOREGROUND=text, COLOR_TEXT_DARK=on_accent,
                SECONDARY=text, ICON=text, BUTTON_PRESSED=accent, BORDER=hover,
                SELECTION_BG=accent, SELECTION_TEXT=on_accent, CURRENT_BG=button, CURRENT_TEXT=title,
                FIELD_BG=list_bg, FIELD_TEXT=text, FIELD_BORDER=hover,
                SLIDER_TRACK=list_bg, SLIDER_FILL=accent, SLIDER_KNOB=title,
                ERROR_BG='#512b2f', ERROR_TEXT='#ffe5e5',
                WHEEL_FACE='#f7f6f2', WHEEL_BORDER='#aaa8a3', WHEEL_TEXT='#525751', WHEEL_CENTER=button,
                WHEEL_CENTER_TEXT=text,
                TITLEBAR=surface)

THEMES = {
    DEFAULT_THEME: base('#0f2419','#1a4d2e','#245a3a','#2d6e45','#5fd685','#7ee89b','#3a8a5a','#e8f5ed','#0f2419'),
    'Blue': base('#060d1a','#0d1f35','#112844','#1a3d5c','#2d8ef0','#6ab4f5','#2060a0','#dceeff','#060d1a'),
    'Amber': base('#180900','#2a1200','#3b1a00','#5a2d00','#f08020','#f5a84d','#7a3e00','#fff3e0','#180900'),
    'Teal Premium': base('#021a1a','#052e2e','#093d3d','#0f5555','#00c8c8','#40e0e0','#0a7070','#e0ffff','#021a1a'),
    'Red Steel': base('#1a0505','#2d0a0a','#3d1010','#5c1a1a','#e03030','#f07070','#7a2020','#ffeaea','#1a0505'),
    'Retro Silver': base('#b4b3ae','#deddd7','#f0f3e9','#c7c8c1','#327ab5','#30363a','#a9b4b5','#26312d','#ffffff'),
    'Retro Pink': base('#9b3c67','#d87ca7','#f2f3eb','#e8aac7','#913b69','#492336','#b96189','#392631','#ffffff'),
}
THEMES[DEFAULT_THEME]['SECONDARY'] = '#b1cabb'
THEMES['Retro Silver']['WHEEL_CENTER'] = '#c4c4bd'
THEMES['Retro Pink']['WHEEL_CENTER'] = '#e8aac7'

# Reference color names only: no device branding, logos or product imagery.
FINISHES = {
    'Reflective Rainbow': ('#7849a1','#dc6593','#e2b958','#74ad89','#459db7','#7863b0'),
    'Reflective Chrome': ('#777f86','#e0e5e8','#a4adb5','#f2f3f1','#707980'),
    'Pink Gradient': ('#f1b7ad','#dc72a0','#ba477f'),
    'Purple & Pink Gradient': ('#8165b5','#ae72b5','#dc7ba0'),
    'Dark Ocean Blue & Silver Gradient': ('#3d5b73','#819caf','#c9d3dc'),
    'Yellow & Blue Gradient': ('#e1d998','#acd6bc','#49aabd'),
    'Red': ('#af2850','#dc4c67'), 'Purple': ('#8255b4','#b08ad3'),
    'Light Blue': ('#7ec9dc','#b4e5ec'), 'Green': ('#8cac52','#bedc83'),
    'Pink': ('#bb78b5','#dda4d1'), 'Silver': ('#abbac3','#dce3e5'),
    'Blue': ('#159cbd','#61d1e1'), 'Gold': ('#b59a79','#dfc8aa'),
    'Slate Black': ('#272c32','#444b54'), 'Charcoal Gray': ('#606266','#989b9e'),
    'Frost Silver': ('#c0d6df','#f0f3f2'),
}

def blend(first, second, amount):
    a, b = [tuple(int(c[i:i+2],16) for i in (1,3,5)) for c in (first,second)]
    return '#' + ''.join(f'{round(x+(y-x)*amount):02x}' for x,y in zip(a,b))

for name, stops in FINISHES.items():
    shell = stops[len(stops)//2]
    dark = name == 'Slate Black'
    foreground = '#f5f6f1' if dark else '#202a30'
    accent = '#b9d8ec' if dark else '#284f68'
    p = base(blend(shell,'#111922',.25),shell,'#edf1e6',blend(shell,'#ffffff',.30),
             accent,foreground,blend(shell,'#111922',.20),foreground,'#152331' if dark else '#ffffff')
    p.update(FIELD_TEXT='#202a30',CURRENT_BG='#d5dfd2',CURRENT_TEXT='#202a30',
             SLIDER_TRACK=blend(shell,'#111922',.23),WHEEL_CENTER=blend(shell,'#ffffff',.40),
             WHEEL_CENTER_TEXT='#202a30')
    # The LCD list always has dark lettering, independently from the shell.
    p['LIST_TEXT'] = '#202a30'
    THEMES[name] = p
for p in THEMES.values():
    p.setdefault('LIST_TEXT',p['COLOR_GENERAL_FOREGROUND'])

def contrast(first,second):
    def luminance(color):
        values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        values=[v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v,w in zip(values,(.2126,.7152,.0722)))
    a,b=sorted((luminance(first),luminance(second)))
    return (b+.05)/(a+.05)

def readable(foreground,background):
    if contrast(foreground,background)>=4.5: return foreground
    target=max(('#000000','#ffffff'),key=lambda c:contrast(c,background))
    for step in range(1,101):
        value=blend(foreground,target,step/100)
        if contrast(value,background)>=4.5: return value
    return target

TEXT_PAIRS=(('COLOR_GENERAL_FOREGROUND','COLOR_MAIN_CONTAINER'),('SECONDARY','COLOR_MAIN_CONTAINER'),
    ('COLOR_NOW_PLAYING_TITLE','COLOR_MAIN_CONTAINER'),('BUTTON_TEXT','COLOR_BUTTON_NORMAL'),
    ('ICON','COLOR_BUTTON_NORMAL'),('LIST_TEXT','COLOR_PLAYLIST_BG'),('SELECTION_TEXT','SELECTION_BG'),
    ('CURRENT_TEXT','CURRENT_BG'),('FIELD_TEXT','FIELD_BG'),('COLOR_TEXT_DARK','COLOR_ACCENT'),
    ('WHEEL_TEXT','WHEEL_FACE'),('WHEEL_CENTER_TEXT','WHEEL_CENTER'),('ERROR_TEXT','ERROR_BG'))
for p in THEMES.values():
    p['BUTTON_TEXT']=p['COLOR_GENERAL_FOREGROUND']
    for foreground,background in TEXT_PAIRS:
        p[foreground]=readable(p[foreground],p[background])

COLOR_GROUPS = {
    'Window': [('COLOR_DARK_BG','Outer background'),('COLOR_MAIN_CONTAINER','Surface'),('BORDER','Borders'),('TITLEBAR','Title bar')],
    'Playlist': [('COLOR_PLAYLIST_BG','List background'),('LIST_TEXT','List text'),('SELECTION_BG','Selection'),('SELECTION_TEXT','Selected text'),('CURRENT_BG','Current track'),('CURRENT_TEXT','Current track text')],
    'Text': [('COLOR_GENERAL_FOREGROUND','Primary text'),('SECONDARY','Secondary text'),('COLOR_NOW_PLAYING_TITLE','Track title')],
    'Controls': [('COLOR_BUTTON_NORMAL','Buttons'),('BUTTON_TEXT','Button text'),('COLOR_DRAG_BORDER_NORMAL','Hover'),('BUTTON_PRESSED','Pressed'),('ICON','Icons'),('COLOR_ACCENT','Active accent'),('COLOR_TEXT_DARK','Text on accent')],
    'Fields': [('FIELD_BG','Field background'),('FIELD_TEXT','Field text'),('FIELD_BORDER','Field border')],
    'Sliders': [('SLIDER_TRACK','Track'),('SLIDER_FILL','Fill'),('SLIDER_KNOB','Handle')],
    'Retro': [('WHEEL_FACE','Wheel face'),('WHEEL_BORDER','Wheel border'),('WHEEL_TEXT','Wheel symbols'),('WHEEL_CENTER','Center button'),('WHEEL_CENTER_TEXT','Center symbol')],
    'Feedback': [('ERROR_BG','Error background'),('ERROR_TEXT','Error text')],
}

def valid_color(value):
    return isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) is not None

def normalize_appearance(preferences):
    saved = preferences.get('saved_palettes',{})
    cleaned = {}
    if isinstance(saved,dict):
        for label,record in saved.items():
            if not isinstance(label,str) or not label.strip() or len(label)>32 or not isinstance(record,dict): continue
            theme=record.get('theme',DEFAULT_THEME)
            if theme not in THEMES: theme=DEFAULT_THEME
            colors=dict(THEMES[theme])
            overrides=record.get('colors',{})
            if isinstance(overrides,dict):
                colors.update({k:v for k,v in overrides.items() if k in colors and valid_color(v)})
            cleaned[label]={'theme':theme,'colors':colors}
    preferences['saved_palettes']=cleaned
    name = ALIASES.get(preferences.get('theme'), preferences.get('theme', DEFAULT_THEME))
    preferences['theme'] = name if name in THEMES else DEFAULT_THEME
    if preferences.get('layout') not in ('Original', 'Retro'):
        preferences['layout'] = 'Retro' if preferences['theme'].startswith('Retro') else 'Original'
    colors = preferences.get('custom_colors', {})
    preferences['custom_colors'] = {key: value.upper() for key, value in colors.items()
                                    if key in THEMES[DEFAULT_THEME] and valid_color(value)} if isinstance(colors, dict) else {}

def palette(preferences, draft=None):
    source = draft if draft is not None else preferences
    result = dict(THEMES.get(source.get('theme'), THEMES[DEFAULT_THEME]))
    result.update({key: value for key, value in source.get('custom_colors', {}).items()
                   if key in result and valid_color(value)})
    return result

def saved_size(preferences):
    size = preferences.get('window_size', {})
    try:
        return max(MIN_WIDTH, min(1920, int(size.get('width', 400)))), max(MIN_HEIGHT, min(1440, int(size.get('height', 500))))
    except (ValueError, TypeError, AttributeError):
        return 400, 500
