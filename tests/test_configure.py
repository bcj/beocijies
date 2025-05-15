"""
Tests for the configuration module
"""

import json
import re
from pathlib import Path

from pytest import raises


def test_save_config(tmp_path: Path):
    from beocijies.configure import FILENAME, save_config

    config_file = tmp_path / FILENAME

    save_config({"test-destination": None, "test": 1}, tmp_path)
    assert config_file.exists()

    with config_file.open() as stream:
        config = json.load(stream)

    assert config == {"test-destination": None, "test": 1}


def test_check_name():
    from beocijies.configure import check_name

    with raises(ValueError):
        check_name("#base")

    with raises(ValueError):
        check_name("#default")

    with raises(ValueError):
        check_name("dog/cat")

    assert check_name("dog")
    assert check_name("bcj")
    assert not check_name("big dog")
    assert not check_name("big_dog")
    assert not check_name("noël")
    assert not check_name("👻")


def test_url_safe_name():
    from beocijies.configure import url_safe_name

    assert url_safe_name("dog") == "dog"
    assert url_safe_name("bcj") == "bcj"
    assert url_safe_name("big dog") == "big dog".encode("punycode").decode("ascii")
    assert url_safe_name("big_dog") == "big_dog".encode("punycode").decode("ascii")
    assert url_safe_name("noël") == "noël".encode("punycode").decode("ascii")
    assert url_safe_name("👻") == "👻".encode("punycode").decode("ascii")


def test_add_user(tmp_path: Path):
    from beocijies.configure import FILENAME, add_user

    static = tmp_path / "static"
    static.mkdir()
    templates = tmp_path / "templates"
    templates.mkdir()
    with (templates / "#default.html.jinja2").open("w") as stream:
        stream.write("default")

    config = tmp_path / FILENAME
    with config.open("w") as stream:
        json.dump(
            {
                "domain": "example.com",
                "destination": str(tmp_path),
                "subdomains": True,
                "users": {},
            },
            stream,
        )

    # illegal names
    for name in ("#base", "#default"):
        with raises(ValueError):
            add_user(tmp_path, name)

    # add an index
    add_user(tmp_path, "index")
    with config.open() as stream:
        assert json.load(stream)["users"] == {}
    assert (static / "index").is_dir()
    assert (templates / "index.html.jinja2").is_file()
    assert (templates / "index.html.jinja2").read_text() == "default"

    # add a user
    add_user(tmp_path, "user", public=True)
    with config.open() as stream:
        assert json.load(stream)["users"] == {"user": {"public": True}}
    assert (static / "user").is_dir()
    assert (templates / "user.html.jinja2").is_file()
    assert (templates / "user.html.jinja2").read_text() == "default"

    # update a user without overwriting their stuff
    (templates / "user.html.jinja2").write_text("custom")

    add_user(tmp_path, "user", public=False)
    with config.open() as stream:
        assert json.load(stream)["users"] == {"user": {"public": False}}
    assert (static / "user").is_dir()
    assert (templates / "user.html.jinja2").is_file()
    assert (templates / "user.html.jinja2").read_text() == "custom"

    # create a user who already has stuff
    (templates / "user2.html.jinja2").write_text("custom2")
    (static / "user2").mkdir()
    (static / "user2" / "file").write_text("hi")

    add_user(tmp_path, "user2")
    with config.open() as stream:
        assert json.load(stream)["users"] == {
            "user": {"public": False},
            "user2": {"public": True},
        }
    assert (static / "user2").is_dir()
    assert (static / "user2" / "file").read_text() == "hi"
    assert (templates / "user2.html.jinja2").is_file()
    assert (templates / "user2.html.jinja2").read_text() == "custom2"

    # create an nginx file
    add_user(tmp_path, "user3", nginx=tmp_path)
    assert (tmp_path / "example.com").is_file()
    sections = (tmp_path / "example.com").read_text().split("server {")
    assert len(sections) == 5  # "", index, user 1–3
    assert not sections[0].strip()
    name_found = root_found = False
    for line in sections[1].splitlines():
        line = line.strip()
        if line.startswith("server_name "):
            assert line == "server_name example.com www.example.com;"
            name_found = True
        elif line.startswith("root "):
            assert line == f"root {tmp_path};"
            root_found = True
    assert name_found
    assert root_found

    users = {"user", "user2", "user3"}
    for section in sections[2:]:
        user = None
        root_found = False

        for line in section.splitlines():
            if "server_name" in line:
                match = re.search(
                    (
                        r"^\s*server_name "
                        r"www\.(user\d?)\.example\.com "
                        r"(\1)\.example\.com;\s*$"
                    ),
                    line,
                )
                user = match.group(1)
                users.remove(user)
            elif "root " in line:
                assert user
                assert line.strip() == f"root {tmp_path}/{user}/;"
                root_found = True

        assert root_found

    assert users == set()

    # no www
    with config.open() as stream:
        data = json.load(stream)
    data["local"] = True
    with config.open("w") as stream:
        json.dump(data, stream)

    add_user(tmp_path, "user3", nginx=tmp_path)
    assert (tmp_path / "example.com").is_file()
    sections = (tmp_path / "example.com").read_text().split("server {")
    assert len(sections) == 5  # "", index, user 1–3
    assert not sections[0].strip()
    name_found = root_found = False
    for line in sections[1].splitlines():
        line = line.strip()
        if line.startswith("server_name "):
            assert line == "server_name example.com;"
            name_found = True
        elif line.startswith("root "):
            assert line == f"root {tmp_path};"
            root_found = True
    assert name_found
    assert root_found

    users = {"user", "user2", "user3"}
    for section in sections[2:]:
        user = None
        root_found = False

        for line in section.splitlines():
            if "server_name" in line:
                match = re.search(
                    (r"^\s*server_name (user\d?)\.example\.com;\s*$"),
                    line,
                )
                user = match.group(1)
                users.remove(user)
            elif "root " in line:
                assert user
                assert line.strip() == f"root {tmp_path}/{user}/;"
                root_found = True

        assert root_found

    # nginx with prefix (also test symlinking)
    nginx = tmp_path / "sites-available"
    nginx.mkdir()
    enabled = tmp_path / "sites-enabled"
    enabled.mkdir()

    with config.open() as stream:
        data = json.load(stream)
    data["prefix"] = "m"
    data["local"] = False
    with config.open("w") as stream:
        json.dump(data, stream)
    add_user(tmp_path, "user3", nginx=nginx)

    sections = (nginx / "m.example.com").read_text().split("server {")
    assert len(sections) == 5  # "", index, user 1–3
    assert not sections[0].strip()
    name_found = location_found = root_found = False
    for line in sections[1].splitlines():
        line = line.strip()
        if line.startswith("server_name "):
            assert line == "server_name m.example.com;"
            name_found = True
        elif line.startswith("location "):
            assert line == "location / {"
            location_found = True
        elif line.startswith("root "):
            assert line == f"root {tmp_path};"
            root_found = True
    assert name_found
    assert location_found
    assert root_found
    assert (enabled / "example.com").is_symlink()

    users = {"user", "user2", "user3"}
    for section in sections[2:]:
        user = None
        location_found = root_found = False

        for line in section.splitlines():
            if "server_name" in line:
                match = re.search(
                    r"^\s*server_name m\.(user\d?)\.example\.com;\s*$", line
                )
                user = match.group(1)
                users.remove(user)
            elif "location " in line:
                assert user
                assert line.strip() == "location / {"
                location_found = True
            elif "root " in line:
                assert location_found
                assert line.strip() == f"root {tmp_path}/{user}/;"
                root_found = True

        assert root_found

    assert users == set()

    # nginx with no subdomains (and subpath)
    with config.open() as stream:
        data = json.load(stream)
    data["subdomains"] = False
    data["domain"] = "example.com/sub/path"
    with config.open("w") as stream:
        json.dump(data, stream)
    add_user(tmp_path, "user3", nginx=tmp_path)

    sections = (tmp_path / "m.example.com").read_text().split("server {")
    assert len(sections) == 2  # "", index
    assert not sections[0].strip()
    name_found = location_found = root_found = False
    for line in sections[1].splitlines():
        line = line.strip()
        if line.startswith("server_name "):
            assert line == "server_name m.example.com;"
            name_found = True
        elif line.startswith("location "):
            assert name_found
            assert line == "location /sub/path {"
            location_found = True
        elif line.startswith("root "):
            assert location_found
            assert line == f"root {tmp_path};"
            root_found = True

    assert root_found


def test_rename_user(tmp_path: Path):
    from beocijies.configure import FILENAME, add_user, rename_user

    static = tmp_path / "static"
    static.mkdir()
    templates = tmp_path / "templates"
    templates.mkdir()
    with (templates / "#default.html.jinja2").open("w") as stream:
        stream.write("default")

    config = tmp_path / FILENAME
    with config.open("w") as stream:
        json.dump(
            {
                "domain": "example.com",
                "destination": str(tmp_path),
                "subdomains": True,
                "users": {},
            },
            stream,
        )

    # non-existent user
    for name in ("index", "cat"):
        with raises(ValueError):
            rename_user(tmp_path, name, "dog")

    add_user(tmp_path, "dog", public=True)
    # illegal names
    for name in ("#base", "#default", "index"):
        with raises(ValueError):
            rename_user(tmp_path, "dog", name)

    # actually rename
    rename_user(tmp_path, "dog", "cat")
    with config.open() as stream:
        assert json.load(stream)["users"] == {"cat": {"public": True}}
    assert (static / "cat").is_dir()
    assert not (static / "dog").is_dir()
    assert (templates / "cat.html.jinja2").is_file()
    assert not (templates / "dog.html.jinja2").is_file()

    add_user(tmp_path, "dog", public=True)
    # don't overwrite existing user
    with raises(ValueError):
        rename_user(tmp_path, "cat", "dog")

    # don't overwrite existing directories
    (static / "cat" / "file").write_text("meow")
    (static / "lion").mkdir()
    (static / "lion" / "file").write_text("roar")
    rename_user(tmp_path, "cat", "lion")
    assert (static / "lion").is_dir()
    assert (static / "cat").is_dir()
    assert (templates / "lion.html.jinja2").is_file()
    assert not (templates / "cat.html.jinja2").is_file()
    assert (static / "lion" / "file").read_text() == "roar"
    assert (static / "cat" / "file").read_text() == "meow"


def test_delete_user(tmp_path: Path):
    from beocijies.configure import FILENAME, add_user, delete_user

    static = tmp_path / "static"
    static.mkdir()
    templates = tmp_path / "templates"
    templates.mkdir()
    with (templates / "#default.html.jinja2").open("w") as stream:
        stream.write("default")

    config = tmp_path / FILENAME
    with config.open("w") as stream:
        json.dump(
            {
                "domain": "example.com",
                "destination": str(tmp_path),
                "subdomains": True,
                "users": {},
            },
            stream,
        )

    # non-existent user
    for name in ("index", "cat"):
        with raises(ValueError):
            delete_user(tmp_path, name)

    # actually remove
    add_user(tmp_path, "dog", public=True)
    delete_user(tmp_path, "dog")
    with config.open() as stream:
        assert json.load(stream)["users"] == {}
    assert (static / "dog").is_dir()
    assert (templates / "dog.html.jinja2").is_file()

    # remove andd delete
    add_user(tmp_path, "dog", public=True)
    delete_user(tmp_path, "dog", delete_files=True)
    with config.open() as stream:
        assert json.load(stream)["users"] == {}
    assert not (static / "dog").is_dir()
    assert not (templates / "dog.html.jinja2").is_file()


def test_create(tmp_path):
    from beocijies.configure import FILENAME, add_user, create

    create(tmp_path, tmp_path / "destination", "beocijies")
    config = tmp_path / FILENAME
    assert config.is_file()
    with config.open() as stream:
        data = json.load(stream)
    assert data["destination"] == str(tmp_path / "destination")
    assert data["name"] == "beocijies"
    assert data["domain"] == "localhost"
    assert data["users"] == {}
    assert (tmp_path / "templates").is_dir()
    assert (tmp_path / "templates" / "#base.html.jinja2").is_file()
    assert (tmp_path / "templates" / "#default.html.jinja2").is_file()
    assert (tmp_path / "templates" / "index.html.jinja2").is_file()
    assert (tmp_path / "static").is_dir()
    assert (tmp_path / "static" / "index").is_dir()
    assert (tmp_path / "static" / "robots.txt").is_file()

    # don't overwrite files
    (tmp_path / "templates" / "#base.html.jinja2").write_text("base")
    (tmp_path / "templates" / "#default.html.jinja2").write_text("default")
    (tmp_path / "templates" / "index.html.jinja2").write_text("index")
    create(
        tmp_path,
        tmp_path / "destination",
        "beocijies2",
        domain="beocijies2.example.com",
    )
    assert config.is_file()
    with config.open() as stream:
        data = json.load(stream)
    assert data["destination"] == str(tmp_path / "destination")
    assert data["name"] == "beocijies2"
    assert data["domain"] == "beocijies2.example.com"
    assert data["users"] == {}
    assert (tmp_path / "templates").is_dir()
    assert (tmp_path / "templates" / "#base.html.jinja2").read_text() == "base"
    assert (tmp_path / "templates" / "#default.html.jinja2").read_text() == "default"
    assert (tmp_path / "templates" / "index.html.jinja2").read_text() == "index"
    assert (tmp_path / "static").is_dir()
    assert (tmp_path / "static" / "index").is_dir()
    assert (tmp_path / "static" / "robots.txt").is_file()

    # test copy existing users
    add_user(tmp_path, "dog", public=True)
    add_user(tmp_path, "cat", public=False)
    create(
        tmp_path,
        tmp_path / "destination",
        "threocijies",
        domain="beocijies3.example.com",
        test_destination=tmp_path / "temp",
    )
    assert config.is_file()
    with config.open() as stream:
        data = json.load(stream)
    assert data["destination"] == str(tmp_path / "destination")
    assert data["test-destination"] == str(tmp_path / "temp")
    assert data["name"] == "threocijies"
    assert data["domain"] == "beocijies3.example.com"
    assert data["users"] == {"dog": {"public": True}, "cat": {"public": False}}
