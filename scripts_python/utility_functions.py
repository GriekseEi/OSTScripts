"""
A module of general utility functions that can be reused in other scripts.
"""
import logging
import multiprocessing
import os
import platform
import signal
import subprocess
import time
from glob import glob
from typing import Iterable, Optional, Sequence


def track_elapsed_time(ndigits: Optional[int] = 4):
    """Decorator that tracks the execution time of the given function and prints it to
    stdout.

    :param ndigits: How many digits the elapsed time should be rounded to.
    Defaults to 4. If None, then the elapsed time will be rounded down to an integer.
    """

    def inner(func):
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            res = func(*args, **kwargs)
            end_time = time.perf_counter()

            logging.info(
                f"Finished operation in {round((end_time - start_time), ndigits)}s!"
            )
            return res

        return wrapper

    return inner


def is_app_installed(cmd: Sequence[str]) -> bool:
    """Checks if a given app is installed on the current system by executing a given
    shell command and seeing if it returns an error or not.

    :param cmd: The command to execute for checking an app's presence. It should be
                structured as a list of string arguments.
    :return: True if the app is executable from shell, False otherwise.
    """
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as ex:
        logging.error(ex)
        return False


def prompt_yes_no(message: str, yes_default: bool, *, max_iterations: int = 5) -> bool:
    """Prompts the user with a message to input either 'y'/'ye'/'yes' or 'n'/'no' in
    order to continue. If another input is given, the prompt will be repeated until
    the user enters a valid response. Inputs are automatically converted to lowercase.

    :param message: The prompt to print to the console.
    :param yes_default: If inputting an empty character with ENTER should be treated as
    a 'yes' if True, and 'no' if False.
    :param total_iterations: How often we will loop the prompt on invalid answers until
    we automatically escape it.
    :return: True if the user entered 'yes', and False if 'no' was entered or if too
    many invalid answers were given.
    """
    while max_iterations > 0:
        max_iterations -= 1
        logging.warning(message)
        valid = {
            "yes": True,
            "y": True,
            "ye": True,
            "no": False,
            "n": False,
            "": yes_default,
        }
        choice = input().lower()

        if choice in valid and valid[choice]:
            return True
        if choice in valid and not valid[choice]:
            return False
    logging.error("Too many invalid responses were given, shutting down program...")
    return False


def run_multiprocessed(func, commands: Iterable) -> list:
    """Executes a given function in multiple processes using an Iterable of commands.
    The amount of processes working in parallel will be (amount of cores in your CPU
    - 1). It's not recommended to call this function if your CPU has one or two cores,
    or if the total amount of commands is too low. Otherwise the performance overhead
    incurred by managing a multiprocessing pool outweighs its potential benefits.

    :Passing multiple arguments:

    Multiple arguments per command can be passed to the target function by wrapping
    them in tuples, like so:

    def func(a, b):
        return a + b

    res = run_multiprocessed(func, [(1, 2), (3, 4), (5, 6)])
    >>> res = [3, 7, 11]

    :param func: The function to execute.
    :param commands: The commands to pass to the given function
    :raises TimeoutError: If the processes took too long to execute (currently the
    limit is set to 4096 seconds.)
    :return: A list of results from the target function
    """
    pool_size = multiprocessing.cpu_count() - 1
    if pool_size < 2:
        raise RuntimeError("Need more than 2 CPU cores for parallel processing")

    # Ignore SIGINT in the main process, so that the child processes created by
    # instantiating the pool will inherit the SIGINT handler
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    with multiprocessing.Pool(pool_size) as pool:
        # Restore the original SIGINT handler in the main process so that we can
        # actually catch KeyboardInterrupts from here
        # TODO: Have KeyboardInterrupts work on Windows as well
        signal.signal(signal.SIGINT, original_sigint_handler)

        try:
            result = pool.starmap_async(func, commands)
            # Wait on the result with a timeout because otherwise the wait would
            # ignore all signals, including KeyboardInterrupt. This is set to
            # something unreasonably high to prevent most timeouts
            result = result.get(0xFFF)
            pool.close()
            return result
        except (TimeoutError, KeyboardInterrupt) as err:
            pool.terminate()
            raise err
        finally:
            pool.join()


def create_missing_folder(path: str):
    """Creates the output folders for when the given output path does not exist.

    :param path: The name of the folders to create.
    :raises SystemExit: If the user decides not to create a new folder.
    """
    msg = (
        f"Could not find output folder '{os.path.join(os.getcwd(), path)}'.\n"
        f"Do you want to create this folder? [Y/n]"
    )

    if prompt_yes_no(msg, True):
        os.makedirs(path)
        logging.info("Created new folder at given path.")
    else:
        raise SystemExit("User refused to create output directory. Aborting...")


def glob_files(
    path: str,
    valid_formats: tuple[str, ...],
    recursive: bool = False,
) -> list[str]:
    """Returns a list of all filenames in the given directory that support the given
    formats if the given path is a directory, or returns a list of only one path if
    the given path points to a single file. The paths in the list are sorted
    alphabetically.

    :param path: The path to the target file or directory.
    :param valid_formats: The formats of the files we want to glob.
    :param recursive: Whether, defaults to False

    :raises FileNotFoundError: If there are no files/folders at the given path with the
    given extensions.
    """
    has_multiple = False
    
    if platform.system() == "Linux":
        # Filenames in Linux are case-sensitive, but not on Windows
        path = get_casecorrect_path(path)
    
    if os.path.isdir(path):
        has_multiple = True
    elif not os.path.isfile(path):
        raise FileNotFoundError(f"Couldn't find image/folder at {path}")

    files = []
    if has_multiple:
        for ext in valid_formats:
            path_to_glob = os.path.join(path, "*" + ext)
            if recursive:
                path_to_glob = os.path.join(path, "**", "*" + ext)

            files.extend(glob(path_to_glob, recursive=recursive))

        if len(files) < 1:
            raise FileNotFoundError(
                "Couldn't find files of supported type in the ",
                f"given folder. Supported types: {valid_formats}",
            )
        files = sorted(files)
    else:
        files.append(path)

    return files

def get_casecorrect_path(path: str) -> str:
    """Takes a path, checks with the filesystem if it has the correct
    capitalization, then returns the corrected path
    
    :param path: The path to verify the capitalization of
    """
    directory, filename = os.path.split(path)
    directory, filename = (directory or '.'), filename.lower()
    for f in os.listdir(directory):
        newpath = os.path.join(directory, f)
        if os.path.isfile(newpath) and f.lower() == filename:
            return newpath
        elif os.path.isdir(newpath) and f.lower() == filename:
            return newpath