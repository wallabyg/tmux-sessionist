#!/usr/bin/env bash

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "$CURRENT_DIR/helpers.sh"

main() {
	local client="$1"
	local mode="$(get_tmux_option '@sessionist-fzf-target' 'sessions')"
	local candidates selection target

	if [ "$mode" = 'windows' ]; then
		candidates=$(tmux list-windows -a -F $'#{session_id}:#{window_id}\t#{session_name}:#{window_index}: #{window_name}') || return
	else
		mode='sessions'
		candidates=$(tmux list-sessions -F $'#{session_id}\t#{session_name} (#{session_windows} windows)') || return
	fi
	[ -n "$candidates" ] || return 0

	# Keep IDs in the output but hide them from the searchable display.
	# Cancellation is a no-op; never send an empty target to tmux.
	# Global fzf options may open a nested popup or change the output format.
	selection=$(printf '%s\n' "$candidates" |
		FZF_DEFAULT_OPTS= FZF_DEFAULT_OPTS_FILE= \
		fzf --delimiter=$'\t' --with-nth=2.. --no-multi \
			--layout=reverse --prompt="$mode> ") || return 0
	[ -n "$selection" ] || return 0
	target="${selection%%$'\t'*}"

	if [ "$mode" = 'windows' ]; then
		[[ "$target" =~ ^\$[0-9]+:@[0-9]+$ ]] || return 0
		tmux select-window -t "$target" || return
		target="${target%%:*}"
	else
		[[ "$target" =~ ^\$[0-9]+$ ]] || return 0
	fi
	tmux switch-client -c "$client" -t "$target"
}

main "$@"
