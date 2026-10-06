from src.crawler.video_embeds import embeds_to_links, normalize_video_url


def test_normalize():
    assert normalize_video_url("https://www.youtube.com/embed/AbC-1_x?rel=0") == "https://www.youtube.com/watch?v=AbC-1_x"
    assert normalize_video_url("https://rutube.ru/play/embed/e49032/") == "https://rutube.ru/video/e49032/"
    assert normalize_video_url("//player.vimeo.com/video/123") == "https://vimeo.com/123"
    assert normalize_video_url("https://vk.com/video_ext.php?oid=-1&id=2&hash=x") == "https://vk.com/video-1_2"


def test_iframe_and_marker_to_link():
    h = '<div><iframe src="https://rutube.ru/play/embed/abc/" width="1"></iframe></div>'
    assert '<a href="https://rutube.ru/video/abc/">▶ Видео (rutube.ru)</a>' in embeds_to_links(h)
    m = '<p><a href="https://www.youtube.com/embed/X1">▶ Видео</a></p>'
    assert 'watch?v=X1">▶ Видео (youtube.com)</a>' in embeds_to_links(m)


def test_foreign_iframe_untouched():
    h = '<iframe src="https://maps.example.com/x"></iframe>'
    assert embeds_to_links(h) == h
