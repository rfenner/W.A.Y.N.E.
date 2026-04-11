import os
import traceback

try:
    import pydevd_pycharm

    try:
        port = 9000
        if "PYDEVD_PORT" in os.environ:
            port = int(os.environ["PYDEVD_PORT"])
        pydevd_pycharm.settrace('host.docker.internal', port=port, stdout_to_server=True, stderr_to_server=True, suspend=False)
    except Exception as e:
 #       traceback.print_exception(e)
        print("Couldn't connect to the pydevd_pycharm server")
except ImportError:
    print("Pycharm debugger not found skipping")

