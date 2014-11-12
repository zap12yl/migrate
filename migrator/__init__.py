"""
migrate.

Usage:
migrate up [<target>] [--skip-preview] [--db=<url>]
migrate down [<target>] [--skip-preview] [--db=<url>]
migrate apply <files>... [--db=<url>]
migrate make <slug> [--db=<url>]
migrate list [--db=<url>]
migrate status [--db=<url>]
migrate rebase <slug> [--db=<url>]
migrate wipe <schema> [--db=<url>]
migrate install [--db=<url>]
migrate -h | --help
migrate --version

Options:
-h --help          Show this screen.
--version          Show version.

-s --skip-preview  Skip the preview.
--db=<url>         Specify DB url [default: DATABASE_URL].
"""
from docopt import docopt

import argparse
import glob
import os
import re

from functools import partial

from sqlalchemy import create_engine
from sqlalchemy import DDL

NOT_EXIST_MSG = "relation \"public.migrations\" does not exist"

PCT_RE = re.compile(r"%")


def get_db_url(args):
    url = args.get("--db")
    if url == "DATABASE_URL" or not url:
        url = os.environ["DATABASE_URL"]
    return url


def get_engine(args):
    url = get_db_url(args)

    engine = create_engine(url)
    return engine


class NoMigrationsTable(Exception):
    pass


class VersionMismatch(Exception):

    def __init__(self, version, expected_version):
        self.version = version
        self.expected_version = expected_version
        msg = "Expected: %s, Actual: %s" % (expected_version, version)
        super(VersionMismatch, self).__init__(msg)


def _find_by_glob(migration_glob, tt, target, kind):
    paths = glob.glob(migration_glob)
    if len(paths) < 1:
        raise Exception("Could not find a migration for %s %s (%s)." % (
            tt, target, kind))
    if len(paths) > 1:
        raise Exception("Duplicate migration #s: %s" % paths)
    assert len(paths) == 1
    path = paths[0]
    return path


def _find_migration(target, kind):
    migration_glob = "migrations/%d.*.%s.sql" % (target, kind)
    return _find_by_glob(migration_glob, "#", target, kind)


def _find_migration_by_slug(slug, kind):
    migration_glob = "migrations/*.%s.%s.sql" % (slug, kind)
    return _find_by_glob(migration_glob, "slug", slug, kind)


def filename_to_tag(filename):
    left = filename.index(".") + 1
    assert left >= 0
    right = filename.rindex(".")
    right = filename[:right].rindex(".")
    assert right >= 0
    assert right > left
    return filename[left:right]


def read_sqls(filename):
    if not filename.endswith(".up.sql"):
        raise Exception("Expected .up.sql file but got: %s" % filename)
    up_filename = filename
    up_sql = open(os.path.join("migrations", up_filename)).read()
    down_filename = up_filename[:-len(".up.sql")] + ".down.sql"
    down_sql = open(os.path.join("migrations", down_filename)).read()
    return up_sql, down_sql


def _escape_migration(migration):
    return PCT_RE.sub("%%", migration)


def _execute_migration(engine, version, filename, migration, down):
    assert filename.startswith(str(version) + ".")

    with engine.begin() as conn:
        try:
            rs = conn.execute("""SELECT MAX(version) AS cur_ver
                                 FROM public.migrations
                              """)
        except somesqlalchemy.Error as ex:
            if NOT_EXIST_MSG in str(ex):
                raise NoMigrationsTable
            else:
                raise
        res = list(rs)[0]
        if res.cur_ver is None:
            cur_ver = 0
        else:
            cur_ver = res.cur_ver

        if down:
            expected_version = cur_ver
        else:
            expected_version = cur_ver + 1

        if version != expected_version:
            raise VersionMismatch(version, expected_version)

        tag = filename_to_tag(filename)

        escaped_migration = _escape_migration(migration)

        conn.execute(DDL(escaped_migration))
        if down:
            conn.execute("""DELETE FROM public.migrations
                            WHERE version = %s
                         """,
                         version)
        else:
            up_sql, down_sql = read_sqls(filename)
            conn.execute("""INSERT INTO public.migrations
                                (version, tag, up_sql, down_sql)
                            VALUES (%s, %s, %s, %s)
                         """,
                         version,
                         tag,
                         up_sql,
                         down_sql)

        print "%s - %s" % (tag, kind(down))


def get_max_target():
    migration_files = glob.glob("migrations/*.*.sql")
    versions = [int(fn.split("/")[-1].split(".")[0]) for fn in migration_files]
    if not len(versions):
        print ("WARNING: No migration files found. Perhaps you are running"
               " migrate in the wrong directory?")
        print "migration_files", migration_files
        print "versions", versions
        return 0
    return max(versions)


def get_current_version(engine):
    with engine.begin() as conn:
        rs = conn.execute("""SELECT MAX(version) AS version
                             FROM public.migrations
                          """)
        row = list(rs)[0]
        return row.version or 0


def _run_migration(engine, version, down):
    path = _find_migration(version, kind(down))
    migration = open(path).read()
    filename = os.path.basename(path)
    return _execute_migration(engine, version, filename, migration, down)


def _generate_migration_list(current_version, max_version, target_version,
                             down):
    if down and 0 <= target_version < current_version:
        return range(current_version, target_version, -1)
    elif not down and current_version <= target_version <= max_version:
        return range(current_version + 1, target_version + 1)
    else:
        raise ValueError("Invalid target version (%s)"
                         " (cur=%s, max=%s, down=%s)" % (target_version,
                                                         current_version,
                                                         max_version,
                                                         down))


def _get_migration_list(engine, target_version, down=False):
    max_version = get_max_target()

    if target_version:
        print "USING SPECIFIED VERSION:", target_version
    else:
        if down:
            target_version = 0
        else:
            target_version = max_version
        print "SELECTED VERSION:", target_version

    current_version = get_current_version(engine)

    if down:
        prev_version = current_version - 1
        target_ok = 0 <= target_version <= current_version
    else:
        next_version = current_version + 1
        target_ok = next_version <= target_version <= max_version

    if not target_ok:
        direction = "down" if down else "up"
        print ("Invalid selection: Current version is %d, max"
               " version is %d.  Requested %s to %d.""" % (current_version,
                                                           max_version,
                                                           direction,
                                                           target_version))

    migration_list = _generate_migration_list(current_version,
                                              max_version,
                                              target_version,
                                              down)
    return migration_list


def _perform_migrations(engine, migration_list, down):
    for version in migration_list:
        _run_migration(engine, version, down)


def kind(down):
    return "down" if down else "up"


def preview(migration_list, down):
    direction = kind(down)
    print "Migrations that will be brought %s:" % direction
    for migration in migration_list:
        filename = _find_migration(migration, direction)
        print filename
    answer = raw_input("Continue? [y/N] ")
    return answer and answer.lower().strip() in ("y", "yes")


def _command_migrate(engine, target_version, down, do_preview):
    target_version = int(target_version) if target_version else 0
    migration_list = _get_migration_list(engine, target_version, down)
    if do_preview:
        if not preview(migration_list, down):
            print "Action canceled."
            return
    _perform_migrations(engine, migration_list, down)


def command_up(args):
    try:
        target_version = args["<target>"]
    except KeyError:
        import ipdb; ipdb.set_trace()
    skip_preview = args.get("--skip-preview")
    engine = get_engine(args)
    _command_migrate(engine, target_version, False, not skip_preview)


def command_down(args):
    target_version = args["<target>"]
    skip_preview = args.get("--skip-preview")
    engine = get_engine(args)
    _command_migrate(engine, target_version, True, not skip_preview)


def command_install(args):
    engine = get_engine(args)
    with engine.begin() as conn:
        conn.execute("""CREATE TABLE public.migrations (
                            version INTEGER,
                            PRIMARY KEY (version),
                            tag TEXT
                                NOT NULL,
                            up_sql TEXT
                                NOT NULL,
                            down_sql TEXT
                                NOT NULL
                        )
                     """)


def command_list(args):
    engine = get_engine(args)
    with engine.begin() as conn:
        sql = "SELECT * FROM public.migrations"
        versions = list(conn.execute(sql))
    if versions:
        print "Showing %d installed migration(s)." % len(versions)
        for version in versions:
            print "%d. %s" % (version.version, version.tag)
    else:
        print "No migrations installed."


def command_wipe(args):
    schema = args["<schema>"]
    DB_URL = get_db_url(args)
    print "WARNING! GOING TO WIPE SCHEMA '%s' in DB: %s" % (schema, DB_URL)
    if "y" == (raw_input("Ok? [y/N] ") or "").strip().lower():
        engine = get_engine(args)
        with engine.begin() as conn:
            sql = "DROP SCHEMA IF EXISTS %s CASCADE" % schema
            conn.execute(sql)
            sql = "DELETE FROM public.migrations"
            conn.execute(sql)
        print "Database wiped."
    else:
        print "No action taken."


def command_status(args):
    engine = get_engine(args)
    try:
        with engine.begin() as conn:
            sql = "SELECT * FROM public.migrations ORDER BY version"
            versions = list(conn.execute(sql))
    except Exception as ex:
        print "There was a problem:"
        print ex
        print "Maybe the database versions table is not installed?"
        print "(If thats the problem, try 'migrate install')."
    else:
        print ("Database versions table installed."
               " %d migrations installed." % len(versions))
        for v in versions:
            print "%d. %s" % (v.version, v.tag)


def command_apply(args):
    fns = args["<files>..."]
    for fn in fns:
        if not os.path.exists(fn):
            raise Exception("Specified file does not exist: %s" % fn)
    engine = get_engine(args)
    with engine.begin() as conn:
        for fn in fns:
            print "Applying: %s" % fn
            sql = open(fn).read()
            conn.execute(sql)


def next_N():
    idx = 0
    files = glob.glob("migrations/*.*.sql")
    fns = [fn[len("migrations/"):] for fn in files]
    for f in fns:
        m = re.match(r"^(\d+)\..+", f)
        if m:
            n = m.groups()[0]
            n = int(n)
            idx = max(idx, n)
    idx += 1
    return idx


def validate_slug(slug):
    return re.match("[a-zA-Z0-9-]", slug)


def command_make(args):
    slug = args["<slug>"]
    if not validate_slug(slug):
        print "Invalid slug, '%s', must be in-this-format." % slug
        return
    n = next_N()
    up_fn = "migrations/%d.%s.up.sql" % (n, slug)
    down_fn = "migrations/%d.%s.down.sql" % (n, slug)
    sql = "BEGIN;\n\nCOMMIT;\n"
    with open(up_fn, "w") as f:
        f.write(sql)
    with open(down_fn, "w") as f:
        f.write(sql)


def _ensure_db_no_higher_than(engine, version):
    current_version = get_current_version(engine)
    print "Current version: %d" % current_version

    if current_version <= version:
        print "Current version is already <= max version: ", version
    else:
        print "Rolling migrations back to version: ", version

        command_down({
            "<target>": version,
            "--skip_preview": True,
            "--db": args["--db"]
        })


def _delete_dbv(engine, version):
    print "Violently removing %s from migrations table." % version
    with engine.begin() as conn:
        conn.execute("""DELETE FROM public.migrations
                        WHERE version = %s""",
                     version)


def get_highest_migration_num():
    any_migration_glob = "migrations/*.*.*.sql"
    paths = glob.glob(any_migration_glob)
    nums = [int(path.split("/")[1].split(".")[0])
            for path in paths]
    return max(nums)


def _rename_file(old_path, new_fn):
    old_dir = os.path.join(*old_path.split("/")[:-1])
    new_path = os.path.join(old_dir, new_fn)
    print "Renaming %s => %s" % (old_path, new_path)
    os.rename(old_path, new_path)


def rename_slug_to_version(up_fn, down_fn, slug, version):
    new_up_fn = "%d.%s.up.sql" % (version, slug)
    new_down_fn = "%d.%s.down.sql" % (version, slug)

    _rename_file(up_fn, new_up_fn)
    _rename_file(down_fn, new_down_fn)


class MockArgs(object):

    def __init__(self, args, kwargs):
        self._args = args
        self._kwargs = kwargs

    @property
    def files(self):
        return self._kwargs.get("files", [])

    @property
    def skip_preview(self):
        return self._kwargs.get("skip_preview", False)

    @property
    def target(self):
        return self._kwargs.get("target", None)


def command_rebase(args):
    slug = args["<slug>"]
    print "Rebasing slug '%s'." % slug

    up_fn, down_fn = [_find_migration_by_slug(slug, "up"),
                      _find_migration_by_slug(slug, "down")]

    dupe_version = int(up_fn.split("/")[1].split(".")[0])

    engine = get_engine(args)

    # Before we roll back the duplicated one, we need to
    # rollback any subsequent migrations that may have been
    # applied since the duplicate.  If there are any, this
    # will roll them back so that we are at the point where
    # the reality is that we should be using the new dupe
    # but we have our old dupe in the db.
    _ensure_db_no_higher_than(engine, dupe_version)

    # Now we manually bring down the live duplicate
    command_apply({
        "<files>...": [down_fn],
        "--db": args["--db"]
    })

    # then manually delete that version (eg. 53) from the migrations table
    _delete_dbv(engine, dupe_version)

    # now it's like that last one never happened, so we
    # rename to 1 above the new highest
    # e.g. migrations/58.payouts.{up,down}.sql

    highest = get_highest_migration_num()
    rename_slug_to_version(up_fn, down_fn, slug, highest + 1)

    command_up({
        "<target>": None,
        "--skip-preview": True,
        "--db": args["--db"]
    })

    print "Rebase complete."


def main():
    args = docopt(__doc__, version='migrate 0.0.5')

    if args.get("up"):
        command_up(args)
    elif args.get("down"):
        command_down(args)
    elif args.get("apply"):
        command_apply(args)
    elif args.get("make"):
        command_make(args)
    elif args.get("list"):
        command_list(args)
    elif args.get("status"):
        command_status(args)
    elif args.get("rebase"):
        command_rebase(args)
    elif args.get("wipe"):
        command_wipe(args)
    elif args.get("install"):
        command_install(args)


if __name__ == "__main__":
    main()
