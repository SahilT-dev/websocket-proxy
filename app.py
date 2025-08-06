import os
from flask import Flask
from flask_sock import Sock
import websocket # This is the 'websocket-client' library
from flask_cors import CORS  # 1. Import the CORS library

# Initialize Flask and Flask-Sock
app = Flask(__name__)
# 2. Configure CORS for your app
# This tells the server to allow requests ONLY from your Render UI's domain.
CORS(app, resources={r"/*": {"origins": "https://test-server-2-oce9.onrender.com"}})

sock = Sock(app)

# The IP address and port of your VM server
VM_SERVER_URL = "ws://34.72.111.25:8080"

@sock.route('/<path:path>')
def websocket_proxy(ws, path):
    """
    Handles the WebSocket connection.
    It opens a connection to the backend Go server and then
    transparently passes messages back and forth.
    """
    backend_url = f"{VM_SERVER_URL}/{path}"
    print(f"Client connected. Proxying to backend: {backend_url}")

    try:
        # Connect to the backend Go server's WebSocket
        backend_ws = websocket.create_connection(backend_url)
        print("Successfully connected to backend WebSocket.")
    except Exception as e:
        print(f"Error connecting to backend WebSocket: {e}")
        ws.close()
        return

    # This is the main loop to pass messages
    while True:
        try:
            # Check for messages from the client (UI) and send to backend
            client_message = ws.receive(timeout=0.01) # Non-blocking receive
            if client_message:
                print(f"C -> B: {client_message}")
                backend_ws.send(client_message)

            # Check for messages from the backend (Go server) and send to client
            backend_message = backend_ws.recv()
            if backend_message:
                print(f"B -> C: {backend_message}")
                ws.send(backend_message)

        except websocket.WebSocketTimeoutException:
            # This is expected when no message is received
            continue
        except Exception as e:
            print(f"An error occurred in the proxy loop: {e}")
            break

    # Clean up connections
    backend_ws.close()
    ws.close()
    print("Connections closed.")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # This requires a more advanced server like 'gunicorn' with gevent workers to run properly
    # For local testing, this is a simplified setup.
    app.run(host='0.0.0.0', port=port)
