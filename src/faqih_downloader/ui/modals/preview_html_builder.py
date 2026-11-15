"""
Unified VidMate-Style HTML5 Preview & Download Settings Builder (preview_html_builder.py).
Generates modern dark-themed HTML5 preview player with synchronized live audio dubbing,
WebVTT subtitle tracks, and interactive format/quality/dubbing/subtitle controls.
"""
from __future__ import annotations
import html, json
from typing import Dict, List, Optional, Any
from ...config import get_setting
from ...services.youtube_models import extract_media_platform, format_filesize
from .preview_subtitle_studio import get_studio_css, get_studio_toolbar_html, get_studio_js
from .preview_clipper_studio import get_clipper_css, get_clipper_toolbar_html, get_clipper_js

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #090d16; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; user-select: none; }
.header { background: #131a29; height: 50px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #1e293b; flex-shrink: 0; gap: 10px; }
.title-group { display: flex; align-items: center; gap: 8px; overflow: hidden; flex: 1; }
.title { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #f8fafc; }
.badge { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px; white-space: nowrap; }
.badge-res { background: #0284c7; color: #fff; } .badge-sub { background: #059669; color: #fff; } .badge-audio { background: #8b5cf6; color: #fff; } .badge-dim { background: #334155; color: #94a3b8; }
.plat-yt { background: #ef4444; color: #fff; } .plat-tt { background: #ec4899; color: #fff; } .plat-ig { background: #a855f7; color: #fff; } .plat-tw { background: #38bdf8; color: #0f172a; font-weight: bold; } .plat-fb { background: #2563eb; color: #fff; } .plat-generic { background: #475569; color: #fff; }
.actions { display: flex; align-items: center; gap: 8px; }
.btn { background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; white-space: nowrap; }
.btn:hover { background: #0284c7; color: #fff; border-color: #0284c7; }
.player-container { flex: 52 1 0; min-height: 200px; position: relative; background: #000; display: flex; align-items: center; justify-content: center; overflow: hidden; }
video, iframe { width: 100%; height: 100%; border: none; outline: none; background: #000; }
video::cue, ::cue, video::-webkit-media-text-track-container, video::-webkit-media-text-track-display, video::-webkit-media-text-track-region { opacity: 0 !important; display: none !important; color: transparent !important; background: transparent !important; text-shadow: none !important; }
.settings-panel { flex: 48 1 0; min-height: 200px; background: #0f172a; border-top: 1px solid #1e293b; padding: 6px 14px; display: flex; flex-direction: column; overflow-y: auto; gap: 5px; }
.settings-header { display: flex; justify-content: space-between; align-items: center; }
.settings-title { font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; } .settings-count { font-size: 11px; color: #94a3b8; }
.table-container { max-height: 82px; overflow-y: auto; background: #131d31; border: 1px solid #1e293b; border-radius: 6px; }
.format-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
.format-table th { background: #17233c; color: #94a3b8; padding: 5px 10px; font-weight: 600; position: sticky; top: 0; border-bottom: 1px solid #1e293b; }
.format-table td { padding: 4px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
.opt-row { cursor: pointer; transition: background 0.1s ease; } .opt-row:hover { background: #1e293b; } .opt-row.selected { background: #0284c7; color: #fff; } .opt-row.selected td { color: #fff; }
.col-center { text-align: center; } .col-right { text-align: right; } .col-note { color: #94a3b8; font-size: 11px; } .opt-row.selected .col-note { color: #e0f2fe; }
.controls-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
.ctrl-group { display: flex; flex-direction: column; gap: 2px; position: relative; } .ctrl-group label { font-size: 11px; font-weight: 600; color: #94a3b8; }
.ctrl-group select { background: #17233c; color: #f8fafc; border: 1px solid #334155; padding: 4px 8px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer; }
.ctrl-group select:disabled { opacity: 0.48; cursor: not-allowed; }
.ext-srt-wrap { position: relative; } #extSrtBtn { background: #17233c; color: #f8fafc; border: 1px solid #334155; padding: 4px 8px; border-radius: 6px; font-size: 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 6px; width: 100%; }
#extSrtBtn.has-sel { border-color: #38bdf8; color: #38bdf8; font-weight: 700; }
#extSrtDropdown { display: none; position: absolute; top: 100%; left: 0; min-width: 235px; max-height: 195px; overflow-y: auto; background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px; padding: 4px; z-index: 1000; box-shadow: 0 10px 25px rgba(0,0,0,0.65); margin-top: 3px; }
#extSrtDropdown.open { display: block; }
.ext-srt-clear { padding: 5px 8px; font-size: 11px; color: #f87171; cursor: pointer; border-bottom: 1px solid #1e293b; margin-bottom: 3px; border-radius: 4px; font-weight: 600; } .ext-srt-clear:hover { background: #1e293b; }
.ext-srt-item { display: flex; align-items: center; gap: 6px; padding: 4px 8px; font-size: 12px; color: #e2e8f0; cursor: pointer; border-radius: 4px; user-select: none; } .ext-srt-item:hover { background: #1e293b; }
.ext-srt-item input { cursor: pointer; accent-color: #38bdf8; margin: 0; }
.dest-card { display: flex; align-items: center; background: #17233c; border: 1px solid #334155; padding: 4px 10px; border-radius: 6px; gap: 8px; }
.dest-card label { font-size: 11px; font-weight: 600; color: #94a3b8; white-space: nowrap; } .dest-card input { background: transparent; color: #f8fafc; border: none; outline: none; font-size: 12px; flex: 1; }
.action-bar { display: flex; align-items: center; gap: 10px; margin-top: 2px; position: sticky; bottom: 0; background: #0f172a; padding-top: 4px; z-index: 10; }
.btn-download { background: #059669; color: #fff; border: none; padding: 7px 15px; font-size: 12px; font-weight: 700; border-radius: 6px; cursor: pointer; } .btn-download:hover { background: #047857; }
.btn-secondary { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 7px 13px; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; } .btn-secondary:hover { background: #334155; }
.btn-cancel { background: transparent; color: #94a3b8; border: 1px solid #334155; padding: 7px 13px; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; margin-left: auto; } .btn-cancel:hover { background: #334155; color: #fff; }
""".strip()

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


def generate_preview_html(
    url: str, video_title: str, stream_url: Optional[str] = None, vtt_data_uri: Optional[str] = None,
    video_id: Optional[str] = None, sub_label: Optional[str] = None, quality_label: Optional[str] = None, sub_lang: str = "ar",
    dub_audio_url: Optional[str] = None, audio_label: Optional[str] = None, selected_audio_track: Optional[Dict[str, Any]] = None,
    audio_tracks: Optional[List[Dict[str, Any]]] = None, options: Optional[List[Any]] = None, subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
    default_dest_path: Optional[str] = None, sid: Optional[str] = None, bridge_port: Optional[int] = None, platform_name: Optional[str] = None,
    selected_sub_track: Optional[Dict[str, Any]] = None, subtitle_embed_mode: str = "hard_burn", selected_q_idx: int = 0,
    subtitle_position: str = "bottom", subtitle_preset: str = "youtube", subtitle_font_scale: float = 1.0,
    subtitle_text_color: str = "#FFFFFF", subtitle_bg_mode: str = "box", subtitle_pos_x: float = 50.0, subtitle_pos_y: float = 86.0,
    clip_start: float = 0.0, clip_end: float = 0.0, dual_sub: bool = False, **kwargs
) -> str:
    """Generates modern dark-themed HTML5 preview player with synchronized dubbing and controls."""
    safe_title = html.escape(video_title or "Video Preview")
    safe_stream = html.escape(stream_url or "")
    if options and 0 <= selected_q_idx < len(options):
        safe_quality = html.escape(getattr(options[selected_q_idx], "resolution_label", "") or "MP4 Stream")
    else:
        safe_quality = html.escape(quality_label or ("MP4 Stream" if stream_url else "Web Player"))

    platform = platform_name or extract_media_platform(url)
    safe_platform = html.escape(platform)

    sel_a_idx = 0
    if selected_audio_track and audio_tracks:
        for idx, trk in enumerate(audio_tracks):
            if trk == selected_audio_track or (trk.get("track_id") and trk.get("track_id") == selected_audio_track.get("track_id")):
                sel_a_idx = idx; break

    eff_dub = dub_audio_url
    eff_audio_lbl = audio_label
    if selected_audio_track and selected_audio_track.get("track_id") != "original":
        if not eff_dub: eff_dub = selected_audio_track.get("url")
        if not eff_audio_lbl: eff_audio_lbl = selected_audio_track.get("label") or selected_audio_track.get("language")
    if not eff_audio_lbl: eff_audio_lbl = "Original Audio"
    safe_audio_label = html.escape(eff_audio_lbl)

    sel_s_idx = 0
    if selected_sub_track and subtitle_tracks:
        for idx, trk in enumerate(subtitle_tracks):
            if trk == selected_sub_track or (trk.get("sub_id") and trk.get("sub_id") == selected_sub_track.get("sub_id")):
                sel_s_idx = idx; break

    safe_sub_label = html.escape(sub_label or "Subtitles")
    safe_sub_lang = html.escape((sub_lang or "ar").split("-")[0].split("_")[0])
    embed_src = f"https://www.youtube.com/embed/{video_id}?autoplay=1&cc_load_policy=1&cc_lang_pref={safe_sub_lang}&hl={safe_sub_lang}" if video_id else url
    bridge_base = f"http://127.0.0.1:{bridge_port}" if bridge_port else ""

    track_html = ""
    if vtt_data_uri:
        track_html = f'<track label="{safe_sub_label}" kind="subtitles" srclang="{safe_sub_lang}" src="{vtt_data_uri}" default id="vttTrack">'
        sub_badge = f'<span id="badgeSub" class="badge badge-sub">💬 {safe_sub_label}</span>'
    elif sid and subtitle_tracks and 0 < sel_s_idx < len(subtitle_tracks):
        st = subtitle_tracks[sel_s_idx]
        lbl = html.escape(st.get("label") or st.get("language") or "Subtitles")
        sc = html.escape((st.get("language") or "ar").split("-")[0].split("_")[0])
        track_html = f'<track label="{lbl}" kind="subtitles" srclang="{sc}" src="{bridge_base}/subtitle.vtt?sid={sid}&s_idx={sel_s_idx}" default id="vttTrack">'
        sub_badge = f'<span id="badgeSub" class="badge badge-sub">💬 {lbl}</span>'
    elif subtitle_tracks and len(subtitle_tracks) > 1 and sel_s_idx > 0:
        sub_badge = f'<span id="badgeSub" class="badge badge-sub">💬 {safe_sub_label}</span>'
    else:
        sub_badge = '<span id="badgeSub" class="badge badge-dim">💬 No Subtitles</span>'
    is_dub_audio = bool(eff_dub and safe_audio_label != "Original Audio")
    audio_badge = f'<span id="badgeAudio" class="badge {"badge-audio" if is_dub_audio else "badge-dim"}">🔊 {safe_audio_label}</span>'

    plat_low = platform.lower()
    plat_cls = "plat-generic"
    if "youtube" in plat_low: plat_cls = "plat-yt"
    elif "tiktok" in plat_low: plat_cls = "plat-tt"
    elif "instagram" in plat_low: plat_cls = "plat-ig"
    elif "twitter" in plat_low or "x" in plat_low: plat_cls = "plat-tw"
    elif "facebook" in plat_low: plat_cls = "plat-fb"

    settings_html = ""
    if options:
        rows = []
        for idx, opt in enumerate(options):
            r_l, r_e = html.escape(getattr(opt, "resolution_label", "Unknown")), html.escape(str(getattr(opt, "ext", "mp4")).upper())
            fps_val = getattr(opt, "fps", 0)
            r_f = str(fps_val) if isinstance(fps_val, (int, float)) and fps_val > 0 else "—"
            r_s, r_n = html.escape(format_filesize(getattr(opt, "filesize_approx", 0))), html.escape(getattr(opt, "note", ""))
            s_cls = "opt-row selected" if idx == selected_q_idx else "opt-row"
            rows.append(f'<tr class="{s_cls}" data-idx="{idx}" data-raw-size="{int(getattr(opt, "filesize_approx", 0) or 0)}" onclick="selectQualityRow({idx})"><td class="col-res"><strong>{r_l}</strong></td><td class="col-center">{r_e}</td><td class="col-right col-size">{r_s}</td><td class="col-center">{r_f}</td><td class="col-note">{r_n}</td></tr>')
        a_opts = [f'<option value="{i}"{" selected" if i == sel_a_idx else ""}>{html.escape(t.get("label") or t.get("language") or f"Audio #{i}")}</option>' for i, t in enumerate(audio_tracks or [])] or ['<option value="0">Original Audio (Default)</option>']
        s_opts = [f'<option value="{i}"{" selected" if i == sel_s_idx else ""}>{html.escape(t.get("label") or t.get("language") or f"Subtitle #{i}")}</option>' for i, t in enumerate(subtitle_tracks or [])] or ['<option value="0">No Subtitles</option>']
        m_opts = [f'<option value="soft_embed"{" selected" if subtitle_embed_mode == "soft_embed" else ""}>دمج ناعم (Soft Embed)</option>', f'<option value="hard_burn"{" selected" if subtitle_embed_mode == "hard_burn" else ""}>حرق دائم (Burn-in)</option>']
        max_conn = int(kwargs.get("max_connections") or get_setting("max_connections", 8))
        c_opts = [f'<option value="{c}"{" selected" if max_conn == c else ""}>{c} {"Track (مسار)" if c == 1 else "Tracks (مسارات)"}</option>' for c in [1, 2, 4, 8, 16, 32]]
        safe_dst = html.escape(default_dest_path or "")
        raw_ext = kwargs.get("external_subtitle_tracks")
        if raw_ext is None and options and 0 <= selected_q_idx < len(options):
            raw_ext = getattr(options[selected_q_idx], "external_subtitle_tracks", None)
        sel_ext_ids = {str(t.get("sub_id")).strip().lower() for t in (raw_ext or []) if isinstance(t, dict) and t.get("sub_id") and str(t.get("sub_id")).lower() != "none"}
        sel_ext_langs = {str(t.get("language")).strip().lower() for t in (raw_ext or []) if isinstance(t, dict) and not t.get("sub_id") and t.get("language") and str(t.get("language")).lower() != "none"}
        ext_items = ['<div class="ext-srt-clear" onclick="clearExtSrt(event)">✕ بدون ملفات خارجية (مسح الكل / Clear All)</div>']
        init_codes, init_cnt = [], 0
        for i, t in enumerate(subtitle_tracks or []):
            if not isinstance(t, dict): continue
            sid_val = str(t.get("sub_id") or "").strip()
            lng_val = str(t.get("language") or "").strip()
            if sid_val.lower() == "none" or lng_val.lower() == "none" or (i == 0 and not t.get("url") and not sid_val): continue
            eff_id = sid_val or lng_val or f"s{i}"
            code = (lng_val or eff_id).split("-")[0].split("_")[0].upper() or f"S{i}"
            is_chk = (eff_id.lower() in sel_ext_ids) or (lng_val.lower() in sel_ext_langs)
            if is_chk:
                init_cnt += 1
                if code not in init_codes: init_codes.append(code)
            ext_items.append(f'<label class="ext-srt-item" onclick="event.stopPropagation()"><input type="checkbox" class="ext-srt-cb" value="{i}" data-lang="{html.escape(code)}" data-subid="{html.escape(eff_id)}"{" checked" if is_chk else ""} onchange="onExtSrtChange(event)"><span>{html.escape(t.get("label") or lng_val or f"Subtitle #{i}")}</span></label>')
        init_ext_lbl = (f"{', '.join(init_codes[:3])}{'..' if len(init_codes) > 3 else ''} ({init_cnt})" if init_cnt > 0 else "بدون (0)")
        mode_dis = " disabled" if sel_s_idx <= 0 else ""
        ext_srt_ctrl = f'<div class="ctrl-group ext-srt-wrap"><label>📄 Ext SRT / ملفات خارجية</label><button type="button" id="extSrtBtn" class="{"has-sel" if init_cnt > 0 else ""}" onclick="toggleExtSrtDropdown(event)"><span id="extSrtBtnText">{html.escape(init_ext_lbl)}</span><span>▾</span></button><div id="extSrtDropdown" onclick="event.stopPropagation()">{"".join(ext_items)}</div></div>'
        clipper_toolbar = get_clipper_toolbar_html(clip_start=clip_start, clip_end=clip_end, dual_sub=dual_sub, audio_boost=bool(kwargs.get("audio_boost", False)), chapters=kwargs.get("chapters", None))
        studio_toolbar = get_studio_toolbar_html(preset=subtitle_preset, scale=subtitle_font_scale, color=subtitle_text_color, bg_mode=subtitle_bg_mode, pos_x=subtitle_pos_x, pos_y=subtitle_pos_y)
        settings_html = f"""<div class="settings-panel"><div class="settings-header"><span class="settings-title">⚡ Download Quality &amp; Controls</span><span class="settings-count">{len(options)} Formats Detected</span></div><div class="table-container"><table class="format-table"><thead><tr><th>Resolution / Quality</th><th class="col-center">Format</th><th class="col-right">Est. Size</th><th class="col-center">FPS</th><th>Stream Details</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="controls-row"><div class="ctrl-group"><label>🔊 Audio / الدبلجة</label><select id="audioSelect" onchange="onAudioChange()">{"".join(a_opts)}</select></div><div class="ctrl-group"><label>💬 Subtitles / الترجمة</label><select id="subSelect" onchange="onSubChange()">{"".join(s_opts)}</select></div><div class="ctrl-group"><label>⚙️ Mode / الطريقة</label><select id="modeSelect" onchange="onModeChange()"{mode_dis}>{"".join(m_opts)}</select></div>{ext_srt_ctrl}<div class="ctrl-group"><label>⚡ Threads / المسارات</label><select id="connSelect" onchange="onConnChange()">{"".join(c_opts)}</select></div></div>{clipper_toolbar}{studio_toolbar}<div class="dest-card"><label>📁 Save As / مسار الحفظ:</label><input type="text" id="destInput" value="{safe_dst}" /><button type="button" class="btn" style="padding:4px 8px;font-size:11px;" onclick="browseDestination()">📁 Browse...</button></div><div class="action-bar"><button class="btn btn-download" onclick="doAction('download')">⚡ Download Selected Quality</button><button class="btn btn-secondary" onclick="doAction('open_in_main')">🖥️ Open in Main Window</button><button class="btn btn-cancel" onclick="doAction('cancel')">✕ Cancel</button></div></div>"""

    opt_needs_audio = [bool(not getattr(o, "is_progressive", False) and not getattr(o, "is_audio_only", False) and getattr(o, "audio_url", None)) for o in (options or [])]
    safe_tracks = [{k: v for k, v in t.items() if (isinstance(v, (str, int, float, bool)) or v is None) and k not in ("style_config", "secondary_track")} for t in (subtitle_tracks or []) if isinstance(t, dict)]
    _j = lambda v: json.dumps(v).replace("</", "<\\/")
    safe_embed_src = html.escape(embed_src or "", quote=True)
    js_code = _JS_TEMPLATE
    for tok, val in (
        ("__HAS_STREAM__", "true" if stream_url else "false"), ("__EMBED_SRC__", _j(embed_src)), ("__DUB_URL__", _j(eff_dub or "")),
        ("__SID__", _j(sid or "")), ("__AUDIO_TRACKS__", _j(audio_tracks or [])), ("__SUBTITLE_TRACKS__", _j(safe_tracks)),
        ("__EFFECTIVE_AUDIO_LABEL__", _j(eff_audio_lbl)), ("__BRIDGE_BASE__", _j(bridge_base)), ("__SELECTED_Q_IDX__", _j(selected_q_idx)),
        ("__OPT_NEEDS_AUDIO__", _j(opt_needs_audio)), ("__SUB_PRESET__", _j(subtitle_preset or "youtube")),
        ("__SUB_SCALE__", str(float(subtitle_font_scale or 1.0))), ("__SUB_COLOR__", _j(subtitle_text_color or "#FFFFFF")),
        ("__SUB_BG__", _j(subtitle_bg_mode or "box")), ("__SUB_PX__", str(float(subtitle_pos_x or 50.0))),
        ("__SUB_PY__", str(float(subtitle_pos_y or 86.0))), ("__SEL_S_IDX__", str(sel_s_idx)), ("__VTT_URI__", _j(vtt_data_uri or "")),
        ("__STUDIO_JS__", get_studio_js()), ("__CLIPPER_JS__", get_clipper_js()), ("__CLIP_START__", str(float(clip_start or 0.0))),
        ("__CLIP_END__", str(float(clip_end or 0.0))), ("__DUAL_SUB__", "true" if dual_sub else "false"),
        ("__AUDIO_BOOST__", "true" if kwargs.get("audio_boost") else "false"), ("__CHAPTER_TITLE__", _j(str(kwargs.get("chapter_title", "") or ""))),
    ):
        js_code = js_code.replace(tok, val)
    player_flex = "52 1 0" if options else "1"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{safe_title} — Faqih Downloader Preview</title><style>
{_CSS}
{get_studio_css()}
{get_clipper_css()}
    .player-container {{ flex: {player_flex}; }}
    </style></head><body>
    <div class="header"><div class="title-group"><span class="badge {plat_cls}">📺 {safe_platform}</span><span id="badgeRes" class="badge badge-res">🎞️ {safe_quality}</span>{audio_badge}{sub_badge}<span class="title" title="{safe_title}">🎬 {safe_title}</span></div>
        <div class="actions"><div style="display:flex;align-items:center;gap:6px;"><button id="muteBtn" class="btn" style="padding:4px 8px;" title="Mute / Unmute">🔊</button><input type="range" id="volSlider" min="0" max="1" step="0.05" value="1" style="width:65px;accent-color:#38bdf8;cursor:pointer;" title="Volume"></div><button id="toggleBtn" class="btn" onclick="togglePlayer()">🌐 Switch to Web Player</button></div></div>
    <div class="player-container" id="playerContainer"><video id="videoEl" src="{safe_stream}" controls autoplay playsinline style="display: {'block' if stream_url else 'none'};">{track_html}</video><div id="liveSubOverlay" class="live-sub-overlay"></div><div id="centerGuideLine" class="center-guide-line"></div><audio id="dubAudioEl" preload="auto" style="display: none;"></audio><iframe id="iframeEl" src="{'about:blank' if stream_url else safe_embed_src}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen style="display: {'none' if stream_url else 'block'};"></iframe></div>
    {settings_html}<script>
{js_code}
    </script></body></html>"""
