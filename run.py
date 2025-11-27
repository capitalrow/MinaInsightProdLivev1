"""
Mina Development Server - WebSocket-enabled
Properly initializes eventlet for full WebSocket support.
"""
import eventlet
eventlet.monkey_patch()

from app import app, socketio

if __name__ == "__main__":
    print("🚀 Starting Mina with WebSocket support...")
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True,
        log_output=True
    )
