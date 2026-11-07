"""
Smart Live Clipper & Dual Bilingual Subtitle Studio (preview_clipper_studio.py).
Provides HTML, CSS, and client-side JavaScript for live interactive clip trimming,
double-click subtitle text correction, and real-time dual bilingual subtitles.
"""
from __future__ import annotations

def get_clipper_css() -> str:
    """Returns CSS rules for the live clipper bar, text editor modal, and dual subtitles."""
    return """
.clipper-bar {
    display: flex; flex-wrap: wrap; align-items: center; background: #131d31;
    border: 1px solid #1e293b; border-radius: 6px; padding: 4px 10px; gap: 8px; font-size: 11px;
}
.clipper-group { display: flex; align-items: center; gap: 5px; }
.clipper-group label { font-weight: 600; color: #94a3b8; white-space: nowrap; }
.clipper-input {
    width: 58px; background: #17233c; color: #38bdf8; border: 1px solid #334155;
    padding: 2px 4px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; outline: none;
}
.clipper-input:focus { border-color: #38bdf8; box-shadow: 0 0 0 1px #38bdf8; }
.sub-edit-modal {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.85); padding: 12px 14px; z-index: 60;
    width: 88%; max-width: 460px; display: flex; flex-direction: column; gap: 8px;
    box-sizing: border-box;
}
.sub-edit-header { display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 700; color: #38bdf8; }
.sub-edit-textarea {
    width: 100%; min-height: 60px; background: #17233c; color: #f8fafc;
    border: 1px solid #334155; border-radius: 5px; padding: 6px 8px; font-size: 13px;
    line-height: 1.4; outline: none; resize: vertical; box-sizing: border-box; font-family: inherit;
}
.sub-edit-textarea:focus { border-color: #38bdf8; }
.sub-edit-actions { display: flex; justify-content: flex-end; gap: 8px; }
.dual-sub-secondary {
    display: block; font-size: 0.78em; color: #e2e8f0; opacity: 0.92;
    margin-top: 3px; font-weight: 500; letter-spacing: 0.2px; text-shadow: 0 1px 2px rgba(0,0,0,0.8);
}
""".strip()

def get_clipper_toolbar_html(clip_start: float = 0.0, clip_end: float = 0.0, dual_sub: bool = False) -> str:
    """Generates HTML markup for the clipper toolbar and floating subtitle text editor modal."""
    c_s = f"{int(clip_start//60):02d}:{int(clip_start%60):02d}" if clip_start > 0 else "00:00"
    c_e = f"{int(clip_end//60):02d}:{int(clip_end%60):02d}" if clip_end > 0 else "00:00"
    badge_txt = f"المقطع: {int((clip_end-clip_start)//60):02d}:{int((clip_end-clip_start)%60):02d}" if clip_end > clip_start else "المقطع: كامل الفيديو"
    return f"""<div class="clipper-bar" id="clipperBar">
<div class="clipper-group">
  <button type="button" class="studio-btn-pill" onclick="setClipStartFromCurrent()" title="تعيين بداية القص من الموضع الحالي">✂️ بداية القص Set Start</button>
  <input type="text" id="clipStartInput" class="clipper-input" value="{c_s}" placeholder="00:00" onchange="onClipInputChange()" />
  <label style="color:#64748b;">—</label>
  <input type="text" id="clipEndInput" class="clipper-input" value="{c_e}" placeholder="00:00" onchange="onClipInputChange()" />
  <button type="button" class="studio-btn-pill" onclick="setClipEndFromCurrent()" title="تعيين نهاية القص من الموضع الحالي">✂️ نهاية القص Set End</button>
</div>
<div class="clipper-group">
  <button type="button" class="studio-btn-pill" id="btnLoopClip" onclick="toggleClipLoop()" title="معاينة دائرية متكررة للمقطع">▶ معاينة المقطع Loop</button>
  <span id="clipDurationBadge" class="badge badge-dim">{badge_txt}</span>
  <button type="button" class="studio-btn-pill" onclick="resetClipRange()" title="إلغاء القص واستعادة كامل الفيديو">↺ كامل الفيديو</button>
</div>
<div class="clipper-group" style="margin-left:auto;gap:6px;">
  <button type="button" class="studio-btn-pill" id="btnEditSubText" onclick="openSubTextEditor()" title="تعديل نص الترجمة الحالية أو اضغط مرتين على الترجمة">✏️ تعديل النص</button>
  <button type="button" class="studio-btn-pill{' active' if dual_sub else ''}" id="btnDualSub" onclick="toggleDualSubtitles()" title="عرض ترجمة مزدوجة عربي + أجنبي">🌍 ترجمة مزدوجة</button>
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

def get_clipper_js() -> str:
    """Returns client-side JavaScript for smart live clipping, subtitle fixer, and dual subs."""
    return """
let clipStartSec = 0.0, clipEndSec = 0.0, isLoopingClip = false;
let subCustomEdits = {}, dualSubEnabled = false, secSubIndex = -1, secondarySubCues = [];
let currentActiveCueIndex = -1;

function secToTimeStr(sec) {
    if (!sec || isNaN(sec) || sec < 0) return "00:00";
    const s = Math.floor(sec % 60), m = Math.floor((sec / 60) % 60), h = Math.floor(sec / 3600);
    return h > 0 ? `${h}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}` : `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
}

function timeStrToSec(str) {
    if (!str) return 0.0;
    const parts = String(str).trim().replace(',', '.').split(':').map(Number);
    if (parts.some(isNaN)) return 0.0;
    if (parts.length === 1) return parts[0];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return 0.0;
}

function updateClipUI() {
    const sIn = document.getElementById("clipStartInput"), eIn = document.getElementById("clipEndInput");
    const bDur = document.getElementById("clipDurationBadge"), bLoop = document.getElementById("btnLoopClip");
    if (sIn && !sIn._focused) sIn.value = secToTimeStr(clipStartSec);
    if (eIn && !eIn._focused) eIn.value = secToTimeStr(clipEndSec);
    if (bDur) {
        if (clipEndSec > clipStartSec) {
            bDur.textContent = `✂️ المقطع: ${secToTimeStr(clipEndSec - clipStartSec)}`;
            bDur.className = "badge badge-res";
        } else {
            bDur.textContent = "المقطع: كامل الفيديو";
            bDur.className = "badge badge-dim";
        }
    }
    if (bLoop) bLoop.classList.toggle("active", isLoopingClip);
}

function setClipStartFromCurrent() {
    if (videoEl && !isNaN(videoEl.currentTime)) {
        clipStartSec = parseFloat(videoEl.currentTime.toFixed(2));
        if (clipEndSec > 0 && clipEndSec <= clipStartSec) clipEndSec = 0.0;
    }
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function setClipEndFromCurrent() {
    if (videoEl && !isNaN(videoEl.currentTime)) {
        clipEndSec = parseFloat(videoEl.currentTime.toFixed(2));
        if (clipEndSec <= clipStartSec) clipStartSec = 0.0;
    }
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function onClipInputChange() {
    const sIn = document.getElementById("clipStartInput"), eIn = document.getElementById("clipEndInput");
    if (sIn) clipStartSec = timeStrToSec(sIn.value);
    if (eIn) clipEndSec = timeStrToSec(eIn.value);
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function toggleClipLoop() {
    isLoopingClip = !isLoopingClip;
    if (isLoopingClip) {
        if (clipEndSec <= clipStartSec && videoEl && videoEl.duration) {
            clipEndSec = parseFloat(videoEl.duration.toFixed(2));
        }
        if (videoEl && clipEndSec > clipStartSec) {
            videoEl.currentTime = clipStartSec;
            videoEl.play().catch(e => {});
        }
    }
    updateClipUI();
}

function resetClipRange() {
    clipStartSec = 0.0; clipEndSec = 0.0; isLoopingClip = false;
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function openSubTextEditor() {
    const modal = document.getElementById("subEditModal"), txtArea = document.getElementById("subEditTextArea");
    const tBadge = document.getElementById("subEditTimeBadge");
    if (!modal || !txtArea) return;
    const ct = (videoEl && !isNaN(videoEl.currentTime)) ? videoEl.currentTime : 0;
    let cueIdx = -1, cue = null;
    if (liveSubCues && liveSubCues.length) {
        cueIdx = liveSubCues.findIndex(c => ct >= c.start && ct <= c.end);
        if (cueIdx === -1) cueIdx = liveSubCues.findIndex(c => c.start >= ct);
        if (cueIdx === -1) cueIdx = 0;
        cue = liveSubCues[cueIdx];
    }
    if (!cue) return;
    currentActiveCueIndex = cueIdx;
    if (videoEl) videoEl.pause();
    txtArea.value = cue.text || "";
    if (tBadge) tBadge.textContent = `${secToTimeStr(cue.start)} --> ${secToTimeStr(cue.end)}`;
    modal.style.display = "flex";
    setTimeout(() => { txtArea.focus(); txtArea.select(); }, 50);
}

function saveSubTextEdit() {
    const modal = document.getElementById("subEditModal"), txtArea = document.getElementById("subEditTextArea");
    if (!modal || !txtArea) return;
    const newText = txtArea.value.trim();
    if (currentActiveCueIndex >= 0 && currentActiveCueIndex < liveSubCues.length) {
        liveSubCues[currentActiveCueIndex].text = newText;
        subCustomEdits[String(currentActiveCueIndex)] = newText;
        subCustomEdits[liveSubCues[currentActiveCueIndex].start.toFixed(2)] = newText;
        if (typeof updateLiveSubDisplay === "function") updateLiveSubDisplay();
        if (typeof syncStateToBridge === "function") syncStateToBridge();
    }
    closeSubTextEditor();
}

function closeSubTextEditor() {
    const modal = document.getElementById("subEditModal");
    if (modal) modal.style.display = "none";
}

function toggleDualSubtitles() {
    dualSubEnabled = !dualSubEnabled;
    const btn = document.getElementById("btnDualSub");
    if (btn) btn.classList.toggle("active", dualSubEnabled);
    if (dualSubEnabled) {
        secSubIndex = -1;
        const sEl = document.getElementById("subSelect");
        const curPrim = sEl ? parseInt(sEl.value) : 1;
        if (subtitleTracks && subtitleTracks.length > 1) {
            for (let i = 1; i < subtitleTracks.length; i++) {
                const lang = String(subtitleTracks[i].language || "").toLowerCase();
                if (i !== curPrim && (lang.startsWith("en") || lang.startsWith("eng"))) { secSubIndex = i; break; }
            }
            if (secSubIndex === -1) {
                for (let i = 1; i < subtitleTracks.length; i++) {
                    if (i !== curPrim) { secSubIndex = i; break; }
                }
            }
        }
        if (secSubIndex > 0 && sid) {
            fetch(`${bridgeBase}/subtitle.vtt?sid=${encodeURIComponent(sid)}&s_idx=${secSubIndex}`)
                .then(r => r.text()).then(txt => {
                    secondarySubCues = (typeof parseVttToCuesArray === "function") ? parseVttToCuesArray(txt) : [];
                    if (typeof updateLiveSubDisplay === "function") updateLiveSubDisplay();
                }).catch(() => { secondarySubCues = []; });
        }
    } else {
        secondarySubCues = [];
    }
    if (typeof updateLiveSubDisplay === "function") updateLiveSubDisplay();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function initClipperStudioHooks() {
    const overlay = document.getElementById("liveSubOverlay");
    if (overlay) {
        overlay.addEventListener("dblclick", (e) => { e.stopPropagation(); openSubTextEditor(); });
    }
    if (videoEl) {
        videoEl.addEventListener("timeupdate", () => {
            if (isLoopingClip && clipEndSec > clipStartSec) {
                if (videoEl.currentTime >= clipEndSec || videoEl.currentTime < clipStartSec) {
                    videoEl.currentTime = clipStartSec;
                }
            }
        });
    }
    const sIn = document.getElementById("clipStartInput"), eIn = document.getElementById("clipEndInput");
    if (sIn) { sIn.addEventListener("focus", () => { sIn._focused = true; }); sIn.addEventListener("blur", () => { sIn._focused = false; }); }
    if (eIn) { eIn.addEventListener("focus", () => { eIn._focused = true; }); eIn.addEventListener("blur", () => { eIn._focused = false; }); }
}
""".strip()
