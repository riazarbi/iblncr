import subprocess
import signal
import sys

def run_docker_container():
    """
    Run the IB Gateway Docker container and handle graceful shutdown on CTRL-C
    """
    try:
        # Start the Docker container
        process = subprocess.Popen([
            "docker", "run",
            "-it",
            "--rm",
            "--name", "broker",
            "-p", "4003:4003",
            "ghcr.io/riazarbi/ib-headless:10.30.1t"
        ])
        
        # Define signal handler for graceful shutdown
        def signal_handler(signum, frame):
            print("\nShutting down Docker container...")
            process.terminate()
            process.wait()
            sys.exit(0)
            
        # Register SIGINT (CTRL-C) handler
        signal.signal(signal.SIGINT, signal_handler)
        
        # Wait for the process to complete
        process.wait()
        
    except Exception as e:
        print(f"Error running Docker container: {e}")
        sys.exit(1) 