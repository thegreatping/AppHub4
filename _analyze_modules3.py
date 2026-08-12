"""Final clean analysis with correct module boundaries."""
import re
from pathlib import Path

base = Path(r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4\msapp_extracted")
mm_file = base / "Src" / "screen_MainMenu.pa.yaml"
content = mm_file.read_text(encoding="utf-8")
lines = content.split("\n")
total_lines = len(lines)

# CORRECT module boundaries (verified from code):
modules = {
    "FastTrack Recommendation": {"app_id": 20, "start": 54947, "end": 56957, "table": "FASTTRACK_RECOMMENDATION"},
    "Cultivate Nomination": {"app_id": 22, "start": 58779, "end": 60717, "table": "CULTIVATE_NOMINATION"},
    "Rush Check Request": {"app_id": 19, "start": 72156, "end": 77090, "table": "Rush Check Request"},
    "PeakLink Idea": {"app_id": 25, "start": 79332, "end": 81198, "table": "PeakLink"},
    "New Hire Alert": {"app_id": 16, "start": 81198, "end": 85396, "table": "NEW_HIRE_ALERTS"},
    "Promo/Transfer Alert (PAF)": {"app_id": 27, "start": 85396, "end": 90459, "table": "PAF Alert"},
    "Mindset Award Nomination": {"app_id": 24, "start": 90459, "end": total_lines, "table": "Peak Mindset Recognition"},
}

def analyze_module(lines_list, start, end, module_name):
    """Deep analysis of a module section."""
    section_lines = lines_list[start-1:end-1]
    section_text = "\n".join(section_lines)
    
    # Controls breakdown
    controls = {"Form": 0, "Gallery": 0, "Button": 0, "ModernButton": 0, 
                "TextInput": 0, "DropDown": 0, "ComboBox": 0, "DatePicker": 0,
                "Label": 0, "Icon": 0, "Image": 0, "Toggle": 0, "CheckBox": 0,
                "GroupContainer": 0, "Other": 0}
    total_controls = 0
    
    for line in section_lines:
        m = re.match(r'\s+Control:\s+(\S+)', line)
        if m:
            total_controls += 1
            ctrl_type = m.group(1).split("@")[0].replace("Classic/", "")
            matched = False
            for key in controls:
                if key in ctrl_type:
                    controls[key] += 1
                    matched = True
                    break
            if not matched:
                controls["Other"] += 1
    
    # Data sources and tables
    data_sources = set()
    for ds in re.findall(r"DataSource:\s*='?([^'\s\n]+)'?", section_text):
        if ds not in ['=', '']:
            data_sources.add(ds.strip("'"))
    
    # Items sources (galleries)
    for im in re.findall(r"Items:\s*=.*?'([A-Z][A-Za-z_ 0-9]+)'", section_text):
        data_sources.add(im)
    for im in re.findall(r"Items:\s*=(?:Sort|Filter|Search)?\(?([A-Z_][A-Z_0-9]+)", section_text):
        if im not in ['Sort', 'Filter', 'Search', 'If', 'RGBA', 'Max', 'Min']:
            data_sources.add(im)
    
    # Patch operations
    patches = len(re.findall(r"Patch\(", section_text))
    patch_targets = set()
    for pm in re.findall(r"Patch\(\s*'?([^',\s)]+)'?", section_text):
        if pm not in ['Defaults']:
            patch_targets.add(pm.strip("'"))
    
    # Sub-states (decimal varSelection)
    sub_states = sorted(set(re.findall(r'varSelection[,\s=]+(\d+\.?\d*)', section_text)))
    
    # Form DataCards (represent fields)
    data_cards = len(re.findall(r'Control:\s*TypedDataCard', section_text))
    
    # DataField entries (actual form fields)
    data_fields = re.findall(r'DataField:\s*="([^"]+)"', section_text)
    
    # SubmitForm calls
    submits = len(re.findall(r"SubmitForm\(", section_text))
    
    # Notify calls
    notifies = len(re.findall(r"Notify\(", section_text))
    
    # Navigate calls
    navigates = len(re.findall(r"Navigate\(", section_text))
    
    # Office365Users / connector calls
    connectors = set()
    if "Office365Users" in section_text:
        connectors.add("Office365Users")
    if "Office365Outlook" in section_text:
        connectors.add("Office365Outlook")
    if "SendEmail" in section_text or "Send(" in section_text:
        connectors.add("Email/Send")
    
    # Lookup complexity
    lookups = len(re.findall(r"LookUp\(", section_text))
    
    # If/Switch complexity  
    if_count = len(re.findall(r"\bIf\(", section_text))
    switch_count = len(re.findall(r"\bSwitch\(", section_text))
    
    return {
        "total_controls": total_controls,
        "controls": {k: v for k, v in controls.items() if v > 0},
        "data_sources": data_sources,
        "patches": patches,
        "patch_targets": patch_targets,
        "sub_states": sub_states,
        "data_cards": data_cards,
        "data_fields": data_fields,
        "submits": submits,
        "notifies": notifies,
        "navigates": navigates,
        "connectors": connectors,
        "lookups": lookups,
        "if_count": if_count,
        "switch_count": switch_count,
        "line_span": end - start,
    }

# Analyze each module
results = {}
for name, info in modules.items():
    result = analyze_module(lines, info["start"], info["end"], name)
    results[name] = result

# Print results
for name, result in sorted(results.items(), key=lambda x: x[1]["line_span"]):
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"  App_ID: {modules[name]['app_id']} | Primary Table: {modules[name]['table']}")
    print(f"  Lines: {modules[name]['start']}-{modules[name]['end']} (span: {result['line_span']})")
    print(f"{'='*70}")
    print(f"  Total Controls: {result['total_controls']}")
    print(f"  Control Breakdown: {result['controls']}")
    print(f"  Form DataCards (fields): {result['data_cards']}")
    if result['data_fields']:
        print(f"  Field Names: {result['data_fields'][:20]}")
        if len(result['data_fields']) > 20:
            print(f"    ... and {len(result['data_fields']) - 20} more")
    print(f"  Sub-states: {result['sub_states']}")
    print(f"  Data Sources: {result['data_sources']}")
    print(f"  Patch targets: {result['patch_targets']} ({result['patches']} calls)")
    print(f"  SubmitForm: {result['submits']}, Notify: {result['notifies']}")
    print(f"  Connectors: {result['connectors']}")
    print(f"  Logic: LookUps={result['lookups']}, If()={result['if_count']}, Switch()={result['switch_count']}")
    
    # Complexity rating
    score = 0
    score += result['line_span'] / 500  # size factor
    score += result['total_controls'] / 20
    score += len(result['sub_states']) * 2
    score += result['patches'] * 3
    score += len(result['data_sources']) * 2
    score += result['if_count'] / 5
    score += result['lookups'] / 3
    score += len(result['connectors']) * 5
    
    if score < 30:
        rating = "SIMPLE"
    elif score < 60:
        rating = "MEDIUM"
    else:
        rating = "COMPLEX"
    
    print(f"\n  >>> COMPLEXITY SCORE: {score:.0f} ({rating})")

# Final ranking
print("\n\n" + "=" * 70)
print("  FINAL RANKING: Simplest → Most Complex")
print("=" * 70)
ranked = sorted(results.items(), key=lambda x: (
    x[1]['line_span'] / 500 + x[1]['total_controls'] / 20 + 
    len(x[1]['sub_states']) * 2 + x[1]['patches'] * 3 +
    len(x[1]['data_sources']) * 2 + x[1]['if_count'] / 5 +
    x[1]['lookups'] / 3 + len(x[1]['connectors']) * 5
))

for i, (name, result) in enumerate(ranked, 1):
    score = (result['line_span'] / 500 + result['total_controls'] / 20 + 
             len(result['sub_states']) * 2 + result['patches'] * 3 +
             len(result['data_sources']) * 2 + result['if_count'] / 5 +
             result['lookups'] / 3 + len(result['connectors']) * 5)
    if score < 30:
        rating = "SIMPLE"
    elif score < 60:
        rating = "MEDIUM"
    else:
        rating = "COMPLEX"
    
    print(f"\n  #{i}. {name} (App_ID {modules[name]['app_id']})")
    print(f"      Score: {score:.0f} | Rating: {rating}")
    print(f"      Controls: {result['total_controls']} | Fields: {result['data_cards']} | Sub-views: {len(result['sub_states'])}")
    print(f"      Patches: {result['patches']} | Submits: {result['submits']} | Table: {modules[name]['table']}")
