"""
subtitle_studio_js.py: Client-side JavaScript for subtitle parsing, live overlay syncing, and drag-and-drop.
"""
from __future__ import annotations


def get_studio_js() -> str:
    """Returns client-side JavaScript for subtitle parsing, live overlay syncing, and drag-drop."""
    return """
let subPreset = "youtube", subScale = 1.0, subColor = "#FFFFFF", subBgMode = "box", subPosX = 50.0, subPosY = 86.0;
let liveSubCues = [];
let isDraggingSub = false, dragStartX = 0, dragStartY = 0, initialSubX = 50.0, initialSubY = 86.0;

function disableNativeTextTracks() {
    try {
        const vt = document.getElementById("vttTrack");
        if (vt && vt.track) vt.track.mode = "disabled";
    } catch(e) {}
    try {
        if (videoEl && videoEl.textTracks) {
            for (let i = 0; i < videoEl.textTracks.length; i++) {
                videoEl.textTracks[i].mode = "disabled";
            }
            if (!videoEl._textTracksHooked && typeof videoEl.textTracks.addEventListener === "function") {
                videoEl._textTracksHooked = true;
                videoEl.textTracks.addEventListener("change", disableNativeTextTracks);
                videoEl.textTracks.addEventListener("addtrack", disableNativeTextTracks);
            }
        }
    } catch(e) {}
}

function getRenderedVideoRect() {
    const container = document.getElementById("playerContainer");
    const cW = (container && container.clientWidth) ? container.clientWidth : (window.innerWidth || 800);
    const cH = (container && container.clientHeight) ? container.clientHeight : 400;
    let vW = (videoEl && videoEl.videoWidth) ? videoEl.videoWidth : 0;
    let vH = (videoEl && videoEl.videoHeight) ? videoEl.videoHeight : 0;

    if (vW <= 0 || vH <= 0) {
        let qText = "";
        const selRow = document.querySelector(".opt-row.selected");
        if (selRow) qText += " " + selRow.textContent;
        const bRes = document.getElementById("badgeRes");
        if (bRes) qText += " " + bRes.textContent;

        const m = qText.match(/(\\d{3,5})\\s*x\\s*(\\d{3,5})/i);
        if (m) {
            vW = parseInt(m[1], 10);
            vH = parseInt(m[2], 10);
        } else if (/vertical|shorts/i.test(qText)) {
            vW = 9; vH = 16;
        } else {
            vW = 16; vH = 9;
        }
    }

    const vRatio = vW / (vH || 1);
    const cRatio = cW / (cH || 1);
    let rW, rH, oX, oY;

    if (vRatio < cRatio) {
        rH = cH;
        rW = Math.round(cH * vRatio);
        oX = Math.round((cW - rW) / 2);
        oY = 0;
    } else {
        rW = cW;
        rH = Math.round(cW / vRatio);
        oX = 0;
        oY = Math.round((cH - rH) / 2);
    }
    return { width: rW, height: rH, offsetX: oX, offsetY: oY };
}

function _decodeVttEntities(str) {
    if (!str || str.indexOf("&") === -1) return str;
    const txt = document.createElement("textarea");
    txt.innerHTML = str;
    return txt.value;
}

function _balanceSingleLine(text) {
    if (!text) return "";
    const stripped = text.trim();
    if (!stripped || stripped.indexOf("\\n") !== -1) return text;
    const words = stripped.split(" ").filter(Boolean);
    if (stripped.length > 38 || words.length > 5) {
        const mid = Math.floor(stripped.length / 2);
        const spaces = [];
        for (let i = 0; i < stripped.length; i++) {
            if (stripped[i] === " ") spaces.push(i);
        }
        if (spaces.length > 0) {
            let best = spaces[0];
            for (let i = 1; i < spaces.length; i++) {
                if (Math.abs(spaces[i] - mid) < Math.abs(best - mid)) best = spaces[i];
            }
            const p1 = stripped.slice(0, best).trim();
            const p2 = stripped.slice(best + 1).trim();
            if (p1 && p2) return p1 + "\\n" + p2;
        }
    }
    return text;
}

function parseVttToCuesArray(vttText) {
    if (!vttText) return [];
    const cues = [], blocks = vttText.split(/\\r?\\n\\r?\\n+/);
    const tsPat = /((?:\\d+:)?\\d{1,2}:\\d{2}[.,]\\d+)\\s*-->\\s*((?:\\d+:)?\\d{1,2}:\\d{2}[.,]\\d+)/;
    const toSec = (str) => {
        const s = str.replace(',', '.'), p = s.split(':').map(Number);
        return p.length === 2 ? p[0] * 60 + p[1] : p[0] * 3600 + p[1] * 60 + p[2];
    };
    for (const b of blocks) {
        const lines = b.split('\\n').map(l => l.trim()).filter(Boolean);
        let tsIdx = -1, m = null;
        for (let i = 0; i < lines.length; i++) {
            const match = lines[i].match(tsPat);
            if (match) { tsIdx = i; m = match; break; }
        }
        if (tsIdx === -1 || !m) continue;
        const body = lines.slice(tsIdx + 1).map(l => _decodeVttEntities(l.replace(/<[^>]+>/g, '').trim())).filter(Boolean).join('\\n');
        if (body) cues.push({ start: toSec(m[1]), end: toSec(m[2]), text: _balanceSingleLine(body) });
    }
    return cues;
}

function loadLiveSubtitlesFromUrl(vttUrl) {
    if (!vttUrl) { liveSubCues = []; updateLiveSubDisplay(); return Promise.resolve([]); }
    if (vttUrl.startsWith("data:")) {
        try {
            const b64 = vttUrl.split(",")[1];
            const txt = decodeURIComponent(escape(atob(b64)));
            liveSubCues = parseVttToCuesArray(txt);
            updateLiveSubDisplay();
            return Promise.resolve(liveSubCues);
        } catch(e) {}
    }
    return fetch(vttUrl).then(r => r.text()).then(txt => {
        liveSubCues = parseVttToCuesArray(txt);
        updateLiveSubDisplay();
        return liveSubCues;
    }).catch(() => { liveSubCues = []; updateLiveSubDisplay(); return []; });
}

function _escapeSubHtml(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function updateLiveSubDisplay() {
    const overlay = document.getElementById("liveSubOverlay");
    if (!overlay) return;
    const sEl = document.getElementById("subSelect");
    const subActive = sEl ? (parseInt(sEl.value) > 0) : true;
    if (!subActive || !liveSubCues.length) {
        overlay.style.display = "none"; overlay.textContent = ""; return;
    }
    const ct = videoEl ? videoEl.currentTime : 0;
    let cue = liveSubCues.find(c => ct >= c.start && ct <= c.end);
    if (!cue && ((videoEl && videoEl.paused) || isDraggingSub)) {
        cue = liveSubCues.find(c => c.start >= ct) || liveSubCues[0];
    }
    if (cue && cue.text) {
        let pTxt = _balanceSingleLine(cue.text);
        if (typeof dualSubEnabled !== "undefined" && dualSubEnabled && typeof secondarySubCues !== "undefined" && secondarySubCues.length > 0) {
            let sCue = secondarySubCues.find(c => ct >= c.start && ct <= c.end) || secondarySubCues.find(c => Math.max(0, Math.min(cue.end, c.end) - Math.max(cue.start, c.start)) > 0.05);
            if (sCue && sCue.text) {
                let sTxt = _balanceSingleLine(sCue.text);
                overlay.innerHTML = '<span class="primary-sub-line">' + _escapeSubHtml(pTxt) + '</span><span class="dual-sub-secondary">' + _escapeSubHtml(sTxt) + '</span>';
                overlay.style.display = "block";
                return;
            }
        }
        overlay.innerHTML = '<span class="primary-sub-line">' + _escapeSubHtml(pTxt) + '</span>'; overlay.style.display = "block";
    } else {
        overlay.textContent = ""; overlay.style.display = "none";
    }
}

function applyLiveSubStyle() {
    const overlay = document.getElementById("liveSubOverlay");
    if (!overlay) return;
    overlay.className = "live-sub-overlay";
    if (subPreset === "tiktok") overlay.classList.add("sub-preset-tiktok");
    else if (subPreset === "golden") overlay.classList.add("sub-preset-golden");
    else if (subPreset === "custom") overlay.classList.add(subBgMode === "box" ? "sub-preset-custom-box" : "sub-preset-custom-outline");
    else overlay.classList.add("sub-preset-youtube");

    const vidRect = getRenderedVideoRect();
    overlay.style.maxWidth = Math.round(vidRect.width * 0.88) + "px";
    const baseSize = Math.max(12, Math.min(28, Math.round(Math.min(vidRect.width, vidRect.height) * 0.045)));
    overlay.style.fontSize = Math.round(baseSize * subScale) + "px";
    if (subPreset === "custom") overlay.style.color = subColor;
    overlay.style.left = Math.round(vidRect.offsetX + (subPosX / 100.0) * vidRect.width) + "px";
    overlay.style.top = Math.round(vidRect.offsetY + (subPosY / 100.0) * vidRect.height) + "px";
}

function setSubPreset(name) {
    subPreset = name;
    document.querySelectorAll("#subStudioBar .studio-btn-pill").forEach(b => {
        if (b.id && b.id.startsWith("btnPre")) b.classList.remove("active");
    });
    const idMap = { youtube: "btnPreYt", tiktok: "btnPreTt", golden: "btnPreGold", custom: "btnPreCust" };
    const btn = document.getElementById(idMap[name]);
    if (btn) btn.classList.add("active");
    applyLiveSubStyle();
    updateLiveSubDisplay();
    syncStateToBridge();
}

function onSubScaleChange(val) {
    subScale = parseFloat(val);
    const lbl = document.getElementById("subScaleLabel");
    if (lbl) lbl.textContent = Math.round(subScale * 100) + "%";
    applyLiveSubStyle();
    syncStateToBridge();
}

function setSubColor(hex, el) {
    subColor = hex;
    document.querySelectorAll(".color-dot").forEach(d => d.classList.remove("active"));
    if (el) el.classList.add("active");
    if (subPreset !== "custom") setSubPreset("custom");
    else { applyLiveSubStyle(); syncStateToBridge(); }
}

function setSubBgMode(mode) {
    subBgMode = mode;
    const bBox = document.getElementById("btnBgBox"), bOut = document.getElementById("btnBgOutline");
    if (bBox && bOut) {
        bBox.classList.toggle("active", mode === "box");
        bOut.classList.toggle("active", mode === "outline");
    }
    if (subPreset !== "custom") setSubPreset("custom");
    else { applyLiveSubStyle(); syncStateToBridge(); }
}

function resetSubPosition() {
    subPosX = 50.0; subPosY = 86.0;
    const pSel = document.getElementById("posSelect");
    if (pSel) pSel.value = "bottom";
    applyLiveSubStyle();
    syncStateToBridge();
}

function initLiveSubDragDrop() {
    const overlay = document.getElementById("liveSubOverlay"), container = document.getElementById("playerContainer"), guide = document.getElementById("centerGuideLine");
    if (!overlay || !container) return;
    const onStart = (e) => {
        isDraggingSub = true; overlay.classList.add("dragging");
        const touch = e.touches && e.touches[0];
        dragStartX = touch ? touch.clientX : (e.clientX || 0);
        dragStartY = touch ? touch.clientY : (e.clientY || 0);
        initialSubX = subPosX; initialSubY = subPosY; e.preventDefault();
        updateLiveSubDisplay();
    };
    const onMove = (e) => {
        if (!isDraggingSub) return;
        const touch = e.touches && e.touches[0];
        const cx = touch ? touch.clientX : (e.clientX || 0);
        const cy = touch ? touch.clientY : (e.clientY || 0);
        const vidRect = getRenderedVideoRect();
        if (vidRect.width <= 0 || vidRect.height <= 0) return;
        let nx = initialSubX + ((cx - dragStartX) / vidRect.width) * 100.0;
        let ny = initialSubY + ((cy - dragStartY) / vidRect.height) * 100.0;
        nx = Math.max(8.0, Math.min(92.0, nx));
        ny = Math.max(8.0, Math.min(92.0, ny));
        if (Math.abs(nx - 50.0) < 1.6) { nx = 50.0; if (guide) guide.style.display = "block"; }
        else if (guide) guide.style.display = "none";
        subPosX = parseFloat(nx.toFixed(1)); subPosY = parseFloat(ny.toFixed(1));
        applyLiveSubStyle();
    };
    const onEnd = () => {
        if (!isDraggingSub) return;
        isDraggingSub = false; overlay.classList.remove("dragging");
        if (guide) guide.style.display = "none";
        updateLiveSubDisplay();
        syncStateToBridge();
    };
    overlay.addEventListener("mousedown", onStart);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onEnd);
    overlay.addEventListener("touchstart", onStart, { passive: false });
    window.addEventListener("touchmove", onMove, { passive: false });
    window.addEventListener("touchend", onEnd);
    window.addEventListener("resize", applyLiveSubStyle);
    if (videoEl) {
        videoEl.addEventListener("loadedmetadata", () => {
            disableNativeTextTracks();
            applyLiveSubStyle();
        });
        videoEl.addEventListener("play", disableNativeTextTracks);
        videoEl.addEventListener("timeupdate", disableNativeTextTracks);
        videoEl.addEventListener("resize", applyLiveSubStyle);
    }
    const vt = document.getElementById("vttTrack");
    if (vt) vt.addEventListener("load", disableNativeTextTracks);
    disableNativeTextTracks();
}
""".strip()


__all__ = ["get_studio_js"]
