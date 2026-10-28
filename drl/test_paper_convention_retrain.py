"""Prespecified one-factor design and Java transition/reward sanity checks."""
import unittest
from .environment import EnvConfig,PaperEnv
from .paper_convention_retrain import feasibility_preflight,load_plan,profile_config


class ConventionRetrainTests(unittest.TestCase):
    def test_profiles_change_exactly_one_setting(self):
        p,base=load_plan()
        for name,override in p['profiles'].items():
            cfg=profile_config(base,override)
            changed={k for k in cfg['properties'] if cfg['properties'][k]!=base['properties'][k]}
            self.assertEqual(set(override),changed)
            self.assertEqual(1000000,cfg['steps_per_model'])
            self.assertEqual([0,1,2],cfg['learning_seeds'])

    def test_completion_changes_freshness_not_single_slot_energy(self):
        with PaperEnv(EnvConfig(layout_seed=0,powered=12,connected=12,max_slots=1)) as ref,PaperEnv(EnvConfig(layout_seed=0,powered=12,connected=12,max_slots=1,properties={'paper.deliveryConvention':'COMPLETED'})) as altered:
            ref.reset(seed=43,options={'task_seed':43});altered.reset(seed=43,options={'task_seed':43})
            a=ref.step(0);b=altered.step(0)
            self.assertEqual(a[4]['seconds'],b[4]['seconds'])
            self.assertEqual(a[4]['uav_battery_j'],b[4]['uav_battery_j'])
            self.assertEqual(0,max(a[0][12:]));self.assertGreater(max(b[0][12:]),0)

    def test_optimistic_cover_bound_is_not_immediately_impossible(self):
        p=feasibility_preflight();self.assertEqual(9,len(p['LOCAL_COMPLETION']['always_uav_dependent_devices']))
        self.assertEqual(7,p['LOCAL_COMPLETION']['optimistic_min_visits_per_age_window'])
        self.assertTrue(p['LOCAL_COMPLETION']['necessary_cover_bound_satisfied'])


if __name__=='__main__':unittest.main()
