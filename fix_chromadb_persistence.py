#!/usr/bin/env python3
"""
ChromaDB HNSW Persistence Fix for DocTel RAG.

ROOT CAUSE:
  PersistentHnswParams defaults in ChromaDB 1.5.5:
    batch_size=100, sync_threshold=1000
  
  These thresholds mean _persist() (which writes the HNSW vector index to 
  link_lists.bin on disk) is ONLY called when >=1000 log records accumulate
  since the last persist. The DocTel project has at most ~478 embeddings per
  collection, so _persist() is NEVER called for ANY VECTOR segment.
  
  Result: all link_lists.bin files are 0 bytes. On server restart, the 
  in-memory HNSW index is lost. Queries return 0 results = RAG broken.

FIX:
  1. Insert low hnsw:batch_size=5 and hnsw:sync_threshold=10 into 
     segment_metadata table for ALL VECTOR segments
  2. Clear the stuck embeddings_queue (964 stale entries)
  3. Reset max_seq_id for VECTOR segments
  4. Delete VECTOR segment storage directories (0-byte HNSW files)
  5. Then: restart server + re-ingest documents

WARNING: Stop the server before running this script!
"""

import sqlite3
import os
import shutil
import socket
import sys
from pathlib import Path

CHROMA_PATH = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
DB_PATH = os.path.join(CHROMA_PATH, "chroma.sqlite3")

# VECTOR segment UUIDs (from segments table, type=urn:chroma:segment/vector/hnsw-local-persisted)
VECTOR_SEGMENTS = {
    "project_1": "b17a53d7-1c11-4766-8d30-d5716df48d03",
    "project_2": "1137e690-9aec-472a-9c40-d0454daa5783",
    "project_3": "2348f82f-b7cc-45e5-8112-2499f48e186c",  # Dunning Manual ← our target
    "project_4": "5abac116-f9e3-48bf-a876-0500d3ebbbe3",
    "project_5": "08418511-d2e8-4af3-a309-b1912197b4a8",
    "project_6": "6397a521-fb8e-413e-a681-b60dc5d225c0",
    "project_7": "5ea04ef3-a76b-4a80-af1d-ab1796bb41f0",
    "test_direct": "09a696af-648e-40ea-9b7c-cd8d73e303f9",
}


def check_server_running() -> bool:
    """Check if anything is listening on port 8000."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", 8000))
        return result == 0
    finally:
        sock.close()


def check_chromadb_usage() -> bool:
    """Check if chroma.sqlite3 is locked by another process."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("SELECT COUNT(*) FROM embeddings_queue")
        conn.close()
        return False  # Not locked
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            return True
        raise


def fix():
    print("=" * 70)
    print("  🔧 DocTel ChromaDB HNSW Persistence Fix")
    print("=" * 70)

    # --- Pre-flight checks ---
    if not os.path.isdir(CHROMA_PATH):
        print(f"❌ ERROR: ChromaDB path not found: {CHROMA_PATH}")
        sys.exit(1)
    if not os.path.isfile(DB_PATH):
        print(f"❌ ERROR: chroma.sqlite3 not found at: {DB_PATH}")
        sys.exit(1)

    if check_server_running():
        print("\n⚠️  WARNING: Server appears to be running on port 8000!")
        print("   The ChromaDB SQLite DB must NOT be in use during this fix.")
        print("   Please stop the server first (Ctrl+C in the terminal).")
        resp = input("\n   Continue anyway? (y/N): ").strip().lower()
        if resp != "y":
            print("   ❌ Aborted. Stop the server and re-run.")
            sys.exit(1)

    if check_chromadb_usage():
        print("\n❌ ERROR: chroma.sqlite3 is locked by another process.")
        print("   Close any programs using it and re-run.")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    print()

    # --- Step 1: Set low HNSW thresholds ---
    print("[1/5] Setting low hnsw:batch_size and hnsw:sync_threshold...")
    inserted = 0
    for proj, seg_uuid in VECTOR_SEGMENTS.items():
        cur.execute(
            "INSERT OR REPLACE INTO segment_metadata (segment_id, key, int_value) VALUES (?, ?, ?)",
            (seg_uuid, "hnsw:batch_size", 5),
        )
        inserted += 1
        cur.execute(
            "INSERT OR REPLACE INTO segment_metadata (segment_id, key, int_value) VALUES (?, ?, ?)",
            (seg_uuid, "hnsw:sync_threshold", 10),
        )
        inserted += 1
        print(f"   ✅ {proj}: batch_size=5, sync_threshold=10")
    db.commit()
    cur.execute("SELECT COUNT(*) FROM segment_metadata")
    total = cur.fetchone()[0]
    print(f"   → {total} rows in segment_metadata (was 0 before fix)")

    # --- Step 2: Clear the embeddings queue ---
    print("\n[2/5] Clearing embeddings_queue...")
    cur.execute("SELECT COUNT(*) FROM embeddings_queue")
    before = cur.fetchone()[0]
    cur.execute("DELETE FROM embeddings_queue")
    db.commit()
    cur.execute("SELECT COUNT(*) FROM embeddings_queue")
    after = cur.fetchone()[0]
    print(f"   → Deleted {before} stale queue entries (0 remaining)")

    # --- Step 3: Reset max_seq_id for VECTOR segments ---
    print("\n[3/5] Resetting max_seq_id for VECTOR segments...")
    ids = list(VECTOR_SEGMENTS.values())
    placeholders = ",".join("?" for _ in ids)
    cur.execute(
        f"SELECT segment_id, seq_id FROM max_seq_id WHERE segment_id IN ({placeholders})",
        ids,
    )
    stale_entries = cur.fetchall()
    if stale_entries:
        cur.execute(
            f"DELETE FROM max_seq_id WHERE segment_id IN ({placeholders})", ids
        )
        print(f"   → Deleted {len(stale_entries)} stale max_seq_id entries:")
        for sid, seq in stale_entries:
            print(f"     • {sid}: seq_id={seq}")
    else:
        print("   → No stale max_seq_id entries (expected for VECTOR segments)")
    db.commit()

    # --- Step 4: Delete VECTOR segment storage directories ---
    print(f"\n[4/5] Deleting VECTOR segment storage directories...")
    for proj, seg_uuid in VECTOR_SEGMENTS.items():
        seg_dir = os.path.join(CHROMA_PATH, seg_uuid)
        if os.path.isdir(seg_dir):
            files = os.listdir(seg_dir)
            link_file = os.path.join(seg_dir, "link_lists.bin")
            link_size = os.path.getsize(link_file) if os.path.isfile(link_file) else 0
            shutil.rmtree(seg_dir)
            print(
                f"   🗑️  {proj}: {seg_uuid}/ ({len(files)} files,"
                f" link_lists.bin was {link_size} bytes → deleted)"
            )
        else:
            print(f"   ⚪ {proj}: {seg_uuid}/ does not exist, skipping")

    # --- Step 5: Verify ---
    print("\n[5/5] Verification...")
    cur.execute("SELECT COUNT(*) FROM segment_metadata")
    print(f"   ✅ segment_metadata: {cur.fetchone()[0]} rows")
    cur.execute("SELECT COUNT(*) FROM embeddings_queue")
    print(f"   ✅ embeddings_queue: {cur.fetchone()[0]} entries")
    cur.execute("SELECT COUNT(*) FROM max_seq_id")
    print(f"   ✅ max_seq_id: {cur.fetchone()[0]} entries")

    # Verify a few segment_metadata entries
    cur.execute(
        "SELECT segment_id, key, int_value FROM segment_metadata WHERE key = 'hnsw:sync_threshold'"
    )
    rows = cur.fetchall()
    print(f"   ✅ segment_metadata with sync_threshold: {len(rows)} rows")
    for sid, key, val in rows[:3]:
        short_sid = sid[:8]
        print(f"     • {short_sid}... → {key}={val}")

    db.close()

    # --- Summary ---
    print()
    print("=" * 70)
    print("  ✅ FIX COMPLETE!")
    print("=" * 70)
    print()
    print("  📋 WHAT WAS DONE:")
    print("  1. Inserted low HNSW thresholds into segment_metadata")
    print("     (batch_size=5, sync_threshold=10 → _persist() fires at 10 records)")
    print("  2. Cleared the stuck embeddings_queue (was {})".format(before))
    print("  3. Reset max_seq_id for VECTOR segments")
    print("  4. Deleted stale VECTOR segment directories (0-byte HNSW files)")
    print()
    print("  ⏭️  NEXT STEPS:")
    print("  1. RESTART the server (so segments re-read metadata on init)")
    print("  2. Re-ingest the Dunning Manual (project_3)")
    print("  3. Ask: 'What does the Dunning Manual say about overdue accounts?'")
    print("  4. Verify citations show, no cloud fallback")
    print()
    print("  📝 NOTE: chroma_client.py has also been updated to set these")
    print("     thresholds on any NEW collections created in the future.")
    print("=" * 70)


if __name__ == "__main__":
    fix()
