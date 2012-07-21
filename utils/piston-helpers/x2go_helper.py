#!/usr/bin/python -u
import fcntl
import gevent
import os
import shlex
import sys
import x2go


def connect(server, port, login, password, session):
    print "PROGRESS: creating"
    cli = x2go.X2goClient(start_pulseaudio=True)
    uuid = cli.register_session(
        server=server,
        port=int(port),
        username=login,
        add_to_known_hosts=True,
        cmd="weblive-session %s" % session,
        geometry="1024x600",
        session_type="desktop"
    )

    print "PROGRESS: connecting"
    try:
        if cli.connect_session(uuid, password=password) not in (None, True):
            # According to documentation, connect_session may return False
            exception("unable to connect")
    except:
        # Any paramiko exception will get here
        exception("unable to connect")

    print "PROGRESS: starting"
    try:
        if cli.start_session(uuid) not in (None, True):
            # According to documentation, start_session may return False
            exception("unable to start")
    except:
        # Just in case
        exception("unable to start")

    print "CONNECTED"
    return (cli,uuid)

def exception(string):
    print "EXCEPTION: %s" % string
    sys.exit(1)

def warning(string):
    print "WARNING: %s" % string

def disconnect(connection, uuid):
    try:
        if connection.terminate_session(uuid) not in (None, True):
            # According to documentation, connect_session may return False
            exception("unable to disconnect")
    except:
        # Any paramiko exception will get here
        exception("unable to disconnect")

    print "DISCONNECTED"
    sys.exit(0)

if __name__ == "__main__":

    # make stdin nonblocking
    fd = sys.stdin.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    # main loop
    connection = None
    uuid = None

    while True:
        # Get anything that appeared on stdin
        try:
            buf = sys.stdin.readline().strip()
        except IOError:
            buf = None

        if buf:
            params = shlex.split(buf)

            # Parse command from stdin
            if params[0] == "CONNECT:":
                if not len(params) == 6:
                    exception("invalid connect string")

                if not uuid and not connection:
                    connection, uuid = connect(*params[1:])
                else:
                    warning("already connected")

            elif params[0] == "DISCONNECT":
                if connection and uuid:
                    disconnect(connection, uuid)
                else:
                    exception("no existing connection")

            else:
                warning("invalid command: '%s'" % params)

        # Check if the session ended
        if connection and uuid and not connection.session_ok(uuid):
            disconnect(connection, uuid)

        if not buf:
            gevent.sleep(0.5)
