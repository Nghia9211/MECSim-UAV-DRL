"""Causal synthetic-paper state extension. First 24 features preserve paper units."""
import numpy as np

GLOBAL_FEATURES = ('uav_x/800', 'uav_y/800', 'uav_battery/capacity',
                   'slots/max_slots', 'seconds/(max_slots*slot_cap)')
DEVICE_FEATURES = ('x/800', 'y/800', 'powered', 'connected', 'capacity_j/80000',
                   'local_bytes_per_s/100000', 'standby_w/10', 'active_w/10')


def encode_state(raw, snapshot, max_slots):
    u = snapshot['uav']
    values = [u['x_m']/800, u['y_m']/800, u['battery_j']/u['capacity_j'],
              snapshot['slots_completed']/max_slots,
              snapshot['time_s']/(max_slots*snapshot['slot_cap_s'])]
    for d in snapshot['devices']:
        values.extend([d['x_m']/800, d['y_m']/800, float(d['powered']), float(d['connected']),
                       d['capacity_j']/80000, d['local_rate_bytes_s']/100000,
                       d['standby_w']/10, d['active_w']/10])
    # Reject unsupported scaling rather than silently conceal out-of-range data.
    extra = np.asarray(values, dtype=np.float32)
    if extra.shape != (101,) or not np.isfinite(extra).all() or (extra < -1e-7).any() or (extra > 1+1e-7).any():
        raise ValueError('State outside declared extended125 normalization')
    return np.concatenate((np.asarray(raw, dtype=np.float32), np.clip(extra, 0, 1)))
