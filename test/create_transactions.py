#!/usr/bin/python

from gi.repository import GObject

import time

from aptdaemon.client import AptClient
from aptdaemon.gtkwidgets import AptProgressDialog

# run with terminal and progress
WITH_GUI=True

MAX_ACTIVE=1
active = 0

def exit_handler(trans, enum):
    global active
    active -= 1
    return True

def run(t):
    if WITH_GUI:
        dia = AptProgressDialog(t)
        dia.run()
        dia.destroy()
    else:
        t.run()

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)

    context = GObject.main_context_default()
    c = AptClient()
    for i in range(100):
        
        print "inst: 3dchess"
        t = c.install_packages(["3dchess"], exit_handler=exit_handler)
        run(t)
        active += 1

        print "inst: 2vcard"
        t = c.install_packages(["2vcard"], exit_handler=exit_handler)
        run(t)
        active += 1
        
        print "rm: 3dchess 2vcard"
        t = c.remove_packages(["3dchess","2vcard"], exit_handler=exit_handler)
        run(t)

        while active > MAX_ACTIVE:
            while context.pending():
                context.iteration()
            time.sleep(1)
