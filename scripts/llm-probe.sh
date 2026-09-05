#!/usr/bin/env bash
# Is the local model serving actually alive? `/v1/models` answers 200 as long as the HTTP
# process exists, which is not the same thing: on 2026-09-04 mlx_lm.server's generation
# thread died of GPU OOM ([METAL] Insufficient Memory) while /v1/models kept answering,
# and every Utopia extraction call then hung to its 300 s timeout for a night. The only
# honest probe is a real completion and a real embedding, each with a short deadline.
#
#   scripts/llm-probe.sh                 # defaults below
#   CHAT_URL=... EMBED_URL=... scripts/llm-probe.sh
set -u
CHAT_URL=${CHAT_URL:-http://localhost:8080/v1}
CHAT_MODEL=${CHAT_MODEL:-mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit}
EMBED_URL=${EMBED_URL:-http://localhost:8766/v1}
EMBED_MODEL=${EMBED_MODEL:-Shitao/bge-m3}
DEADLINE=${DEADLINE:-30}
rc=0

probe() { # name url json jq-path
  local start end body
  start=$(date +%s.%N)
  body=$(curl -s -m "$DEADLINE" "$2" -H 'Content-Type: application/json' -d "$3" 2>/dev/null) || body=""
  end=$(date +%s.%N)
  if python3 - "$body" "$4" <<'PY' 2>/dev/null
import sys, json
d = json.loads(sys.argv[1])
for k in sys.argv[2].split("."):
    d = d[int(k)] if k.isdigit() else d[k]
assert d
PY
  then printf '%-6s ALIVE  %5.1fs  %s\n' "$1" "$(echo "$end - $start" | bc)" "$2"
  else printf '%-6s DEAD   >%ss  %s  %s\n' "$1" "$DEADLINE" "$2" "${body:0:80}"; rc=1
  fi
}

probe chat  "$CHAT_URL/chat/completions" \
  "{\"model\":\"$CHAT_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: ok\"}],\"max_tokens\":5}" \
  "choices.0.message.content"
probe embed "$EMBED_URL/embeddings" \
  "{\"model\":\"$EMBED_MODEL\",\"input\":[\"probe\"]}" \
  "data.0.embedding.0"
exit $rc
