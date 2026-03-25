"""GitHub Contents API client for committing fills to the project fork."""

import base64
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_API_BASE = "https://api.github.com"


class GitHubError(Exception):
    """Raised when a GitHub API call fails."""


def parse_repo(fork_repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL.

    >>> parse_repo("https://github.com/polyproof/carleson")
    'polyproof/carleson'
    """
    url = fork_repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    prefix = "https://github.com/"
    if url.startswith(prefix):
        return url[len(prefix):]
    raise GitHubError(f"Cannot parse GitHub repo from URL: {fork_repo_url}")


async def get_file_content(
    repo: str, path: str, branch: str
) -> tuple[str, str]:
    """Fetch a file from GitHub and return (decoded_content, blob_sha).

    Uses the GitHub Contents API. The blob SHA is needed for subsequent
    commits (optimistic concurrency).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/repos/{repo}/contents/{path}",
            params={"ref": branch},
            headers=_headers(),
        )
        if resp.status_code != 200:
            raise GitHubError(
                f"GET /repos/{repo}/contents/{path} returned {resp.status_code}: "
                f"{resp.text[:200]}"
            )

        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]


async def commit_file(
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str,
    sha: str,
    author_name: str = "PolyProof",
    author_email: str = "noreply@polyproof.org",
) -> str:
    """Commit a file to the fork via the GitHub Contents API.

    Returns the new commit SHA.
    """
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.put(
            f"{_API_BASE}/repos/{repo}/contents/{path}",
            headers=_headers(),
            json={
                "message": message,
                "content": encoded,
                "sha": sha,
                "branch": branch,
                "author": {"name": author_name, "email": author_email},
            },
        )
        if resp.status_code not in (200, 201):
            raise GitHubError(
                f"PUT /repos/{repo}/contents/{path} returned {resp.status_code}: "
                f"{resp.text[:200]}"
            )

        return resp.json()["commit"]["sha"]


def replace_sorry_in_declaration(
    file_content: str,
    declaration_name: str,
    tactics: str,
    sorry_index: int = 0,
) -> str:
    """Replace a sorry in a declaration with the agent's tactics.

    Finds the declaration by name, locates the Nth ``sorry`` in its body
    (where N = sorry_index), and replaces it with the provided tactics
    (preserving indentation).

    Returns the modified file content.
    """
    short_name = declaration_name.rsplit(".", 1)[-1]

    # Find the declaration — allow optional modifiers before the keyword.
    # Use lookahead instead of \b because names can end with ' (prime),
    # which is not a word character, so \b fails after it.
    pattern = re.compile(
        rf"^(?:@\[.*?\]\s+)?(?:noncomputable\s+|private\s+|protected\s+)*"
        rf"(theorem|lemma|def|instance)\s+{re.escape(short_name)}(?=[\s{{(:]|$)",
        re.MULTILINE,
    )
    match = pattern.search(file_content)
    if not match:
        raise GitHubError(
            f"Declaration '{short_name}' not found in file content"
        )

    decl_start = match.start()

    # Find the end of this declaration: the next top-level declaration or EOF
    next_decl = re.compile(
        r"^(?:@\[.*?\]\s+)?(?:noncomputable\s+|private\s+|protected\s+)*"
        r"(?:theorem|lemma|def|instance|class|structure|inductive|abbrev)\s",
        re.MULTILINE,
    )
    next_match = next_decl.search(file_content, match.end())
    decl_end = next_match.start() if next_match else len(file_content)

    # Find the Nth 'sorry' within this declaration's body
    sorry_pattern = re.compile(r"\bsorry\b")
    sorry_match = None
    search_start = decl_start
    for i in range(sorry_index + 1):
        sorry_match = sorry_pattern.search(file_content, search_start, decl_end)
        if not sorry_match:
            raise GitHubError(
                f"Sorry index {sorry_index} not found in declaration '{short_name}' "
                f"(only {i} sorry's found)"
            )
        if i < sorry_index:
            search_start = sorry_match.end()

    # Determine indentation of the sorry line
    line_start = file_content.rfind("\n", 0, sorry_match.start()) + 1
    indent = ""
    for ch in file_content[line_start:sorry_match.start()]:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break

    # Indent the replacement tactics to match
    tactic_lines = tactics.strip().splitlines()
    indented = tactic_lines[0]
    for line in tactic_lines[1:]:
        indented += "\n" + indent + line

    return (
        file_content[:sorry_match.start()]
        + indented
        + file_content[sorry_match.end():]
    )


def map_positions_to_declarations(
    file_content: str,
    positions: list[tuple[int, int]],
) -> list[str | None]:
    """Map (line, col) positions to their enclosing declaration names.

    Scans the file for theorem/lemma/def/instance declarations and builds
    a sorted list of (start_line, name) pairs. For each position, returns
    the name of the declaration that contains it, or None if not found.

    Lines are 1-indexed (matching Lean's output).
    """
    # Find all declarations with their line numbers
    decl_pattern = re.compile(
        r"^(?:@\[.*?\]\s+)?(?:noncomputable\s+|private\s+|protected\s+)*"
        r"(theorem|lemma|def|instance)\s+(\S+)",
        re.MULTILINE,
    )

    decls: list[tuple[int, str]] = []
    for m in decl_pattern.finditer(file_content):
        # Convert character offset to 1-indexed line number
        line_num = file_content[:m.start()].count("\n") + 1
        name = m.group(2)
        # Strip trailing type annotation chars
        name = name.rstrip(":{(⦃[")
        decls.append((line_num, name))

    if not decls:
        return [None] * len(positions)

    # Sort by line number
    decls.sort()

    results: list[str | None] = []
    for line, _col in positions:
        # Find the last declaration that starts at or before this line
        enclosing = None
        for decl_line, decl_name in decls:
            if decl_line <= line:
                enclosing = decl_name
            else:
                break
        results.append(enclosing)

    return results


def _headers() -> dict[str, str]:
    """Build GitHub API request headers."""
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.GITHUB_PAT:
        h["Authorization"] = f"Bearer {settings.GITHUB_PAT}"
    return h
