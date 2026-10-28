package uav.offloading;

/** Marker enabling full queue projections in the fixed-UAV kernel; fallback forbidden. */
public final class QueueImpactRouting implements OffloadingPolicy {
    private final double backgroundWeight;
    public QueueImpactRouting(double weight){if(!Double.isFinite(weight)||weight<0)throw new IllegalArgumentException("Invalid weight");backgroundWeight=weight;}
    public double backgroundWeight(){return backgroundWeight;}
    @Override public Destination choose(Task task,Context context){throw new IllegalStateException("QIOS needs admitted-queue context");}
}
