BEGIN;

ALTER TABLE users
      DROP COLUMN password;

COMMIT;
