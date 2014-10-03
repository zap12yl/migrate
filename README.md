# migrate

Migrate is a database migration assistant.

## Underconstruction

This README is under construction, but here are some quick and dirty notes:

It is designed to assist with a specific type of database migration flow, to whit:

It is assumed you are working with git or a similar version control system and
have a workflow that involves something like parallel feature branches.

You have a directory called "migrations" at the top level of your project.  In
that directory, when you are working on a feature branch and want to add a new
migration, you run something like this:

    $ migrate make add_created_at

Which will create... well, I was going to say X.whatever files but it created
N.whatever files, so TODO: rework this.

...

It's assumed that you are using postgres or some other database with
transactional DDL.  If not, migrate may still work, but you're taking your life
into your own hands.

In the meantime, once you have some migrations, you can use "migrate up" and
"migrate down" to migrate all the way up to the latest version or all the way
down to zero.  You can use "migrate up <target>" or "migrate down <target>" to
migrate to a specific version.


