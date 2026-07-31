import json
import os
import threading
import time
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PIL import Image


EXTERNAL_OUTPUT_NONE = "None"
EXTERNAL_OUTPUT_G2 = "Even G2"
EXTERNAL_OUTPUT_CHOICES = [EXTERNAL_OUTPUT_NONE, EXTERNAL_OUTPUT_G2]

G2_SUPPORTED_ORDER_TYPES = ["Anomaly", "Malignancy", "System", "Diagnosis"]
G2_ORDER_TYPE_LABELS = {
    "Anomaly": "Anomaly",
    "Malignancy": "Malignancy",
    "System": "Bethesda",
    "Diagnosis": "Diagnosis",
}

AVAILABLE_SPECIMENS = ["cervix"]


class HandsfreeBridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._output_target = EXTERNAL_OUTPUT_NONE
        self._specimen = AVAILABLE_SPECIMENS[0]
        self._order_type = "System"
        self._latest_image = None
        self._pending_command = None
        self._pending_capture = None
        self._next_command_id = 1
        self._settings_revision = 0
        self._pending_ui_settings = None
        self._last_g2_seen_at = None
        self._state_revision = 0
        self._status = "disabled"
        self._result = None
        self._error = None

    def reset(self):
        with self._lock:
            self._output_target = EXTERNAL_OUTPUT_NONE
            self._specimen = AVAILABLE_SPECIMENS[0]
            self._order_type = "System"
            self._latest_image = None
            self._pending_command = None
            self._pending_capture = None
            self._next_command_id = 1
            self._settings_revision = 0
            self._pending_ui_settings = None
            self._last_g2_seen_at = None
            self._state_revision = 0
            self._status = "disabled"
            self._result = None
            self._error = None

    def set_output_target(self, output_target):
        if output_target not in EXTERNAL_OUTPUT_CHOICES:
            raise ValueError(f"Unsupported external output: {output_target}")

        with self._lock:
            self._output_target = output_target
            self._pending_command = None
            self._pending_capture = None
            self._result = None
            self._error = None
            self._status = "ready" if output_target == EXTERNAL_OUTPUT_G2 else "disabled"
            self._state_revision += 1

    def set_latest_image(self, image):
        if image is None:
            return
        if not isinstance(image, Image.Image):
            return
        with self._lock:
            self._latest_image = image.convert("RGB").copy()

    def get_latest_image(self):
        with self._lock:
            if self._latest_image is None:
                return None
            return self._latest_image.copy()

    def update_settings(self, specimen, order_type, source="mac"):
        if specimen not in AVAILABLE_SPECIMENS:
            raise ValueError(f"Unsupported specimen: {specimen}")
        if order_type not in G2_SUPPORTED_ORDER_TYPES and order_type != "Full":
            raise ValueError(f"Unsupported question type: {order_type}")
        if source == "g2" and order_type == "Full":
            raise ValueError("Full is not available on G2")

        with self._lock:
            changed = specimen != self._specimen or order_type != self._order_type
            self._specimen = specimen
            self._order_type = order_type
            if source == "g2" and changed:
                self._settings_revision += 1
                self._pending_ui_settings = {
                    "specimen": specimen,
                    "order_type": order_type,
                }
            if changed:
                self._state_revision += 1

    def enqueue_analyze(self, specimen, order_type):
        if specimen not in AVAILABLE_SPECIMENS:
            raise ValueError(f"Unsupported specimen: {specimen}")
        if order_type not in G2_SUPPORTED_ORDER_TYPES:
            raise ValueError(f"Unsupported G2 question type: {order_type}")

        with self._lock:
            if self._output_target != EXTERNAL_OUTPUT_G2:
                raise PermissionError("Even G2 output is disabled in CYTOLONE")
            if self._pending_command is not None or self._status == "analyzing":
                raise RuntimeError("CYTOLONE is already processing a G2 command")

            command = {
                "id": self._next_command_id,
                "action": "analyze",
                "specimen": specimen,
                "order_type": order_type,
            }
            self._next_command_id += 1
            self._specimen = specimen
            self._order_type = order_type
            self._settings_revision += 1
            self._pending_ui_settings = {
                "specimen": specimen,
                "order_type": order_type,
            }
            self._pending_command = command
            self._pending_capture = None
            self._status = "queued"
            self._result = None
            self._error = None
            self._state_revision += 1
            return deepcopy(command)

    def pop_command(self):
        with self._lock:
            command = self._pending_command
            self._pending_command = None
            self._pending_capture = None
            return deepcopy(command)

    def submit_capture(self, command_id, image_data):
        if image_data is not None and not (
            isinstance(image_data, str) and image_data.startswith("data:image/")
        ):
            raise ValueError("Captured frame must be an image data URL or null")

        with self._lock:
            if self._pending_command is None:
                raise ValueError("No G2 analyze command is waiting for a frame")
            if command_id != self._pending_command["id"]:
                raise ValueError("Captured frame does not match the pending command")
            self._pending_capture = {
                "command_id": command_id,
                "image": image_data,
            }

    def pop_ready_command(self):
        with self._lock:
            if self._pending_command is None or self._pending_capture is None:
                return None, None
            command = self._pending_command
            captured_image = self._pending_capture["image"]
            self._pending_command = None
            self._pending_capture = None
            return deepcopy(command), captured_image

    def pop_ui_settings(self):
        with self._lock:
            settings = self._pending_ui_settings
            self._pending_ui_settings = None
            return deepcopy(settings)

    def begin_analysis(self, command_id):
        with self._lock:
            self._status = "analyzing"
            self._error = None
            self._state_revision += 1
            return command_id

    def publish_result(self, specimen, order_type, label_probs):
        sorted_scores = sorted(label_probs.items(), key=lambda item: item[1], reverse=True)
        result = {
            "specimen": specimen,
            "order_type": order_type,
            "order_type_label": G2_ORDER_TYPE_LABELS.get(order_type, order_type),
            "scores": [
                {
                    "label": label,
                    "probability": float(probability),
                    "percentage": round(float(probability) * 100, 1),
                }
                for label, probability in sorted_scores
            ],
        }

        with self._lock:
            if self._output_target != EXTERNAL_OUTPUT_G2:
                return None
            self._status = "result"
            self._result = result
            self._error = None
            self._state_revision += 1
            return deepcopy(result)

    def publish_error(self, code, message):
        with self._lock:
            self._status = "error"
            self._error = {"code": code, "message": message}
            self._result = None
            self._state_revision += 1

    def dismiss_result(self):
        with self._lock:
            self._status = "ready" if self._output_target == EXTERNAL_OUTPUT_G2 else "disabled"
            self._result = None
            self._error = None
            self._state_revision += 1

    def mark_g2_seen(self):
        with self._lock:
            self._last_g2_seen_at = time.monotonic()

    def connection_status(self):
        with self._lock:
            if self._output_target != EXTERNAL_OUTPUT_G2:
                return "Even G2: disabled"
            if self._last_g2_seen_at is None:
                return "Even G2: waiting"
            if time.monotonic() - self._last_g2_seen_at <= 3:
                return "Even G2: connected"
            return "Even G2: disconnected"

    def snapshot(self, mark_seen=False):
        if mark_seen:
            self.mark_g2_seen()

        with self._lock:
            return {
                "enabled": self._output_target == EXTERNAL_OUTPUT_G2,
                "output_target": self._output_target,
                "status": self._status,
                "revision": self._state_revision,
                "settings_revision": self._settings_revision,
                "settings": {
                    "specimen": self._specimen,
                    "order_type": self._order_type,
                },
                "pending_command_id": (
                    self._pending_command["id"]
                    if self._pending_command is not None
                    else None
                ),
                "available": {
                    "specimens": list(AVAILABLE_SPECIMENS),
                    "order_types": [
                        {"value": value, "label": G2_ORDER_TYPE_LABELS[value]}
                        for value in G2_SUPPORTED_ORDER_TYPES
                    ],
                },
                "result": deepcopy(self._result),
                "error": deepcopy(self._error),
            }


handsfree_bridge = HandsfreeBridge()


class HandsfreeRequestHandler(BaseHTTPRequestHandler):
    server_version = "CYTOLONEHandsfree/0.1"

    def log_message(self, format, *args):
        return

    def _send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        if self.path == "/api/state":
            self._send_json(200, handsfree_bridge.snapshot(mark_seen=True))
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        try:
            payload = self._read_json()
            if self.path == "/api/settings":
                handsfree_bridge.mark_g2_seen()
                handsfree_bridge.update_settings(
                    payload.get("specimen"),
                    payload.get("order_type"),
                    source="g2",
                )
                self._send_json(200, handsfree_bridge.snapshot())
                return
            if self.path == "/api/analyze":
                handsfree_bridge.mark_g2_seen()
                command = handsfree_bridge.enqueue_analyze(
                    payload.get("specimen"),
                    payload.get("order_type"),
                )
                self._send_json(202, {"command": command})
                return
            if self.path == "/api/frame":
                handsfree_bridge.mark_g2_seen()
                handsfree_bridge.submit_capture(
                    payload.get("command_id"),
                    payload.get("image"),
                )
                self._send_json(202, {"status": "captured"})
                return
            if self.path == "/api/dismiss":
                handsfree_bridge.mark_g2_seen()
                handsfree_bridge.dismiss_result()
                self._send_json(200, handsfree_bridge.snapshot())
                return
            self._send_json(404, {"error": "not_found"})
        except PermissionError as error:
            self._send_json(409, {"error": "g2_disabled", "message": str(error)})
        except RuntimeError as error:
            self._send_json(409, {"error": "busy", "message": str(error)})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": "invalid_request", "message": str(error)})
        except Exception as error:
            self._send_json(500, {"error": "internal_error", "message": str(error)})


class HandsfreeServer:
    def __init__(self, host="127.0.0.1", port=None):
        self.host = host
        self.port = (
            int(os.environ.get("CYTOLONE_HANDSFREE_PORT", "8765"))
            if port is None
            else port
        )
        self._server = None
        self._thread = None

    def start(self):
        if self._server is not None:
            return
        self._server = ThreadingHTTPServer((self.host, self.port), HandsfreeRequestHandler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
