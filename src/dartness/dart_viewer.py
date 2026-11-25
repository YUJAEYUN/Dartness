"""Read literal DART TOC locations for explicitly named sections; never execute web JS."""

import re
from urllib.parse import urlencode

_FIELDS = ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd")


def viewer_section_url(main: bytes, receipt: str, corp_code: str, title: str) -> str | None:
    """Return no URL for missing/ambiguous nodes, rejecting conflicting identities."""
    if not re.fullmatch(r"[0-9]{14}", receipt) or not re.fullmatch(r"[0-9]{8}", corp_code):
        raise ValueError("viewer_identity_required")
    if len(main) > 2 * 1024 * 1024:
        raise ValueError("viewer_page_too_large")
    try:
        text = main.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("unsupported_viewer_encoding") from error
    companies = re.findall(r"openCorpInfoNew\('([0-9]{8})'", text)
    if companies != [corp_code]:
        raise ValueError("viewer_company_mismatch")
    candidates: list[dict[str, str]] = []
    # No eval/JS execution. A variable declaration delimits each observed TOC node.
    for block in re.split(r"\bvar node[0-9]+\s*=\s*\{\}\s*;", text)[1:]:
        pairs = re.findall(r'node[0-9]+\[\'(\w+)\'\]\s*=\s*"([^"\r\n]*)"\s*;', block)
        fields = dict(pairs)
        label = re.sub(r"^[0-9.\-\s]+", "", fields.get("text", ""))
        if "".join(label.split()) != title:
            continue
        if len(fields) != len(pairs) or any(key not in fields for key in _FIELDS):
            raise ValueError("invalid_viewer_node")
        if fields["rcpNo"] != receipt:
            raise ValueError("viewer_receipt_mismatch")
        if any(not re.fullmatch(r"[0-9]{1,10}", fields[key]) for key in _FIELDS[1:-1]):
            raise ValueError("invalid_viewer_location")
        if int(fields["length"]) <= 0 or fields["dtd"] != "dart4.xsd":
            raise ValueError("unsupported_viewer_location")
        candidates.append(fields)
    if len(candidates) != 1:
        return None
    return "https://dart.fss.or.kr/report/viewer.do?" + urlencode(
        {key: candidates[0][key] for key in _FIELDS}
    )
