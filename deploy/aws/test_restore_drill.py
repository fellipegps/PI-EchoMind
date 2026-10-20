"""Fail closed on expanding the planned recovery templates. No AWS calls."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml
from check_infra import CfnLoader

ROOT = Path(__file__).resolve().parent

def read(name):
    return yaml.load((ROOT/name).read_text(encoding='utf-8'),Loader=CfnLoader)

def guard(template):
    with tempfile.TemporaryDirectory(prefix='restore-guard-') as directory:
        data=Path(directory)/'template.json'
        data.write_text(json.dumps(template),encoding='utf-8')
        return subprocess.run(['cfn-guard','validate','--rules',str(ROOT/'restore-security.guard'),
            '--data',str(data),'--output-format','json'],capture_output=True,text=True,timeout=30)

def validate_access(template):
    assert set(template['Resources']) == {'RecoveryOperatorPolicy','RecoveryExecutionInspectionPolicy'}
    allowed = {'ec2:DescribeSnapshots','dlm:GetLifecyclePolicy','cloudformation:CreateStack',
        'cloudformation:DescribeStacks','cloudformation:DescribeEvents','cloudformation:DescribeStackEvents',
        'cloudformation:DescribeStackResource','cloudformation:DescribeStackResources',
        'cloudformation:ListStackResources','cloudformation:GetTemplate','cloudformation:DeleteStack'}
    for resource in template['Resources'].values():
        assert resource['Type'] == 'AWS::IAM::ManagedPolicy'
        policy=resource['Properties']['PolicyDocument']
        assert len(json.dumps(policy,separators=(',',':'))) < 6144
        for statement in policy['Statement']:
            actions=statement['Action']
            actions={actions} if isinstance(actions,str) else set(actions)
            assert actions <= allowed and statement['Effect']=='Allow'
            if any(action.startswith('cloudformation:') for action in actions):
                assert statement['Resource']['Fn::Sub'].endswith('stack/${ApplicationStackName}-restore-drill/*')
                assert statement['Condition']['Bool']['aws:MultiFactorAuthPresent'] is True
    create=next(s for s in template['Resources']['RecoveryOperatorPolicy']['Properties']['PolicyDocument']['Statement']
                if s['Sid']=='CreateOnlyRecoveryStack')
    assert create['Condition']['ArnEquals']['cloudformation:RoleArn']['Fn::Sub'].endswith('role/${ExecutionRoleName}')
    reader=template['Resources']['RecoveryExecutionInspectionPolicy']['Properties']['PolicyDocument']['Statement']
    assert len(reader)==1 and reader[0]['Action']=='ec2:DescribeSnapshots'

class RestoreTemplateTest(unittest.TestCase):
    def test_baselines_and_limits(self):
        for name in ('restore-access.yaml','restore-drill.yaml'):
            self.assertLess((ROOT/name).stat().st_size,51200)
            template=read(name)
            result=guard(template)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        validate_access(read('restore-access.yaml'))
        copy=read('restore-drill.yaml')['Resources']['RestoreVolume']
        self.assertEqual(copy['Properties']['SnapshotId'],{'Ref':'SnapshotId'})
        self.assertEqual(copy['Properties']['Size'],20)
        self.assertEqual(copy['DeletionPolicy'],'Delete')

    def test_no_iam_writes_or_production_stack_delete(self):
        for action in ('iam:PutRolePolicy','ec2:DeleteVolume','cloudformation:UpdateStack'):
            template=read('restore-access.yaml')
            template['Resources']['RecoveryOperatorPolicy']['Properties']['PolicyDocument']['Statement'][0]['Action']=action
            with self.assertRaises(AssertionError):validate_access(template)
        template=read('restore-access.yaml')
        statement=template['Resources']['RecoveryOperatorPolicy']['Properties']['PolicyDocument']['Statement'][-1]
        statement['Resource']['Fn::Sub']=statement['Resource']['Fn::Sub'].replace('-restore-drill','')
        with self.assertRaises(AssertionError):validate_access(template)
        self.assertNotEqual(guard(template).returncode,0)

    def test_mfa_and_fixed_role_cannot_be_removed(self):
        for key in ('Bool','ArnEquals'):
            template=read('restore-access.yaml')
            statement=next(s for s in template['Resources']['RecoveryOperatorPolicy']['Properties']['PolicyDocument']['Statement']
                           if s['Sid']=='CreateOnlyRecoveryStack')
            statement['Condition'].pop(key)
            with self.assertRaises((AssertionError,KeyError)):validate_access(template)

    def test_guard_rejects_live_slot_unencrypted_copy_and_automatic_backup_tag(self):
        mutations = [
            lambda t:t['Resources']['RestoreAttachment']['Properties'].update(Device='/dev/sdf'),
            lambda t:t['Resources']['RestoreVolume']['Properties'].update(Encrypted=False),
            lambda t:t['Resources']['RestoreVolume']['Properties']['Tags'].append({'Key':'EchoMindBackup','Value':'echomind-prod'}),
            lambda t:t['Resources'].update(UnexpectedInstance={'Type':'AWS::EC2::Instance','Properties':{}}),
        ]
        for mutate in mutations:
            template=deepcopy(read('restore-drill.yaml'))
            mutate(template)
            self.assertNotEqual(guard(template).returncode,0)

if __name__=='__main__':
    unittest.main()
