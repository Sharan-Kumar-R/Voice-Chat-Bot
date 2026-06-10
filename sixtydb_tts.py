"""60db TTS — peer of Voice_Bot.SpeechSynthesizer.

Exposes `SixtyDbSpeechSynthesizer.speak(text)` with the same streaming
semantics as the Deepgram path: POST → iter chunks → write to ffplay
stdin → audio plays as it arrives.

Three transport surfaces, picked via SIXTYDB_TTS_TRANSPORT env:
    stream (default) — POST /tts-stream (NDJSON of base64 mp3 chunks)
    sync             — POST /tts-synthesize (one-shot mp3)
    ws               — wss://api.60db.ai/ws/tts (LINEAR16 24k PCM,
                       ffplay invoked with -f s16le for raw PCM)

References:
    https://docs.60db.ai/api-reference/tts/text-to-speech
    https://docs.60db.ai/api-reference/tts/text-to-speech-stream
    https://docs.60db.ai/websocket-api/tts
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import time

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE = "https://api.60db.ai"
DEFAULT_VOICE_ID = "fbb75ed2-975a-40c7-9e06-38e30524a9a1"
WS_SAMPLE_RATE = 24000


class SixtyDbSpeechSynthesizer:
    """Drop-in peer of Voice_Bot.SpeechSynthesizer."""

    def __init__(self, _config=None):
        self.api_key = os.getenv("SIXTYDB_API_KEY")
        if not self.api_key:
            raise ValueError("SIXTYDB_API_KEY is not set in the environment.")
        self.api_base = (os.getenv("SIXTYDB_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        self.voice_id = os.getenv("SIXTYDB_TTS_VOICE_ID", DEFAULT_VOICE_ID)
        self.transport = os.getenv("SIXTYDB_TTS_TRANSPORT", "stream").strip().lower()

    def speak(self, text: str) -> None:
        if self.transport == "sync":
            self._speak_sync(text)
        elif self.transport == "ws":
            self._speak_ws(text)
        else:
            self._speak_ndjson(text)

    # ---- helpers -----------------------------------------------------------

    @staticmethod
    def _spawn_ffplay(extra_args: list[str] | None = None) -> subprocess.Popen:
        cmd = ["ffplay", "-autoexit", "-nodisp", *(extra_args or []), "-"]
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _auth_json_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ---- sync REST (POST /tts-synthesize → mp3) ----------------------------

    def _speak_sync(self, text: str) -> None:
        payload = {
            "text": text,
            "voice_id": self.voice_id,
            "enhance": True,
            "speed": 1,
            "stability": 50,
            "similarity": 75,
            "output_format": "mp3",
        }
        start = time.time()
        try:
            r = requests.post(
                f"{self.api_base}/tts-synthesize",
                json=payload,
                headers=self._auth_json_headers(),
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("success") or not data.get("audio_base64"):
                print(f"60db /tts-synthesize empty: {data.get('message')}")
                return
            mp3 = base64.b64decode(data["audio_base64"])
            ttfb = int((time.time() - start) * 1000)
            print(f"TTS TTFB: {ttfb}ms (sync REST)\n")
            player = self._spawn_ffplay()
            try:
                player.stdin.write(mp3)
            finally:
                if player.stdin:
                    player.stdin.close()
                player.wait()
        except requests.exceptions.RequestException as e:
            print(f"TTS Request Error: {e}")

    # ---- NDJSON stream (POST /tts-stream → mp3 chunks) ---------------------

    def _speak_ndjson(self, text: str) -> None:
        payload = {"text": text, "voice_id": self.voice_id, "output_format": "mp3"}
        player = self._spawn_ffplay()
        start = time.time()
        first = False
        try:
            with requests.post(
                f"{self.api_base}/tts-stream",
                json=payload,
                headers=self._auth_json_headers(),
                stream=True,
                timeout=120,
            ) as r:
                r.raise_for_status()
                for raw in r.iter_lines(decode_unicode=True):
                    line = (raw or "").strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "error":
                        print(f"60db TTS stream error: {line[:200]}")
                        break
                    if msg.get("type") == "complete":
                        break
                    content = msg.get("audioContent")
                    if not content:
                        continue
                    chunk = base64.b64decode(content)
                    if not first:
                        ttfb = int((time.time() - start) * 1000)
                        print(f"TTS TTFB: {ttfb}ms (NDJSON stream)\n")
                        first = True
                    player.stdin.write(chunk)
                    player.stdin.flush()
        except requests.exceptions.RequestException as e:
            print(f"TTS Request Error: {e}")
        finally:
            if player.stdin:
                player.stdin.close()
            player.wait()

    # ---- WebSocket (wss://.../ws/tts → LINEAR16 PCM) ----------------------

    def _speak_ws(self, text: str) -> None:
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            print(f"SIXTYDB_TTS_TRANSPORT=ws needs 'websockets': {e}")
            return
        # Raw 16-bit PCM needs explicit format flags so ffplay doesn't
        # try to auto-detect a container.
        player = self._spawn_ffplay(
            ["-f", "s16le", "-ar", str(WS_SAMPLE_RATE), "-ac", "1"]
        )
        start = time.time()
        first_holder = [False]

        async def _run():
            import websockets
            ws_base = self.api_base.replace("https://", "wss://").replace("http://", "ws://")
            url = f"{ws_base}/ws/tts?apiKey={self.api_key}"
            context_id = f"ctx-{os.getpid()}"
            async with websockets.connect(url, max_size=None) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    if "connection_established" in msg:
                        await ws.send(json.dumps({
                            "create_context": {
                                "context_id": context_id,
                                "voice_id": self.voice_id,
                                "audio_config": {
                                    "audio_encoding": "LINEAR16",
                                    "sample_rate_hertz": WS_SAMPLE_RATE,
                                },
                            }
                        }))
                        continue
                    if "context_created" in msg:
                        await ws.send(json.dumps({
                            "send_text": {"context_id": context_id, "text": text}
                        }))
                        await ws.send(json.dumps({
                            "flush_context": {"context_id": context_id}
                        }))
                        continue
                    chunk_b64 = msg.get("audio_chunk", {}).get("audioContent")
                    if chunk_b64:
                        pcm = base64.b64decode(chunk_b64)
                        if not first_holder[0]:
                            ttfb = int((time.time() - start) * 1000)
                            print(f"TTS TTFB: {ttfb}ms (WebSocket)\n")
                            first_holder[0] = True
                        player.stdin.write(pcm)
                        player.stdin.flush()
                        continue
                    if "flush_completed" in msg:
                        try:
                            await ws.send(json.dumps({
                                "close_context": {"context_id": context_id}
                            }))
                        except Exception:
                            pass
                        break

        try:
            asyncio.new_event_loop().run_until_complete(_run())
        except Exception as e:
            print(f"60db WS TTS error: {e}")
        finally:
            if player.stdin:
                player.stdin.close()
            player.wait()
