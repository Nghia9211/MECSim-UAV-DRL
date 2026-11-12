package uav.mec;

import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.Event;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import com.mechalikh.pureedgesim.simulationengine.SimEntity;

/** Drives a {@link MecSimulator} with the PureEdgeSim event engine as the clock (one event per kernel event).
 * The engine keeps a static entity list, so episodes run one at a time on this path.
 */
public final class EngineDriver extends SimEntity {
    private static final int TICK = 7_201;
    private final MecSimulator sim;

    private EngineDriver(PureEdgeSim engine, MecSimulator sim) {
        super(engine);
        this.sim = sim;
    }

    public static synchronized MecSimulator.Result run(Scenario scenario, Policies.Policy policy, boolean trace) {
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS = false;
        var engine = new PureEdgeSim();
        var sim = new MecSimulator(scenario, policy, trace);
        new EngineDriver(engine, sim);
        engine.start();
        return sim.result();
    }

    @Override public void startInternal() { scheduleNext(); }

    private void scheduleNext() {
        double now = getSimulation().clock();
        schedule(this, sim.nextEventTime() - now, TICK);
    }

    @Override public void processEvent(Event e) {
        if (e.getTag() != TICK) throw new IllegalArgumentException("unexpected event tag " + e.getTag());
        sim.advanceTo(getSimulation().clock());
        if (sim.done()) getSimulation().setSimDone(true);
        else scheduleNext();
    }
}
