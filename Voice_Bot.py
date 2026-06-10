import asyncio
import os
import shutil
import subprocess
import sys
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from deepgram import (DeepgramClient, DeepgramClientOptions, LiveOptions,
                     LiveTranscriptionEvents, Microphone)
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (ChatPromptTemplate, HumanMessagePromptTemplate,
                               MessagesPlaceholder,
                               SystemMessagePromptTemplate)
from langchain_groq import ChatGroq

load_dotenv()

class Config:
    """Loads and validates all necessary configuration from environment variables."""
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        
        # Models
        self.llm_model = "llama-3.1-8b-instant"
        self.stt_model = "nova-2"
        self.tts_model = "aura-helios-en"
        
        # File paths
        self.Bot_prompt_file = "Bot_prompt.txt"
        
        self._validate()

    def _validate(self):
        """Ensures all required configurations are present."""
        if not self.groq_api_key:
            raise ValueError("ERROR: GROQ_API_KEY is not set in the environment.")
        if not self.deepgram_api_key:
            raise ValueError("ERROR: DEEPGRAM_API_KEY is not set in the environment.")
        if not os.path.exists(self.Bot_prompt_file):
            raise FileNotFoundError(f"ERROR: Bot prompt file not found at '{self.Bot_prompt_file}'")
        if not self._is_installed("ffplay"):
            raise RuntimeError("ERROR: ffplay is not installed. Please install ffmpeg to play audio.")

    @staticmethod
    def _is_installed(lib_name: str) -> bool:
        """Checks if a command-line tool is available in the system's PATH."""
        return shutil.which(lib_name) is not None

# --- Service Classes ---

class LiveTranscriber:
    """Handles real-time speech-to-text transcription using Deepgram."""
    def __init__(self, config: Config):
        client_config = DeepgramClientOptions(options={"keepalive": "true"})
        self.client = DeepgramClient(config.deepgram_api_key, client_config)
        self.stt_model = config.stt_model
        self.transcript_future: Optional[asyncio.Future] = None

    async def listen(self) -> str:
        """
        Listens for a single, complete sentence from the microphone and returns it.
        """
        self.transcript_future = asyncio.Future()
        
        connection = self.client.listen.asynclive.v("1")
        connection.on(LiveTranscriptionEvents.Transcript, self._on_message)
        connection.on(LiveTranscriptionEvents.Error, self._on_error)

        options = LiveOptions(
            model=self.stt_model,
            language="en-US",
            punctuate=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            endpointing=300,  # Milliseconds of silence to determine end of speech
            smart_format=True,
        )
        await connection.start(options)
        
        microphone = Microphone(connection.send)
        microphone.start()

        try:
            final_transcript = await self.transcript_future
            return final_transcript
        finally:
            microphone.finish()
            await connection.finish()

    async def _on_message(self, _, result, **kwargs):
        """Callback for handling transcript messages from Deepgram."""
        if result.is_final and result.channel.alternatives[0].transcript.strip():
            transcript = result.channel.alternatives[0].transcript
            if self.transcript_future and not self.transcript_future.done():
                self.transcript_future.set_result(transcript)

    async def _on_error(self, _, error, **kwargs):
        """Callback for handling connection errors."""
        print(f"\nSTT Error: {error}\n")
        if self.transcript_future and not self.transcript_future.done():
            # Propagate the error to the listener
            self.transcript_future.set_exception(Exception(f"STT Error: {error}"))

class LLMProcessor:
    """Manages the language model interaction, including memory."""
    def __init__(self, config: Config):
        llm = ChatGroq(temperature=0, model_name=config.llm_model, groq_api_key=config.groq_api_key)
        
        with open(config.Bot_prompt_file, 'r') as f:
            Bot_prompt = f.read().strip()
        
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(Bot_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{text}")
        ])
        
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        
        self.conversation_chain = LLMChain(llm=llm, prompt=prompt_template, memory=memory)

    def generate_response(self, user_text: str) -> str:
        """Generates a response from the LLM based on user input."""
        start_time = time.time()
        response = self.conversation_chain.invoke({"text": user_text})
        end_time = time.time()
        elapsed_ms = int((end_time - start_time) * 1000)
        
        ai_response = response.get('text', 'I am not sure how to respond to that.')
        print(f"LLM ({elapsed_ms}ms): {ai_response}")
        return ai_response

class SpeechSynthesizer:
    """Handles text-to-speech conversion and audio playback using Deepgram."""
    def __init__(self, config: Config):
        self.api_key = config.deepgram_api_key
        self.model_name = config.tts_model
        self.api_url = f"https://api.deepgram.com/v1/speak?model={self.model_name}&encoding=linear16&sample_rate=24000"

    def speak(self, text: str):
        """Converts text to speech and plays it back in real-time."""
        headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
        payload = {"text": text}
        
        player_command = ["ffplay", "-autoexit", "-", "-nodisp"]
        player_process = subprocess.Popen(
            player_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        request_start_time = time.time()
        
        try:
            with requests.post(self.api_url, stream=True, headers=headers, json=payload, timeout=20) as response:
                response.raise_for_status()
                first_byte_received = False
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        if not first_byte_received:
                            ttfb = int((time.time() - request_start_time) * 1000)
                            print(f"TTS TTFB: {ttfb}ms\n")
                            first_byte_received = True
                        player_process.stdin.write(chunk)
                        player_process.stdin.flush()
        except requests.exceptions.RequestException as e:
            print(f"TTS Request Error: {e}")
        finally:
            if player_process.stdin:
                player_process.stdin.close()
            player_process.wait()

# --- Main Application Orchestrator ---

class VoiceAssistant:
    """The main application class that orchestrates the conversation flow."""
    TERMINATION_PHRASE = "goodbye"

    def __init__(self, config: Config):
        # Provider switches — each defaults to the original Deepgram/Groq
        # path so existing setups keep working with no .env edits.
        #   STT_PROVIDER=sixtydb → 60db /ws/stt
        #   TTS_PROVIDER=sixtydb → 60db /tts-stream → ffplay
        # The LLM stays on Groq here; the LLM can also be routed through
        # 60db by editing LLMProcessor's ChatGroq to ChatOpenAI(base_url=...).
        stt_provider = os.getenv("STT_PROVIDER", "deepgram").strip().lower()
        tts_provider = os.getenv("TTS_PROVIDER", "deepgram").strip().lower()

        if stt_provider in ("sixtydb", "60db"):
            from sixtydb_stt import SixtyDbLiveTranscriber
            self.transcriber = SixtyDbLiveTranscriber(config)
        else:
            self.transcriber = LiveTranscriber(config)

        self.llm_processor = LLMProcessor(config)

        if tts_provider in ("sixtydb", "60db"):
            from sixtydb_tts import SixtyDbSpeechSynthesizer
            self.synthesizer = SixtyDbSpeechSynthesizer(config)
        else:
            self.synthesizer = SpeechSynthesizer(config)

    async def run(self):
        """The main loop for the voice assistant."""
        print("--- Voice Assistant Activated ---")
        print(f"Say '{self.TERMINATION_PHRASE}' to end the conversation.")
        
        while True:
            try:
                print("\nListening...")
                user_text = await self.transcriber.listen()
                
                if not user_text:
                    continue
                    
                print(f"Human: {user_text}")

                if self.TERMINATION_PHRASE in user_text.lower().strip():
                    print("Termination phrase detected. Shutting down.")
                    goodbye_message = "Goodbye! Have a great day."
                    print(f"AI: {goodbye_message}")
                    self.synthesizer.speak(goodbye_message)
                    break

                ai_response = self.llm_processor.generate_response(user_text)
                self.synthesizer.speak(ai_response)
                
            except Exception as e:
                print(f"An error occurred in the main loop: {e}")
                # When an STT error occurs, we want to retry listening
                # rather than crashing the whole application.
                print("Restarting listening loop...")
                await asyncio.sleep(1) # a short delay before retrying

async def main():
    """Initializes and runs the Voice Assistant."""
    import os
    try:
        config = Config()
        assistant = VoiceAssistant(config)
        await assistant.run()
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"Configuration Error: {e}")
        os._exit(1)
    except KeyboardInterrupt:
        print("\n--- Assistant Deactivated by User ---")
        os._exit(0)
    except Exception as e:
        print(f"An unexpected fatal error occurred: {e}")
        os._exit(1)
    finally:
        os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())
