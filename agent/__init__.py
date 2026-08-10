# Agent package.
#
# Agent classes are imported lazily (inside orchestrator/router.py's lambdas
# and tools/_dispatch_tool methods) so that importing `agents.orchestrator`
# or `scoring` does not require openai to be installed.
