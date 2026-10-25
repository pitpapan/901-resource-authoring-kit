"""Contract/compiler checks; never write gameplay state or contact a model."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import compile_resources as compiler


class ContractCompilerTest(unittest.TestCase):
    def test_explicit_candidate_package_includes_only_verified_projection_and_preserves_identity(self):
        package=compiler.ROOT/'outputs/技艺适配-20261025'
        candidates,index,docs,_=compiler.load_candidate_package(package)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            with patch.object(compiler,'dump'):
                counts=compiler.compile_to(dest,package)
            data=json.loads((dest/'resource-data.mjs').read_text().split('=',1)[1].strip().removesuffix(';'))
            actions=json.loads((dest/'resource-action-index.mjs').read_text().split('=',1)[1].strip().removesuffix(';'))
            self.assertEqual(counts['developmentCandidates'],len(candidates))
            projected={id:d for id,d in data.items() if d['identity'].get('adoptionStatus')=='candidate'}
            self.assertEqual(projected,candidates)
            self.assertEqual([a for a in actions if a['resourceId'] in candidates],index)
            for id,d in projected.items():
                self.assertEqual(d['contractVersion'],docs[id]['version'])
                self.assertEqual(d['reading'],docs[id]['reading'])
                self.assertFalse(d['verification']['runtimeFullyVerified'])

    def test_classifier_and_runtime_retain_exact_contract_provenance(self):
        docs = compiler.load_contracts()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with patch.object(compiler, 'dump'):
                counts = compiler.compile_to(dest)
            text = (dest / 'resource-action-index.mjs').read_text()
            index = json.loads(text.split('=', 1)[1].strip().removesuffix(';'))
            self.assertEqual(counts['contracts'], len(docs))
            for contract, row in zip(docs, index):
                self.assertEqual(row['reading'], contract['reading'])
                self.assertEqual(row['sourceChecked'], contract['verification']['sourceChecked'])

    def test_unresolved_rule_cannot_be_marked_fully_verified(self):
        doc = copy.deepcopy(compiler.load_contracts()[0])
        doc['verification'].update(status='verified', runtimeFullyVerified=True)
        doc['implementationGaps'] = []
        for clause in doc['clauses']:
            clause['status'] = 'implemented'
        doc['unresolvedRules'] = [dict(parameter='price', basis='source lacks price', recommendation='confirm price')]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'resources/execution').mkdir(parents=True)
            (root / doc['reading']['path']).parent.mkdir(parents=True, exist_ok=True)
            (root / doc['reading']['path']).write_bytes((compiler.ROOT / doc['reading']['path']).read_bytes())
            (root / 'resources/execution/test.rule.json').write_text(json.dumps(doc))
            with patch.object(compiler, 'ROOT', root), self.assertRaisesRegex(ValueError, '未决|unresolved'):
                compiler.load_contracts()


if __name__ == '__main__':
    unittest.main()
