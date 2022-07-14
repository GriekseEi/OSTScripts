# pylint:disable=missing-function-docstring,unused-argument
import os
import re
from unittest.mock import MagicMock
import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock.plugin import MockerFixture
import utility_functions as util


UTIL_PATH = "utility_functions"


@pytest.fixture(name="fake_fs", scope="function")
def fixture_fake_filesystem(fs: FakeFilesystem):  # pylint:disable=invalid-name
    fs.create_file("./test/img1.jpg")
    fs.create_file("./test/img2.png")
    fs.create_file("./test/img3.jpg")
    fs.create_file("./test/song1.mp3")
    fs.create_file("./test/song2.wav")
    fs.create_file("./test/song3.mp3")
    fs.create_file("./test/song4.wav")
    fs.create_file("./test/song5.mp3")
    fs.create_file("./test/song6.mp3")
    fs.create_file("./test/song7.mp3")
    fs.create_file("./test/sub/song8.mp3")
    fs.create_file("./test/sub/song9.mp3")
    fs.create_file("./test/sub/song0.mp2")
    fs.create_dir("./output")
    yield fs


@pytest.mark.parametrize(
    "path, file_format, recursive, expected_count",
    [
        ("./test/song1.mp3", (".mp3",), False, 1),
        ("./test", (".mp3",), False, 5),
        ("./test", (".mp3",), True, 7),
        ("./test", (".mp3", ".mp2"), True, 8),
    ],
)
def test_glob_files(
    path, file_format, recursive, expected_count, fake_fs: FakeFilesystem
):
    res = util.glob_files(path, file_format, recursive)

    assert len(res) == expected_count


def test_glob_files_returns_error_if_no_files_found(fake_fs: FakeFilesystem):
    with pytest.raises(FileNotFoundError):
        util.glob_files("./test", (".mpx",), False)


def test_creates_missing_output_folder(mocker: MockerFixture, fake_fs: FakeFilesystem):
    mocker.patch(f"{UTIL_PATH}.prompt_yes_no", return_value=True)

    util.create_missing_folder("./testpath")

    assert os.path.exists("./testpath")


@pytest.mark.parametrize("cores", [1, 2])
def test_run_multiprocessing_ends_if_not_enough_cores(cores, mocker: MockerFixture):
    mocker.patch("multiprocessing.cpu_count", return_value=cores)

    with pytest.raises(RuntimeError):
        util.run_multiprocessed(MagicMock, ["test"])


def job(arg_1, arg_2):
    return arg_1 + arg_2


def test_run_multiprocessing(mocker: MockerFixture):
    mocker.patch("multiprocessing.cpu_count", return_value=4)

    res = util.run_multiprocessed(job, [(1, 2), (3, 4), (5, 6)])

    assert res == [3, 7, 11]


@pytest.mark.parametrize(
    "arg, expected",
    [
        ("yes", True),
        ("no", False),
        ("YES", True),
        ("NO", False),
        ("Y", True),
        ("N", False),
        ("YE s", False),
        ("", True),
        ("y", True),
        ("n", False),
        ("uhadiuui", False),
        ("1", False),
        ("0", False),
    ],
)
def test_prompt_yes_no_handles_inputs_correctly(
    arg: str, expected: bool, mocker: MockerFixture
):
    mocker.patch("builtins.input", return_value=arg)
    assert util.prompt_yes_no("", True, max_iterations=1) is expected


@pytest.mark.parametrize(
    "start_time, end_time, ndigits",
    [
        (6, 9, None),
        (8.5, 13.2, 1),
        (7.234235, 10.4444, None),
        (3.2495, 10, 4),
    ],
)
def test_track_elapsed_time(
    start_time, end_time, ndigits, mocker: MockerFixture, capfd
):
    mock_time = mocker.patch("time.perf_counter")

    # Return the start_time the first time that time.perf_counter is called,
    # and the end_time for the second time
    def time_side_effect():
        if len(mock_time.mock_calls) == 1:
            return start_time
        return end_time

    mock_time.side_effect = time_side_effect

    @util.track_elapsed_time(ndigits=ndigits)
    def test_function():
        print("Hello, World!")

    test_function()
    output = capfd.readouterr().out
    elapsed_time = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", output)

    assert elapsed_time[0] == str(round(end_time - start_time, ndigits=ndigits))
