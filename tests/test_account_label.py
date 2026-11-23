"""Account labels reduce to their core name; words are never removed (issue #56)."""

import pytest

from dartness.account_label import core_account_name


@pytest.mark.parametrize(
    ("label", "core"),
    [
        ("현금및현금성자산", "현금및현금성자산"),
        ("　　현금및현금성자산", "현금및현금성자산"),
        ("(5)현금및현금성자산", "현금및현금성자산"),
        ("Ⅰ.비유동자산", "비유동자산"),
        ("ⅳ. 단기금융상품", "단기금융상품"),
        ("가. 매출채권", "매출채권"),
        ("(가)매출채권", "매출채권"),
        ("① 재고자산", "재고자산"),
        ("(A)기타자산", "기타자산"),
        ("(5)1.현금및현금성자산", "현금및현금성자산"),
        ("현금및현금성자산 (주4,29)", "현금및현금성자산"),
        ("(5)현금및현금성자산(주5)", "현금및현금성자산"),
    ],
)
def test_outline_markers_and_note_references_are_removed(label: str, core: str) -> None:
    assert core_account_name(label) == core


@pytest.mark.parametrize(
    ("label", "core"),
    [
        ("제한된 현금및현금성자산", "제한된현금및현금성자산"),
        ("현금및현금성자산 등", "현금및현금성자산등"),
        ("(주)현금및현금성자산", "(주)현금및현금성자산"),
        ("(주4)현금및현금성자산", "(주4)현금및현금성자산"),
        ("5현금및현금성자산", "5현금및현금성자산"),
        ("().현금및현금성자산", "().현금및현금성자산"),
        ("현금및현금성자산 (주)", "현금및현금성자산(주)"),
        ("현금및현금성자산 (주4) 외", "현금및현금성자산(주4)외"),
    ],
)
def test_words_and_unclear_marks_are_kept(label: str, core: str) -> None:
    assert core_account_name(label) == core
