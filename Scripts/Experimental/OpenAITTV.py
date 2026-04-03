# Tooltip: OpenAI text to speech
from openai import OpenAI
import os
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ''))

response = client.audio.speech.create(
    model="tts-1",
    voice="onyx",
    input="I, uh, I think I did pretty well",
)

response.stream_to_file("output.mp3")