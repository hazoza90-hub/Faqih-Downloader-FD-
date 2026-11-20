"""
clipper_js.py: Client-side JavaScript for smart live clipping, subtitle fixer, Web Audio boost, and dual subs.
"""
from __future__ import annotations


def get_clipper_js() -> str:
    """Returns client-side JavaScript for smart live clipping, subtitle fixer, and dual subs."""
    return """
let clipStartSec = 0.0, clipEndSec = 0.0, isLoopingClip = false;
let subCustomEdits = {}, dualSubEnabled = false, secSubIndex = -1, secondarySubCues = [];
let currentActiveCueIndex = -1;
let audioBoostEnabled = false, selectedChapterTitle = "";
let _studioAudioCtx = null, _studioBoostNodes = [];

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

function populateAutoChaptersIfNeeded() {
    const sel = document.getElementById("chapterSelect");
    if (!sel || sel.options.length > 1) return;
    if (typeof videoEl === "undefined" || !videoEl || isNaN(videoEl.duration) || !isFinite(videoEl.duration) || videoEl.duration <= 0) return;
    const dur = videoEl.duration;
    if (dur >= 120) {
        let step = (dur > 3600) ? 900 : ((dur > 900) ? 600 : 300), curr = 0, idx = 1;
        while (curr < dur) {
            const end = Math.min(curr + step, dur), opt = document.createElement("option");
            opt.value = "auto_" + idx; opt.setAttribute("data-start", curr.toFixed(2)); opt.setAttribute("data-end", end.toFixed(2));
            const title = "الجزء " + idx + " - تقسيم تلقائي";
            opt.setAttribute("data-title", title); opt.textContent = "[" + secToTimeStr(curr) + " - " + secToTimeStr(end) + "] " + title;
            sel.appendChild(opt); curr += step; idx++;
        }
        if (sel.options[0]) sel.options[0].textContent = "📑 الفصول (" + (idx - 1) + " جزء بالتقسيم الذكي - اختر لتحميله)";
    } else {
        const mid = dur / 2, opt1 = document.createElement("option"), opt2 = document.createElement("option");
        opt1.value = "auto_1"; opt1.setAttribute("data-start", "0.00"); opt1.setAttribute("data-end", mid.toFixed(2));
        opt1.setAttribute("data-title", "النصف الأول من الفيديو"); opt1.textContent = "[00:00 - " + secToTimeStr(mid) + "] النصف الأول من الفيديو";
        sel.appendChild(opt1);
        opt2.value = "auto_2"; opt2.setAttribute("data-start", mid.toFixed(2)); opt2.setAttribute("data-end", dur.toFixed(2));
        opt2.setAttribute("data-title", "النصف الثاني من الفيديو"); opt2.textContent = "[" + secToTimeStr(mid) + " - " + secToTimeStr(dur) + "] النصف الثاني من الفيديو";
        sel.appendChild(opt2);
        if (sel.options[0]) sel.options[0].textContent = "📑 الفصول (2 جزء بالتقسيم الذكي - اختر لتحميله)";
    }
}

function formatClipBytes(bytes) {
    if (!bytes || bytes <= 0) return "—";
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + " GB";
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
}

function updateClipUI() {
    const sIn = document.getElementById("clipStartInput"), eIn = document.getElementById("clipEndInput");
    const bDur = document.getElementById("clipDurationBadge"), bLoop = document.getElementById("btnLoopClip");
    if (sIn && !sIn._focused) sIn.value = secToTimeStr(clipStartSec);
    if (eIn && !eIn._focused) eIn.value = secToTimeStr(clipEndSec);

    let ratio = 1.0;
    if (clipEndSec > clipStartSec) {
        let totalDur = (typeof videoEl !== "undefined" && videoEl && videoEl.duration > 0 && isFinite(videoEl.duration)) ? videoEl.duration : 0;
        if (totalDur <= 0) {
            const chSel = document.getElementById("chapterSelect");
            if (chSel && chSel.options) {
                for (let i = 0; i < chSel.options.length; i++) {
                    const de = parseFloat(chSel.options[i].getAttribute("data-end") || 0);
                    if (de > totalDur) totalDur = de;
                }
            }
        }
        if (totalDur > 0 && (clipEndSec - clipStartSec) < totalDur - 0.5) {
            ratio = Math.max(0.03, Math.min(1.0, (clipEndSec - clipStartSec) / totalDur));
        }
    }

    let selEstStr = "";
    document.querySelectorAll(".opt-row[data-raw-size]").forEach(row => {
        const raw = parseFloat(row.getAttribute("data-raw-size") || "0");
        const cell = row.querySelector(".col-size");
        if (cell && raw > 0) {
            const estBytes = Math.round(raw * ratio);
            const formatted = (ratio < 0.99 ? "~" : "") + formatClipBytes(ratio < 0.99 ? estBytes : raw);
            cell.textContent = formatted;
            if (row.classList.contains("selected") && ratio < 0.99) selEstStr = formatted;
        }
    });

    if (bDur) {
        if (clipEndSec > clipStartSec) {
            const durText = secToTimeStr(clipEndSec - clipStartSec);
            const sizeSuffix = selEstStr ? ` • ${selEstStr}` : "";
            bDur.textContent = selectedChapterTitle ? `📑 ${selectedChapterTitle.slice(0, 22)} (${durText}${sizeSuffix})` : `✂️ المقطع: ${durText}${sizeSuffix}`;
            bDur.className = "badge badge-res";
        } else {
            bDur.textContent = "المقطع: كامل الفيديو"; bDur.className = "badge badge-dim";
        }
    }
    if (bLoop) bLoop.classList.toggle("active", isLoopingClip);
}

function setClipStartFromCurrent() {
    clipStartSec = parseFloat((videoEl && !isNaN(videoEl.currentTime) ? videoEl.currentTime : 0).toFixed(2));
    if (clipEndSec <= clipStartSec) {
        clipEndSec = (videoEl && !isNaN(videoEl.duration) && isFinite(videoEl.duration) && videoEl.duration > clipStartSec) ? parseFloat(videoEl.duration.toFixed(2)) : parseFloat((clipStartSec + 30.0).toFixed(2));
    }
    selectedChapterTitle = ""; const sel = document.getElementById("chapterSelect"); if (sel) sel.selectedIndex = 0;
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
    if (typeof requestUpdatedFilename === "function") requestUpdatedFilename();
}

function setClipEndFromCurrent() {
    if (videoEl && !isNaN(videoEl.currentTime)) {
        clipEndSec = parseFloat(videoEl.currentTime.toFixed(2));
        if (clipEndSec <= clipStartSec) clipStartSec = 0.0;
    }
    selectedChapterTitle = ""; const sel = document.getElementById("chapterSelect"); if (sel) sel.selectedIndex = 0;
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
    if (typeof requestUpdatedFilename === "function") requestUpdatedFilename();
}

function onClipInputChange() {
    const sIn = document.getElementById("clipStartInput"), eIn = document.getElementById("clipEndInput");
    if (sIn) clipStartSec = timeStrToSec(sIn.value);
    if (eIn) clipEndSec = timeStrToSec(eIn.value);
    selectedChapterTitle = ""; const sel = document.getElementById("chapterSelect"); if (sel) sel.selectedIndex = 0;
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
    if (typeof requestUpdatedFilename === "function") requestUpdatedFilename();
}

function toggleClipLoop() {
    isLoopingClip = !isLoopingClip;
    if (isLoopingClip) {
        if (clipEndSec <= clipStartSec && videoEl && videoEl.duration) {
            clipEndSec = parseFloat(videoEl.duration.toFixed(2));
        }
        if (videoEl && clipEndSec > clipStartSec) {
            videoEl.currentTime = clipStartSec;
            if (typeof hasDubAudio !== "undefined" && hasDubAudio && typeof dubAudioEl !== "undefined" && dubAudioEl) {
                try { dubAudioEl.currentTime = clipStartSec; } catch(e) {}
            }
            videoEl.play().catch(e => {});
            if (typeof hasDubAudio !== "undefined" && hasDubAudio && typeof dubAudioEl !== "undefined" && dubAudioEl) {
                dubAudioEl.play().catch(e => {});
            }
        }
    }
    updateClipUI();
}

function resetClipRange() {
    clipStartSec = 0.0; clipEndSec = 0.0; isLoopingClip = false;
    selectedChapterTitle = "";
    const sel = document.getElementById("chapterSelect");
    if (sel) sel.selectedIndex = 0;
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
    if (typeof requestUpdatedFilename === "function") requestUpdatedFilename();
}

function onChapterSelectChange() {
    const sel = document.getElementById("chapterSelect");
    if (!sel) return;
    if (sel.selectedIndex <= 0) {
        clipStartSec = 0.0; clipEndSec = 0.0;
        selectedChapterTitle = "";
        updateClipUI();
        if (typeof syncStateToBridge === "function") syncStateToBridge();
        if (typeof requestUpdatedFilename === "function") requestUpdatedFilename();
        return;
    }
    const opt = sel.options[sel.selectedIndex];
    const s = parseFloat(opt.getAttribute("data-start") || 0);
    const e = parseFloat(opt.getAttribute("data-end") || 0);
    const title = opt.getAttribute("data-title") || "";
    clipStartSec = s;
    clipEndSec = e;
    selectedChapterTitle = title;
    if (typeof videoEl !== "undefined" && videoEl) {
        try { videoEl.currentTime = s; } catch (err) {}
    }
    if (typeof hasDubAudio !== "undefined" && hasDubAudio && typeof dubAudioEl !== "undefined" && dubAudioEl) {
        try { dubAudioEl.currentTime = s; } catch (err) {}
    }
    updateClipUI();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
    if (typeof requestUpdatedFilename === "function") requestUpdatedFilename();
}

function requestUpdatedFilename() {
    if (!sid || typeof destInput === "undefined" || !destInput) return;
    const q_idx = (typeof selected_q_idx !== "undefined") ? selected_q_idx : 0;
    const s_idx = (typeof subSelect !== "undefined" && subSelect) ? parseInt(subSelect.value) : 0;
    const sub_mode = (typeof modeSelect !== "undefined" && modeSelect) ? modeSelect.value : "hard_burn";
    fetch(`${bridgeBase}/api/update_filename?sid=${encodeURIComponent(sid)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            q_idx: q_idx, s_idx: s_idx, sub_mode: sub_mode, current_dest: destInput.value,
            clip_start: (typeof clipStartSec !== "undefined" ? clipStartSec : 0.0),
            clip_end: (typeof clipEndSec !== "undefined" ? clipEndSec : 0.0),
            chapter_title: (typeof selectedChapterTitle !== "undefined" ? selectedChapterTitle : "")
        })
    }).then(r => r.json()).then(d => { if (d && d.dest_path) destInput.value = d.dest_path; }).catch(e => {});
}

function initStudioWebAudioBoost() {
    if (_studioAudioCtx) return;
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        _studioAudioCtx = new AudioCtx();
        const targets = [];
        if (typeof videoEl !== "undefined" && videoEl) targets.push(videoEl);
        if (typeof dubAudioEl !== "undefined" && dubAudioEl) targets.push(dubAudioEl);
        _studioBoostNodes = [];
        targets.forEach(el => {
            try {
                const source = _studioAudioCtx.createMediaElementSource(el);
                const hp = _studioAudioCtx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 80;
                const presence = _studioAudioCtx.createBiquadFilter(); presence.type = "peaking"; presence.frequency.value = 2800; presence.Q.value = 1.0; presence.gain.value = 3.5;
                const comp = _studioAudioCtx.createDynamicsCompressor(); comp.threshold.value = -24; comp.knee.value = 10; comp.ratio.value = 2.2; comp.attack.value = 0.01; comp.release.value = 0.15;
                const gain = _studioAudioCtx.createGain(); gain.gain.value = 2.8;
                _studioBoostNodes.push({ el, source, hp, presence, comp, gain, connectedBoost: false });
            } catch (e) {}
        });
    } catch (e) {}
}

function applyStudioWebAudioRouting() {
    try {
        if (audioBoostEnabled) {
            initStudioWebAudioBoost();
            if (_studioAudioCtx && _studioAudioCtx.state === "suspended") _studioAudioCtx.resume().catch(e => {});
            _studioBoostNodes.forEach(item => {
                try { item.source.disconnect(); item.hp.disconnect(); item.presence.disconnect(); item.comp.disconnect(); item.gain.disconnect(); } catch(e) {}
                try {
                    item.source.connect(item.hp); item.hp.connect(item.presence); item.presence.connect(item.comp);
                    item.comp.connect(item.gain); item.gain.connect(_studioAudioCtx.destination);
                    item.gain.gain.setValueAtTime(2.8, _studioAudioCtx.currentTime); item.connectedBoost = true;
                } catch(e) {}
            });
        } else if (_studioAudioCtx) {
            _studioBoostNodes.forEach(item => {
                try { item.source.disconnect(); item.hp.disconnect(); item.presence.disconnect(); item.comp.disconnect(); item.gain.disconnect(); } catch(e) {}
                try { item.source.connect(_studioAudioCtx.destination); item.connectedBoost = false; } catch(e) {}
            });
        }
    } catch (e) {}
}

function toggleStudioAudioBoost() {
    audioBoostEnabled = !audioBoostEnabled;
    const btn = document.getElementById("btnAudioBoost");
    if (btn) btn.classList.toggle("active", audioBoostEnabled);
    applyStudioWebAudioRouting();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function openSubTextEditor() {
    const modal = document.getElementById("subEditModal"), txtArea = document.getElementById("subEditTextArea");
    const tBadge = document.getElementById("subEditTimeBadge");
    if (!modal || !txtArea) return;
    const sEl = document.getElementById("subSelect");
    let loadP = null;
    if (sEl && parseInt(sEl.value) <= 0 && typeof subtitleTracks !== "undefined" && subtitleTracks && subtitleTracks.length > 1) {
        let firstIdx = 1;
        for (let i = 1; i < subtitleTracks.length; i++) {
            if (String(subtitleTracks[i].language || "").toLowerCase().startsWith("ar")) { firstIdx = i; break; }
        }
        sEl.value = String(firstIdx);
        if (typeof onSubChange === "function") {
            const res = onSubChange();
            if (res && typeof res.then === "function") loadP = res;
        }
    }
    const renderModal = () => {
        const ct = (videoEl && !isNaN(videoEl.currentTime)) ? videoEl.currentTime : 0;
        let cueIdx = -1, cue = null;
        if (liveSubCues && liveSubCues.length > 0) {
            cueIdx = liveSubCues.findIndex(c => ct >= c.start && ct <= c.end);
            if (cueIdx === -1) {
                let minDiff = Infinity;
                for (let i = 0; i < liveSubCues.length; i++) {
                    const diff = Math.abs(liveSubCues[i].start - ct);
                    if (diff < minDiff) { minDiff = diff; cueIdx = i; }
                }
            }
            if (cueIdx >= 0 && cueIdx < liveSubCues.length) {
                cue = liveSubCues[cueIdx];
            }
        }
        if (!cue) {
            const startT = Math.max(0, parseFloat(ct.toFixed(2)));
            const endT = parseFloat((startT + 4.0).toFixed(2));
            cue = { start: startT, end: endT, text: "", _isSynthetic: true };
            if (!Array.isArray(liveSubCues)) liveSubCues = [];
            liveSubCues.push(cue);
            cueIdx = liveSubCues.length - 1;
        }
        currentActiveCueIndex = cueIdx;
        if (videoEl) videoEl.pause();
        txtArea.value = cue.text || "";
        if (tBadge) tBadge.textContent = `${secToTimeStr(cue.start)} --> ${secToTimeStr(cue.end)}`;
        modal.style.display = "flex";
        setTimeout(() => { txtArea.focus(); txtArea.select(); }, 50);
    };

    if (loadP) loadP.then(renderModal);
    else renderModal();
}

function saveSubTextEdit() {
    const modal = document.getElementById("subEditModal"), txtArea = document.getElementById("subEditTextArea");
    if (!modal || !txtArea) return;
    const newText = txtArea.value.trim();
    if (currentActiveCueIndex >= 0 && currentActiveCueIndex < liveSubCues.length) {
        delete liveSubCues[currentActiveCueIndex]._isSynthetic;
        const origText = liveSubCues[currentActiveCueIndex]._origText || liveSubCues[currentActiveCueIndex].text || "";
        liveSubCues[currentActiveCueIndex]._origText = origText;
        if (origText.trim()) subCustomEdits[origText.trim()] = newText;
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
    if (currentActiveCueIndex >= 0 && currentActiveCueIndex < liveSubCues.length) {
        if (liveSubCues[currentActiveCueIndex]._isSynthetic && !liveSubCues[currentActiveCueIndex].text) {
            liveSubCues.splice(currentActiveCueIndex, 1);
        }
    }
    currentActiveCueIndex = -1;
}

function toggleDualSubtitles() {
    dualSubEnabled = !dualSubEnabled;
    const btn = document.getElementById("btnDualSub");
    if (btn) btn.classList.toggle("active", dualSubEnabled);
    if (dualSubEnabled) {
        const sEl = document.getElementById("subSelect");
        if (sEl && parseInt(sEl.value) <= 0 && typeof subtitleTracks !== "undefined" && subtitleTracks && subtitleTracks.length > 1) {
            let firstIdx = 1;
            for (let i = 1; i < subtitleTracks.length; i++) {
                if (String(subtitleTracks[i].language || "").toLowerCase().startsWith("ar")) { firstIdx = i; break; }
            }
            sEl.value = String(firstIdx);
            if (typeof onSubChange === "function") onSubChange();
        }
        secSubIndex = -1;
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
        if (secSubIndex > 0) {
            const secUrl = sid ? `${bridgeBase}/subtitle.vtt?sid=${encodeURIComponent(sid)}&s_idx=${secSubIndex}` : (subtitleTracks[secSubIndex] ? subtitleTracks[secSubIndex].url : "");
            if (secUrl) {
                if (secUrl.startsWith("data:")) {
                    try {
                        const b64 = secUrl.split(",")[1];
                        const txt = decodeURIComponent(escape(atob(b64)));
                        secondarySubCues = (typeof parseVttToCuesArray === "function") ? parseVttToCuesArray(txt) : [];
                        if (typeof updateLiveSubDisplay === "function") updateLiveSubDisplay();
                    } catch(e) { secondarySubCues = []; }
                } else {
                    fetch(secUrl).then(r => r.text()).then(txt => {
                        secondarySubCues = (typeof parseVttToCuesArray === "function") ? parseVttToCuesArray(txt) : [];
                        if (typeof updateLiveSubDisplay === "function") updateLiveSubDisplay();
                    }).catch(() => { secondarySubCues = []; });
                }
            }
        }
    } else {
        secondarySubCues = [];
    }
    if (typeof updateLiveSubDisplay === "function") updateLiveSubDisplay();
    if (typeof syncStateToBridge === "function") syncStateToBridge();
}

function initClipperStudioHooks() {
    const overlay = document.getElementById("liveSubOverlay");
    if (overlay) overlay.addEventListener("dblclick", (e) => { e.stopPropagation(); openSubTextEditor(); });
    populateAutoChaptersIfNeeded();
    if (videoEl) {
        videoEl.addEventListener("loadedmetadata", populateAutoChaptersIfNeeded);
        videoEl.addEventListener("durationchange", populateAutoChaptersIfNeeded);
        videoEl.addEventListener("play", () => {
            if (_studioAudioCtx && _studioAudioCtx.state === "suspended") _studioAudioCtx.resume().catch(e => {});
        });
        videoEl.addEventListener("timeupdate", () => {
            if (isLoopingClip && clipEndSec > clipStartSec) {
                if (videoEl.currentTime >= clipEndSec || videoEl.currentTime < clipStartSec) {
                    videoEl.currentTime = clipStartSec;
                    if (typeof hasDubAudio !== "undefined" && hasDubAudio && typeof dubAudioEl !== "undefined" && dubAudioEl) {
                        try { dubAudioEl.currentTime = clipStartSec; } catch(e) {}
                    }
                }
            }
        });
    }
    const sIn = document.getElementById("clipStartInput"), eIn = document.getElementById("clipEndInput");
    if (sIn) { sIn.addEventListener("focus", () => { sIn._focused = true; }); sIn.addEventListener("blur", () => { sIn._focused = false; }); }
    if (eIn) { eIn.addEventListener("focus", () => { eIn._focused = true; }); eIn.addEventListener("blur", () => { eIn._focused = false; }); }
    const bBoost = document.getElementById("btnAudioBoost");
    if (bBoost) bBoost.classList.toggle("active", !!audioBoostEnabled);
    applyStudioWebAudioRouting();
}
""".strip()


__all__ = ["get_clipper_js"]
