from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import os
from ultralytics import YOLO

app = FastAPI()

PLACEHOLDER_PATH = "placeholder.jpg"
IMAGE_PATH = "image.jpg"

# Initialize YOLO model with optimized settings
model = YOLO('yolo11n.pt')  # Latest YOLO11 model - 22% fewer parameters than YOLOv8
model.overrides['verbose'] = False  # Reduce logging overhead


def is_valid_image(image_bytes):
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        # Decode image
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img is not None
    except Exception as e:
        print("image invalid:", e)
        return False

def mjpeg_generator():
    while True:
        try:
            with open(IMAGE_PATH, "rb") as f:
                image_bytes = f.read()
            
            # Convert bytes to numpy array and decode with OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Perform object detection with optimized parameters
            results = model(img, conf=0.25, iou=0.45, verbose=False, imgsz=640)
            
            # Use YOLO's built-in plot method for visualization
            annotated_img = results[0].plot()
            
            # Encode back to JPEG
            _, img_encoded = cv2.imencode('.jpg', annotated_img)
            img_bytes = img_encoded.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
        except Exception as e:
            print("encountered an exception: ", e)
            if os.path.exists(PLACEHOLDER_PATH):
                try:
                    with open(PLACEHOLDER_PATH, "rb") as f:
                        image_bytes = f.read()
                    
                    # Convert bytes to numpy array and decode with OpenCV
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    img_bytes = img.tobytes()
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
                except Exception as e2:
                    print("placeholder error:", e2)
            import time
            time.sleep(0.1)  # Increased sleep time to reduce CPU load

@app.get("/")
def index():
    return StreamingResponse(mjpeg_generator(), media_type='multipart/x-mixed-replace; boundary=frame')

async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
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
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_handler(websocket)

# For running both FastAPI and WebSocket server in one process
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)