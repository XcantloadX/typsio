import socketio
import uvicorn
from typsio import setup_rpc
from .api_defs import rpc_registry

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio)

# 将 API 定义附加到服务器
setup_rpc(sio, rpc_registry)

@sio.event
async def connect(sid, environ):
    print(f'Client connected: {sid}')

if __name__ == "__main__":
    uvicorn.run("my_app.server:app", host="0.0.0.0", port=8000, reload=True)
