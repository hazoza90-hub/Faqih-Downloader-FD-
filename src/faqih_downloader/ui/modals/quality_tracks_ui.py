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
    from faqih_downloader.config import get_setting, set_setting, is_test_environment
except Exception:
    def get_setting(k: str, d: Any = None) -> Any: return d  # type: ignore
    def set_setting(k: str, v: Any) -> bool: return True  # type: ignore
    def is_test_environment() -> bool: return False  # type: ignore


def format_ext_srt_button_text(selected_tracks: List[Dict[str, Any]]) -> str:
    """Formats button summary text for selected external .SRT languages, e.g. 'AR, EN (2)' or 'بدون (0)'."""
    codes: List[str] = []
    seen = set()
    for trk in (selected_tracks or []):
        if not isinstance(trk, dict):
            continue
        raw = str(trk.get("language") or trk.get("sub_id") or "").strip()
        if not raw or raw.lower() == "none":
            continue
        code = raw.split("-")[0].split("_")[0].upper()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    if not codes:
        return tr("btn_ext_srt_none", "بدون (0)")
    head = ", ".join(codes[:3]) + (f" +{len(codes) - 3}" if len(codes) > 3 else "")
    return f"{head} ({len(codes)})"


def open_ext_srt_popup_menu(
    widget: Any,
    subtitle_tracks: List[Dict[str, Any]],
    selected_tracks: List[Dict[str, Any]],
    on_change: Any,
    theme: Optional[Dict[str, str]] = None,
) -> Optional[Any]:
    """Opens dark multi-select popup menu allowing selection of zero or more external .SRT tracks."""
    if tk is None or widget is None:
        return None
    t = theme or {}
    c_bg = t.get("c_panel", "#1e293b")
    c_fg = t.get("c_text_bright", "#f8fafc")
    c_acc = t.get("c_accent", "#38bdf8")
    menu = tk.Menu(widget, tearoff=0, bg=c_bg, fg=c_fg, activebackground=c_acc, activeforeground="#0f172a", selectcolor=c_acc, font=("Segoe UI", 9))
    menu._vars = {}
    menu._tracks = [
        s for s in (subtitle_tracks or [])
        if isinstance(s, dict) and str(s.get("sub_id") or "").lower() != "none" and str(s.get("language") or "").lower() != "none"
    ]
    sel_langs = {str(s.get("language") or s.get("sub_id") or "").strip().lower() for s in (selected_tracks or []) if isinstance(s, dict)}
    menu.add_command(label=tr("menu_ext_srt_clear", "✕ عدم تنزيل ملفات خارجية (مسح الكل)"), command=lambda: on_change([]))
    if menu._tracks:
        menu.add_separator()

    def _on_toggle():
        picked = [
            s for s in menu._tracks
            if (var := menu._vars.get(str(s.get("language") or s.get("sub_id") or "").strip().lower())) is not None and bool(var.get())
        ]
        on_change(picked)

    for s in menu._tracks:
        lc = str(s.get("language") or s.get("sub_id") or "").strip().lower()
        var = tk.BooleanVar(master=menu, value=(lc in sel_langs))
        menu._vars[lc] = var
        menu.add_checkbutton(label=s.get("label") or lc.upper(), variable=var, onvalue=True, offvalue=False, command=_on_toggle)

    widget._ext_srt_menu = menu
    if not is_test_environment() and getattr(widget, "winfo_ismapped", lambda: False)():
        try:
            menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        except Exception:
            pass
    return menu


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
            ("soft_embed", tr("sub_mode_soft", "دمج ناعم (Soft Embed)")),
            ("hard_burn", tr("sub_mode_burn", "حرق دائم (Burn-in)")),
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

        cb_sub._external_subtitle_tracks = []
        lbl_ext_srt = tk.Label(row2, text=tr("lbl_ext_srt", "❏ خارجي:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright)
        lbl_ext_srt.pack(side=tk.LEFT, padx=(8, 4))
        btn_ext_srt = tk.Button(
            row2, text=format_ext_srt_button_text([]), font=("Segoe UI", 8, "bold"),
            bg=c_input_bg, fg=c_text_bright, activebackground=c_accent, activeforeground="#0f172a",
            relief="flat", bd=1, padx=8, pady=2, cursor="hand2"
        )
        btn_ext_srt.pack(side=tk.LEFT, padx=(0, 6))

        def _set_ext_tracks(tracks: List[Dict[str, Any]], notify: bool = True):
            clean = [dict(t) for t in (tracks or []) if isinstance(t, dict) and str(t.get("sub_id") or "").lower() != "none"]
            cb_sub._external_subtitle_tracks = clean
            if btn_ext_srt.winfo_exists():
                btn_ext_srt.configure(text=format_ext_srt_button_text(clean))
            if notify:
                cb_fn = getattr(cb_sub, "_on_ext_srt_changed", None)
                if callable(cb_fn):
                    cb_fn(clean)

        def _open_ext_menu():
            open_ext_srt_popup_menu(
                btn_ext_srt, subtitle_tracks, getattr(cb_sub, "_external_subtitle_tracks", []),
                lambda picked: _set_ext_tracks(picked, notify=True), theme=theme
            )

        btn_ext_srt.configure(command=_open_ext_menu)
        cb_sub._ext_srt_label = lbl_ext_srt
        cb_sub._ext_srt_button = btn_ext_srt
        cb_sub.get_external_subtitle_tracks = lambda: list(getattr(cb_sub, "_external_subtitle_tracks", []) or [])
        cb_sub.set_external_subtitle_tracks = _set_ext_tracks
        cb_sub.open_external_subtitles_menu = _open_ext_menu

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

        # Connections / Threads Combobox (on dedicated row3 so Arabic labels/controls never clip on row2)
        row3 = tk.Frame(card, bg=c_panel)
        row3.pack(fill=tk.X, pady=(4, 0))
        is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))
        tk.Label(row3, text=tr("lbl_modal_threads", "⚡ المسارات:" if is_ar else "⚡ Threads:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright).pack(side=tk.LEFT, padx=(0, 6))
        conn_vals = ["1", "2", "4", "8", "16", "32"]
        cb_conn = ttk.Combobox(row3, values=conn_vals, state="readonly", font=("Segoe UI", 8), width=8)
        saved_conn = str(get_setting("max_connections", 8))
        if saved_conn not in conn_vals: saved_conn = "8"
        cb_conn.set(saved_conn)
        cb_conn.pack(side=tk.LEFT, padx=(0, 6))

        def _on_conn_changed(event=None):
            val = str(cb_conn.get()).strip()
            if val.isdigit() and int(val) in (1, 2, 4, 8, 16, 24, 32):
                set_setting("max_connections", int(val))
                cb_sub._selected_connections = int(val)
                try:
                    w = parent_frame
                    while w:
                        parent_app = getattr(w, "parent_app", None)
                        if parent_app and hasattr(parent_app, "conn_var"):
                            parent_app.conn_var.set(val)
                            break
                        w = getattr(w, "master", None)
                except Exception:
                    pass

        cb_conn.bind("<<ComboboxSelected>>", _on_conn_changed)
        cb_sub._conn_combobox = cb_conn
        cb_sub._selected_connections = int(saved_conn)
        cb_sub.get_selected_connections = lambda: getattr(cb_sub, "_selected_connections", 8)
        # Backward-compatibility attributes for existing tests/callers expecting pos attributes:
        cb_sub._pos_combobox = cb_conn
        cb_sub._selected_pos = "bottom"
        cb_sub.get_selected_pos = lambda: "bottom"

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


__all__ = ["format_ext_srt_button_text", "open_ext_srt_popup_menu", "build_audio_subtitle_row"]
