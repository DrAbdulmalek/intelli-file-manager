#!/usr/bin/env bash
# install_hooks.sh — تركيب بوابات git المحلية للـHarness (F003)
#
# يركّب scripts/hooks/pre-push في .git/hooks/pre-push لرفض الدفع
# عند فشل بوابة verify.sh --quick. آمن للتكرار (idempotent)،
# ولا يستبدل أي hook موجود لا ينتمي لهذا الـHarness.
#
# الاستخدام: ./scripts/install_hooks.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/scripts/hooks/pre-push"
DST="$ROOT/.git/hooks/pre-push"

if [[ ! -f "$SRC" ]]; then
    echo "❌ المصدر مفقود: $SRC" >&2
    exit 1
fi
if [[ ! -d "$ROOT/.git" ]]; then
    echo "❌ ليس مستودع git: $ROOT" >&2
    exit 1
fi
mkdir -p "$ROOT/.git/hooks"
if [[ -f "$DST" ]] && ! grep -q 'scripts/hooks/pre-push' "$DST" 2>/dev/null; then
    echo "⚠️  يوجد pre-push hook آخر في .git/hooks — لن يُستبدل. راجعه يدويًا." >&2
    exit 1
fi
install -m 0755 "$SRC" "$DST"
echo "✅ رُكّب .git/hooks/pre-push → scripts/verify.sh --quick (F003)"
