import argparse
import glob
import os
import re

from functools import partial

from sqlalchemy import create_engine
from sqlalchemy import DDL

NOT_EXIST_MSG = "relation \"public.database_versions\" does not exist"

# # TODO: compartementalize
# DB_URL = os.environ["DATABASE_URL"]
# engine = create_engine(DB_URL)


class NoDatabaseVersionsTable(Exception):
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


def _execute_migration(version, filename, migration, down):
    assert filename.startswith(str(version) + ".")

    with engine.begin() as conn:
        try:
            rs = conn.execute("""SELECT MAX(version) AS cur_ver
                                 FROM public.database_versions
                              """)
        except somesqlalchemy.Error as ex:
            if NOT_EXIST_MSG in str(ex):
                raise NoDatabaseVersionsTable
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

        conn.execute(DDL(migration))
        if down:
            conn.execute("""DELETE FROM public.database_versions
                            WHERE version = %s
                         """,
                         version)
        else:
            up_sql, down_sql = read_sqls(filename)
            conn.execute("""INSERT INTO public.database_versions
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


def get_current_version():
    with engine.begin() as conn:
        rs = conn.execute("""SELECT MAX(version) AS version
                             FROM database_versions
                          """)
        row = list(rs)[0]
        return row.version or 0


def _run_migration(version, down):
    path = _find_migration(version, kind(down))
    migration = open(path).read()
    filename = os.path.basename(path)
    return _execute_migration(version, filename, migration, down)


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


def _get_migration_list(target_version, down=False):
    max_version = get_max_target()

    if target_version:
        print "USING SPECIFIED VERSION:", target_version
    else:
        if down:
            target_version = 0
        else:
            target_version = max_version
        print "SELECTED VERSION:", target_version

    current_version = get_current_version()

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


def _perform_migrations(migration_list, down):
    for version in migration_list:
        _run_migration(version, down)


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


def _command_migrate(target_version, down, do_preview):
    migration_list = _get_migration_list(target_version, down)
    if do_preview:
        if not preview(migration_list, down):
            print "Action canceled."
            return
    _perform_migrations(migration_list, down)


def command_up(args):
    target_version = args.target
    _command_migrate(target_version, False, not args.skip_preview)


def command_down(args):
    target_version = args.target
    _command_migrate(target_version, True, not args.skip_preview)


def command_install(args):
    with engine.begin() as conn:
        conn.execute("""CREATE TABLE public.database_versions (
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
    with engine.begin() as conn:
        sql = "SELECT * FROM public.database_versions"
        versions = list(conn.execute(sql))
    if versions:
        print "Showing %d installed migration(s)." % len(versions)
        for version in versions:
            print "%d. %s" % (version.version, version.tag)
    else:
        print "No migrations installed."


def command_wipe(args):
    schema = args.schema
    print "WARNING! GOING TO WIPE SCHEMA '%s' in DB: %s" % (schema, DB_URL)
    if "y" == (raw_input("Ok? [y/N] ") or "").strip().lower():
        with engine.begin() as conn:
            conn.execute("DROP SCHEMA IF EXISTS %s CASCADE", schema)
        print "Database wiped."
    else:
        print "No action taken."


def command_status(args):
    try:
        with engine.begin() as conn:
            sql = "SELECT * FROM database_versions ORDER BY version"
            versions = list(conn.execute(sql))
    except Exception:
        print "Database versions table not installed."
    else:
        print ("Database versions table installed."
               " %d migrations installed." % len(versions))
        for v in versions:
            print "%d. %s" % (v.version, v.tag)


def command_apply(args):
    fns = args.files
    for fn in fns:
        if not os.path.exists(fn):
            raise Exception("Specified file does not exist: %s" % fn)
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
    slug = args.slug
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


def _ensure_db_no_higher_than(version):
    current_version = get_current_version()
    print "Current version: %d" % current_version

    if current_version <= version:
        print "Current version is already <= max version: ", version
    else:
        print "Rolling migrations back to version: ", version

        invoke_command(command_down, target=version, skip_preview=True)


def _delete_dbv(version):
    print "Violently removing %s from database_versions table." % version
    with engine.begin() as conn:
        conn.execute("""DELETE FROM database_versions
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


def invoke_command(cmd, *args, **kwargs):
    args = MockArgs(args, kwargs)
    return cmd(args)


def command_rebase(args):
    slug = args.slug
    print "Rebasing slug '%s'." % slug

    up_fn, down_fn = [_find_migration_by_slug(slug, "up"),
                      _find_migration_by_slug(slug, "down")]

    dupe_version = int(up_fn.split("/")[1].split(".")[0])

    # Before we roll back the duplicated one, we need to
    # rollback any subsequent migrations that may have been
    # applied since the duplicate.  If there are any, this
    # will roll them back so that we are at the point where
    # the reality is that we should be using the new dupe
    # but we have our old dupe in the db.
    _ensure_db_no_higher_than(dupe_version)

    # Now we manually bring down the live duplicate
    invoke_command(command_apply, files=[down_fn])

    # then manually delete that version (eg. 53) from database_versions
    _delete_dbv(dupe_version)

    # now it's like that last one never happened, so we
    # rename to 1 above the new highest
    # e.g. migrations/58.payouts.{up,down}.sql

    highest = get_highest_migration_num()
    rename_slug_to_version(up_fn, down_fn, slug, highest + 1)

    invoke_command(command_up, skip_preview=True)

    print "Rebase complete."


def main():
    # TODO: docopt

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="sub-command help")

    parser_up = subparsers.add_parser("up", help="migrate up")
    parser_up.add_argument("target", type=int, nargs="?")
    parser_up.add_argument("-s", "--skip-preview", action="store_true")
    parser_up.set_defaults(func=command_up)

    parser_down = subparsers.add_parser("down", help="migrate down")
    parser_down.add_argument("target", type=int, nargs="?")
    parser_down.add_argument("-s", "--skip-preview", action="store_true")
    parser_down.set_defaults(func=command_down)

    parser_status = subparsers.add_parser("status",
                                          help="show current status")
    parser_status.set_defaults(func=command_status)

    parser_install = subparsers.add_parser(
        "install", help="install the database_versions table")
    parser_install.set_defaults(func=command_install)

    parser_list = subparsers.add_parser(
        "list", help="list installed migrations")
    parser_list.set_defaults(func=command_list)

    parser_wipe = subparsers.add_parser("wipe", help="wipe a schema")
    parser_wipe.add_argument("schema")
    parser_wipe.set_defaults(func=command_wipe)

    parser_run = subparsers.add_parser("apply",
                                       help="apply specific SQL file(s).")
    parser_run.add_argument("files", nargs="+")
    parser_run.set_defaults(func=command_apply)

    parser_run = subparsers.add_parser(
        "make", help="make a set of new empty migrations")
    parser_run.add_argument("slug")
    parser_run.set_defaults(func=command_make)

    parser_run = subparsers.add_parser(
        "rebase", help="rebase a duplicate migration to the end.")
    parser_run.add_argument("slug")
    parser_run.set_defaults(func=command_rebase)

    args = parser.parse_args()
    args.func(args)

"""
Naval Fate.

Usage:
naval_fate ship new <name>...
naval_fate ship <name> move <x> <y> [--speed=<kn>]
naval_fate ship shoot <x> <y>
naval_fate mine (set|remove) <x> <y> [--moored|--drifting]
naval_fate -h | --help
naval_fate --version

Options:
-h --help     Show this screen.
--version     Show version.
--speed=<kn>  Speed in knots [default: 10].
--moored      Moored (anchored) mine.
--drifting    Drifting mine.
"""
from docopt import docopt

def main():
    args = docopt(__doc__, version='Naval Fate 2.0')

    
    if __name__ == "__main__":
        main()
