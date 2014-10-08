import glob

from pytest import raises

from migrate import _generate_migration_list
from migrate import _escape_migration

# Just to make the tests easier to read:
UP = False
DOWN = True


class TestMigrations(object):

    def test_target_is_current_up(self):
        for x in 0, 10:
            assert _generate_migration_list(x, x, x, UP) == []

    def test_target_is_max_up(self):
        # This is kinda begging the question, but...
        for x in 1, 10:
            assert _generate_migration_list(0, x, x, UP) == range(1, x + 1)

    def test_target_is_current_down(self):
        for x in 0, 10:
            assert _generate_migration_list(x + 1, x + 1, x, DOWN) == [x + 1]

    def test_target_is_zero_down(self):
        # This is kinda begging the question, but...
        for x in 0, 10:
            assert (_generate_migration_list(x + 1, x + 1, 0, DOWN)
                    == range(x + 1, 0, -1))

    def test_c0_m1_t1_up(self):
        assert _generate_migration_list(0, 1, 1, UP) == [1]

    def test_c0_m2_t1_up(self):
        assert _generate_migration_list(0, 2, 1, UP) == [1]

    def test_c5_m10_t4_up(self):
        with raises(ValueError):
            _generate_migration_list(5, 10, 4, UP)

    def test_c5_m10_t4_down(self):
        assert _generate_migration_list(5, 10, 4, DOWN) == [5]

    def test_c3_m10_t4_up(self):
        assert _generate_migration_list(3, 10, 4, UP) == [4]

    def test_c3_m10_t4_down(self):
        with raises(ValueError):
            _generate_migration_list(3, 10, 4, DOWN)


class TestMigrationsDirectory:
    """This test checks that there isn't more than one migration with the same
       number in the migrations directory.
    """

    def test_migrations_are_unique(self):
        up_migrations = glob.glob("migrations/*.up.sql")
        down_migrations = glob.glob("migrations/*.down.sql")
        len_pre = len("migrations/")
        up_fns = [fn[len_pre:] for fn in up_migrations]
        down_fns = [fn[len_pre:] for fn in down_migrations]
        f = lambda fn: fn.split(".")[0]
        up_numbers = map(f, up_fns)
        down_numbers = map(f, down_fns)
        assert len(up_numbers) == len(frozenset(up_numbers))
        assert len(down_numbers) == len(frozenset(down_numbers))


def test_escape_migration():
    assert _escape_migration("foo % bar") == "foo %% bar"
    assert _escape_migration("foo % bar % baz") == "foo %% bar %% baz"
