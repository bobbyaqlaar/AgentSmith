# shellcheck shell=bash
# AgentSmith — the old ai-* command names, as one-line wrappers around `agentsmith`.
#
# OPTIONAL and never sourced by the installer. For muscle memory only:
#   source ~/.agent-framework/shell/ai-compat.sh
# Every wrapper is a plain call: the mode is recorded in ~/.agent-framework/state/
# for every process, so nothing here exports anything. Removed in the next minor
# release (FIXES_AND_CLEANUP.md); scripts/test/test_cli_install.py checks each
# wrapper names a real subcommand.

ai-mode-local()             { agentsmith mode local "$@"; }
ai-mode-hybrid()            { agentsmith mode hybrid "$@"; }
ai-stack-off()              { agentsmith mode off "$@"; }
ai-stack-check()            { agentsmith check "$@"; }
ai-stack-status()           { agentsmith status "$@"; }
ai-stack-judge-model()      { agentsmith models --judge "$@"; }
ai-stack-required-models()  { agentsmith models --ollama "$@"; }
ai-dashboard-start()        { agentsmith dashboard start "$@"; }
ai-dashboard-stop()         { agentsmith dashboard stop "$@"; }
ai-test-evals()             { agentsmith evals "$@"; }
ai-stack-promote()          { agentsmith promote "$@"; }
ai-tenant-init()            { agentsmith tenant init "$@"; }
ai-tenant-promote()         { agentsmith tenant promote "$@"; }
ai-onprem-deploy-scaffold() { agentsmith tenant onprem-scaffold "$@"; }
ai-stack-upgrade()          { agentsmith upgrade "$@"; }
ai-stack-scrub()            { agentsmith scrub "$@"; }
ai-stack-uninstall()        { agentsmith uninstall "$@"; }
