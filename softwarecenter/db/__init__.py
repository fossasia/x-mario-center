import logging

try:
    from debfile import DebFileApplication, DebFileOpenError
    DebFileApplication  # pyflakes
    DebFileOpenError  # pyflakes
except:
    logging.exception("DebFileApplication import")

    class DebFileApplication(object):
        pass

    class DebFileOpenError(Exception):
        pass
