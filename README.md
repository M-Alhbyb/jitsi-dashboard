# Jitsi Dashboard

A comprehensive **Django-based dashboard** for managing and monitoring Jitsi Meet video conferencing servers. This application provides real-time server statistics, conference management, JWT authentication, recording controls, and analytics.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Django](https://img.shields.io/badge/django-4.2+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## ✨ Features

### 🖥️ Server Monitoring
- **Real-time Statistics**: Monitor active conferences, participants, and server load via Colibri REST API
- **Health Checks**: Jicofo and JVB health monitoring
- **Multi-server Support**: Manage multiple Jitsi servers from a single dashboard
- **Bandwidth Monitoring**: Track upload/download bitrates and packet rates

### 📹 Conference Management
- **Create Meetings**: Generate secure meeting rooms with JWT authentication
- **Conference History**: Full audit trail of all meetings with status tracking (active, ended, scheduled)
- **Participant Tracking**: Monitor who joined/left meetings and for how long
- **Password Protection**: Support for password-protected rooms

### 🎥 Recording & Streaming (Jibri)
- **Recording Control**: Start/stop recordings via Jibri API
- **Live Streaming**: Support for YouTube and other RTMP streaming
- **Recording History**: Track all recordings with status and file sizes

### 🔐 JWT Authentication
- **Secure Tokens**: Generate JWT tokens for authenticated meeting access
- **Moderator Controls**: Set user roles and permissions
- **Feature Flags**: Enable/disable recording, screen sharing, transcription per user

### 📊 Analytics & Reporting
- **Usage Analytics**: Conference counts, participant statistics, duration trends
- **Time-based Reports**: Daily, weekly, and monthly usage breakdowns
- **Server Load Analysis**: Track stress levels and resource utilization

### ⚙️ Webhook Integration
- Real-time event processing for room creation/destruction
- Participant join/leave tracking
- Automatic conference status updates

---

## 🛠️ Tech Stack

- **Backend**: Django 4.2+
- **Database**: SQLite (default) / PostgreSQL (production)
- **API Integration**: Jitsi REST APIs (Colibri, Jicofo, Jibri)
- **Authentication**: JWT (PyJWT)
- **HTTP Client**: Requests

---

## 📋 Prerequisites

- Python 3.12+
- A running Jitsi Meet server with:
  - Colibri REST API enabled (port 8080)
  - Jicofo REST API enabled (port 8888)
  - JWT authentication configured
  - (Optional) Jibri for recording (port 2222)

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/jitsi-dashboard.git
cd jitsi-dashboard
```

### 2. Create Virtual Environment

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install django pyjwt requests
```

### 4. Configure Jitsi Server Settings

Edit `jitsi/settings.py` and update the Jitsi configuration:

```python
# Jitsi Configuration
JITSI_SERVER_URL = 'https://your-jitsi-server.com'
JITSI_COLIBRI_PORT = 8080      # JVB REST API port
JITSI_JICOFO_PORT = 8888       # Jicofo REST API port
JITSI_JIBRI_PORT = 2222        # Jibri API port (if using recording)
JITSI_APP_ID = 'your_app_id'   # JWT app ID (must match Prosody config)
JITSI_APP_SECRET = 'your_secret'  # JWT secret (must match Prosody config)
JITSI_VERIFY_SSL = False       # Set to True in production with valid certs
```

### 5. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Run Development Server

```bash
python manage.py runserver
```

Visit `http://localhost:8000/` to access the dashboard.

---

## 🔧 Jitsi Server Configuration

For the dashboard to communicate with your Jitsi server, you need to enable the REST APIs.

### Enable Colibri REST API (JVB)

Edit `/etc/jitsi/videobridge/jvb.conf`:

```hocon
videobridge {
    http-servers {
        public {
            port = 8080
        }
    }
    apis {
        rest {
            enabled = true
        }
    }
}
```

### Enable Jicofo REST API

Edit `/etc/jitsi/jicofo/jicofo.conf`:

```hocon
jicofo {
    rest {
        port = 8888
    }
}
```

### Configure JWT Authentication

The included `jitsi_fix_script.sh` can help configure JWT authentication on your Jitsi server:

```bash
sudo bash jitsi_fix_script.sh
```

This script:
- Installs required Lua dependencies
- Configures Prosody for JWT authentication
- Sets up the correct plugin paths
- Restarts all Jitsi services

---

## 📁 Project Structure

```
jitsi/
├── dashboard/                 # Main application
│   ├── jitsi_api.py          # Jitsi API integration service
│   ├── models.py             # Database models
│   ├── views.py              # View functions
│   ├── urls.py               # URL routing
│   ├── admin.py              # Django admin configuration
│   └── templates/            # HTML templates
│       └── dashboard/
│           ├── base.html     # Base template
│           ├── home.html     # Dashboard home
│           ├── analytics.html
│           ├── settings.html
│           ├── conferences/  # Conference-related templates
│           ├── participants/ # Participant templates
│           └── recordings/   # Recording templates
├── jitsi/                    # Django project settings
│   ├── settings.py           # Main settings
│   ├── urls.py               # Root URL configuration
│   └── wsgi.py               # WSGI application
├── jitsi_fix_script.sh       # Jitsi JWT fix utility
├── manage.py                 # Django management script
└── db.sqlite3               # SQLite database
```

---

## 📡 API Endpoints

| Endpoint                | Method | Description                      |
| ----------------------- | ------ | -------------------------------- |
| `/api/stats/`           | GET    | Get full server overview         |
| `/api/colibri/`         | GET    | Get JVB Colibri statistics       |
| `/api/token/`           | POST   | Generate JWT token               |
| `/api/recording/start/` | POST   | Start recording                  |
| `/api/recording/stop/`  | POST   | Stop recording                   |
| `/webhooks/`            | POST   | Webhook handler for Jitsi events |

---

## 🖥️ Dashboard Pages

| URL                    | Description                         |
| ---------------------- | ----------------------------------- |
| `/`                    | Dashboard home with real-time stats |
| `/conferences/`        | List all conferences                |
| `/conferences/create/` | Create a new meeting                |
| `/conferences/<id>/`   | Conference details                  |
| `/participants/`       | List all participants               |
| `/recordings/`         | List all recordings                 |
| `/analytics/`          | Analytics and reports               |
| `/settings/`           | Dashboard settings                  |

---

## 🗄️ Database Models

### JitsiServer
Stores Jitsi server configurations for multi-server support.

### Conference
Tracks conference/meeting history with status, participants count, and duration.

### Participant
Records individual participant sessions within conferences.

### Recording
Manages recording metadata and status.

### WebhookEvent
Logs all webhook events from Jitsi for debugging and analytics.

### DashboardSettings
Singleton model for dashboard configuration (refresh intervals, thresholds, etc.).

---

## 🔒 Security Considerations

1. **Production Deployment**:
   - Set `DEBUG = False`
   - Use a strong `SECRET_KEY`
   - Configure `ALLOWED_HOSTS`
   - Use HTTPS with valid SSL certificates

2. **JWT Secrets**:
   - Never commit real secrets to version control
   - Use environment variables for sensitive data

3. **API Access**:
   - Consider adding authentication to API endpoints
   - Restrict webhook access by IP if possible

---

## 🐛 Troubleshooting

### "Connection refused" to Jitsi APIs
- Verify the Jitsi REST APIs are enabled
- Check firewall rules (ports 8080, 8888, 2222)
- Ensure the server URL is correct in settings

### JWT Authentication Errors
- Run the `jitsi_fix_script.sh` on your Jitsi server
- Verify APP_ID and APP_SECRET match Prosody configuration
- Check Prosody logs: `sudo tail -f /var/log/prosody/prosody.log`

### SSL Certificate Warnings
- Set `JITSI_VERIFY_SSL = False` for self-signed certificates
- In production, use proper SSL certificates

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📞 Support

If you encounter any issues or have questions, please open an issue on GitHub.
