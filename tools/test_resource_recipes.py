import copy
import unittest
from resource_recipes import compile_contract

class Recipes(unittest.TestCase):
    def contract(self):
        return {'id':'test:opposed', 'version':'test', 'reading':{'path':'rules.md','heading':'示例','sha256':'test'},
                'clauses':[{'id':'base','heading':'示例'}], 'authoring':{'executionSource':'contract'},
                'definition':{'programs':{'cast':{'action':'standard','target':'single','effectComponents':{'main':{'families':['mind']}},
                    'recipe':{'id':'opposed-status','version':1,'clauseId':'base','args':{'component':'main','saveType':'will',
                        'active':{'context':'cast'},'maximumPoints':{'op':'mul','args':[3,{'context':'P'}]},
                        'statusType':'恐惧','properties':{'decayPerRound':1}}}}}},
                'actions':[{'id':'cast','operation':'cast','name':'示例'}]}

    def test_expansion_is_deterministic_and_preserves_source_without_mutating_contract(self):
        raw=self.contract();before=copy.deepcopy(raw)
        first=compile_contract(raw);second=compile_contract(raw)
        self.assertEqual(raw,before);self.assertEqual(first,second)
        p=first['definition']['programs']['cast']
        self.assertNotIn('recipe',p);self.assertEqual([x['op'] for x in p['steps']],['save','status'])
        self.assertEqual(p['steps'][1]['resistance'],{'receipt':'opposition','kind':'resolved'})
        self.assertEqual(p['steps'][1]['points']['args'][1],raw['definition']['programs']['cast']['recipe']['args']['maximumPoints'])
        self.assertEqual(p['compilation']['resourceId'],'test:opposed')
        self.assertEqual(p['compilation']['clauseId'],'base')
        self.assertEqual(p['compilation']['stepIds'],['cast/resist','cast/apply'])
        self.assertEqual(first['actions'][0]['actionCost'],'standard')
        self.assertEqual(first['actions'][0]['resistanceModes'][0]['kind'],'opposed')

    def test_unavailable_recipe_version_or_mixed_editing_sources_fail_before_output(self):
        for kind in ['version','steps','source','clause']:
            raw=self.contract();p=raw['definition']['programs']['cast']
            if kind=='version':p['recipe']['version']=999
            if kind=='steps':p['steps']=[]
            if kind=='source':raw.pop('authoring')
            if kind=='clause':p['recipe']['clauseId']='missing'
            with self.assertRaises(ValueError):compile_contract(raw)

    def test_parameter_types_and_exact_parameter_set_are_checked(self):
        for key,value in [('saveType','invented'),('active','dice-from-model'),('properties',3),('extra',1)]:
            raw=self.contract();raw['definition']['programs']['cast']['recipe']['args'][key]=value
            with self.assertRaises(ValueError):compile_contract(raw)

if __name__=='__main__':unittest.main()
