import copy,json,re,unittest
import compile as compiler
from contracts import BASE

class AcquisitionProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs,cls.reuse=compiler.load()
        cls.passive=json.loads((BASE/'execution/runtime-verification.json').read_text())
        cls.proof=json.loads((BASE/'execution/acquisition-verification.json').read_text())
        cls.id='candidate-901-magic-bundle-ba577210e69dafd5'

    def projection(self,docs=None,proof=None):
        artifacts,counts=compiler.build(self.docs if docs is None else docs,self.reuse,self.passive,acquisition_evidence=proof)
        data=json.loads(re.search(r'export const RESOURCE_DATA=(.*);',artifacts['resource-data.mjs'])[1])
        return data,counts

    def test_no_acquisition_proof_does_not_export_or_sell_the_bundle(self):
        data,counts=self.projection()
        self.assertNotIn(self.id,data)
        self.assertEqual(counts['verifiedAcquisitionTransactions'],0)
        self.assertEqual(counts['verifiedPassiveSlices'],3)

    def test_current_proof_exports_only_arcane_D_C_and_grant_operation(self):
        data,counts=self.projection(proof=self.proof)
        self.assertEqual(data[self.id]['learning']['byGrade'],{'D':15,'C':35})
        self.assertEqual(data[self.id]['acquisition']['specializations'],['奥术'])
        self.assertEqual(data[self.id]['operations'],['claimLearning'])
        self.assertFalse(data[self.id]['verification']['runtimeFullyVerified'])
        self.assertEqual(counts['verifiedAcquisitionTransactions'],1)

    def test_changed_acquisition_contract_cannot_reuse_previous_proof(self):
        docs=copy.deepcopy(self.docs)
        next(d for d in docs if d['id']==self.id)['definition']['acquisition']['stages']['C']['poolCapacity']=11
        data,counts=self.projection(docs,proof=self.proof)
        self.assertNotIn(self.id,data)
        self.assertEqual(counts['verifiedAcquisitionTransactions'],0)

    def test_changed_runtime_proof_is_rejected(self):
        proof=copy.deepcopy(self.proof);proof['engineModules'][0]['sha256']='stale'
        with self.assertRaisesRegex(ValueError,'executor/test changed'):
            self.projection(proof=proof)

if __name__=='__main__':unittest.main()
