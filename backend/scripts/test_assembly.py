import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core.script_assembly import assemble_training_script, assemble_executable_script

think_block = "I am a think block"
phase2_code_1 = "chair = 5\nfinal_object_name = \"chair\""
phase2_code_2 = "chair = 5\nfinal_object_name = chair"

print("--- EXECUTABLE SCRIPT (with quotes) ---")
print(assemble_executable_script(phase2_code_1))

print("--- EXECUTABLE SCRIPT (without quotes) ---")
print(assemble_executable_script(phase2_code_2))
