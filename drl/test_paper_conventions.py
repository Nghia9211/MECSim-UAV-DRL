"""Default paper parity and opt-in convention protocol tests against Java."""
import unittest
from .environment import EnvConfig,PaperEnv


class ConventionGymTests(unittest.TestCase):
    def finish(self,env):
        obs,info=env.reset(seed=5,options={'task_seed':7})
        rewards=[]
        while True:
            obs,r,t,u,info=env.step(0)
            self.assertTrue(env.observation_space.contains(obs))
            rewards.append(r)
            if t or u:return obs,rewards,info

    def test_above_limit_exposes_terminal_age_eleven(self):
        with PaperEnv(EnvConfig(powered=12,connected=0)) as a,PaperEnv(EnvConfig(powered=12,connected=0,properties={'paper.expiryConvention':'ABOVE_LIMIT'})) as b:
            x,_,ia=self.finish(a);y,_,ib=self.finish(b)
            self.assertEqual(10,ia['slots']);self.assertEqual(11,ib['slots'])
            self.assertEqual(10,max(x[12:]));self.assertEqual(11,max(y[12:]))

    def test_reward_timing_changes_reward_not_fixed_actions_physics(self):
        with PaperEnv(EnvConfig(powered=12,connected=0)) as a,PaperEnv(EnvConfig(powered=12,connected=0,properties={'paper.rewardSnapshot':'AFTER'})) as b:
            x,ra,ia=self.finish(a);y,rb,ib=self.finish(b)
            self.assertEqual(ia['slots'],ib['slots']);self.assertEqual(ia['seconds'],ib['seconds'])
            self.assertEqual(x.tolist(),y.tolist());self.assertNotEqual(ra,rb)


if __name__=='__main__':unittest.main()
