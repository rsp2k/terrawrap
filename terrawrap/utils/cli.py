"""Module for containing CLI convenience functions"""
from __future__ import print_function

import getpass
import logging
import subprocess
import tempfile

from typing import List, Tuple, Union

import requests

from amplify_aws_utils.resource_helper import Jitter

from terrawrap.utils.git_utils import get_git_root

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRIABLE_ERRORS = [
    'RequestError: send request failed',
    'unexpected EOF',
    'Throttling',
    'timeout while waiting for state',
    'ServiceUnavailable: Service Unavailable',
    'failed to decode query XML error response',
    'connection reset',
    'Connection reset',
    'Please try again.',
    'Client.Timeout exceeded',
    'Request limit for operation',
    'try again later',
    'handshake timeout',
    'SSL_ERROR_SYSCALL',
    'ConditionalCheckFailedException',
    'Api Rate Limit Exceeded',
    'TooManyUpdates',
]


def execute_command(
        args: Union[List[str], str],
        *pargs,
        print_output: bool = True,
        capture_stderr: bool = True,
        print_command: bool = False,
        retry: bool = False,
        timeout: int = 15 * 60,
        audit_api_url: str = None,
        **kwargs
) -> Tuple[int, List[str]]:
    """
    Convenience function for executing a given command and optionally printing the output.
    :param args: List of arguments to execute, or a single string.
    :param pargs: Any additional positional arguments to Popen.
    :param print_output: True if the output of the command should be printed immediately. Defaults to True.
    :param capture_stderr: True if stderr should be captured. Defaults to True.
    :param print_command: True if the command should be printed before executing. Defaults to False.
    :param timeout: Max amount of time to keep retrying to execute command. Defaults to 15 minutes.
    :param retry: Retry a number of times if network errors. Defaults to False.
    :param audit_api_url: Audit API URL to submit POST request. Defaults to None so no data is sent.
    :param kwargs: Any additional keyword arguments to Popen.
    :return: A tuple of the exit code and output of the command.
    """
    try_count = 0

    # It's possible for an envvar to be set to none, so exclude those envvars.
    if 'env' in kwargs:
        kwargs['env'] = {
            key: value
            for key, value in kwargs['env'].items()
            if value is not None
        }

    jitter = Jitter()
    time_passed = 0
    exit_code = 0
    stdout: List[str] = []
    while try_count < MAX_RETRIES if retry else 1:
        exit_code, stdout = _execute_command(
            args,
            print_output,
            capture_stderr,
            print_command,
            *pargs,
            **kwargs,
        )

        try_count += 1

        network_errors = _get_retriable_errors(stdout)
        if exit_code != 0 and network_errors and retry:
            logger.warning('Found network errors while running %s command: %s', args, network_errors)
        else:
            # The command either succeeded or failed with a non network error. don't retry
            break

        if time_passed >= timeout:
            raise TimeoutError(f'Timed out retrying {args} command')

        time_passed = jitter.backoff()

    if audit_api_url and kwargs['cwd']:
        _post_to_audit_api_url(audit_api_url, kwargs['cwd'], exit_code, stdout)

    return exit_code, stdout


def _execute_command(
        args: Union[List[str], str],
        print_output: bool,
        capture_stderr: bool,
        print_command: bool,
        *pargs,
        **kwargs
) -> Tuple[int, List[str]]:
    """
    Private function for executing a given command and optionally printing the output.
    :param args: List of arguments to execute, or a single string.
    :param print_output: True if the output of the command should be printed immediately. Defaults to True.
    :param capture_stderr: True if stderr should be captured. Defaults to True.
    :param print_command: True if the command should be printed before executing. Defaults to False.
    :param pargs: Any additional positional arguments to Popen.
    :param kwargs: Any additional keyword arguments to Popen.
    :return: A tuple of the exit code and output of the command.
    """
    stdout_write, stdout_path = tempfile.mkstemp()
    with open(stdout_path, "rb") as stdout_read, open('/dev/null', 'w', encoding='utf-8') as dev_null:

        if print_command:
            print(f"Executing: {' '.join(args)}")

        kwargs['stdout'] = stdout_write
        kwargs['stderr'] = stdout_write if capture_stderr else dev_null

        # pylint: disable=consider-using-with
        process = subprocess.Popen(
            args,
            *pargs,
            **kwargs
        )

        while True:
            output = stdout_read.read(1).decode(errors="replace")

            if output == '' and process.poll() is not None:
                break

            if print_output and output:
                print(output, end="", flush=True)

        exit_code = process.poll()

        stdout_read.seek(0)
        stdout = [line.decode(errors="replace") for line in stdout_read.readlines()]

        # ignoring mypy error below because it thinks exit_code can sometimes be None
        # we know that will never be the case because the above While loop will keep looping forever
        # until exit_code is not None
        return exit_code, stdout  # type: ignore


def _get_retriable_errors(out: List[str]) -> List[str]:
    """Filter line output for retriable errors"""
    return [
        line for line in out
        if any(error in line for error in RETRIABLE_ERRORS)
    ]


def _post_to_audit_api_url(audit_api_url: str, path: str, exit_code: int, stdout: List[str]):
    root = get_git_root(path)
    path = path.replace(root, '')

    status = 'SUCCESS' if exit_code == 0 else 'FAILED'
    user = getpass.getuser()

    logger.info('Attempting to send data to Audit API: %s run by %s(%s)', path, user, status)

    try:
        requests.post(
            audit_api_url, json={
                'directory': path,
                'status': status,
                'run_by': user,
                'output': stdout
            })
        logger.info('Successfully posted data to provided url: %s', audit_api_url)
    except requests.exceptions.RequestException:
        logger.error("Unable to post data to provided url: %s", audit_api_url)
