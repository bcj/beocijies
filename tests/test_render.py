import json
from pathlib import Path

from pytest import raises


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
