# migrator

Migrator is a database migration assistant.

The tool is designed to automate common tasks that are necessary when
maintaining your migrations as a sequentially numbered series of
N.<description>.up.sql and N.<description>.down.sql files.


## Commands

### migrate install

This command creates the 'migrations' table in the database which is necessary
for all subsequent operations.

    $ migrate install

No output means it worked.

### migrate up

This command migrates the database version from a lower number to a higher
number -- that is, moving forwards in time.

To migrate the database to the most recent known version, simply:

    $ migrate up
    SELECTED VERSION: 2
    Migrations that will be brought up:
    migrations/1.first-example.up.sql
    migrations/2.add_password.up.sql
    Continue? [y/N] y
    first-example - up
    add_password - up

By default you will be prompted to confirm the application of any migrations (up
or down).  To bypass this confirmation, you can supply the -s format:

    $ migrate up -s
    SELECTED VERSION: 2
    first-example - up
    add_password - up

If you want to migrate up to a specific version, specify the version:

    $ migrate up -s 1
    USING SPECIFIED VERSION: 1
    first-example - up

### migrate down

This command migrates the database version from a higher number to a lower
number -- that is, moving backwards in time.

To migrate the database to the original ("empty") version, simply:

    $ migrate down
    SELECTED VERSION: 0
    Migrations that will be brought down:
    migrations/2.add_password.down.sql
    migrations/1.first-example.down.sql
    Continue? [y/N] y
    add_password - down
    first-example - down

As with 'up', the '-s' flag works:

    $ migrate down -s
    SELECTED VERSION: 0
    add_password - down
    first-example - down

If you want to migrate down to a specific version, specify the version:

    $ migrate down -s 1
    USING SPECIFIED VERSION: 1
    add_password - down

### migrate list

This command will list the migrations that have been applie to the database.

    $ migrate list
    Showing 2 installed migration(s).
    1. first-example
    2. add_password

### migrate make

This command will create empty up and down migrations with the next number in the sequence:

    $ migrate make foo
    $ cat migrations/3.foo.up.sql
    BEGIN;

    COMMIT;
    $ cat migrations/3.foo.down.sql
    BEGIN;

    COMMIT;

### migrate wipe

This command will WIPE OUT THE ENTIRE SCHEMA you specify.  So use with caution:

    $ migrate wipe snow
    WARNING! GOING TO WIPE SCHEMA 'snow' in DB: postgresql://snow@localhost
    Ok? [y/N] y
    Database wiped.

### migrate rebase

This command is for dealing with the situation where you are merging a feature
branch and you find that the migration you have added on your branch conflicts
with a migration that has made it into master before you have merged.

For example, you might be working on a feature branch that was forked from
master after migrations 1 & 2 have been applied as above.  In your branch you've
created a new migration called 3.add_table_foo.{up,down}.sql.  In another branch
another developer has created 3.add_table_bar.{up,down}.sql.  Unfortunately
that developer has merged their code first, so when you pull you end up with
both 3.add_table_foo.* and 3.add_table_bar.*.

Leaving your migrations directory looking something like this:

    $ ls -1 migrations
    1.first-example.down.sql
    1.first-example.up.sql
    2.add_password.down.sql
    2.add_password.up.sql
    3.add_table_bar.down.sql
    3.add_table_bar.up.sql
    3.add_table_foo.down.sql
    3.add_table_foo.up.sql

With "3.add_table_foo.up.sql" applied to your database and
"3.add_table_bar.up.sql" NOT applied.

The solution to this is:

    $ migrate rebase add_table_foo
    Rebasing slug 'add_table_foo'.
    Current version: 3
    Current version is already <= max version:  3
    Applying: migrations/3.add_table_foo.down.sql
    Violently removing 3 from migrations table.
    Renaming migrations/3.add_table_foo.up.sql => migrations/4.add_table_foo.up.sql
    Renaming migrations/3.add_table_foo.down.sql => migrations/4.add_table_foo.down.sql
    SELECTED VERSION: 4
    add_table_bar - up
    add_table_foo - up
    Rebase complete.

which will migrate down your conflicting add_table_foo migration, then rename it
to be 1 higher than the current higest migration, then applies all unapplied
migrations which include the original conflicting (and currently missing)
migration and any subsequently added ones from master followed by your new one.

Assuming everything works at this point you can commit and merge your branch to
master before some other jerk commits new and also conflicting migrations :)
