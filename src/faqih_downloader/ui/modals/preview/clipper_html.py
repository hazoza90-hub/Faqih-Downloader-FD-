"""
clipper_html.py: HTML toolbar markup for live clipper controls, chapters selector, audio boost, and subtitle editor modal.
"""
from __future__ import annotations

import html as _html
from typing import Any, Dict, List, Optional


def get_clipper_toolbar_html(
    clip_start: float = 0.0, clip_end: float = 0.0, dual_sub: bool = False,
    audio_boost: bool = False, chapters: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Generates HTML markup for the clipper toolbar, chapters selector, audio booster, and subtitle editor."""
    clip_start, clip_end = float(clip_start or 0.0), float(clip_end or 0.0)
    c_s = f"{int(clip_start//60):02d}:{int(clip_start%60):02d}" if clip_start > 0 else "00:00"
    c_e = f"{int(clip_end//60):02d}:{int(clip_end%60):02d}" if clip_end > 0 else "00:00"
    badge_txt = f"المقطع: {int((clip_end-clip_start)//60):02d}:{int((clip_end-clip_start)%60):02d}" if clip_end > clip_start else "المقطع: كامل الفيديو"

    def _fmt_ts(sec: float) -> str:
        sec = max(0.0, float(sec or 0.0))
        s, m, h = int(sec % 60), int((sec / 60) % 60), int(sec / 3600)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    if chapters and isinstance(chapters, list) and len(chapters) > 0:
        is_auto = any(isinstance(ch, dict) and ch.get("is_auto") for ch in chapters)
        header_title = f"📑 الفصول ({len(chapters)} جزء بالتقسيم الذكي - اختر لتحميله)" if is_auto else f"📑 الفصول ({len(chapters)} فصل متاح - اختر لتحميله)"
        opts = [f'<option value="">{header_title}</option>']
        for idx, ch in enumerate(chapters):
            s_t = float(ch.get("start_time", 0.0) or 0.0)
            e_t = float(ch.get("end_time", 0.0) or 0.0)
            s_str = _fmt_ts(s_t)
            e_str = _fmt_ts(e_t)
            t_label = _html.escape(str(ch.get("title", f"فصل {idx+1}") or f"فصل {idx+1}").strip())
            opts.append(f'<option value="{idx}" data-start="{s_t:.2f}" data-end="{e_t:.2f}" data-title="{t_label}">[{s_str} - {e_str}] {t_label}</option>')
    else:
        opts = ['<option value="">📑 الفصول (تقسيم ذكي للمقطع...)</option>']
    chapters_html = f'<div class="clipper-group"><select id="chapterSelect" class="clipper-input" style="width:165px;text-align:right;" onchange="onChapterSelectChange()">{"".join(opts)}</select></div>'

    boost_cls = " active" if audio_boost else ""
    return f"""<div class="clipper-bar" id="clipperBar">
<div class="clipper-group">
  <button type="button" class="studio-btn-pill" onclick="setClipStartFromCurrent()" title="تعيين بداية القص من الموضع الحالي">✂️ بداية القص Set Start</button>
  <input type="text" id="clipStartInput" class="clipper-input" value="{c_s}" placeholder="00:00" onchange="onClipInputChange()" />
  <label style="color:#64748b;">—</label>
  <input type="text" id="clipEndInput" class="clipper-input" value="{c_e}" placeholder="00:00" onchange="onClipInputChange()" />
  <button type="button" class="studio-btn-pill" onclick="setClipEndFromCurrent()" title="تعيين نهاية القص من الموضع الحالي">✂️ نهاية القص Set End</button>
</div>
{chapters_html}
<div class="clipper-group">
  <button type="button" class="studio-btn-pill" id="btnLoopClip" onclick="toggleClipLoop()" title="معاينة دائرية متكررة للمقطع">▶ معاينة المقطع Loop</button>
  <span id="clipDurationBadge" class="badge badge-dim">{badge_txt}</span>
  <button type="button" class="studio-btn-pill" onclick="resetClipRange()" title="إلغاء القص واستعادة كامل الفيديو">↺ كامل الفيديو</button>
</div>
<div class="clipper-group" style="margin-left:auto;gap:6px;">
  <button type="button" class="studio-btn-pill" id="btnEditSubText" onclick="openSubTextEditor()" title="تعديل نص الترجمة الحالية أو اضغط مرتين على الترجمة">✏️ تعديل النص</button>
  <button type="button" class="studio-btn-pill{' active' if dual_sub else ''}" id="btnDualSub" onclick="toggleDualSubtitles()" title="عرض ترجمة مزدوجة عربي + أجنبي">🌍 ترجمة مزدوجة</button>
  <button type="button" class="studio-btn-pill{boost_cls}" id="btnAudioBoost" onclick="toggleStudioAudioBoost()" title="تعزيز وتصفية الصوت المنخفض في المعاينة وعند التحميل">🎙️ تعزيز الصوت Boost</button>
</div>
</div>
<div id="subEditModal" class="sub-edit-modal" style="display:none;">
  <div class="sub-edit-header">
    <span>✏️ تصحيح نص الترجمة (Live Subtitle Fixer)</span>
    <span id="subEditTimeBadge" class="badge badge-dim">00:00 --> 00:00</span>
  </div>
  <textarea id="subEditTextArea" class="sub-edit-textarea" placeholder="اكتب التصحيح هنا..."></textarea>
  <div class="sub-edit-actions">
    <button type="button" class="studio-btn-pill active" onclick="saveSubTextEdit()">✓ حفظ التعديل</button>
    <button type="button" class="studio-btn-pill" onclick="closeSubTextEditor()">✕ إلغاء</button>
  </div>
</div>"""


__all__ = ["get_clipper_toolbar_html"]
