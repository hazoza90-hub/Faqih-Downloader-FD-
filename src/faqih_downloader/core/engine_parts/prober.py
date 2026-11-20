"""
Engine server capabilities prober mixin: HEAD/GET range probing, redirect handling, and clen extraction.
"""
import os
import urllib.request
import urllib.error
import urllib.parse
from typing import Any


class EngineProberMixin:
    """Server capabilities prober mixin for TurboDownloadEngine."""

    @staticmethod
    def _extract_googlevideo_clen(url: str) -> int:
        """Extracts positive integer content length from a googlevideo URL's `clen` query parameter."""
        try:
            clen = urllib.parse.parse_qs(urllib.parse.urlsplit(str(url)).query).get("clen")
            if clen and int(clen[0]) > 0:
                return int(clen[0])
        except Exception:
            pass
        return 0

    def _handle_redirect(self, resp: Any):
        redirected_url = resp.geturl()
        if redirected_url:
            if urllib.parse.urlsplit(redirected_url).scheme.lower() not in ("http", "https", "ftp"):
                raise ValueError("Unsupported redirect scheme")
            if redirected_url != self.url:
                self.url = redirected_url
                if self.is_googlevideo_url(self.url):
                    self.is_googlevideo = True

    def probe(self):
        """
        Inspect target URL for Content-Length, HTTP 206 Accept-Ranges, and file name.
        Uses HEAD with fallback to GET Range: bytes=0-0 to bypass servers blocking HEAD.
        """
        self.log(f"Probing server capabilities: {self.url}")
        if self.is_googlevideo or "googlevideo.com" in self.url:
            clen_val = self._extract_googlevideo_clen(self.url)
            if clen_val > 0:
                self.total_size, self.supports_ranges = clen_val, True
                self.log(f"Fast clen probe: {self.total_size:,} bytes (Accept-Ranges verified)")
                if not self.filename or os.path.isdir(self.destination_path) or self.filename in (".", "..", "download.bin"):
                    url_fn = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(self.url).path.rstrip("/")))
                    if url_fn:
                        self.filename = url_fn
                if os.path.isdir(self.destination_path) or self.destination_path.endswith(("/", "\\")):
                    self.destination_path = os.path.join(self.destination_path, self.filename or "download.bin")
                    self.temp_dir = self.destination_path + ".sd_parts"
                return

        req = self._create_request(method="HEAD")

        head_succeeded = False
        try:
            with urllib.request.urlopen(req, timeout=12, context=self.ssl_context) as resp:
                self._handle_redirect(resp)
                cl = resp.headers.get("Content-Length")
                ar = resp.headers.get("Accept-Ranges", "").lower()
                raw_ct = resp.headers.get("Content-Type", "")
                self.content_type = raw_ct.split(";")[0].strip().lower()
                self.total_size = int(cl) if cl and cl.isdigit() else 0
                self.supports_ranges = (ar == "bytes") and (self.total_size > 0)
                cd_fn = self._parse_filename_from_cd(resp.headers.get("Content-Disposition", ""))
                if cd_fn:
                    self.filename = cd_fn
                head_succeeded = True
        except ValueError:
            raise
        except urllib.error.HTTPError as e:
            e.close()
            head_succeeded = False
        except Exception:
            head_succeeded = False

        # If HEAD failed or did not confirm range support, test with GET Range: bytes=0-0
        if not head_succeeded or not self.supports_ranges:
            req = self._create_request()
            req.add_header("Range", "bytes=0-0")
            try:
                with urllib.request.urlopen(req, timeout=12, context=self.ssl_context) as resp:
                    self._handle_redirect(resp)
                    raw_ct = resp.headers.get("Content-Type", "")
                    if raw_ct:
                        self.content_type = raw_ct.split(";")[0].strip().lower()

                    cr = resp.headers.get("Content-Range", "")
                    if "/" in cr:
                        total_str = cr.split("/")[-1].strip()
                        if total_str.isdigit():
                            self.total_size = int(total_str)
                            self.supports_ranges = True
                    elif resp.getcode() == 206:
                        self.supports_ranges = True

                    if not self.total_size and resp.getcode() == 200:
                        cl = resp.headers.get("Content-Length")
                        self.total_size = int(cl) if cl and cl.isdigit() else 0

                    cd = resp.headers.get("Content-Disposition", "")
                    cd_fn = self._parse_filename_from_cd(cd)
                    if cd_fn:
                        self.filename = cd_fn
            except ValueError:
                raise
            except Exception as e:
                if isinstance(e, urllib.error.HTTPError):
                    e.close()
                    if e.code in (401, 403, 410):
                        self.has_expired_link = True
                        self.last_http_status = e.code
                if not head_succeeded:
                    try:
                        req_plain = self._create_request()
                        with urllib.request.urlopen(req_plain, timeout=12, context=self.ssl_context) as resp:
                            self._handle_redirect(resp)
                            raw_ct = resp.headers.get("Content-Type", "")
                            if raw_ct:
                                self.content_type = raw_ct.split(";")[0].strip().lower()

                            cl = resp.headers.get("Content-Length")
                            ar = resp.headers.get("Accept-Ranges", "").lower()
                            self.total_size = int(cl) if cl and cl.isdigit() else 0
                            self.supports_ranges = (ar == "bytes") and (self.total_size > 0)
                            cd_fn = self._parse_filename_from_cd(resp.headers.get("Content-Disposition", ""))
                            if cd_fn:
                                self.filename = cd_fn
                    except ValueError:
                        raise
                    except Exception as e_plain:
                        if isinstance(e_plain, urllib.error.HTTPError):
                            e_plain.close()
                            if e_plain.code in (401, 403, 410):
                                self.has_expired_link = True
                                self.last_http_status = e_plain.code
                        raise RuntimeError(f"Connection failed: {e_plain}")

        # Additional defense for googlevideo.com streams: extract clen query parameter if total_size is missing
        if (self.is_googlevideo or "googlevideo.com" in self.url) and self.total_size <= 0:
            try:
                clen = urllib.parse.parse_qs(urllib.parse.urlsplit(self.url).query).get("clen")
                if clen and clen[0].isdigit():
                    self.total_size, self.supports_ranges = int(clen[0]), True
            except Exception:
                pass
        if self.is_googlevideo and self.total_size > 0:
            self.supports_ranges = True

        # Fallback filename extraction from URL if Content-Disposition was absent
        if not self.filename or os.path.isdir(self.destination_path) or self.filename in (".", "..", "download.bin"):
            try:
                parsed_path = urllib.parse.urlsplit(self.url).path
                url_fn = os.path.basename(urllib.parse.unquote(parsed_path.rstrip("/")))
                if url_fn:
                    self.filename = url_fn
            except Exception:
                pass

        if os.path.isdir(self.destination_path) or self.destination_path.endswith(("/", "\\")):
            self.destination_path = os.path.join(self.destination_path, self.filename or "download.bin")
            self.temp_dir = self.destination_path + ".sd_parts"
            for leg in (self.destination_path + ".tdm_parts", self.destination_path + ".idm_parts"):
                if os.path.isdir(leg) and not os.path.exists(self.temp_dir):
                    try:
                        os.replace(leg, self.temp_dir)
                        break
                    except Exception:
                        pass

        # HTML response safety net: abort if server returned an HTML page instead of a binary file
        fn_to_check = self.filename or os.path.basename(self.destination_path)
        dest_ext = os.path.splitext(fn_to_check)[1].lower() if fn_to_check else ""
        if getattr(self, "content_type", "") == "text/html" and (not dest_ext or dest_ext == ".bin"):
            raise RuntimeError("Server returned a web page (HTML), not a file")

        if self.supports_ranges and self.total_size > 0:
            self.log(f"Server supports HTTP 206 Multi-threading! Total Size: {self.total_size / (1024*1024):.2f} MB ({self.total_size:,} bytes).")
        elif self.total_size > 0:
            self.log(f"Server does not support HTTP Range requests. Size: {self.total_size:,} bytes. Single-stream fallback active.")
        else:
            self.log("Server does not support HTTP Range requests and size is dynamic/unknown. Single-stream fallback active.")
