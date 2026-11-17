"""Bounded streaming and per-origin pacing; no automatic retry of 429."""
import math
import threading
import time
from urllib.parse import urlsplit


class RequestPolicy:
    def __init__(self, interval=0.5, max_bytes=5 * 1024 * 1024):
        if (isinstance(interval, bool) or not isinstance(interval, (int, float))
                or not math.isfinite(interval) or interval < 0
                or isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0):
            raise ValueError('Invalid request limits')
        self.interval, self.max_bytes = interval, max_bytes
        self.last = {}
        self.stopped = set()
        self.lock = threading.Lock()

    def get(self, session, url, **kwargs):
        origin = urlsplit(url).netloc.lower()
        with self.lock:
            if origin in self.stopped:
                raise ValueError('Requests stopped after HTTP 429 for this origin')
            delay = self.interval - (time.monotonic() - self.last.get(origin, -float('inf')))
            if delay > 0:
                time.sleep(delay)
            self.last[origin] = time.monotonic()
        started = time.perf_counter()
        response = session.get(url, stream=True, **kwargs)
        headers_ms = (time.perf_counter() - started) * 1000
        try:
            if response.status_code == 429:
                self.stopped.add(origin)
            length = response.headers.get('Content-Length')
            if length and int(length) > self.max_bytes:
                raise ValueError('Response exceeds max_response_bytes')
            if hasattr(response, 'iter_content'):
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ValueError('Response exceeds max_response_bytes')
                    chunks.append(chunk)
                response._content = b''.join(chunks)
                response._content_consumed = True
            elif len(response.text.encode('utf-8')) > self.max_bytes:
                raise ValueError('Response exceeds max_response_bytes')
            response.seo_metrics = {
                'headers_ms': round(headers_ms, 3),
                'html_fetch_ms': round((time.perf_counter() - started) * 1000, 3),
                'decoded_body_bytes': len(response.content) if hasattr(response, 'content') else len(response.text.encode('utf-8')),
                'method': 'single HTTP request incl. body; excludes pacing, redirects and browser rendering',
                'core_web_vitals': None,
            }
            return response
        except Exception:
            response.close()
            raise
