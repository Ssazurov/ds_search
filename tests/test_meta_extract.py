from src.metadata.meta_extract import extract_page_meta


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
