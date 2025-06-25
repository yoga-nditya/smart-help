from fastapi import FastAPI, WebSocket, Query, WebSocketDisconnect,File, UploadFile, Request,Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse,HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import speech_recognition as sr

import asyncio
import json
from model import *
from gtts import gTTS
import os
import uuid
import subprocess
import hashlib
from datetime import datetime
from controller import *

client_agent = "0J2V8eVuDdl"
secretekey_agent = "V42IoWXAas5mdfSole5Q6RJFZHQ7dhci"


listcors = ['https://localhost','https://webrtc.lippomallpuri.com','http://localhost','http://10.141.42.31','https://10.141.42.31']
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=listcors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

rooms = {}          # room_id: [WebSocket, ...]
room_status = {}    # room_id: "waiting" | "active"
room_clients = set()

@app.websocket("/ws/available-rooms")
async def available_rooms_ws(
    websocket: WebSocket,
    client_id: str = Query(...),
    client_secret: str = Query(...)
):
    if not (client_id == client_agent and client_secret == secretekey_agent):
        
        hasil = get_user(clientid=client_id, secretekey=client_secret)
        if not hasil:
            print("❌ Rejected: get_user() failed for client:", client_id)
            await websocket.close(code=1008)
            return
    await websocket.accept()
    print(f"Client {client_id} connected")

    monitor_task = asyncio.create_task(monitor_status(websocket))

    try:
        while True:
            data = await websocket.receive_text()
            print(f"Client sent: {data}")
            try:
                payload = json.loads(data)
                msg_type = payload.get("type")
                room_id = str(payload.get("room")) if payload.get("room") else None

                if msg_type == "room_join":
                    room_id = str(payload["UserRoleId"])

                    # Buat room jika belum ada
                    if room_id not in rooms:
                        rooms[room_id] = []
                        room_status[room_id] = "waiting"

                    # Masukkan client ke dalam room
                    if websocket not in rooms[room_id]:
                        rooms[room_id].append(websocket)
                    
                    if client_id == client_agent:
                        print("agent join")
                        update_chatuser(roileid=int(room_id), status=10)  # ✅ Agent join
                        print(update_chatuser)

                    # Ubah status jika sudah 2 user
                    if len(rooms[room_id]) >= 2:
                        room_status[room_id] = "active"
                        update_chatuser(roileid=int(room_id), status=20) 

                    # 🔴 Hentikan monitor_status
                    if not monitor_task.done():
                        monitor_task.cancel()

                    print(f"Client {client_id} joined room {room_id}")

                elif msg_type in ("offer", "answer", "candidate", "chat"):
                    if room_id and room_id in rooms:
                        for client in rooms[room_id]:
                            if client != websocket:
                                await client.send_json(payload)

            except json.JSONDecodeError:
                print("❌ Invalid JSON from client:", data)

    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected")
        monitor_task.cancel()

        for r_id in list(rooms.keys()):
            if websocket in rooms[r_id]:
                rooms[r_id].remove(websocket)

                if not rooms[r_id]:
                    # ✅ Semua keluar → hapus room
                    del rooms[r_id]
                    room_status.pop(r_id, None)
                    #update_chatuser(roileid=int(r_id), status=10)
                    print(f"Room {r_id} kosong. Status fallback 10")
                else:
                    # Cek apakah agent masih ada di room
                    agent_still_inside = any(
                        c != websocket and client_agent == client_id
                        for c in rooms[r_id]
                    )

                    if client_id == client_agent:
                        # ✅ Agent keluar → status 30
                        update_chatuser(roileid=int(r_id), status=30)
                        print(f"Agent keluar dari room {r_id}. Status jadi 30")
                        for client in rooms[r_id]:
                            try:
                                await client.send_json({
                                    "type": "room_close",
                                    "status": "agent_disconnected",
                                    "message": "Agent telah keluar dari room. Silakan tunggu agent lain."
                                })
                            except Exception as e:
                                print(f"❌ Gagal kirim notifikasi ke client: {e}")
                    else:
                        if not agent_still_inside:
                            # ✅ Client keluar & agent juga sudah keluar → status 30
                            update_chatuser(roileid=int(r_id), status=30)
                            print(f"Client keluar dan agent tidak ada. Status 30")
                        else:
                            # ✅ Client keluar, agent masih ada → status 10
                            room_status[r_id] = "waiting"
                            update_chatuser(roileid=int(r_id), status=10)
                            print(f"Client keluar, agent masih di room {r_id}. Status 10")

                        # Notifikasi ke agent yang tersisa
                        for client in rooms[r_id]:
                            try:
                                await client.send_json({
                                    "type": "room_status",
                                    "status": "waiting"
                                })
                            except Exception as e:
                                print(f"❌ Gagal kirim status ke client: {e}")


async def monitor_status(websocket: WebSocket):
    try:
        while True:
            await asyncio.sleep(3)
            cek_status = get_ready(10)
            if cek_status:
                cek_status = json.loads(cek_status)
                await websocket.send_json({
                    "type": "room_ready",
                    **cek_status
                })
    except Exception as e:
        print(f"Monitor error: {e}")
        await websocket.close()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sendtext/{text}")
async def get_sendtext (text : str,client_key: str = Header(..., alias="client-key"),
    signature_key: str = Header(..., alias="signature-key"),
    requesttimestamp: str = Header(..., alias="requesttimestamp")):
    if not is_valid_signature_v2(client_key, signature_key, requesttimestamp):
        return JSONResponse(status_code=403, content={"code": 1, "answer": "Unauthorized"})
    try:
        tenant_data = load_tenant_data_from_api()
        corpus, metadata = build_corpus(tenant_data)
        answer = jawab_pertanyaan(text, corpus, metadata, model)
        return JSONResponse({"code": 0 ,"answer": answer})
    except Exception as e:
        return JSONResponse({"code": 1 ,"answer": str(e)})


# @app.post("/upload-audio/")
# async def upload_audio(file: UploadFile = File(...)):
#     try:
#         # Simpan file
#         temp_filename = f"static/audio/temp_{uuid.uuid4().hex}.webm"
#         with open(temp_filename, "wb") as f:
#             f.write(await file.read())
#          # Konversi ke .wav PCM 16-bit 16000 Hz mono
#         wav_filename = f"static/audio/temp_{uuid.uuid4().hex}.wav"
#         subprocess.run([
#             "ffmpeg", "-y", "-i", temp_filename,
#             "-ar", "16000", "-ac", "1", "-f", "wav", wav_filename
#         ], check=True)
#         # Speech to text
#         recognizer = sr.Recognizer()
#         with sr.AudioFile(wav_filename) as source:
#             audio_data = recognizer.record(source)
#             question_text = recognizer.recognize_google(audio_data, language="id-ID")

#         os.remove(temp_filename)
#         os.remove(wav_filename)
#         print("User:", question_text)

#         answer = find_best_answer(question_text)

#         # Text to Speech
#         tts = gTTS(text=answer, lang='id')
#         audio_file = f"static/audio/jawaban_{uuid.uuid4().hex}.mp3"
#         tts.save(audio_file)

#         return JSONResponse({"answer": answer, "audio_url": f"/{audio_file}"})

#     except Exception as e:
#         print(e)
#         return JSONResponse(content={"error": str(e)}, status_code=500)

# @app.get("/{filename}")
# async def get_audio(filename: str):
#     return FileResponse(filename)