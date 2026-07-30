#!/usr/bin/env python3
"""
PwnPet for iSH / Pythonista - PNG Relay Edition
Tailscale + Flask compatible
"""

import json, time, random, io
from PIL import Image

def encode_to_png(data: bytes) -> bytes:
    width = int((len(data) ** 0.5)) + 1
    padded = data + b'\x00' * ((width * width * 3) - len(data))
    img = Image.frombytes('RGB', (width, width), padded)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()

def decode_from_png(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes))
    raw = img.tobytes()
    return raw.split(b'\x00')[0]

class PwnPet:
    def __init__(self, name="Pwnagotchi_iSH"):
        self.name = name
        self.handshakes = 0
        self.boredom = 50
        self.face = "(◕‿◕)"
        self.last_scan = time.time()
        self.alive = True
        self.node_id = f"ish_pwnpet_{name}_{int(time.time())}"

    def tick(self):
        if time.time() - self.last_scan > 30:  # Slower for mobile
            self.boredom = min(100, self.boredom + 3)
            self.last_scan = time.time()

    def to_png(self) -> bytes:
        state = {k: getattr(self, k) for k in ['name', 'handshakes', 'boredom', 'face', 'alive', 'last_scan', 'node_id']}
        payload = json.dumps(state).encode('utf-8')
        return encode_to_png(payload)

    @classmethod
    def from_png(cls, png_bytes: bytes):
        raw = decode_from_png(png_bytes)
        data = json.loads(raw.decode('utf-8'))
        pet = cls(data.get('name'))
        for k, v in data.items():
            if hasattr(pet, k):
                setattr(pet, k, v)
        return pet

    def save(self):
        png = self.to_png()
        path = f"{self.name}_{int(time.time())}.png"
        with open(path, "wb") as f:
            f.write(png)
        print(f"📦 Saved {path} - Airdrop or Tailscale to relay!")

if __name__ == "__main__":
    pet = PwnPet()
    pet.save()
    print("🐾 iSH PwnPet ready for PNG relay.")