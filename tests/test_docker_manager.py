import pytest
from unittest.mock import patch, MagicMock
from iblncr.docker_manager import run_docker_container

def test_run_docker_container():
    with patch('subprocess.Popen') as mock_popen:
        # Setup mock process
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Run the container
        with patch('signal.signal') as mock_signal:
            run_docker_container()
            
            # Verify Docker command
            mock_popen.assert_called_once_with([
                "docker", "run",
                "-it",
                "--rm",
                "--name", "broker",
                "-p", "4003:4003",
                "ghcr.io/riazarbi/ib-headless:10.30.1t"
            ])
            
            # Verify signal handler was registered
            mock_signal.assert_called_once()
            
            # Verify process.wait() was called
            mock_process.wait.assert_called_once()

def test_docker_container_error_handling():
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.side_effect = Exception("Docker error")
        
        with pytest.raises(SystemExit) as exc_info:
            run_docker_container()
        
        assert exc_info.value.code == 1 