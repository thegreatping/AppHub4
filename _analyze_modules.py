"""Analyze Power Apps modules from extracted .pa.yaml to determine complexity."""
import re
from pathlib import Path

base = Path(r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4\msapp_extracted")
mm_file = base / "Src" / "screen_MainMenu.pa.yaml"

content = mm_file.read_text(encoding="utf-8")
lines = content.split("\n")

# Find all varSelection visibility blocks and their line ranges
print("=" * 80)
print("SECTION 1: varSelection containers and their line ranges")
print("=" * 80)

# We want to find containers with Visible: =varSelection = X for our target values
targets = [7, 9, 12, 14, 15, 17, 18, 19, 20, 22, 25]

for i, line in enumerate(lines, 1):
    for t in targets:
        # Match exact varSelection = N (not decimals)
        if re.search(rf'Visible:.*varSelection\s*=\s*{t}\b', line):
            print(f"  Line {i}: varSelection = {t} -> {line.strip()[:120]}")

print("\n" + "=" * 80)
print("SECTION 2: Analyzing the Gallery OnSelect Switch (module routing)")
print("=" * 80)

# Find the big gallery OnSelect that has the Switch statement
for i, line in enumerate(lines, 1):
    if "Set(varSelection,Value(ThisItem.App_ID))" in line and "Switch" in line:
        # This is the main routing switch - extract and parse it
        raw = line
        # Find all module cases: N, //Comment
        cases = re.findall(r'(\d+),\s*//([^\r\n]+?)\\r\\n', raw)
        print("\n  APP_ID → Module Name mapping from Switch:")
        for case_id, case_name in cases:
            print(f"    {case_id:>3} → {case_name.strip()}")
        break

print("\n" + "=" * 80)
print("SECTION 3: Data sources referenced per module (from OnStart)")
print("=" * 80)

app_file = base / "Src" / "App.pa.yaml"
app_content = app_file.read_text(encoding="utf-8")

# Module → table mappings from OnStart Switch
module_tables = {
    16: "NEW_HIRE_ALERTS",
    17: "Peak Vendor Setup",
    18: "Special Handling",
    19: "Rush Check Request",
    20: "FASTTRACK_RECOMMENDATION",
    21: "MENTOR_CERTIFICATION",
    22: "CULTIVATE_NOMINATION",
    24: "Peak Mindset Recognition",
    25: "PeakLink",
    26: "The Pitch",
    27: "PAF Alert",
}
for mid, tbl in module_tables.items():
    print(f"  App_ID {mid:>2} → Primary table: {tbl}")

print("\n" + "=" * 80)
print("SECTION 4: Container sizes (line ranges) for each varSelection")
print("=" * 80)

# For decimal-based modules, find their ranges
# Pattern: varSelection >= X && varSelection < Y
decimal_modules = {}
for i, line in enumerate(lines, 1):
    m = re.search(r'varSelection\s*>=\s*(\d+)\s*&&\s*varSelection\s*<\s*(\d+)', line)
    if m:
        start_val = int(m.group(1))
        if start_val not in decimal_modules:
            decimal_modules[start_val] = i
            
# For integer-based visibility
int_modules = {}
for i, line in enumerate(lines, 1):
    m = re.search(r'Visible:\s*=varSelection\s*=\s*(\d+)\s*$', line)
    if m:
        val = int(m.group(1))
        if val in [7, 9, 12, 14, 15]:
            if val not in int_modules:
                int_modules[val] = i

print("\n  Integer-based modules (old style, embedded in MainMenu):")
for val, start_line in sorted(int_modules.items()):
    print(f"    varSelection = {val} starts at line {start_line}")

print("\n  Decimal-based modules (new style, state machine):")
for val, start_line in sorted(decimal_modules.items()):
    print(f"    varSelection >= {val} starts at line {start_line}")

# Now count controls in each module section
print("\n" + "=" * 80)
print("SECTION 5: Control counts per module (approximate)")
print("=" * 80)

def count_controls_in_range(lines_list, start_line, end_line):
    """Count Control: entries in a line range."""
    count = 0
    data_sources = set()
    patches = 0
    for line in lines_list[start_line-1:end_line-1]:
        if "Control:" in line and not line.strip().startswith("#"):
            count += 1
        # Look for data source references
        for ds_match in re.finditer(r"DataSource:\s*=([^\s]+)", line):
            data_sources.add(ds_match.group(1).strip("'\""))
        # Look for Patch operations
        if "Patch(" in line:
            patches += 1
        # Look for table references in Items
        for items_match in re.finditer(r"Items:\s*=(?:Sort\(|Filter\()?'?([A-Z_][A-Za-z_0-9]*)'?", line):
            data_sources.add(items_match.group(1))
    return count, data_sources, patches

# For the newer decimal-state modules, find their full ranges
# These typically span from their start to the next major container
sorted_decimal = sorted(decimal_modules.items())
for idx, (val, start_line) in enumerate(sorted_decimal):
    if idx + 1 < len(sorted_decimal):
        end_line = sorted_decimal[idx + 1][1]
    else:
        end_line = min(start_line + 3000, len(lines))
    
    ctrl_count, ds, patches = count_controls_in_range(lines, start_line, end_line)
    if val in [20, 22, 25]:  # Our targets
        module_name = {20: "FastTrack", 22: "Cultivate", 25: "PeakLink"}.get(val, f"Module {val}")
        print(f"\n  {module_name} (varSelection >= {val}): lines {start_line}-{end_line}")
        print(f"    Controls: {ctrl_count}")
        print(f"    Data sources found: {ds}")
        print(f"    Patch operations: {patches}")
        print(f"    Line span: {end_line - start_line}")

# For integer modules
sorted_int = sorted(int_modules.items())
for idx, (val, start_line) in enumerate(sorted_int):
    # Find end by looking for next container at same indent level
    # Approximate: next varSelection container or +5000 lines
    if idx + 1 < len(sorted_int):
        end_line = sorted_int[idx + 1][1]
    else:
        end_line = min(start_line + 8000, len(lines))
    
    ctrl_count, ds, patches = count_controls_in_range(lines, start_line, end_line)
    module_name = {7: "Mindset", 9: "EDM", 12: "SAM/PeakLink?", 14: "Maintenance", 15: "Promo/Transfer"}.get(val, f"Module {val}")
    print(f"\n  {module_name} (varSelection = {val}): lines {start_line}-{end_line}")
    print(f"    Controls: {ctrl_count}")
    print(f"    Data sources found: {ds}")
    print(f"    Patch operations: {patches}")
    print(f"    Line span: {end_line - start_line}")
