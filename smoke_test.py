import json

import main

assert main.is_http_url("https://example.com/page")
assert not main.is_http_url("not a url")
assert main.choose_candidate(["https://example.com/plain", "https://cdn.example.com/video.m3u8"]).endswith("video.m3u8")
assert main.find_candidate_urls(json.dumps({"url": "https://example.com/player"})) == ["https://example.com/player"]
print("SMOKE_TEST_OK")
