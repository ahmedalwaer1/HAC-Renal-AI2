import subprocess
import sys

python_exe = r"C:\laragon\bin\python\python-3.13\python.exe"

# Install python-dotenv first (small package)
result = subprocess.run([python_exe, "-m", "pip", "install", "python-dotenv"], 
                       capture_output=True, text=True, timeout=120)
print("STDOUT:", result.stdout[-2000:] if result.stdout else "")
print("STDERR:", result.stderr[-2000:] if result.stderr else "")
print("Return code:", result.returncode)

# Install langchain
result2 = subprocess.run([python_exe, "-m", "pip", "install", "langchain"], 
                        capture_output=True, text=True, timeout=300)
print("=== LangChain ===")
print("STDOUT:", result2.stdout[-2000:] if result2.stdout else "")
print("STDERR:", result2.stderr[-2000:] if result2.stderr else "")
print("Return code:", result2.returncode)

# Install langchain-openai
result3 = subprocess.run([python_exe, "-m", "pip", "install", "langchain-openai"], 
                        capture_output=True, text=True, timeout=300)
print("=== LangChain-OpenAI ===")
print("STDOUT:", result3.stdout[-2000:] if result3.stdout else "")
print("STDERR:", result3.stderr[-2000:] if result3.stderr else "")
print("Return code:", result3.returncode)