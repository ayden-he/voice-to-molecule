"""Run from the same terminal as the server; never print the API key.

One minimal API call, then one command-schema call only if the first succeeds.
No molecule edits. At most two requests count toward the project's quota.
"""

import json
import os
import argparse
import io
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, getproxies

from interpreter import GeminiInterpreter, InterpretationError, http_diagnostic


def curl_probe(request, key):
    """Compare Windows curl's HTTP stack without putting keys in process args."""
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        print("curl is not installed; transport comparison unavailable.")
        return
    config = '\n'.join([
        'url = ' + json.dumps(request.full_url),
        'header = ' + json.dumps('x-goog-api-key: ' + key),
        'header = "Content-Type: application/json"',
        'data = ' + json.dumps(request.data.decode('utf-8')),
    ])
    try:
        result = subprocess.run(
            [executable, '--silent', '--max-time', '30', '--config', '-',
             '--write-out', '\nHTTP_STATUS:%{http_code}'],
            input=config, text=True, capture_output=True, timeout=35,
        )
        if result.returncode:
            print("curl connection failed (exit {}). Check VPN/proxy/network settings.".format(result.returncode))
            return
        body, _, code = result.stdout.rpartition('\nHTTP_STATUS:')
        if code == '200':
            print("curl minimal request PASSED. The key/model work through curl; the Python HTTP transport needs investigation.")
        else:
            error = HTTPError(request.full_url, int(code), 'request failed', {}, io.BytesIO(body.encode()))
            print("curl minimal request failed: HTTP {}. {}".format(code, http_diagnostic(error, key)))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        print("curl comparison could not complete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--curl', action='store_true', help='Run only one minimal request through curl instead of Python')
    options = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("GEMINI_API_KEY is missing in this terminal. Set it here first.")
        return
    if key != key.strip() or any(char.isspace() for char in key) or key.startswith(('"', "'")):
        print("The key contains whitespace or surrounding quotes. Re-enter only the key when prompted.")
        return
    print("Key length: {} characters; Google-style key format: {}.".format(
        len(key), bool(re.fullmatch(r'AIza[A-Za-z0-9_-]+', key))))
    print("Proxy types detected: {}.".format(', '.join(sorted(getproxies())) or 'none'))
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if not model or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._" for char in model):
        print("GEMINI_MODEL is not a valid model ID.")
        return
    print("Step 1: Testing key/model access without the app's schema.")
    request = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(model),
        data=json.dumps({"contents": [{"parts": [{"text": "Reply with OK."}]}]}).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    if options.curl:
        curl_probe(request, key)
        return
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        if not result.get("candidates"):
            print("The minimal request returned no candidate. The command-schema test was skipped.")
            return
    except HTTPError as exc:
        print("Minimal request failed: HTTP {}. {}".format(exc.code, http_diagnostic(exc, key)))
        return
    except (URLError, OSError, ValueError):
        print("Minimal request failed: network, TLS, or unreadable response. Check connection/proxy settings.")
        return
    print("Minimal request passed. Step 2: Testing the app's command schema.")
    try:
        plan = GeminiInterpreter()("add a carbon", {"atoms": [], "current_atom": None, "queued": []})
        if len(plan) == 1 and plan[0]["command"] == "add carbon":
            print("Command-schema test passed: add carbon. No molecule was changed.")
        else:
            print("Schema accepted, but the model did not interpret the simple request as expected.")
    except InterpretationError as exc:
        print(str(exc))


if __name__ == "__main__":
    main()
