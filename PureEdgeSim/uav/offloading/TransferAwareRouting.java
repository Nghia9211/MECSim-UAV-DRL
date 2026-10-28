package uav.offloading;

/** ADP-inspired adaptation: keep a new task local while UAV receives an admitted upload.
 * No controller waiting pool, cloud or vehicles; not the original paper's full ADP.
 */
public final class TransferAwareRouting implements OffloadingPolicy {
    @Override public Destination choose(Task task,Context context){
        return OffloadingPolicy.baseline(Baseline.DEADLINE_ENERGY).choose(task,context);
    }
}
