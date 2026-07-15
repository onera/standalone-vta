# Bash / Zsh tab completion for the ./mill wrapper, with cleaned descriptions.
#
# On <Tab> it calls `mill --tab-complete`, which resolves the task tree live and
# prints each candidate followed by its description (the task's `/** ... */` doc
# comment in the *.mill build files). Descriptions are cleaned for display:
# javadoc tags (@param, @note, @see, ...) are dropped, `[[Foo]]` links are
# unwrapped to `Foo`, and whitespace is collapsed.
#
# If fzf is installed, <Tab> opens an fzf drill-down picker: names + the first
# sentence on the left, the full cleaned description wrapped over ~4 lines in a
# bottom preview, and dot-hierarchy navigation:
#     Tab    drill deeper: reload with the selected module's children (or accept
#            it if it is a leaf task)
#     Enter  accept the highlighted path as-is and leave the picker -> completes
#            to `<path>` at whatever level you are on
#     Left   go up one level (moves the cursor instead while a query is typed)
#     Esc    close the picker
# An already-typed token opens fzf at the matching level (`./mill examples<Tab>`
# opens inside examples). The logic lives in the sibling `mill-fzf-level` helper.
# Without fzf it falls back to the native completion menu with one cleaned line
# per candidate (first sentence, truncated to the terminal width). Tasks without
# a doc comment complete as a bare name either way.
#
# The fzf-vs-native choice auto-detects fzf by default. Set MILL_COMPLETION_FZF
# before sourcing (or export it in your rc) to force one front-end:
#     unset / auto            auto-detect (default): fzf when interactive and
#                             installed, otherwise the native menu
#     0 / off / no / false    force the basic native menu, even if fzf is
#                             installed (still shows each task's description)
#     1 / on / yes / true     prefer fzf; falls back to the native menu when fzf
#                             or the mill-fzf-level helper is unavailable
#
# Enable it by sourcing this file from your shell startup, e.g. add to
# ~/.bashrc or ~/.zshrc (adjust the path to your clone):
#
#     source /path/to/standalone-vta/tools/completions/mill-completion.sh
#
# It registers completion for both `mill` and `./mill`.

# Directory holding this file and the mill-fzf-level helper (resolve symlinks so
# it points at the real tools/ dir even when this file is symlinked).
if [ -n "${ZSH_VERSION:-}" ]; then
  _mill_src="${(%):-%x}"
else
  _mill_src="${BASH_SOURCE[0]}"
fi
_mill_tools_dir="$(cd -- "$(dirname -- "$(readlink -f -- "$_mill_src" 2>/dev/null || printf '%s' "$_mill_src")")" 2>/dev/null && pwd)"
unset _mill_src

# Clean raw "name<pad>description" lines into TSV rows "name<TAB>short<TAB>full":
#   full  = description with javadoc tags dropped, [[Foo]] unwrapped, ws collapsed
#   short = full up to the first ". " (sentence boundary)
# `mill --tab-complete` emits flattened Cross modules, so the same name can appear
# twice - once with its description and once bare (e.g. `examples`). Collapse to
# one row per name, keeping the row that carries a description, so the native menu
# does not list a task twice. A single awk pass so large candidate sets don't fork
# a process per line.
_mill_awk_rows() {
  awk '
  {
    line = $0
    if (match(line, /^[^ \t]+/)) { name = substr(line, 1, RLENGTH); rest = substr(line, RLENGTH + 1) }
    else { name = line; rest = "" }
    sub(/^[ \t]+/, "", rest)
    full = rest
    # drop everything from the first javadoc tag (longest alternatives first)
    if (match(full, / @(returns|return|param|note|see|throws|example|group)([^A-Za-z]|$)/))
      full = substr(full, 1, RSTART - 1)
    gsub(/\[\[/, "", full); gsub(/\]\]/, "", full)   # unwrap [[Foo]] -> Foo
    gsub(/[ \t]+/, " ", full)                        # collapse whitespace
    sub(/^ /, "", full); sub(/ $/, "", full)
    short = full
    if (match(short, /\. /)) short = substr(short, 1, RSTART)   # up to first ". "
    row = name "\t" short "\t" full
    if (!(name in seen)) { seen[name] = 1; order[++n] = name; keep[name] = row; if (full != "") hasdesc[name] = 1 }
    else if (full != "" && !(name in hasdesc)) { keep[name] = row; hasdesc[name] = 1 }
  }
  END { for (i = 1; i <= n; i++) print keep[order[i]] }'
}

# $1 = mill launcher, $2 = already-typed token. Opens the fzf drill-down picker
# (dot-hierarchy navigation via the mill-fzf-level helper) at the level matching
# the token, and prints the chosen path (empty if cancelled). Exports for fzf's
# binding subshells:
#   MILL_EXE - which mill launcher the helper queries
#   PATH     - so the bindings can call `mill-fzf-level` by bare name
#   SHELL    - force POSIX sh for binding commands (deterministic quoting)
_mill_fzf() {
  local -x MILL_EXE="$1"
  local -x PATH="$_mill_tools_dir:$PATH"
  local res prefix query prompt
  res=$("$_mill_tools_dir/mill-fzf-level" resolve "$2" 2>/dev/null)
  prefix=${res%%$'\t'*}
  query=${res#*$'\t'}
  prompt='> '
  [ -n "$prefix" ] && prompt="$prefix > "
  # Fullscreen (alt-screen), NOT --height: a `complete`-driven completion function
  # cannot force a readline/zle redraw the way fish's `commandline -f repaint` does,
  # so with --height fzf leaves the cursor mispositioned and readline repaints only
  # the completed word - the prompt and the `./mill ` prefix visually vanish. The
  # alt-screen save/restore keeps the original prompt line intact. (The fish
  # front-end can and does use --height because it repaints explicitly.)
  "$_mill_tools_dir/mill-fzf-level" level "$prefix" 2>/dev/null | SHELL=/bin/sh fzf \
    --ansi --reverse --prompt "$prompt" --query="$query" \
    --delimiter=$'\t' --with-nth=2,3 --nth=1 \
    --preview 'printf "%s\n" {4}' --preview-window=down:4:wrap \
    --bind 'tab:transform:mill-fzf-level drill {1}' \
    --bind 'left:transform:mill-fzf-level up' \
    | sed $'s/\t.*//'
}

# Decide whether the fzf drill-down picker should be used, folding in the
# MILL_COMPLETION_FZF override (see the header). Returns success (0) when fzf
# should handle completion:
#   0/off/no/false  -> never (force the basic native menu)
#   1/on/yes/true, auto, or unset -> use fzf when it is installed and the
#                                    mill-fzf-level helper is executable
# Interactivity is checked by the caller (it is shell-specific).
_mill_want_fzf() {
  case "${MILL_COMPLETION_FZF:-auto}" in
    0|off|no|false|OFF|NO|FALSE) return 1 ;;
  esac
  command -v fzf >/dev/null 2>&1 && [ -x "$_mill_tools_dir/mill-fzf-level" ]
}

_mill_bash() {
  local IFS=$'\n'
  shopt -s checkwinsize 2>/dev/null   # keep $COLUMNS current
  local raw=( $("${COMP_WORDS[0]}" --tab-complete "$COMP_CWORD" "${COMP_WORDS[@]}" 2>/dev/null) )

  if [[ $- == *i* ]] && _mill_want_fzf && (( ${#raw[@]} > 0 )); then
    local chosen
    chosen=$(_mill_fzf "${COMP_WORDS[0]}" "${COMP_WORDS[COMP_CWORD]}")
    if [ -n "$chosen" ]; then COMPREPLY=( "$chosen" ); else COMPREPLY=(); fi
    return
  fi

  compopt -o nospace 2>/dev/null
  local cols="${COLUMNS:-80}" name short full line
  local trimmed=()
  while IFS=$'\t' read -r name short full; do
    [ -n "$short" ] && line="$name  $short" || line="$name"
    (( ${#line} > cols )) && line="${line:0:cols-3}..."
    trimmed+=( "$line" )
  done < <(printf '%s\n' "${raw[@]}" | _mill_awk_rows)
  COMPREPLY=( "${trimmed[@]}" )
}

_mill_zsh() {
  local -a raw
  raw=("${(f)$($words[1] --tab-complete "$((CURRENT - 1))" $words 2>/dev/null)}")

  if [[ -o interactive ]] && _mill_want_fzf && (( ${#raw} > 0 )); then
    local chosen
    chosen=$(_mill_fzf "$words[1]" "$words[CURRENT]")
    [ -n "$chosen" ] && compadd -- "$chosen"
    return
  fi

  local cols="${COLUMNS:-80}" name short full line
  local -a opts trimmed
  while IFS=$'\t' read -r name short full; do
    opts+=( "$name" )
    [ -n "$short" ] && line="$name  $short" || line="$name"
    (( ${#line} > cols )) && line="${line:0:cols-3}..."
    trimmed+=( "$line" )
  done < <(printf '%s\n' $raw | _mill_awk_rows)
  compadd -S '' -d trimmed -- $opts
}

if [ -n "${ZSH_VERSION:-}" ]; then
  autoload -Uz compinit
  compinit
  compdef _mill_zsh mill
  compdef _mill_zsh './mill' 2>/dev/null
elif [ -n "${BASH_VERSION:-}" ]; then
  complete -F _mill_bash mill ./mill
fi
