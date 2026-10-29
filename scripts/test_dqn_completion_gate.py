"""Windows completion gate: no SSH/shutdown. Reject incomplete, mislabeled or corrupt artifacts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SHELL=Path(os.environ.get('WINDIR','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
COMMIT='a'*40


@unittest.skipUnless(SHELL.exists(),'Windows PowerShell gate')
class CompletionGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='dqn-completion-gate-')
        self.root=Path(self.tmp.name);(self.root/'control').mkdir();(self.root/'smoke').mkdir()
        write=lambda p,obj:p.write_text(json.dumps(obj),encoding='utf8')
        protocol=dict(modes=['paper24','extended125'],learning_seeds=[0,1,2],steps=1000000,test_episodes=30,
            properties={'paper.deliveryConvention':'LEGACY'})
        write(self.root/'control/protocol.json',protocol)
        digest=hashlib.sha256((self.root/'control/protocol.json').read_bytes()).hexdigest()
        self.manifest=dict(status='COMPLETE',smoke=False,commit=COMMIT,plan=protocol,protocol_sha256=digest)
        write(self.root/'manifest.json',self.manifest)
        write(self.root/'smoke/manifest.json',dict(status='COMPLETE',smoke=True,commit=COMMIT,protocol_sha256=digest))
        write(self.root/'smoke/verification.json',dict(status='PASS',traces=32))
        (self.root/'control/exit-code').write_text('0');(self.root/'control/commit').write_text(COMMIT)
        (self.root/'control/job.log').write_text('DQN_24_125_COMPLETE_AND_VERIFIED')
        proofs=[]
        for mode in ['paper24','extended125']:
            for seed in range(3):
                run=f'{mode}/seed-{seed}';d=self.root/run;d.mkdir(parents=True)
                write(d/'config.json',dict(actual_steps=1000000,gradient_updates=249975,seed=seed,environment=dict(observation_mode=mode)))
                for cp in ['best','final']:
                    p=d/(cp+'_model.zip');p.write_bytes((run+cp).encode())
                    proofs.append(dict(run=run,checkpoint=cp,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),steps=1000000))
        write(self.root/'verification.json',dict(status='PASS',source_unchanged=True,traces=1440,checkpoints=proofs))

    def tearDown(self):self.tmp.cleanup()

    def check(self,success):
        p=subprocess.run([str(SHELL),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/wait-dqn-24-125.ps1'),
            '-Directory',str(self.root),'-ExpectedCommit',COMMIT,'-ValidateOnly'],capture_output=True,text=True)
        self.assertEqual(p.returncode==0,success,p.stdout+p.stderr)
        self.assertFalse((self.root/'Tat_may_sau_train.cmd').exists(),'ValidateOnly must not create shutdown command')

    def test_complete_valid_artifacts(self):self.check(True)

    def test_running_campaign_rejected(self):
        self.manifest['status']='RUNNING';(self.root/'manifest.json').write_text(json.dumps(self.manifest));self.check(False)

    def test_corrupt_checkpoint_rejected(self):
        (self.root/'paper24/seed-0/best_model.zip').write_bytes(b'corrupt');self.check(False)

    def test_mislabeled_state_rejected(self):
        p=self.root/'paper24/seed-0/config.json';cfg=json.loads(p.read_text());cfg['environment']['observation_mode']='extended125'
        p.write_text(json.dumps(cfg));self.check(False)

    def test_wrong_source_rejected(self):
        (self.root/'control/commit').write_text('b'*40);self.check(False)


if __name__=='__main__':unittest.main()
