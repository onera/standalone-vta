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
# A token starting with `-D` is completed as a JVM system property instead of a
# task: `-D<Tab>` lists the `-Dvta.*` keys this build reads, and `-Dvta.<key>=<Tab>`
# lists that key's values where they form a closed set (config JSONs, boards,
# true/false, directories). These always use the native menu, never fzf. Doing
# this requires shadowing the stock mill.fish - see the sibling fish/mill.fish
# and the comment above the $fish_complete_path line below.
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

# --- -D system properties ---------------------------------------------------

# `mill --tab-complete` advertises the `-D` flag but has no values for it (it
# resolves tasks, not JVM properties), so the build's own `-Dvta.*` knobs are
# completed here instead. Two levels: the bare key list on `-D<Tab>`, then the
# candidate values on `-Dvta.<key>=<Tab>` for the keys with a closed set.

# Repo root for the *current* directory (walk up for build.mill). Deliberately
# not $__mill_tools_dir/../..: with git worktrees the checkout you run ./mill in
# is not the one this file was sourced from, and the value lists must describe
# the former. Empty (status 1) outside a Mill repo, which suppresses -D
# completion entirely rather than offering keys that no build reads.
function __mill_repo_root
    set -l dir (pwd -P)
    while test -n "$dir"
        if test -f "$dir/build.mill"
            echo $dir
            return 0
        end
        test "$dir" = /; and break
        set dir (path dirname $dir)
    end
    return 1
end

# The -Dvta.* keys the build reads, as "key=<TAB>description" rows. Keep in sync
# with the sys.props lookups in util.mill and vta/*/package.mill.
function __mill_vta_keys
    printf '%s\t%s\n' \
        vta.config.file= 'Active hardware config JSON in config/ (default vta_config.json)' \
        vta.config.fromResources= 'Load the config from test resources instead of config/' \
        vta.board.name= 'Target FPGA board in vta/fpga/boards/ (default zcu104)' \
        vta.ddr.base= 'DDR base for the baremetal codegen; match the board (default 0x0)' \
        vta.xil.dir= 'Shallow root for Vivado/Vitis project trees (Windows long-path fix)' \
        vta.compilerOutDir= 'emitVtaPostSynthTb: compiler_output dir to replay' \
        vta.simOutDir= 'emitVtaPostSynthTb: fsim --dump-layers output dir' \
        vta.layers= 'emitVtaPostSynthTb: subset of layers to emit' \
        vta.reloStride= 'emitVtaPostSynthTb: relocation stride' \
        vta.perLayerTimeout= 'emitVtaPostSynthTb: per-layer timeout'
end

# Emit "<key>=<name><TAB>desc" for every *.json in $dir (nothing if absent).
# $ext controls the value form and must match how the build reads the property:
#   keep  - file name with extension, as vta.config.file wants (util.mill:41,
#           whose default is the literal "vta_config.json")
#   strip - base name only, as vta.board.name wants (boardNames maps _.baseName
#           over the dir, util.mill:122, so the cross keys are "zcu104" etc.)
function __mill_vta_json_values --argument-names key dir desc ext
    test -d "$dir"; or return
    for f in (path filter -f "$dir"/*.json 2>/dev/null)
        set -l name (path basename $f)
        test "$ext" = strip; and set name (path change-extension '' $name)
        printf '%s\t%s\n' "$key=$name" "$desc"
    end
end

# Emit "<key>=<dir>/" candidates for a path-valued property.
function __mill_vta_dir_values --argument-names key val
    for d in (__fish_complete_directories "$val" 2>/dev/null)
        printf '%s\n' "$key=$d"
    end
end

# Candidates for the current -D token. Fish matches these against the token with
# the leading -D stripped, so every row is emitted without it. Keys whose value
# is free-form (layers, reloStride, perLayerTimeout) deliberately fall through to
# nothing rather than re-offering the key the user has already finished typing.
function __mill_vta_props
    set -l root (__mill_repo_root); or return
    set -l tok (string replace -r '^-D' '' -- (commandline -ct))
    switch $tok
        case 'vta.config.file=*'
            __mill_vta_json_values vta.config.file $root/config 'hardware config' keep
        case 'vta.board.name=*'
            __mill_vta_json_values vta.board.name $root/vta/fpga/boards 'FPGA board' strip
        case 'vta.config.fromResources=*'
            printf '%s\t%s\n' \
                vta.config.fromResources=true 'read the config from test resources' \
                vta.config.fromResources=false 'read the config from config/'
        case 'vta.ddr.base=*'
            printf '%s\t%s\n' \
                vta.ddr.base=0x0 default \
                vta.ddr.base=0x10000000 'typical external-DDR base'
        case 'vta.compilerOutDir=*' 'vta.simOutDir=*'
            __mill_vta_dir_values \
                (string replace -r '=.*$' '' -- $tok) \
                (string replace -r '^[^=]*=' '' -- $tok)
        case '*=*'
            # a key with a free-form value: nothing to suggest
        case '*'
            __mill_vta_keys
    end
end

# The `complete -c mill -s D` registration deliberately lives in the sibling
# fish/mill.fish rather than here, because it has to *replace* the stock
# mill.fish that ships in ~/.config/fish/completions: that file declares -D as a
# boolean flag, so fish reads a typed `-Dvta.c` as a short-flag cluster and
# offers nothing (bare `-D` even completes to `-Db`, `-Dd`, ... - mill's other
# short flags, not JVM properties).
#
# Re-declaring -D with --require-parameter here does not help: fish autoloads
# completion files lazily, on the first completion of `mill`, which is *after*
# this file is sourced - so the stock declaration lands last and wins. Sourcing
# it early by hand does not mark it loaded either; it still autoloads and
# clobbers. Prepending our own directory to $fish_complete_path makes fish
# autoload ours *instead* (first match in the path wins), which sidesteps the
# ordering entirely.
#
# Note this shadows the stock mill.fish completely, so its flag list stops being
# offered. That list is Ammonite-era (--repl, --predef, --thin, --no-default-predef)
# and no longer matches Mill 1.x; its task completion (`mill resolve __`) is
# superseded by __mill_complete_native above.
if not contains $__mill_tools_dir/fish $fish_complete_path
    set -p fish_complete_path $__mill_tools_dir/fish
end

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
    # A -D<key>=<value> token is a flag argument, not a task path. The fzf picker
    # navigates the task dot-hierarchy and would read the dots in a property name
    # as module nesting, so hand these to the native menu regardless of fzf.
    if string match -q -- '-D*' (commandline -ct)
        commandline -f complete
        return
    end
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
