#!/bin/bash
#
# Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
# PreToolUse hook of the writing subagents (designer, implementer, mechanical,
# integrator; the `hooks:` field of their frontmatter). It makes mechanical what
# `.claude/rules/subagents.md` says in words: a subagent never pushes, never
# amends, never forces, never writes under `upstream/` or under a `reference/`
# tree (the Kernel's pinned clone of another system), never cds into either, and never installs
# or downloads anything (`cargo install`, `rustup`, `brew`, `pip`, `npm`,
# `curl`, `wget`). Exit 2 refuses the call and hands the reason to the agent;
# anything else exits 0 at once. The main session has no such hook: pushing,
# installing and fetching are the user's, done from there on their word. A belt
# against a slip, not a wall against an adversary: a command built at run time
# is beyond a pattern.
payload=$(cat)
tool=$(printf '%s' "$payload" | jq -r '.tool_name // empty')
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')

refuse() {
    printf 'blocked by .claude/hooks/agent-guard.sh: %s (.claude/rules/subagents.md; the main session does this when the user asks)\n' "$1" >&2
    exit 2
}

guarded_path() {
    local p=$1
    case "$p" in /*) ;; *) p="${cwd:-.}/$p" ;; esac
    case "$p" in
    */upstream/*|*/upstream|*/reference/*|*/reference) return 0 ;;
    esac
    return 1
}

case "$tool" in
Edit|Write|NotebookEdit)
    path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -n "$path" ] || exit 0
    guarded_path "$path" && refuse "a subagent never writes under upstream/ or a reference tree ($path)"
    exit 0
    ;;
Bash) ;;
*) exit 0 ;;
esac

cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')
[ -n "$cmd" ] || exit 0
# `git`, with any `VAR=x` or `env` before it and an optional `-C <dir>`, as a shell word at
# the start of a command or after a separator.
G='(^|[;&|(`]|&&)[[:space:]]*((env|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*)[[:space:]]+)*git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+'
W='(^|[;&|(`]|&&)[[:space:]]*((env|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*)[[:space:]]+)*'

printf '%s\n' "$cmd" | grep -qE "${G}push([[:space:]]|$)" && refuse "a subagent never pushes"
printf '%s\n' "$cmd" | grep -qE "${G}commit[^;&|]*[[:space:]]--amend([[:space:]]|$)" && refuse "a subagent never amends a commit"
printf '%s\n' "$cmd" | grep -qE "${G}[a-z-]+[^;&|]*[[:space:]](-f|--force|--force-with-lease)([[:space:]]|$)" && \
    printf '%s\n' "$cmd" | grep -qE "${G}(push|branch|checkout|reset|clean|worktree)" && refuse "a subagent never forces anything in git"

# Installing and downloading are the user's.
printf '%s\n' "$cmd" | grep -qE "${W}cargo[[:space:]]+(\+[^[:space:]]+[[:space:]]+)?install([[:space:]]|$)" && refuse "a subagent never cargo-installs"
printf '%s\n' "$cmd" | grep -qE "${W}(rustup|brew|pip3?|npm|pnpm|yarn|gem|port)([[:space:]]|$)" && refuse "a subagent never installs tools"
printf '%s\n' "$cmd" | grep -qE "${W}(curl|wget|fetch|ftp)([[:space:]]|$)" && refuse "a subagent never downloads"

# `cd` into upstream/ or a reference tree (read them with `git show`, never from inside).
printf '%s\n' "$cmd" | grep -qE '(^|[;&|(]|&&)[[:space:]]*cd[[:space:]]+"?[^;&|[:space:]"]*(upstream|reference)(/|"|[[:space:]]|$)' && \
    refuse "a subagent never cds into upstream/ or a reference tree"

# `git -C <reference or upstream tree> <subcommand>`: only reading subcommands there.
while read -r sub; do
    case "$sub" in
    show|log|diff|grep|blame|ls-files|ls-tree|rev-parse|cat-file|status|describe|name-rev|rev-list|shortlog|merge-base|remote|branch|tag|config|var|count-objects) ;;
    *) refuse "a subagent never runs 'git $sub' in upstream/ or a reference tree" ;;
    esac
done < <(printf '%s\n' "$cmd" | grep -oE 'git[[:space:]]+-C[[:space:]]+"?[^[:space:]"]*(upstream|reference)(/[^[:space:]"]*)?"?[[:space:]]+[a-z-]+' | awk '{print $NF}')

# Writes under upstream/ or a reference tree: redirections, in-place edits, copies, moves,
# removals, mkdir, touch, chmod, git add/checkout/restore of a path there.
if printf '%s\n' "$cmd" | grep -qE '(upstream|reference)(/|$|"|[[:space:]])'; then
    printf '%s\n' "$cmd" | grep -qE '(>>?|[[:space:]]tee[[:space:]])[[:space:]]*"?[^[:space:]"]*(upstream|reference)/' && refuse "a subagent never writes under upstream/ or a reference tree"
    printf '%s\n' "$cmd" | grep -qE "${W}(rm|mv|cp|mkdir|rmdir|touch|chmod|chown|ln|sed[[:space:]]+-i|perl[[:space:]]+-i|install|truncate|dd)([[:space:]]|$)[^;&|]*(upstream|reference)(/|$|\"|[[:space:]])" && refuse "a subagent never changes upstream/ or a reference tree"
    printf '%s\n' "$cmd" | grep -qE "${G}(add|checkout|restore|rm|mv|stash|apply|am|clean)([[:space:]]|$)[^;&|]*(upstream|reference)(/|$|\"|[[:space:]])" && refuse "a subagent never stages or restores paths under upstream/ or a reference tree"
fi
exit 0
