
import os
import sys
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    sys.exit("ERROR: GOOGLE_API_KEY not found.")

client = genai.Client(api_key=API_KEY)

audio_path = input("Enter audio file path: ").strip().strip('"')

if not os.path.exists(audio_path):
    sys.exit("ERROR: Audio file does not exist.")

try:
    print("\n1. Uploading audio...")

    audio_file = client.files.upload(
        file=audio_path
    )

    print("2. Audio uploaded:", audio_file.uri)
    print("\n3. Testing Gemini transcription model...")

    interaction = client.interactions.create(
        model="gemini-3.5-transcribe",
        input=[
            {
                "type": "audio",
                "uri": audio_file.uri,
                "mime_type": audio_file.mime_type
            }
        ]
    )

    print("\n4. TRANSCRIPTION SUCCESSFUL")
    print("-" * 50)
    print(interaction.output_text)
    print("-" * 50)

except Exception as e:

    print("\nTRANSCRIPTION FAILED")
    print("Error type:", type(e).__name__)
    print("Error details:", str(e))
