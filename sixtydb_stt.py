"""60db STT — peer of Voice_Bot.LiveTranscriber.

Exposes `SixtyDbLiveTranscriber.listen()` async coroutine returning a
final transcript string, matching the LiveTranscriber interface in
Voice_Bot.py. Uses 60db /ws/stt browser mode (linear PCM 16k JSON
envelopes) and PyAudio for mic capture.

The session closes after the first canonical final (is_final +
speech_final), mirroring how LiveTranscriber resolves its Future per
turn so the main loop advances identically.

Reference: https://docs.60db.ai/websocket-api/stt
"""

from __future__ import annotations

import asyncio
import base64
import json
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE = "https://api.60db.ai"
SAMPLE_RATE = 16000
CHUNK_BYTES = int(SAMPLE_RATE * 2 * 0.06)  # 60 ms of 16-bit mono


class SixtyDbLiveTranscriber:
    """Drop-in peer of Voice_Bot.LiveTranscriber."""

    def __init__(self, _config=None):
        self.api_key = os.getenv("SIXTYDB_API_KEY")
        if not self.api_key:
            raise ValueError("SIXTYDB_API_KEY is not set in the environment.")
        self.api_base = (os.getenv("SIXTYDB_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        self.language = os.getenv("SIXTYDB_STT_LANGUAGE", "en")

    async def listen(self) -> str:
        try:
            import websockets
            import pyaudio
        except ImportError as e:
            raise RuntimeError(
                "60db STT requires 'websockets' and 'pyaudio': " + str(e)
            )

        ws_base = self.api_base.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_base}/ws/stt?apiKey={self.api_key}"
        final_text = ""
        transcription_complete = asyncio.Event()
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_BYTES // 2,
        )

        try:
            async with websockets.connect(url, max_size=None) as ws:
                # Skip past `connecting`, await `connection_established`.
                while True:
                    probe = json.loads(await ws.recv())
                    if "connection_established" in probe:
                        break

                await ws.send(json.dumps({
                    "type": "start",
                    "languages": [self.language],
                    "config": {
                        "encoding": "linear",
                        "sample_rate": SAMPLE_RATE,
                        "utterance_end_ms": 500,
                        "continuous_mode": False,
                        "interim_results_frequency": 300,
                        "audio_enhancement": "adaptive",
                    },
                }))

                async def _send_audio():
                    loop = asyncio.get_running_loop()
                    while not transcription_complete.is_set():
                        try:
                            chunk = await loop.run_in_executor(
                                None, stream.read, CHUNK_BYTES // 2, False
                            )
                        except OSError:
                            break
                        if not chunk:
                            continue
                        try:
                            await ws.send(json.dumps({
                                "type": "audio",
                                "audio": base64.b64encode(chunk).decode(),
                                "encoding": "linear",
                                "sample_rate": SAMPLE_RATE,
                            }))
                        except Exception:
                            break

                sender_task: asyncio.Task | None = None
                async for raw in ws:
                    msg = json.loads(raw)
                    mtype = msg.get("type")
                    if mtype == "connected" and sender_task is None:
                        sender_task = asyncio.create_task(_send_audio())
                        continue
                    if mtype in ("speech_started", "session_stopped"):
                        if mtype == "session_stopped":
                            break
                        continue
                    if mtype != "transcription":
                        continue
                    text = (msg.get("text") or "").strip()
                    if not text:
                        continue
                    if msg.get("is_final") and msg.get("speech_final"):
                        final_text = text
                        transcription_complete.set()
                        try:
                            await ws.send(json.dumps({"type": "stop"}))
                        except Exception:
                            pass
                        try:
                            await asyncio.wait_for(ws.recv(), timeout=2.0)
                        except (asyncio.TimeoutError, Exception):
                            pass
                        break

                if sender_task:
                    sender_task.cancel()
                    try:
                        await sender_task
                    except (asyncio.CancelledError, Exception):
                        pass
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            pa.terminate()

        return final_text
