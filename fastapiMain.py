import asyncio
from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
import os
import threading

app = FastAPI()

PLACEHOLDER_PATH = "placeholder.jpg"
IMAGE_PATH = "image.jpg"


def is_valid_image(image_bytes):
    try:
        Image.open(BytesIO(image_bytes))
        return True
    except UnidentifiedImageError:
        print("image invalid")
        return False

def mjpeg_generator():
    while True:
        try:
            with open(IMAGE_PATH, "rb") as f:
                image_bytes = f.read()
            image = Image.open(BytesIO(image_bytes))
            img_io = BytesIO()
            image.save(img_io, 'JPEG')
            img_io.seek(0)
            img_bytes = img_io.read()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
        except Exception as e:
            print("encountered an exception: ", e)
            if os.path.exists(PLACEHOLDER_PATH):
                try:
                    with open(PLACEHOLDER_PATH, "rb") as f:
                        image_bytes = f.read()
                    image = Image.open(BytesIO(image_bytes))
                    img_io = BytesIO()
                    image.save(img_io, 'JPEG')
                    img_io.seek(0)
                    img_bytes = img_io.read()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
                except Exception as e2:
                    print("placeholder error:", e2)
            import time
            time.sleep(0.1)

@app.get("/")
def index():
    return StreamingResponse(mjpeg_generator(), media_type='multipart/x-mixed-replace; boundary=frame')

async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"] is not None:
                data = message["bytes"]
                print(len(data))
                if len(data) > 5000:
                    if is_valid_image(data):
                        with open(IMAGE_PATH, "wb") as f:
                            f.write(data)
            elif "text" in message and message["text"] is not None:
                print("Text message:", message["text"])
            print()
    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except ConnectionClosedOK:
        print("WebSocket connection closed cleanly.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_handler(websocket)

# For running both FastAPI and WebSocket server in one process
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
