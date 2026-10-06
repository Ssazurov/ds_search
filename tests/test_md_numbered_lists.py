"""issue #566: normalize_numbered_lists."""
from src.crawler.md_tables import normalize_numbered_lists as f


def test_variants_normalized():
    src = "1. **A**\n\n2 **B**\n\n**3. C**\n\n**4.** D\n\n**5. E** текст"
    assert f(src) == "1. **A**\n\n2. **B**\n\n3. **C**\n\n4. D\n\n5. **E** текст"


def test_blank_line_before_item_after_paragraph():
    assert f("Текст\n2. **B**") == "Текст\n\n2. **B**"
    assert f("Текст\n1. **A**") == "Текст\n1. **A**"


def test_adjacent_items_untouched():
    s = "1. a\n2. b\n3. c"
    assert f(s) == s


def test_code_fence_untouched():
    s = "```\n**3. x**\n2 **y**\n```"
    assert f(s) == s


def test_plain_text_untouched():
    s = "В 2020 году **важно** всё.\n\n**Заголовок**"
    assert f(s) == s


def test_idempotent():
    s = "**3. C**\n\n2 **B**"
    assert f(f(s)) == f(s)
