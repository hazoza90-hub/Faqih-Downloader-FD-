"""
ChunksVisualizerMixin: Dynamic chunk visualization canvas and segment byte map.
"""
from __future__ import annotations
from typing import List, Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr, get_current_language


class ChunksVisualizerMixin:
    """Provides methods for building and updating the real-time chunk segment visualizer."""

    def _build_chunk_visualizer_card(self, parent):
        """Visual TDM-style horizontal segmented chunk block visualizer."""
        card = tk.Frame(parent, bg=self.c_panel, padx=14, pady=8, relief="flat", highlightbackground=self.c_border, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        header_row = tk.Frame(card, bg=self.c_panel)
        header_row.pack(fill=tk.X, pady=(0, 4))

        self.lbl_chunk_vis_title = tk.Label(header_row, text=tr("lbl_chunk_vis_title", "▦ SD DYNAMIC CHUNK VISUALIZER (Segmented Byte Map)"), font=("Segoe UI", 9, "bold"), bg=self.c_panel, fg=self.c_accent)
        self.lbl_chunk_vis_title.pack(side=tk.LEFT)

        self.lbl_chunk_vis_legend = tk.Label(header_row, text=tr("lbl_chunk_vis_legend", "■ نشط (سماوي)   ■ مكتمل (أخضر)   ■ متبقي (داكن)"), font=("Segoe UI", 8), bg=self.c_panel, fg=self.c_text_muted)
        self.lbl_chunk_vis_legend.pack(side=tk.RIGHT)

        chunks_height = max(28, int(28 * getattr(self, "dpi_scale", 1.0)))
        self.canvas_chunks = tk.Canvas(card, height=chunks_height, bg=self.c_input_bg, highlightthickness=1, highlightbackground=self.c_border)
        self.chunk_canvas = self.canvas_chunks
        self.canvas_chunks.pack(fill=tk.X)
        self.canvas_chunks.bind("<Configure>", lambda e: self._draw_chunk_segments(getattr(self.engine, "chunks", []) if getattr(self, "engine", None) and hasattr(self.engine, "chunks") and isinstance(self.engine.chunks, (list, tuple)) else []))
        self._draw_chunk_segments([])

    def _draw_chunk_segments(self, chunks: List[Any]):
        canvas = getattr(self, "chunk_canvas", None) or getattr(self, "canvas_chunks", None)
        if not canvas:
            return
        w = canvas.winfo_width()
        if w <= 10:
            w = 910
        h = canvas.winfo_height()
        if h <= 6:
            h = max(28, int(28 * getattr(self, "dpi_scale", 1.0)))

        if not isinstance(chunks, (list, tuple)):
            chunks = []

        total_size = 0
        if getattr(self, "engine", None):
            raw_ts = getattr(self.engine, "total_size", 0)
            try:
                total_size = int(raw_ts)
            except Exception:
                total_size = 0

        # Cache lightweight visual signature to eliminate redundant 4x/sec canvas redraws
        chunk_sig = []
        try:
            for c in chunks:
                with c.lock:
                    span = max(1, c.end_byte - c.start_byte + 1)
                    ratio_int = int((c.downloaded_bytes / span) * 1000)
                    chunk_sig.append((c.chunk_id, c.start_byte, c.end_byte, ratio_int, c.status))
        except Exception:
            chunk_sig = []
        current_lang = get_current_language() if callable(get_current_language) else getattr(self, "_current_lang", "")
        current_sig = (w, h, tuple(chunk_sig), total_size, current_lang)

        if getattr(self, "_last_chunk_canvas_sig", None) == current_sig:
            return
        self._last_chunk_canvas_sig = current_sig

        canvas.delete("all")

        c_input_bg = getattr(self, "c_input_bg", "#090e1a")
        c_border = getattr(self, "c_border", "#283548")
        c_text_muted = getattr(self, "c_text_muted", "#94a3b8")
        c_success = getattr(self, "c_success", "#10b981")
        c_accent = getattr(self, "c_accent", "#38bdf8")

        # Background track
        canvas.create_rectangle(0, 0, w, h, fill=c_input_bg, outline=c_border)

        if not chunks or not getattr(self, "engine", None) or total_size <= 0:
            msg = tr("lbl_waiting_to_start", "بانتظار بدء التحميل...") if not getattr(self, "engine", None) else tr("lbl_single_stream", "مسار واحد / حجم غير معروف")
            canvas.create_text(w / 2, h / 2, text=msg, font=("Segoe UI", 9), fill=c_text_muted, anchor="center")
            return

        for c in chunks:
            with c.lock:
                start_x = (c.start_byte / total_size) * w
                end_x = ((c.end_byte + 1) / total_size) * w
                done_x = min(end_x, ((c.start_byte + c.downloaded_bytes) / total_size) * w)
                status = c.status

            chunk_w = max(1.0, end_x - start_x)

            # Segment un-downloaded portion
            canvas.create_rectangle(start_x, 2, end_x, h - 2, fill="#1e293b", outline="")

            # Segment downloaded portion
            if done_x > start_x:
                fill_color = c_success if status == "completed" else c_accent
                canvas.create_rectangle(start_x, 2, done_x, h - 2, fill=fill_color, outline="")

            # Chunk divider line
            canvas.create_line(end_x, 0, end_x, h, fill=c_border, width=1)

            # Chunk label if wide enough
            if chunk_w > 36:
                mid_x = (start_x + end_x) / 2
                canvas.create_text(mid_x, h / 2, text=f"#{c.chunk_id}", font=("Segoe UI", 8, "bold"), fill="white")

    def _refresh_chunk_displays(self):
        if not getattr(self, "engine", None):
            return

        if hasattr(self.engine, "get_chunks_snapshot"):
            chunks_copy = self.engine.get_chunks_snapshot()
        else:
            chunks_copy = list(getattr(self.engine, "chunks", []))

        # 1. Update Visual Segment Map
        self._draw_chunk_segments(chunks_copy)

        # 2. Update Table Rows with fast set lookup
        existing_items = set(self.tree_chunks.get_children())
        current_ids = set()
        for idx, c in enumerate(chunks_copy):
            with c.lock:
                item_id = f"c_{c.chunk_id}"
                current_ids.add(item_id)
                span = max(1, c.end_byte - c.start_byte + 1)
                pct_val = min(100.0, (c.downloaded_bytes / span) * 100.0)
                span_str = f"{span:,} B"
                done_str = f"{c.downloaded_bytes:,} B"
                pct_str = f"{pct_val:.1f}%"
                if c.status == "failed" and any(k in str(c.error_msg).lower() for k in ("expired", "401", "403", "410", "forbidden")):
                    status_str = "Expired ⚠️"
                else:
                    status_str = c.status.capitalize()
                range_str = f"{c.start_byte:,} — {c.end_byte:,}"

            vals = (f"#{c.chunk_id}", range_str, span_str, done_str, pct_str, status_str)

            if item_id in existing_items:
                self.tree_chunks.item(item_id, values=vals)
            else:
                self.tree_chunks.insert("", tk.END, iid=item_id, values=vals)

        # Prune any stale chunk rows (e.g. from previous stream phases)
        for stale_id in (existing_items - current_ids):
            self.tree_chunks.delete(stale_id)
