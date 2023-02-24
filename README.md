# Beocijies

Beocijies is a project for hosting tiny hand-written webpages for your friends.

## Philosophy

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

## Making your own beocijies site

If you want to make your own beocijies site for your friends, you should do it!
Your site doesn't need to follow the same rules as the original beocijies, but it should be made in the same spirit.
You should adapt the rules to whatever is the most fun for you and your friends.

If you don't have a computer that's on all the time, that's fine.
It's more to the ethos of beocijies to have a site that goes offline than one is hosted remotely (though it would be completely reasonable to put a remote server in front of it that provides a nice error message when your server is offline).

Some ideas on how you could adapt the the site to match your needs:
* Allow people to create remote pages by sending you postcards with the code on it (Maggie's idea)
* Have people describe their website to you over the phone, watching the page update as you implement it
* Have people come over in VR chat and make their website there

## Jinja

User pages are [Jinja templates](https://jinja.palletsprojects.com/en/3.1.x/), not bare HTML pages.

This is done to add the 'uneditable' footer image with the page update date and the user's picture.
The user should be able to edit the page just like it's an HTML page.

Another thing the jinja template allows is to easily link to other users by writing `{{user("USERNAME")}}`.

For use in the index page, the `users` variable has a list of all users that were willing to be included in a public directory.
You can link to all the users with the following code:

```jinja2
<ul>
{% for name in users %}
    <li>{{user(name)}}</li>
{% endfor %}
</ul>
```

# Install

Beocijies is being written/tested against Python 3.8.

To install, download this repo and then run:
```sh
python3 setup.py install
```

This will add a `beocijies` command that is used to set up and update the site.

# Usage

### Creating a site

```sh
beocijies create DIRECTORY --destination DESTINATION --mobile MOBILE --name NAME --domain DOMAIN
```

Where:
* `DIRECTORY`: Where to save the configuration files (including the user templates) for the project. This will default to the current directory, and will make the directory if it doesn't currently exist.
* `DESTINATION`: Where to save the generated HTML files. This is where you'll want to point your nginx (or apache) server. The directory will be made if it doesn't already exist
* `MOBILE`: Where to save the configuration files for the mobile site. This should be on your removable storage device. If you aren't making a mobile site, you don't need this.
* `NAME`: What your site is called.
* `DOMAIN`: The domain your site is hosted at

This will create an 'index' user that represents the base page.
You should edit the index page under the same conditions you expect users to update their pages.

If you rerun this script, it shouldn't erase your users or any existing templates but it will update your settings.

Your site name and domain aren't hardcoded into pages, updating the settings file should be enough to change them on all user pages.
If you're using the script-generated nginx template, you will need to regenerate it if you change domain names.

### Creating a user

```sh
beocijies add NAME
```

The user's name should be unique across both the mobile and the desktop site.
If the user wants to be included in the site directory, you should pass the `--public` flag.

By default, pages are made for both desktop and mobile environments. Pass either `--desktop` or `--mobile` to only generate a page for that environment.

Rerunning add on an existing user will update the settings for their publicness, and whether they have desktop and mobile sites.
It will create template files for the required environments, but will not overwrite any existing templates.

### Updating pages

When the user is ready to create or edit their page, run:

```sh
beocijies render --live
```

And then have the user edit the document `templates/USERNAME.html.jinja2`.
If the user has static items they want to add (e.g., images), they should add them to `static/USERNAME`.
It's up to your discretion on what a user can add, but I recommend against allowing the user to have additional pages, or to have separate CSS or Javascript files.
You will need to manually add the image of the user to their static directory. Images should be named `update-#`, incrementing the number each session.

The `--live` flag checks for further changes ever 2 seconds. If you just need to update once (e.g., updating the mobile site), you can omit it.

By default, the script is looking for changes for all users.
You can pass `--users USER1 USER2 ...` to just update a subset of them.
Remember, the main page is the user `index`, so you probably want to include that in your subset.

#### Mobile Pages

A copy of your beocijies configuration is saved in the mobile directory for access on the go (assuming you also have access to a computer with beocijies installed).
You can add users to that configuration, and then sync them when you get home by running the following on the server:

```sh
beocijies mobile-sync
```

The mobile configuration has rendered pages saved to a folder in the configuration directory named `test-build`.
Open the appropriate rendered page in your browser and the user can update their page on the go

## TODO

You might notice that this is version `0.1.0-dev`.
Here's what needs to get done before this gets even a preliminary release
* Some tests would sure be nice
* This should generate a test html page for a user to edit directly for building on computers without beocijies installed
* Add user should give you the certbot command to run after creating a user
  * reminder (see caveats in todos below):
    * edit cname for user, www.user, m.user
    * sudo brew services restart nginx
    * certbot --nginx --nginx-server-root NGINX_DIRECTORY_ROOT --email EMAIL --domains a,b,c,d,d,e
* This readme could use another pass or two
* What if the index template included the user list by default?
* The sync stuff could be better
* A system for linking to users on other beocijies?
* index should probably just be added to the users list
* nginx assumes desktop and mobile for each user
* just make people point at the nginx root instead of the servers folder
* the thread pool stuff might be bad if there are a ton of users?
* fix logging for render
* clean up render more generally