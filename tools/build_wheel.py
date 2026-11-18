"""
Builds anycubic_cloud-1.0.0-py3-none-any.whl for OrcaSlicer.
"""

import os
import zipfile
import hashlib
import base64

def build_whl():
    whl_name = "anycubic_cloud-1.0.0-py3-none-any.whl"
    out_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    whl_path = os.path.join(out_dir, whl_name)

    src_file = os.path.join(out_dir, "anycubic_cloud.py")
    with open(src_file, "rb") as f:
        src_data = f.read()

    metadata = b"""Metadata-Version: 2.1
Name: anycubic-cloud
Version: 1.0.0
Summary: Conexao nativa com a Anycubic Cloud para OrcaSlicer (Kobra 3, Kobra X, Kobra S1, Kobra 2 e Photon)
Author: Murilo & OrcaSlicer Community
Requires-Python: >=3.12
Requires-Dist: paho-mqtt>=2.0.0
Requires-Dist: requests>=2.31.0

Plugin nativo para o OrcaSlicer que permite conectar diretamente nas impressoras Anycubic via nuvem.
"""

    wheel = b"""Wheel-Version: 1.0
Generator: custom_builder
Root-Is-Purelib: true
Tag: py3-none-any
"""

    record_lines = []

    def add_entry(zf, path, data):
        zf.writestr(path, data)
        digest = hashlib.sha256(data).digest()
        b64_digest = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        record_lines.append(f"{path},sha256={b64_digest},{len(data)}")

    with zipfile.ZipFile(whl_path, "w", zipfile.ZIP_DEFLATED) as zf:
        add_entry(zf, "anycubic_cloud.py", src_data)
        add_entry(zf, "anycubic_cloud-1.0.0.dist-info/METADATA", metadata)
        add_entry(zf, "anycubic_cloud-1.0.0.dist-info/WHEEL", wheel)
        add_entry(zf, "anycubic_cloud-1.0.0.dist-info/top_level.txt", b"anycubic_cloud\n")

        # Record file itself
        record_lines.append("anycubic_cloud-1.0.0.dist-info/RECORD,,")
        zf.writestr("anycubic_cloud-1.0.0.dist-info/RECORD", "\n".join(record_lines) + "\n")

    print(f"Built wheel: {whl_path}")

if __name__ == "__main__":
    build_whl()
