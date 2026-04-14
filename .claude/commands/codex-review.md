Run an adversarial security and rule-compliance review of $ARGUMENTS using the local qwen2.5-coder:7b model.

Execute this shell command and display the full output:

```bash
ollama run qwen2.5-coder:7b "You are a hostile security reviewer. Find every flaw in the following code. Check for: (1) hardcoded secrets or tokens, (2) outbound connections other than Ollama localhost:11434 and api.telegram.org, (3) rule violations — R1=Ollama-only inference, R5=no money/fund actions, R8=no file writes outside ai-holding-company/, R10=silence by default, R11=no OpenClaw/Docker/broker, (4) crash or silent-failure edge cases, (5) missing input validation. Be specific and unsparing. List every issue.\n\nCODE:\n$(cat $ARGUMENTS)"
```

For every issue raised: fix it immediately. If you disagree, add a comment `# CODEX-DISPUTE: <reasoning>` and move on. Do not proceed to the next component until all issues are resolved or disputed.
