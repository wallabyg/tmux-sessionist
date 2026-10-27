#!/usr/bin/env bash

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "$CURRENT_DIR/helpers.sh"

fzf_available() {
	[ "$(get_tmux_option '@sessionist-fzf' 'on')" != 'off' ] &&
		command -v fzf >/dev/null 2>&1 &&
		tmux list-commands | command grep -q '^display-popup '
}

main() {
	if fzf_available; then
		local client="${1:-$(tmux display-message -p '#{client_name}')}"
		local command
		# Quote arguments for the shell used by display-popup, including paths
		# containing spaces or single quotes.
		command="bash '${CURRENT_DIR//\'/\'\\\'\'}/fzf_session.sh' '${client//\'/\'\\\'\'}'"
		if tmux display-popup -c "$client" -E -w 80% -h 60% "$command"; then
			return
		fi
	fi

	# displays tmux session list
	tmux run-shell -b "$CURRENT_DIR/list_sessions.sh"
	# goto command prompt
	tmux command -p session: "run '$CURRENT_DIR/switch_or_loop.sh \"%1\"'"
}
main "$@"
