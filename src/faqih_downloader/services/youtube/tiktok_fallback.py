"""
TikTokFallbackMixin: direct HTML rehydration and TikWM API fallback extractors.
"""
import re
import json
import http.cookiejar
import urllib.request
from typing import Dict, List, Optional, Any

from .url_matcher import extract_media_id
from ...core.chunk import get_permissive_ssl_context


class TikTokFallbackMixin:
    """Mixin providing direct TikTok HTML rehydration and TikWM API fallback."""

    def _extract_tiktok_via_tikwm(self, url: str) -> Optional[Dict[str, Any]]:
        """Queries TikWM API fallback when TikTok webpage requests fail or trigger WAF challenge."""
        try:
            import urllib.parse
            api_url = f"https://www.tikwm.com/api/?url={urllib.parse.quote(url)}&hd=1"
            self.log(f"[TIKTOK] Querying TikWM API fallback: {api_url}")
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12, context=get_permissive_ssl_context()) as resp:
                res = json.loads(resp.read().decode("utf-8", errors="replace"))

            if not isinstance(res, dict) or res.get("code") != 0 or not isinstance(res.get("data"), dict):
                return None

            d = res["data"]
            media_id = str(d.get("id") or extract_media_id(url) or "tiktok_video")
            raw_title = re.sub(r"[\ufffd\s]+", " ", str(d.get("title") or "")).strip()
            title = (raw_title or f"TikTok_Video_{media_id}")[:180]
            music_info = d.get("music_info") if isinstance(d.get("music_info"), dict) else {}
            duration = int(d.get("duration") or 0) or int(music_info.get("duration") or 0)
            thumbnail = d.get("origin_cover") or d.get("cover") or ""
            formats: List[Dict[str, Any]] = []
            seen_urls = set()

            def _resolve_url(u: str) -> str:
                return f"https://www.tikwm.com{u}" if u.startswith("/") else u

            stream_headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"}

            if d.get("hdplay"):
                hd_url = _resolve_url(str(d["hdplay"]))
                seen_urls.add(hd_url)
                formats.append({
                    "format_id": "hd_no_watermark", "url": hd_url, "ext": "mp4",
                    "width": 1080, "height": 1920,
                    "filesize": int(d.get("hd_size") or d.get("size") or 0),
                    "tbr": 0.0, "vcodec": "h264", "acodec": "aac",
                    "http_headers": dict(stream_headers), "protocol": "https",
                    "format_note": "HD (No Watermark)"
                })

            if d.get("play"):
                play_url = _resolve_url(str(d["play"]))
                if play_url not in seen_urls:
                    seen_urls.add(play_url)
                    formats.append({
                        "format_id": "sd_no_watermark", "url": play_url, "ext": "mp4",
                        "width": 576, "height": 1024,
                        "filesize": int(d.get("size") or 0),
                        "tbr": 0.0, "vcodec": "h264", "acodec": "aac",
                        "http_headers": dict(stream_headers), "protocol": "https",
                        "format_note": "SD (No Watermark)"
                    })

            if d.get("wmplay"):
                wm_url = _resolve_url(str(d["wmplay"]))
                if wm_url not in seen_urls:
                    seen_urls.add(wm_url)
                    formats.append({
                        "format_id": "watermarked", "url": wm_url, "ext": "mp4",
                        "width": 480, "height": 854,
                        "filesize": int(d.get("wm_size") or d.get("size") or 0),
                        "tbr": 0.0, "vcodec": "h264", "acodec": "aac",
                        "http_headers": dict(stream_headers), "protocol": "https"
                    })

            if d.get("music"):
                music_url = _resolve_url(str(d["music"]))
                formats.append({
                    "format_id": "music_audio", "url": music_url, "ext": "mp3",
                    "vcodec": "none", "acodec": "mp3", "abr": 128, "filesize": 0,
                    "http_headers": dict(stream_headers), "protocol": "https"
                })

            if not formats:
                return None

            self.log(f"[TIKTOK] TikWM API extraction successful: {len(formats)} formats found.")
            return {
                "id": media_id, "title": title, "duration": duration, "thumbnail": thumbnail,
                "webpage_url": url, "http_headers": stream_headers, "_sd_cookie_header": "",
                "formats": formats, "subtitles": {}
            }
        except Exception as e:
            self.log(f"[TIKTOK ERROR] TikWM extraction failed: {e}")
            return None

    def _extract_tiktok_direct(self, url: str) -> Optional[Dict[str, Any]]:
        """Direct TikTok rehydration extractor parsing __UNIVERSAL_DATA_FOR_REHYDRATION__, falling back to TikWM API."""
        html_info = None
        try:
            self.log(f"[TIKTOK] Attempting direct HTML rehydration extraction for: {url}")
            cj = http.cookiejar.CookieJar()
            ctx = get_permissive_ssl_context()
            https_h = urllib.request.HTTPSHandler(context=ctx)
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), https_h)
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.tiktok.com/",
            })
            with opener.open(req, timeout=12) as resp:
                final_url = resp.geturl()
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc or raw[:2] == b"\x1f\x8b":
                    import gzip; raw = gzip.decompress(raw)
                elif "deflate" in enc:
                    import zlib; raw = zlib.decompress(raw)
                html = raw.decode("utf-8", errors="replace")

            data = None
            m = re.search(r'<script[^>]*\bid="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if m:
                try: data = json.loads(m.group(1).strip())
                except Exception: pass
            if not data:
                m2 = re.search(r'<script[^>]*\bid="(?:SIGI_STATE|sigi-persisted-data)"[^>]*>(.*?)</script>', html, re.DOTALL)
                if m2:
                    try: data = json.loads(m2.group(1).strip())
                    except Exception: pass

            if isinstance(data, dict):
                scope = data.get("__DEFAULT_SCOPE__", {})
                vdetail = scope.get("webapp.video-detail", {})
                item = vdetail.get("itemInfo", {}).get("itemStruct") or vdetail.get("itemStruct")
                if not item and "ItemModule" in data and isinstance(data["ItemModule"], dict):
                    item = next(iter(data["ItemModule"].values()), None)
                if not isinstance(item, dict):
                    def _find_item(obj, d=0):
                        if d > 8 or not isinstance(obj, dict): return None
                        if "itemStruct" in obj and isinstance(obj["itemStruct"], dict): return obj["itemStruct"]
                        if "video" in obj and "id" in obj and isinstance(obj.get("video"), dict): return obj
                        for v in obj.values():
                            if isinstance(v, dict):
                                r = _find_item(v, d + 1)
                                if r: return r
                        return None
                    item = _find_item(data)

                if isinstance(item, dict):
                    cookie_header = "; ".join(f"{c.name}={c.value}" for c in cj)
                    stream_headers = {"User-Agent": ua, "Referer": "https://www.tiktok.com/"}
                    if cookie_header: stream_headers["Cookie"] = cookie_header
                    video = item.get("video") or {}
                    media_id = str(item.get("id") or extract_media_id(final_url) or "tiktok_video")
                    title = str(item.get("desc") or f"TikTok_Video_{media_id}").strip()[:180]
                    duration = int(video.get("duration") or 0)
                    thumbnail = video.get("originCover") or video.get("cover") or ""
                    formats: List[Dict[str, Any]] = []
                    seen_urls = set()

                    for b in video.get("bitrateInfo") or []:
                        if not isinstance(b, dict): continue
                        pa = b.get("PlayAddr") or {}
                        url_list = pa.get("UrlList") or []
                        s_url = next((u for u in url_list if u and isinstance(u, str) and u.startswith("http")), None)
                        if not s_url or s_url in seen_urls: continue
                        seen_urls.add(s_url)
                        formats.append({
                            "format_id": str(b.get("GearName") or f"tt_{pa.get('Height') or 1024}p"),
                            "url": s_url, "ext": "mp4",
                            "width": int(pa.get("Width") or video.get("width") or 576),
                            "height": int(pa.get("Height") or video.get("height") or 1024),
                            "filesize": int(pa.get("DataSize") or 0),
                            "tbr": float(b.get("Bitrate") or 0) / 1000.0,
                            "vcodec": str(b.get("CodecType") or "h264").lower(),
                            "acodec": "aac", "http_headers": dict(stream_headers), "protocol": "https"
                        })

                    for k, pfx in (("downloadAddr", "download"), ("playAddr", "play")):
                        v = video.get(k)
                        cu = v if isinstance(v, str) and v.startswith("http") else None
                        if not cu and isinstance(v, dict):
                            cu = next((u for u in v.get("UrlList") or [] if isinstance(u, str) and u.startswith("http")), None)
                        if cu and cu not in seen_urls:
                            seen_urls.add(cu)
                            formats.append({
                                "format_id": f"{pfx}_addr", "url": cu, "ext": "mp4",
                                "width": int(video.get("width") or 576), "height": int(video.get("height") or 1024),
                                "filesize": int(video.get("dataSize") or 0), "tbr": 0.0,
                                "vcodec": "h264", "acodec": "aac", "http_headers": dict(stream_headers), "protocol": "https"
                            })

                    music = item.get("music") or {}
                    mu = music.get("playUrl")
                    if isinstance(mu, str) and mu.startswith("http") and mu not in seen_urls:
                        seen_urls.add(mu)
                        formats.append({
                            "format_id": "music_audio", "url": mu, "ext": "mp3",
                            "vcodec": "none", "acodec": "mp3", "abr": 128,
                            "http_headers": dict(stream_headers), "protocol": "https"
                        })

                    subtitles: Dict[str, List[Dict[str, Any]]] = {}
                    caps = (video.get("claInfo") or {}).get("captionInfos") or video.get("subtitleInfos") or (item.get("claInfo") or {}).get("captionInfos") or item.get("subtitleInfos") or []
                    for cap in caps:
                        if isinstance(cap, dict) and cap.get("Url"):
                            lang_raw = str(cap.get("LanguageCodeName") or cap.get("language") or "und").strip()
                            l_key = lang_raw.split("-")[0].lower() if "-" in lang_raw else lang_raw.lower()
                            fmt = str(cap.get("Format") or "vtt").lower()
                            subtitles.setdefault(l_key, []).append({
                                "url": str(cap["Url"]), "ext": fmt if fmt in ("vtt", "srt") else "vtt", "name": lang_raw
                            })

                    if formats:
                        self.log(f"[TIKTOK] Direct rehydration successful: {len(formats)} formats, {len(subtitles)} subtitle tracks.")
                        html_info = {
                            "id": media_id, "title": title, "duration": duration, "thumbnail": thumbnail,
                            "webpage_url": final_url, "http_headers": stream_headers, "_sd_cookie_header": cookie_header,
                            "formats": formats, "subtitles": subtitles
                        }
        except Exception as e:
            self.log(f"[TIKTOK ERROR] Direct extraction failed: {e}")

        if html_info and html_info.get("formats"):
            return html_info

        self.log(f"[TIKTOK] Direct HTML rehydration produced no formats. Falling back to TikWM API for: {url}")
        tikwm_info = self._extract_tiktok_via_tikwm(url)
        if tikwm_info and tikwm_info.get("formats"):
            return tikwm_info

        return None
