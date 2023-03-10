# Beocijies

Beocijies is a project for hosting tiny hand-written webpages for your friends.

Quick Links:
* [Install](#install)
* [Prerequisites](#what-youll-need)
* [Creating a beocijies](#creating-your-site)
* [Adding users](#adding-users)
  * [Updating users](#updating-users)
  * [Removing users](#updating-users)
* [Creating/Updating pages](#rendering-your-site)
* [Creating/Updating mobile pages](#rendering-on-the-go)

# Install

Beocijies is being written/tested against Python 3.8.

Beocijies is available on PyPI and can be installed by running:
```sh
pip3 install beocijies
```

You may also install it by, downloading this repo and then running:
```sh
python3 setup.py install
```

This will add a `beocijies` command that is used to set up and update the site.

# Philosophy

[beocijies.com](https://beocijies.com) was, first and foremost, made as an excuse to invite friends over.
All other goals for the project are in service of that.

The idea of beocijies is making personal webpages that are actually personal.
Pages are written by hand, so they're limited in scope and completely made by the user.
Pages are written directly on the computer hosting the site, so the server isn't abstract.
Pages are live-updated, so the process of making a page is made visible.
Pages include an image of the user updating the page, so this process is kept visible after the fact.
And pages are made in coordination with the person who hosts the website, so changes are a social event.

The idea has since expanded to include 'mobile' pages, in an attempt to replicate the process for those that can't easily travel to the server.
Files for the mobile site live on a flash drive, and are added to the site when the host returns home.

# Your own beocijies Site

If you want to make your own beocijies site for your friends, you should do it!
Your site doesn't need to follow the same rules as the original beocijies, but it should be made in the same spirit.
You should adapt the rules to whatever is the most fun for you and your friends.

Some ideas on how you can set up your site to match your needs:
* Have people come over and make edits on the server (how beocijies.com works)
* Have people make their pages on a flash drive you carry around (how m.beocijies.com works)
* Allow people to create remote pages by sending you postcards with the code on it (Maggie's idea)
* Have people describe their website to you over the phone, watching the page update as you implement it
* Have people come over in VR chat and make their website there

Also, you really don't need to refer to it as a 'beocijies' site.
'beocijies' is unwieldy and is just a dumb joke based on my name.
Pick something personal to you.

## What you'll need

### A Computer You Can Use as a Server

If you don't have a computer that's on all the time, that's fine.
It's more to the ethos of beocijies to have a site that goes offline than one is hosted remotely (though it would be completely reasonable to put a remote server in front of it that provides a nice error message when your server is offline).

This code has only been tested on macOS and linux.
It should _probably_ work with WSL 2.0 and maybe even normal Windows?
Good luck.

### Python 3.8 or later

The code used to create all the configuration files and to render people's pages (see the section on [Jinja](#jinja) for more details) needs at least this recent of Python.

As long as you're fine manually copying the files over, this actually could be done from a different computer.

### A Web Server

The code in this repo will create all the required files, but doesn't come with a web-server.
This project officially recommends using [NGINX](https://nginx.org/en/), and can automatically generate the configuration file required for hosting your site with NGINX.

The project also has provisional support for [httpd (Apache)](https://httpd.apache.org/), but it is completely untested and has not been confirmed to work

The generated templates are all for HTTP, not HTTPS.
This is done with the assumption that you'll then use [certbot](https://certbot.eff.org/) to set up SSL certificates for your site.

### A Domain

If you already have a separate domain, you could host your beocijies pages on a subdomain (e.g., `beocijies.yoursite.com`), or as an address within your site (e.g., `yoursite.com/beocijies`).

#### Intranet sites

If you just want to run your beocijies site within a local network (e.g., your home/dorm), you can use your computer's network name.
If you don't supply a domain when creating a beocijies, it will default to your computer's name.

#### DNS

If you want each user to have their own subdomain, you'll need to update your DNS records whenever you add a new user.

If you're ISP doesn't provide you with a static IP address, you'll need to use [Dynamic DNS](https://en.wikipedia.org/wiki/Dynamic_DNS) to point to your server.
Your domain registrar may offer this as a free service, as might your ISP or even the manufacturer of your router.

## Creating your site

To create a website, use the `create` command:
```sh
beocijies create DIRECTORY --destination DESTINATION --name NAME --domain DOMAIN
```

This will create the configuration for your site in the supplied directory (creating the directory if it doesn't already exist).
Within the directory, the following files and directories will be generated:
* `settings.json`: This contains all the information about your site in a format that is, technically, readable. It is safe to edit this directly, but you generally shouldn't need to.
* `static`: Any files in this directory will be copied to the site. Any files or folders in a user's subdirectory will be copied to their section of the site. When updating the main page for the site, you should put the update images in the `index` subdirectory.
* `templates`: This will contain the templates for each user's personal page as well as a few extra files:
  * `base.html.jinja2`: All of the sites pages 'extend' this page. If you would like to edit how the footer for all the pages look, you'll need to edit this page.
  * `default.html.jinja2`: When you add a user to this site, their page will be a copy of this page. If you edit this page, it won't affect the pages of any user that already exists.
  * `index.html.jinja2`: This is the base homepage for your site. Internally, beocijies (mostly) pretends that index is just another user of the site. This means you can adjust some settings for the user using the various user commands.

It is safe to rerun the `create` command.
On rerun, any settings will be updated and any files that don't exist will be created.
No existing files in the `static` or `templates` directories will be replaced.

If you want users to be able to access their pages at `user.yoursite.com` instead of just `yoursite.com/user`, pass the `--subdomains` flag.
If you make this change, you'll need to update your web server and your DNS records every time you add a user.

```sh
beocijies create DIRECTORY --destination DESTINATION --name NAME --domain DOMAIN --subdomains
```

If you want to have beocijies generate an NGINX template for you, use the `--nginx` flag.
The script will try to find the server configuration directory NGINX is expecting, but if the directory is in a unexpected location, you'll need to pass the path along with the flag.

If you plan on hosting your site over http instead of https, pass the `--http` flag.

### Mobile

If you would like to have a 'mobile' version of the website, pass the `--mobile` flag.
If you're setting up a mobile site and plan to have user build their pages on a computer that can run the beocijies script, you should also pass `--test-destination` and supply a location on that removable storage device.

If you won't (or won't always) having people build their site on a computer with the beocijies script, don't worry.
There are [instructions](#rendering-on-the-go) for working around this.

### Web Crawlers

By default, beocijies creates a [robots.txt](https://en.wikipedia.org/wiki/Robots.txt) file that blocks all web crawlers.
This means Google and others won't index your site.
You can enable crawling by passing the `--robots` flag.
Additionally, you can allow individual crawlers by passing a list of names to `--agents` and/or block individual crawlers by passing a list of names to `--bad-agents`.

## Users

Each user on your website will need their own unique username.
While it's strongly recommended that there are restrictions on when/how a user can create or update their page, you should allow users to change their username, make their page private, or delete their page on request with none of those restrictions.

Because usernames are included in URLs, it's strongly recommended that you restrict usernames to just include Latin letters, digits, and hyphens.
Usernames should also be considered case insensitive.
If you're not providing subdomains for users, you can be a bit more permissive.

If a user is public, their name will be included in the `users.json` file made available on your server and other users will be able to link to them.
It is recommended that you only put public users in any site directory you create.

### Adding Users

To add a user, use the `add` command:
```sh
beocijies add NAME
```

This command should be run from within your beocijies configuration directory (but can be run from anywhere by passing the `--directory` flag with the path to that directory).

This command will add the user to your internal users list, create a template for them in your template directory (copied from your default template), and a static file directory for them in your static folder.
Rerunning this command is safe, and will not affect existing files in your static or template directories.

Users are made private by default, but can be made public using the `--public` flag:
```sh
beocijies add NAME --public
```

**NOTE**: No Changes will take affect on your site until you [render it](#rendering-your-site).

### Updating Users

If a user wants to change their public/private status, you should rerun add with/without the `--public` flag.

If a user wants to change their username, use the rename command:
```
beocijies rename OLD NEW
```

This will change their name and move their template and static files to a location matching their new name.
This will not edit any references to them on other people's pages (you should use your own discretion in deciding whether those references should be updated manually)

**NOTE**: No Changes will take affect on your site until you [render it](#rendering-your-site).

### Removing Users

If a user no longer wishes to have a page, you can remove them with the `remove` command:
```
beocijies remove NAME
```

This command will only delete their template and static files if you pass the `--delete` command.

Their page will still be accessible until you delete the rendered files.
You can do this by [rendering](#rendering-your-site) with the `--fresh` flag.

### Managing Subdomains

If you wish to make users pages available at custom subdomains, you will need to make changes to your DNS records and server configuration each time you add or rename a user (and preferably if you remove them).

You will also need to update your server configuration and generate SSL certificates as necessary.

If you want beocijies to generate an NGINX template for you, use the `--nginx` flag when running `create`/`add`/`rename`/`remove`.
The script will try to find the server configuration directory NGINX is expecting, but if the directory is in a unexpected location, you'll need to pass the path along with the flag.

When you run commands with the `--nginx` flag, it will tell you which subdomains need DNS records and the `certbot` command required to update your certificate (this assumes you've already set up a certbot account).

## Rendering Your Site

When a user is ready to create/update their website, run the `render` command:
```sh
beocijies render
```

By default, the script just updates the page once.
If you would like the script to watch for further changes and rerender any time it sees them, pass the `--live` flag:
```sh
beocijies render --live
```

This will watch for changes to any page.
You can pass any number of users (and/or 'index' for the main page) to just update those pages:
```sh
beocijies render index user1 user2 --live
```

If you configured your site with a test destination, that's what the script will default to.
You can render to the 'real' destination with the `--production` flag:
```sh
beocijies render --production
```

If you didn't supply a test destination in your configuration, you don't need to pass this flag.

Or to a custom destination with the `--destination` flag:
```sh
beocijies render --destination LOCATION
```

By default, beocijies renders local links to other local users as absolute if you allow subdomains and relative otherwise.
If you want to override this behavior (e.g., you are doing local testing for a mobile site and just loading the files in the browser of your choice), use the `--relative` or `--absolute` flags.

### Updating Pages

Whenever a user is updating their page (or you are updating the main page), you should add a new photo that you take during the editing session.
The photo should go in the user folder within the `static` directory (or the `index` folder within `static` for the main page).
Any filetype the `img` tag accepts is fine, but the file should be named `update-NUMBER`, with number starting at `1` and being incremented every time that page is updated.
The page will automatically display the image with the highest number for that user.

The users page will be in the `templates` directory and will be named `USERNAME.html.jinja2` (see [jinja](#jinja) for why this isn't just an html page).
This template will be rendered to `domain/USER/index.html`.
The user directory will also contain any files the user adds to their static folder.
What they can add is up to your discretion, but I recommend against allowing the user additional pages or allowing them separate CSS or JavaScript files.

### Jinja

User pages are [Jinja templates](https://jinja.palletsprojects.com/en/3.1.x/), not bare HTML pages.

This is done to add the 'uneditable' footer image with the page update date and the user's picture.
The user should be able to treat the template just like an HTML page, writing the header and body in the two provided 'blocks'.
It is unlikely that a user would accidentally add something to their page that Jinja would interpret weirdly (and the script will provide an error message if this does occur).

A user-facing feature that the Jinja template provides, is a way to easily link to other user pages by writing `{{user("USERNAME")}}`.

For use in the index page, the `users` variable has a list of all users that were willing to be included in a public directory.
You can link to all the users with the following code:

```jinja2
<details open=true>
    <summary>users:</summary>
    <ul>
    {% for name in users | sort %}
        <li>{{user(name)}}</li>
    {% endfor %}
    </ul>
</details>
```

#### Referencing Users on Other Sites

If you have multiple sites (e.g., desktop and mobile), or have a cool webring with another beocijies site, you can make it easy for your users to reference the users on that site.

Use the `connect` command to grab a server's user list:
```sh
beocijies connect NAME DOMAIN
```

where `NAME` is how you'll refer to that site and `DOMAIN` is the base page of that site.
E.g., for the original beocijies site:
```sh
beocijies connect beocijies https://beocijies.com
```

Your users can now link to the user by saying `{{user("USERNAME", "SITENAME")` (e.g., `{{user("bcj", "beocijies")}}`) and if that user is public on that site, that will be replaced with a link and the text `USER (SITE)` (e.g., `bcj (beocijies)`).

You can update the user list by rerunning the command and you can forget about that site with the disconnect command:
```sh
beocijies disconnect NAME
```

Site names must be unique but have no other restrictions.

### Rendering on the Go

If you know in advance that a user is going to be making their page on a computer that doesn't run the beocijies script, you should add the user in advance, add a dummy update image to their static directory, then render that empty page to a location on the removable storage device they'll edit the file on.
They can then just edit that rendered page directly, and view the file in their browser of choice as they edit.
When you get home, you can copy the information they changed back into a template.

Chances are, you have not heavily customized the default user page.
Because of this, you can also have new users write a brand new html page and deal with putting their page back into the template later.
Likewise, you can have existing users download their current page if you have an internet connection.

# Future Work

I wouldn't expect a lot of it.
This whole project is a goofy toy and it's already good enough at being that.
I'll add some silly features if they sound fun and fix any bugs people run into.

* A number of the tests for this are pretty rudimentary, and they don't even lint the nginx/httpd configurations that are generated
* Actually, the apache stuff hasn't been tested at all yet.
* Nothing's in place for migrating configuration files if updates include breaking changes. It will be added once it's needed