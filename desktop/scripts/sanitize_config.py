# config sanitizer: strip any real api_key value from staged config.yaml
# Usage: python _sanitize_config.py <path-to-config.yaml>
# CRLF-safe, idempotent. Exits 1 if a real key remains (safety net).
import re
import sys

def repl(m):
    val = m.group(2).strip()
    if val in ('', '""', "''"):
        return m.group(0)          # already empty - keep as is
    return m.group(1) + '""'

def main():
    path = sys.argv[1]
    with open(path, 'rb') as f:
        s = f.read().decode('utf-8')

    s2 = re.sub(r'(?m)^(\s*api_key:[ \t]*)([^\r\n]*)', repl, s)

    if s2 != s:
        with open(path, 'wb') as f:
            f.write(s2.encode('utf-8'))
        print('    api_key value REPLACED with ""')
    else:
        print('    api_key already empty - nothing to do')

    # safety net: verify no real key remains
    m = re.search(r'(?m)^\s*api_key:[ \t]*([^\r\n]*)', s2)
    val = m.group(1).strip() if m else ''
    if m is None:
        print('    NOTE: no api_key line found (ok if key comes from env)')
    elif val not in ('', '""', "''"):
        print(f'    FATAL: api_key still non-empty: {val[:6]}***')
        sys.exit(1)

if __name__ == '__main__':
    main()
