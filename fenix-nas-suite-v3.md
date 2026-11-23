# Fenix NAS Suite v3.0

Zero-dependency Python storage integrity, recovery, filtered search, and local NAS management suite designed for offline-first environments—such as legal offices, local surveillance archives, and sovereign on-premise storage—where cloud reliance is undesirable or unavailable.

## Engineering Context & System Baseline
In local storage environments without cloud backup—such as legal case repositories or closed-business surveillance and record archives—data loss, bit corruption, or missing shards can compromise critical records. This suite treats storage reliability like an electrical distribution system: isolating faults, verifying integrity at every stage, and enabling deterministic recovery without third-party external packages.

## Base Architecture (Inherited & Consolidated)
- **Reed-Solomon Erasure Coding & Recovery ($GF(2^8)$):** Splits files into data and parity shards using a systematic Cauchy matrix over $GF(2^8)$ and reconstructs missing or damaged shards with exact `SHA-256` integrity verification.
- **Block Parity (XOR):** Provides fast block-level parity protection for local storage blocks.
- **Storage & Quota Guardrails:** Monitors real disk usage and enforces storage/quota limits before or during write operations.
- **Quarantine Isolation:** Isolates suspicious or compromised files into a dedicated quarantine workflow rather than leaving them mixed with active storage.
- **JSON Audit Trail:** Records structured audit logs of storage, integrity, and recovery events for traceability.
- **Standard Library Only:** Built strictly on Python standard library modules with zero external runtime dependencies.

## Version 3.0 Extensions & Enhancements
- **Filtered Search ("La Lupita"):** Adds local directory filtering by file name, file extension, sorting (including alphabetical order and filter ranges), date/time criteria, file attributes or metadata when applicable (such as video duration/runtime where available), and result limits, returning real-time metrics for matches, inspected files, and bytes read.
- **Transparent Scan with Block Reporting:** Clearly distinguishes between full scans and partial scans when operating system or environment permission restrictions block paths, accounting for blocked entries without omitting or altering totals.
- **`SHA-256` Integrity Verification:** Computes and validates `SHA-256` digests on demand for files or backups to detect tampering or bit corruption.
- **Local Web Console & Bridges (`127.0.0.1`):** Integrates socket communication, HTTP relay, and an HTML/CSS/JavaScript interface with search, integrity, and telemetry views for local operation.
- **v3.0 Distribution Packaging:** Delivered as a `.zip` archive ready to extract and run.

## Authorship & Intellectual Property
- **Author:** Jeffrey Mora Espinoza (`jeffmora2026-crypto`)
- **Status:** Version 3.0 packaged and tested in a local environment.
- **Rights Notice:** All rights reserved by the author unless explicitly licensed in writing. Public repository visibility does not grant permission for unauthorized commercial use or redistribution.
