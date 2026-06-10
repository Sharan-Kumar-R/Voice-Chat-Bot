<h1 align="center">Real-time AI ChatBot and voice-enabled AI VoiceBot</h1>
<br>
<p align="center">
  <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python">
  <img src="https://img.shields.io/badge/langchain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/groq-FF6600?style=for-the-badge&logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI">
  <img src="https://img.shields.io/badge/deepgram-13EF93?style=for-the-badge&logo=deepgram&logoColor=black" alt="Deepgram">
</p>
<br>


🔊 Real-Time Voice AI Assistant using Groq LLaMA3 + Deepgram + LangChain .

This project is a real-time voice-based conversational AI assistant that integrates:

   🧠 Groq’s LLaMA3 (via LangChain) for ultra-fast, high-quality conversational intelligence
   
   🎙️ Deepgram STT (Speech-to-Text) for real-time transcription from microphone input
   
   🗣️ Deepgram TTS (Text-to-Speech) for fast and natural voice responses using ffplay
   
Core components such as LLM (Large Language Model), STT (Speech to Text Model), TTS (Text to Speech Model), and the overall Chatbot architecture have also been documented to support comprehensive understanding and customization.

## Features

- Real-time voice recognition using Deepgram
- AI-powered responses via Groq LLM
- Easy setup with virtual environment
- Cross-platform compatibility

## Installation

### Step 1: Clone the Repository

**Option A: Using VS Code Terminal**
1. Open Visual Studio Code
2. Open a new terminal (Terminal → New Terminal or `Ctrl+Shift+`` )
3. Navigate to your desired directory:
   ```bash
   cd path/to/your/desired/folder
   ```
4. Clone the repository:
   ```bash
   git clone https://github.com/Sharan-Kumar-R/Voice-Chat-Bot.git
   ```
5. Open the project folder:
   ```bash
   cd Voice-Chat-Bot
   ```
6. Open the project in VS Code:
   ```bash
   code .
   ```

**Option B: Using VS Code Git Integration**
1. Open Visual Studio Code
2. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
3. Type "Git: Clone" and select it
4. Paste the repository URL: `https://github.com/Sharan-Kumar-R/Voice-Chat-Bot.git`
5. Choose a folder location and click "Select Repository Location"
6. Click "Open" when prompted

### Step 2: Install FFmpeg

1. Visit [FFmpeg Download Page](https://www.ffmpeg.org/download.html)
2. Download the appropriate version for your operating system
3. Follow the installation instructions for your platform
4. Verify the installation by opening a terminal/command prompt and typing:
   ```bash
   ffmpeg -version
   ```
   If FFmpeg is properly installed, you should see version information displayed.

### Step 3: Create Virtual Environment

Open a terminal in Visual Studio Code and run:

```bash
python -m venv myenv
```

### Step 4: Activate Virtual Environment

**For Windows:**
```bash
myenv\Scripts\activate
```

**For macOS/Linux:**
```bash
source myenv/bin/activate
```

After activation, you should see something like this in your terminal:
```
(myenv) PS C:\Users\username\path\to\project>
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```
## API Setup

### 1. Groq API Key

1. Visit [Groq Console](https://groq.com/)
2. Create an account or sign in
3. Generate a new API key
4. Copy the API key for later use

### 2. Deepgram API Key

1. Visit [Deepgram Console](https://deepgram.com/)
2. Create an account or sign in
3. Generate a new API key
4. Copy the API key for later use

### 3. Environment Configuration

Update the `.env` file in the project root directory and add your API keys (replace if already exists):

```env
GROQ_API_KEY=your_groq_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

**Important:** Replace `your_groq_api_key_here` and `your_deepgram_api_key_here` with your actual API keys.

## Usage

### Running the Voice Bot

1. Make sure your virtual environment is activated:
   ```bash
   myenv\Scripts\activate
   ```

2. Run the main voice bot application:
   ```bash
   python Voice_Bot.py
   ```
3. **Start talking!** The bot will:
   - Listen to your voice input
   - Process it through Groq LLaMA3
   - Respond with natural speech

### Customizing the Bot

To customize the bot's behavior, such as naming the model and defining its function, edit the `Bot_prompt.txt` file.

### Running Other Scripts

To run any other Python file in the project:
```bash
python <filename>.py
```

## Deactivating the Environment

When you're done working with the project, deactivate the virtual environment:

```bash
deactivate
```

## Troubleshooting

- Ensure your API keys are correctly set in the `.env` file
- Make sure your virtual environment is activated before running any scripts
- Check that all dependencies are installed with `pip list`
- Verify your internet connection for API services
- **FFmpeg Issues**: If you encounter audio-related errors, verify FFmpeg installation with `ffmpeg --version`

## Project Structure

```
Voice-Chat-Bot/
├── .env                     # Environment variables (API keys)
├── Chat_Bot.py              # Chat bot implementation
├── llm.py                   # Language model integration
├── Voice_Bot.py             # Main voice bot application
├── README.md                # This documentation
├── requirements.txt         # Python dependencies
├── speech_to_text.py        # Speech-to-text streaming functionality
├── Bot_prompt.txt           # System prompt configuration
├── text_to_speech.py        # Text-to-speech functionality
└── myenv/                   # Virtual environment folder (created during setup)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 60db Provider (alongside Deepgram)

This fork adds [60db](https://docs.60db.ai) as a peer of Deepgram for both TTS and STT. Each service has an independent env switch and defaults preserve the Deepgram + Groq path.

| Concern | File | Switch | Endpoint |
|---|---|---|---|
| TTS | `sixtydb_tts.py` (`SixtyDbSpeechSynthesizer`) | `TTS_PROVIDER=sixtydb` + `SIXTYDB_TTS_TRANSPORT=stream\|sync\|ws` | `POST /tts-stream` (default, NDJSON mp3 chunks), `POST /tts-synthesize` (one-shot mp3), or `wss://api.60db.ai/ws/tts` (LINEAR16 PCM 24k, ffplay invoked with `-f s16le -ar 24000 -ac 1`) |
| STT | `sixtydb_stt.py` (`SixtyDbLiveTranscriber`) | `STT_PROVIDER=sixtydb` | `wss://api.60db.ai/ws/stt` browser mode (linear PCM 16k) |
| LLM | _no new file_ | manual edit | replace `ChatGroq(...)` in `Voice_Bot.py:113` with `ChatOpenAI(model="60db-tiny", base_url="https://api.60db.ai/v1", api_key=os.getenv("SIXTYDB_API_KEY"))` |

Both 60db classes match their Deepgram counterparts' interfaces exactly (`speak(text)` and `async listen() -> str`), so `VoiceAssistant.__init__` only branches on env — no body changes elsewhere.

```env
SIXTYDB_API_KEY=sk_live_...
TTS_PROVIDER=sixtydb
STT_PROVIDER=sixtydb
SIXTYDB_API_BASE=https://api.60db.ai
SIXTYDB_TTS_VOICE_ID=fbb75ed2-975a-40c7-9e06-38e30524a9a1
SIXTYDB_STT_LANGUAGE=en
```

Extra Python deps for the 60db path: `websockets`, `pyaudio` (already required by Deepgram's `Microphone`).

Reference: [docs.60db.ai](https://docs.60db.ai).

In case of any queries, please leave a message or contact me via the email provided in my profile.

<p align="center">
⭐ <strong>Star this repository if you found it helpful!</strong>
</p>
