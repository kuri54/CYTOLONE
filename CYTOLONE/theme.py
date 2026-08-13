import gradio as gr


CYTOLONE_GREEN = "#00AF50"
CYTOLONE_PURPLE = "#7030A0"
CYTOLONE_GREEN_DARK = "#007A38"
CYTOLONE_GREEN_HOVER = "#006F32"
CYTOLONE_PURPLE_DARK = "#4E216F"

CYTOLONE_GREEN_PALETTE = gr.themes.Color(
    c50="#EAF8EF",
    c100="#C8EED7",
    c200="#98DDAF",
    c300="#64CB87",
    c400="#31BA63",
    c500=CYTOLONE_GREEN,
    c600="#008F41",
    c700="#006F32",
    c800="#005224",
    c900="#003516",
    c950="#00240F",
    name="cytolone-green",
)

CYTOLONE_PURPLE_PALETTE = gr.themes.Color(
    c50="#F4EEF8",
    c100="#E6D8EE",
    c200="#D0B8DE",
    c300="#B18BC5",
    c400="#8E5AAF",
    c500=CYTOLONE_PURPLE,
    c600="#5A287F",
    c700="#4E216F",
    c800="#3C1956",
    c900="#29113D",
    c950="#1C0B2A",
    name="cytolone-purple",
)

CYTOLONE_THEME = gr.themes.Base(
    primary_hue=CYTOLONE_GREEN_PALETTE,
    secondary_hue=CYTOLONE_PURPLE_PALETTE,
    neutral_hue=gr.themes.colors.slate,
).set(
    color_accent=CYTOLONE_GREEN,
    color_accent_soft="#EAF8EF",
    color_accent_soft_dark="#164B2B",
    border_color_accent=CYTOLONE_GREEN,
    border_color_accent_dark="#62D18C",
    input_border_color_focus=CYTOLONE_GREEN_DARK,
    input_border_color_focus_dark="#62D18C",
    checkbox_background_color_selected=CYTOLONE_GREEN_DARK,
    checkbox_background_color_selected_dark=CYTOLONE_GREEN,
    checkbox_border_color_focus=CYTOLONE_GREEN_DARK,
    checkbox_border_color_focus_dark="#62D18C",
    button_primary_background_fill=CYTOLONE_GREEN_DARK,
    button_primary_background_fill_dark=CYTOLONE_GREEN_DARK,
    button_primary_background_fill_hover=CYTOLONE_GREEN_HOVER,
    button_primary_background_fill_hover_dark=CYTOLONE_GREEN_HOVER,
    button_primary_border_color=CYTOLONE_GREEN_DARK,
    button_primary_border_color_dark=CYTOLONE_GREEN_HOVER,
    button_primary_text_color="white",
    button_primary_text_color_dark="white",
    button_secondary_background_fill="#F4EEF8",
    button_secondary_background_fill_dark=CYTOLONE_PURPLE_DARK,
    button_secondary_background_fill_hover="#E6D8EE",
    button_secondary_background_fill_hover_dark=CYTOLONE_PURPLE,
    button_secondary_border_color="#D0B8DE",
    button_secondary_border_color_dark="#8E5AAF",
    button_secondary_text_color=CYTOLONE_PURPLE_DARK,
    button_secondary_text_color_dark="white",
    link_text_color=CYTOLONE_PURPLE_DARK,
    link_text_color_dark="#D0B8DE",
    link_text_color_hover=CYTOLONE_PURPLE,
    link_text_color_hover_dark="#E6D8EE",
)
