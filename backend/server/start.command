#!/bin/zsh
set -eu
server_dir="${0:A:h}"
cd "$server_dir"
for candidate in "$server_dir/.venv/bin/python" "$server_dir/../.venv/bin/python"; do
    if "$candidate" -c 'import django' >/dev/null 2>&1; then
        exec "$candidate" -u "$server_dir/run_local.py" --open "$@"
    fi
done
if ! python3 -c 'import sys' >/dev/null 2>&1; then
    print -u2 'Python 3 не найден или повреждён. Установите Python 3 с python.org и повторите запуск.'
    exit 1
fi
print 'Окружение server/.venv отсутствует или повреждено, пересоздаю...'
python3 "$server_dir/setup_local.py"
exec "$server_dir/.venv/bin/python" -u "$server_dir/run_local.py" --open "$@"
