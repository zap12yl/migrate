# Change Log

# 0.0.8 - Add "plant" command

- Added "plant" command to insert a row for one or more migrations without
  applying the migration(s).  Useful e.g. in the case where a long running
  migration successfully completes but then migrator loses it's connection to
  the database before being able to update the migrations table.  Use with
  caution.

- Fixed bugs

# 0.0.2 - Bug Fixes

- Fixed missing schema prefix on two queries.

# 0.0.1 - Initial Release
