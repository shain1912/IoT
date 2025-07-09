# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an IoT image streaming server with two implementation variants:
- **FastAPI implementation** (`fastapiMain.py`) - Modern async web framework with WebSocket support
- **Flask + WebSocket implementation** (`flaskMain.py`) - Traditional web framework with separate WebSocket server

Both implementations serve the same core functionality: receive images via WebSocket, stream them as MJPEG video feed via HTTP, and provide fallback to placeholder images when the main image is unavailable.

## Key Architecture

### Core Components
- **Image Reception**: WebSocket endpoint receives image data from IoT devices
- **Image Validation**: `is_valid_image()` function validates incoming image data using PIL
- **MJPEG Streaming**: Continuous HTTP stream serving images in MJPEG format
- **Fallback System**: Automatic fallback to `placeholder.jpg` when `image.jpg` is unavailable

### Data Flow
1. IoT devices send image data via WebSocket (`/ws` endpoint)
2. Server validates and saves images as `image.jpg`
3. HTTP endpoint (`/`) continuously streams images as MJPEG
4. If main image fails, server falls back to `placeholder.jpg`

## Running the Applications

### FastAPI Version
```bash
python fastapiMain.py
```
Runs on `0.0.0.0:3001` with both HTTP and WebSocket on same server

### Flask Version
```bash
python flaskMain.py
```
Runs Flask on HTTP and separate WebSocket server, both on `0.0.0.0:3001`

## Key Technical Details

### Image Handling
- Images must be >5000 bytes to be processed
- All images are validated using PIL before saving
- Images are converted to JPEG format for streaming
- Placeholder fallback prevents browser freezing during image failures

### WebSocket Protocol
- **FastAPI**: Uses FastAPI WebSocket with proper connection handling
- **Flask**: Uses websockets library with async handler
- Both accept binary image data and text messages

### Error Handling
- Graceful WebSocket disconnection handling
- Image validation prevents invalid data from being saved
- Automatic fallback to placeholder image on any streaming errors
- Exception logging for debugging

## Dependencies
Both implementations require:
- `fastapi` and `uvicorn` (FastAPI version)
- `flask` (Flask version)
- `websockets` (Flask version)
- `PIL` (Pillow) for image processing

## File Structure
- `fastapiMain.py` - FastAPI implementation
- `flaskMain.py` - Flask + WebSocket implementation
- `image.jpg` - Current image from IoT device
- `placeholder.jpg` - Fallback image for error states