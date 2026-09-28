from src.metadata.meta_extract import extract_author_from_markdown, extract_page_meta


def test_prefers_og_and_article_tags():
    meta = {
        'description': 'fallback desc',
        'og:description': 'og desc',
        'author': 'fallback author',
        'article:author': 'Ivan Ivanov',
        'article:published_time': '2024-01-02T00:00:00Z',
    }
    result = extract_page_meta(meta)
    assert result == {
        'author': 'Ivan Ivanov',
        'publish_date': '2024-01-02T00:00:00Z',
        'description': 'og desc',
    }


def test_falls_back_to_plain_meta_tags():
    meta = {'description': 'plain desc', 'author': 'Plain Author'}
    result = extract_page_meta(meta)
    assert result == {'author': 'Plain Author', 'publish_date': '', 'description': 'plain desc'}


def test_empty_or_missing_metadata():
    assert extract_page_meta(None) == {'author': '', 'publish_date': '', 'description': ''}
    assert extract_page_meta({}) == {'author': '', 'publish_date': '', 'description': ''}


def test_author_from_markdown_preserves_link():
    markdown = "Автор: [КАПЛАН Виталий](https://foma.ru/authors/kaplan-vitalij)Журнал: Фома"
    result = extract_page_meta({'article:author': 'https://facebook.com/foma.ru'}, markdown)
    assert result['author'] == '[КАПЛАН Виталий](https://foma.ru/authors/kaplan-vitalij)'


def test_body_author_wins_over_metadata_and_url_author_is_ignored():
    assert extract_page_meta({'author': 'https://example.test/team'}, 'Автор: Мария Иванова')['author'] == 'Мария Иванова'
    assert extract_page_meta({'author': 'https://example.test/team'})['author'] == ''


def test_author_extraction_handles_absent_or_non_author_lines():
    assert extract_author_from_markdown('Текст без автора\nЖурнал: X') == ''
    assert extract_author_from_markdown('Автор: Иванов\nЖурнал: Журнал') == 'Иванов'
