import os
from flask import Flask, request, Response
from flask_sock import Sock
from flask_cors import CORS
import requests
import websocket # websocket-client library

# --- Initialization ---
app = Flask(__name__)

# Configure CORS to allow requests ONLY from your Render UI's domain.
# This will automatically handle the OPTIONS preflight requests for you.
CORS(app, resources={r"/*": {"origins": "https://test-server-2-oce9.onrender.com"}})

sock = Sock(app)

# The base URLs for your backend VM server
VM_HTTP_URL = "http://34.72.111.25:8080"
VM_WEBSOCKET_URL = "ws://34.72.111.25:8080"


# --- Route 1: Handle All Regular HTTP Requests ---
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def http_proxy(path):
    """
    This route handles all standard HTTP traffic (like the initial status check).
    It forwards the request to the VM and returns the response.
    """
    try:
        url = f"{VM_HTTP_URL}/{path}"
        
        # Forward the request to the VM
        vm_response = requests.request(
            method=request.method,
            url=url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=10 # Add a timeout
        )

        # Create a response to send back to the UI
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in vm_response.raw.headers.items() if name.lower() not in excluded_headers]

        return Response(vm_response.content, vm_response.status_code, headers)

    except requests.exceptions.RequestException as e:
        print(f"Error forwarding HTTP request: {e}")
        return "Proxy Error: Could not connect to the backend server.", 502


# --- Route 2: Handle All WebSocket Connections ---
@sock.route('/<path:path>')
def websocket_proxy(ws, path):
    """
    This route handles the real-time "to and fro" WebSocket communication.
    """
    backend_url = f"{VM_WEBSOCKET_URL}/{path}"
    print(f"Client connected. Proxying WebSocket to: {backend_url}")

    try:
        # Connect to the backend Go server's WebSocket
        backend_ws = websocket.create_connection(backend_url, timeout=10)
        print("Successfully connected to backend WebSocket.")
    except Exception as e:
        print(f"Error connecting to backend WebSocket: {e}")
        ws.close(1011, "Failed to connect to backend")
        return

    # Main loop to pass messages back and forth
    try:
        while True:
            # Try to receive from client and send to backend
            client_message = ws.receive(timeout=0.05)
            if client_message:
                backend_ws.send(client_message)

            # Try to receive from backend and send to client
            # Use poll() to check for data without blocking forever
            if backend_ws.poll(timeout=0.05):
                 backend_message = backend_ws.recv()
                 if backend_message:
                     ws.send(backend_message)

    except Exception as e:
        print(f"An error occurred in the proxy loop: {e}")
    finally:
        # Clean up connections
        backend_ws.close()
        ws.close()
        print("Proxy connections closed.")

