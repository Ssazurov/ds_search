from src.metadata.downsideup_header import parse_header

VIDEO = "[▶ Видео (rutube.ru)](https://rutube.ru/video/abc/)"


def test_video_link_not_in_description():
    md = (
        "30.12.2020 2260\n# Название\n#### Описание:\n"
        f"{VIDEO}\nРеальное описание статьи.\n  * #### Автор:\n[ Имя](http://a)\n\nТекст статьи."
    )
    meta, body = parse_header(md)
    assert meta["description"] == "Реальное описание статьи."
    assert "▶" not in meta["description"]
    assert meta["author"] == "Имя"
    assert VIDEO in body and "Текст статьи." in body


def test_description_without_video_unchanged():
    md = "30.12.2020 1\n# T\n#### Описание:\nОписание.\n\nТекст."
    meta, body = parse_header(md)
    assert meta["description"] == "Описание."
    assert body == "Текст."
