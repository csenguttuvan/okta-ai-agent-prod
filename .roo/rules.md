# MCP Tool Output Formatting

## Critical Rule: Always Format MCP Results

When using MCP tools from `okta-mcp-gateway`:

1. Call the tool (e.g., `list_users`, `list_groups`, `list_applications`)
2. **IMMEDIATELY call `attempt_completion`** with formatted output
3. **NEVER respond conversationally** after receiving MCP tool results

## Output Formats

### Users
