"""
migrate.

Usage:
migrate up [<target>] [--skip-preview] [--db=<url>]
migrate down [<target>] [--skip-preview] [--db=<url>]
migrate apply <files>... [--db=<url>]
migrate make <slug> [--db=<url>]
migrate list [--db=<url>]
migrate plant <migrations>...
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
import glob
import os
import re
from sqlalchemy import create_engine, DDL
from sqlalchemy.exc import SQLAlchemyError

NOT_EXIST_MSG = "relation \"public.migrations\" does not exist"
PCT_RE = re.compile(r"%")

def get_db_url(args):
    url = args.get("--db")
    if url == "DATABASE_URL" or not url:
        url = os.environ["DATABASE_URL"]
    return url

def get_engine(args):
    url = get_db_url(args)
    return create_engine(url)

class NoMigrationsTable(Exception):
    pass

class VersionMismatch(Exception):
    def __init__(self, version, expected_version):
        self.version = version
        self.expected_version = expected_version
        msg = f"Expected: {expected_version}, Actual: {version}"
        super().__init__(msg)

def _find_by_glob(migration_glob, tt, target, kind):
    paths = glob.glob(migration_glob)
    if len(paths) < 1:
        raise Exception(f"Could not find a migration for {tt} {target} ({kind}).")
    if len(paths) > 1:
        raise Exception(f"Duplicate migration #s: {paths}")
    return paths[0]

def _find_migration(target, kind):
    return _find_by_glob(f"migrations/{target}.*.{kind}.sql", "#", target, kind)

def filename_to_tag(filename):
    left = filename.index(".") + 1
    right = filename[:filename.rindex(".")].rindex(".")
    return filename[left:right]

def read_sqls(filename):
    if not filename.endswith(".up.sql"):
        raise Exception(f"Expected .up.sql file but got: {filename}")
    up_sql = open(os.path.join("migrations", filename)).read()
    down_filename = filename[:-7] + ".down.sql"
    down_sql = open(os.path.join("migrations", down_filename)).read()
    return up_sql, down_sql

def _escape_migration(migration):
    return PCT_RE.sub("%%", migration)

def _execute_migration(engine, version, filename, migration, down):
    with engine.begin() as conn:
        try:
            rs = conn.execute("SELECT MAX(version) AS cur_ver FROM public.migrations")
        except SQLAlchemyError as ex:
            if NOT_EXIST_MSG in str(ex):
                raise NoMigrationsTable
            else:
                raise
        res = list(rs)[0]
        cur_ver = res.cur_ver if res.cur_ver is not None else 0
        expected_version = cur_ver - 1 if down else cur_ver + 1
        if version != expected_version:
            raise VersionMismatch(version, expected_version)
        tag = filename_to_tag(filename)
        escaped_migration = _escape_migration(migration)
        conn.execute(DDL(escaped_migration))
        if down:
            conn.execute("DELETE FROM public.migrations WHERE version = %s", (version,))
        else:
            up_sql, down_sql = read_sqls(filename)
            conn.execute("""INSERT INTO public.migrations (version, tag, up_sql, down_sql)
                            VALUES (%s, %s, %s, %s)""", (version, tag, up_sql, down_sql))
        print(f"{tag} - {'down' if down else 'up'}")

def get_current_version(engine):
    with engine.begin() as conn:
        rs = conn.execute("SELECT MAX(version) AS version FROM public.migrations")
        row = list(rs)[0]
        return row.version or 0

def preview(migration_list, down):
    direction = "down" if down else "up"
    print(f"Migrations that will be brought {direction}:")
    for migration in migration_list:
        filename = _find_migration(migration, direction)
        print(filename)
    answer = input("Continue? [y/N] ").strip().lower()
    return answer in ("y", "yes")

def command_up(args):
    target_version = args["<target>"]
    skip_preview = args.get("--skip-preview")
    engine = get_engine(args)
    _command_migrate(engine, target_version, False, not skip_preview)

def command_down(args):
    target_version = args["<target>"]
    skip_preview = args.get("--skip-preview")
    engine = get_engine(args)
    _command_migrate(engine, target_version, True, not skip_preview)

def command_list(args):
    engine = get_engine(args)
    with engine.begin() as conn:
        sql = "SELECT * FROM public.migrations ORDER BY version ASC"
        versions = list(conn.execute(sql))
    if versions:
        print(f"Showing {len(versions)} installed migration(s).")
        for version in versions:
            print(f"{version.version}. {version.tag}")
    else:
        print("No migrations installed.")

def command_status(args):
    engine = get_engine(args)
    try:
        with engine.begin() as conn:
            sql = "SELECT * FROM public.migrations ORDER BY version"
            versions = list(conn.execute(sql))
    except Exception as ex:
        print("There was a problem:")
        print(ex)
        print("Maybe the database versions table is not installed?")
        print("(If that's the problem, try 'migrate install').")
    else:
        print(f"Database versions table installed. {len(versions)} migrations installed.")
        for v in versions:
            print(f"{v.version}. {v.tag}")

def main():
    args = docopt(__doc__, version='migrate 0.0.5')
    if args.get("up"):
        command_up(args)
    elif args.get("down"):
        command_down(args)
    elif args.get("list"):
        command_list(args)
    elif args.get("status"):
        command_status(args)

if __name__ == "__main__":
    main()