"""
quality_tracks_ui.py: UI widgets for audio tracks and subtitle options in QualitySelectionModal.
"""
from typing import Dict, List, Optional, Tuple, Any

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None  # type: ignore
    ttk = None  # type: ignore

try:
    from faqih_downloader.locales.i18n import tr
except Exception:
    def tr(key: str, default: str = "") -> str:  # type: ignore
        return default

try:
    from faqih_downloader.config import get_setting, set_setting
except Exception:
    def get_setting(k: str, d: Any = None) -> Any: return d  # type: ignore
    def set_setting(k: str, v: Any) -> bool: return True  # type: ignore


def build_audio_subtitle_row(
    parent_frame: Any, theme: Dict[str, str],
    audio_tracks: List[Dict[str, Any]], subtitle_tracks: List[Dict[str, Any]]
) -> Tuple[Optional[Any], Optional[Any]]:
    """Renders spacious themed 2-row Audio Track, Subtitles, and Delivery Mode card for QualitySelectionModal."""
    if tk is None or ttk is None:
        return None, None
    if not audio_tracks and not subtitle_tracks:
        return None, None
    c_panel = theme.get("c_panel", "#1e293b")
    c_border = theme.get("c_border", "#475569")
    c_text_bright = theme.get("c_text_bright", "#f8fafc")
    c_input_bg = theme.get("c_input_bg", "#0f172a")
    c_accent = theme.get("c_accent", "#38bdf8")

    card = tk.Frame(parent_frame, bg=c_panel, padx=12, pady=8, highlightbackground=c_border, highlightthickness=1)
    card.pack(fill=tk.X, pady=(0, 10))

    cb_audio, cb_sub = None, None

    # Row 1: Audio Track & Subtitles dropdowns
    row1 = tk.Frame(card, bg=c_panel)
    row1.pack(fill=tk.X, pady=(0, 6 if subtitle_tracks else 0))

    if audio_tracks:
        tk.Label(row1, text=tr("lbl_audio_track", "♪ لغة الصوت:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright).pack(side=tk.LEFT, padx=(0, 6))
        cb_audio = ttk.Combobox(row1, values=[t.get("label", "") for t in audio_tracks], state="readonly", font=("Segoe UI", 8), width=23)
        pref_a = str(get_setting("preferred_audio_lang", "original") or "").lower()
        a_idx = next((i for i, t in enumerate(audio_tracks) if pref_a in (str(t.get("language") or "").lower(), str(t.get("track_id") or "").lower())), 0)
        cb_audio.current(a_idx)
        def _on_audio_changed(event=None):
            c_a = cb_audio.current()
            if 0 <= c_a < len(audio_tracks):
                t = audio_tracks[c_a]
                set_setting("preferred_audio_lang", t.get("language") or t.get("track_id") or "original")
        cb_audio.bind("<<ComboboxSelected>>", _on_audio_changed)
        cb_audio.pack(side=tk.LEFT, padx=(0, 14))

    if subtitle_tracks:
        tk.Label(row1, text=tr("lbl_subtitle_track", "≡ الترجمة:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright).pack(side=tk.LEFT, padx=(0, 6))
        cb_sub = ttk.Combobox(row1, values=[s.get("label", "") for s in subtitle_tracks], state="readonly", font=("Segoe UI", 8), width=23)
        pref_s = str(get_setting("preferred_subtitle_lang", "none") or "").lower()
        s_idx = next((i for i, s in enumerate(subtitle_tracks) if pref_s != "none" and pref_s in (str(s.get("language") or "").lower(), str(s.get("sub_id") or "").lower())), 0)
        cb_sub.current(s_idx)
        cb_sub._user_touched_mode = False
        cb_sub.pack(side=tk.LEFT, padx=(0, 8))

        mode_options = [
            ("soft_embed", tr("sub_mode_soft", "دمج ناعم")),
            ("srt_only", tr("sub_mode_srt_only", "ملف منفصل")),
            ("hard_burn", tr("sub_mode_burn", "حرق دائم")),
        ]
        mode_codes = [m[0] for m in mode_options]
        mode_labels = [m[1] for m in mode_options]
        saved_mode = get_setting("subtitle_embed_mode", "hard_burn")
        initial_idx = mode_codes.index(saved_mode) if saved_mode in mode_codes else 0
        current_mode = mode_codes[initial_idx]

        cb_sub_mode = ttk.Combobox(card, values=mode_labels, state="disabled", font=("Segoe UI", 8), width=20)
        cb_sub_mode.current(initial_idx)

        row2 = tk.Frame(card, bg=c_panel)
        row2.pack(fill=tk.X, pady=(2, 0))
        tk.Label(row2, text=tr("lbl_subtitle_mode", "⚙️ الوضع:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright).pack(side=tk.LEFT, padx=(0, 6))
        mode_var = tk.StringVar(master=card, value=current_mode)

        def _on_sub_changed(event=None):
            idx = cb_sub.current()
            if event is not None and 0 <= idx < len(subtitle_tracks):
                set_setting("preferred_subtitle_lang", subtitle_tracks[idx].get("language") or "none")
            if idx > 0:
                cb_sub_mode.configure(state="readonly")
                if not getattr(cb_sub, "_user_touched_mode", False):
                    cb_sub._selected_mode = "hard_burn"
                    mode_var.set("hard_burn")
                    if "hard_burn" in mode_codes:
                        cb_sub_mode.current(mode_codes.index("hard_burn"))
            else:
                cb_sub_mode.configure(state="disabled")
                cb_sub._user_touched_mode = False

        def _on_radio_click():
            chosen = mode_var.get()
            cb_sub._selected_mode = chosen
            cb_sub._user_touched_mode = True
            if chosen in mode_codes:
                cb_sub_mode.current(mode_codes.index(chosen))
            set_setting("subtitle_embed_mode", chosen)
            if cb_sub.current() <= 0 and len(subtitle_tracks) > 1:
                ar_idx = next((i for i, s in enumerate(subtitle_tracks) if i > 0 and str(s.get("language", "")).lower().startswith("ar")), 1)
                cb_sub.current(ar_idx)
                _on_sub_changed()

        radio_widgets = []
        for code, label_txt in mode_options:
            rb = tk.Radiobutton(row2, text=label_txt, value=code, variable=mode_var, command=_on_radio_click, bg=c_panel, fg=c_text_bright, selectcolor=c_input_bg, activebackground=c_panel, activeforeground=c_accent, cursor="hand2", font=("Segoe UI", 8, "bold"))
            rb.pack(side=tk.LEFT, padx=(0, 6))
            radio_widgets.append(rb)

        def _on_mode_var_changed(*_):
            val = mode_var.get()
            if val in mode_codes:
                cb_sub._selected_mode = val
                cb_sub._user_touched_mode = True
                idx = mode_codes.index(val)
                if cb_sub_mode.current() != idx:
                    cb_sub_mode.current(idx)
                if cb_sub.current() <= 0 and len(subtitle_tracks) > 1:
                    ar_idx = next((i for i, s in enumerate(subtitle_tracks) if i > 0 and str(s.get("language", "")).lower().startswith("ar")), 1)
                    cb_sub.current(ar_idx)
                    _on_sub_changed()

        try:
            mode_var.trace_add("write", _on_mode_var_changed)
        except Exception:
            try:
                mode_var.trace("w", _on_mode_var_changed)
            except Exception:
                pass

        # Subtitle Position Combobox
        tk.Label(row2, text=tr("lbl_subtitle_pos", "● الموضع:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright).pack(side=tk.LEFT, padx=(10, 4))
        pos_codes = ["bottom", "middle", "top"]
        pos_labels = [tr("sub_pos_bottom", "أسفل (Bottom)"), tr("sub_pos_middle", "وسط (Middle)"), tr("sub_pos_top", "أعلى (Top)")]
        cb_sub_pos = ttk.Combobox(row2, values=pos_labels, state="readonly", font=("Segoe UI", 8), width=14)
        saved_pos = get_setting("subtitle_position", "bottom")
        p_idx = pos_codes.index(saved_pos) if saved_pos in pos_codes else 0
        cb_sub_pos.current(p_idx)
        cb_sub_pos.pack(side=tk.LEFT, padx=(0, 6))

        def _on_pos_changed(event=None):
            c_p = cb_sub_pos.current()
            if 0 <= c_p < len(pos_codes):
                chosen_p = pos_codes[c_p]
                cb_sub._selected_pos = chosen_p
                if event is not None:
                    set_setting("subtitle_position", chosen_p)

        cb_sub_pos.bind("<<ComboboxSelected>>", _on_pos_changed)
        cb_sub._pos_combobox = cb_sub_pos
        cb_sub._selected_pos = pos_codes[p_idx]
        cb_sub.get_selected_pos = lambda: getattr(cb_sub, "_selected_pos", "bottom")

        def _on_mode_cb_changed(event=None):
            cur_idx = cb_sub_mode.current()
            if 0 <= cur_idx < len(mode_codes):
                code = mode_codes[cur_idx]
                cb_sub._selected_mode = code
                cb_sub._user_touched_mode = True
                mode_var.set(code)
                set_setting("subtitle_embed_mode", code)
                if cb_sub.current() <= 0 and len(subtitle_tracks) > 1:
                    ar_idx = next((i for i, s in enumerate(subtitle_tracks) if i > 0 and str(s.get("language", "")).lower().startswith("ar")), 1)
                    cb_sub.current(ar_idx)
                    _on_sub_changed()

        def _get_active_mode() -> str:
            cur_idx = cb_sub_mode.current()
            if 0 <= cur_idx < len(mode_codes):
                cb_code = mode_codes[cur_idx]
                if cb_code != getattr(cb_sub, "_selected_mode", None):
                    cb_sub._selected_mode = cb_code
                    if mode_var and mode_var.get() != cb_code:
                        mode_var.set(cb_code)
                    return cb_code
            if mode_var and mode_var.get() in mode_codes:
                val = mode_var.get()
                cb_sub._selected_mode = val
                idx = mode_codes.index(val)
                if cb_sub_mode.current() != idx:
                    cb_sub_mode.current(idx)
                return val
            if 0 <= cur_idx < len(mode_codes):
                return mode_codes[cur_idx]
            return getattr(cb_sub, "_selected_mode", "soft_embed")

        cb_sub._mode_combobox = cb_sub_mode
        cb_sub._mode_radios = radio_widgets
        cb_sub._mode_var = mode_var
        cb_sub._selected_mode = current_mode
        cb_sub._mode_codes = mode_codes
        cb_sub.get_selected_mode = _get_active_mode
        cb_sub._update_mode_state = _on_sub_changed

        cb_sub.bind("<<ComboboxSelected>>", _on_sub_changed)
        cb_sub_mode.bind("<<ComboboxSelected>>", _on_mode_cb_changed)
        if s_idx > 0:
            cb_sub_mode.configure(state="readonly")

    return cb_audio, cb_sub


__all__ = ["build_audio_subtitle_row"]
