import base64
import requests
from pathlib import Path

token = "0CmBGYHN5kxjtj7M70kD"
fingerprint = base64.b64encode(16 * b"_" + b"0").decode()

response = requests.put("https://webcam.connect.prusa3d.com/c/snapshot/", headers={
    "Content-Type": "image/jpg",
    "Fingerprint": fingerprint,
    "Token": token,
}, data=Path("jpegsystems-home.jpg").read_bytes())


print(response.status_code)
print(response.headers)
print(f"{response.text!r}")