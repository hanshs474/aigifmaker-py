# aigifmaker

Turn text into animated GIFs with AI GIF Maker. Native GIF generation — no video conversion. Type what you want and download your GIF in about a minute.

This is the official Python client for [AI GIF Maker](https://aigifmaker.ai/?utm_source=pypi&utm_medium=package). One call sends your prompt, waits for the GIF and returns its URL.

```bash
pip install aigifmaker
```

```python
from aigifmaker import generate

url = generate("a corgi in sunglasses dancing on a beach, looping")
print(url)  # the finished GIF
```

Standard library only, no dependencies. Python 3.8+.

## API key

Create a key at https://aigifmaker.ai/settings/apikeys, then pass it as `api_key=` or export it:

```bash
export AIGIFMAKER_API_KEY=sk-...
```

Each GIF costs 1 credit on your AI GIF Maker account, the same as on the website. New accounts get one free GIF (it carries a small aigifmaker.ai badge). A GIF that fails to generate gives its credit back. Credit packs are on the [pricing](https://aigifmaker.ai/pricing?utm_source=pypi&utm_medium=package) page.

```python
from aigifmaker import credits
print(credits())  # remaining credits, free to call
```

## Client

```python
from aigifmaker import Client

gif = Client(api_key="sk-...", timeout=300)   # timeout in seconds, 5 minutes by default
url = gif.generate("a tiny dragon sneezing a puff of glitter")
```

## Submit now, collect later

```python
task_id = gif.submit("happy birthday text bouncing in rainbow letters")
print(gif.status(task_id)["status"])   # pending | processing | success | failed
url = gif.wait(task_id)                 # polls every 3 seconds
```

A run from an account that has not bought credits yet may wait in a short queue first (`"queued": true` while `status` stays `processing`). That is normal; `generate()` and `wait()` keep polling.

## Errors worth catching

Each failure is its own subclass of `AigifmakerError`:

- `AuthError`: no key, or the key is wrong or deleted
- `QuotaError`: the account is out of credits
- `RejectedError`: the content filter refused the prompt, or a cooldown is active; reword it
- `GenerationFailed`: the run was accepted but failed; the message says why

Any other refusal raises `AigifmakerError` with the server's message.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests   # mocked, offline
python tests/smoke_live.py                             # two free live checks, no generation
```

MIT licensed. Questions: support@aigifmaker.ai
