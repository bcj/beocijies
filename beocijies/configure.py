"""
Configure the website
"""
import json
import logging
from pathlib import Path
from shutil import copy2
from typing import Dict, List, Optional, Union

from jinja2 import Template

from beocijies.version import __version__

FILENAME = "settings.json"

ROBOTS_TEMPLATE = """{% for agent in disallowed or () %}
User-agent: {{agent}}
Disallow: /
{% endfor %}{% for agent in allowed or () %}
User-agent: {{agent}}
Allow: /
{% endfor %}User-agent: *
{% if allow_robots %}Allow{% else %}Disallow{% endif %}: /
"""

BASE_TEMPLATE = """<!DOCTYPE html>
<html{% if language %} lang="{{language}}"{% endif %}>
<head>
    <meta charset="utf-8">
    {% block head %}{% endblock %}
</head>
    <body>
        {% block body %}{% endblock %}
        <footer>
            <hr>
            {% if me != "index "%}<a href="{{"../index.html"}}">a {{site_name}} site</a><br>{% endif %}
            <em>last updated {{page_date}}</em><br>
            {% if latest_image -%}
                <img style="max-width: 100%; max-height: 500px;" src="{{latest_image}}" alt="{{me}} updating their {{site_name}} site">
            {%- endif %}
        </footer>
    </body>
</html>
"""  # noqa: E501

DEFAULT_TEMPLATE = """{% extends "base.html.jinja2" %}
{% block head %}
    <title>{{me}}'s {{site_name}} page</title>
    <style type="text/css"></style>
{% endblock %}
{% block body %}
    <h1>🚧 Under Construction 🚧</h1>
    <p>I'm about to set up my {{site_name}} page</p>
{% endblock %}
"""


NGINX_TEMPLATE = """
{% for domain in domains %}
server {
    server_name {{domain}} www.{{domain}};
    listen 80;
    listen [::]:80;

    location / {
        root {{path}}/;
    }
}
{% if mobile %}
server {
    server_name m.{{domain}};
    listen 80;
    listen [::]:80;

    location / {
        root {{path}}/mobile/;
    }

    location /desktop {
        root {{path}}/;
    }
}
{% endif %}
{% endfor %}
"""

LOGGER = logging.getLogger("beocijies")


def create(
    directory: Path,
    destination: Path,
    name: str,
    *,
    mobile: Optional[Path] = None,
    domain: str = "localhost",
    language: Optional[str] = None,
    allowed_agents: Optional[List[str]] = None,
    disallowed_agents: Optional[List[str]] = None,
    robots: bool = False,
    subdomains: bool = False,
    nginx: Optional[Path] = None,
):
    config: Dict[str, Optional[Union[str, bool, dict]]] = {
        "version": __version__,
        "destination": str(destination.absolute()),
        "mobile": str(mobile.absolute()) if mobile else None,
        "name": name,
        "domain": domain,
        "language": language,
        "robots": {
            "default": robots,
            "allowed": allowed_agents,
            "disallowed": disallowed_agents,
        },
        "subdomains": subdomains,
        "users": {},
    }

    directory.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    if mobile:
        mobile.mkdir(parents=True, exist_ok=True)
        (mobile / "test-build").mkdir(parents=True, exist_ok=True)

    existing_users = {}
    config_file = directory / FILENAME
    if config_file.exists():
        with config_file.open("r") as stream:
            old_config = json.load(stream)

        existing_users = old_config["users"]

    save_config(config, directory)

    directories = [directory]
    if mobile:
        directories.append(mobile)

    for path in directories:
        static = path / "static"
        static.mkdir(exist_ok=True)

        with (static / "robots.txt").open("w") as stream:
            stream.write(
                Template(ROBOTS_TEMPLATE).render(
                    allow_robots=robots,
                    allowed=allowed_agents,
                    disallowed=disallowed_agents,
                )
            )

        templates = path / "templates"
        templates.mkdir(exist_ok=True)

        base_template = templates / "base.html.jinja2"
        if not base_template.exists():
            with base_template.open("w") as stream:
                stream.write(BASE_TEMPLATE)

        default_template = templates / "default.html.jinja2"
        if not default_template.exists():
            with default_template.open("w") as stream:
                stream.write(DEFAULT_TEMPLATE)

    if existing_users:
        for name, info in existing_users.items():
            if name == "index":
                continue

            add_user(directory, name, **info)

    add_user(
        directory,
        "index",
        public=False,
        desktop=True,
        mobile=bool(mobile),
        nginx=nginx,
    )


def add_user(
    directory: Path,
    name: str,
    *,
    public: bool = True,
    desktop: bool = True,
    mobile: bool = False,
    nginx: Optional[Path] = None,
):
    if name in {"desktop", "mobile", "base", "default"}:
        raise ValueError("Forbidden name: {name}")

    path = directory / FILENAME

    with path.open("r") as stream:
        config = json.load(stream)

    if name in config["users"]:
        LOGGER.info("updating existing user %s", name)

    config["users"][name] = {
        "public": public,
        "desktop": desktop,
        "mobile": mobile,
    }

    save_config(config, directory)

    directories = []

    if desktop:
        directories.append(directory)

    if mobile and config.get("mobile"):
        directories.append(Path(config["mobile"]))

    for path in directories:
        templates = path / "templates"

        template = templates / f"{name}.html.jinja2"

        if not template.exists():
            LOGGER.debug("Creating template %s", template)
            copy2(templates / "default.html.jinja2", template)

        LOGGER.debug("Creating static directory")
        (path / "static" / name).mkdir(exist_ok=True)

    if nginx:
        LOGGER.info("Generating nginx configuration")
        base = config["domain"]
        domains = [base]

        if config["subdomains"]:
            for user in config["users"]:
                if user != "index":
                    domains.append(f"{user}.{base}")

        nginx_template = Template(NGINX_TEMPLATE)
        with (nginx / base).open("w") as stream:
            stream.write(
                nginx_template.render(
                    domains=domains,
                    path=config["destination"],
                    mobile=bool(config["mobile"]),
                )
            )


def mobile_import(directory: Path):
    with (directory / FILENAME).open("r") as stream:
        config = json.load(stream)

    with (Path(config["mobile"]) / FILENAME).open("r") as stream:
        mobile_config = json.load(stream)

    for user, info in mobile_config["users"].items():
        if user not in config["users"]:
            LOGGER.info("creating user %s", user)
            config["users"][user] = info
        elif info["mobile"] != config["users"][user]["mobile"]:
            LOGGER.info("updating mobile settings for %s", user)
            config["users"][user]["mobile"] = True

    save_config(config, directory)


def save_config(config: dict, directory: Path):
    path = directory / FILENAME
    LOGGER.debug("saving config %s", path)
    with path.open("w") as stream:
        json.dump(
            config,
            stream,
            sort_keys=True,
            indent=4,
        )

    if config["mobile"]:
        mobile = Path(config["mobile"])

        if mobile.exists():
            LOGGER.debug("saving config %s", mobile / FILENAME)
            with (mobile / FILENAME).open("w") as stream:
                json.dump(
                    {**config, "destination": str(mobile / "test-build")},
                    stream,
                    sort_keys=True,
                    indent=4,
                )
