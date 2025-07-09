# ====================================================================
# IoT 이미지 스트리밍 서버 (FastAPI + YOLO 객체 감지)
# ====================================================================
# 
# 주요 기능:
# 1. 웹소켓으로 IoT 디바이스에서 실시간 이미지 수신
# 2. YOLO11을 사용한 실시간 객체 감지
# 3. 감지 결과를 MJPEG 형식으로 웹 스트리밍
# 4. 에러 시 placeholder 이미지로 자동 대체
#
# 사용법:
# - 서버 실행: python fastapiMain_opencv.py
# - 웹 스트리밍: http://localhost:3001
# - 웹소켓 연결: ws://localhost:3001/ws
# ====================================================================

import asyncio
from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK
import cv2                                    # OpenCV - 이미지 처리
import numpy as np                           # 이미지 데이터 배열 처리
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
import os
import threading
from ultralytics import YOLO                # YOLO 객체 감지 라이브러리

# FastAPI 앱 생성
app = FastAPI()

# 이미지 파일 경로 설정
PLACEHOLDER_PATH = "placeholder.jpg"        # 기본 이미지 (에러 시 표시)
IMAGE_PATH = "image.jpg"                    # 실시간 이미지 저장 경로

# YOLO 모델 초기화 (최적화된 설정)
model = YOLO('yolo11n.pt')                  # YOLO11 nano 모델 (가장 빠른 버전)
model.overrides['verbose'] = False           # 로깅 출력 최소화로 성능 향상


def is_valid_image(image_bytes):
    """이미지 바이트 데이터 유효성 검사
    
    Args:
        image_bytes: 이미지 바이트 데이터
        
    Returns:
        bool: 유효한 이미지인지 여부
    """
    try:
        # 바이트 데이터를 numpy 배열로 변환
        nparr = np.frombuffer(image_bytes, np.uint8)
        # OpenCV로 이미지 디코딩 시도
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img is not None
    except Exception as e:
        print("이미지 유효성 검사 실패:", e)
        return False


def mjpeg_generator():
    """MJPEG 스트리밍용 이미지 생성기
    
    실시간으로 이미지를 읽어서 YOLO 객체 감지를 수행한 후
    MJPEG 형식으로 스트리밍하는 제너레이터
    """
    while True:
        try:
            # 실시간 이미지 파일 읽기
            with open(IMAGE_PATH, "rb") as f:
                image_bytes = f.read()
            
            # 바이트 데이터를 numpy 배열로 변환 후 OpenCV로 디코딩
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # YOLO 객체 감지 수행 (최적화된 파라미터)
            # conf=0.25: 신뢰도 25% 이상인 객체만 감지
            # iou=0.45: 중복 박스 제거 임계값
            # imgsz=640: 입력 이미지 크기 고정으로 성능 향상
            results = model(img, conf=0.25, iou=0.45, verbose=False, imgsz=640)
            
            # YOLO 내장 시각화 메서드로 박스와 라벨 자동 그리기
            # 각 클래스별 다른 색상, 신뢰도 표시, 최적화된 렌더링
            annotated_img = results[0].plot()
            
            # 처리된 이미지를 JPEG로 인코딩
            _, img_encoded = cv2.imencode('.jpg', annotated_img)
            img_bytes = img_encoded.tobytes()
            
            # MJPEG 스트리밍 형식으로 반환
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
                   
        except Exception as e:
            print("이미지 처리 중 오류 발생:", e)
            
            # 오류 발생 시 placeholder 이미지로 대체
            if os.path.exists(PLACEHOLDER_PATH):
                try:
                    with open(PLACEHOLDER_PATH, "rb") as f:
                        image_bytes = f.read()
                    
                    # placeholder 이미지도 동일하게 처리
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    # placeholder에도 객체 감지 적용
                    results = model(img, conf=0.25, iou=0.45, verbose=False, imgsz=640)
                    
                    # YOLO 내장 시각화 적용
                    annotated_img = results[0].plot()
                    
                    # JPEG로 인코딩 후 스트리밍
                    _, img_encoded = cv2.imencode('.jpg', annotated_img)
                    img_bytes = img_encoded.tobytes()
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
                           
                except Exception as e2:
                    print("placeholder 이미지 처리 오류:", e2)
                    
            import time
            time.sleep(0.1)  # CPU 부하 감소를 위한 대기시간


@app.get("/")
def index():
    """메인 페이지 - MJPEG 스트리밍 엔드포인트
    
    브라우저에서 localhost:3001에 접속하면
    실시간 객체 감지가 적용된 영상을 볼 수 있음
    """
    return StreamingResponse(mjpeg_generator(), media_type='multipart/x-mixed-replace; boundary=frame')


async def ws_handler(websocket: WebSocket):
    """웹소켓 메시지 처리 핸들러
    
    IoT 디바이스에서 전송되는 이미지 데이터를 받아서
    유효성 검사 후 파일로 저장
    
    Args:
        websocket: 웹소켓 연결 객체
    """
    await websocket.accept()  # 웹소켓 연결 수락
    
    try:
        while True:
            # 웹소켓 메시지 수신 대기
            message = await websocket.receive()
            
            # 연결 종료 메시지 체크
            if message["type"] == "websocket.disconnect":
                break
                
            # 바이너리 데이터 (이미지) 처리
            if "bytes" in message and message["bytes"] is not None:
                data = message["bytes"]
                print(f"받은 이미지 크기: {len(data)} bytes")
                
                # 최소 크기 체크 (5KB 이상인 이미지만 처리)
                if len(data) > 5000:
                    # 이미지 유효성 검사
                    if is_valid_image(data):
                        # 유효한 이미지를 파일로 저장
                        with open(IMAGE_PATH, "wb") as f:
                            f.write(data)
                        print("이미지 저장 완료")
                    else:
                        print("유효하지 않은 이미지 데이터")
                else:
                    print("이미지 크기가 너무 작음")
                    
            # 텍스트 메시지 처리
            elif "text" in message and message["text"] is not None:
                print("텍스트 메시지 수신:", message["text"])
                
            print()  # 로그 구분용 빈 줄
            
    except WebSocketDisconnect:
        print("웹소켓 연결이 끊어짐")
    except ConnectionClosedOK:
        print("웹소켓 연결이 정상적으로 종료됨")
    except Exception as e:
        print(f"웹소켓 처리 중 오류 발생: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """웹소켓 엔드포인트
    
    IoT 디바이스가 ws://localhost:3001/ws로 연결하여
    실시간 이미지 데이터를 전송할 수 있음
    """
    await ws_handler(websocket)


# 서버 실행 부분
if __name__ == "__main__":
    import uvicorn
    print("=== IoT 이미지 스트리밍 서버 시작 ===")
    print("- 웹 스트리밍: http://localhost:3001")
    print("- 웹소켓 연결: ws://localhost:3001/ws")
    print("- YOLO 모델: yolo11n.pt (객체 감지 활성화)")
    print("- 지원 기능: 실시간 객체 감지, MJPEG 스트리밍")
    
    # FastAPI 서버 시작
    # host="0.0.0.0": 모든 네트워크 인터페이스에서 접근 가능
    # port=3001: 포트 3001에서 서버 실행
    uvicorn.run(app, host="0.0.0.0", port=3001)