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
# A token starting with `-` is completed as a flag rather than a task, always
# through the native menu and never fzf:
#     * mill's own options come from `mill --tab-complete` like everything else,
#       so they track the installed mill version. A bare `-` lists the short flags
#       and the long ones together; `--<Tab>` lists the long ones.
#     * `-D` is completed as a JVM system property: `-D<Tab>` lists the `-Dvta.*`
#       keys this build reads, and `-Dvta.<key>=<Tab>` lists that key's values
#       where they form a closed set (config JSONs, boards, true/false, dirs).
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
# twice - once with its description and once bare (e.g. `examples`). The same goes
# for its single-match output shape, which is the bare name followed by
# "name: description" on a second line; a trailing `:` is stripped off the parsed
# name so those two merge (`:` cannot appear in a mill task segment or flag, so no
# real name is truncated). Collapse to one row per name, keeping the row that
# carries a description, so the native menu does not list a task twice. A single
# awk pass so large candidate sets don't fork a process per line.
_mill_awk_rows() {
  awk '
  {
    line = $0
    if (match(line, /^[^ \t]+/)) { name = substr(line, 1, RLENGTH); rest = substr(line, RLENGTH + 1) }
    else { name = line; rest = "" }
    sub(/:$/, "", name)                              # "name: desc" -> "name"
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

# --- -D system properties ---------------------------------------------------
#
# `mill --tab-complete` advertises the -D flag but has no values for it (it
# resolves tasks, not JVM properties), so the build's own -Dvta.* knobs are
# completed here. Two levels: the bare key list on `-D<Tab>`, then values on
# `-Dvta.<key>=<Tab>` for the keys with a closed set.

# Repo root for the *current* directory (walk up for build.mill). Deliberately
# not $_mill_tools_dir/../..: with git worktrees the checkout you run ./mill in
# is not the one this file was sourced from, and the value lists must describe
# the former. Fails outside a Mill repo, which suppresses -D completion rather
# than offering keys no build reads.
_mill_repo_root() {
  local dir="$PWD"
  while [ -n "$dir" ]; do
    if [ -f "$dir/build.mill" ]; then printf '%s' "$dir"; return 0; fi
    [ "$dir" = / ] && break
    dir="$(dirname -- "$dir")"
  done
  return 1
}

# The -Dvta.* keys the build reads. Keep in sync with the sys.props lookups in
# build.mill, vta/pipeline.mill and vta/*/package.mill (and with __mill_vta_keys
# in the fish file).
_mill_vta_keys() {
  cat <<'EOF'
vta.config.file=
vta.config.fromResources=
vta.board.name=
vta.ddr.base=
vta.xil.out=
vta.compilerOutDir=
vta.simOutDir=
vta.layers=
vta.reloStride=
vta.perLayerTimeout=
EOF
}

# $1 = the full -D token typed so far. Prints one candidate per line, each
# carrying the leading -D. Value forms must match how the build reads them:
# vta.config.file keeps the .json extension (build.mill's defaultConfigName is the
# literal "vta_config.json"), vta.board.name drops it (boardNames maps
# _.baseName over the dir, so the cross keys are "zcu104" etc.).
# Keys with a free-form value print nothing.
_mill_vta_props() {
  local tok="${1#-D}" root f d key val
  root=$(_mill_repo_root) || return 0
  case "$tok" in
    vta.config.file=*)
      for f in "$root"/config/*.json; do
        [ -f "$f" ] && printf -- '-Dvta.config.file=%s\n' "${f##*/}"
      done ;;
    vta.board.name=*)
      for f in "$root"/vta/fpga/boards/*.json; do
        [ -f "$f" ] || continue
        f="${f##*/}"; printf -- '-Dvta.board.name=%s\n' "${f%.json}"
      done ;;
    vta.config.fromResources=*)
      printf -- '-Dvta.config.fromResources=%s\n' true false ;;
    vta.ddr.base=*)
      printf -- '-Dvta.ddr.base=%s\n' 0x0 0x10000000 ;;
    vta.compilerOutDir=*|vta.simOutDir=*)
      key="${tok%%=*}"; val="${tok#*=}"
      for d in "$val"*/; do
        [ -d "$d" ] && printf -- '-D%s=%s\n' "$key" "$d"
      done ;;
    *=*) ;;   # key with a free-form value: nothing to suggest
    *) _mill_vta_keys | sed 's/^/-D/' ;;
  esac
}

_mill_bash() {
  local IFS=$'\n'

  # `=` is in COMP_WORDBREAKS, so bash splits -Dvta.config.file=vta_c into
  # several words: rebuild the real token from the line, and strip the part
  # bash already considers typed off each candidate before handing it back.
  local tok="${COMP_LINE:0:COMP_POINT}"; tok="${tok##* }"
  if [[ $tok == -D* ]]; then
    local cur="${COMP_WORDS[COMP_CWORD]}" prefix cand
    prefix="${tok%"$cur"}"
    COMPREPLY=()
    for cand in $(compgen -W "$(_mill_vta_props "$tok")" -- "$tok"); do
      COMPREPLY+=( "${cand#"$prefix"}" )
    done
    compopt -o nospace 2>/dev/null
    return
  fi

  shopt -s checkwinsize 2>/dev/null   # keep $COLUMNS current
  local raw=( $("${COMP_WORDS[0]}" --tab-complete "$COMP_CWORD" "${COMP_WORDS[@]}" 2>/dev/null) )

  # Mill answers a bare `-` with its short flags only, so ask again with `--` to
  # show the long flags in the same menu.
  if [[ $tok == - ]]; then
    local dd=( "${COMP_WORDS[@]}" ); dd[COMP_CWORD]='--'
    raw+=( $("${COMP_WORDS[0]}" --tab-complete "$COMP_CWORD" "${dd[@]}" 2>/dev/null) )
  fi

  # Flags are not task paths, and the fzf picker only navigates the task
  # dot-hierarchy, so a `-` token always uses the native menu below.
  if [[ $- == *i* ]] && [[ $tok != -* ]] && _mill_want_fzf && (( ${#raw[@]} > 0 )); then
    local chosen
    chosen=$(_mill_fzf "${COMP_WORDS[0]}" "${COMP_WORDS[COMP_CWORD]}")
    if [ -n "$chosen" ]; then COMPREPLY=( "$chosen" ); else COMPREPLY=(); fi
    return
  fi

  compopt -o nospace 2>/dev/null
  local cols="${COLUMNS:-80}" name short full line
  local names=() trimmed=()
  while IFS=$'\t' read -r name short full; do
    names+=( "$name" )
    [ -n "$short" ] && line="$name  $short" || line="$name"
    # $(( )) around the length is load-bearing for zsh: it reads the `cols` in a
    # bare ${line:0:cols-3} as a history modifier and aborts with "unrecognized
    # modifier". Bash accepts either form.
    (( ${#line} > cols )) && line="${line:0:$((cols - 3))}..."
    trimmed+=( "$line" )
  done < <(printf '%s\n' "${raw[@]}" | _mill_awk_rows)
  # bash has no display-vs-value split (zsh's `compadd -d`), so the descriptions
  # ride along in COMPREPLY and are only ever *shown* - with two or more entries
  # bash inserts their common prefix, which is the shared part of the names. A
  # lone entry would be inserted whole, description and all, so hand back the
  # bare name in that case.
  if (( ${#trimmed[@]} == 1 )); then COMPREPLY=( "${names[0]}" ); else COMPREPLY=( "${trimmed[@]}" ); fi
}

_mill_zsh() {
  # zsh keeps -Dvta.config.file=vta_c as one word (no COMP_WORDBREAKS split), so
  # the token is used as-is and candidates are added whole.
  local tok="$words[CURRENT]"
  if [[ $tok == -D* ]]; then
    local -a cands
    cands=("${(f)$(_mill_vta_props "$tok")}")
    compadd -S '' -- ${(M)cands:#${tok}*}
    return
  fi

  local -a raw
  raw=("${(f)$($words[1] --tab-complete "$((CURRENT - 1))" $words 2>/dev/null)}")

  # Mill answers a bare `-` with its short flags only, so ask again with `--` to
  # show the long flags in the same menu.
  if [[ $tok == - ]]; then
    local -a dd; dd=($words); dd[CURRENT]='--'
    raw+=("${(f)$($words[1] --tab-complete "$((CURRENT - 1))" $dd 2>/dev/null)}")
  fi

  # Flags are not task paths, and the fzf picker only navigates the task
  # dot-hierarchy, so a `-` token always uses the native menu below.
  if [[ -o interactive ]] && [[ $tok != -* ]] && _mill_want_fzf && (( ${#raw} > 0 )); then
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
    # $(( )) around the length is load-bearing for zsh: it reads the `cols` in a
    # bare ${line:0:cols-3} as a history modifier and aborts with "unrecognized
    # modifier". Bash accepts either form.
    (( ${#line} > cols )) && line="${line:0:$((cols - 3))}..."
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
