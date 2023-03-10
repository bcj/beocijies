"""
Run beocijies from the command line
"""
import logging
from argparse import ArgumentParser
from os import environ
from pathlib import Path
from typing import List, Optional

from beocijies.configure import (
    add_user,
    create,
    delete_user,
    forget_users,
    grab_users,
    rename_user,
)
from beocijies.render import LinkType, render


def main(input_args: Optional[List[str]] = None):
    """
    Run beocijies from the command line.
    """
    parser = ArgumentParser(description="Manage a beocijies site")

    parser.set_defaults(log_level=logging.INFO)
    parser.add_argument(
        "--debug",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        help="Show debug logs",
    )

    subparsers = parser.add_subparsers(dest="command", description="beocijies commands")

    create_parser = subparsers.add_parser("create", help="Create a beocijies site")
    create_parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Where to save the beocijies configuration",
    )
    create_parser.add_argument(
        "--destination",
        required=True,
        type=Path,
        help="Where to build the beocijies website",
    )
    create_parser.add_argument(
        "--test-destination",
        type=Path,
        help="A location to build the site for non-live edits",
    )
    create_parser.add_argument(
        "--name", default="beocijies", help="The name of the site"
    )
    create_parser.add_argument("--domain", help="The domain of the site")
    prefix_group = create_parser.add_mutually_exclusive_group()
    prefix_group.add_argument("--prefix", help="A prefix to add to all domains")
    prefix_group.add_argument(
        "--mobile",
        dest="prefix",
        action="store_const",
        const="m",
        help="Only make the site available at m.DOMAIN",
    )
    create_parser.add_argument("--language", help="The language the site is in")
    create_parser.add_argument(
        "--subdomains",
        action="store_true",
        help="Give users their own subdomains (user.yoursite.com)",
    )
    create_parser.add_argument("--robots", action="store_true", help="Allow scraping")
    create_parser.add_argument("--agents", nargs="+", help="Any user agents to allow")
    create_parser.add_argument(
        "--bad-agents", nargs="+", help="Any user agents to deny"
    )
    create_parser.add_argument(
        "--nginx",
        nargs="?",
        default=False,
        type=Path,
        help="Generate an NGINX file in this directory",
    )
    create_parser.add_argument(
        "--httpd",
        "--apache",
        type=Path,
        help="Where to generate the virtual hosts file",
    )
    create_parser.set_defaults(protocol="https")
    create_parser.add_argument(
        "--http",
        dest="protocol",
        action="store_const",
        const="http",
        help="Serve the website over http, not https",
    )

    add_parser = subparsers.add_parser("add", help="Add a beocijies user")
    add_parser.add_argument("name", help="The name of the user")
    add_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )
    add_parser.add_argument(
        "--public", action="store_true", help="List the user in the index"
    )
    add_parser.add_argument(
        "--nginx",
        nargs="?",
        default=False,
        type=Path,
        help="Generate an NGINX file in this directory",
    )
    add_parser.add_argument(
        "--httpd",
        "--apache",
        type=Path,
        help="Where to generate the virtual hosts file",
    )

    rename_parser = subparsers.add_parser("rename", help="Rename a beocijies user")
    rename_parser.add_argument("old", help="The old name of the user")
    rename_parser.add_argument("new", help="The new name of the user")
    rename_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )
    rename_parser.add_argument(
        "--nginx",
        nargs="?",
        default=False,
        type=Path,
        help="Generate an NGINX file in this directory",
    )
    rename_parser.add_argument(
        "--httpd",
        "--apache",
        type=Path,
        help="Where to generate the virtual hosts file",
    )

    delete_parser = subparsers.add_parser("remove", help="Remove a beocijies user")
    delete_parser.add_argument("name", help="The name of the user")
    delete_parser.add_argument(
        "--delete", action="store_true", help="Delete files associated with the user"
    )
    delete_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )
    delete_parser.add_argument(
        "--nginx",
        nargs="?",
        default=False,
        type=Path,
        help="Generate an NGINX file in this directory",
    )
    delete_parser.add_argument(
        "--httpd",
        "--apache",
        type=Path,
        help="Where to generate the virtual hosts file (untested)",
    )

    connect_parser = subparsers.add_parser(
        "connect", help="Grab/Update another server's user list"
    )
    connect_parser.add_argument("name", help="The name of the server")
    connect_parser.add_argument("domain", help="The domain of the server")
    connect_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )

    disconnect_parser = subparsers.add_parser(
        "disconnect", help="Forget another server's user list"
    )
    disconnect_parser.add_argument("name", help="The name of the server")
    disconnect_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )

    render_parser = subparsers.add_parser("render", help="Render beocijies sites")
    render_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )
    render_parser.add_argument(
        "users",
        nargs="*",
        help="Users to render the site for (use index for the main page)",
    )
    render_parser.add_argument(
        "--live", action="store_true", help="Watch for further changes"
    )
    destination_group = render_parser.add_mutually_exclusive_group()
    destination_group.add_argument(
        "--production",
        action="store_true",
        help="Render to destination not test-destination",
    )
    destination_group.add_argument(
        "--destination", type=Path, help="Render to this location"
    )

    link_group = render_parser.add_mutually_exclusive_group()
    link_group.add_argument(
        "--relative",
        dest="link_type",
        action="store_const",
        const=LinkType.RELATIVE,
        help="Render users with relative links",
    )
    link_group.add_argument(
        "--absolute",
        dest="link_type",
        action="store_const",
        const=LinkType.ABSOLUTE,
        help="Render users with absolute links",
    )
    render_parser.add_argument(
        "--fresh", action="store_true", help="delete existing files"
    )

    args = parser.parse_args()

    logger = logging.getLogger("beocijies")
    logger.setLevel(level=args.log_level)
    logger.addHandler(logging.StreamHandler())

    if args.command in ("create", "add", "rename", "remove"):
        if not args.nginx and args.nginx is not False:
            args.nginx = find_nginx_directory()
        if args.httpd and args.httpd.is_dir():
            args.httpd = args.httpd / "httpd-vhosts.conf"

    if args.command == "create":
        if args.domain is None:
            args.domain = environ.get("HOST", "localhost")

        create(
            args.directory,
            args.destination,
            args.name,
            test_destination=args.test_destination,
            domain=args.domain,
            prefix=args.prefix,
            language=args.language,
            allowed_agents=args.agents,
            disallowed_agents=args.bad_agents,
            robots=args.robots,
            subdomains=args.subdomains,
            nginx=args.nginx,
            httpd=args.httpd,
            protocol=args.protocol,
        )
    elif args.command == "add":
        add_user(
            args.directory,
            args.name,
            public=args.public,
            nginx=args.nginx,
            httpd=args.httpd,
        )
    elif args.command == "rename":
        rename_user(
            args.directory, args.old, args.new, nginx=args.nginx, httpd=args.httpd
        )
    elif args.command == "remove":
        delete_user(
            args.directory,
            args.name,
            delete_files=args.delete,
            nginx=args.nginx,
            httpd=args.httpd,
        )
    elif args.command == "connect":
        grab_users(args.directory, args.name, args.domain)
    elif args.command == "disconnect":
        forget_users(args.directory, args.name)
    elif args.command == "render":
        render(
            args.directory,
            destination=args.destination or args.production,
            users=args.users,
            live=args.live,
            fresh=args.fresh,
            link_type=args.link_type,
        )
    else:
        raise NotImplementedError(f"Haven't added support for command {args.command!r}")


def find_nginx_directory() -> Path:
    paths = []

    # sorry, I own a mac. I'm going to try mac stuff first
    if "HOMEBREW_PREFIX" in environ:
        paths.append(Path(environ["HOMEBREW_PREFIX"]) / "etc/nginx/")

    # where else might nginx store its config?
    # https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/
    paths.extend(
        (
            Path("/etc/nginx/"),
            Path("/usr/local/nginx/"),
            Path("/usr/local/nginx/conf/"),
            Path("/usr/local/etc/nginx/"),
        )
    )

    logging.debug("looking for NGINX directory")
    for path in paths:
        # nginx might want your server config in servers or it might
        # want you to put it in a 'sites-available' directory and then
        # symlinked in 'sites-enabled'.
        for name in ("servers", "sites-available"):
            directory = path / name

            logging.debug("checking %s", directory)
            if directory.exists():
                return directory

    raise ValueError(
        "Could not find NGINX servers directory. "
        "(tried looking for 'servers' and 'sites-available' in: {})".format(
            ", ".join(map(str, paths))
        )
    )


if __name__ == "__main__":
    main()
