#!/usr/bin/env python3
"""
fenix_nas_suite.py
Programa único, autocontenido y sin dependencias externas (Python 3 stdlib)
para Termux / Linux: almacenamiento/cuotas, auditoría y recuperación XOR/Reed-Solomon.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


GF256_POLY = 0x11D
_GF_EXP = [0] * 512
_GF_LOG = [0] * 256


def _init_gf256() -> None:
    x = 1
    for i in range(255):
        _GF_EXP[i] = x
        _GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= GF256_POLY
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]


_init_gf256()


def gf_add(a: int, b: int) -> int:
    return a ^ b


def gf_sub(a: int, b: int) -> int:
    return a ^ b


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def gf_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("División por cero en GF(2^8)")
    if a == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] - _GF_LOG[b] + 255) % 255]


def gf_pow(a: int, power: int) -> int:
    if power == 0:
        return 1
    if a == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] * power) % 255]


def _rs_generator_matrix(k: int, m: int) -> List[List[int]]:
    """
    Matriz sistemática de (k + m) x k sobre GF(2^8):
    - Filas 0..k-1: identidad (fragmentos de datos directos).
    - Filas k..k+m-1: matriz de Cauchy 1 / (x_i ^ y_j) con puntos disjuntos,
      garantizando que cualquier subconjunto de k filas sea invertible.
    """
    if k + m > 256:
        raise ValueError("k + m no puede superar 256 en GF(2^8).")
    matrix: List[List[int]] = []
    for r in range(k):
        row = [0] * k
        row[r] = 1
        matrix.append(row)
    for i in range(m):
        x_val = k + i
        p_row = [gf_div(1, x_val ^ j) for j in range(k)]
        matrix.append(p_row)
    return matrix


def _invert_matrix_gf256(matrix: List[List[int]]) -> List[List[int]]:
    n = len(matrix)
    aug = [
        row[:] + [1 if i == j else 0 for j in range(n)]
        for i, row in enumerate(matrix)
    ]
    for col in range(n):
        pivot_row = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if pivot_row is None:
            raise ValueError("Matriz singular en GF(2^8); no invertible.")
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        inv_pivot = gf_div(1, aug[col][col])
        aug[col] = [gf_mul(val, inv_pivot) for val in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                factor = aug[r][col]
                aug[r] = [
                    gf_sub(aug[r][c], gf_mul(factor, aug[col][c]))
                    for c in range(2 * n)
                ]
    return [row[n:] for row in aug]


def rs_encode_shards(data: bytes, k: int, m: int) -> Tuple[List[bytes], List[bytes], int]:
    if k <= 0 or m <= 0:
        raise ValueError("k y m deben ser mayores que 0.")
    if k + m > 256:
        raise ValueError("k + m no debe exceder 256 en GF(2^8).")

    orig_len = len(data)
    shard_size = (orig_len + k - 1) // k if orig_len > 0 else 1
    padded = bytearray(data)
    total_needed = k * shard_size
    if len(padded) < total_needed:
        padded.extend(b"\x00" * (total_needed - len(padded)))

    data_shards = [
        bytearray(padded[i * shard_size : (i + 1) * shard_size]) for i in range(k)
    ]
    gen = _rs_generator_matrix(k, m)
    parity_rows = gen[k : k + m]
    parity_shards = [bytearray(shard_size) for _ in range(m)]

    for p_idx in range(m):
        coeffs = parity_rows[p_idx]
        p_buf = parity_shards[p_idx]
        for pos in range(shard_size):
            acc = 0
            for d_idx in range(k):
                acc = gf_add(acc, gf_mul(coeffs[d_idx], data_shards[d_idx][pos]))
            p_buf[pos] = acc

    return (
        [bytes(s) for s in data_shards],
        [bytes(s) for s in parity_shards],
        orig_len,
    )


def rs_reconstruct_data(
    available_shards: Dict[int, bytes],
    k: int,
    m: int,
    original_len: int,
) -> bytes:
    if len(available_shards) < k:
        raise ValueError(
            f"Fragmentos insuficientes: tenés {len(available_shards)} y se requieren al menos {k}."
        )
    chosen_indices = sorted(available_shards.keys())[:k]
    shard_size = len(available_shards[chosen_indices[0]])

    gen = _rs_generator_matrix(k, m)
    sub_matrix = [gen[idx] for idx in chosen_indices]
    inv_sub = _invert_matrix_gf256(sub_matrix)

    chosen_bufs = [available_shards[idx] for idx in chosen_indices]
    recovered_data_shards = [bytearray(shard_size) for _ in range(k)]

    for d_idx in range(k):
        row_weights = inv_sub[d_idx]
        out_buf = recovered_data_shards[d_idx]
        for pos in range(shard_size):
            acc = 0
            for s_pos in range(k):
                acc = gf_add(acc, gf_mul(row_weights[s_pos], chosen_bufs[s_pos][pos]))
            out_buf[pos] = acc

    return b"".join(bytes(s) for s in recovered_data_shards)[:original_len]


def xor_block_protect(data: bytes, block_size: int = 64) -> Tuple[List[bytes], bytes, int]:
    orig_len = len(data)
    blocks: List[bytearray] = []
    for i in range(0, orig_len, block_size):
        chunk = bytearray(data[i : i + block_size])
        if len(chunk) < block_size:
            chunk.extend(b"\x00" * (block_size - len(chunk)))
        blocks.append(chunk)
    if not blocks:
        blocks.append(bytearray(block_size))

    parity = bytearray(block_size)
    for blk in blocks:
        for idx in range(block_size):
            parity[idx] ^= blk[idx]

    return [bytes(b) for b in blocks], bytes(parity), orig_len


def xor_block_recover(
    blocks_or_none: List[Optional[bytes]],
    parity: bytes,
    orig_len: int,
) -> bytes:
    missing = [i for i, b in enumerate(blocks_or_none) if b is None]
    if len(missing) > 1:
        raise ValueError(
            f"XOR simple solo reconstruye 1 bloque faltante; faltan {len(missing)}."
        )
    block_size = len(parity)
    if len(missing) == 1:
        m_idx = missing[0]
        rec = bytearray(parity)
        for idx, blk in enumerate(blocks_or_none):
            if idx != m_idx and blk is not None:
                for pos in range(block_size):
                    rec[pos] ^= blk[pos]
        blocks_or_none[m_idx] = bytes(rec)

    return b"".join(b for b in blocks_or_none if b is not None)[:orig_len]

RISK_VECTORS = (
    "permission_denied",
    "checksum_mismatch",
    "bulk_modification",
    "unauthorized_ip",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def isolate_to_quarantine(target: Path, quarantine_dir: Path) -> str:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    dest = quarantine_dir / f"isolated_{target.name}"
    shutil.move(str(target), str(dest))
    try:
        os.chmod(str(dest), 0o400)
    except OSError:
        pass
    return str(dest)


def audit_json_events(events: object) -> Dict[str, object]:
    items = events if isinstance(events, list) else [events]
    vector_counts: Dict[str, int] = {vec: 0 for vec in RISK_VECTORS}
    matched_records: List[Dict[str, object]] = []

    for idx, entry in enumerate(items):
        raw_text = json.dumps(entry, ensure_ascii=False).lower()
        found_in_entry = [vec for vec in RISK_VECTORS if vec in raw_text]
        for vec in found_in_entry:
            vector_counts[vec] += 1
        if found_in_entry:
            matched_records.append(
                {
                    "record_index": idx,
                    "vectors_found": found_in_entry,
                    "entry": entry,
                }
            )

    return {
        "total_records_scanned": len(items),
        "vector_counts": vector_counts,
        "flagged_records_count": len(matched_records),
        "flagged_records": matched_records,
    }


def evaluate_quotas_and_disk(
    quotas_gb: Dict[str, float],
    consumption_gb: Dict[str, float],
    mount_path: Path,
) -> Dict[str, object]:
    du = shutil.disk_usage(str(mount_path))
    anomalies: List[Dict[str, object]] = []

    for volume, quota in quotas_gb.items():
        used = float(consumption_gb.get(volume, 0.0))
        if quota <= 0:
            continue
        ratio = round(used / quota, 2)
        if ratio >= 1.2:
            severity = (
                "CRITICAL / POTENTIAL INTRUSION OR DATA EXFILTRATION"
                if ratio >= 3.0
                else "HIGH / QUOTA OVERCONSUMPTION"
            )
            anomalies.append(
                {
                    "volume": volume,
                    "quota_gb": quota,
                    "consumption_gb": used,
                    "anomaly_ratio": ratio,
                    "severity": severity,
                }
            )

    return {
        "mount_path": str(mount_path),
        "physical_disk": {
            "total_gb": round(du.total / (1024**3), 2),
            "used_gb": round(du.used / (1024**3), 2),
            "free_gb": round(du.free / (1024**3), 2),
        },
        "anomalies": anomalies,
    }


def telemetry_snapshot(start_perf: float) -> Dict[str, object]:
    elapsed_ms = round((time.perf_counter() - start_perf) * 1000, 3)
    max_rss_kb = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return {"elapsed_ms": elapsed_ms, "max_rss_kb": max_rss_kb}

def protect_file_rs(file_path: Path, out_dir: Path, k: int = 4, m: int = 2) -> Dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = file_path.read_bytes()
    orig_hash = hashlib.sha256(raw).hexdigest()

    data_shards, parity_shards, orig_len = rs_encode_shards(raw, k=k, m=m)
    shard_records: List[Dict[str, object]] = []

    for i, d_bytes in enumerate(data_shards):
        s_name = f"{file_path.name}.d{i}.shard"
        (out_dir / s_name).write_bytes(d_bytes)
        shard_records.append(
            {
                "index": i,
                "role": "data",
                "file": s_name,
                "sha256": hashlib.sha256(d_bytes).hexdigest(),
            }
        )

    for j, p_bytes in enumerate(parity_shards):
        idx = k + j
        s_name = f"{file_path.name}.p{j}.shard"
        (out_dir / s_name).write_bytes(p_bytes)
        shard_records.append(
            {
                "index": idx,
                "role": "parity",
                "file": s_name,
                "sha256": hashlib.sha256(p_bytes).hexdigest(),
            }
        )

    manifest = {
        "source_file": file_path.name,
        "original_size_bytes": orig_len,
        "original_sha256": orig_hash,
        "k_data_shards": k,
        "m_parity_shards": m,
        "shards": shard_records,
    }
    manifest_path = out_dir / f"{file_path.name}.rs_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "manifest_path": str(manifest_path),
        "k": k,
        "m": m,
        "original_sha256": orig_hash,
    }


def recover_file_rs(manifest_path: Path, shards_dir: Path, restored_path: Path) -> Dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    k = int(manifest["k_data_shards"])
    m = int(manifest["m_parity_shards"])
    orig_len = int(manifest["original_size_bytes"])
    expected_hash = str(manifest["original_sha256"])

    available: Dict[int, bytes] = {}
    damaged_or_missing: List[Dict[str, object]] = []

    for rec in manifest["shards"]:
        idx = int(rec["index"])
        s_path = shards_dir / str(rec["file"])
        expected_s_hash = str(rec["sha256"])

        if not s_path.exists():
            damaged_or_missing.append({"index": idx, "reason": "missing"})
            continue

        content = s_path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_s_hash:
            damaged_or_missing.append({"index": idx, "reason": "hash_mismatch"})
            continue

        available[idx] = content

    restored_bytes = rs_reconstruct_data(available, k=k, m=m, original_len=orig_len)
    restored_path.parent.mkdir(parents=True, exist_ok=True)
    restored_path.write_bytes(restored_bytes)
    actual_hash = hashlib.sha256(restored_bytes).hexdigest()

    return {
        "restored_path": str(restored_path),
        "damaged_or_missing_shards": damaged_or_missing,
        "used_shards_indices": sorted(available.keys())[:k],
        "expected_sha256": expected_hash,
        "restored_sha256": actual_hash,
        "exact_integrity_verified": (actual_hash == expected_hash),
    }


def run_full_demo(work_dir: Path) -> Dict[str, object]:
    t0 = time.perf_counter()
    work_dir.mkdir(parents=True, exist_ok=True)

    payload_file = work_dir / "nas_critical_data.bin"
    payload_file.write_bytes(
        b"FENIX-NAS-SUITE // BLOQUE CRITICO DE AUDITORIA, CUOTAS Y RECUPERACION "
        b"EN CUERPO FINITO GF(2^8) CON VERIFICACION SHA-256."
    )
    shards_dir = work_dir / "rs_shards"
    prot_info = protect_file_rs(payload_file, shards_dir, k=4, m=2)

    (shards_dir / f"{payload_file.name}.d0.shard").unlink(missing_ok=True)
    (shards_dir / f"{payload_file.name}.p0.shard").unlink(missing_ok=True)

    restored_file = work_dir / "recovered_nas_critical_data.bin"
    rs_recovery = recover_file_rs(
        Path(prot_info["manifest_path"]), shards_dir, restored_file
    )

    xor_blocks, xor_parity, xor_len = xor_block_protect(payload_file.read_bytes(), block_size=32)
    xor_corrupted: List[Optional[bytes]] = list(xor_blocks)
    xor_corrupted[0] = None
    xor_recovered_bytes = xor_block_recover(xor_corrupted, xor_parity, xor_len)
    xor_ok = (
        hashlib.sha256(xor_recovered_bytes).hexdigest() == prot_info["original_sha256"]
    )

    quotas = {"/srv/nas/media": 500.0, "/srv/nas/backups": 150.0, "/srv/nas/logs": 50.0}
    usage = {"/srv/nas/media": 650.0, "/srv/nas/backups": 900.0, "/srv/nas/logs": 45.0}
    quota_res = evaluate_quotas_and_disk(quotas, usage, work_dir)

    suspect_file = work_dir / "suspect_dump.bin"
    suspect_file.write_bytes(b"MODIFICACION_NO_AUTORIZADA_DETECTADA")
    quarantined_to = isolate_to_quarantine(suspect_file, work_dir / "quarantine")

    sample_events = [
        {"ts": "2026-11-22T16:40:00Z", "event": "permission_denied", "user": "svc_nas"},
        {"ts": "2026-11-22T16:41:00Z", "event": "unauthorized_ip", "ip": "10.99.4.22"},
        {"ts": "2026-11-22T16:42:00Z", "event": "read_ok", "file": "vault.enc"},
    ]
    audit_res = audit_json_events(sample_events)

    report = {
        "suite": "fenix_nas_suite.py",
        "reed_solomon_gf256_recovery": rs_recovery,
        "xor_single_block_recovery_verified": xor_ok,
        "quotas_and_disk": quota_res,
        "quarantine_action": {"isolated_to": quarantined_to},
        "log_audit": audit_res,
        "telemetry": telemetry_snapshot(t0),
    }

    report_file = work_dir / "fenix_suite_report.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fenix NAS Suite: almacenamiento/cuotas, auditoría y recuperación XOR/Reed-Solomon."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Ejecuta prueba completa de paridad, recuperación, cuotas y auditoría.")
    p_demo.add_argument("--dir", type=Path, default=Path("./fenix_suite_lab"))

    p_prot = sub.add_parser("protect", help="Genera fragmentos de datos y paridad Reed-Solomon para un archivo.")
    p_prot.add_argument("file", type=Path)
    p_prot.add_argument("--out", type=Path, default=Path("./rs_out"))
    p_prot.add_argument("-k", type=int, default=4)
    p_prot.add_argument("-m", type=int, default=2)

    p_rec = sub.add_parser("recover", help="Reconstruye un archivo desde su manifiesto y fragmentos disponibles.")
    p_rec.add_argument("manifest", type=Path)
    p_rec.add_argument("--shards-dir", type=Path, required=True)
    p_rec.add_argument("--output", type=Path, required=True)

    p_aud = sub.add_parser("audit", help="Audita un archivo JSON de eventos o logs.")
    p_aud.add_argument("json_file", type=Path)

    p_quo = sub.add_parser("quotas", help="Evalúa espacio físico real y umbrales desde un archivo JSON.")
    p_quo.add_argument("config_json", type=Path)
    p_quo.add_argument("--mount", type=Path, default=Path("."))

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo":
        res = run_full_demo(args.dir)
    elif args.command == "protect":
        res = protect_file_rs(args.file, args.out, k=args.k, m=args.m)
    elif args.command == "recover":
        res = recover_file_rs(args.manifest, args.shards_dir, args.output)
    elif args.command == "audit":
        payload = json.loads(args.json_file.read_text(encoding="utf-8"))
        res = audit_json_events(payload)
    elif args.command == "quotas":
        cfg = json.loads(args.config_json.read_text(encoding="utf-8"))
        res = evaluate_quotas_and_disk(
            cfg.get("quotas_gb", {}),
            cfg.get("consumption_gb", {}),
            args.mount,
        )
    else:
        return 1

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
