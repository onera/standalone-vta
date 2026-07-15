# Fish tab completion for the ./mill wrapper, with cleaned descriptions and an
# fzf picker that shows the full description over several lines.
#
# On <Tab> for a `mill` / `./mill` command line this calls `mill --tab-complete`
# and cleans each candidate's description (the task's `/** ... */` doc comment in
# the *.mill build files): javadoc tags (@param, @note, @see, ...) are dropped,
# `[[Foo]]` links are unwrapped to `Foo`, and whitespace is collapsed.
#
# Two front-ends share that cleaning:
#   * native completion (`complete -c mill`)  - one cleaned line per candidate,
#     works with no extra dependency.
#   * an fzf drill-down picker (when fzf is installed) - names on the left, the
#     full cleaned description wrapped over ~4 lines in a bottom preview, and
#     dot-hierarchy navigation:
#         Tab    drill deeper: reload the list with the selected module's
#                children (or accept it if it is a leaf task)
#         Enter  accept the highlighted path as-is and leave the picker ->
#                inserts `./mill <path>` at whatever level you are on
#         Left   go up one level (moves the cursor instead while a query is typed)
#         Esc    close the picker
#     An already-typed token opens fzf at the matching level (`./mill examples<Tab>`
#     opens inside examples). The logic lives in the sibling `mill-fzf-level` helper.
# Tab only diverts to fzf when the command line is a mill command; every other
# command falls through to fish's normal completion untouched.
#
# The fzf-vs-native choice auto-detects fzf by default. Set MILL_COMPLETION_FZF
# before sourcing (or in your config) to force one front-end:
#     unset / auto            auto-detect (default): fzf when installed, else the
#                             native completion menu
#     0 / off / no / false    force the basic native menu, even if fzf is
#                             installed (still shows each task's description)
#     1 / on / yes / true     prefer fzf; falls back to the native menu when fzf
#                             or the mill-fzf-level helper is unavailable
#
# Enable it by sourcing this file from ~/.config/fish/config.fish (it binds Tab,
# so it must run for interactive shells; adjust the path to your clone):
#
#     source /path/to/standalone-vta/tools/completions/mill-completion.fish
#
# The `mill-fzf-level` helper is found relative to this file, so keep the two
# together in tools/completions/.

# Directory holding this file and the mill-fzf-level helper (resolve symlinks so
# it points at the real tools/completions/ dir even when sourced via a symlink).
set -g __mill_tools_dir (path dirname (path resolve (status filename)))

# --- description cleaning ---------------------------------------------------

# Clean a raw mill description into readable prose: drop everything from the
# first javadoc tag, unwrap [[Foo]] links, collapse whitespace.
function __mill_clean --argument-names raw
    printf '%s' $raw \
        | string replace -r ' @(param|note|see|return|returns|throws|example|group)\b.*$' '' \
        | string replace -ra '\[\[([^]]+)\]\]' '$1' \
        | string replace -ra '\s+' ' ' \
        | string trim
end

# First sentence of a cleaned description (everything up to the first ". ").
function __mill_short --argument-names clean
    string replace -r '\. .*$' '.' -- $clean
end

# Emit one "name<TAB>short<TAB>full" row per completion candidate for the
# current command line.
function __mill_rows
    set -l tokens (commandline -opc)
    test (count $tokens) -ge 1; or return
    set -l current (commandline -ct)
    set -l cword (count $tokens)
    set -l exe $tokens[1]
    # Quote "$current" so an empty current token is still passed as one word.
    command $exe --tab-complete $cword $tokens "$current" 2>/dev/null | while read -l line
        test -n "$line"; or continue
        set -l name (string replace -r '^(\S+).*$' '$1' -- $line)
        set -l raw (string replace -r '^\S+\s*' '' -- $line)
        set -l full (__mill_clean "$raw")
        set -l short (__mill_short "$full")
        printf '%s\t%s\t%s\n' $name $short $full
    end
end

# --- native completion ------------------------------------------------------

# name<TAB>short (drop the full field, and any trailing tab when short is empty).
# `mill --tab-complete` emits flattened Cross modules, so the same name can
# appear twice - once with its description and once bare (e.g. `examples`). Fish
# keeps both as distinct candidates (their descriptions differ), showing the name
# twice with the description on only one. Collapse to one row per name, keeping
# the row that carries a description.
function __mill_complete_native
    __mill_rows \
        | awk -F '\t' '
            { name = $1
              if (!(name in seen)) { seen[name] = 1; order[++n] = name; row[name] = $0; if ($3 != "") hasdesc[name] = 1 }
              else if ($3 != "" && !(name in hasdesc)) { row[name] = $0; hasdesc[name] = 1 }
            }
            END { for (i = 1; i <= n; i++) print row[order[i]] }' \
        | string replace -r '^([^\t]*\t[^\t]*)\t.*$' '$1' \
        | string replace -r '\t$' ''
end

complete -c mill -f -a '(__mill_complete_native)'

# --- fzf picker -------------------------------------------------------------

function __mill_fzf_complete
    set -l tokens (commandline -opc)
    test (count $tokens) -ge 1; or return
    set -l exe $tokens[1]

    # Export state for fzf and the shell it spawns for the enter/left bindings:
    #   MILL_EXE  - which mill launcher the helper queries
    #   PATH      - so the bindings can call `mill-fzf-level` by bare name
    #   SHELL     - force POSIX sh for binding commands (deterministic quoting)
    set -lx MILL_EXE $exe
    set -lx PATH $__mill_tools_dir $PATH
    set -lx SHELL /bin/sh

    # Open at the level matching an already-typed token (resolve -> "prefix\tquery").
    set -l res ($__mill_tools_dir/mill-fzf-level resolve (commandline -ct) 2>/dev/null | string collect)
    set -l parts (string split -m1 \t -- $res)
    set -l prefix $parts[1]
    set -l query $parts[2]
    set -l prompt '> '
    test -n "$prefix"; and set prompt "$prefix > "

    set -l picked ($__mill_tools_dir/mill-fzf-level level "$prefix" 2>/dev/null \
        | fzf --ansi --height 45% --reverse --prompt "$prompt" --query "$query" \
            --delimiter \t --with-nth 2,3 --nth 1 \
            --preview 'printf "%s\n" {4}' --preview-window 'down:4:wrap' \
            --bind 'tab:transform:mill-fzf-level drill {1}' \
            --bind 'left:transform:mill-fzf-level up' \
        | string replace -r '\t.*$' '')
    if test -n "$picked"
        commandline -rt -- $picked
    end
    commandline -f repaint
end

# --- Tab binding ------------------------------------------------------------

# Whether the fzf drill-down picker should handle Tab, folding in the
# MILL_COMPLETION_FZF override (see the header): 0/off/no/false forces the basic
# native menu; auto/1/on/yes/true (or unset) uses fzf when it is installed and
# the mill-fzf-level helper is executable.
function __mill_want_fzf
    switch (string lower -- "$MILL_COMPLETION_FZF")
        case 0 off no false
            return 1
    end
    type -q fzf; and test -x $__mill_tools_dir/mill-fzf-level
end

function __mill_tab
    set -l buf (commandline -pc)
    if string match -qr '^\s*(\./)?mill\b' -- $buf; and __mill_want_fzf
        __mill_fzf_complete
    else
        commandline -f complete
    end
end

if status is-interactive
    bind \t __mill_tab
    bind -M insert \t __mill_tab 2>/dev/null
end
