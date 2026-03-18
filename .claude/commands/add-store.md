Help the user add a new store to ElectrodomesticsBot:

1. Ask for the store URL
2. Delegate to @store-researcher subagent to analyze the store
3. Based on findings, create the adapter file in adapters/
4. Register it in adapters/__init__.py
5. Run a test search to validate
6. Delegate to @adapter-tester subagent for thorough validation
7. Report results

Use subagents for steps 2 and 6 to keep main context clean.