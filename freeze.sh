#!/usr/bin/env bash
set -eu
msg() {
    word="${1-}"; shift
    case "$word" in
        Create | Install | Update) COLOR='1;35' ;;  # green
        Clean | Fix | Check)       COLOR='1;33' ;;  # yellow
        Freeze)                    COLOR='1;36' ;;  # cyan
        Ohno)                      COLOR='1;31' ;;  # red
        -?*)                       COLOR='1;37' ;;  # white
    esac
    echo -e " \033[1;37m---> \033[1m\033[${COLOR}m${word}\033[1;37m ${*}\033[0m" >&2
}
etab() {
    if [ -t 1 ]
        then sed 's/^/      /'
        else cat
    fi
}
did_not_match() {
    msg Ohno the new freeze differs
    diff -U1 requirements.txt requirements.freezing.txt | etab
    [ -t 1 ] || exit 1  # end here if we're not in an interactive shell
    msg Freeze these changes to requirements.txt?
    [[ "$(read -ep ' [yN] '; echo $REPLY)" == [Yy]* ]] || exit 1 && {
        msg Update requirements.txt
        cp requirements.freezing.txt requirements.txt
    }
}

msg Create temporary virtualenv venv.freezing
python3 -m venv venv.freezing

msg Install dependencies to venv.freezing
venv.freezing/bin/pip --disable-pip-version-check install -qr requirements.thawed.txt

msg Freeze packages in venv.freezing to requirements.freezing.txt
venv.freezing/bin/pip freeze > requirements.freezing.txt

msg Clean system packages from requirements.freezing.txt
sed -e '/^\s*$/d' -e '/^#/d' requirements.system.txt \
    | while read dep; do sed -e "/^$dep/d" -i '' requirements.freezing.txt; done

msg Clean up venv.freezing
rm -fr venv.freezing/

msg Check if the new freeze maches the latest
diff -q requirements.freezing.txt requirements.txt >/dev/null || did_not_match

msg Clean requirements.freezing.txt
rm requirements.freezing.txt
