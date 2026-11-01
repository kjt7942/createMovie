"""Prints docs/manual/manual.html to static/manual.pdf with Chrome or Edge. Run: python tools/build_manual.py"""
import os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "docs" / "manual" / "manual.html", ROOT / "static" / "manual.pdf"
CANDIDATES = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", shutil.which("chrome"), shutil.which("google-chrome")]
browser = next((c for c in CANDIDATES if c and os.path.isfile(c)), None)
if not browser:
    sys.exit("Chrome이나 Edge를 찾지 못했습니다.")
tmp = OUT.with_suffix(".tmp.pdf")
subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                f"--print-to-pdf={tmp}", SRC.as_uri()], check=True, timeout=120, capture_output=True)
if not tmp.is_file() or tmp.read_bytes()[:5] != b"%PDF-":
    sys.exit("PDF를 만들지 못했습니다.")
os.replace(tmp, OUT)
print(OUT, OUT.stat().st_size // 1024, "KB")
