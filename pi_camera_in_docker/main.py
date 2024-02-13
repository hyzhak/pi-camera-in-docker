#!/usr/bin/python3

# Mostly copied from https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# Run this script, then point a web browser at http:<this-ip-address>:8000
# Note: needs simplejpeg to be installed (pip3 install simplejpeg).

import argparse
import cv2
from http import server
import io
import logging
import numpy as np
import socketserver
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

# Parse command line arguments
parser = argparse.ArgumentParser(description="Picamera2 MJPEG streaming demo with options")
parser.add_argument("--resolution", type=str, help="Video resolution in WIDTHxHEIGHT format (default: 640x480)", default="640x480")
parser.add_argument("--edge_detection", action="store_true", help="Enable edge detection")
args = parser.parse_args()

# Parse resolution
resolution = tuple(map(int, args.resolution.split('x')))

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="{width}" height="{height}" />
</body>
</html>
""".format(width=resolution[0], height=resolution[1])


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        if args.edge_detection:
            # Convert the image buffer to a numpy array
            img_array = np.frombuffer(buf, dtype=np.uint8)
            # Decode the image array into an image
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            # Apply edge detection
            edges = cv2.Canny(img, 100, 200)
            # Encode the result back to JPEG
            _, buf = cv2.imencode('.jpg', edges)
            buf = buf.tobytes()
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": resolution}))
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()
