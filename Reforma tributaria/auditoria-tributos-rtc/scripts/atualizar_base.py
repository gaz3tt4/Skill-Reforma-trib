#!/usr/bin/env python3
"""Baixa os scripts Flyway mais recentes do repositório oficial e regenera data/rtc.db.

Uso: python -I scripts/atualizar_base.py
"""
import io
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL = "https://codeload.github.com/ReceitaFederal/calculadora-rtc-regime-regular/zip/refs/heads/main"
aqui = Path(__file__).resolve().parent
destino = aqui.parent / "data" / "rtc.db"

with tempfile.TemporaryDirectory() as tmp:
    print("Baixando", URL)
    dados = urllib.request.urlopen(URL, timeout=120).read()
    zipfile.ZipFile(io.BytesIO(dados)).extractall(tmp)
    repo = next(Path(tmp).iterdir())
    novo = Path(tmp) / "rtc.db"
    r = subprocess.run([sys.executable, "-I", str(aqui / "build_db.py"), str(repo), str(novo)],
                       capture_output=True, text=True)
    print(r.stdout[-3000:])
    if r.returncode != 0 or "FAIL" in r.stdout or not novo.exists():
        sys.exit("Falha ao gerar a base; a base atual foi mantida.\n" + r.stderr[-2000:])
    shutil.copy2(novo, destino)
    print("Base atualizada em", destino)
