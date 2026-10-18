"""Exercise the actual CLI from an unrelated working directory, without a model."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix='901-kit-cwd-') as cwd:
        def run(tool, *args):
            result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'tools'/tool), *args],
                                    cwd=cwd, capture_output=True, encoding='utf-8')
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            return result.stdout
        report = json.loads(run('check_library.py'))
        assert report['error_count'] == 0, report
        checks.append('package_integrity_and_local_links')
        curated = json.loads(run('check_resources.py'))
        assert curated['error_count'] == 0, curated
        assert curated['source_occurrences'] == 222 and curated['imperial_legal'] == 208, curated
        checks.append('curated_resources_and_spell_source_coverage')
        cards = run('library.py', 'cards', 'CR-04', 'TB-01', 'S-01')
        assert all(cid in cards for cid in ('CR-04', 'TB-01', 'S-01'))
        assert '### S-02' not in cards
        assert '来源：authoring/' in cards
        checks.append('selected_cards_use_packaged_files')
        hit = json.loads(run('library.py', 'search', '武士', 'C级', '--kind', 'resources', '--limit', '1'))
        assert hit['results'][0]['title'] == '武士', hit
        checks.append('exact_resource_name_ranks_first')
        legacy = json.loads(run('library.py', 'search', '剑术师与骑士', '--limit', '1'))
        included = json.loads(run('library.py', 'search', '剑术师与骑士', '--limit', '1', '--include-legacy'))
        assert legacy['matches'] == 0 and included['matches'] > 0
        checks.append('legacy_filter')
        body = run('library.py', 'read', 'content/RE/02_resources/能力组/近战类型/武器类型/武士.md', '--start', '6', '--lines', '12')
        assert body.startswith('6: ') and 'D级' in body
        checks.append('source_lines_from_unrelated_cwd')
        mage = run('library.py', 'read', 'resources/imperial-mage.md', '--start', '43', '--lines', '14')
        assert '魔力增储' in mage and '上限＋10' in mage
        checks.append('curated_resource_from_unrelated_cwd')
        denied = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'tools/library.py'),
                                 'read', '../outside.md'], cwd=cwd, capture_output=True, encoding='utf-8')
        assert denied.returncode != 0 and 'Read only paths under content/ or resources/' in denied.stderr
        checks.append('read_rejects_paths_outside_allowed_folders')
    print(json.dumps({'passed': len(checks), 'checks': checks, 'python': sys.version.split()[0],
                      'model_generation_test': False}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
