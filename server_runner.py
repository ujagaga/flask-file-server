#!/usr/bin/env python3

import time
import os
import datetime

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))

while True:
    print("*** Starting the file server at {}\n".format(datetime.datetime.now().strftime("%d.%B.%Y, %H:%M:%S")))
    os.system('{}'.format(os.path.join(SCRIPT_PATH, "Ohana_fileServer.py")))
    print("\n*** File server stopped at {}\n".format(datetime.datetime.now().strftime("%d.%B.%Y, %H:%M:%S")))
    time.sleep(5)