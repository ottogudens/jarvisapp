import requests
import os

url = 'https://jarvisapp-production-f259.up.railway.app/auth/login'
json_data = {'email': 'mecanico@loshermanos.com', 'password': 'admin123'}
r = requests.post(url, json=json_data)
token = r.json()['access_token']

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
try:
    client.models.generate_content(
        model='gemini-3.6-flash',
        contents=[types.Part.from_bytes(data=b'dummy audio content', mime_type='audio/mp4'), 'Transcribe'],
        config=types.GenerateContentConfig(response_mime_type='application/json')
    )
except Exception as e:
    print('Gemini error:', e)
