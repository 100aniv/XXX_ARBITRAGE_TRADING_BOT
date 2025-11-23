"""Fix AlertRecord instantiations in test files to include title parameter"""

import re
from pathlib import Path

def fix_alert_records(filepath):
    """Fix AlertRecord calls to include title parameter"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: AlertRecord without title, has message
    # Look for patterns like:
    # AlertRecord(
    #     severity=...,
    #     source=...,
    #     message="...",
    
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts an AlertRecord
        if 'AlertRecord(' in line:
            # Collect the full AlertRecord block
            block_start = i
            block_lines = [line]
            paren_count = line.count('(') - line.count(')')
            i += 1
            
            while i < len(lines) and paren_count > 0:
                block_lines.append(lines[i])
                paren_count += lines[i].count('(') - lines[i].count(')')
                i += 1
            
            # Check if block has 'message=' but no 'title='
            block_text = '\n'.join(block_lines)
            if 'message=' in block_text and 'title=' not in block_text:
                # Need to fix: insert title before message
                fixed_block = []
                for bline in block_lines:
                    if 'message=' in bline:
                        # Add title line before message
                        indent = len(bline) - len(bline.lstrip())
                        title_line = ' ' * indent + 'title="Test",'
                        fixed_block.append(title_line)
                    fixed_block.append(bline)
                fixed_lines.extend(fixed_block)
            else:
                fixed_lines.extend(block_lines)
        else:
            fixed_lines.append(line)
            i += 1
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    
    print(f"✅ Fixed {filepath}")

if __name__ == '__main__':
    test_files = [
        Path('tests/test_email_notifier.py'),
        Path('tests/test_postgres_storage.py'),
    ]
    
    for test_file in test_files:
        if test_file.exists():
            fix_alert_records(test_file)
        else:
            print(f"⚠️  File not found: {test_file}")
