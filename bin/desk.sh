# fman.sh
#
# Description: desk for doing work on fman.
# (see https://github.com/jamesob/desk)

# To install this file, symlink it to your local desks directory:
#   ln -s <ABSOLUTE PATH TO THIS FILE> ~/.desk/desks/fman.sh
# You can then switch to the desk with the command:
#   desk . fman

# Find the directory this script lies in, even when the script is called via a
# symlink, as per the installation instructions above. Copied from
# http://stackoverflow.com/a/246128/1839209:
if [[ $SHELL == */zsh ]]; then
	SOURCE="$0"
else
	SOURCE="${BASH_SOURCE[0]}"
fi
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
THIS_SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

PROJECT_DIR="$THIS_SCRIPT_DIR/.."

cd "$PROJECT_DIR"
source .venv/bin/activate

PS1="(fman) \h:\W \u\$ "

function build {
	python build.py "$@"
}

alias run='python build.py run'
alias clean='python build.py clean'
alias freeze='python build.py freeze'
alias sign='python build.py sign'
alias installer='python build.py installer'
alias sign_installer='python build.py sign_installer'
alias publish='python build.py publish'
alias release='python build.py release'
alias tests='python build.py test'
alias arch-docker-image='python build.py buildvm arch'
alias arch='python build.py runvm arch'
alias ubuntu-docker-image='python build.py buildvm ubuntu'
alias ubuntu='python build.py runvm ubuntu'
alias fedora-docker-image='python build.py buildvm fedora'
alias fedora='python build.py runvm fedora'