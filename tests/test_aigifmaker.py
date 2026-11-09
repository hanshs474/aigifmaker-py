"""Unit tests against the real response shapes of aigifmaker.ai (mocked transport; no network)."""
import os
import unittest

import aigifmaker

BODY = {
    "provider": "openlux",
    "mediaType": "image",
    "model": "gif-maker-v1",
    "scene": "text-to-image",
    "prompt": "a dancing cat",
    "options": {"output_format": "gif"},
}


def fake(calls, polls, submit_reply=None):
    polls = list(polls)
    submit_reply = submit_reply or (200, {"code": 0, "message": "ok", "data": {"id": "t1", "status": "pending", "taskId": "up-1"}})

    def t(method, url, body, headers):
        calls.append((method, url, body, headers))
        if url.endswith("/api/ai/generate"):
            return submit_reply
        if url.endswith("/api/ai/query"):
            return 200, {"code": 0, "message": "ok", "data": polls.pop(0)}
        return 200, {"code": 0, "message": "ok", "data": {"remainingCredits": 42, "made": 3}}

    return t


def client(calls, polls=(), submit_reply=None, key="sk-abc"):
    return aigifmaker.Client(key, base_url="https://t", poll_every=0, transport=fake(calls, polls, submit_reply))


def refusal(message, code=-1):
    return 200, {"code": code, "message": message}


class AigifmakerTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("AIGIFMAKER_API_KEY", None)

    def test_validates_prompt(self):
        with self.assertRaises(ValueError):
            client([]).submit("  ")

    def test_success(self):
        calls = []
        polls = [
            {"id": "t1", "status": "processing"},
            {"id": "t1", "status": "success", "images": ["https://cdn/x.gif"], "watermarked": [False]},
        ]
        url = client(calls, polls).generate("a dancing cat")
        self.assertEqual(url, "https://cdn/x.gif")
        self.assertEqual(calls[0][1], "https://t/api/ai/generate")
        self.assertEqual(calls[0][2], BODY)
        self.assertEqual(calls[0][3], {"Authorization": "Bearer sk-abc"})
        self.assertEqual(calls[1][1], "https://t/api/ai/query")
        self.assertEqual(calls[1][2], {"taskId": "t1"})
        self.assertEqual(len(calls), 3)

    def test_queued_keeps_polling(self):
        calls = []
        polls = [
            {"id": "t1", "status": "processing", "queued": True, "queueEta": 40},
            {"id": "t1", "status": "processing", "queued": True, "queueEta": 10},
            {"id": "t1", "status": "success", "images": ["https://cdn/q.gif"], "watermarked": [True]},
        ]
        self.assertEqual(client(calls, polls).generate("x"), "https://cdn/q.gif")
        self.assertEqual(len(calls), 4)

    def test_failed(self):
        polls = [{"id": "t1", "status": "failed", "errorMessage": "upstream error", "refundNote": "credits refunded"}]
        with self.assertRaises(aigifmaker.GenerationFailed) as cm:
            client([], polls).generate("x")
        self.assertIn("upstream error", str(cm.exception))

    def test_failed_moderation(self):
        polls = [{"id": "t1", "status": "failed", "errorMessage": "blocked", "failureKind": "moderation"}]
        with self.assertRaises(aigifmaker.RejectedError):
            client([], polls).generate("x")

    def test_timeout(self):
        c = aigifmaker.Client("sk", poll_every=0, timeout=0, transport=fake([], [{"status": "processing"}] * 5))
        with self.assertRaises(aigifmaker.AigifmakerError):
            c.generate("x")

    def test_invalid_key(self):
        reply = refusal("invalid API key — create one at https://aigifmaker.ai/settings/apikeys")
        with self.assertRaises(aigifmaker.AuthError):
            client([], submit_reply=reply).submit("x")

    def test_wall_without_key(self):
        calls = []
        reply = (200, {"code": 0, "message": "ok", "data": {"wall": True, "reason": "anon_credits", "cost": 1, "remaining": 0, "grant": 0}})
        with self.assertRaises(aigifmaker.AuthError):
            client(calls, submit_reply=reply, key=None).submit("x")
        self.assertEqual(calls[0][3], {})

    def test_insufficient_credits(self):
        with self.assertRaises(aigifmaker.QuotaError) as cm:
            client([], submit_reply=refusal("insufficient credits")).submit("x")
        self.assertIn("https://aigifmaker.ai/pricing", str(cm.exception))

    def test_cooldown_and_other(self):
        with self.assertRaises(aigifmaker.RejectedError):
            client([], submit_reply=refusal("slow down", code=-2)).submit("x")
        with self.assertRaises(aigifmaker.AigifmakerError) as cm:
            client([], submit_reply=refusal("prompt too long")).submit("x")
        self.assertIs(type(cm.exception), aigifmaker.AigifmakerError)
        self.assertEqual(str(cm.exception), "prompt too long")

    def test_credits(self):
        self.assertEqual(client([]).credits(), 42)

        def bad(method, url, body, headers):
            return refusal("no auth, please sign in")

        with self.assertRaises(aigifmaker.AuthError):
            aigifmaker.Client("sk", transport=bad).credits()

    def test_env_key(self):
        os.environ["AIGIFMAKER_API_KEY"] = "sk-env"
        calls = []
        aigifmaker.credits(transport=fake(calls, []))
        self.assertEqual(calls[0][3], {"Authorization": "Bearer sk-env"})


if __name__ == "__main__":
    unittest.main()
