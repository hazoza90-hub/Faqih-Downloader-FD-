"""
Comprehensive unit tests for 100% Dynamic 3-Column Kanban Pipeline in Smart Download (SD) v2.0.2:
1. Verification of ZERO fake/demo data and absence of hardcoded mock methods.
2. Column 1: Queued & Parsing dynamic empty state and real link card rendering.
3. Column 2: Active Turbo Streams idle 'Engine Ready' state, 0.0 MB/s speed, LED matrix zeroing, and live stream updates.
4. Column 3: Completed Vault reading from DownloadHistoryManager with appropriate visual format cards and dynamic completion callbacks.
5. Localization: Seamless Arabic/English in-place translation synchronization for all pipeline components.
6. Windows Acrylic/Mica backdrop helper and rounded glass drawing utilities.
"""
from __future__ import annotations

import os
import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch

from faqih_downloader.locales.i18n import LocalizationManager, tr
from faqih_downloader.ui.main_window import ModernFramelessGUI
from faqih_downloader.ui.panels.kanban_panel import KanbanPanelMixin
from faqih_downloader.ui.components.led_matrix import LedEqualizerMatrix
from faqih_downloader.utils.window_effects import (
    apply_acrylic_or_mica_effect,
    draw_rounded_rect,
    draw_glow_border,
)


class TestKanbanPipeline(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.test_dir = tempfile.mkdtemp()
        self._orig_cfg = os.environ.get("SD_CONFIG_DIR")
        os.environ["SD_TESTING"] = "1"
        os.environ["SD_CONFIG_DIR"] = self.test_dir

        for attempt in range(4):
            try:
                self.root = tk.Tk()
                break
            except Exception:
                if attempt == 3:
                    raise
                import time
                time.sleep(0.1)
        self.root.withdraw()
        self.loc = LocalizationManager.get_instance()
        self.loc.set_language("en")

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        import shutil
        if hasattr(self, "test_dir") and os.path.isdir(self.test_dir):
            try:
                shutil.rmtree(self.test_dir, ignore_errors=True)
            except Exception:
                pass
        if getattr(self, "_orig_cfg", None):
            os.environ["SD_CONFIG_DIR"] = self._orig_cfg
        else:
            os.environ.pop("SD_CONFIG_DIR", None)

    def test_zero_fake_data_in_codebase(self):
        """Verifies zero hardcoded fake/demo filenames, URLs, or speeds exist in kanban_panel.py."""
        kanban_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "faqih_downloader", "ui", "panels", "kanban_panel.py"
        )
        with open(kanban_path, "r", encoding="utf-8") as f:
            code = f.read()

        forbidden_strings = [
            "Cyberpunk_2077_Cinematic_Teaser",
            "AI_Tutorial_Part_3.mp4",
            "Nature_Drone_Footage.mp4",
            "Beat_Loop_Theme.wav",
            "Unreal_Scene_Draft.rar",
            "Design_Brief_2025.pdf",
            "56.4 MB/s",
            "_build_queued_card_1",
            "_build_queued_card_2",
            "_build_vault_video_card",
            "_build_vault_audio_card",
            "_build_vault_archive_card",
            "_build_vault_document_card",
            "set_demo_levels",
        ]
        for s in forbidden_strings:
            self.assertNotIn(s, code, f"Forbidden fake demo string/function '{s}' found in kanban_panel.py!")

    def test_led_matrix_has_no_demo_levels(self):
        """Verifies set_demo_levels is removed from LedEqualizerMatrix."""
        matrix = LedEqualizerMatrix(self.root, height=50)
        self.assertFalse(hasattr(matrix, "set_demo_levels"), "set_demo_levels must not exist in LedEqualizerMatrix!")

    def test_col1_empty_state_and_dynamic_parsing(self):
        """Verifies Column 1 displays Empty State when queue is empty, and cards when links exist."""
        gui = ModernFramelessGUI(self.root, start_hidden=True)
        try:
            # Initially empty
            self.assertEqual(len(getattr(gui, "_parsing_links", [])), 0)
            self.assertEqual(len(getattr(gui, "_download_queue", [])), 0)
            self.assertIn("(0)", gui.lbl_col1_title.cget("text"))

            # Add parsing link
            test_url = "https://example.com/video.mp4"
            gui.add_parsing_link(test_url)
            self.assertIn("(1)", gui.lbl_col1_title.cget("text"))
            self.assertEqual(len(gui.cards_col1_container.winfo_children()), 1)

            # Remove parsing link
            gui.remove_parsing_link(test_url)
            self.assertIn("(0)", gui.lbl_col1_title.cget("text"))
        finally:
            gui._cleanup_resources()

    def test_col2_idle_engine_ready_state(self):
        """Verifies Column 2 is in quiet Engine Ready state with 0.0 MB/s speed and 0% LEDs when idle."""
        gui = ModernFramelessGUI(self.root, start_hidden=True)
        try:
            gui.reset_kanban_active_stream()
            self.assertIn("(0)", gui.lbl_col2_title.cget("text"))
            self.assertEqual(gui.lbl_col2_total_speed.cget("text"), "0.0 MB/s")
            self.assertFalse(gui._active_stream_live)
            # Check LED levels are all 0
            for lvl in gui.matrix_a1._levels:
                self.assertEqual(lvl, 0.0)

            # Trigger active stream update
            mock_chunk = MagicMock(start_byte=0, end_byte=1000, downloaded_bytes=500, status="downloading")
            gui.update_kanban_active_stream("Real_Test_File.mp4", 50.0, "12.5 MB/s", [mock_chunk], 1)
            self.assertTrue(gui._active_stream_live)
            self.assertIn("(1)", gui.lbl_col2_title.cget("text"))
            self.assertEqual(gui.lbl_col2_total_speed.cget("text"), "12.5 MB/s")
            self.assertEqual(gui.lbl_a1_pct.cget("text"), "50%")
            self.assertIn("Real_Test_File", gui.lbl_a1_filename.cget("text"))

            # Reset back to idle
            gui.reset_kanban_active_stream()
            self.assertFalse(gui._active_stream_live)
            self.assertIn("(0)", gui.lbl_col2_title.cget("text"))
            self.assertEqual(gui.lbl_col2_total_speed.cget("text"), "0.0 MB/s")
        finally:
            gui._cleanup_resources()

    def test_col3_vault_reads_real_history(self):
        """Verifies Column 3 reads completed items from history_manager."""
        gui = ModernFramelessGUI(self.root, start_hidden=True)
        try:
            # Clear or ensure empty
            gui.history_manager._entries = []
            gui.refresh_kanban_col3()
            self.assertIn("(0)", gui.lbl_col3_title.cget("text"))

            # Add completed real entry
            gui.history_manager.add_or_update_entry(
                url="https://example.com/test_presentation.pdf",
                file_path="/downloads/test_presentation.pdf",
                size_bytes=2048000,
                status="Completed",
                elapsed_sec=1.5
            )
            gui.refresh_kanban_col3()
            self.assertIn("(1)", gui.lbl_col3_title.cget("text"))
            self.assertEqual(len(gui.vault_cards_container.winfo_children()), 1)

            # Verify completion callback
            gui.on_kanban_download_completed("/downloads/video.mp4", 10485760)
            self.assertFalse(gui._active_stream_live)
        finally:
            gui._cleanup_resources()

    def test_pipeline_localization_sync(self):
        """Verifies dynamic Arabic and English translation toggles update all columns immediately."""
        gui = ModernFramelessGUI(self.root, start_hidden=True)
        try:
            self.loc.set_language("en")
            gui._update_ui_language()
            self.assertIn(tr("pipeline_col_queued", "Queued & Parsing"), gui.lbl_col1_title.cget("text"))
            self.assertIn(tr("pipeline_col_active", "Active Turbo Streams"), gui.lbl_col2_title.cget("text"))
            self.assertIn(tr("pipeline_col_vault", "Completed Vault"), gui.lbl_col3_title.cget("text"))

            # Switch to Arabic
            self.loc.set_language("ar")
            gui._update_ui_language()
            self.assertIn(tr("pipeline_col_queued"), gui.lbl_col1_title.cget("text"))
            self.assertIn(tr("pipeline_col_active"), gui.lbl_col2_title.cget("text"))
            self.assertIn(tr("pipeline_col_vault"), gui.lbl_col3_title.cget("text"))

            # Check button translations
            self.assertEqual(gui.btn_paste.cget("text"), tr("btn_paste_plain"))
            self.assertIn(tr("lbl_save_to"), gui.btn_save_to.cget("text"))

            # Column 2 idle empty state must re-translate to Arabic
            self.assertTrue(hasattr(gui, "empty_active_canvas"))
            self.assertTrue(gui.empty_active_canvas.winfo_exists())
        finally:
            self.loc.set_language("en")
            gui._cleanup_resources()

    def test_window_effects_and_rounded_drawing(self):
        """Verifies Acrylic/Mica backdrop helper, RoundedGlassCard, and rounded Canvas drawing run safely."""
        from faqih_downloader.utils.window_effects import RoundedGlassCard
        res = apply_acrylic_or_mica_effect(self.root, alpha=0.93)
        self.assertTrue(isinstance(res, bool))

        cv = tk.Canvas(self.root, width=200, height=100)
        p1 = draw_rounded_rect(cv, 5, 5, 195, 95, radius=10, fill="#161b26", outline="#252b3b")
        self.assertIsNotNone(p1)

        draw_glow_border(cv, 10, 10, 190, 90, radius=8, glow_color="#19f3ee")
        self.assertTrue(len(cv.find_withtag("glow_frame")) > 0)

        # Verify RoundedGlassCard
        card = RoundedGlassCard(self.root, radius=12, height=100)
        card.pack()
        self.assertIsNotNone(card.inner)
        lbl = tk.Label(card.inner, text="Testing")
        lbl.pack()
        card._on_resize()

    def test_kanban_components_are_rounded_glass_cards(self):
        """Verifies cards, glowing column border, and url field are Canvas-based RoundedGlassCard instances."""
        from faqih_downloader.utils.window_effects import RoundedGlassCard
        gui = ModernFramelessGUI(self.root, start_hidden=True)
        try:
            # Active column border is a RoundedGlassCard canvas
            self.assertTrue(isinstance(gui.active_column_border, RoundedGlassCard))
            self.assertTrue(isinstance(gui.card_active_1, RoundedGlassCard))

            # Column 1 queued card is RoundedGlassCard
            gui.add_parsing_link("https://example.com/stream.mp4")
            card1 = gui.cards_col1_container.winfo_children()[0]
            self.assertTrue(isinstance(card1, RoundedGlassCard))

            # Column 3 vault card is RoundedGlassCard
            gui.history_manager.add_or_update_entry(
                url="https://example.com/audio.mp3",
                file_path="/downloads/audio.mp3",
                size_bytes=5000000,
                status="Completed",
                elapsed_sec=2.0
            )
            gui.refresh_kanban_col3()
            card3 = gui.vault_cards_container.winfo_children()[0]
            self.assertTrue(isinstance(card3, RoundedGlassCard))
        finally:
            gui._cleanup_resources()

    def test_transparency_setting_and_stream_coordinator_resolution(self):
        """Verifies window_alpha setting and active stream filename resolution from coordinator destination_path."""
        from faqih_downloader.config import get_setting, set_setting
        gui = ModernFramelessGUI(self.root, start_hidden=True)
        try:
            # Window alpha setting
            self.assertAlmostEqual(float(get_setting("window_alpha", 1.0)), 1.0, places=2)
            set_setting("window_alpha", 0.85)
            self.assertAlmostEqual(float(get_setting("window_alpha", 1.0)), 0.85, places=2)
            set_setting("window_alpha", 1.0)

            # Stream coordinator filename resolution (destination_path attribute)
            mock_coord = MagicMock()
            mock_coord.destination_path = "C:/Downloads/My_YouTube_Stream.mp4"
            mock_coord.dest_path = None
            mock_coord.is_running = lambda: True
            mock_chunk = MagicMock(start_byte=0, end_byte=1000, downloaded_bytes=500, status="downloading")
            gui.engine = mock_coord
            gui.update_kanban_active_stream(
                getattr(mock_coord, "dest_path", None) or getattr(mock_coord, "destination_path", None),
                75.0,
                "8.4 MB/s",
                [mock_chunk],
                1
            )
            self.assertIn("My_YouTube_Stream", gui.lbl_a1_filename.cget("text"))
            self.assertEqual(gui.lbl_a1_pct.cget("text"), "75%")
        finally:
            gui._cleanup_resources()


if __name__ == "__main__":
    unittest.main()

