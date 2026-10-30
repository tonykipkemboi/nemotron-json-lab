# Get JSON from Nemotron Lightning with thinking turned off

A small example for `nvidia/Nemotron-3_5-Lightning` on Nebius Token Factory.
Use it when you want structured data that your application can read, such as
turning a support message into an issue type, urgency, and summary.

## The problem

A model can use its entire output-token budget on reasoning before producing an
answer. The API may return HTTP 200 even though the answer is empty or unfinished.

In the test below, Lightning used all 512 available output tokens on reasoning
and returned no final answer. An application that only checks HTTP status could
mistake that for a successful result.

## The solution

For this extraction task, turn thinking off and request a JSON schema. Then check
that the answer finished and validate its content before using it.

The setting goes in different places depending on how you call the API:

**OpenAI Python SDK** — add this argument to `client.chat.completions.create(...)`:

```python
extra_body={"chat_template_kwargs": {"enable_thinking": False}}
```

**Direct HTTP** — add this field to the top level of the request's JSON body:

```json
"chat_template_kwargs": {"enable_thinking": false}
```

`extra_body` is a Python SDK argument. It is not a wrapper to send in the HTTP body.
Both methods can be combined with `response_format` using `json_schema`.

Keep checking `finish_reason`: `length` means the response was cut off, even with
thinking disabled. Never use partial reasoning as the final JSON answer.

## Reproduce the test

From this project's folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v test_probe
```

The 11 offline tests need no API key and make no API calls.

For the live test, copy the template and put your key in the local `.env` file:

```sh
cp .env.example .env
# Edit .env and set NEBIUS_API_KEY to your key.
python probe.py --env-file .env
```

If `NEBIUS_API_KEY` is already set in your environment, run `python probe.py`.
Keep the key private; `.env` is excluded from Git.

The live test makes up to five requests and can incur normal API charges. It has
no automatic retries. Results appear in the terminal and in `results/live.json`.
Each run replaces that local report.

### Observed results

Tested October 29, 2026, with Python 3.15 and the versions in `requirements.txt`,
against `https://api.tokenfactory.nebius.com/v1`.

| Test | Result |
| --- | --- |
| Nano, 24-token limit | Truncated reasoning; no final answer |
| Lightning, default thinking, 512-token limit | All 512 output tokens used for reasoning; no final answer |
| Lightning, thinking off, direct HTTP | Valid JSON in 27 output tokens; zero reasoning tokens reported |
| Lightning, thinking off, Python SDK | Valid JSON in 27 output tokens; zero reasoning tokens reported |
| Lightning, thinking off, 8-token limit | Truncated output, correctly rejected |

Both successful calls returned:

```json
{
  "issue_type": "bug",
  "urgency": "low",
  "summary": "The export button has stopped working."
}
```

These are results from one run, not guaranteed token counts. A valid JSON structure
does not guarantee a correct answer. Evaluate the content for your own use case.

## Use it in your application

`probe.py` contains three small helpers:

- `request_body()` builds the prompt, JSON schema, and thinking-off setting.
- `sdk_request()` sends that request through the OpenAI Python SDK.
- `inspect_response()` checks completion, refusal, and schema validity.

For one request, run this from the project folder with `NEBIUS_API_KEY` set in
your environment. It makes a live API call:

```python
import os
from openai import OpenAI
from probe import BASE, request_body, sdk_request, inspect_response

with OpenAI(
    api_key=os.environ["NEBIUS_API_KEY"],
    base_url=BASE,
    max_retries=0,
    timeout=60,
) as client:
    result = inspect_response(sdk_request(client, request_body()))

if result["status"] == "valid_json":
    print(result["output"])
else:
    print("No usable answer:", result["status"])
```

Adapt the `Ticket` schema and prompt in `request_body()` to your task. For direct
HTTP, send the dictionary returned by `request_body()` to `/v1/chat/completions`;
the HTTP branch in `probe.py` shows the complete call.

Turning thinking off is useful here because the task needs a short structured
answer. Other tasks may benefit from reasoning and a larger token budget. Verify
behavior for your chosen model rather than assuming all Nemotron models behave alike.

## Related material

- [Original developer question](https://discord.com/channels/1222156136380235877/1298640342098116608/1563256988492890343)
- [Cookbook PR #79](https://github.com/nebius/token-factory-cookbook/pull/79) documents a related **Nano** truncation behavior. It does not change the API or implement this Lightning example.
- [Structured output documentation](https://docs.tokenfactory.nebius.com/ai-models-inference/json)
- [AGENTS.md](AGENTS.md) — instructions for coding agents working with this project.
