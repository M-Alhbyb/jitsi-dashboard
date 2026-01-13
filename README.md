# Jitsi Dashboard

A Django dashboard for managing and monitoring Jitsi Meet servers.

## Features

- **Real-time Monitoring** – Server stats via Colibri/Jicofo APIs
- **Conference Management** – Create meetings with JWT authentication
- **Participant Tracking** – Monitor who joins/leaves meetings
- **Recording Control** – Start/stop recordings via Jibri
- **Analytics** – Usage reports and statistics
- **Webhooks** – Automatic event processing

## Quick Start

### 1. Install

```bash
python -m venv env
source env/bin/activate
pip install django pyjwt requests
```

### 2. Configure

Edit `jitsi/settings.py`:

```python
JITSI_SERVER_URL = 'https://your-jitsi-server.com'
JITSI_APP_ID = 'your_app_id'
JITSI_APP_SECRET = 'your_secret'
```

### 3. Run

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://localhost:8000/`

## API Endpoints

| Endpoint                     | Description       |
| ---------------------------- | ----------------- |
| `GET /api/stats/`            | Server statistics |
| `GET /api/colibri/`          | JVB stats         |
| `POST /api/token/`           | Generate JWT      |
| `POST /api/recording/start/` | Start recording   |
| `POST /api/recording/stop/`  | Stop recording    |

## Jitsi Server Setup

Run the included fix script on your Jitsi server for JWT authentication:

```bash
sudo bash jitsi_fix_script.sh
```

## License

MIT
