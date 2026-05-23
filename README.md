# AudioToText - OCI Speech Transcription Web App

A web-based application that converts audio files to text using **Oracle Cloud Infrastructure (OCI) Speech AI** service.

Built with **Python FastAPI** backend and a clean, responsive HTML/CSS/JS frontend.

## Features

- 🎤 **Audio Upload** - Drag-and-drop or file picker for MP3, WAV, M4A, FLAC, OGG, AAC, WebM, AMR, Opus
- 🧠 **OCI Speech AI** - Powered by Oracle Cloud Infrastructure's speech recognition
- 🌐 **Multi-language** - Supports 13+ languages including English, Spanish, French, German, Japanese, Chinese, Arabic, Hindi, and more
- 👤 **User Accounts** - Login and manage your transcriptions (accounts managed by admins)
- 👑 **Admin Panel** - User management (create, enable/disable, promote/demote, delete users)
- 📜 **Transcript History** - View, search, and manage all past transcriptions
- 📥 **Download Options** - Export transcripts as TXT or SRT (subtitle format)
- 🔧 **Demo Mode** - Test the full UI without OCI credentials using simulated transcription

## Quick Start

### Prerequisites

- Python 3.10+
- OCI account (optional - demo mode works without it)

### Installation

```bash
# Clone and enter the directory
cd audiototext

# Install dependencies
pip install -r requirements.txt

# Configure (optional - demo mode works out of the box)
# Edit .env to add OCI credentials if desired
```

### Run the App

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000** in your browser.

## Configuration

### Demo Mode (Default)

The app runs in demo mode by default (`DEMO_MODE=true`). No OCI credentials needed.
Upload any audio file to see a simulated transcription result.

### OCI Mode

To use real OCI Speech AI transcription:

1. Set up an OCI API key:
   - Generate an API key pair in OCI Console (User Settings → API Keys)
   - Download the private key (.pem file)

2. Configure `.env`:
```env
OCI_USER_OCID=ocid1.user.oc1..xxxxxxxxxxxxxxxx
OCI_TENANCY_OCID=ocid1.tenancy.oc1..xxxxxxxxxxxxxxxx
OCI_FINGERPRINT=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
OCI_PRIVATE_KEY_PATH=C:/path/to/your/oci_api_key.pem
OCI_REGION=us-ashburn-1
DEMO_MODE=false
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Redirect to transcribe page |
| GET | `/health` | Health check |
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Get current user info |
| GET | `/transcribe/` | Upload page |
| POST | `/transcribe/upload` | Upload & transcribe audio |
| GET | `/transcribe/status/{id}` | Check transcript status |
| GET | `/history/` | Transcript history page |
| GET | `/history/list` | List transcripts (paginated) |
| GET | `/history/{id}` | View transcript detail |
| DELETE | `/history/{id}` | Delete transcript |
| GET | `/history/{id}/download` | Download transcript (txt/srt) |
| GET | `/admin/users` | Admin: list all users |
| POST | `/admin/users/create` | Admin: create new user |
| POST | `/admin/users/{id}/toggle-active` | Admin: enable/disable user |
| POST | `/admin/users/{id}/toggle-admin` | Admin: promote/demote admin |
| POST | `/admin/users/{id}/delete` | Admin: delete user |

## Project Structure

```
audiototext/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration
│   ├── database.py          # SQLite database setup
│   ├── models.py            # User & Transcript models
│   ├── auth.py              # JWT authentication
│   ├── routers/
│   │   ├── auth.py          # Login/register endpoints
│   │   ├── transcribe.py    # Upload & transcribe
│   │   ├── history.py       # History & downloads
│   │   └── admin.py         # Admin user management
│   ├── services/
│   │   └── oci_speech.py    # OCI Speech API integration
│   └── templates/
│       ├── base.html        # Base template with navbar
│       ├── login.html       # Login page
│       ├── register.html    # Registration page
│       ├── index.html       # Upload & transcribe page
│       ├── dashboard.html   # Transcript history
│       └── transcript.html  # Single transcript view
├── uploads/                 # Uploaded audio files
├── requirements.txt
├── .env
└── README.md
```

## Tech Stack

- **Backend**: Python FastAPI
- **Database**: SQLite (via SQLAlchemy)
- **Auth**: JWT tokens (python-jose)
- **Cloud**: OCI Python SDK (oci)
- **Frontend**: HTML + CSS + Vanilla JavaScript
