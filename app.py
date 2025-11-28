from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    def __init__(self):
        self.agents = {}       # agent_id: WebSocket
        self.customers = {}    # customer_id: WebSocket
        self.sessions = {}     # customer_id: agent_id

    async def connect(self, role, user_id, websocket: WebSocket):
        await websocket.accept()
        if role == "agent":
            self.agents[user_id] = websocket
        else:
            self.customers[user_id] = websocket

            # Cari agent yang tersedia
            for agent_id, agent_ws in self.agents.items():
                if agent_id not in self.sessions.values():
                    self.sessions[user_id] = agent_id
                    await agent_ws.send_json({"type": "new_customer", "customer_id": user_id})
                    break

    async def relay(self, sender_id, message: dict, role):
        target_id = ""
        if role == "customer":
            target_id = self.sessions.get(sender_id)
            target_ws = self.agents.get(target_id)
        else:
            
            target_id = message.get("to")
            target_ws = self.customers.get(target_id)
        
        if target_ws:
            await target_ws.send_json(message)

    def disconnect(self, role, user_id):
        if role == "agent":
            self.agents.pop(user_id, None)
        else:
            self.customers.pop(user_id, None)
            if user_id in self.sessions:
                self.sessions.pop(user_id)

manager = ConnectionManager()

@app.websocket("/ws/{role}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, role: str, user_id: str):
    await manager.connect(role, user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.relay(user_id, data, role)
    except WebSocketDisconnect:
        manager.disconnect(role, user_id)
