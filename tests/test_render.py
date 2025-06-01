import json
from pathlib import Path

from pytest import raises

FIXTURES = Path(__file__).parent / "fixtures"


def test_render(tmp_path: Path):
    from beocijies.configure import add_user, create, delete_user
    from beocijies.render import LinkType, render

    config_dir = tmp_path / "config"
    render_dir = tmp_path / "render"
    test_dir = tmp_path / "test"

    create(
        config_dir,
        render_dir,
        name="fake-site",
        test_destination=test_dir,
        domain="192.168.0.1",
        local=True,
        protocol="http",
    )
    (config_dir / "templates" / "#default.html.jinja2").write_text("{{user(me)}}")
    add_user(config_dir, "dog", public=True)
    add_user(config_dir, "secret", public=False)

    # local site, test config, no subdomains, all users
    render(config_dir)
    assert test_dir.is_dir()
    assert (test_dir / "index.html").is_file()
    assert (test_dir / "users.json").is_file()
    with (test_dir / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"dog": "http://192.168.0.1/dog"}
    assert (test_dir / "dog" / "index.html").is_file()
    assert (test_dir / "dog" / "index.html").read_text() == (
        "<a href='../dog/index.html'>dog</a>"
    )
    assert (test_dir / "secret" / "index.html").is_file()
    assert (test_dir / "secret" / "index.html").read_text() == "secret"

    # force absolute, subset
    (test_dir / "secret" / "index.html").unlink()
    render(config_dir, link_type=LinkType.ABSOLUTE, users=["dog"])
    assert test_dir.is_dir()
    assert (test_dir / "index.html").is_file()
    assert (test_dir / "users.json").is_file()
    with (test_dir / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"dog": "http://192.168.0.1/dog"}
    assert (test_dir / "dog" / "index.html").is_file()
    assert (test_dir / "dog" / "index.html").read_text() == (
        "<a href='http://192.168.0.1/dog'>dog</a>"
    )
    assert not (test_dir / "secret" / "index.html").is_file()

    # don't allow fresh with subset
    (test_dir / "dog" / "secret.html").touch()
    with raises(ValueError):
        render(config_dir, link_type=LinkType.ABSOLUTE, users=["dog"], fresh=True)
    assert (test_dir / "dog" / "secret.html").is_file()

    # test config, prefix, subdomains, all users
    create(
        config_dir,
        render_dir,
        name="fake-site",
        test_destination=test_dir,
        domain="example.com",
        prefix="mysite",
        subdomains=True,
        protocol="https",
    )
    render(config_dir)
    assert test_dir.is_dir()
    assert (test_dir / "index.html").is_file()
    assert (test_dir / "users.json").is_file()
    with (test_dir / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"dog": "https://mysite.example.com/dog"}
    assert (test_dir / "dog" / "index.html").is_file()
    assert (test_dir / "dog" / "index.html").read_text() == (
        "<a href='https://mysite.example.com/dog'>dog</a>"
    )
    assert (test_dir / "secret" / "index.html").is_file()
    assert (test_dir / "secret" / "index.html").read_text() == "secret"

    # force relative
    render(config_dir, link_type=LinkType.RELATIVE, destination=False)
    assert test_dir.is_dir()
    assert (test_dir / "index.html").is_file()
    assert (test_dir / "users.json").is_file()
    with (test_dir / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"dog": "https://mysite.example.com/dog"}
    assert (test_dir / "dog" / "index.html").is_file()
    assert (test_dir / "dog" / "index.html").read_text() == (
        "<a href='../dog/index.html'>dog</a>"
    )
    assert (test_dir / "secret" / "index.html").is_file()
    assert (test_dir / "secret" / "index.html").read_text() == "secret"

    # production deploy
    create(
        config_dir,
        render_dir,
        name="fake-site",
        test_destination=test_dir,
        domain="example.com",
        subdomains=True,
        protocol="https",
    )
    render(config_dir, destination=True)
    assert render_dir.is_dir()
    assert (render_dir / "index.html").is_file()
    assert (render_dir / "users.json").is_file()
    with (render_dir / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"dog": "https://www.example.com/dog"}
    assert (render_dir / "dog" / "index.html").is_file()
    assert (render_dir / "dog" / "index.html").read_text() == (
        "<a href='https://www.example.com/dog'>dog</a>"
    )
    assert (render_dir / "secret" / "index.html").is_file()
    assert (render_dir / "secret" / "index.html").read_text() == "secret"

    # force specific location
    other = tmp_path / "other"
    render(config_dir, destination=other)
    assert other.is_dir()
    assert (other / "index.html").is_file()
    assert (other / "users.json").is_file()
    with (other / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"dog": "https://www.example.com/dog"}
    assert (other / "dog" / "index.html").is_file()
    assert (other / "dog" / "index.html").read_text() == (
        "<a href='https://www.example.com/dog'>dog</a>"
    )
    assert (other / "secret" / "index.html").is_file()
    assert (other / "secret" / "index.html").read_text() == "secret"

    # fresh
    (other / "extra.html").touch()
    delete_user(config_dir, "dog")
    add_user(config_dir, "secret", public=True)
    render(config_dir, destination=other, fresh=True)
    assert other.is_dir()
    assert not (other / "extra.html").is_file()
    assert (other / "index.html").is_file()
    assert (other / "users.json").is_file()
    with (other / "users.json").open() as stream:
        users = json.load(stream)
    assert users == {"secret": "https://www.example.com/secret"}
    assert not (other / "dog" / "index.html").is_file()
    assert (other / "secret" / "index.html").is_file()
    assert (other / "secret" / "index.html").read_text() == (
        "<a href='https://www.example.com/secret'>secret</a>"
    )


def test_parse_entries_file_only(tmp_path: Path):
    from beocijies.render import parse_entries

    page = tmp_path / "page.html"

    with page.open("w") as stream:
        stream.write("<html><body>My empty beocijies page</body></html>")

    # no updates
    assert {} == parse_entries(
        page, "https://example.com", FIXTURES / "no-updates", "beocijies"
    )

    # created
    assert {
        "": {
            "contents": "<p>beocijies created</p>",
            "id": "",
            "published": "2025-06-01T00:15:15+0000",
            "summary": "beocijies created",
            "updated": "2025-06-01T00:15:15+0000",
            "url": "https://example.com/index.html",
        },
    } == parse_entries(page, "https://example.com", FIXTURES / "created", "beocijies")

    assert {
        "": {
            "author": "bcj",
            "contents": "<p>bcj created their beocijies</p>",
            "id": "",
            "published": "2025-06-01T00:15:15+0000",
            "summary": "bcj created their beocijies",
            "updated": "2025-06-01T00:15:15+0000",
            "url": "https://example.com/bcj/index.html",
        },
    } == parse_entries(
        page,
        "https://example.com/bcj",
        FIXTURES / "created",
        "beocijies",
        user="bcj",
    )

    # updated
    assert {
        "": {
            "contents": "<p>beocijies updated</p>",
            "id": "",
            "published": "2025-06-01T00:15:15+0000",
            "summary": "beocijies updated",
            "updated": "2025-06-01T00:18:50+0000",
            "url": "https://example.com/index.html",
        },
    } == parse_entries(page, "https://example.com", FIXTURES / "updated", "beocijies")

    assert {
        "": {
            "author": "bcj",
            "contents": "<p>bcj updated their beocijies</p>",
            "id": "",
            "published": "2025-06-01T00:15:15+0000",
            "summary": "bcj updated their beocijies",
            "updated": "2025-06-01T00:18:50+0000",
            "url": "https://example.com/bcj/index.html",
        },
    } == parse_entries(
        page,
        "https://example.com/bcj",
        FIXTURES / "updated",
        "beocijies",
        user="bcj",
    )


def test_parse_entries(tmp_path: Path):
    from beocijies.render import parse_entries

    page = tmp_path / "page.html"

    with page.open("w") as stream:
        stream.write(
            """
            <html>
            <head><meta charset="UTF-8"></head>
            <body>
            <main>
                <!-- fully defined -->
                <article id="entry-1" class="h-entry">
                    <h1 class="p-name">Entry 1 Title</h1>
                    <h3 class="p-author">
                        bcj
                    </h3>
                    <div>
                        published: <time
                            class="dt-published"
                            datetime="2025-01-02T03:04:05-0600"
                        >January 2nd 3:04 AM CST</time>
                        <br>
                        updated: <time
                            class="dt-updated"
                            datetime="2025-07-08T09:10:11-0500"
                        >July 7th 8:09 AM CDT</time>
                    </div>
                    <div class="p-summary" style="display: none">A short summary</div>
                    <div class="e-content"><ol><li>one</li></ol></div>
                </article>

                <!-- duplicate id, ignore -->
                <article id="entry-1" class="h-entry">
                    <h1 class="p-name">Entry 1a Title</h1>
                    <h3 class="p-author">
                        bcj-a
                    </h3>
                    <div>
                        published: <time
                            class="dt-published"
                            datetime="2026-01-02T03:04:05-0600"
                        >January 2nd 3:04 AM CST</time>
                        <br>
                        updated: <time
                            class="dt-updated"
                            datetime="2026-07-08T09:10:11-0500"
                        >July 7th 8:09 AM CDT</time>
                    </div>
                    <div class="p-summary" style="display: none">The short summary</div>
                    <div class="e-content"><ol><li>alpha</li></ol></div>
                </article>

                <!-- minimal -->
                <article id="entry-2" class="h-entry">
                    <h1>Entry 2 Title</h1>
                    <div>
                        published: <time
                            class="dt-published"
                            datetime="2025-02-03T04:05:06-0700"
                        >February 3rd 4:05 AM MST</time>
                    </div>
                    <div class="e-content">a<br>b</div>
                </article>

                <!-- invalid date, ignore -->
                <article id="entry-2a" class="h-entry">
                    <h1>Entry 2 Title</h1>
                    <div>
                        published: <time
                            class="dt-published"
                            datetime="February 3rd 4:05 AM MST"
                        >February 3rd 4:05 AM MST</time>
                    </div>
                    <div class="e-content">alpha<br>bravo</div>
                </article>

                <!-- missing contents, ignore -->
                <article id="entry-2b" class="h-entry">
                    <h1>Entry 2 Title</h1>
                    <div>
                        published: <time
                            class="dt-published"
                            datetime="February 3rd 4:05 AM MST"
                        >February 3rd 4:05 AM MST</time>
                    </div>
                    <div>contents</div>
                </article>
            </main>
            </body>
            </html>
            """
        )

    assert {
        "": {
            "contents": "<p>beocijies updated</p>",
            "id": "",
            "published": "2025-06-01T00:15:15+0000",
            "summary": "beocijies updated",
            "updated": "2025-06-01T00:18:50+0000",
            "url": "https://example.com/index.html",
        },
        "entry-1": {
            "id": "entry-1",
            "url": "https://example.com/index.html#entry-1",
            "author": "bcj",
            "published": "2025-01-02T03:04:05-0600",
            "updated": "2025-07-08T09:10:11-0500",
            "title": "Entry 1 Title",
            "summary": "A short summary",
            "contents": '<div class="e-content"><ol><li>one</li></ol></div>',
        },
        "entry-2": {
            "id": "entry-2",
            "url": "https://example.com/index.html#entry-2",
            "published": "2025-02-03T04:05:06-0700",
            "updated": "2025-02-03T04:05:06-0700",
            "contents": '<div class="e-content">a<br/>b</div>',
        },
    } == parse_entries(page, "https://example.com", FIXTURES / "updated", "beocijies")

    assert {
        "": {
            "author": "bcj",
            "contents": "<p>bcj updated their beocijies</p>",
            "id": "",
            "published": "2025-06-01T00:15:15+0000",
            "summary": "bcj updated their beocijies",
            "updated": "2025-06-01T00:18:50+0000",
            "url": "https://example.com/bcj/index.html",
        },
        "entry-1": {
            "id": "entry-1",
            "url": "https://example.com/bcj/index.html#entry-1",
            "author": "bcj",
            "published": "2025-01-02T03:04:05-0600",
            "updated": "2025-07-08T09:10:11-0500",
            "title": "Entry 1 Title",
            "summary": "A short summary",
            "contents": '<div class="e-content"><ol><li>one</li></ol></div>',
        },
        "entry-2": {
            "id": "entry-2",
            "url": "https://example.com/bcj/index.html#entry-2",
            "author": "bcj",
            "published": "2025-02-03T04:05:06-0700",
            "updated": "2025-02-03T04:05:06-0700",
            "contents": '<div class="e-content">a<br/>b</div>',
        },
    } == parse_entries(
        page,
        "https://example.com/bcj",
        FIXTURES / "updated",
        "beocijies",
        user="bcj",
    )
