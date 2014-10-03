# migrate

Migrate is a database migration assistant.

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
    $ cat migrations/3.foo.up.sql                                                                                                                                                                                                     ✹ ✭
    BEGIN;

    COMMIT;
    cat migrations/3.foo.up.sql  0.00s user 0.00s system 82% cpu 0.003 total
    (migrate)[john@maia:~/src/migrate on master]
    % cat migrations/3.foo.down.sql                                                                                                                                                                                                   ✹ ✭
    BEGIN;

    COMMIT;


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
