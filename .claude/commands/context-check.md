Run /context and analyze the output. Report:
1. Current context usage percentage
2. Biggest token consumers (MCP tools, conversation, system prompt)
3. Recommended action:
   - Under 60%: "Context healthy. Continue working."
   - 60-70%: "Consider compacting at next milestone."
   - 70-80%: "Compact now. Suggest: /compact [focus instruction based on recent work]"
   - Over 80%: "Critical. Recommend /clear with handoff to .claude/handoff.md"
4. If any MCP servers are consuming excessive tokens, recommend disabling them.