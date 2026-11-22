# Fenix NAS Suite (`fenix_nas_suite.py`)

Zero-dependency Python storage integrity, recovery, and local NAS management suite designed for offline-first environments such as legal offices, local surveillance archives, and sovereign on-premise storage where cloud reliance is undesirable or unavailable.

## Purpose & Engineering Context

In local storage environments without cloud backup—such as legal case repositories or closed-business surveillance and record archives—data loss, bit corruption, or missing shards can compromise critical records. This suite treats storage reliability like an electrical distribution system: isolating faults, verifying integrity at every stage, and enabling deterministic recovery without third-party external packages.

## Core Architecture & Modules

- **Reed-Solomon Erasure Coding & Recovery ($GF(2^8)$):** Splits files into data and parity shards using a systematic Cauchy matrix over $GF(2^8)$ and reconstructs missing or damaged shards with exact `SHA-256` integrity verification (`exact_integrity_verified`).
- **Block Parity (XOR):** Provides fast block-level parity protection for local storage blocks.
- **Storage & Quota Guardrails:** Monitors real disk usage and enforces storage/quota limits before or during write operations.
- **Quarantine Isolation:** Isolates suspicious or compromised files into a dedicated quarantine workflow rather than leaving them mixed with active storage.
- **JSON Audit Trail:** Records structured audit logs of storage, integrity, and recovery events for traceability.
- **Standard Library Only:** Built strictly on Python standard library modules with zero external runtime dependencies.

## Authorship & Intellectual Property

- **Author:** Jeffrey Mora Espinoza (`jeffmora2026-crypto`)
- **Status:** Verified standalone script (`fenix_nas_suite.py`) compiled cleanly to bytecode and tested for integrity and recovery.
- **Rights Notice:** All rights reserved by the author unless explicitly licensed in writing. Public repository visibility does not grant permission for unauthorized commercial use or redistribution.
