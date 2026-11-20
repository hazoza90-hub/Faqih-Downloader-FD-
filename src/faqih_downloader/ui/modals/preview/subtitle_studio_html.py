"""
subtitle_studio_html.py: HTML markup for the interactive subtitle styling toolbar.
"""
from __future__ import annotations


def get_studio_toolbar_html(
    preset: str = "youtube", scale: float = 1.0, color: str = "#FFFFFF",
    bg_mode: str = "box", pos_x: float = 50.0, pos_y: float = 86.0
) -> str:
    """Generates the HTML markup for the interactive subtitle styling toolbar."""
    p, bg, c = str(preset or "youtube").lower(), str(bg_mode or "box").lower(), str(color or "#FFFFFF").upper()
    return f"""<div class="sub-studio-bar" id="subStudioBar">
<div class="sub-studio-group">
  <label>🎨 Style / النمط:</label>
  <button type="button" class="studio-btn-pill{' active' if p == 'youtube' else ''}" id="btnPreYt" onclick="setSubPreset('youtube')">YouTube (افتراضي)</button>
  <button type="button" class="studio-btn-pill{' active' if p == 'tiktok' else ''}" id="btnPreTt" onclick="setSubPreset('tiktok')">TikTok بارز</button>
  <button type="button" class="studio-btn-pill{' active' if p == 'golden' else ''}" id="btnPreGold" onclick="setSubPreset('golden')">ذهبي</button>
  <button type="button" class="studio-btn-pill{' active' if p == 'custom' else ''}" id="btnPreCust" onclick="setSubPreset('custom')">مخصص</button>
</div>
<div class="sub-studio-group">
  <label>🔤 Size / الحجم:</label>
  <input type="range" id="subScaleSlider" min="0.6" max="1.5" step="0.05" value="{scale:.2f}" style="width:65px;accent-color:#38bdf8;cursor:pointer;" oninput="onSubScaleChange(this.value)">
  <span id="subScaleLabel" style="color:#cbd5e1;min-width:26px;">{int(scale * 100)}%</span>
</div>
<div class="sub-studio-group" id="customColorGroup">
  <label>Color:</label>
  <span class="color-dot{' active' if c == '#FFFFFF' else ''}" style="background:#ffffff;" title="White" onclick="setSubColor('#FFFFFF', this)"></span>
  <span class="color-dot{' active' if c == '#FFD700' else ''}" style="background:#ffd700;" title="Gold" onclick="setSubColor('#FFD700', this)"></span>
  <span class="color-dot{' active' if c == '#00FFFF' else ''}" style="background:#00ffff;" title="Cyan" onclick="setSubColor('#00FFFF', this)"></span>
  <span class="color-dot{' active' if c == '#4ADE80' else ''}" style="background:#4ade80;" title="Green" onclick="setSubColor('#4ADE80', this)"></span>
</div>
<div class="sub-studio-group">
  <label>Bg:</label>
  <button type="button" class="studio-btn-pill{' active' if bg == 'box' else ''}" id="btnBgBox" onclick="setSubBgMode('box')">صندوق</button>
  <button type="button" class="studio-btn-pill{' active' if bg == 'outline' else ''}" id="btnBgOutline" onclick="setSubBgMode('outline')">حواف</button>
</div>
<div class="sub-studio-group" style="margin-left:auto;">
  <button type="button" class="studio-btn-pill" onclick="resetSubPosition()" title="Reset subtitle position">↺ Reset Pos</button>
</div>
</div>"""


__all__ = ["get_studio_toolbar_html"]
