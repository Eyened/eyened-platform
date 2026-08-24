import os


def pytest_configure(config):
    # Note: due to the way application configuration is created and imported throughout the application,
    # there is no clean way to test code that imports (database) settings, which is virtually everything.
    # Below is a rather ugly hack to work around this, that will probably result in new issues when we
    # want to add database-backend tests for the server. The correct solution is to handle settings
    # loading differently in the application.

    # Add mock values for required configuration values
    os.environ.setdefault("EYENED_DATABASE_USER", "test_user")
    os.environ.setdefault("EYENED_DATABASE_PASSWORD", "test_password")
