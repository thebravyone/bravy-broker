import os
import platform
import secrets
import subprocess
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

BASE_URL = "https://login.eveonline.com/v2/oauth/authorize/"

EVE_CLIENT_ID = os.getenv("EVE_CLIENT_ID")
EVE_SECRET_KEY = os.getenv("EVE_SECRET_KEY")

EVE_SCOPE = "publicData esi-markets.structure_markets.v1"
EVE_CALLBACK_URL = "http://localhost:30001/"


print(
    "\nThis script will guide you through the process of acquiring an ESI refresh token."
)

# Step 1: Open the browser to authenticate at EVE Online
state = secrets.token_urlsafe(16)
params = {
    "response_type": "code",
    "client_id": EVE_CLIENT_ID,
    "redirect_uri": EVE_CALLBACK_URL,
    "scope": EVE_SCOPE,
    "state": state,
}

eve_auth_url = f"{BASE_URL}?{urlencode(params)}"

print("1 - Authenticate at EVE Online")
webbrowser.open(eve_auth_url)


# Step 2 - Setup HTTP server to listen for the callback
def run_server():
    server_address = ("", 30001)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    httpd.handle_request()  # Handle a single request
    return httpd.auth_code, httpd.auth_state


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/":

            query_params = parse_qs(parsed_path.query)
            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            self.wfile.write(b"Authorization code received. You can close this window.")

            self.server.auth_code = code
            self.server.auth_state = state

    def log_message(self, format, *args):
        return  # Override to suppress server logs


auth_code, auth_state = run_server()


# Step 3 - Exchange the authorization code for an access token
def get_access_token(auth_code):
    token_url = "https://login.eveonline.com/v2/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": EVE_CALLBACK_URL,
    }
    auth = (EVE_CLIENT_ID, EVE_SECRET_KEY)
    response = requests.post(token_url, data=data, auth=auth)
    return response.json()


refresh_token: str = None

print("2 - Exchanging authorization code for access token")
if auth_code and auth_state == state:
    token_response = get_access_token(auth_code)
    refresh_token = token_response.get("refresh_token")

    print(f'3 - Received Refresh token: "{refresh_token}"')

    system = platform.system()
    if system == "Windows":
        subprocess.run("clip", text=True, input=refresh_token)
        print("4 - Copied to clipboard!")
else:
    print("Failed to receive a valid authorization code or state mismatch.")
