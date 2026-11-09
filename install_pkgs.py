import subprocess
import sys

python_exe = r"C:\laragon\bin\python\python-3.13\python.exe"
packages = ["langchain", "langchain-openai", "python-dotenv"]

result = subprocess.check_call([python_exe, "-m", "pip", "install"] + packages)
print(f"Install result: {result}")