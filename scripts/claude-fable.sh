#!/bin/zsh
# Start Claude Code on Fable 5.1 through the Harvard Bedrock gateway, billed to the HUIT key in .env.
# The key is read at launch and never written anywhere. Usage: scripts/claude-fable.sh [claude args]
cd "${0:A:h}/.." || exit 1
KEY=$(grep '^ANTHROPIC_API_KEY=' .env | cut -d= -f2- | tr -d "\"' ")
[[ -n $KEY ]] || { echo "ANTHROPIC_API_KEY is missing from .env" >&2; exit 1; }
exec env -u ANTHROPIC_API_KEY \
  CLAUDE_CODE_USE_BEDROCK=1 CLAUDE_CODE_SKIP_BEDROCK_AUTH=1 AWS_REGION=us-east-1 \
  ANTHROPIC_BEDROCK_BASE_URL=https://apis.huit.harvard.edu/ais-bedrock-llm/v2 \
  ANTHROPIC_CUSTOM_HEADERS="x-api-key: $KEY" \
  ANTHROPIC_MODEL=us.anthropic.claude-fable-5-1 \
  ANTHROPIC_DEFAULT_HAIKU_MODEL=us.anthropic.claude-haiku-5-5 \
  claude "$@"
