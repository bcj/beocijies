"""
Render the beocijies sites
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from shutil import copy2, rmtree
from time import sleep
from typing import Any, Callable, Dict, Optional, Sequence, Union

from jinja2 import Environment, FileSystemLoader

from beocijies.configure import FILENAME

LOGGER = logging.getLogger("beocijies")


class LinkType(Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass
class PageInfo:
    template: Path
    kwargs: Dict[str, Any]
    number: Optional[int] = None
    last: Dict[Path, int] = field(default_factory=dict)


def render(
    directory: Path,
    *,
    users: Optional[Sequence[str]] = None,
    destination: Optional[Union[bool, Path]] = None,
    link_type: Optional[LinkType] = None,
    live: bool = False,
    fresh: bool = False,
):
    with (directory / FILENAME).open("r") as stream:
        config = json.load(stream)

    if destination is True:
        destination = Path(config["destination"])
    elif not destination:
        destination = Path(config.get("test-destination", config["destination"]))

    if link_type is None:
        if config["subdomains"]:
            link_type = LinkType.ABSOLUTE
        else:
            link_type = LinkType.RELATIVE

    if not users:
        users = ["index", *config["users"]]
    elif fresh:
        raise ValueError("Users cannot be supplied if fresh is true")

    environment = Environment(loader=FileSystemLoader((directory / "templates")))
    templates = directory / "templates"
    static = directory / "static"
    domain = config["domain"]

    prefix = config.get("prefix") or "www"
    if link_type == LinkType.ABSOLUTE:
        link_format = index_link_format = f"//{prefix}.{domain}/{{}}"
    else:
        link_format = "../{}/index.html"
        index_link_format = "./{}/index.html"

    neighbours = config["neighbours"]
    public_users = {user for user, info in config["users"].items() if info["public"]}
    language = config.get("language")
    site_name = config["name"]

    def get_user(user: str) -> Callable[[str, Optional[str]], str]:
        def link_user(name: str, site: Optional[str] = None) -> str:
            text = name

            if site:
                text = f"{name} ({site})"
                if site in neighbours:
                    if name in neighbours[site]:
                        text = f"<a href={neighbours[site][name]}>{text}</a>"
            elif name in public_users:
                if user == "index":
                    format_string = index_link_format
                else:
                    format_string = link_format

                text = f"<a href={format_string.format(name)}>{name}</a>"

            return text

        return link_user

    if fresh and destination.exists():
        LOGGER.info("deleting existing rendered site")
        rmtree(destination)
    destination.mkdir(exist_ok=True, parents=True)

    # copy any files in the base
    for path in static.iterdir():
        if path.is_file():
            copy2(path, destination)

    protocol = config["protocol"]
    with (destination / "users.json").open("w") as stream:
        json.dump(
            {user: f"{protocol}://{prefix}.{domain}/{user}" for user in public_users},
            stream,
            indent=4,
            sort_keys=True,
        )

    print(users)
    pages = {
        user: PageInfo(
            templates / f"{user}.html.jinja2",
            {
                "me": user,
                "language": language,
                "site_url": domain,
                "site_name": site_name,
                "user": get_user(user),
                "users": public_users,
            },
        )
        for user in users
    }

    loop = True
    while loop:
        try:
            for user, info in pages.items():
                changed = False

                if user == "index":
                    user_destination = destination
                else:
                    user_destination = destination / user

                user_static = static / user
                directories = [user_static]
                while directories:
                    directory = directories.pop(0)
                    dest = user_destination / directory.relative_to(user_static)
                    dest.mkdir(exist_ok=True, parents=True)
                    for path in directory.iterdir():
                        if path.is_dir():
                            directories.append(path)
                        elif path.name.lower() != ".ds_store":  # thanks apple
                            modified_time = int(path.stat().st_mtime)
                            last_modified = info.last.get(path)
                            if last_modified is None or modified_time != last_modified:
                                info.last[path] = modified_time
                                changed = True
                                LOGGER.info("copying %s", path)
                                copy2(
                                    path,
                                    user_destination / path.relative_to(user_static),
                                )

                                if directory == user_static:
                                    match = re.search(r"^update-(\d+)$", path.stem)
                                    if match:
                                        number = int(match.group(1))

                                    image_number = info.number
                                    if image_number is None or number > image_number:
                                        info.number = number
                                        info.kwargs["latest_image"] = path.name

                modified_time = int(info.template.stat().st_mtime)
                last_modified = info.last.get(info.template)
                if last_modified is None or modified_time != last_modified:
                    info.last[info.template] = modified_time
                    info.kwargs["page_date"] = datetime.fromtimestamp(
                        modified_time
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    changed = True

                if changed:
                    template = environment.get_template(info.template.name)

                    try:
                        LOGGER.info("rendering page for %s", user)
                        with (user_destination / "index.html").open("w") as stream:
                            stream.write(template.render(**info.kwargs))
                    except Exception:
                        LOGGER.exception("updating page for %s failed", user)

            loop = live
            if loop:
                sleep(2)

        except KeyboardInterrupt:
            LOGGER.info("stopping")
            loop = False
