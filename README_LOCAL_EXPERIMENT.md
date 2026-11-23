# Local Experiment Log — Terminal Bridge and Web Console

This document records the real local experiment run in `~/fenix_v2` to connect the `fenix_nas_suite.py` core with a split web interface in the browser[span_4](start_span)[span_4](end_span)[span_5](start_span)[span_5](end_span)[span_6](start_span)[span_6](end_span)[span_7](start_span)[span_7](end_span). It requires no external dependencies and no cloud connection[span_8](start_span)[span_8](end_span).

## Three-Terminal / View Bridge Architecture

* **Terminal 1 — TCP Socket Bridge (`127.0.0.1:8765`):** Runs `socket_bridge.py`[span_9](start_span)[span_9](end_span). It acts as the main listener on port `8765`, imports `fenix_nas_suite` (`core_loaded: true`), and processes JSON commands (`ping`, `integrity_check`, `zero_trust_scan`, `telemetry_snapshot`)[span_10](start_span)[span_10](end_span)[span_11](start_span)[span_11](end_span).
* **Terminal 2 — Local HTTP Relay (`127.0.0.1:8766`):** Runs `http_relay.py`. It acts as the translator on port `8766`, serving the web interface (`ui/dashboard.html`) and forwarding `POST /cmd` requests from the browser to the TCP socket on Terminal 1 (`127.0.0.1:8765`).
* **Terminal 3 / Browser — Split Console (`http://127.0.0.1:8766/`):** Displays the interface divided into tools (*1. Resiliencia e Integridad*, *2. Cero Confianza y Cuarentena*, *3. Telemetría y Estado*) along with the real-time *Notificaciones de Ejecución y Resultados* feed[span_12](start_span)[span_12](end_span)[span_13](start_span)[span_13](end_span)[span_14](start_span)[span_14](end_span).

## Measured Parameters and Live Test Results

* **TCP Bridge (`127.0.0.1:8765`):** Active and listening, with `fenix_nas_suite` importable (`core_loaded: true`)[span_15](start_span)[span_15](end_span)[span_16](start_span)[span_16](end_span).
* **HTTP Relay (`127.0.0.1:8766`):** Active, linking the browser (`8766`) with the TCP socket (`8765`).
* **`ping` (`socket`):** `status: "ok"`, `core_loaded: true`, `core_note: "fenix_nas_suite importable"`, response time `1.52 ms`[span_17](start_span)[span_17](end_span).
* **`integrity_check` (`resilience`):** Sent with an empty `target` (`""`), returned `status: "error"` (`"Ruta no encontrada para verificar integridad."`) in `0.72 ms`, confirming path validation[span_18](start_span)[span_18](end_span).
* **`zero_trust_scan` (`zerotrust`):** Run twice on `volumen_local`, returning `status: "ok"`, `core_available: true`, and `isolation_ready: true` in `0.06 ms` and `0.05 ms`[span_19](start_span)[span_19](end_span).
* **`telemetry_snapshot` (`telemetry`):** `status: "ok"`, `pid: 29746`, `load_avg_1m: 29.103515625`, `cwd: "/data/data/com.termux/files/home/fenix_v2"`, response time `3.39 ms`[span_20](start_span)[span_20](end_span).

## Evidence Screenshots Attached in the Repository

You can attach your screenshots here (for example under `capturas/` or `docs/`) as visual proof of the test[span_21](start_span)[span_21](end_span)[span_22](start_span)[span_22](end_span)[span_23](start_span)[span_23](end_span)[span_24](start_span)[span_24](end_span):

* **Startup and initial socket test:** Screenshot showing `core_loaded: true` on `127.0.0.1:8765`[span_25](start_span)[span_25](end_span)[span_26](start_span)[span_26](end_span).
* **Split interface views:** Screenshots of the panel in mobile view and desktop / landscape view on `127.0.0.1:8766`[span_27](start_span)[span_27](end_span)[span_28](start_span)[span_28](end_span).
* **Telemetry and all-button notifications:** Screenshot of the *Notificaciones de Ejecución y Resultados* log showing `ping`, `integrity_check`, `zero_trust_scan`, and `telemetry_snapshot`[span_29](start_span)[span_29](end_span).
