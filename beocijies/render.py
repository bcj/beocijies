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
from typing import Any, Callable, Iterable, Optional, Union
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from notifypy import Notify  # type: ignore

from beocijies.configure import FILENAME, UPDATES_FILENAME, Feed

# reminder to self: you can do this from 3.11+
try:
    from datetime import UTC  # type: ignore
except ImportError:
    from datetime import timedelta, timezone

    UTC = timezone(timedelta(0))

LOGGER = logging.getLogger("beocijies")

POST_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
ATOM_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RSS_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z"


class LinkType(Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass
class PageInfo:
    template: Path
    kwargs: dict[str, Any]
    number: Optional[int] = None
    last: dict[Path, int] = field(default_factory=dict)


# reminder to self: Union -> | as of min 3.10
def render(
    directory: Path,
    *,
    users: Optional[set[str]] = None,
    destination: Optional[Union[bool, Path]] = None,
    link_type: Optional[LinkType] = None,
    live: bool = False,
    notify: bool = False,
    fresh: bool = False,
):
    """
    Render a website

    directory: the directory containing the config file
    users: Optionally, a list of users to render pages for. If not
        supplied, all users and the index will be updated.
    destination: Either, the location to render the site at, True, to
        use the main destination in the config, or False/None to default
        to a test destination if it is defined.
    link_type: Either relative or absolute, or None to default based on
        whether the site uses subdomains
    live: Watch for new changes and continue to update as they appear.
    notify: Send a desktop notification if rendering fails
    fresh: Delete existing files before rendering. If supplied, a user
        list cannot be supplied
    """
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
        users = set({"index", *config["users"]})
    elif fresh:
        raise ValueError("Users cannot be supplied if fresh is true")

    environment = Environment(loader=FileSystemLoader((directory / "templates")))
    templates = directory / "templates"
    static = directory / "static"
    domain = config["domain"]

    if config.get("prefix"):
        prefix = f"{config['prefix']}."
    elif config.get("local", False):
        prefix = ""
    else:
        prefix = "www."

    protocol = config["protocol"]
    if link_type == LinkType.ABSOLUTE:
        link_format = index_link_format = f"{protocol}://{prefix}{domain}/{{}}"
    else:
        link_format = "../{}/index.html"
        index_link_format = "./{}/index.html"

    neighbours = config["neighbours"]
    public_users = {
        user for user, info in config["users"].items() if info.get("public", False)
    }
    language = config.get("language")
    site_name = config["name"]

    def get_user(user: str) -> Callable[[str, Optional[str]], str]:
        def link_user(name: str, site: Optional[str] = None) -> str:
            text = name

            if site:
                text = f"{name} ({site})"
                if site in neighbours:
                    if name in neighbours[site]:
                        text = f"<a href={neighbours[site][name]!r}>{text}</a>"
            elif name in public_users:
                if user == "index":
                    format_string = index_link_format
                else:
                    format_string = link_format

                text = f"<a href={format_string.format(name)!r}>{name}</a>"

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

    with (destination / "users.json").open("w") as stream:
        json.dump(
            {user: f"{protocol}://{prefix}{domain}/{user}" for user in public_users},
            stream,
            indent=4,
            sort_keys=True,
        )

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
                "neighbours": neighbours,
                "has_feed": Feed.NONE
                != Feed(config["users"].get(user, {}).get("feed", "personal")),
            },
        )
        for user in users
    }

    failing_users = set()
    updated = set()

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
                    current_directory = directories.pop(0)
                    dest = user_destination / current_directory.relative_to(user_static)
                    dest.mkdir(exist_ok=True, parents=True)
                    for path in current_directory.iterdir():
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

                                if current_directory == user_static:
                                    match = re.search(r"^update-(\d+)$", path.stem)
                                    if match:
                                        number = int(match.group(1))

                                        if info.number is None or number > info.number:
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

                        if user not in failing_users and notify:
                            failing_users.add(user)
                            send_notification(f"Building page for {user} failed")

                        if not live:
                            raise
                    else:
                        if user in failing_users and notify:
                            failing_users.remove(user)
                            send_notification(f"Page for {user} fixed")

                    updated.add(user)

            loop = live
            if loop:
                sleep(2)

        except KeyboardInterrupt:
            LOGGER.info("stopping")
            loop = False

    LOGGER.info(f"updated pages for {', '.join(sorted(updated))}")

    global_feed = Feed(config["users"].get("index", {}).get("feed", "personal"))
    if global_feed != Feed.NONE and updated:
        updates_file = directory / UPDATES_FILENAME

        if updates_file.exists():
            with updates_file.open("r") as stream:
                updates = json.load(stream)
        else:
            updates = {}

        for user in updated:
            user_feed = Feed(config["users"].get(user, {}).get("feed", "personal"))

            if user == "index":
                listed_user = None
                user_page = destination / "index.html"
                user_root = f"{protocol}://{prefix}{domain}"
            else:
                listed_user = user
                user_page = destination / user / "index.html"
                user_root = f"{protocol}://{prefix}{domain}/{user}"

            updates[user] = parse_entries(
                user_page, user_root, static / user, site_name, user=listed_user
            )

        with updates_file.open("w") as stream:
            json.dump(updates, stream, indent=4, sort_keys=True)

        for user in users:
            user_feed = Feed(config["users"].get(user, {}).get("feed", "personal"))
            if user_feed != Feed.NONE:
                root_url = f"{protocol}://{prefix}{domain}/{user}/"

                user_entries = updates.get(user, {})

                LOGGER.info("rendering feed for %s", user)
                posts = sort_posts(user_entries.values())
                build_atom(posts, destination, site_name, root_url, user=user)
                build_rss(posts, destination, site_name, root_url, user=user)

        if global_feed != Feed.NONE:
            root_url = f"{protocol}://{prefix}{domain}/"

            LOGGER.info("rendering global feed")
            posts = sort_posts(
                post
                for user, user_posts in updates.items()
                for post in user_posts.values()
                if Feed(config["users"].get(user, {}).get("feed", "personal"))
                == Feed.PUBLIC
            )
            build_atom(posts, destination, site_name, root_url)
            build_rss(posts, destination, site_name, root_url)


def parse_entries(
    page: Path, url_root: str, static: Path, site_name: str, user: Optional[str] = None
) -> dict[str, dict[str, str]]:
    """
    Parse h-entries within a page

    page: The webpage to fetch entries from
    url_root: The URL of this page
    user: Who created the page
    """
    entries = {}

    with (page).open("r") as stream:
        root = BeautifulSoup(stream.read(), "html.parser")

    for node in root.select(".h-entry"):
        if not node["id"]:
            LOGGER.warning("Entry for user %s missing id", user)
            continue

        entry_id = str(node["id"])

        if entry_id in entries:
            LOGGER.warning("Duplicate entry id for user %s: %s", user, entry_id)
            continue

        entry: dict[str, str] = {
            "id": entry_id,
            "url": f"{url_root}/index.html#{entry_id}",
        }

        if user:
            entry["author"] = user

        title_node = node.select_one(".p-name")
        if title_node:
            entry["title"] = title_node.text.strip() or ""

        summary_node = node.select_one(".p-summary")
        if summary_node:
            entry["summary"] = summary_node.text.strip() or ""

        author_node = node.select_one(".p-author")
        if author_node:
            entry["author"] = author_node.text.strip()

        for key, selector in (
            ("published", "time.dt-published"),
            ("updated", "time.dt-updated"),
        ):
            time_node = node.select_one(selector)

            if time_node is None:
                continue

            try:
                datetime.strptime(str(time_node["datetime"]), POST_DATE_FORMAT)
            except Exception:
                LOGGER.warning(
                    "Could not parse date for user %s's post %s: %s",
                    user,
                    entry_id,
                    time_node["datetime"],
                )
            else:
                entry[key] = str(time_node["datetime"])

        if "published" not in entry:
            LOGGER.warning("Could not find date for user %s's post: %s", user, entry_id)
            continue

        entry.setdefault("updated", entry["published"])

        summary_node = node.select_one(".p-summary")
        if summary_node:
            entry["summary"] = summary_node.text.strip()

        content_node = node.select_one(".e-content")

        if content_node:
            entry["contents"] = str(content_node)
            entries[entry_id] = entry
        else:
            LOGGER.warning(
                "Could not find contents for user %s's post: %s", user, entry_id
            )

    earliest = latest = None
    for path in static.iterdir():
        if path.is_file() and re.search(r"^update-\d+$", path.stem):
            mtime = path.stat().st_mtime
            if earliest is None or mtime < earliest:
                earliest = mtime

            if latest is None or mtime > latest:
                latest = mtime

    if earliest is not None and latest is not None:
        if earliest == latest:
            action = "created"
        else:
            action = "updated"

        if not user or user == "index":
            summary = f"{site_name} {action}"
        else:
            summary = f"{user} {action} their {site_name}"

        contents = f"<p>{summary}</p>"

        entry = {
            "id": "",
            "url": f"{url_root}/index.html",
            "published": datetime.fromtimestamp(earliest, UTC).strftime(
                POST_DATE_FORMAT
            ),
            "updated": datetime.fromtimestamp(latest, UTC).strftime(POST_DATE_FORMAT),
            "contents": contents,
            "summary": summary,
        }

        if user:
            entry["author"] = user

        entries[""] = entry

    return entries


def build_atom(
    posts: list[dict[str, str]],
    directory: Path,
    site_name: str,
    root_url,
    user: Optional[str] = None,
):
    now = datetime.now(UTC)

    root = ElementTree.Element("feed", attrib={"xmlns": "http://www.w3.org/2005/Atom"})

    ElementTree.SubElement(root, "id").text = root_url
    ElementTree.SubElement(root, "title").text = site_name
    ElementTree.SubElement(root, "updated").text = now.strftime(ATOM_DATE_FORMAT)

    ElementTree.SubElement(
        root,
        "link",
        attrib={"rel": "self", "href": f"{root_url}atom.xml"},
    )

    ElementTree.SubElement(root, "subtitle").text = "A beocijies site"

    for post in posts:
        entry = ElementTree.SubElement(root, "entry")
        ElementTree.SubElement(
            entry,
            "link",
            attrib={"rel": "alternate", "href": post["url"]},
        )
        ElementTree.SubElement(entry, "id").text = post["url"]

        author = post.get("author", user or f"A {site_name} user")

        ElementTree.SubElement(
            ElementTree.SubElement(entry, "author"),
            "name",
        ).text = author

        ElementTree.SubElement(entry, "title").text = post.get(
            "title", f"{site_name} update"
        )
        ElementTree.SubElement(entry, "published").text = datetime.strptime(
            post["published"], POST_DATE_FORMAT
        ).strftime(ATOM_DATE_FORMAT)
        ElementTree.SubElement(entry, "updated").text = datetime.strptime(
            post["updated"], POST_DATE_FORMAT
        ).strftime(ATOM_DATE_FORMAT)

        ElementTree.SubElement(entry, "content", attrib={"type": "html"}).text = post[
            "contents"
        ]

        summary = f"{author} updated a post on {site_name}"
        ElementTree.SubElement(entry, "summary").text = post.get("summary", summary)

    if user and user != "index":
        path = directory / user / "atom.xml"
    else:
        path = directory / "atom.xml"

    ElementTree.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)


def build_rss(
    posts: list[dict[str, str]],
    directory: Path,
    site_name: str,
    root_url,
    user: Optional[str] = None,
):
    now = datetime.now(UTC)

    root = ElementTree.Element(
        "rss", attrib={"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"}
    )

    channel = ElementTree.SubElement(root, "channel")
    ElementTree.SubElement(channel, "title").text = site_name
    ElementTree.SubElement(channel, "lastBuildDate").text = now.strftime(
        RSS_DATE_FORMAT
    )

    ElementTree.SubElement(channel, "link").text = f"{root_url}rss.xml"
    ElementTree.SubElement(
        channel,
        "atom:link",
        attrib={"rel": "self", "href": f"{root_url}atom.xml"},
    )

    ElementTree.SubElement(channel, "description").text = "A beocijies site"

    for post in posts:
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "link").text = post["url"]
        ElementTree.SubElement(item, "guid").text = post["url"]
        ElementTree.SubElement(item, "title").text = post.get(
            "title", f"{site_name} update"
        )
        ElementTree.SubElement(item, "pubDate").text = datetime.strptime(
            post["updated"], POST_DATE_FORMAT
        ).strftime(RSS_DATE_FORMAT)

        author = post.get("author", user or f"A {site_name} user")
        summary = f"{author} updated a post on their {site_name}"
        ElementTree.SubElement(item, "description").text = post.get("summary", summary)

    if user and user != "index":
        path = directory / user / "rss.xml"
    else:
        path = directory / "rss.xml"

    ElementTree.ElementTree(root).write(path, encoding="UTF-8")


def sort_posts(posts: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    # I don't think atom/rss actually require entries to be in a specific
    # order but we're going to sort to put the newest first since that's
    # how they'll be read and we'll further sort by author/id (although
    # reverse-alphabetically) just to ensure a consistent post order
    return sorted(
        posts,
        key=lambda post: (
            post["updated"],
            post["published"],
            post.get("author", ""),
            post["id"],
        ),
        reverse=True,
    )


def send_notification(message):
    notification = Notify()
    notification.title = "beocijies"
    notification.message = message

    notification.send()
