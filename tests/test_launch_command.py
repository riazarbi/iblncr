import pytest
from click.testing import CliRunner
from iblncr.main import cli
from unittest.mock import patch

@pytest.fixture
def runner():
    return CliRunner()

@patch('iblncr.main.run_docker_container')
def test_cli_launch_option(mock_run_docker, runner):
    # Test successful launch
    result = runner.invoke(cli, ['launch'])
    assert result.exit_code == 0
    mock_run_docker.assert_called_once()

    # Test launch with error
    mock_run_docker.reset_mock()
    mock_run_docker.side_effect = Exception("Docker error")
    result = runner.invoke(cli, ['launch'])
    assert result.exit_code == 1
    assert "Docker error: Docker error" in result.output

def test_cli_invalid_option(runner):
    result = runner.invoke(cli, ['--invalid'])
    assert result.exit_code != 0 