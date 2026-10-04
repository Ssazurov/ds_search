from src.crawler.md_tables import merge_adjacent_emphasis as m


def test_punct():
    assert m('**Новая жизнь****, любовь**') == '**Новая жизнь, любовь**'


def test_lost_space_cyr():
    assert m('**наших****любимых**') == '**наших любимых**'


def test_italic():
    assert m('**_Анастасия,_****_мама Ксюши:_**') == '**_Анастасия, мама Ксюши:_**'


def test_latin_midword():
    assert m('[**And****roid**](u)') == '[**Android**](u)'


def test_hr_untouched():
    assert m('\n****\n') == '\n****\n'
