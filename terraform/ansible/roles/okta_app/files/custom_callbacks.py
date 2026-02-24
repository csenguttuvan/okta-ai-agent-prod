# custom_callbacks.py - Token-optimized MCP tool filtering
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Set
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
import re
import copy

SLIM_SYSTEM_PROMPT = """Okta admin with full access via okta-admin MCP. Delete requires deactivate first. Tables for groups/apps, bullets for users.

Available tools:
- Users: find, create, update, deactivate, delete, reactivate
- Groups: list, find, create, update, delete, members  
- Apps: list, get, assign
- Policies: list, get, create, update, delete

Call ONE tool per turn. No assumptions."""


def _extract_tool_name(tool: Any) -> str:
    if not isinstance(tool, dict):
        return ""
    fn = tool.get("function") or {}
    if isinstance(fn, dict):
        n = fn.get("name")
        return n if isinstance(n, str) else ""
    return ""


def _is_okta_mcp(name: str) -> bool:
    return name.startswith("mcp--okta") or name.startswith("mcp__okta")


def _prune_conversation(messages: list, max_history: int = 6) -> list:
    if len(messages) <= max_history + 1:
        return messages

    system = [messages[0]] if messages and messages[0].get("role") == "system" else []
    rest = messages[len(system):]

    if len(rest) <= max_history:
        return system + rest

    recent = rest[-max_history:]

    # Collect tool_use IDs in the kept slice
    kept_ids = set()
    for msg in recent:
        if msg.get("role") == "assistant":
            for block in (msg.get("content") or []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    kept_ids.add(block["id"])

    # Expand window until no orphaned tool_results remain
    for expand in range(0, min(8, len(rest) - max_history), 2):
        orphaned = False
        candidate = rest[-(max_history + expand):]

        # Recompute kept IDs for this candidate slice
        cand_ids = set()
        for msg in candidate:
            if msg.get("role") == "assistant":
                for block in (msg.get("content") or []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        cand_ids.add(block["id"])

        for msg in candidate:
            for block in (msg.get("content") or []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if block.get("tool_use_id") not in cand_ids:
                        orphaned = True
                        break
            if orphaned:
                break

        recent = candidate
        if not orphaned:
            break  # ✅ Clean slice found

    pruned = system + recent
    saved = len(messages) - len(pruned)
    if saved > 0:
        print(f"[MCP] 🔪 Pruned {saved} old messages (kept {len(pruned)}, pair-safe)")
    return pruned




def _normalize_plural(text: str) -> str:
    """Normalize plural forms to singular for consistent matching"""
    replacements = {
        "groups": "group",
        "users": "user",
        "apps": "app",
        "applications": "application",
        "policies": "policy",
        "rules": "rule",
        "members": "member",
        "factors": "factor",
        "roles": "role",
    }
    for plural, singular in replacements.items():
        text = text.replace(plural, singular)
    return text


def _extract_latest_user_query(messages: list) -> str:
    """Extract ONLY the most recent user query (multi-turn safe)"""

    # 🔍 DEBUG: Print last 2 messages to see format
    if len(messages) >= 2:
        print(f"[MCP DEBUG] Last message role: {messages[-1].get('role')}")
        print(
            f"[MCP DEBUG] Last message content preview: {str(messages[-1].get('content', ''))[:200]}"
        )

    # Priority 1: Check for user query in tool_result (after attempt_completion)
    for msg in reversed(messages):
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            if isinstance(content, str):
                # Look for <user_message> in tool result
                match = re.search(
                    r"<user_message>\s*(.+?)\s*</user_message>",
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                )
                if match:
                    query = match.group(1).strip()
                    query = re.sub(r"<[^>]+>", "", query)
                    if len(query) > 3:
                        print(
                            f"[MCP] 📋 Extracted from tool_result <user_message>: {query[:60]}"
                        )
                        return query.lower()
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text", "")
                        match = re.search(
                            r"<user_message>\s*(.+?)\s*</user_message>",
                            text,
                            flags=re.DOTALL | re.IGNORECASE,
                        )
                        if match:
                            query = match.group(1).strip()
                            query = re.sub(r"<[^>]+>", "", query)
                            if len(query) > 3:
                                print(
                                    f"[MCP] 📋 Extracted from tool_result <user_message>: {query[:60]}"
                                )
                                return query.lower()

    # Priority 2: Check last user message
    last_user_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg
            break

    if last_user_msg:
        content = last_user_msg.get("content", "")

        # Handle list format (Roo's standard format)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")

                    # Skip environment_details blocks
                    if (
                        "<environment_details>" in text
                        and "</environment_details>" in text
                    ):
                        # But check if query is BEFORE environment_details
                        parts = text.split("<environment_details>")
                        if parts[0].strip() and len(parts[0].strip()) > 5:
                            query = parts[0].strip()
                            query = re.sub(r"<[^>]+>", "", query)
                            print(f"[MCP] 📋 Extracted before environment: {query[:60]}")
                            return query.lower()
                        continue

                    # Try ALL possible tag formats
                    for tag in [
                        "user_message",
                        "task",
                        "user_query",
                        "query",
                        "instruction",
                    ]:
                        pattern = f"<{tag}>(.*?)</{tag}>"
                        match = re.search(
                            pattern, text, flags=re.DOTALL | re.IGNORECASE
                        )
                        if match:
                            query = match.group(1).strip()
                            query = re.sub(r"<[^>]+>", "", query)
                            if len(query) > 3:
                                print(f"[MCP] 📋 Extracted from <{tag}>: {query[:60]}")
                                return query.lower()

                    # If no tags found but text is short and meaningful, use it
                    cleaned = re.sub(r"<[^>]+>", "", text).strip()
                    if cleaned and len(cleaned) < 200 and len(cleaned) > 5:
                        # But skip if it's just environment noise
                        if not any(
                            noise in cleaned.lower()
                            for noise in [
                                "vscode",
                                "current time",
                                "iso 8601",
                                "time zone",
                                "error",
                                "reminder",
                            ]
                        ):
                            print(f"[MCP] 📋 Extracted from plain text: {cleaned[:60]}")
                            return cleaned.lower()

        # Handle string format
        elif isinstance(content, str):
            # Check if query is BEFORE environment_details
            if "<environment_details>" in content:
                parts = content.split("<environment_details>")
                if parts[0].strip() and len(parts[0].strip()) > 5:
                    query = parts[0].strip()
                    query = re.sub(r"<[^>]+>", "", query)
                    print(f"[MCP] 📋 Extracted before environment: {query[:60]}")
                    return query.lower()

            # Try ALL possible tag formats
            for tag in ["user_message", "task", "user_query", "query", "instruction"]:
                pattern = f"<{tag}>(.*?)</{tag}>"
                match = re.search(pattern, content, flags=re.DOTALL | re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    query = re.sub(r"<[^>]+>", "", query)
                    if len(query) > 3:
                        print(f"[MCP] 📋 Extracted from <{tag}>: {query[:60]}")
                        return query.lower()

            # ✨ FALLBACK FOR ORCHESTRATOR: Handle plain operation strings
            # Pattern 1: "Execute the Okta operation: OPERATION_NAME"
            match = re.search(
                r"Execute the Okta operation:\s*(\w+)", content, re.IGNORECASE
            )
            if match:
                operation = match.group(1)
                print(f"[MCP] ✅ Extracted operation from orchestrator: {operation}")
                return operation.lower()

            # Pattern 2: "operation: OPERATION_NAME" or "action: ACTION_NAME"
            match = re.search(
                r"(?:operation|action):\s*(\w+(?:_\w+)*)", content, re.IGNORECASE
            )
            if match:
                operation = match.group(1)
                print(f"[MCP] ✅ Extracted operation keyword: {operation}")
                return operation.lower()

            # Pattern 3: Common Okta operations with user context
            operations_pattern = r"\b(unlock|reset|deactivate|delete|suspend|activate|reactivate|create|update|list|find|search|add|remove)\b"
            context_pattern = (
                r"\b(user|group|app|application|mfa|password|factor|member)\b"
            )

            op_match = re.search(operations_pattern, content, re.IGNORECASE)
            ctx_match = re.search(context_pattern, content, re.IGNORECASE)

            if op_match and ctx_match:
                operation = op_match.group(1)
                context = ctx_match.group(1)
                query = f"{operation} {context}"
                print(f"[MCP] ✅ Extracted compound query: {query}")
                return query.lower()
            elif op_match:
                operation = op_match.group(1)
                print(f"[MCP] ✅ Extracted operation: {operation}")
                return operation.lower()

            # Pattern 4: Underscore-separated operation names (e.g., "reset_user_mfa")
            match = re.search(r"\b([a-z]+_[a-z_]+)\b", content, re.IGNORECASE)
            if match:
                operation = match.group(1)
                print(f"[MCP] ✅ Extracted snake_case operation: {operation}")
                return operation.lower()

            # Pattern 5: Email mentions suggest user operations
            if re.search(
                r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", content, re.IGNORECASE
            ):
                # User email found, check for operation keywords
                for kw in [
                    "unlock",
                    "reset",
                    "deactivate",
                    "delete",
                    "suspend",
                    "activate",
                    "mfa",
                    "password",
                ]:
                    if kw in content.lower():
                        print(f"[MCP] ✅ Extracted from email context: {kw} user")
                        return f"{kw} user"

    print("[MCP] ⚠️ No query extracted, using defaults")
    return ""


# 🆕 ADD THESE TWO NEW FUNCTIONS HERE (before _get_relevant_tools)
def _compress_system_prompt_gentle(prompt: str) -> str:
    """
    Gently compress system prompt while preserving critical sections.
    """
    if not prompt or len(prompt) < 1000:
        return prompt

    # Critical patterns that MUST be preserved
    critical_sections = [
        "attempt_completion",
        "ask_followup_question",
        "tool in your previous response",
        "Instructions for Tool Use",
        "Next Steps",
        "Reminder:",
        "[ERROR]",
        "tool calling mechanism",
        "required parameters",
        "MCP",
        "okta-admin",
    ]

    lines = prompt.split("\n")
    kept_lines = []
    skip_next = False

    for i, line in enumerate(lines):
        line_lower = line.lower()

        # Always keep critical instruction lines
        is_critical = any(
            pattern.lower() in line_lower for pattern in critical_sections
        )

        if is_critical:
            kept_lines.append(line)
            skip_next = False
            continue

        # Remove verbose example blocks (but keep short examples)
        if any(
            marker in line_lower for marker in ["example:", "for example:", "e.g.,"]
        ):
            if len(line) < 100:
                kept_lines.append(line)
            else:
                skip_next = True
            continue

        if skip_next:
            if line.strip() and not line.strip().startswith(("#", "-", "*", ">")):
                continue
            else:
                skip_next = False

        # Remove excessive whitespace
        if not line.strip():
            if kept_lines and kept_lines[-1].strip():
                kept_lines.append("")
            continue

        # Keep everything else
        kept_lines.append(line)

    # Join and clean up excessive blank lines
    compressed = "\n".join(kept_lines)
    while "\n\n\n" in compressed:
        compressed = compressed.replace("\n\n\n", "\n\n")

    return compressed.strip()


def _compress_tool_response_gentle(content: str) -> str:
    """
    Gently compress tool responses by removing redundant verbose fields.
    """
    try:
        import json

        data = json.loads(content)

        def strip_redundant(obj, depth=0):
            """Recursively remove verbose fields while keeping essentials"""

            if depth > 10:
                return obj

            if isinstance(obj, dict):
                essential = {
                    "id",
                    "name",
                    "email",
                    "status",
                    "label",
                    "type",
                    "description",
                    "firstName",
                    "lastName",
                    "login",
                    "profile",
                    "created",
                    "activated",
                    "statusChanged",
                    "lastLogin",
                    "lastUpdated",
                    "passwordChanged",
                    "success",
                    "error",
                    "message",
                    "count",
                    "results",
                    "data",
                    "userId",
                    "groupId",
                    "appId",
                    "credentials",
                    "provider",
                }

                verbose = {"_links", "_embedded", "_meta", "self", "schema"}

                cleaned = {}
                for k, v in obj.items():
                    if k in verbose:
                        continue

                    if k in essential:
                        if isinstance(v, (dict, list)):
                            cleaned[k] = strip_redundant(v, depth + 1)
                        else:
                            cleaned[k] = v
                    elif depth < 3:
                        if isinstance(v, (dict, list)):
                            cleaned[k] = strip_redundant(v, depth + 1)
                        else:
                            cleaned[k] = v

                return cleaned

            elif isinstance(obj, list):
                max_items = 50
                if len(obj) > max_items:
                    truncated = [
                        strip_redundant(item, depth + 1) for item in obj[:max_items]
                    ]
                    truncated.append(
                        {
                            "_truncated": f"... and {len(obj) - max_items} more items (total: {len(obj)})"
                        }
                    )
                    return truncated
                else:
                    return [strip_redundant(item, depth + 1) for item in obj]

            return obj

        compressed_data = strip_redundant(data)
        return json.dumps(compressed_data, separators=(",", ":"), ensure_ascii=False)

    except json.JSONDecodeError:
        if len(content) > 2000:
            return (
                content[:2000]
                + f"\n\n[... truncated {len(content) - 2000} chars for token efficiency]"
            )
        return content
    except Exception as e:
        print(f"[MCP DEBUG] Tool response compression failed: {e}")
        return content


def _get_relevant_tools(messages: list) -> Set[str]:
    msg = _extract_latest_user_query(messages)
    msg = _normalize_plural(msg)  # Normalize plurals to singular

    print(f"[MCP DEBUG] 🔍 Query after normalization: '{msg}'")
    print(f"[MCP DEBUG] 🔍 'delete' in msg: {'delete' in msg}")
    print(f"[MCP DEBUG] 🔍 'user' in msg: {'user' in msg}")
    print(f"[MCP DEBUG] 🔍 'group' not in msg: {'group' not in msg}")

    tools = set()

    def add_tool(base_name):
        # Try all possible MCP server naming conventions
        tools.add(f"mcp--okta-admin--{base_name}")  # Standard: okta-admin
        tools.add(f"mcp--okta___admin--{base_name}")  # Triple underscore variant
        tools.add(f"mcp--oktaadmin--{base_name}")  # No dash: oktaadmin
        tools.add(f"mcp__okta_admin__{base_name}")  # All underscores

    add_tool("check_permissions")
    add_tool("checkpermissions")  # No underscore variant

    # 🆕 ADD THIS: Context detection for follow-up queries
    # Check if previous tool calls indicate user/group operations
    recent_context = {"user": False, "group": False, "app": False}
    for m in reversed(messages[-5:]):  # Check last 5 messages
        if m.get("role") == "assistant":
            content = m.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "").lower()
                        if "user" in tool_name:
                            recent_context["user"] = True
                        if "group" in tool_name:
                            recent_context["group"] = True
                        if "app" in tool_name or "application" in tool_name:
                            recent_context["app"] = True

    if not msg or len(msg) < 3:
        add_tool("list_users")
        add_tool("listusers")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("find_user")
        add_tool("finduser")
        return tools

    attribute_keywords = [
        "division",
        "department",
        "title",
        "location",
        "manager",
        "costcenter",
        "cost center",
        "office",
        "city",
        "country",
        "org",
        "organization",
        "team",
        "role",
        "level",
        "grade",
        "profile",
        "attribute",
        "property",
        "field",
    ]
    has_attribute_query = any(kw in msg for kw in attribute_keywords)

    # LOGS - Process FIRST to prioritize log queries
    is_log_query = any(
        w in msg for w in ["log", "logs", "audit", "event", "activity", "history"]
    )

    if is_log_query:
        # Try all possible tool name variations
        add_tool("get_logs")  # Standard naming: get_logs
        add_tool("getlogs")  # No underscore variant: getlogs
        add_tool("list_system_logs")  # Alternative naming
        add_tool("listsystemlogs")
        add_tool("system_logs")
        add_tool("systemlogs")

        # If asking about logs for a specific user, also include user lookup
        if "user" in msg or any(w in msg for w in ["for", "by", "from", "about"]):
            add_tool("find_user")
            add_tool("finduser")
            add_tool("get_user")
            add_tool("getuser")

        return tools  # Return early to prioritize log queries

    # USERS
    if "list" in msg and "user" in msg and "group" not in msg and "app" not in msg:
        add_tool("list_users")
        add_tool("listusers")
    if any(
        w in msg
        for w in ["search", "find", "lookup", "get", "show", "who has", "user with"]
    ):
        if "user" in msg or has_attribute_query:
            add_tool("find_user")
            add_tool("finduser")
            add_tool("search_users_fuzzy")
            add_tool("searchusersfuzzy")
            add_tool("get_user")
            add_tool("getuser")
            add_tool("search_users")
            add_tool("searchusers")
            if has_attribute_query:
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")
    if "create" in msg and "user" in msg and "group" not in msg:
        add_tool("create_user")
        add_tool("createuser")
    if ("update" in msg or "modify" in msg or "change" in msg) and "user" in msg:
        add_tool("update_user")
        add_tool("updateuser")
        add_tool("get_user")
        add_tool("getuser")
        add_tool("find_user")
        add_tool("finduser")
    if "deactivate" in msg and "user" in msg:
        add_tool("deactivate_user")
        add_tool("deactivateuser")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if "activate" in msg and "user" in msg:
        add_tool("activate_user")
        add_tool("activateuser")
        add_tool("reactivate_user")
        add_tool("reactivateuser")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if "reactivate" in msg and "user" in msg:
        add_tool("reactivate_user")
        add_tool("reactivateuser")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if "delete" in msg:
        # Explicit: "delete user X"
        if "user" in msg and "group" not in msg:
            print(f"[MCP DEBUG] 🔴 DELETE USER MATCHED! msg='{msg}'")
            add_tool("delete_user")
            add_tool("deleteuser")
            add_tool("deactivate_user")
            add_tool("deactivateuser")
            add_tool("find_user")
            add_tool("finduser")
        # Implicit: "yes, delete permanently" after user operations
        elif recent_context["user"] and not recent_context["group"]:
            print(f"[MCP DEBUG] 🔄 Implicit user deletion from context! msg='{msg}'")
            add_tool("delete_user")
            add_tool("deleteuser")
            add_tool("deactivate_user")
            add_tool("deactivateuser")
            add_tool("find_user")
            add_tool("finduser")
    if (
        any(
            w in msg
            for w in ["what group", "which group", "user group", "user's group"]
        )
        and "user" in msg
    ):
        add_tool("get_user_groups")
        add_tool("getusergroups")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("get_user")
        add_tool("getuser")
    if any(w in msg for w in ["reset", "unlock", "mfa", "password", "2fa", "factor"]):
        if "user" in msg or "mfa" in msg or "password" in msg:
            add_tool("reset_user_mfa_and_password")
            add_tool("resetusermfaandpassword")
            add_tool("find_user")
            add_tool("finduser")
    # Batch operations with attribute filtering
    if has_attribute_query and "user" in msg:
        if any(w in msg for w in ["add", "assign"]) and "group" in msg:
            add_tool("add_users_to_group_by_attribute")
            add_tool("adduserstogroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("search_groups_fuzzy")
            add_tool("searchgroupsfuzzy")
        if any(w in msg for w in ["remove", "unassign"]) and "group" in msg:
            add_tool("remove_users_from_group_by_attribute")
            add_tool("removeusersfromgroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("search_groups_fuzzy")
            add_tool("searchgroupsfuzzy")
        if any(w in msg for w in ["remove", "unassign"]) and (
            "app" in msg or "application" in msg
        ):
            add_tool("unassign_users_from_application_by_attribute")
            add_tool("unassignusersfromapplicationbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")

    # GROUPS
    if (
        "list" in msg
        and "group" in msg
        and any(w in msg for w in ["user", "member", "in the group", "in group"])
    ):
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
    elif "list" in msg and "group" in msg:
        add_tool("list_groups")
        add_tool("listgroups")
    if (
        any(w in msg for w in ["search", "find", "lookup", "get", "show"])
        and "group" in msg
    ):
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
    if "create" in msg and "group" in msg:
        add_tool("create_group")
        add_tool("creategroup")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        if has_attribute_query or any(
            w in msg for w in ["add all", "add user", "with", "who have"]
        ):
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("add_users_to_group_by_attribute")
            add_tool("adduserstogroupbyattribute")
            add_tool("list_group_users")
            add_tool("listgroupusers")
            add_tool("add_user_to_group")
            add_tool("addusertogroup")
            add_tool("list_group_users")
            add_tool("listgroupusers")
            add_tool("find_user")
            add_tool("finduser")
    if ("update" in msg or "modify" in msg or "change" in msg) and "group" in msg:
        add_tool("update_group")
        add_tool("updategroup")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("list_groups")
        add_tool("listgroups")
    if "delete" in msg and "group" in msg:
        add_tool("delete_group")
        add_tool("deletegroup")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
        # Add preview tool for safety
        if any(w in msg for w in ["preview", "impact", "check", "what", "show"]):
            add_tool("preview_group_deletion_impact")
            add_tool("previewgroupdeletionimpact")
        if any(w in msg for w in ["empty", "member", "clear"]):
            add_tool("list_group_users")
            add_tool("listgroupusers")
            add_tool("remove_users_from_group")
            add_tool("removeusersfromgroup")
    elif "delete" in msg and recent_context["group"] and not recent_context["user"]:
        # User said something like "yes, delete it" after working with groups
        add_tool("delete_group")
        add_tool("deletegroup")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("preview_group_deletion_impact")
        add_tool("previewgroupdeletionimpact")
        print("[MCP DEBUG] 🔄 Implicit group deletion detected from context")
    if any(w in msg for w in ["add", "assign", "join"]) and "group" in msg:
        add_tool("add_user_to_group")
        add_tool("addusertogroup")
        add_tool("add_users_to_group")
        add_tool("adduserstogroup")
        add_tool("find_user")
        add_tool("finduser")
        add_tool("searchgroupsfuzzy")
        add_tool("search_groups_fuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")
        if has_attribute_query or any(
            w in msg for w in ["who have", "with", "all user"]
        ):
            add_tool("add_users_to_group_by_attribute")
            add_tool("adduserstogroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")
            add_tool("list_group_users")
            add_tool("listgroupusers")
    if ("remove" in msg or "unassign" in msg) and "group" in msg and "user" in msg:
        add_tool("remove_user_from_group")
        add_tool("removeuserfromgroup")
        add_tool("remove_users_from_group")
        add_tool("removeusersfromgroup")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("find_user")
        add_tool("finduser")
        if has_attribute_query:
            add_tool("remove_users_from_group_by_attribute")
            add_tool("removeusersfromgroupbyattribute")
            add_tool("search_users_by_attribute")
            add_tool("searchusersbyattribute")

    # Preview group deletion impact (separate condition for clarity)
    if (
        any(w in msg for w in ["preview", "impact", "check", "what happen"])
        and "delet" in msg
        and "group" in msg
    ):
        add_tool("preview_group_deletion_impact")
        add_tool("previewgroupdeletionimpact")
        add_tool("search_groups_fuzzy")
        add_tool("searchgroupsfuzzy")
        add_tool("get_group")
        add_tool("getgroup")
        add_tool("list_groups")
        add_tool("listgroups")

    # APPLICATIONS
    if "list" in msg and ("app" in msg or "application" in msg):
        if "user" in msg:
            add_tool("find_application")
            add_tool("findapplication")
            add_tool("list_application_users")
            add_tool("listapplicationusers")
            add_tool("get_application")
            add_tool("getapplication")
        elif "group" in msg:
            add_tool("list_application_groups")
            add_tool("listapplicationgroups")
            add_tool("get_application")
            add_tool("getapplication")
        else:
            add_tool("list_applications")
            add_tool("listapplications")

    if any(w in msg for w in ["get", "show", "find"]) and (
        "app" in msg or "application" in msg
    ):
        add_tool("find_application")
        add_tool("findapplication")
        add_tool("get_application")
        add_tool("getapplication")
        add_tool("list_applications")
        add_tool("listapplications")
    if "create" in msg and ("app" in msg or "application" in msg):
        add_tool("create_application")
        add_tool("createapplication")
        add_tool("find_application")
        add_tool("findapplication")
        add_tool("list_applications")
        add_tool("listapplications")
    if "delete" in msg and ("app" in msg or "application" in msg):
        add_tool("delete_application")
        add_tool("deleteapplication")
        add_tool("find_application")
        add_tool("findapplication")
        add_tool("get_application")
        add_tool("getapplication")
        add_tool("list_applications")
        add_tool("listapplications")

    if any(w in msg for w in ["assign", "add", "grant"]) and (
        "app" in msg or "application" in msg
    ):
        if "group" in msg:
            add_tool("find_user")
            add_tool("finduser")
            add_tool("assign_group_to_application")
            add_tool("assigngrouptoapplication")
            add_tool("get_application")
            add_tool("getapplication")
            add_tool("find_application")
            add_tool("findapplication")
            add_tool("search_groups_fuzzy")
            add_tool("searchgroupsfuzzy")
            add_tool("list_groups")
            add_tool("listgroups")

            
        if "user" in msg:
            add_tool("assign_user_to_application")
            add_tool("assignusertoapplication")
            add_tool("batch_assign_users_to_application")
            add_tool("batchassignuserstoapplication")
            add_tool("get_application")
            add_tool("getapplication")
            add_tool("find_application")
            add_tool("findapplication")
            add_tool("find_user")
            add_tool("finduser")
            add_tool("list_applications")
            add_tool("listapplications")


            if any(w in msg for w in ["role", "arn", "aws", "saml"]):
                add_tool("assign_user_to_application_with_role")
                add_tool("assignusertoapplicationwithrole")
                add_tool("list_application_available_roles")
                add_tool("listapplicationavailableroles")
                add_tool("check_role_exists_on_application")
                add_tool("checkroleexistsonapplication")
            if has_attribute_query:
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")
            if has_attribute_query:
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")

    if any(w in msg for w in ["unassign", "remove"]) and (
        "app" in msg or "application" in msg
    ):
        if "user" in msg:
            add_tool("list_application_users")
            add_tool("listapplicationusers")
            add_tool("find_application")
            add_tool("findapplication")
            add_tool("get_application")
            add_tool("getapplication")
            add_tool("find_user")
            add_tool("finduser")
            if has_attribute_query:
                add_tool("unassign_users_from_application_by_attribute")
                add_tool("unassignusersfromapplicationbyattribute")
                add_tool("search_users_by_attribute")
                add_tool("searchusersbyattribute")
    if (
        ("update" in msg or "change" in msg)
        and ("role" in msg or "arn" in msg)
        and ("app" in msg or "application" in msg)
    ):
        add_tool("update_user_application_role")
        add_tool("updateuserapplicationrole")
        add_tool("list_application_available_roles")
        add_tool("listapplicationavailableroles")
        add_tool("get_application")
        add_tool("getapplication")
        add_tool("find_application")
        add_tool("findapplication")
        add_tool("find_user")
        add_tool("finduser")
    if (
        any(w in msg for w in ["list", "show", "available"])
        and "role" in msg
        and ("app" in msg or "application" in msg)
    ):
        add_tool("list_application_available_roles")
        add_tool("listapplicationavailableroles")
        add_tool("find_application")
        add_tool("findapplication")
        add_tool("get_application")
        add_tool("getapplication")
    if "check" in msg and "role" in msg:
        add_tool("check_role_exists_on_application")
        add_tool("checkroleexistsonapplication")
        add_tool("get_application")
        add_tool("getapplication")

    # POLICIES
    if "list" in msg and "policy" in msg:
        add_tool("list_policies")
        add_tool("listpolicies")
        if "rule" in msg:
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
            add_tool("get_policy")
            add_tool("getpolicy")

    if any(w in msg for w in ["get", "show", "find"]) and "policy" in msg:
        add_tool("get_policy")
        add_tool("getpolicy")
        add_tool("list_policies")
        add_tool("listpolicies")

    if "create" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("create_policy_rule")
            add_tool("createpolicyrule")
            add_tool("get_policy")
            add_tool("getpolicy")
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
        else:
            add_tool("create_policy")
            add_tool("createpolicy")
            add_tool("list_policies")
            add_tool("listpolicies")

    if "update" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("update_policy_rule")
            add_tool("updatepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("update_policy")
            add_tool("updatepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")
            add_tool("list_policies")
            add_tool("listpolicies")

    if "delete" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("delete_policy_rule")
            add_tool("deletepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("list_policy_rules")
            add_tool("listpolicyrules")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("delete_policy")
            add_tool("deletepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")
            add_tool("list_policies")
            add_tool("listpolicies")

    if "activate" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("activate_policy_rule")
            add_tool("activatepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("activate_policy")
            add_tool("activatepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")

    if "deactivate" in msg and "policy" in msg:
        if "rule" in msg:
            add_tool("deactivate_policy_rule")
            add_tool("deactivatepolicyrule")
            add_tool("get_policy_rule")
            add_tool("getpolicyrule")
            add_tool("get_policy")
            add_tool("getpolicy")
        else:
            add_tool("deactivate_policy")
            add_tool("deactivatepolicy")
            add_tool("get_policy")
            add_tool("getpolicy")

    if any(w in msg for w in ["get", "show"]) and "rule" in msg and "policy" in msg:
        add_tool("get_policy_rule")
        add_tool("getpolicyrule")
        add_tool("list_policy_rules")
        add_tool("listpolicyrules")
        add_tool("get_policy")
        add_tool("getpolicy")

    # FALLBACK
    if len(tools) == 1:
        add_tool("list_users")
        add_tool("listusers")
        add_tool("list_groups")
        add_tool("listgroups")
        add_tool("list_group_users")
        add_tool("listgroupusers")
        add_tool("find_user")
        add_tool("finduser")

    return tools


def _ultra_slim_tool(t: Dict[str, Any]) -> Dict[str, Any]:
    fn = t.get("function", {})
    params = fn.get("parameters", {})
    props = params.get("properties", {})
    required = params.get("required", [])
    minimal_props = {}
    for key, prop in props.items():
        # Keep first sentence of description + emphasize parameter name
        desc = (
            prop.get("description", "").split(".")[0].split("\n")[0][:80].strip()
        )  # Increased from 60 to 80
        minimal_props[key] = {"type": prop.get("type", "string"), "description": desc}
        if prop.get("enum"):
            minimal_props[key]["enum"] = prop["enum"][:]

    # Keep function description concise but complete
    func_desc = ".".join(fn.get("description", "").split(".")[:2]).strip()
    if func_desc and not func_desc.endswith("."):
        func_desc += "."

    # Add parameter hint to description
    if required:
        func_desc += f" Required: {', '.join(required)}."

    return {
        "type": "function",
        "function": {
            "name": fn.get("name", ""),
            "description": func_desc,
            "parameters": {
                "type": "object",
                "properties": minimal_props,
                "required": required[:] if required else [],
            },
        },
    }


class McpOnlyToolsHandler(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: Literal["completion", "embeddings", "image_generation", ...],
    ) -> dict:
        try:
            messages = data.get("messages", [])
            if not messages:
                return data

            
            messages = _prune_conversation(messages, max_history=6)
            data["messages"] = messages

            # 🔧 OPTIMIZATION 2: Gentle system prompt compression (preserves critical sections)
            if messages and messages[0].get("role") == "system":
                original_prompt = messages[0].get("content", "")
                compressed_prompt = _compress_system_prompt_gentle(original_prompt)

                if len(compressed_prompt) < len(original_prompt):
                    messages[0]["content"] = compressed_prompt
                    saved = len(original_prompt) - len(compressed_prompt)
                    print(
                        f"[MCP] 📝 Gently compressed system prompt: {len(original_prompt)} → {len(compressed_prompt)} chars ({saved} saved)"
                    )

            # 🔧 OPTIMIZATION 3: Gentle tool response compression (only removes redundant data)
            for msg in messages:
                if msg.get("role") == "tool":
                    original_content = msg.get("content", "")
                    if (
                        isinstance(original_content, str)
                        and len(original_content) > 1000
                    ):
                        compressed = _compress_tool_response_gentle(original_content)
                        if (
                            len(compressed) < len(original_content) * 0.8
                        ):  # Only apply if >20% savings
                            msg["content"] = compressed
                            print(
                                f"[MCP] 🗜️  Compressed tool response: {len(original_content)} → {len(compressed)} chars"
                            )

            # Extract query for tool filtering
            query = _extract_latest_user_query(messages)
            relevant_tools = _get_relevant_tools(messages)

            # Deep copy to avoid mutation
            data = copy.deepcopy(data)

            # Find where tools are stored
            direct_tools = data.get("tools")
            optional_params = data.get("optional_params")
            optional_tools = (
                optional_params.get("tools")
                if isinstance(optional_params, dict)
                else None
            )

            container = None
            tools = None
            if isinstance(direct_tools, list):
                container = "data.tools"
                tools = direct_tools
            elif isinstance(optional_tools, list):
                container = "data.optional_params.tools"
                tools = optional_tools

            if not tools:
                return data

            # Filter tools
            kept = []
            okta_count = 0
            all_okta_tools = []
            matched_okta_tools = []

            for t in tools:
                name = _extract_tool_name(t)
                if not _is_okta_mcp(name):
                    kept.append(t)
                    continue

                all_okta_tools.append(name)

                if name in relevant_tools:
                    kept.append(_ultra_slim_tool(t))
                    matched_okta_tools.append(name)
                    okta_count += 1

            # Update the tools in the correct container
            if container == "data.tools":
                data["tools"] = kept
            elif container == "data.optional_params.tools":
                data["optional_params"]["tools"] = kept

            # Log the filtering results
            total_before = len(tools)
            total_after = len(kept)

            query_preview = query[:50] + "..." if len(query) > 50 else query
            if not query_preview:
                query_preview = "unknown query"

            print(
                f"[MCP] '{query_preview}' | {total_before} → {total_after} ({okta_count} Okta)"
            )

            if okta_count < len(all_okta_tools):
                print(
                    f"[MCP DEBUG] Filtered out {len(all_okta_tools) - okta_count} Okta tools"
                )

            return data

        except Exception as e:
            print(f"[MCP ERROR] {e}")
            import traceback

            traceback.print_exc()
            return data


proxy_handler_instance = McpOnlyToolsHandler()
