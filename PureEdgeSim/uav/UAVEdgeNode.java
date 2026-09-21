package uav;

import com.mechalikh.pureedgesim.datacentersmanager.DefaultComputingNode;
import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationmanager.SimulationManager;

/** A real MECSim computing node; its simulation manager advances it on engine events. */
public final class UAVEdgeNode extends DefaultComputingNode {
    private UAVEnergyModel.Load load = UAVEnergyModel.Load.IDLE;

    /** Account for the old load up to this time, then apply the new load. */
    public void setLoadAt(double time, UAVEnergyModel.Load next) {
        java.util.Objects.requireNonNull(next);
        advanceTo(time);
        load = next;
    }
    public UAVEdgeNode(SimulationManager manager, UAVMobilityModel mobility, UAVEnergyModel energy,
                       double mipsPerCore, long cores, long storageMb) {
        super(manager, mipsPerCore, cores, storageMb);
        UAVMobilityModel.requirePositive(mipsPerCore, "MIPS per core");
        if (cores <= 0 || storageMb <= 0) throw new IllegalArgumentException("Cores and storage must be positive");
        setName("UAV-1");
        setType(SimulationParameters.TYPES.EDGE_DATACENTER);
        setMobilityModel(java.util.Objects.requireNonNull(mobility));
        setEnergyModel(java.util.Objects.requireNonNull(energy));
    }

    @Override public UAVMobilityModel getMobilityModel() { return (UAVMobilityModel) mobilityModel; }
    @Override public UAVEnergyModel getEnergyModel() { return (UAVEnergyModel) energyModel; }

    // Do not activate the ground-node update/reassociation loop for a UAV.
    @Override public void startInternal() { }
    @Override protected void updateStatus() { advanceTo(getSimulation().clock()); }

    public void advanceTo(double time) {
        UAVMobilityModel motion = getMobilityModel();
        double start = motion.getLastTime();
        double dt = time - start;
        if (!Double.isFinite(time) || dt < 0) throw new IllegalArgumentException("Time must be monotonic");
        double flightSeconds = motion.isMobile()
                ? Math.min(dt, motion.getRemainingDistance() / motion.getSpeed()) : 0;
        double flown = getEnergyModel().consume(flightSeconds, true, load);
        motion.advanceTo(time, flown);
        double hovered = getEnergyModel().consume(dt - flightSeconds, false, load);
        if (getEnergyModel().getBatteryLevel() <= 1e-10 && !isDead()) {
            setDeath(true, start + flown + hovered);
            motion.setMobile(false); // Freeze; emergency descent is not modeled.
        }
    }
}
