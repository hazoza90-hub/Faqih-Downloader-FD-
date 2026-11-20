"""
JavaScript template for HTML5 preview player.
"""

_JS_TEMPLATE = """
const hasStream = __HAS_STREAM__, embedUrl = __EMBED_SRC__, initialDubAudioUrl = __DUB_URL__;
const sid = __SID__, audioTracks = __AUDIO_TRACKS__, subtitleTracks = __SUBTITLE_TRACKS__;
const bridgeBase = __BRIDGE_BASE__;
const optNeedsSeparateAudio = __OPT_NEEDS_AUDIO__;
const videoEl = document.getElementById("videoEl"), dubAudioEl = document.getElementById("dubAudioEl");
const iframeEl = document.getElementById("iframeEl"), toggleBtn = document.getElementById("toggleBtn");
const audioBadge = document.getElementById("badgeAudio"), subBadge = document.getElementById("badgeSub"), resBadge = document.getElementById("badgeRes");
const audioSelect = document.getElementById("audioSelect"), subSelect = document.getElementById("subSelect"), modeSelect = document.getElementById("modeSelect"), connSelect = document.getElementById("connSelect"), destInput = document.getElementById("destInput");
const muteBtn = document.getElementById("muteBtn"), volSlider = document.getElementById("volSlider");
let isUsingVideo = hasStream, selected_q_idx = __SELECTED_Q_IDX__, hasDubAudio = Boolean(initialDubAudioUrl);
let actionSubmitted = false;
window._userTouchedMode = false;

function updateUI() {
    if (isUsingVideo) {
        videoEl.style.display = "block"; iframeEl.style.display = "none";
        toggleBtn.textContent = "🌐 Switch to Web Player / المشغل المدمج";
        try { videoEl.play(); } catch (e) {}
    } else {
        try { videoEl.pause(); } catch (e) {}
        videoEl.style.display = "none"; iframeEl.style.display = "block";
        if (!iframeEl.src || iframeEl.src === "about:blank") iframeEl.src = embedUrl;
        toggleBtn.textContent = "🎞️ Switch to Direct Stream / المشغل المباشر";
    }
}
function togglePlayer() { if (!hasStream && isUsingVideo) return; isUsingVideo = !isUsingVideo; updateUI(); }
function handleVideoError() { console.warn("[SD Preview] Direct stream fallback to Web Embed"); isUsingVideo = false; updateUI(); }
if (videoEl) { videoEl.addEventListener("error", handleVideoError); }

function setDubAudioTrack(url, label) {
    if (!dubAudioEl) return;
    if (url) {
        hasDubAudio = true; dubAudioEl.src = url;
        const syncTime = () => {
            if (videoEl && !isNaN(videoEl.currentTime)) {
                try { dubAudioEl.currentTime = videoEl.currentTime; } catch (e) {}
            }
            if (videoEl && !videoEl.paused) dubAudioEl.play().catch(e => {});
        };
        if (dubAudioEl.readyState >= 1) syncTime();
        else dubAudioEl.addEventListener("loadedmetadata", syncTime, { once: true });
        videoEl.muted = true;
        const isOrig = (label === "Original Audio");
        if (audioBadge) {
            audioBadge.textContent = "🔊 " + (label || "Dubbed Audio");
            audioBadge.className = isOrig ? "badge badge-dim" : "badge badge-audio";
        }
    } else {
        hasDubAudio = false; dubAudioEl.pause(); dubAudioEl.removeAttribute("src"); videoEl.muted = false;
        if (audioBadge) { audioBadge.textContent = "🔊 Original Audio"; audioBadge.className = "badge badge-dim"; }
    }
}
if (initialDubAudioUrl) {
    setDubAudioTrack(initialDubAudioUrl, __EFFECTIVE_AUDIO_LABEL__);
} else if (sid && optNeedsSeparateAudio && optNeedsSeparateAudio[selected_q_idx]) {
    setDubAudioTrack(`${bridgeBase}/stream_audio?sid=${encodeURIComponent(sid)}&a_idx=0&q_idx=${selected_q_idx}`, "Original Audio");
}

if (videoEl && dubAudioEl) {
    videoEl.addEventListener("volumechange", () => {
        if (hasDubAudio) { dubAudioEl.volume = videoEl.volume; if (!videoEl.muted) videoEl.muted = true; }
        if (volSlider) volSlider.value = videoEl.volume;
    });
    videoEl.addEventListener("play", () => { if (hasDubAudio) { dubAudioEl.currentTime = videoEl.currentTime; dubAudioEl.play().catch(e => {}); } });
    videoEl.addEventListener("pause", () => { if (hasDubAudio) dubAudioEl.pause(); });
    videoEl.addEventListener("seeking", () => { if (hasDubAudio) dubAudioEl.currentTime = videoEl.currentTime; updateLiveSubDisplay(); });
    videoEl.addEventListener("seeked", () => { if (hasDubAudio) dubAudioEl.currentTime = videoEl.currentTime; updateLiveSubDisplay(); });
    videoEl.addEventListener("waiting", () => { if (hasDubAudio) dubAudioEl.pause(); });
    videoEl.addEventListener("playing", () => { if (hasDubAudio) { if (Math.abs(dubAudioEl.currentTime - videoEl.currentTime) > 0.28) dubAudioEl.currentTime = videoEl.currentTime; dubAudioEl.play().catch(e => {}); } });
    videoEl.addEventListener("ratechange", () => { if (hasDubAudio) dubAudioEl.playbackRate = videoEl.playbackRate; });
    videoEl.addEventListener("timeupdate", () => {
        if (hasDubAudio && !videoEl.paused) {
            if (Math.abs(dubAudioEl.currentTime - videoEl.currentTime) > 0.28) {
                try { dubAudioEl.currentTime = videoEl.currentTime; } catch (e) {}
            }
            if (dubAudioEl.paused && dubAudioEl.readyState >= 2) {
                dubAudioEl.play().catch(e => {});
            }
        }
        updateLiveSubDisplay();
    });
    dubAudioEl.addEventListener("error", (e) => { hasDubAudio = false; videoEl.muted = false; if (audioBadge) { audioBadge.textContent = "🔊 Original Audio"; audioBadge.className = "badge badge-dim"; } });
}

if (muteBtn && volSlider) {
    muteBtn.addEventListener("click", () => {
        const isM = hasDubAudio ? dubAudioEl.muted : videoEl.muted;
        const nextM = !isM;
        if (hasDubAudio) { dubAudioEl.muted = nextM; }
        else { videoEl.muted = nextM; }
        muteBtn.textContent = nextM ? "🔇" : "🔊";
    });
    volSlider.addEventListener("input", (e) => {
        const v = parseFloat(e.target.value);
        if (hasDubAudio) { dubAudioEl.volume = v; dubAudioEl.muted = (v === 0); }
        videoEl.volume = v;
        if (!hasDubAudio) { videoEl.muted = (v === 0); }
        muteBtn.textContent = (v === 0) ? "🔇" : "🔊";
    });
}

function selectQualityRow(idx) {
    selected_q_idx = idx; document.querySelectorAll(".opt-row").forEach(r => r.classList.remove("selected"));
    const row = document.querySelector(`.opt-row[data-idx="${idx}"]`);
    if (row) {
        row.classList.add("selected");
        if (row.scrollIntoView) { setTimeout(() => row.scrollIntoView({ block: "center", behavior: "instant" }), 50); }
    }
    const resCell = row ? row.querySelector(".col-res strong") : null;
    if (resCell && resBadge) resBadge.textContent = "🎞️ " + resCell.textContent;
    if (sid) {
        const savedTime = videoEl ? videoEl.currentTime : 0;
        const curA = audioSelect ? parseInt(audioSelect.value) : 0;
        videoEl.src = `${bridgeBase}/stream_video?sid=${encodeURIComponent(sid)}&q_idx=${idx}&a_idx=${curA}`;
        if (curA <= 0) {
            const needsAud = Boolean(optNeedsSeparateAudio && optNeedsSeparateAudio[idx]);
            if (needsAud) setDubAudioTrack(`${bridgeBase}/stream_audio?sid=${encodeURIComponent(sid)}&a_idx=0&q_idx=${idx}`, "Original Audio");
            else setDubAudioTrack(null, "Original Audio");
        }
        if (savedTime > 0) {
            videoEl.addEventListener("loadedmetadata", () => {
                try { videoEl.currentTime = savedTime; } catch (e) {}
                if (hasDubAudio && dubAudioEl) { try { dubAudioEl.currentTime = savedTime; } catch (e) {} }
                videoEl.play().catch(e => {});
                if (hasDubAudio && dubAudioEl) { dubAudioEl.play().catch(e => {}); }
            }, { once: true });
        } else {
            videoEl.play().catch(e => {});
            if (hasDubAudio && dubAudioEl) { dubAudioEl.play().catch(e => {}); }
        }
        if (typeof applyLiveSubStyle === "function") applyLiveSubStyle();
        if (typeof updateClipUI === "function") updateClipUI();
        syncStateToBridge();
        requestUpdatedFilename();
    }
}

function onAudioChange() {
    if (!audioSelect) return;
    const a = parseInt(audioSelect.value);
    if (a <= 0 || a >= audioTracks.length) {
        const needsAud = Boolean(optNeedsSeparateAudio && optNeedsSeparateAudio[selected_q_idx]);
        if (needsAud) setDubAudioTrack(sid ? `${bridgeBase}/stream_audio?sid=${encodeURIComponent(sid)}&a_idx=0&q_idx=${selected_q_idx}` : (initialDubAudioUrl || ""), "Original Audio");
        else setDubAudioTrack(null, "Original Audio");
    } else {
        const t = audioTracks[a];
        setDubAudioTrack(sid ? `${bridgeBase}/stream_audio?sid=${encodeURIComponent(sid)}&a_idx=${a}&q_idx=${selected_q_idx}` : (t.url || ""), t.label || t.language);
    }
    syncStateToBridge();
    if (sid && videoEl) {
        const savedTime = videoEl.currentTime || 0;
        videoEl.src = `${bridgeBase}/stream_video?sid=${encodeURIComponent(sid)}&q_idx=${selected_q_idx}&a_idx=${a}`;
        if (savedTime > 0) {
            videoEl.addEventListener("loadedmetadata", () => {
                try { videoEl.currentTime = savedTime; } catch (e) {}
                if (hasDubAudio && dubAudioEl) { try { dubAudioEl.currentTime = savedTime; } catch (e) {} }
                videoEl.play().catch(e => {});
                if (hasDubAudio && dubAudioEl) { dubAudioEl.play().catch(e => {}); }
            }, { once: true });
        } else {
            videoEl.play().catch(e => {});
            if (hasDubAudio && dubAudioEl) { dubAudioEl.play().catch(e => {}); }
        }
    }
}

function applySubtitlePosition(pos) {
    if (pos === "top") subPosY = 12.0;
    else if (pos === "middle") subPosY = 50.0;
    else subPosY = 86.0;
    subPosX = 50.0;
    applyLiveSubStyle();
}

function onConnChange() {
    if (!connSelect) return;
    if (connSelect.value === "32" && typeof showToast === "function") showToast("⚡ 32 Threads: High server load / أقصى استهلاك للشبكة", "warn");
    syncStateToBridge();
}

function browseDestination() {
    if (!sid || !destInput) return;
    fetch(`${bridgeBase}/api/browse?sid=${encodeURIComponent(sid)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_dest: destInput.value })
    }).then(r => r.json()).then(d => {
        if (d && d.ok && d.dest) { destInput.value = d.dest; syncStateToBridge(); }
    }).catch(e => {});
}

function onSubChange() {
    if (!subSelect) return;
    const s = parseInt(subSelect.value);
    const isNoSub = (s <= 0 || s >= subtitleTracks.length);
    if (modeSelect) modeSelect.disabled = isNoSub;
    if (!isNoSub && !window._userTouchedMode && modeSelect) modeSelect.value = "hard_burn";
    let trk = document.getElementById("vttTrack"), loadP = null;
    if (s <= 0 || s >= subtitleTracks.length) {
        if (trk) { trk.src = ""; try { trk.track.mode = "disabled"; } catch (e) {} }
        if (subBadge) { subBadge.textContent = "💬 No Subtitles"; subBadge.className = "badge badge-dim"; }
        loadP = loadLiveSubtitlesFromUrl(null);
    } else {
        const t = subtitleTracks[s], lbl = t.label || t.language || "Subtitles", vUrl = sid ? `${bridgeBase}/subtitle.vtt?sid=${encodeURIComponent(sid)}&s_idx=${s}` : (t.url || "");
        if (subBadge) { subBadge.textContent = "💬 " + lbl; subBadge.className = "badge badge-sub"; }
        if (!trk) { trk = document.createElement("track"); trk.id = "vttTrack"; trk.kind = "subtitles"; trk.default = true; videoEl.appendChild(trk); }
        trk.label = lbl; trk.srclang = (t.language || "ar").split("-")[0].split("_")[0]; trk.src = vUrl;
        try { trk.track.mode = "disabled"; } catch (e) {}
        loadP = loadLiveSubtitlesFromUrl(vUrl);
        applyLiveSubStyle();
    }
    if (typeof disableNativeTextTracks === "function") disableNativeTextTracks();
    syncStateToBridge();
    requestUpdatedFilename();
    return loadP;
}

function onModeChange() {
    if (!modeSelect) return;
    window._userTouchedMode = true;
    if (modeSelect.value === "hard_burn" && subSelect && parseInt(subSelect.value) <= 0 && subtitleTracks.length > 1) {
        let ar = 1; for (let i = 1; i < subtitleTracks.length; i++) { if (String(subtitleTracks[i].language || "").toLowerCase().startsWith("ar")) { ar = i; break; } }
        subSelect.value = String(ar); onSubChange(); return;
    }
    requestUpdatedFilename();
    syncStateToBridge();
}

function getCheckedExtBoxes() { return Array.from(document.querySelectorAll(".ext-srt-cb:checked")); }
function getSelectedExtSubIndices() { return getCheckedExtBoxes().map(cb => parseInt(cb.value)).filter(n => !isNaN(n)); }
function getSelectedExtSubLangs() { return getCheckedExtBoxes().map(cb => cb.getAttribute("data-subid") || cb.getAttribute("data-lang") || "").filter(Boolean); }
function updateExtSrtBtnLabel() {
    const btn = document.getElementById("extSrtBtn"), txt = document.getElementById("extSrtBtnText");
    if (!btn || !txt) return;
    const cbs = getCheckedExtBoxes(), codes = [];
    cbs.forEach(cb => { const c = (cb.getAttribute("data-lang") || "").toUpperCase(); if (c && !codes.includes(c)) codes.push(c); });
    if (cbs.length === 0) { txt.textContent = "بدون (0)"; btn.classList.remove("has-sel"); }
    else { const head = codes.slice(0, 3).join(", ") + (codes.length > 3 ? ".." : ""); txt.textContent = `${head} (${cbs.length})`; btn.classList.add("has-sel"); }
}
function toggleExtSrtDropdown(e) { if (e) e.stopPropagation(); const dd = document.getElementById("extSrtDropdown"); if (dd) dd.classList.toggle("open"); }
function onExtSrtChange(e) { if (e) e.stopPropagation(); updateExtSrtBtnLabel(); syncStateToBridge(); }
function clearExtSrt(e) { if (e) e.stopPropagation(); document.querySelectorAll(".ext-srt-cb").forEach(cb => { cb.checked = false; }); updateExtSrtBtnLabel(); syncStateToBridge(); }
document.addEventListener("click", (ev) => {
    const wrap = document.querySelector(".ext-srt-wrap"), dd = document.getElementById("extSrtDropdown");
    if (dd && dd.classList.contains("open") && wrap && !wrap.contains(ev.target)) dd.classList.remove("open");
});

function getSyncPayload(extra) {
    return Object.assign({
        q_idx: selected_q_idx, a_idx: audioSelect ? parseInt(audioSelect.value) : 0,
        s_idx: subSelect ? parseInt(subSelect.value) : 0, sub_mode: modeSelect ? modeSelect.value : "hard_burn",
        ext_sub_indices: getSelectedExtSubIndices(), ext_sub_langs: getSelectedExtSubLangs(),
        max_connections: connSelect ? parseInt(connSelect.value) : 8, sub_pos: "bottom", sub_preset: subPreset, sub_scale: subScale, sub_color: subColor,
        sub_bg_mode: subBgMode, sub_pos_x: subPosX, sub_pos_y: subPosY, dest_path: destInput ? destInput.value.trim() : "",
        clip_start: (typeof clipStartSec !== "undefined" ? clipStartSec : 0.0),
        clip_end: (typeof clipEndSec !== "undefined" ? clipEndSec : 0.0),
        duration: (typeof videoEl !== "undefined" && videoEl && !isNaN(videoEl.duration) && isFinite(videoEl.duration) && videoEl.duration > 0) ? parseFloat(videoEl.duration.toFixed(2)) : 0.0,
        sub_custom_edits: (typeof subCustomEdits !== "undefined" ? subCustomEdits : {}),
        dual_sub: (typeof dualSubEnabled !== "undefined" ? dualSubEnabled : false),
        sec_s_idx: (typeof secSubIndex !== "undefined" ? secSubIndex : -1),
        audio_boost: (typeof audioBoostEnabled !== "undefined" ? audioBoostEnabled : false),
        chapter_title: (typeof selectedChapterTitle !== "undefined" ? selectedChapterTitle : "")
    }, extra || {});
}

function syncStateToBridge() {
    if (!sid) return;
    fetch(`${bridgeBase}/api/sync_state?sid=${encodeURIComponent(sid)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(getSyncPayload())
    }).catch(e => {});
}

function requestUpdatedFilename() {
    if (!sid || !destInput) return;
    fetch(`${bridgeBase}/api/update_filename?sid=${encodeURIComponent(sid)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            q_idx: selected_q_idx, s_idx: subSelect ? parseInt(subSelect.value) : 0,
            sub_mode: modeSelect ? modeSelect.value : "hard_burn", current_dest: destInput.value
        })
    }).then(r => r.json()).then(d => { if (d && d.dest_path) destInput.value = d.dest_path; }).catch(e => {});
}

function doAction(actionType) {
    actionSubmitted = true;
    document.querySelectorAll(".action-bar button").forEach(b => { b.disabled = true; b.style.opacity = "0.6"; });
    try { if (videoEl) { videoEl.pause(); videoEl.removeAttribute('src'); videoEl.load(); } if (dubAudioEl) { dubAudioEl.pause(); dubAudioEl.removeAttribute('src'); dubAudioEl.load(); } } catch (e) {}
    const _closeWin = () => { try { if (window.pywebview && window.pywebview.api && window.pywebview.api.close_window) window.pywebview.api.close_window(); } catch(e) {} try { window.close(); } catch(e) {} };
    if (!sid) { _closeWin(); return; }
    fetch(`${bridgeBase}/api/action?sid=${encodeURIComponent(sid)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(getSyncPayload({ action: actionType }))
    }).then(r => r.json()).then(() => { setTimeout(_closeWin, 120); }).catch(_closeWin);
}

__STUDIO_JS__
__CLIPPER_JS__

subPreset = __SUB_PRESET__; subScale = __SUB_SCALE__; subColor = __SUB_COLOR__;
subBgMode = __SUB_BG__; subPosX = __SUB_PX__; subPosY = __SUB_PY__;
clipStartSec = __CLIP_START__; clipEndSec = __CLIP_END__; dualSubEnabled = __DUAL_SUB__;
audioBoostEnabled = __AUDIO_BOOST__; selectedChapterTitle = __CHAPTER_TITLE__;
initLiveSubDragDrop();
if (typeof initClipperStudioHooks === "function") initClipperStudioHooks();
if (typeof updateClipUI === "function") updateClipUI();
if (typeof disableNativeTextTracks === "function") disableNativeTextTracks();
if (modeSelect && subSelect) { const s0 = parseInt(subSelect.value); modeSelect.disabled = (!s0 || s0 <= 0 || s0 >= subtitleTracks.length); }
applyLiveSubStyle();
if (sid && subtitleTracks && __SEL_S_IDX__ > 0) {
    loadLiveSubtitlesFromUrl(`${bridgeBase}/subtitle.vtt?sid=${encodeURIComponent(sid)}&s_idx=${__SEL_S_IDX__}`);
} else if (__VTT_URI__) {
    loadLiveSubtitlesFromUrl(__VTT_URI__);
}

const initRow = document.querySelector(`.opt-row[data-idx="${selected_q_idx}"]`);
if (initRow && initRow.scrollIntoView) {
    setTimeout(() => initRow.scrollIntoView({ block: "center", behavior: "instant" }), 50);
}
window.addEventListener("pagehide", () => {
    if (sid && !actionSubmitted) { try { navigator.sendBeacon(`${bridgeBase}/api/action?sid=${encodeURIComponent(sid)}`, JSON.stringify({ action: "cancel" })); } catch (e) {} }
});
""".strip()

__all__ = ["_JS_TEMPLATE"]
