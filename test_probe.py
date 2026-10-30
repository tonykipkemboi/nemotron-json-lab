import json
import unittest
from types import SimpleNamespace

import httpx
from openai import OpenAI

from probe import inspect_response, request_body, sdk_request, validate_base


def response(content=None, finish="stop", **fields):
    return {"choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": content, **fields}}]}


VALID = '{"issue_type":"bug","urgency":"low","summary":"Export unavailable"}'


class ProbeTests(unittest.TestCase):
    def test_pr79_fallback_recovers_partial_reasoning_but_does_not_complete_answer(self):
        message = SimpleNamespace(content=None, reasoning="Partial thought")
        # Exact expression from PR #79.
        text = message.content or getattr(message, "reasoning", None)
        self.assertEqual(text, "Partial thought")
        self.assertEqual(inspect_response(response(None, "length", reasoning=text))["status"], "truncated")

    def test_valid_json_is_validated(self):
        self.assertEqual(inspect_response(response(VALID))["status"], "valid_json")

    def test_valid_looking_json_still_rejected_when_truncated(self):
        self.assertEqual(inspect_response(response(VALID, "length"))["status"], "truncated")

    def test_reasoning_is_never_used_as_json(self):
        result = inspect_response(response(None, reasoning=VALID))
        self.assertEqual(result["status"], "empty_content")
        self.assertNotIn("output", result)

    def test_refusal_is_not_success(self):
        self.assertEqual(inspect_response(response(VALID, refusal="Cannot comply"))["status"], "refused")

    def test_tool_call_is_not_final_answer(self):
        self.assertEqual(inspect_response(response(VALID, "tool_calls"))["status"], "incomplete")

    def test_missing_choices(self):
        self.assertEqual(inspect_response({})["status"], "missing_choices")

    def test_invalid_json_schema_and_extra_fields(self):
        for content in ['not JSON', '{}', VALID.replace('"low"', '"urgent"'), VALID[:-1] + ',"extra":1}', VALID.replace('"Export unavailable"', '42')]:
            with self.subTest(content=content):
                self.assertEqual(inspect_response(response(content))["status"], "invalid_json_or_schema")

    def test_sdk_flattens_extra_body_to_match_direct_http(self):
        captured = []
        def handler(req):
            captured.append(json.loads(req.content))
            return httpx.Response(200, json=response(VALID))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            with OpenAI(api_key="test-placeholder", base_url="https://example.test/v1", http_client=http, max_retries=0) as sdk:
                sdk_request(sdk, request_body())
        self.assertEqual(captured, [request_body()])
        self.assertNotIn("extra_body", captured[0])

    def test_report_omits_raw_reasoning(self):
        result = inspect_response(response(None, "length", reasoning="sensitive text"))
        self.assertNotIn("sensitive text", json.dumps(result))

    def test_endpoint_validation_prevents_key_forwarding(self):
        for base in ['http://api.tokenfactory.nebius.com/v1', 'https://evil.test/v1', 'https://api.tokenfactory.nebius.com.evil.test/v1', 'https://name:pass@api.tokenfactory.nebius.com/v1', 'https://api.tokenfactory.nebius.com/v1?secret=x']:
            with self.subTest(base=base), self.assertRaises(ValueError):
                validate_base(base)
        self.assertEqual(validate_base('https://api.tokenfactory.nebius.com/v1/'), 'https://api.tokenfactory.nebius.com/v1')


if __name__ == "__main__":
    unittest.main()
