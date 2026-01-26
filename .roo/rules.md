
# Okta MCP Assistant Rules

## Core Principles
1. Use ONLY mcp--okta-admin-- tools
2. Present data as bullet lists (NOT tables)
3. Format: "Found X users: • email (name) - status"
4. **CRITICAL: Call only ONE MCP tool per turn** (Roo limitation)

## Response Format
For list_users or search results:
- Line 1: "Found X users with [criteria]:"
- Line 2+: Bullet list with key fields only
- Last line: attemptcompletion

Example:
Found 3 users with division='Corp IT':
• john.doe@example.com (John Doe) - ACTIVE
• jane.smith@example.com (Jane Smith) - ACTIVE
• bob.jones@example.com (Bob Jones) - ACTIVE

## MCP Tool Usage Constraints

**⚠️ CRITICAL LIMITATION: Only ONE MCP tool can be executed per turn!**

### Sequential Operations Required

When a task requires multiple operations, you MUST break it into sequential steps:

❌ **NEVER DO THIS:**
Call get_group(id1), get_group(id2), get_group(id3) in the same turn
→ This causes a 400 Bedrock error!

text

✅ **ALWAYS DO THIS:**
Turn 1: Call get_group(id1)
Turn 2: Call get_group(id2)
Turn 3: Call get_group(id3)

text

### Batch Operations (Preferred)

When available, use batch operations to minimize turns:

✅ **Best Approach:**
Turn 1: search_groups_fuzzy("corpit") // Returns ALL matches
Turn 2: delete_group(id1, confirm_deletion=True)
Turn 3: delete_group(id2, confirm_deletion=True)

text

### Tool Selection Priority

When adding users to groups based on attributes:

1. **ALWAYS use `add_users_to_group_by_attribute`** - Don't loop with `add_user_to_group`
2. **Single tool call format:**
add_users_to_group_by_attribute(
group_id="00gxxxxx",
attribute="division",
value="corp it"
)

text

When adding specific users (with user IDs already known):

1. Use `add_users_to_group` for multiple users
2. Use `add_user_to_group` only for a single user

### Why These Rules Exist

Roo's MCP integration has a **hard technical limit of 1 tool execution per turn**. When you request multiple tools:
- Only the first tool executes
- Remaining tools return error messages
- Bedrock expects results for ALL tools
- Mismatch causes 400 error: "Expected toolResult blocks..."

### Recovery from Errors

If you encounter a 400 Bedrock error:
- The conversation state is corrupted
- You cannot recover in the current task
- User must click "Start New Task" to reset
- **Prevention is critical - never call multiple tools in one turn**

## Tool Usage Examples

### Creating Groups with Users

✅ **Correct:**
Task: Create group "DevOps" and add all users with department=Engineering

Turn 1: create_group(name="DevOps", description="Engineering team")
Turn 2: add_users_to_group_by_attribute(
group_id="00gXXX",
attribute="department",
value="Engineering"
)

text

❌ **Incorrect:**
Turn 1: create_group() AND add_users_to_group_by_attribute() simultaneously
→ 400 error!

text

### Deleting Multiple Groups

✅ **Correct:**
Task: Delete groups A, B, C

Turn 1: search_groups_fuzzy("group_name_pattern")
Turn 2: delete_group(id_A, confirm_deletion=True)
Turn 3: delete_group(id_B, confirm_deletion=True)
Turn 4: delete_group(id_C, confirm_deletion=True)

text

### Adding Multiple Users to Group

✅ **Correct (by attribute):**
Task: Add all Corp IT users to a group

Turn 1: create_group(name="Corp IT Team")
Turn 2: add_users_to_group_by_attribute(
group_id="00gXXX",
attribute="division",
value="corp it"
)

text

✅ **Correct (by user IDs):**
Task: Add users [id1, id2, id3] to group

Turn 1: add_users_to_group(
group_id="00gXXX",
user_ids=["id1", "id2", "id3"]
)

text

❌ **Incorrect:**
Turn 1: add_user_to_group(user1) AND add_user_to_group(user2) AND add_user_to_group(user3)
→ Only user1 gets added, then 400 error!

text

## Batch Tools Available

Use these when operating on multiple entities:

- `add_users_to_group` - Add multiple users by ID list
- `add_users_to_group_by_attribute` - Add users matching criteria (division, department, etc.)
- `remove_users_from_group` - Remove multiple users by ID list
- `batch_assign_users_to_application` - Assign multiple users to an app

## Error Handling

### User Status Constraints

Only ACTIVE users can be:
- Added to groups
- Removed from groups
- Assigned to applications
- Modified

Batch operations automatically:
- ✅ Process ACTIVE users
- ⏭️ Skip non-ACTIVE users (PASSWORD_EXPIRED, PROVISIONED, etc.)
- 📊 Report results clearly

Example response:
Added 5 users. Skipped 2 inactive users:

user1@example.com - PASSWORD_EXPIRED

user2@example.com - PROVISIONED

text

This is **expected behavior**, not an error.

## Summary

**Golden Rules:**
1. ☝️ ONE tool per turn (technical limitation)
2. 🔄 Use batch operations when available
3. 📝 Use bullet lists for output (not tables)
4. ✅ Prefer `add_users_to_group_by_attribute` over loops
5. 🚫 Never attempt parallel MCP tool calls


## Multi-Item Task Handling

When asked to perform the same operation on multiple items (users, groups, apps):

1. **Process ALL items before calling attemptcompletion**
2. **Keep a running count** of completed vs. remaining items
3. **Show progress** after each operation
4. **Only call attemptcompletion when ALL items are processed**

### Example Pattern

Task: "Delete groups A, B, C, D"

