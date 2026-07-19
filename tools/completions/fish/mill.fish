# Autoloaded completion for `mill`, shadowing the stock one in
# ~/.config/fish/completions.
#
# This file exists only so that fish's lazy autoload picks *our* -D declaration
# instead of the stock file's. It is reached because the sibling
# ../mill-completion.fish prepends this directory to $fish_complete_path; do not
# source it directly, and keep the two together.
#
# Everything else (task completion, the fzf picker, the Tab binding) is set up by
# ../mill-completion.fish, which also defines __mill_vta_props.
#
# --require-parameter (-r) is the load-bearing flag: it tells fish that -D takes
# a value, so a typed `-Dvta.config.file=` is routed to the -a candidates below
# instead of being parsed as a cluster of short flags.

complete -c mill -s D -r -f -a '(__mill_vta_props)' \
    -d 'Define a JVM system property (<k>=<v>)'
