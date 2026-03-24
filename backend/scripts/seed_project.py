"""Seed a Lean project by auto-discovering and extracting sorry's.

Usage:
    cd backend
    .venv/bin/python scripts/seed_project.py \\
        --title "Carleson: Lorentz Space Infrastructure" \\
        --upstream "https://github.com/fpvandoorn/carleson" \\
        --workspace "/opt/polyproof-lean/workspace/.lake/packages/carleson" \\
        --lean-server-host "204.168.160.169" \\
        --source-prefix "Carleson/"

The script will:
1. SSH to the Lean server to discover all .lean files containing sorry
2. Filter out commented-out sorry's by running the Lean metaprogram
3. Extract goal states for each sorry'd declaration
4. Create the project and import sorry records via the platform API

Requires:
    - SSH access to the Lean server (key-based auth)
    - Backend running at localhost:8000 (or API_BASE_URL env var)
    - ADMIN_API_KEY and LEAN_SERVER_SECRET in .env
"""

import argparse
import asyncio
import json
import os
import shlex
import subprocess
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
ADMIN_KEY = os.environ["ADMIN_API_KEY"]
LEAN_URL = os.environ["LEAN_SERVER_URL"]
LEAN_SECRET = os.environ.get("LEAN_SERVER_SECRET", "")

def discover_sorry_files(
    ssh_host: str, workspace_path: str, source_prefix: str, ssh_user: str = "root"
) -> list[str]:
    """SSH to the Lean server and find all .lean files containing 'sorry'."""
    safe_path = shlex.quote(f"{workspace_path}/{source_prefix}")
    cmd = [
        "ssh", f"{ssh_user}@{ssh_host}",
        f"grep -rl 'sorry' {safe_path} --include='*.lean' 2>/dev/null",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("  ERROR: SSH timed out after 30s")
        sys.exit(1)

    if result.returncode != 0 and not result.stdout.strip():
        if result.stderr.strip():
            print(f"  ERROR: SSH failed: {result.stderr.strip()[:200]}")
            sys.exit(1)
        print("  No files with sorry found.")
        return []

    files = []
    for line in result.stdout.strip().splitlines():
        # Convert absolute path to relative path within the workspace
        rel = line.replace(workspace_path + "/", "").strip()
        if rel and rel.endswith(".lean"):
            files.append(rel)

    return sorted(files)


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
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}
        data = resp.json()
        return data["results"][0] if data.get("results") else {}


async def extract_sorries_from_file(
    file_path: str, ssh_host: str, workspace_path: str, ssh_user: str = "root"
) -> list[dict]:
    """Extract sorry's by compiling the file and reading the REPL's sorries field.

    Fetches the file content via SSH, sends it to Kimina for compilation,
    and parses the goal states from the response's ``sorries`` array.
    Maps each sorry position to its enclosing declaration name.
    """
    import re
    import subprocess as sp

    # Fetch file content via SSH
    full_path = f"{workspace_path}/{file_path}"
    try:
        cat_result = sp.run(
            ["ssh", f"{ssh_user}@{ssh_host}", f"cat {shlex.quote(full_path)}"],
            capture_output=True, text=True, timeout=15,
        )
        if cat_result.returncode != 0:
            print(f"    ERROR: could not read {file_path}")
            return []
        file_content = cat_result.stdout
    except sp.TimeoutExpired:
        print(f"    ERROR: SSH timed out reading {file_path}")
        return []

    # Compile the file on Kimina
    result = await query_lean(file_content, timeout=300)

    if "error" in result and isinstance(result["error"], str):
        print(f"    ERROR: {result['error'][:100]}")
        return []

    resp = result.get("response", {})
    raw_sorries = resp.get("sorries", []) if resp else []

    if not raw_sorries:
        return []

    # Map positions to declaration names
    decl_pattern = re.compile(
        r"^(?:@\[.*?\]\s+)?(?:noncomputable\s+|private\s+|protected\s+)*"
        r"(theorem|lemma|def|instance)\s+(\S+)",
        re.MULTILINE,
    )
    decls: list[tuple[int, str]] = []
    for m in decl_pattern.finditer(file_content):
        line_num = file_content[:m.start()].count("\n") + 1
        name = m.group(2).rstrip(":{(⦃[")
        decls.append((line_num, name))
    decls.sort()

    # Build sorry records
    decl_counts: dict[str, int] = {}
    sorries = []
    for s in raw_sorries:
        pos = s.get("pos", {})
        line = pos.get("line", 0)
        goal = s.get("goal", "")

        # Find enclosing declaration
        enclosing = None
        for decl_line, decl_name in decls:
            if decl_line <= line:
                enclosing = decl_name
            else:
                break

        if enclosing is None:
            continue

        idx = decl_counts.get(enclosing, 0)
        decl_counts[enclosing] = idx + 1

        sorries.append({
            "file_path": file_path,
            "declaration_name": enclosing,
            "sorry_index": idx,
            "goal_state": goal,
            "line": line,
            "col": pos.get("column"),
            "priority": "normal",
        })

    return sorries


async def create_project(args: argparse.Namespace, tracked_files: list[str]) -> str:
    """Create the project via the platform API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/projects",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json={
                "title": args.title,
                "description": args.description or f"Sorry-filling project for {args.upstream}",
                "upstream_repo": args.upstream,
                "upstream_branch": args.upstream_branch,
                "fork_repo": args.fork_repo or args.upstream,
                "fork_branch": "polyproof",
                "lean_toolchain": args.lean_toolchain,
                "workspace_path": args.workspace,
                "tracked_files": tracked_files,
            },
        )
        if resp.status_code != 201:
            print(f"Failed to create project: {resp.status_code} {resp.text}")
            sys.exit(1)

        project_id = resp.json()["id"]
        return project_id


async def import_sorries(project_id: str, sorries: list[dict]) -> dict:
    """Import sorry records via the bulk import endpoint."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/projects/{project_id}/import-sorries",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json=sorries,
        )
        if resp.status_code == 200:
            return resp.json()
        return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}


async def main():
    parser = argparse.ArgumentParser(description="Seed a Lean project with auto-discovered sorry's")
    parser.add_argument("--title", required=True, help="Project title")
    parser.add_argument("--description", help="Project description")
    parser.add_argument("--upstream", required=True, help="Upstream repo URL")
    parser.add_argument("--upstream-branch", default="master")
    parser.add_argument("--fork-repo", help="Fork repo URL")
    parser.add_argument("--workspace", required=True, help="Workspace path on Lean server")
    parser.add_argument("--lean-server-host", required=True, help="SSH host")
    parser.add_argument("--lean-server-user", default="root", help="SSH user")
    parser.add_argument("--source-prefix", required=True, help="e.g. Carleson/")
    parser.add_argument("--lean-toolchain", default="leanprover/lean4:v4.28.0")
    args = parser.parse_args()

    print(f"=== Seeding Project: {args.title} ===\n")

    # Step 1: Discover files with sorry via SSH
    print(f"Discovering sorry files on {args.lean_server_host}:{args.workspace}...")
    candidate_files = discover_sorry_files(
        args.lean_server_host, args.workspace, args.source_prefix, args.lean_server_user
    )
    print(f"  Found {len(candidate_files)} candidate files (grep matches)")

    if not candidate_files:
        print("No files with sorry found. Nothing to seed.")
        return

    # Step 2: Compile each file and extract sorry's from the REPL response
    all_sorries = []
    files_with_sorries = []

    for i, file_path in enumerate(candidate_files, 1):
        module = file_path.replace("/", ".").removesuffix(".lean")
        print(f"\n  [{i}/{len(candidate_files)}] {module}...")
        sorries = await extract_sorries_from_file(
            file_path, args.lean_server_host, args.workspace, args.lean_server_user
        )
        if sorries:
            print(f"    {len(sorries)} sorry'd declarations:")
            for s in sorries:
                print(f"      - {s['declaration_name']}")
            all_sorries.extend(sorries)
            files_with_sorries.append(file_path)
        else:
            print("    0 (grep matched comments, not real sorry's)")

    print(f"\n  Total: {len(all_sorries)} sorry'd declarations in {len(files_with_sorries)} files")

    if not all_sorries:
        print("\nNo sorry'd declarations found after Lean analysis.")
        return

    # Step 3: Create project
    print("\nCreating project...")
    project_id = await create_project(args, files_with_sorries)
    print(f"  Project ID: {project_id}")

    # Step 4: Import sorry records
    print(f"\nImporting {len(all_sorries)} sorry's...")
    result = await import_sorries(project_id, all_sorries)
    print(f"  Result: {json.dumps(result, indent=2)}")

    if result.get("status") != "ok":
        print("\nERROR: Import failed. Check the output above.")
        sys.exit(1)

    # Step 5: Verify
    print("\nVerifying...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{API_BASE}/api/v1/projects/{project_id}")
            resp.raise_for_status()
            detail = resp.json()
            print(f"  Project: {detail['title']}")
            print(f"  Total sorry's: {detail.get('total_sorries', '?')}")
            print(f"  Open sorry's: {detail.get('open_sorries', '?')}")
            print(f"  Files tracked: {len(detail.get('files', []))}")
    except Exception as e:
        print(f"  Verification request failed: {e}")

    print(f"\nDone! Project ID: {project_id}")


if __name__ == "__main__":
    asyncio.run(main())
