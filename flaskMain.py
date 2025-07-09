import asyncio
from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from flask import Flask, Response
import os

app = Flask(__name__)

def is_valid_image(image_bytes):
    try:
        Image.open(BytesIO(image_bytes))
        return True
    except UnidentifiedImageError:
        print("image invalid")
        return False

def get_image():
    while True:
        try:
            with open("image.jpg", "rb") as f:
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
            # Always serve placeholder if available, to prevent browser freezing
            if os.path.exists("placeholder.jpg"):
                try:
                    with open("placeholder.jpg", "rb") as f:
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
        # No continue here, always yield something to browser

@app.route('/')
def index():
    return Response(get_image(), mimetype='multipart/x-mixed-replace; boundary=frame')

async def handler(websocket):
    try:
        async for message in websocket:
            print(len(message))
            if len(message) > 5000:
                if is_valid_image(message):
                    with open("image.jpg", "wb") as f:
                        f.write(message)
            print()
    except ConnectionClosedOK:
        print("WebSocket connection closed cleanly.")

async def main():
    async with serve(handler, "0.0.0.0", 3001):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    import threading
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', debug=False, threaded=True), daemon=True)
    flask_thread.start()
    asyncio.run(main())