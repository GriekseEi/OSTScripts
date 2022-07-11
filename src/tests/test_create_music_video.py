# pylint:disable=missing-function-docstring
import pytest
import src.create_music_video as cmv

DEFAULT_ARGS = ["-a", "asdasd", "-i", "asdasds", "-o", "assd"]


@pytest.fixture(name="fake_fs")
def fixture_fake_fs(fs):  # pylint:disable=invalid-name
    yield fs


def test_prints_help_if_no_arguments_are_passed():
    res = cmv.main()
    assert res == 1


@pytest.mark.parametrize(
    "args",
    (
        ["-f"],
        ["-a", "test.mp3", "-i", "test.jpg", "-f"],
        ["-f", "-a", "test.mp3", "-i", "test.jpg"],
    ),
)
def test_format_switch_prints_all_formats(args, capfd):
    res = cmv.main(cli_args=args)
    out = capfd.readouterr().out

    assert res == 1
    assert str(cmv.VALID_IMG_FORMATS) in out
    assert str(cmv.VALID_AUD_FORMATS) in out
    assert str(cmv.VALID_VID_FORMATS) in out


def test_installs_ffmpeg_on_windows_if_not_present(mocker):
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("src.create_music_video.is_app_installed", return_value=False)
    mocked_install = mocker.patch(
        "src.create_music_video.install_ffmpeg_windows", return_value=None
    )
    cmv.main(cli_args=DEFAULT_ARGS)
    mocked_install.assert_called_once()


@pytest.mark.parametrize("system_name", ("Linux", ""))
def test_notifies_non_windows_user_if_ffmpeg_not_present(system_name, mocker):
    mocker.patch("platform.system", return_value=system_name)
    mocker.patch("src.create_music_video.is_app_installed", return_value=False)
    assert cmv.main(cli_args=DEFAULT_ARGS) == 1


@pytest.mark.parametrize(
    "path, file_format, recursive, expected_count",
    [
        ("./test1/test.mp3", (".mp3"), False, 1),
        ("./test1", (".mp3"), False, 3),
        ("./test1", (".mp3"), True, 5),
        ("./test1", (".mp3", ".mp2"), True, 6),
    ],
)
def test_glob_files(path, file_format, recursive, expected_count, fake_fs):
    fake_fs.create_file("/test1/test.mp3")
    fake_fs.create_file("/test1/test2.mp3")

    res = cmv.glob_files(path, file_format, recursive)
    assert len(res) == expected_count
