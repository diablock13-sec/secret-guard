#!/bin/sh
# Demo secret-guard di repo sementara. Rahasia palsu dirakit saat runtime.
set -e
SG="uv run --project $HOME/Roadmap_altop/secret-guard secret-guard"
D=$(mktemp -d /tmp/demo-sg.XXXXXX)
cd "$D"
git init -q
git config user.name demo
git config user.email demo@example.com
export PS1='$ '

say() { printf '\n$ %s\n' "$*"; sleep 1; }

say "secret-guard install-hook"
$SG install-hook
sleep 1

AWS="AKIA$(printf 'ABCDEFGH')$(printf 'IJKLMNOP')"
say "echo 'aws_key = \"<kunci>\"' > config.py && git add config.py"
printf 'aws_key = "%s"\n' "$AWS" > config.py
git add config.py
sleep 1

say "git commit -m 'tambah konfigurasi'"
set +e
git commit -q -m "tambah konfigurasi"
echo "(kode keluar: $?)"
set -e
sleep 2

say "git rm --cached config.py && echo 'print(1)' > app.py && git add app.py"
git rm -q --cached config.py
echo 'print(1)' > app.py
git add app.py
sleep 1

say "git commit -m 'tambah app'"
git commit -q -m "tambah app"
echo "(kode keluar: $?)"
sleep 2

cd /
rm -rf "$D"
