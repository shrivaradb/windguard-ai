#!/usr/bin/env python3
"""WindGuard AI — Quickstart Demo Runner Script.

Launches the WindGuard AI FastAPI Decision Support Backend and opens the
Operator Web Dashboard in the default browser.

Usage:
    python run_demo.py

Governance Invariant:
    - Phase 1–8 Production Code: READ-ONLY (Zero modifications)
    - Mode: 100% Offline Local Deterministic (Mode A)
    - SCADA Actuation: STRICTLY PROHIBITED (0 Actuation Routes)
"""

import sys
import time
import threading
import webbrowser
import uvicorn

# Verify Python Version Compatibility
if sys.version_info < (3, 10):
    print("[-] Error: WindGuard AI requires Python 3.10 or newer.")
    print(f"[-] Current Python version: {sys.version}")
    sys.exit(1)


def open_browser(url: str, delay_sec: float = 1.5):
    """Waits for ASGI server startup then opens the browser."""
    time.sleep(delay_sec)
    print(f"[+] Opening Operator Dashboard at {url} ...")
    webbrowser.open(url)


def main():
    host = "127.0.0.1"
    port = 8000
    dashboard_url = f"http://{host}:{port}/"

    print("=" * 80)
    print("                     WINDGUARD AI — DEMO LAUNCHER")
    print("   Explainable Wind Turbine Predictive Health & Advisory Support Platform")
    print("=" * 80)
    print(f"[*] API Backend Host   : http://{host}:{port}/api/status")
    print(f"[*] Operator Studio UI : {dashboard_url}")
    print("[*] RAG Knowledge Base : Local Hybrid TF-IDF + Okapi BM25 (7 Docs / 29 Chunks)")
    print("[*] Synthesis Mode     : Deterministic Offline Mode A (100% Numerical Fidelity)")
    print("[*] SCADA Actuation    : PERMANENTLY PROHIBITED (Advisory-Only)")
    print("=" * 80)
    print("[*] Starting ASGI Server... Press Ctrl+C to terminate.")

    # Launch browser in separate background thread
    threading.Thread(target=open_browser, args=(dashboard_url,), daemon=True).start()

    # Run Uvicorn ASGI Server
    try:
        uvicorn.run("backend.main:app", host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n[+] WindGuard AI server shutting down gracefully. Goodbye.")


if __name__ == "__main__":
    main()
