"""
Render the beocijies sites
"""
import json
import logging
import re
from datetime import datetime
from multiprocessing import Pool, get_logger
from pathlib import Path
from shutil import copy2, copytree
from subprocess import check_call
from time import sleep
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from beocijies.configure import FILENAME


def render(
    directory: Path,
    users: Optional[List[str]] = None,
    live: bool = False,
    absolute: bool = False,
):
    with (directory / FILENAME).open("r") as stream:
        config = json.load(stream)

    if users is None:
        users = list(config["users"])

    destination = Path(config["destination"])

    environment = Environment(loader=FileSystemLoader((directory / "templates")))
    templates = directory / "templates"
    static = directory / "static"

    mobile_environment = mobile_templates = mobile_static = None

    for path in static.iterdir():
        if path.is_file():
            copy2(path, destination)

    if config.get("mobile"):
        mobile_directory = Path(config["mobile"])
        if mobile_directory.exists():  # drive plugged in
            mobile_environment = Environment(
                loader=FileSystemLoader((mobile_directory / "templates"))
            )
            mobile_templates = mobile_directory / "templates"
            mobile_static = mobile_directory / "static"

            (destination / "mobile").mkdir(exist_ok=True)
            fake_desktop = destination / "mobile" / "desktop"
            if not (absolute or fake_desktop.is_symlink()):
                check_call(("ln", "-s", str(destination), str(fake_desktop)))

            for path in mobile_static.iterdir():
                if path.is_file():
                    copy2(path, destination / "mobile")

    public_users = []
    mobile_public_users = []
    to_update = []
    for user, info in config["users"].items():
        if info["public"]:
            if info["desktop"]:
                public_users.append(user)

            if info["mobile"]:
                mobile_public_users.append(user)

        if user in users:
            if info["desktop"]:
                to_update.append(
                    (
                        user,
                        environment,
                        templates / f"{user}.html.jinja2",
                        static / user,
                        destination if user == "index" else destination / user,
                        public_users,
                        mobile_public_users,
                        config["language"],
                        config["domain"],
                        config["name"],
                        "desktop",
                        live,
                        absolute,
                    )
                )

            if (
                info["mobile"]
                and mobile_environment
                and mobile_templates
                and mobile_static
            ):
                to_update.append(
                    (
                        user,
                        mobile_environment,
                        mobile_templates / f"{user}.html.jinja2",
                        mobile_static / user,
                        (
                            destination / "mobile"
                            if user == "index"
                            else destination / "mobile" / user
                        ),
                        public_users,
                        mobile_public_users,
                        config["language"],
                        config["domain"],
                        config["name"],
                        "mobile",
                        live,
                        absolute,
                    )
                )

    with Pool(len(to_update)) as pool:
        pool.starmap(watch_site, to_update)


def watch_site(
    user: str,
    environment: Environment,
    template_file: Path,
    static: Path,
    destination: Path,
    users: List[str],
    mobile_users: List[str],
    language: Optional[str],
    site_url: str,
    site_name: str,
    site_type: str,
    live: bool = False,
    absolute: bool = False,
):
    logger = get_logger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

    page_date = "Never"
    latest_image = None
    image_number = 0
    modified_times: Dict[Path, int] = {}

    destination.mkdir(exist_ok=True)

    if absolute:
        desktop_path = f"//{site_url}/{{}}/index.html"
        mobile_path = f"//m.{site_url}/{{}}/index.html"

        if site_type == "desktop":
            local_users = users

            paths = {name: desktop_path.format(name) for name in users}
            for name in mobile_users:
                paths.setdefault(name, mobile_path.format(name))
        else:
            paths = {name: mobile_path.format(name) for name in mobile_users}
            for name in users:
                paths.setdefault(name, desktop_path.format(name))

            local_users = mobile_users
    else:
        dots = "." if user == "index" else ".."
        if site_type == "desktop":
            desktop_path = f"{dots}/{{}}/index.html"
            mobile_path = f"{dots}/mobile/{{}}/index.html"

            paths = {name: desktop_path.format(name) for name in users}
            for name in mobile_users:
                paths.setdefault(name, mobile_path.format(name))

            local_users = users
        else:
            desktop_path = f"{dots}/desktop/{{}}/index.html"
            mobile_path = f"{dots}/{{}}/index.html"

            paths = {name: mobile_path.format(name) for name in mobile_users}
            for name in users:
                paths.setdefault(name, desktop_path.format(name))

            local_users = mobile_users

    def get_user(name: str) -> str:
        if name in paths:
            return f'<a href="{paths[name]}">{name}</a>'

        return name

    loop = True
    while loop:
        changed = False

        for path in (*static.iterdir(), template_file):
            if path.name.lower() == ".ds_store":
                continue

            modified_time = int(path.stat().st_mtime)
            if path not in modified_times or modified_times[path] < modified_time:
                changed = True
                modified_times[path] = modified_time

                if path != template_file:
                    logger.info("copying %s", path)
                    if path.is_dir():
                        copytree(path, destination)
                    else:
                        copy2(path, destination)

                match = re.search(r"^update-(\d+)$", path.stem)
                if match:
                    number = int(match.group(1))

                    if latest_image is None or number > image_number:
                        image_number = number
                        latest_image = path.name

            if path == template_file:
                page_date = datetime.fromtimestamp(modified_time).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        if changed:
            template = environment.get_template(template_file.name)

            try:
                logger.info("rendering page for %s", user)
                with (destination / "index.html").open("w") as stream:
                    stream.write(
                        template.render(
                            me=user,
                            language=language,
                            site_url=site_url,
                            site_name=site_name,
                            latest_image=latest_image,
                            page_date=page_date,
                            user=get_user,
                            users=local_users,
                        )
                    )
            except Exception:
                logger.exception("updating page for %s failed", user)

        loop = live
        if loop:
            sleep(2)
