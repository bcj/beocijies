"""
Configure the website
"""
import json
import logging
import re
from pathlib import Path
from shutil import copy2, move, rmtree
from typing import Any, Dict, List, Optional, Union

import requests
from jinja2 import Template

from beocijies.version import __version__

FILENAME = "settings.json"

SAFE_NAME = re.compile(r"^[A-Za-z0-9-]+$")
FORBIDDEN_NAMES = {"#base", "#default"}

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
            {% if me != "index" %}<a href="../index.html">a {{site_name}} site</a><br>{% endif %}
            <em>last updated {{page_date}}</em><br>
            {% if latest_image -%}
                <img style="max-width: 100%; max-height: 500px;" src="{{latest_image}}" alt="{{me}} updating their {{site_name}} site">
            {%- endif %}
            <hr>
            <a href="https://github.com/bcj/beocijies/">make your own site</a>
        </footer>
    </body>
</html>
"""  # noqa: E501

DEFAULT_TEMPLATE = """{% extends "#base.html.jinja2" %}
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
server {
    server_name {% if prefix %}{{prefix}}.{{domain}}{% else %}{{domain}} www.{{domain}}{% endif %};
    listen 80;
    listen [::]:80;

    location {{url_path}} {
        root {{path}};
    }
}
{% for user in users %}
server {
    server_name {% if prefix %}{{prefix}}{% else %}{{url_safe_name(user)}}.{{domain}} www{% endif %}.{{url_safe_name(user)}}.{{domain}};
    listen 80;
    listen [::]:80;

    location / {
        root {{path}}/{{user}}/;
    }
}
{% endfor %}
"""  # noqa: E501

HTTPD_TEMPLATE = """
<VirtualHost *:80>
    {% if url_path %}<Directory "{{url_path}}">
        {% endif %}DocumentRoot "{{path}}"{% if url_path %}
    </Directory>{% endif %}
    ServerName {% if prefix %}{{prefix}}.{{domain}}{% else %}{{domain}}
    ServerAlias www.{{domain}}{% endif %}
</VirtualHost>
{% for user in users %}
<VirtualHost *:80>
    {% if url_path %}<Directory "{{url_path}}">
        {% endif %}DocumentRoot "{{path}}/{{user}}"{% if url_path %}
    </Directory>{% endif %}
    ServerName {% if prefix %}{{prefix}}.{{user}}.{{domain}}{% else %}{{user}}.{{domain}}
    ServerAlias www.{{user}}.{{domain}}{% endif %}
</VirtualHost>
{% endfor %}
"""  # noqa: E501

LOGGER = logging.getLogger("beocijies")


def create(
    directory: Path,
    destination: Path,
    name: str,
    *,
    test_destination: Optional[Path] = None,
    domain: str = "localhost",
    prefix: Optional[str] = None,
    language: Optional[str] = None,
    allowed_agents: Optional[List[str]] = None,
    disallowed_agents: Optional[List[str]] = None,
    robots: bool = False,
    subdomains: bool = False,
    nginx: Optional[Path] = None,
    httpd: Optional[Path] = None,
    protocol: str = "https",
):
    config: Dict[str, Optional[Union[str, bool, dict]]] = {
        "version": __version__,
        "destination": str(destination.absolute()),
        "name": name,
        "protocol": protocol,
        "domain": domain,
        "prefix": prefix,
        "language": language,
        "robots": {
            "default": robots,
            "allowed": allowed_agents,
            "disallowed": disallowed_agents,
        },
        "subdomains": subdomains,
        "users": {},
        "neighbours": {},
    }

    if test_destination:
        config["test-destination"] = str(test_destination.absolute())

    directory.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    existing_users = {}
    config_file = directory / FILENAME
    if config_file.exists():
        with config_file.open("r") as stream:
            old_config = json.load(stream)

        existing_users = old_config["users"]

        config["neighbours"] = old_config["neighbours"]

    save_config(config, directory)

    static = directory / "static"
    static.mkdir(exist_ok=True)

    with (static / "robots.txt").open("w") as stream:
        stream.write(
            Template(ROBOTS_TEMPLATE).render(
                allow_robots=robots,
                allowed=allowed_agents,
                disallowed=disallowed_agents,
            )
        )

    templates = directory / "templates"
    templates.mkdir(exist_ok=True)

    base_template = templates / "#base.html.jinja2"
    if not base_template.exists():
        with base_template.open("w") as stream:
            stream.write(BASE_TEMPLATE)

    default_template = templates / "#default.html.jinja2"
    if not default_template.exists():
        with default_template.open("w") as stream:
            stream.write(DEFAULT_TEMPLATE)

    if existing_users:
        for name, info in existing_users.items():
            if name == "index":
                continue

            add_user(directory, name, **info)

    add_user(directory, "index", public=False, nginx=nginx, httpd=httpd)


def add_user(
    directory: Path,
    name: str,
    *,
    public: bool = True,
    nginx: Optional[Path] = None,
    httpd: Optional[Path] = None,
):
    check_name(name)

    path = directory / FILENAME

    with path.open("r") as stream:
        config = json.load(stream)

    if name in config["users"]:
        LOGGER.info("updating existing user %s", name)
        added = False
    else:
        LOGGER.info("creating user %s", name)
        added = True

    if name != "index":
        config["users"][name] = {"public": public}

    save_config(config, directory)

    templates = directory / "templates"

    template = templates / f"{name}.html.jinja2"

    if not template.exists():
        LOGGER.debug("Creating template %s", template)
        copy2(templates / "#default.html.jinja2", template)

    LOGGER.debug("Creating static directory")
    (directory / "static" / name).mkdir(exist_ok=True)

    if nginx:
        _write_nginx(nginx, config, certbot=added)

    if httpd:
        _write_httpd(httpd, config, certbot=added)


def rename_user(
    directory: Path,
    old_name: str,
    new_name: str,
    *,
    nginx: Optional[Path] = None,
    httpd: Optional[Path] = None,
):
    check_name(new_name)

    path = directory / FILENAME

    with path.open("r") as stream:
        config = json.load(stream)

    if old_name not in config["users"]:
        raise ValueError(f"Unknown user: {old_name}")

    if new_name in config["users"] or new_name == "index":
        raise ValueError(f"Username already taken: {new_name}")

    LOGGER.info("renaming user %s to %s", old_name, new_name)

    config["users"][new_name] = config["users"].pop(old_name)

    save_config(config, directory)

    LOGGER.debug("moving template")
    templates = directory / "templates"
    old_template = templates / f"{old_name}.html.jinja2"
    new_template = templates / f"{new_name}.html.jinja2"

    # python 3.8 expects the arguments to move to be strings
    if old_template.exists():
        move(str(old_template), str(new_template))

    LOGGER.debug("moving static directory")
    old_static = directory / "static" / old_name
    new_static = directory / "static" / new_name

    if old_static.exists():
        if new_static.exists():
            logging.error("can't move static directory. new directory exists")
        else:
            # python 3.8 expects the arguments to move to be strings
            move(str(old_static), str(new_static))

    if nginx:
        _write_nginx(nginx, config)

    if httpd:
        _write_httpd(httpd, config)


def delete_user(
    directory: Path,
    name: str,
    *,
    delete_files: bool = False,
    nginx: Optional[Path] = None,
    httpd: Optional[Path] = None,
):
    path = directory / FILENAME

    with path.open("r") as stream:
        config = json.load(stream)

    if name not in config["users"]:
        raise ValueError(f"User doesn't exist: {name}")

    LOGGER.info("Deleting user %s", name)

    del config["users"][name]

    save_config(config, directory)

    if delete_files:
        templates = directory / "templates"

        template = templates / f"{name}.html.jinja2"

        if template.exists():
            LOGGER.debug("Deleting template %s", template)
            template.unlink()

        static = directory / "static" / name
        if static.is_dir():
            LOGGER.debug("Deleting static directory")
            rmtree(static)

    if nginx:
        _write_nginx(nginx, config, certbot=False)

    if httpd:
        _write_httpd(httpd, config, certbot=False)


def grab_users(directory: Path, name: str, domain: str):
    path = directory / FILENAME

    with path.open("r") as stream:
        config = json.load(stream)

    if name in config["neighbours"]:
        LOGGER.info("updating server info for %s", name)

    config["neighbours"][name] = requests.get(f"{domain}/users.json").json()

    save_config(config, directory)


def forget_users(directory: Path, name: str):
    path = directory / FILENAME

    with path.open("r") as stream:
        config = json.load(stream)

    if name not in config["neighbours"]:
        LOGGER.error("No server info known for %s", name)
    else:
        del config["neighbours"][name]


def check_name(name: str) -> bool:
    """
    Check a username, returning true if it only contains safe characters
    and raising if it will break beocijies
    """
    # i'm going to just save everyone some time and forbid slashes in names
    if name in FORBIDDEN_NAMES or "/" in name:
        raise ValueError(f"Forbidden name: {name}")

    if SAFE_NAME.search(name):
        return True

    logging.warning(
        "Name (%s) may cause problems with subdomains or server configuration"
    )
    return False


def url_safe_name(name: str) -> str:
    """
    Convert a name to punycode if it contains characters that aren't
    allowed in urls.
    """
    if check_name(name):
        return name

    return name.encode("punycode").decode("ascii")


def _write_nginx(directory: Path, config: Dict[str, Any], certbot: bool = True):
    LOGGER.info("Generating nginx configuration")
    domain, *rest = config["domain"].split("/", 1)
    if rest:
        url_path = f"/{rest[0]}"
    else:
        url_path = "/"
    prefix = config.get("prefix")
    users = config["users"] if config["subdomains"] else {}

    nginx_template = Template(NGINX_TEMPLATE)
    nginx_file = directory / domain
    with nginx_file.open("w") as stream:
        stream.write(
            nginx_template.render(
                domain=domain,
                url_path=url_path,
                prefix=prefix,
                users=users,
                path=config["destination"],
                url_safe_name=url_safe_name,
            )
        )

    if directory.name == "sites-available":
        symlink = directory.parent / "sites-enabled" / domain
        if not symlink.is_symlink():
            symlink.symlink_to(nginx_file)

    if certbot and users:
        subdomains = [prefix or "www"]
        domains = []

        if prefix:
            subdomains.extend((f"{prefix}.{user}" for user in users))
        else:
            subdomains.extend(users)
            subdomains.extend((f"www.{user}" for user in users))
            domains.append(domain)

        domains.extend((f"{subdomain}.{domain}" for subdomain in subdomains))

        print(
            "make sure you have DNS records set up for the following subdomains:\n"
            f"\t{', '.join(subdomains)}\n\n"
            "Once DNS records are set up, run the following certbot command "
            "to create/update a certificate that covers all your subdomains:\n"
            f"\tsudo certbot --nginx --nginx-server-root {directory.parent} "
            f"--domains {','.join(domains)}"
        )


def _write_httpd(path: Path, config: Dict[str, Any], certbot: bool = True):
    LOGGER.info("Generating httpd (apache) configuration")
    domain, *rest = config["domain"].split("/", 1)
    if rest:
        url_path = f"/{rest[0]}"
    else:
        url_path = "/"
    prefix = config.get("prefix")
    users = config["users"] if config["subdomains"] else {}

    httpd_template = Template(HTTPD_TEMPLATE)
    with path.open("w") as stream:
        stream.write(
            httpd_template.render(
                domain=domain,
                url_path=url_path,
                prefix=prefix,
                users=users,
                path=config["destination"],
                url_safe_name=url_safe_name,
            )
        )

    if certbot and users:
        subdomains = [prefix or "www"]
        domains = []

        if prefix:
            subdomains.extend((f"{prefix}.{user}" for user in users))
        else:
            subdomains.extend(users)
            subdomains.extend((f"www.{user}" for user in users))
            domains.append(domain)

        domains.extend((f"{subdomain}.{domain}" for subdomain in subdomains))

        print(
            "make sure you have DNS records set up for the following subdomains:\n"
            f"\t{', '.join(subdomains)}\n\n"
            "Once DNS records are set up, run the following certbot command "
            "to create/update a certificate that covers all your subdomains:\n"
            f"\tsudo certbot --apache --domains {','.join(domains)}"
        )


def save_config(config: dict, directory: Path):
    """
    Save the configuration file

    config: The configuration to save
    directory: The directory to save the configuration in
    """
    path = directory / FILENAME
    LOGGER.debug("saving config %s", path)
    with path.open("w") as stream:
        json.dump(
            config,
            stream,
            sort_keys=True,
            indent=4,
        )
