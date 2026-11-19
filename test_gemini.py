
import os
import socket
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=True)

HOST = "generativelanguage.googleapis.com"

print("STEP 1: Checking Gemini DNS...")

try:
    addresses = socket.getaddrinfo(
        HOST,
        443,
        type=socket.SOCK_STREAM
    )

    print("DNS successful!")
    print("Resolved address:", addresses[0][4][0])

except socket.gaierror as e:
    print("DNS FAILED:", e)
    raise SystemExit(
        "Your computer cannot resolve Google's Gemini API address."
    )

print("\nSTEP 2: Initializing Gemini client...")

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise SystemExit("GOOGLE_API_KEY missing from .env")

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        timeout=20000
    )
)

print("STEP 3: Sending test request...")

start = time.time()

try:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Reply with CONNECTED."
    )

    print("\nSUCCESS!")
    print("Response:", response.text)
    print("Time:", round(time.time() - start, 2), "seconds")

except Exception as e:
    print("\nGEMINI REQUEST FAILED:")
    print(type(e).__name__, str(e))
    print("Time:", round(time.time() - start, 2), "seconds")
