package uav;

import com.mechalikh.pureedgesim.energy.EnergyModelComputingNode;

/** Component power baseline, not a calibrated rotor or hardware model. */
public final class UAVEnergyModel extends EnergyModelComputingNode {
    private final double flightPowerW;
    private final double hoverPowerW;
    private double flightWh;
    private double hoverWh;
    private double transmitWh;
    private double receiveWh;

    /** Electrical power drawn concurrently, not radiated RF power. */
    public record Load(double computeW, double transmitW, double receiveW) {
        public static final Load IDLE = new Load(0, 0, 0);
        public Load {
            for (double value : new double[] {computeW, transmitW, receiveW}) {
                if (!Double.isFinite(value) || value < 0)
                    throw new IllegalArgumentException("Load power must be finite and nonnegative");
            }
            if (!Double.isFinite(computeW + transmitW + receiveW))
                throw new IllegalArgumentException("Load power overflow");
        }
    }

    public UAVEnergyModel(double capacityWh, double flightPowerW, double hoverPowerW) {
        super(0, 0);
        UAVMobilityModel.requirePositive(capacityWh, "battery (Wh)");
        UAVMobilityModel.requirePositive(flightPowerW, "flight power (W)");
        UAVMobilityModel.requirePositive(hoverPowerW, "hover power (W)");
        this.flightPowerW = flightPowerW;
        this.hoverPowerW = hoverPowerW;
        setBattery(true);
        setBatteryCapacity(capacityWh);
    }

    /** Consume up to the available battery; return powered duration in seconds. */
    public double consume(double seconds, boolean flying) {
        return consume(seconds, flying, Load.IDLE);
    }

    /** All components stop together on depletion, sharing the same powered duration. */
    public double consume(double seconds, boolean flying, Load load) {
        java.util.Objects.requireNonNull(load);
        if (!Double.isFinite(seconds) || seconds < 0)
            throw new IllegalArgumentException("Duration must be finite and nonnegative");
        double propulsion = flying ? flightPowerW : hoverPowerW;
        double power = propulsion + load.computeW() + load.transmitW() + load.receiveW();
        if (!Double.isFinite(power)) throw new IllegalArgumentException("Total power overflow");
        double powered = Math.min(seconds, getBatteryLevel() / power * 3600.0);
        double hours = powered / 3600.0;
        if (flying) flightWh += propulsion * hours; else hoverWh += propulsion * hours;
        cpuEnergyConsumption += load.computeW() * hours;
        transmitWh += load.transmitW() * hours;
        receiveWh += load.receiveW() * hours;
        return powered;
    }

    @Override public double getTotalEnergyConsumption() {
        return flightWh + hoverWh + cpuEnergyConsumption + transmitWh + receiveWh;
    }
    @Override public double getBatteryLevel() {
        return Math.max(0, getBatteryCapacity() - getTotalEnergyConsumption());
    }
    public double getFlightWh() { return flightWh; }
    public double getHoverWh() { return hoverWh; }
    public double getComputeWh() { return cpuEnergyConsumption; }
    public double getTransmitWh() { return transmitWh; }
    public double getReceiveWh() { return receiveWh; }
    public double getCommunicationWh() { return transmitWh + receiveWh; }

    // Fail fast rather than let legacy task callbacks bypass the shared power budget.
    @Override public void updateStaticEnergyConsumption() { throw legacyUpdate(); }
    @Override public void updateDynamicEnergyConsumption(double length, double mipsCapacity) { throw legacyUpdate(); }
    @Override public void updateDynamicEnergyConsumption(double capacity, double requirement, double latency) { throw legacyUpdate(); }
    @Override public void updatewirelessEnergyConsumption(double bits,
            com.mechalikh.pureedgesim.datacentersmanager.ComputingNode origin,
            com.mechalikh.pureedgesim.datacentersmanager.ComputingNode destination, int flag) { throw legacyUpdate(); }
    private UnsupportedOperationException legacyUpdate() {
        return new UnsupportedOperationException("UAV energy must be integrated through UAVEdgeNode.setLoadAt/advanceTo");
    }
}
