#!/usr/bin/env python3
"""
Analyze coverage gaps and prioritize improvements
"""

# Coverage data from the report
coverage_data = [
    ("pod/connections/container.py", 128, 104, 19),
    ("pod/client.py", 17, 10, 41),
    ("pod/os_abstraction/base.py", 112, 22, 80),
    ("pod/connections/base.py", 53, 10, 81),
    ("pod/connections/winrm.py", 109, 18, 83),
    ("pod/os_abstraction/factory.py", 87, 15, 83),
    ("pod/os_abstraction/linux.py", 278, 48, 83),
    ("pod/os_abstraction/windows.py", 256, 41, 84),
    ("pod/os_abstraction/container.py", 160, 18, 89),
    ("pod/infrastructure/vsphere/network_config.py", 131, 11, 92),
    ("pod/infrastructure/vsphere/vm_manager.py", 140, 10, 93),
    ("pod/connections/ssh.py", 103, 3, 97),
]

# Sort by potential impact (missing statements)
coverage_data.sort(key=lambda x: x[2], reverse=True)

print("Coverage Gap Analysis")
print("=" * 80)
print(f"{'File':<50} {'Stmts':>6} {'Miss':>6} {'Cover':>6} {'Impact':>8}")
print("-" * 80)

total_missing = sum(item[2] for item in coverage_data)
cumulative = 0

for file, stmts, miss, cover in coverage_data:
    impact = (miss / total_missing) * 100
    cumulative += miss
    file_short = file.replace("pod/", "")
    print(f"{file_short:<50} {stmts:>6} {miss:>6} {cover:>5}% {impact:>7.1f}%")
    
    # Mark files that would get us to 90%
    if cumulative <= 141:
        print(f"  → Covering this file: cumulative = {cumulative} statements")

print("\nTop Priority Files to Reach 90% Coverage:")
print("-" * 50)

# Calculate what we need
priority_files = []
covered_so_far = 0
for file, stmts, miss, cover in coverage_data:
    if covered_so_far < 141:
        priority_files.append((file, miss, cover))
        covered_so_far += miss
        if covered_so_far >= 141:
            # Calculate partial coverage needed from this file
            excess = covered_so_far - 141
            actual_needed = miss - excess
            print(f"\n{file}:")
            print(f"  Current: {cover}% ({stmts - miss}/{stmts})")
            print(f"  Need to cover: {actual_needed} of {miss} missing statements")
            print(f"  Would reach: {((stmts - miss + actual_needed) / stmts * 100):.1f}%")
            break
        else:
            print(f"\n{file}:")
            print(f"  Current: {cover}% ({stmts - miss}/{stmts})")
            print(f"  Need to cover: ALL {miss} missing statements")
            print(f"  Would reach: 100%")

print(f"\nTotal statements to cover: {min(141, covered_so_far)}")
print(f"This would bring overall coverage from 82% to 90%+")