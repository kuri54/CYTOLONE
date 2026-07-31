import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from CYTOLONE.handsfree import (
    EXTERNAL_OUTPUT_G2,
    HandsfreeBridge,
    HandsfreeServer,
    handsfree_bridge,
)


class HandsfreeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = HandsfreeBridge()

    def test_g2_commands_are_rejected_until_output_is_enabled(self):
        with self.assertRaises(PermissionError):
            self.bridge.enqueue_analyze("cervix", "System")

        self.bridge.set_output_target(EXTERNAL_OUTPUT_G2)
        command = self.bridge.enqueue_analyze("cervix", "System")
        self.assertEqual(self.bridge.pop_ready_command(), (None, None))

        frame = "data:image/png;base64,AA=="
        self.bridge.submit_capture(command["id"], frame)
        ready_command, captured_frame = self.bridge.pop_ready_command()
        self.assertEqual(ready_command, command)
        self.assertEqual(captured_frame, frame)

    def test_full_remains_mac_only(self):
        self.bridge.update_settings("cervix", "Full", source="mac")

        with self.assertRaises(ValueError):
            self.bridge.update_settings("cervix", "Full", source="g2")

    def test_g2_settings_are_available_for_mac_ui_sync(self):
        self.bridge.update_settings("cervix", "Diagnosis", source="g2")

        self.assertEqual(
            self.bridge.pop_ui_settings(),
            {"specimen": "cervix", "order_type": "Diagnosis"},
        )
        self.assertIsNone(self.bridge.pop_ui_settings())

    def test_result_contains_all_scores_sorted_as_percentages_without_llm_fields(self):
        self.bridge.set_output_target(EXTERNAL_OUTPUT_G2)
        result = self.bridge.publish_result(
            "cervix",
            "System",
            {"NILM": 0.12, "HSIL": 0.81, "LSIL": 0.07},
        )

        self.assertEqual([score["label"] for score in result["scores"]], ["HSIL", "NILM", "LSIL"])
        self.assertEqual([score["percentage"] for score in result["scores"]], [81.0, 12.0, 7.0])
        self.assertNotIn("comments", result)
        self.assertNotIn("llm", result)


class HandsfreeServerTests(unittest.TestCase):
    def setUp(self):
        handsfree_bridge.reset()
        self.server = HandsfreeServer(port=0)
        self.server.start()
        self.base_url = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()
        handsfree_bridge.reset()

    def request_json(self, path, method="GET", payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            method=method,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_state_never_exposes_an_llm_payload(self):
        handsfree_bridge.set_output_target(EXTERNAL_OUTPUT_G2)
        handsfree_bridge.publish_result("cervix", "Anomaly", {"Normal": 0.2, "Anomaly": 0.8})

        status, state = self.request_json("/api/state")

        self.assertEqual(status, 200)
        self.assertNotIn("comments", json.dumps(state).lower())
        self.assertNotIn("llm", json.dumps(state).lower())

    def test_analyze_endpoint_is_gated_by_external_output(self):
        with self.assertRaises(HTTPError) as context:
            self.request_json(
                "/api/analyze",
                method="POST",
                payload={"specimen": "cervix", "order_type": "System"},
            )

        self.assertEqual(context.exception.code, 409)

        handsfree_bridge.set_output_target(EXTERNAL_OUTPUT_G2)
        status, response = self.request_json(
            "/api/analyze",
            method="POST",
            payload={"specimen": "cervix", "order_type": "System"},
        )

        self.assertEqual(status, 202)
        self.assertEqual(response["command"]["action"], "analyze")

        _, state = self.request_json("/api/state")
        command_id = response["command"]["id"]
        self.assertEqual(state["pending_command_id"], command_id)

        frame_status, _ = self.request_json(
            "/api/frame",
            method="POST",
            payload={"command_id": command_id, "image": None},
        )
        self.assertEqual(frame_status, 202)
        ready_command, captured_image = handsfree_bridge.pop_ready_command()
        self.assertEqual(ready_command["id"], command_id)
        self.assertIsNone(captured_image)


if __name__ == "__main__":
    unittest.main()
