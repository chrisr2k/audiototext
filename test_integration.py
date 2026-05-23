"""Integration test for the AudioToText web app."""
import requests
import os
import wave
import struct
import math
import tempfile
import time

BASE = 'http://localhost:8000'

# Register user first (in case DB was recreated)
reg_resp = requests.post(f'{BASE}/auth/register', json={
    'username': 'testuser',
    'email': 'test@example.com',
    'password': 'testpass123'
})
print(f'Register status: {reg_resp.status_code}')

# Login
login_resp = requests.post(f'{BASE}/auth/login', json={
    'username': 'testuser',
    'password': 'testpass123'
})
print(f'Login status: {login_resp.status_code}')
token = login_resp.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

# Create a small test WAV file
sample_rate = 8000
duration = 3
num_samples = sample_rate * duration

samples = []
for i in range(num_samples):
    t = float(i) / sample_rate
    val = math.sin(2 * math.pi * 440 * t) * 0.3
    val += math.sin(2 * math.pi * 880 * t) * 0.1
    val += math.sin(2 * math.pi * 220 * t) * 0.2
    samples.append(int(val * 32767))

test_file = os.path.join(tempfile.gettempdir(), 'integration_test.wav')
with wave.open(test_file, 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(struct.pack('<' + 'h' * len(samples), *samples))

print(f'Created test file: {test_file} ({os.path.getsize(test_file)} bytes)')

# Upload via the web API
with open(test_file, 'rb') as f:
    response = requests.post(
        f'{BASE}/transcribe/upload',
        files={'file': ('test.wav', f, 'audio/wav')},
        data={'language': 'en-US'},
        headers=headers
    )

print(f'Upload response status: {response.status_code}')
result = response.json()
print(f'Upload response: {result}')

# Check status
transcript_id = result.get('transcript_id')
if transcript_id:
    time.sleep(1)
    status_resp = requests.get(f'{BASE}/transcribe/status/{transcript_id}', headers=headers)
    print(f'Status response: {status_resp.json()}')

os.remove(test_file)
print("Test completed successfully!")
