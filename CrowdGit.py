import subprocess
import os

def run_batch_file(batch_file_path):
    """Runs a batch file and handles errors."""
    try:
        subprocess.run([batch_file_path], check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing batch file: {e}")
    except FileNotFoundError:
        print(f"Batch file not found at: {batch_file_path}")

if __name__ == "__main__":
    batch_file = os.path.join(os.path.dirname(__file__), "launch.bat")
    run_batch_file(batch_file)
    
# pyinstaller --onefile --windowed --icon=skull-icon-5253.png CrowdGit.py