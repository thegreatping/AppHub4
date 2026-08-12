"""Better analysis - find correct module boundaries and analyze complexity."""
import re
from pathlib import Path

base = Path(r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4\msapp_extracted")
mm_file = base / "Src" / "screen_MainMenu.pa.yaml"
content = mm_file.read_text(encoding="utf-8")
lines = content.split("\n")
total_lines = len(lines)

print(f"Total lines in screen_MainMenu.pa.yaml: {total_lines}")

# The decimal-state modules use pattern: Visible: =varSelection >= X && varSelection < Y
# Let's find ALL major container boundaries
print("\n" + "=" * 80)
print("ALL decimal-state module containers (varSelection >= X && < Y)")
print("=" * 80)

decimal_containers = []
for i, line in enumerate(lines, 1):
    m = re.search(r'Visible:\s*=varSelection\s*>=\s*(\d+)\s*&&\s*varSelection\s*<\s*(\d+)', line)
    if m:
        start_val = int(m.group(1))
        end_val = int(m.group(2))
        decimal_containers.append((i, start_val, end_val))

for line_num, sv, ev in decimal_containers:
    print(f"  Line {line_num}: varSelection >= {sv} && < {ev}")

# Also find the varSelection = 15 container for Promo/Transfer
print("\n" + "=" * 80)
print("Looking for varSelection = 15 (Promo/Transfer)")
print("=" * 80)
for i, line in enumerate(lines, 1):
    if "varSelection" in line and "15" in line and "Visible" in line:
        print(f"  Line {i}: {line.strip()[:150]}")

# Now let's analyze each TARGET module
# Based on the gallery Switch, the CORRECT APP_IDs are:
# PeakLink = 25, Cultivate = 22, Mindset = 24, Rush Check = 19, 
# FastTrack = 20, NHA = 16, Promo/Transfer = 27 (PAF) or varSelection=15

# For each decimal module, find its container start and the NEXT container start
print("\n" + "=" * 80)
print("MODULE ANALYSIS")
print("=" * 80)

# Create a sorted list of all major containers by line number
all_containers = []
for line_num, sv, ev in decimal_containers:
    all_containers.append((line_num, f"varSel >= {sv} && < {ev}"))

# Also add the integer-based containers
for i, line in enumerate(lines, 1):
    m = re.search(r'Visible:\s*=varSelection\s*=\s*(\d+)\s*$', line.strip())
    if m:
        val = int(m.group(1))
        if val in [7, 9, 12, 14, 15, 100]:
            all_containers.append((i, f"varSel = {val}"))

all_containers.sort(key=lambda x: x[0])

# Now for each module, find the correct container and analyze it
target_modules = {
    25: ("PeakLink Idea", ">=25 && <26"),
    22: ("Cultivate Nomination", ">=22 && <23"),
    24: ("Peak Mindset Recognition", ">=24 && <25"),
    19: ("Rush Check Request", ">=19 && <20"),
    20: ("FastTrack Recommendation", ">=20 && <21"),
    16: ("New Hire Alert", ">=16 && <17"),
    27: ("Promo/Transfer Alert (PAF)", ">=27 && <28"),
}

def analyze_section(lines_list, start_line, end_line):
    """Analyze a section for controls, data sources, patches, sub-states."""
    controls = 0
    data_sources = set()
    patch_count = 0
    sub_states = set()
    collections = set()
    form_controls = 0
    galleries = 0
    buttons = 0
    text_inputs = 0
    dropdowns = 0
    
    section = "\n".join(lines_list[start_line-1:end_line-1])
    
    for line in lines_list[start_line-1:end_line-1]:
        stripped = line.strip()
        
        # Count controls
        if re.match(r'Control:', stripped):
            controls += 1
            if "Form" in stripped:
                form_controls += 1
            elif "Gallery" in stripped:
                galleries += 1
            elif "Button" in stripped or "ModernButton" in stripped:
                buttons += 1
            elif "TextInput" in stripped:
                text_inputs += 1
            elif "DropDown" in stripped or "ComboBox" in stripped:
                dropdowns += 1
        
        # Data sources
        for ds in re.findall(r"DataSource:\s*='?([^'\s,;)]+)", line):
            if ds not in ['=', ''] and not ds.startswith('='):
                data_sources.add(ds)
        
        # Patch operations  
        if "Patch(" in line:
            patch_count += line.count("Patch(")
            # Get table being patched
            for pm in re.finditer(r"Patch\(\s*'?([A-Z][A-Za-z_0-9 ]*)'?", line):
                data_sources.add(pm.group(1).strip())
        
        # Sub-states (decimal varSelection values)
        for sm in re.findall(r'varSelection[,\s]*=?\s*(\d+\.\d+)', line):
            sub_states.add(sm)
        
        # Collections / data loads
        for cm in re.findall(r'ClearCollect\(\s*([a-zA-Z_0-9]+)', line):
            collections.add(cm)
        
        # Items sources
        for im in re.findall(r"Items:\s*=(?:Sort\(|Filter\()?'?([A-Z][A-Za-z_0-9 ]*)'?", line):
            if im not in ['Sort', 'Filter', 'Search', 'If']:
                data_sources.add(im.strip())
    
    return {
        "controls": controls,
        "data_sources": data_sources,
        "patches": patch_count,
        "sub_states": sorted(sub_states),
        "collections": collections,
        "forms": form_controls,
        "galleries": galleries,
        "buttons": buttons,
        "text_inputs": text_inputs,
        "dropdowns": dropdowns,
        "line_span": end_line - start_line,
    }

# Find proper boundaries for each decimal module
for target_id, (name, pattern) in sorted(target_modules.items()):
    # Find the container line
    container_line = None
    for line_num, sv, ev in decimal_containers:
        if sv == target_id:
            container_line = line_num
            break
    
    if container_line is None:
        # Try the integer pattern for varSelection = 15
        for i, line in enumerate(lines, 1):
            if f"varSelection = {target_id}" in line and "Visible" in line:
                container_line = i
                break
    
    if container_line is None:
        print(f"\n  {name} (App_ID {target_id}): NOT FOUND in screen")
        continue
    
    # Find end: next container at same or lower indent level
    # For decimal modules, use next decimal container start
    end_line = None
    for cl, desc in all_containers:
        if cl > container_line + 10:  # Skip self
            end_line = cl
            break
    if end_line is None:
        end_line = min(container_line + 5000, total_lines)
    
    # For decimal containers, use their exact partner
    for ln, sv, ev in decimal_containers:
        if sv == target_id:
            # Find next decimal container that's NOT a sub-container
            for ln2, sv2, ev2 in decimal_containers:
                if ln2 > ln + 50 and sv2 != target_id:
                    end_line = ln2
                    break
            break
    
    result = analyze_section(lines, container_line, end_line)
    
    print(f"\n{'='*60}")
    print(f"  {name} (App_ID {target_id})")
    print(f"  Lines: {container_line} - {end_line} (span: {result['line_span']})")
    print(f"{'='*60}")
    print(f"    Total Controls: {result['controls']}")
    print(f"    Forms: {result['forms']}, Galleries: {result['galleries']}")
    print(f"    Buttons: {result['buttons']}, TextInputs: {result['text_inputs']}, Dropdowns: {result['dropdowns']}")
    print(f"    Patch operations: {result['patches']}")
    print(f"    Sub-states: {result['sub_states']}")
    print(f"    Data sources: {result['data_sources']}")
    print(f"    Collections loaded: {result['collections']}")
