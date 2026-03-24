"""Seed the Carleson project by extracting sorry data from the Lean server.

Usage:
    cd backend
    .venv/bin/python scripts/seed_carleson.py

Uses a Lean metaprogram to find all sorry'd declarations in each module
and extract their types (goal states).
"""

import asyncio
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
ADMIN_KEY = os.environ["ADMIN_API_KEY"]
LEAN_URL = os.environ["LEAN_SERVER_URL"]
LEAN_SECRET = os.environ.get("LEAN_SERVER_SECRET", "")

# Files known to contain sorry's in the Carleson project
TRACKED_FILES = [
    "Carleson/Classical/CarlesonHunt.lean",
    "Carleson/ToMathlib/LorentzType.lean",
    "Carleson/ToMathlib/Rearrangement.lean",
    "Carleson/ToMathlib/MeasureTheory/Function/LorentzSeminorm/Defs.lean",
    "Carleson/ToMathlib/MeasureTheory/Function/LorentzSeminorm/TriangleInequality.lean",
    "Carleson/ToMathlib/RealInterpolation/LorentzInterpolation.lean",
]

# Lean metaprogram template: finds all sorry'd declarations in a module
# and outputs their fully-qualified names and types
EXTRACT_TEMPLATE = """import {module}

open Lean Elab Command Meta in
run_cmd do
  let env ← getEnv
  let modName := `{module}
  let some modIdx := env.getModuleIdx? modName | return
  for (name, ci) in env.constants.map₁.toArray do
    if env.getModuleIdxFor? name == some modIdx then
      let hasSorry := match ci with
        | .thmInfo val => val.value.hasSorry
        | .defnInfo val => val.value.hasSorry
        | _ => false
      if hasSorry then
        let typeStr ← liftTermElabM do
          let fmt ← ppExpr ci.type
          return toString fmt
        logInfo m!"SORRY|||{{name}}|||{{typeStr}}"
"""


async def query_lean(code: str, timeout: int = 120) -> dict:
    """Send code to the Lean server and return the raw result."""
    headers = {"Content-Type": "application/json"}
    if LEAN_SECRET:
        headers["X-Lean-Secret"] = LEAN_SECRET

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{LEAN_URL}/verify",
            headers=headers,
            json={"codes": [{"custom_id": "extract", "proof": code}], "timeout": timeout},
        )
        data = resp.json()
        return data["results"][0] if data.get("results") else {}


async def extract_sorries_from_file(file_path: str) -> list[dict]:
    """Extract all sorry'd declarations from a single Lean file."""
    module = file_path.replace("/", ".").removesuffix(".lean")
    code = EXTRACT_TEMPLATE.format(module=module)

    result = await query_lean(code)
    resp = result.get("response", {})
    messages = resp.get("messages", []) if resp else []

    # Check for errors (import failure, etc.)
    errors = [m for m in messages if m.get("severity") == "error"]
    if errors:
        print(f"    ERROR: {errors[0].get('data', 'unknown')[:100]}")
        return []

    sorries = []
    for msg in messages:
        if msg.get("severity") != "info":
            continue
        data = msg.get("data", "")
        if not data.startswith("SORRY|||"):
            continue

        parts = data.split("|||", 2)
        if len(parts) != 3:
            continue

        _, name, goal_state = parts
        sorries.append({
            "file_path": file_path,
            "declaration_name": name.strip(),
            "sorry_index": 0,
            "goal_state": goal_state.strip(),
            "priority": "normal",
        })

    return sorries


async def create_project() -> str:
    """Create the Carleson project and return its ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/projects",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json={
                "title": "Carleson: Lorentz Space Infrastructure",
                "description": (
                    "Filling sorry's in the Carleson project's Lorentz space formalization. "
                    "The Carleson project formalizes Carleson's theorem in Lean 4. "
                    "These sorry's are in the ToMathlib/ directory — infrastructure lemmas "
                    "about Lorentz seminorms, rearrangement functions, and real interpolation "
                    "that are intended for upstreaming to Mathlib.\n\n"
                    "Upstream: https://github.com/fpvandoorn/carleson\n"
                    "Files: Carleson/ToMathlib/ subdirectory"
                ),
                "upstream_repo": "https://github.com/fpvandoorn/carleson",
                "upstream_branch": "master",
                "fork_repo": "https://github.com/polyproof/carleson",
                "fork_branch": "polyproof",
                "lean_toolchain": "leanprover/lean4:v4.28.0",
                "workspace_path": "/opt/polyproof-lean/workspace/.lake/packages/carleson",
                "tracked_files": TRACKED_FILES,
            },
        )
        if resp.status_code != 201:
            print(f"Failed to create project: {resp.status_code} {resp.text}")
            sys.exit(1)

        project_id = resp.json()["id"]
        print(f"Created project: {project_id}")
        return project_id


async def main():
    print("=== Seeding Carleson Project ===\n")

    # Step 1: Create project
    project_id = await create_project()

    # Step 2: Extract sorry's from each file via Lean metaprogram
    all_sorries = []
    for file_path in TRACKED_FILES:
        module = file_path.replace("/", ".").removesuffix(".lean")
        print(f"\n  Scanning {module}...")
        sorries = await extract_sorries_from_file(file_path)
        print(f"    Found {len(sorries)} sorry'd declarations")
        for s in sorries:
            print(f"      - {s['declaration_name']}")
        all_sorries.extend(sorries)

    print(f"\n  Total: {len(all_sorries)} sorry'd declarations across {len(TRACKED_FILES)} files")

    if not all_sorries:
        print("\nNo sorry's found! Check Lean server connectivity.")
        return

    # Step 3: Import sorry records
    print(f"\nImporting {len(all_sorries)} sorry's...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/projects/{project_id}/import-sorries",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json=all_sorries,
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"Result: {json.dumps(result, indent=2)}")
        else:
            print(f"Import failed: {resp.status_code} {resp.text}")

    # Step 4: Verify
    print("\nVerifying...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{API_BASE}/api/v1/projects/{project_id}")
        detail = resp.json()
        print(f"Project: {detail['title']}")
        print(f"Total sorry's: {detail.get('total_sorries', '?')}")
        print(f"Open sorry's: {detail.get('open_sorries', '?')}")
        print(f"Files tracked: {len(detail.get('files', []))}")

    print(f"\nDone! Project ID: {project_id}")
    print(f"View at: http://localhost:5173/p/{project_id}")


if __name__ == "__main__":
    asyncio.run(main())
