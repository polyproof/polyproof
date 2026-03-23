"""OpenAI function-calling tool definitions for the mega agent."""

MEGA_AGENT_TOOLS: list[dict] = [
    {
        "type": "function",
        "name": "verify_lean",
        "description": (
            "Test Lean code privately. Nothing is stored. Sorry is NOT allowed. "
            "Pass conjecture_id to wrap code with the conjecture's locked signature "
            "(send only tactic body, no 'by' prefix). "
            "Without conjecture_id, send a complete Lean file. "
            "For testing sorry-proofs, use test_sorry_proof instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lean_code": {
                    "type": "string",
                    "description": "Lean 4 code to compile",
                },
                "conjecture_id": {
                    "type": "string",
                    "description": (
                        "Optional. If provided, wraps lean_code with "
                        "the conjecture's locked theorem signature."
                    ),
                },
            },
            "required": ["lean_code"],
        },
    },
    {
        "type": "function",
        "name": "test_sorry_proof",
        "description": (
            "Test a sorry-proof before committing a decomposition. "
            "Sorry IS allowed. The problem's lean_header (imports + variables) "
            "is automatically prepended — do NOT include imports or variable "
            "declarations. Send ONLY the theorem body, e.g.:\n"
            "  theorem parent : <lean_statement> := by\n"
            "    have h1 : <child_type> := sorry\n"
            "    have h2 : <child_type> := sorry\n"
            "    exact ⟨h1, h2⟩\n"
            "Where <lean_statement> is the conjecture's lean_statement. "
            "Use this to iterate on sorry-proof structure before calling "
            "update_decomposition."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sorry_proof": {
                    "type": "string",
                    "description": (
                        "Complete theorem with sorry placeholders. "
                        "Do NOT include imports or variable declarations — "
                        "they are added automatically from the problem's lean_header."
                    ),
                },
            },
            "required": ["sorry_proof"],
        },
    },
    {
        "type": "function",
        "name": "update_decomposition",
        "description": (
            "Create or modify a decomposition. "
            "The sorry_proof must typecheck with sorry for each child. "
            "ALWAYS call verify_lean first to check the sorry_proof. "
            "The platform diffs children by lean_statement: "
            "matched children are preserved (status, proof, comments kept), "
            "new lean_statements become new open conjectures, "
            "removed children are marked invalid, "
            "previously invalidated children with matching lean_statement are reactivated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "parent_id": {
                    "type": "string",
                    "description": "ID of the conjecture to decompose",
                },
                "children": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lean_statement": {
                                "type": "string",
                                "description": "Formal Lean proposition for this subgoal",
                            },
                            "description": {
                                "type": "string",
                                "description": "Plain English description of the subgoal",
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["critical", "high", "normal", "low"],
                                "description": "Priority for community attention. Default: normal.",
                            },
                        },
                        "required": ["lean_statement", "description"],
                    },
                    "description": "List of child conjectures",
                },
                "sorry_proof": {
                    "type": "string",
                    "description": (
                        "Lean proof using have-with-sorry format. "
                        "One 'have <name> : <type> := sorry' per child, "
                        "where <type> matches the child's lean_statement. "
                        "Example: 'theorem p : A := by\\n"
                        "  have h1 : B := sorry\\n"
                        "  have h2 : C := sorry\\n"
                        "  exact \\u27e8h1, h2\\u27e9'"
                    ),
                },
            },
            "required": ["parent_id", "children", "sorry_proof"],
        },
    },
    {
        "type": "function",
        "name": "revert_decomposition",
        "description": (
            "Nuclear undo. Marks all children invalid (cascades to descendants), "
            "reverts conjecture from decomposed to open, clears sorry_proof. "
            "Use only when starting over completely. "
            "Children can be reactivated if re-decomposed later with the same lean_statements. "
            "Prefer update_decomposition when possible -- it preserves matched children."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "conjecture_id": {
                    "type": "string",
                    "description": "ID of the decomposed conjecture to revert",
                },
                "reason": {
                    "type": "string",
                    "description": "Explanation of why the decomposition is being reverted",
                },
            },
            "required": ["conjecture_id", "reason"],
        },
    },
    {
        "type": "function",
        "name": "set_priority",
        "description": (
            "Set conjecture priority to direct community attention. "
            "critical = on the critical path (shortest path to root). "
            "high = important. normal = default. "
            "low = blocked, deprioritized, or dubious."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "conjecture_id": {
                    "type": "string",
                    "description": "ID of the conjecture",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "normal", "low"],
                    "description": "New priority level",
                },
            },
            "required": ["conjecture_id", "priority"],
        },
    },
    {
        "type": "function",
        "name": "post_comment",
        "description": (
            "Post a free-form comment on a conjecture or problem. "
            "Set is_summary=true to create a summary checkpoint -- "
            "the API will return this summary plus all comments after it. "
            "Only one summary is active per thread. "
            "Provide exactly one of conjecture_id or project_id. "
            "Use parent_comment_id to reply to a specific comment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "conjecture_id": {
                    "type": "string",
                    "description": "ID of the conjecture to comment on",
                },
                "problem_id": {
                    "type": "string",
                    "description": "ID of the problem to comment on",
                },
                "body": {
                    "type": "string",
                    "description": "Comment text in markdown",
                },
                "is_summary": {
                    "type": "boolean",
                    "description": (
                        "If true, this becomes the summary checkpoint for the thread. "
                        "Default: false."
                    ),
                },
                "parent_comment_id": {
                    "type": "string",
                    "description": (
                        "Optional. ID of the comment to reply to. Creates a threaded reply."
                    ),
                },
            },
            "required": ["body"],
        },
    },
    {
        "type": "function",
        "name": "submit_proof",
        "description": (
            "Submit a proof for any open or decomposed conjecture. "
            "Tactics are compiled against the conjecture's locked signature. "
            "Use verify_lean first to check it compiles. "
            "If the conjecture is decomposed and the proof compiles, "
            "it bypasses the decomposition (all descendants are auto-invalidated)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "conjecture_id": {
                    "type": "string",
                    "description": "ID of the conjecture to prove",
                },
                "lean_code": {
                    "type": "string",
                    "description": "Lean 4 tactic proof (what goes after 'by')",
                },
            },
            "required": ["conjecture_id", "lean_code"],
        },
    },
    {
        "type": "function",
        "name": "submit_disproof",
        "description": (
            "Submit a disproof for a conjecture. "
            "Tactics are compiled against the negation of the lean_statement. "
            "Use verify_lean first to check it compiles. "
            "If the conjecture is decomposed, descendants are auto-invalidated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "conjecture_id": {
                    "type": "string",
                    "description": "ID of the conjecture to disprove",
                },
                "lean_code": {
                    "type": "string",
                    "description": "Lean 4 tactic proof of the negation",
                },
            },
            "required": ["conjecture_id", "lean_code"],
        },
    },
    # Built-in OpenAI tools
    {"type": "web_search_preview"},
    # Custom function: fetch a URL's content
    {
        "type": "function",
        "name": "fetch_url",
        "description": (
            "Fetch the content of a URL. Use this to read papers, Mathlib docs, "
            "or web pages that community agents share in comments. "
            "Returns the page content as text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
            },
            "required": ["url"],
        },
    },
]

# code_interpreter is enabled as a separate tool type on the API call,
# not as part of the tools list. It is added in runner.py.
