"""
Jitsi API Integration Service

- Colibri REST API (JVB statistics)
- Jicofo REST API (health checks)
- JWT Token Generation
- Jibri Recording Control

"""

import jwt
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from django.conf import settings
import urllib3

# Disable SSL warnings for self-signed certificates (development only)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class JitsiServerConfig:
    base_url: str
    colibri_port: int = 8080
    jicofo_port: int = 8888
    jibri_port: int = 2222
    app_id: str = "jitsi_dashboard"
    app_secret: str = ""
    verify_ssl: bool = False


class JitsiAPI:
    
    def __init__(self, config: JitsiServerConfig):
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        
    # ==================== SERVER STATISTICS ====================
    
    def get_colibri_stats(self) -> Dict[str, Any]:
        host = self.config.base_url.replace("https://", "").replace("http://", "")
        url = f"http://{host}:{self.config.colibri_port}/colibri/stats"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "data": self._get_default_stats()
            }
    
    def get_jicofo_health(self) -> Dict[str, Any]:
        host = self.config.base_url.replace("https://", "").replace("http://", "")
        url = f"http://{host}:{self.config.jicofo_port}/about/health"
        try:
            response = self.session.get(url, timeout=10)
            return {
                "success": True,
                "healthy": response.status_code == 200,
                "status_code": response.status_code
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "healthy": False,
                "error": str(e)
            }
    
    def get_jicofo_stats(self) -> Dict[str, Any]:
        host = self.config.base_url.replace("https://", "").replace("http://", "")
        url = f"http://{host}:{self.config.jicofo_port}/stats"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    def _get_default_stats(self) -> Dict[str, Any]:
        #Return default stats structure when API is unavailable.
        return {
            "conferences": 0,
            "participants": 0,
            "largest_conference": 0,
            "total_conferences_created": 0,
            "total_participants": 0,
            "bit_rate_download": 0,
            "bit_rate_upload": 0,
            "packet_rate_download": 0,
            "packet_rate_upload": 0,
            "stress_level": 0,
            "drain": False,
            "graceful_shutdown": False
        }
    
    # ==================== JWT TOKEN GENERATION ====================
    
    def generate_jwt_token(
        self,
        room_name: str,
        user_name: str,
        user_email: str = "",
        is_moderator: bool = False,
        avatar_url: str = "",
        expiry_hours: int = 24,
        features: Optional[Dict[str, bool]] = None
    ) -> str:
        if not self.config.app_secret:
            raise ValueError("app_secret is required for JWT generation")
        
        now = int(time.time())
        expiry = now + (expiry_hours * 3600)
        
        default_features = {
            "livestreaming": True,
            "recording": True,
            "transcription": False,
            "outbound-call": False,
            "screen-sharing": True
        }
        
        if features:
            default_features.update(features)
        
        payload = {
            "context": {
                "user": {
                    "name": user_name,
                    "email": user_email,
                    "avatar": avatar_url,
                    "moderator": is_moderator
                },
                "features": default_features
            },
            "room": room_name,
            "iss": self.config.app_id,
            "aud": "jitsi",
            "sub": self.config.base_url.replace("https://", "").replace("http://", "").rstrip("/"),
            "iat": now,
            "exp": expiry,
            "nbf": now
        }
        
        return jwt.encode(payload, self.config.app_secret, algorithm="HS256")
    
    def generate_meeting_url(
        self,
        room_name: str,
        user_name: str,
        user_email: str = "",
        is_moderator: bool = False,
        use_jwt: bool = True,
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> str:
        # Clean room name (remove spaces, special chars)
        clean_room = room_name.replace(" ", "-").lower()
        url = f"{self.config.base_url}/{clean_room}"
        
        params = []
        
        if use_jwt and self.config.app_secret:
            token = self.generate_jwt_token(
                room_name=clean_room,
                user_name=user_name,
                user_email=user_email,
                is_moderator=is_moderator
            )
            params.append(f"jwt={token}")
        
        if config_overrides:
            import json
            config_str = json.dumps(config_overrides)
            params.append(f"config.{config_str}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url

    # ==================== RECORDING (JIBRI) ====================
    
    def get_jibri_health(self) -> Dict[str, Any]:
        host = self.config.base_url.replace("https://", "").replace("http://", "")
        url = f"http://{host}:{self.config.jibri_port}/jibri/api/v1.0/health"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "status": data.get("status", {}).get("busyStatus", "UNKNOWN"),
                "health": data.get("status", {}).get("health", {}),
                "data": data
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "status": "UNAVAILABLE",
                "error": str(e)
            }
    
    def start_recording(
        self,
        room_name: str,
        mode: str = "file",  # "file", "stream", or "local"
        stream_url: str = ""
         ) -> Dict[str, Any]:
        
        url = f"{self.config.base_url}:{self.config.jibri_port}/jibri/api/v1.0/startService"
        
        payload = {
            "sessionId": f"session_{room_name}_{int(time.time())}",
            "callParams": {
                "callUrlInfo": {
                    "baseUrl": self.config.base_url,
                    "callName": room_name
                }
            },
            "callLoginParams": {},
            "sinkType": mode.upper()
        }
        
        if mode == "stream" and stream_url:
            payload["youTubeStreamKey"] = stream_url
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return {
                "success": True,
                "message": "Recording started",
                "data": response.json() if response.text else {}
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop_recording(self) -> Dict[str, Any]:
        url = f"{self.config.base_url}:{self.config.jibri_port}/jibri/api/v1.0/stopService"
        try:
            response = self.session.post(url, timeout=30)
            response.raise_for_status()
            return {
                "success": True,
                "message": "Recording stopped"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== UTILITY METHODS ====================
    
    def get_server_overview(self) -> Dict[str, Any]:
        colibri = self.get_colibri_stats()
        jicofo_health = self.get_jicofo_health()
        jicofo_stats = self.get_jicofo_stats()
        jibri = self.get_jibri_health()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "server_url": self.config.base_url,
            "components": {
                "jvb": {
                    "healthy": colibri.get("success", False),
                    "stats": colibri.get("data", {})
                },
                "jicofo": {
                    "healthy": jicofo_health.get("healthy", False),
                    "stats": jicofo_stats.get("data", {})
                },
                "jibri": {
                    "available": jibri.get("success", False),
                    "status": jibri.get("status", "UNKNOWN")
                }
            },
            "summary": {
                "active_conferences": colibri.get("data", {}).get("conferences", 0),
                "active_participants": colibri.get("data", {}).get("participants", 0),
                "total_conferences": colibri.get("data", {}).get("total_conferences_created", 0),
                "upload_bitrate_kbps": colibri.get("data", {}).get("bit_rate_upload", 0) / 1000,
                "download_bitrate_kbps": colibri.get("data", {}).get("bit_rate_download", 0) / 1000,
                "stress_level": colibri.get("data", {}).get("stress_level", 0)
            }
        }


# Singleton instance for the configured Jitsi server
def get_jitsi_api() -> JitsiAPI:
    config = JitsiServerConfig(
        base_url=getattr(settings, 'JITSI_SERVER_URL', 'https://192.168.117.153'),
        colibri_port=getattr(settings, 'JITSI_COLIBRI_PORT', 8080),
        jicofo_port=getattr(settings, 'JITSI_JICOFO_PORT', 8888),
        jibri_port=getattr(settings, 'JITSI_JIBRI_PORT', 2222),
        app_id=getattr(settings, 'JITSI_APP_ID', 'jitsi_dashboard'),
        app_secret=getattr(settings, 'JITSI_APP_SECRET', ''),
        verify_ssl=getattr(settings, 'JITSI_VERIFY_SSL', False)
    )
    return JitsiAPI(config)


import requests
from requests.auth import HTTPBasicAuth

def terminate_meeting(room_name):
    muc_domain = "conference.192.168.117.153"
    # 5280 is prosody port
    url = f"http://192.168.117.153:5280/admin/rooms/{room_name.lower()}@{muc_domain}"
    
    auth = HTTPBasicAuth('admin@auth.192.168.117.153', 'pshpsh00')
    
    try:
        response = requests.delete(url, auth=auth, timeout=5)
        if response.status_code == 200:
            return True
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Connection failed: {e}")
        return False