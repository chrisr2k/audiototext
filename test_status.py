"""Test the status endpoint to verify OCI results are retrieved."""
import requests

BASE = 'http://localhost:8000'

# Login as chris
login_resp = requests.post(BASE + '/auth/login', json={
    'username': 'chris',
    'password': 'test123'
})
print('Login:', login_resp.status_code)
token = login_resp.json().get('access_token')
headers = {'Authorization': 'Bearer ' + token}

# Call the list endpoint - this should now check OCI for processing transcripts
list_resp = requests.get(BASE + '/history/list?page=1&per_page=20', headers=headers)
data = list_resp.json()
print(f'\nChris transcripts ({len(data.get("transcripts", []))}):')
for t in data.get('transcripts', []):
    text = t.get("text") or ""
    print(f'  ID: {t["id"]}, Status: {t["status"]}, Text: {repr(text[:60])}')
