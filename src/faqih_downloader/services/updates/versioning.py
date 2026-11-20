"""
Semantic and date-based version parsing and comparison helpers.
"""
import re
from typing import List, Tuple


def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    Parses a semantic or date-based version string (e.g. 'v2.1.0', '2.0.0', '2026.03.17')
    into a tuple of integers (e.g. (2, 1, 0), (2026, 3, 17)).
    Returns an empty tuple () if version_str is empty or invalid.
    """
    if not version_str or not isinstance(version_str, str):
        return ()
    cleaned = version_str.strip().lstrip("vV").strip()
    if not cleaned or cleaned.endswith("-") or cleaned.endswith("+"):
        return ()
    if "+" in cleaned:
        base_and_pre, build_meta = cleaned.split("+", 1)
        if not build_meta.strip():
            return ()
    else:
        base_and_pre = cleaned
    if "-" in base_and_pre:
        main_part, pre_part = base_and_pre.split("-", 1)
        if not pre_part.strip():
            return ()
    else:
        main_part = base_and_pre
    main_part = main_part.strip()
    if not main_part:
        return ()
    parts: List[int] = []
    for token in main_part.split("."):
        token_s = token.strip()
        m = re.match(r"^(\d+)$", token_s)
        if not m:
            return ()
        parts.append(int(m.group(1)))
    return tuple(parts)


def _compare_prerelease(pre_a: str, pre_b: str) -> int:
    """
    Compares two SemVer pre-release strings (e.g. 'alpha.10' vs 'alpha.2', 'rc10' vs 'rc2').
    Returns 1 if pre_a > pre_b, -1 if pre_a < pre_b, 0 if equal.
    """
    if pre_a == pre_b:
        return 0
    ids_a = [p.strip() for p in pre_a.split(".")]
    ids_b = [p.strip() for p in pre_b.split(".")]
    for tok_a, tok_b in zip(ids_a, ids_b):
        if tok_a == tok_b:
            continue
        a_is_num = tok_a.isdigit()
        b_is_num = tok_b.isdigit()
        if a_is_num and b_is_num:
            na, nb = int(tok_a), int(tok_b)
            if na != nb:
                return 1 if na > nb else -1
        elif a_is_num != b_is_num:
            # Per SemVer 2.0.0 section 11: numeric identifiers have lower precedence than non-numeric
            return -1 if a_is_num else 1
        else:
            # Natural comparison for combined alphanumeric tokens like 'rc10' vs 'rc2'
            chunks_a = [int(x) if x.isdigit() else x for x in re.findall(r"\d+|\D+", tok_a)]
            chunks_b = [int(x) if x.isdigit() else x for x in re.findall(r"\d+|\D+", tok_b)]
            for ca, cb in zip(chunks_a, chunks_b):
                if ca == cb:
                    continue
                if isinstance(ca, int) and isinstance(cb, int):
                    return 1 if ca > cb else -1
                sa, sb = str(ca), str(cb)
                if sa != sb:
                    return 1 if sa > sb else -1
            if len(chunks_a) != len(chunks_b):
                return 1 if len(chunks_a) > len(chunks_b) else -1
    if len(ids_a) != len(ids_b):
        return 1 if len(ids_a) > len(ids_b) else -1
    return 0


def is_newer_version(remote_ver: str, current_ver: str) -> bool:
    """
    Compares remote_ver against current_ver and returns True if remote_ver is strictly newer.
    Supports:
    - Semantic versions: 'v2.1.0' > '2.0.0', '2.0.1' > '2.0', '2.0.0' == 'v2.0.0'
    - Pre-release tags: '2.0.0' > '2.0.0-beta.1', '2.0.0-alpha.10' > '2.0.0-alpha.2'
    - Date-based versions (yt-dlp): '2026.03.17' > '2025.11.12'
    Returns False on empty, malformed, or equal versions.
    """
    if not remote_ver or not current_ver or not isinstance(remote_ver, str) or not isinstance(current_ver, str):
        return False
    r_tuple = parse_version(remote_ver)
    c_tuple = parse_version(current_ver)
    if not r_tuple or not c_tuple:
        return False

    max_len = max(len(r_tuple), len(c_tuple))
    r_padded = r_tuple + (0,) * (max_len - len(r_tuple))
    c_padded = c_tuple + (0,) * (max_len - len(c_tuple))
    if r_padded != c_padded:
        return r_padded > c_padded

    # Numeric components are equal; compare pre-release suffix (e.g. '2.0.0' vs '2.0.0-beta.1')
    r_clean = remote_ver.strip().lstrip("vV").strip().split("+", 1)[0]
    c_clean = current_ver.strip().lstrip("vV").strip().split("+", 1)[0]
    r_pre = r_clean.split("-", 1)[1].strip() if "-" in r_clean else ""
    c_pre = c_clean.split("-", 1)[1].strip() if "-" in c_clean else ""
    r_has_pre = bool(r_pre)
    c_has_pre = bool(c_pre)
    if c_has_pre and not r_has_pre:
        # Stable release is newer than pre-release of the same number
        return True
    if r_has_pre and not c_has_pre:
        # Pre-release is older than stable release of the same number
        return False
    if r_has_pre and c_has_pre:
        return _compare_prerelease(r_pre, c_pre) > 0
    return False


def is_version_ge(v1: str, v2: str) -> bool:
    """Returns True if version v1 >= v2."""
    if not v1:
        return False
    if not v2 or is_newer_version(v1, v2):
        return True
    if is_newer_version(v2, v1):
        return False
    p1, p2 = parse_version(v1), parse_version(v2)
    if p1 and p2:
        max_len = max(len(p1), len(p2))
        p1_pad = p1 + (0,) * (max_len - len(p1))
        p2_pad = p2 + (0,) * (max_len - len(p2))
        if p1_pad == p2_pad:
            c1 = str(v1).strip().lstrip("vV").strip().split("+", 1)[0]
            c2 = str(v2).strip().lstrip("vV").strip().split("+", 1)[0]
            pre1 = c1.split("-", 1)[1].strip() if "-" in c1 else ""
            pre2 = c2.split("-", 1)[1].strip() if "-" in c2 else ""
            return pre1 == pre2
    return str(v1).strip().lstrip("vV") == str(v2).strip().lstrip("vV")
