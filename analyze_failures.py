import re
from collections import Counter

log = open('docs/D99/evidence/d99_6_p1_fixpack_20251222_183648/step0_baseline_full_regression.txt', 'rb').read().decode('utf-8', errors='ignore')

# Extract FAILED test lines
failed_tests = [l.strip() for l in log.split('\n') if l.strip().startswith('FAILED tests/')]

# Extract test files
test_files = []
for test in failed_tests:
    match = re.search(r'FAILED (tests/[^:]+)', test)
    if match:
        test_files.append(match.group(1))

# Count by file
file_counts = Counter(test_files)

# Output
result = []
result.append(f'Total FAILED tests: {len(failed_tests)}')
result.append(f'Total unique test files: {len(file_counts)}')
result.append('\nTop 10 test files by FAIL count:')
for i, (file, count) in enumerate(file_counts.most_common(10), 1):
    pct = (count / len(failed_tests)) * 100 if failed_tests else 0
    result.append(f'{i}. {file}: {count} failures ({pct:.1f}%)')

# Top 3 coverage
top3_count = sum(count for _, count in file_counts.most_common(3))
top3_pct = (top3_count / len(failed_tests)) * 100 if failed_tests else 0
result.append(f'\nTop 3 coverage: {top3_count}/{len(failed_tests)} ({top3_pct:.1f}%)')

output = '\n'.join(result)
print(output)
open('docs/D99/evidence/d99_6_p1_fixpack_20251222_183648/step1_error_signature.txt', 'w', encoding='utf-8').write(output)
