@echo off

if not exist templates mkdir templates
if not exist outputs mkdir outputs

(
echo from pathlib import Path
echo p = Path("generate_logsheet.py")
echo txt = p.read_text(encoding="utf-8")
echo txt = txt.replace("/mnt/user-data/uploads/Logsheet_Template.docx", "templates/Logsheet_Template.docx")
echo txt = txt.replace("/mnt/user-data/outputs/Logsheet_June_2026_Test.docx", "outputs/Logsheet_June_2026_Test.docx")
echo p.write_text(txt, encoding="utf-8")
echo print("Patched successfully.")
) > patch_paths.py

python patch_paths.py

pause
