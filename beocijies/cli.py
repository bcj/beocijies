"""
Run beocijies from the command line
"""
from argparse import ArgumentParser
from pathlib import Path
from typing import List, Optional

from beocijies.configure import add_user, create, mobile_import
from beocijies.render import render

NGINX_DIRECTORY = Path("/opt/homebrew/etc/nginx/servers")


def main(input_args: Optional[List[str]] = None):
    """
    Run beocijies from the command line.
    """
    parser = ArgumentParser(description="Manage a beocijies site")

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
        "--mobile",
        type=Path,
        help="Where to save the mobile configurations",
    )
    create_parser.add_argument("--name", required=True, help="The name of the site")
    create_parser.add_argument(
        "--domain", default="localhost", help="The name of the site"
    )
    create_parser.add_argument("--language", help="The language the site is in")
    create_parser.add_argument(
        "--subdomains",
        action="store_true",
        help="Give users their own subdomains (user.domain/m.user.domain)",
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
        help="Generate an nginx file in this location",
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
        "--no-desktop", dest="desktop", action="store_false", help="Make a default page"
    )
    add_parser.add_argument("--mobile", action="store_true", help="Make a mobile page")
    add_parser.add_argument(
        "--nginx",
        nargs="?",
        default=False,
        type=Path,
        help="Generate an nginx file in this location",
    )

    render_parser = subparsers.add_parser("render", help="Render beocijies sites")
    render_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )
    render_parser.add_argument(
        "--users", nargs="+", help="Users to render the site for"
    )
    render_parser.add_argument(
        "--live", action="store_true", help="Watch for further changes"
    )

    mobile_parser = subparsers.add_parser(
        "mobile-sync", help="Pull in new mobile users"
    )
    mobile_parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="The beocijies configuration directory",
    )

    args = parser.parse_args()

    if args.command in ("create", "add"):
        if args.nginx is not False:
            args.nginx = NGINX_DIRECTORY

    if args.command == "create":
        create(
            args.directory,
            args.destination,
            args.name,
            mobile=args.mobile,
            domain=args.domain,
            language=args.language,
            allowed_agents=args.agents,
            disallowed_agents=args.bad_agents,
            robots=args.robots,
            subdomains=args.subdomains,
            nginx=args.nginx,
        )
    elif args.command == "add":
        add_user(
            args.directory,
            args.name,
            public=args.public,
            desktop=args.desktop,
            mobile=args.mobile,
            nginx=args.nginx,
        )
    elif args.command == "render":
        render(args.directory, users=args.users, live=args.live)
    elif args.command == "mobile-sync":
        mobile_import(args.directory)
    else:
        raise NotImplementedError(f"Haven't added support for command {args.command!r}")


if __name__ == "__main__":
    main()
