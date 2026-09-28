"""Single source for Komicove palette tokens.

Legacy color keys are retained because the reader and other screens still use
them. New screen colors should use these tokens, never scattered literals.
"""

DARK = {
    "bg": "#090b0f",
    "surface": "#10141b",
    "surface_alt": "#171d26",
    "surface_hover": "#222b36",
    "border": "#28313c",
    "border_glow": "#98262d",
    "accent": "#e12835",
    "accent2": "#ff4b55",
    "text": "#f5f6f8",
    "text_dim": "#a1adba",
    "text_muted": "#65717e",
    "canvas_bg": "#05070a",
    "btn_hover": "#b91e2b",
    "progress_bg": "#27303b",
    "shadow": "#030407",
    "shadow_light": "#161b23",
    "read_badge": "#153d2d",
    "read_badge_text": "#66d49b",
    "search_bg": "#121922",
}

LIGHT = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "surface_alt": "#edf0f3",
    "surface_hover": "#e1e6eb",
    "border": "#cfd7df",
    "border_glow": "#d84c55",
    "accent": "#cf2633",
    "accent2": "#e23842",
    "text": "#1a2028",
    "text_dim": "#53606c",
    "text_muted": "#84909b",
    "canvas_bg": "#e9edf1",
    "btn_hover": "#ae1e2b",
    "progress_bg": "#dce2e8",
    "shadow": "#b7c0c9",
    "shadow_light": "#dce2e8",
    "read_badge": "#ddf2e5",
    "read_badge_text": "#227347",
    "search_bg": "#ffffff",
}
