# pylint:disable=missing-function-docstring
"""
Unit test suite for create_music_video.py
"""
import os
import random
from unittest.mock import MagicMock

import create_music_video as cmv
import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock.plugin import MockerFixture

from tests.test_utility_functions import UTIL_PATH

# alias for cmv when we need to mock functions
CMV_PATH = "create_music_video"


@pytest.fixture(name="fake_fs", scope="function")
def fixture_fake_filesystem(fs: FakeFilesystem):  # pylint:disable=invalid-name
    fs.create_file(os.path.join(".", "test", "img1.jpg"))
    fs.create_file(os.path.join(".", "test", "img2.png"))
    fs.create_file(os.path.join(".", "test", "img3.jpg"))
    fs.create_file(os.path.join(".", "test", "song1.mp3"))
    fs.create_file(os.path.join(".", "test", "song2.wav"))
    fs.create_file(os.path.join(".", "test", "song3.mp3"))
    fs.create_file(os.path.join(".", "test", "song4.wav"))
    fs.create_file(os.path.join(".", "test", "song5.mp3"))
    fs.create_file(os.path.join(".", "test", "song6.mp3"))
    fs.create_file(os.path.join(".", "test", "song7.mp3"))
    fs.create_file(os.path.join(".", "test", "sub", "song8.mp3"))
    fs.create_file(os.path.join(".", "test", "sub", "song9.mp3"))
    fs.create_file(os.path.join(".", "test", "sub", "song0.mp2"))
    fs.create_dir("output")
    yield fs


@pytest.fixture(scope="function")
def fixture_cv(mocker: MockerFixture):
    # Disable parallel processing for compatibility's sake
    mocker.patch("multiprocessing.cpu_count", return_value=1)
    mocker.patch(f"{UTIL_PATH}.is_app_installed", return_value=True)
    return mocker.patch(f"{CMV_PATH}.run_ffmpeg_command")


def test_argument_parser_exits_if_no_arguments_are_passed():
    with pytest.raises(SystemExit):
        cmv.parse_args()


@pytest.mark.parametrize(
    "args",
    (
        ["-f"],
        ["-a", "test.mp3", "-i", "test.jpg", "-f"],
        ["-f", "-a", "test.mp3", "-i", "test.jpg"],
    ),
)
def test_format_switch_prints_all_formats(args):
    with pytest.raises(SystemExit) as err:
        cmv.main(cli_args=args)

    assert str(cmv.VALID_IMG_FORMATS) in str(err)
    assert str(cmv.VALID_AUD_FORMATS) in str(err)
    assert str(cmv.VALID_VID_FORMATS) in str(err)


def test_installs_ffmpeg_on_windows_if_not_present(mocker: MockerFixture):
    # End main function prematurely after doing install_ffmpeg_windows
    def glob_side_effect(alpha, beta, gamma):
        raise SystemExit()

    mocked_glob = mocker.patch(f"{UTIL_PATH}.glob_files")
    mocked_glob.side_effect = glob_side_effect
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch(f"{UTIL_PATH}.is_app_installed", return_value=False)
    mocked_install: MagicMock = mocker.patch(
        f"{CMV_PATH}.install_ffmpeg_windows", return_value=None
    )

    with pytest.raises(SystemExit):
        cmv.main(cli_args=["-a", "a", "-i", "b", "-o", "c"])

    mocked_install.assert_called_once()


@pytest.mark.parametrize("system_name", ("Linux", ""))
def test_notifies_non_windows_user_if_ffmpeg_not_present(
    system_name, mocker: MockerFixture
):
    mocker.patch("platform.system", return_value=system_name)
    mocker.patch(f"{UTIL_PATH}.is_app_installed", return_value=False)

    with pytest.raises(SystemExit):
        cmv.main(cli_args=["-a", "a", "-i", "b", "-o", "c"])


@pytest.mark.parametrize("user_input", ["1", "2"])
def test_install_ffmpeg_windows_installs_scoop_if_prompted(
    user_input, mocker: MockerFixture
):
    def is_app_installed_side_effect(*args):
        if args[0] == ["scoop"]:
            return False
        return True

    mock_app: MagicMock = mocker.patch(f"{UTIL_PATH}.is_app_installed")
    mock_app.side_effect = is_app_installed_side_effect
    mocker.patch("builtins.input", return_value=user_input)
    mocker.patch("subprocess.run", return_value=True)
    mock_scoop: MagicMock = mocker.patch(f"{CMV_PATH}.install_scoop")

    cmv.install_ffmpeg_windows()

    mock_scoop.assert_called_once()


def test_install_ffmpeg_windows_downloads_git_build_if_prompted(mocker: MockerFixture):
    mocker.patch(f"{UTIL_PATH}.is_app_installed", return_value=False)
    mck: MagicMock = mocker.patch(f"{CMV_PATH}.download_ffmpeg_git_build")

    cmv.install_ffmpeg_windows()

    mck.assert_called_once()


scale_string = (
    f"scale={cmv.RESOLUTIONS['360p'][0]}:{cmv.RESOLUTIONS['360p'][1]}:"
    f"force_original_aspect_ratio=decrease,pad={cmv.RESOLUTIONS['360p'][0]}:"
    f"{cmv.RESOLUTIONS['360p'][1]}:(ow-iw)/2:(oh-ih)/2"
)


@pytest.mark.parametrize(
    "extra_args, args_to_check, out_format",
    [
        ([], ("libvorbis", "libvpx-vp9"), "webm"),
        (["--use-x265"], ("libvorbis", "libvpx-vp9"), "webm"),
        (["-vf", "mp4"], ("copy", "libx264", "pad=ceil(iw/2)*2:ceil(ih/2)*2"), "mp4"),
        (["-res", "360p"], ("libvpx-vp9", "libvorbis", scale_string), "webm"),
        (["-vf", "mp4", "-res", "360p"], ("copy", "libx264", scale_string), "mp4"),
        (
            ["-vf", "mp4", "-res", "360p", "--use-x265"],
            ("copy", "libx265", scale_string),
            "mp4",
        ),
    ],
)
def test_create_videos_builds_correct_commands_with_different_encoders_and_resolutions(
    extra_args, args_to_check, out_format, fake_fs: FakeFilesystem, fixture_cv
):
    args = ["-a", "test", "-i", "test"]
    args.extend(extra_args)
    res = cmv.main(cli_args=args)

    assert res == 0
    assert len(fixture_cv.mock_calls) == 7
    for call in fixture_cv.mock_calls:
        assert all(elem in call.args[0] for elem in args_to_check)
        assert call.args[0][-1].endswith(out_format)


def test_create_videos_iterates_through_multiple_images_if_provided(
    fake_fs: FakeFilesystem, fixture_cv: MagicMock
):
    images = (
        os.path.join("test", "img1.jpg"),
        os.path.join("test", "img2.png"),
        os.path.join("test", "img3.jpg"),
    )

    res = cmv.main(cli_args=["-a", "test", "-i", "test"])

    assert res == 0
    # Assert that the image paths are looped over sequentially in the FFMPEG commands
    counter = 0
    for call in fixture_cv.mock_calls:
        assert images[counter] in call.args[0]
        counter += 1
        if counter >= len(images):
            counter = 0


def test_create_videos_iterates_through_images_randomly_if_opted_for(
    fake_fs: FakeFilesystem, fixture_cv: MagicMock
):
    # Set RNG to a fixed seed for consistent testing outcomes
    random.seed("test_create_videos")
    expected_choices = (
        os.path.join("test", "img3.jpg"),
        os.path.join("test", "img1.jpg"),
        os.path.join("test", "img2.png"),
        os.path.join("test", "img2.png"),
        os.path.join("test", "img2.png"),
        os.path.join("test", "img3.jpg"),
        os.path.join("test", "img3.jpg"),
    )

    res = cmv.main(cli_args=["-a", "test", "-i", "test", "-rng"])

    assert res == 0
    for index, call in enumerate(fixture_cv.mock_calls):
        assert expected_choices[index] in call.args[0]


@pytest.mark.parametrize(
    "out_folder, out_format",
    [
        (".", "webm"),
        ("output", "wmv"),
        ("output", "mp4"),
        (".", "mov"),
        (".", "webm"),
    ],
)
def test_create_videos_builds_correct_output_filenames(
    out_folder, out_format, fake_fs: FakeFilesystem, fixture_cv: MagicMock
):
    res = cmv.main(
        cli_args=["-a", "test", "-i", "test", "-o", out_folder, "-vf", out_format]
    )

    assert res == 0
    for index, call in enumerate(fixture_cv.mock_calls):
        expected_filename = os.path.join(out_folder, f"song{index + 1}.{out_format}")
        assert expected_filename in call.args[0]
