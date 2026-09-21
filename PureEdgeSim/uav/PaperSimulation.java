package uav;

import com.mechalikh.pureedgesim.scenariomanager.Scenario;
import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.Event;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import com.mechalikh.pureedgesim.simulationmanager.SimulationManager;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import static uav.PaperParameters.*;

/** Paper-oriented environment shared by baselines and Gym; not author source.
 * See PAPER_ALIGNMENT.md for timing, radio, reward and output-link conventions.
 */
public final class PaperSimulation {
    public record DeviceSpec(double x, double y, Hardware hardware, VisionTask task,
                             double capacityJ, boolean powered, boolean connected) {
        public DeviceSpec {
            if (!Double.isFinite(x) || !Double.isFinite(y) || x < 0 || x > AREA_M || y < 0 || y > AREA_M
                    || !Double.isFinite(capacityJ) || capacityJ <= 0)
                throw new IllegalArgumentException("Invalid device position or battery");
            Objects.requireNonNull(hardware); Objects.requireNonNull(task);
        }
    }
    @FunctionalInterface public interface Policy { int choose(double[] observation); }
    public enum Baseline { ROUND_ROBIN, OLDEST_DATA, RANDOM }

    public static List<DeviceSpec> layout(long seed, int poweredCount, int connectedCount) {
        if (poweredCount < 0 || poweredCount > DEVICES || connectedCount < 0 || connectedCount > DEVICES)
            throw new IllegalArgumentException("Availability counts must be in [0,12]");
        Random rng = new Random(seed);
        List<Integer> power = new ArrayList<>(), comms = new ArrayList<>();
        for (int i = 0; i < DEVICES; i++) { power.add(i); comms.add(i); }
        Collections.shuffle(power, rng); Collections.shuffle(comms, rng);
        List<DeviceSpec> result = new ArrayList<>();
        for (int i = 0; i < DEVICES; i++) result.add(new DeviceSpec(
                rng.nextDouble() * AREA_M, rng.nextDouble() * AREA_M,
                Hardware.values()[rng.nextInt(Hardware.values().length)],
                VisionTask.values()[rng.nextInt(VisionTask.values().length)],
                MIN_BATTERY_J + rng.nextDouble() * (MAX_BATTERY_J - MIN_BATTERY_J),
                power.indexOf(i) < poweredCount, comms.indexOf(i) < connectedCount));
        return List.copyOf(result);
    }

    public static Policy policy(Baseline name, long seed) {
        Random rng = new Random(seed);
        int[] next = {0};
        return observation -> {
            if (name == Baseline.RANDOM) return rng.nextInt(DEVICES);
            if (name == Baseline.ROUND_ROBIN) return next[0]++ % DEVICES;
            // Round-robin tie breaking prevents permanent starvation when all data ages are zero.
            int best = next[0] % DEVICES;
            for (int k = 1; k < DEVICES; k++) {
                int i = (next[0] + k) % DEVICES;
                if (observation[DEVICES + i] > observation[DEVICES + best]) best = i;
            }
            next[0] = (best + 1) % DEVICES;
            return best;
        };
    }

    public static final class Manager extends SimulationManager {
        private static final int START_SLOT = 81001, END_SLOT = 81002;
        private final List<DeviceSpec> devices;
        private final double[] battery = new double[DEVICES];
        private final int[] ages = new int[DEVICES];
        private final Random taskRandom;
        private final long taskSeed;
        private final PaperDatasetWorkload dataset;
        private PaperDatasetWorkload.CpuPlan cpuPlan;
        private PaperDatasetWorkload.ImageTask[] imageTasks;
        private double[] localRequired;
        private long imageSubmitted,imageDelivered,cpuSubmitted,cpuCompleted;
        private double deliveredLatency;
        private final List<String> workloadRows=new ArrayList<>(List.of("slot,device,image_index,input_bytes,uav_compute_mi,local_required_s,delivered,latency_s"));
        private final List<String> cpuRows=new ArrayList<>(List.of("slot,source,device,source_index,ready_s,planned_start_s,planned_finish_s,requested_mi,executed_mi,status"));
        private final Policy policy;
        private final int maxSlots;
        private final UAVEdgeNode uav;
        private final List<String> slots = new ArrayList<>(List.of(
                "slot,action,start_s,end_s,duration_s,x_m,y_m,h_m,uav_battery_j,min_device_battery_fraction,max_data_age,completed_offloads,capped_work_items,reward,terminated,truncated,reason"));
        private final List<String> deviceRows = new ArrayList<>(List.of(
                "slot,device,powered,connected,input_bytes,offload_candidate,offload_completed,battery_j,energy_used_j,data_age"));
        private int slot, action;
        private double start, duration, flight, reward;
        private double[] workBytes, activeStart, activeDuration, activePower;
        private boolean[] candidates;
        private double selectedAge, oldestAge;
        private int capped;
        private boolean terminated, truncated;
        private String reason = "RUNNING";
        private boolean recordTrace = true;

        /** Disable CSV formatting/storage during training without changing transitions. */
        public void setRecordTrace(boolean enabled) { recordTrace = enabled; }

        public Manager(PureEdgeSim engine, List<DeviceSpec> devices, long taskSeed, Policy policy, int maxSlots) {
            this(engine,devices,taskSeed,policy,maxSlots,null);
        }
        public Manager(PureEdgeSim engine, List<DeviceSpec> devices, long taskSeed, Policy policy, int maxSlots,
                       PaperDatasetWorkload dataset) {
            super(null, engine, 1, 1, new Scenario(DEVICES, 0, 0));
            if (devices.size() != DEVICES || maxSlots <= 0)
                throw new IllegalArgumentException("Use 12 devices and a positive slot safety limit");
            this.devices = List.copyOf(devices); this.taskRandom = new Random(taskSeed);
            this.taskSeed=taskSeed; this.dataset=dataset;
            this.policy = Objects.requireNonNull(policy); this.maxSlots = maxSlots;
            for (int i = 0; i < DEVICES; i++) battery[i] = devices.get(i).capacityJ();
            var motion = new UAVMobilityModel(this, new Location3D(0, 0, ALTITUDE_M), SPEED_MPS, AREA_M, AREA_M);
            // Capacity fields satisfy the host node API; paper processing uses Tables 2-3, not these fields.
            uav = new UAVEdgeNode(this, motion, new UAVEnergyModel(UAV_BATTERY_J / 3600, FLIGHT_W, HOVER_W),
                    dataset==null?1:dataset.config().uavMips(), 1, 1);
        }
        public double[] observation() {
            double[] state = new double[2 * DEVICES];
            for (int i = 0; i < DEVICES; i++) { state[i] = battery[i] / devices.get(i).capacityJ(); state[DEVICES + i] = ages[i]; }
            return state;
        }
        public UAVEdgeNode getUav() { return uav; }
        public int slotsElapsed() { return slot; }
        public boolean terminated() { return terminated; }
        public boolean truncated() { return truncated; }
        public String reason() { return reason; }
        public double lastReward() { return reward; }
        public List<String> slotRows() { return List.copyOf(slots); }
        public List<String> deviceRows() { return List.copyOf(deviceRows); }
        public List<String> cpuRows() { return List.copyOf(cpuRows); }
        public List<String> workloadRows() { return List.copyOf(workloadRows); }
        public long imageSubmitted() { return imageSubmitted; }
        public long imageDelivered() { return imageDelivered; }
        public long cpuSubmitted() { return cpuSubmitted; }
        public long cpuCompleted() { return cpuCompleted; }
        public double deliveredLatencyMean() { return imageDelivered==0?Double.NaN:deliveredLatency/imageDelivered; }
        @Override public void startInternal() { schedule(this, 0.0, START_SLOT); }
        @Override public void processEvent(Event e) {
            if (e.getTag() == START_SLOT) beginSlot();
            else if (e.getTag() == END_SLOT) endSlot();
            else throw new IllegalArgumentException("Unexpected paper event");
        }
        private void beginSlot() {
            action = policy.choose(observation());
            if (action < 0 || action >= DEVICES) throw new IllegalArgumentException("Action must be in [0,11]");
            start = getSimulation().clock();
            selectedAge = ages[action]; oldestAge = Arrays.stream(ages).max().orElse(0);
            DeviceSpec target = devices.get(action);
            var destination = new Location3D(target.x(), target.y(), ALTITUDE_M);
            uav.getMobilityModel().setDestination(destination);
            flight = uav.getMobilityModel().getRemainingDistance() / SPEED_MPS;
            duration = flight; capped = 0;
            workBytes = new double[DEVICES]; activeStart = new double[DEVICES];
            activeDuration = new double[DEVICES]; activePower = new double[DEVICES]; candidates = new boolean[DEVICES];
            imageTasks=new PaperDatasetWorkload.ImageTask[DEVICES]; localRequired=new double[DEVICES];
            List<PaperDatasetWorkload.Job> cpuJobs=dataset==null?new ArrayList<>():new ArrayList<>(dataset.background(taskSeed,slot));
            for (int i = 0; i < DEVICES; i++) {
                DeviceSpec d = devices.get(i);
                workBytes[i] = MIN_TASK_BYTES + taskRandom.nextDouble() * (MAX_TASK_BYTES - MIN_TASK_BYTES);
                if(dataset!=null) { imageTasks[i]=dataset.image(taskSeed,slot,i); workBytes[i]=imageTasks[i].metadata().bytes(); }
                localRequired[i]=workBytes[i]/bytesPerSecond(d.hardware(),d.task());
                double distance = destination.distanceTo(new Location3D(d.x(), d.y(), 0));
                candidates[i] = distance <= RANGE_M;
                activeStart[i] = candidates[i] ? flight : 0;
                double requested = candidates[i] ? workBytes[i] * 8 / rateBps(distance)
                        : localRequired[i];
                if(dataset!=null && candidates[i])cpuJobs.add(new PaperDatasetWorkload.Job("RESCUENET",i,imageTasks[i].index(),flight+requested,imageTasks[i].computeMi()));
                activeDuration[i] = Math.min(requested, MAX_SLOT_S - activeStart[i]);
                if (activeDuration[i] < requested) capped++;
                activePower[i] = candidates[i] ? TRANSMIT_W : activeW(d.hardware(), d.task());
                duration = Math.max(duration, activeStart[i] + activeDuration[i]);
            }
            if(dataset!=null) {
                cpuPlan=new PaperDatasetWorkload.CpuPlan(cpuJobs,dataset.config().uavMips());
                duration=Math.min(MAX_SLOT_S,Math.max(duration,cpuPlan.finish()));
            }
            // Stop at the first physical battery failure, even within a slot.
            double uavJ = uav.getEnergyModel().getBatteryLevel() * 3600;
            double available = uavJ <= flight * FLIGHT_W ? uavJ / FLIGHT_W
                    : flight + (uavJ - flight * FLIGHT_W) / HOVER_W;
            duration = Math.min(duration, available);
            if(dataset!=null)duration=cpuPlan.poweredDuration(duration,flight,dataset.config().cpuPowerW(),uavJ);
            for (int i = 0; i < DEVICES; i++) if (!devices.get(i).powered())
                duration = Math.min(duration, timeToEmpty(i));
            schedule(this, duration, END_SLOT);
        }
        private double energyAt(int i, double elapsed) {
            return standbyW(devices.get(i).hardware()) * elapsed
                    + activePower[i] * Math.max(0, Math.min(activeDuration[i], elapsed - activeStart[i]));
        }
        private double timeToEmpty(int i) {
            double standby = standbyW(devices.get(i).hardware()), energy = battery[i];
            if (energy <= standby * activeStart[i]) return energy / standby;
            energy -= standby * activeStart[i];
            double busyPower = standby + activePower[i];
            if (energy <= busyPower * activeDuration[i]) return activeStart[i] + energy / busyPower;
            return activeStart[i] + activeDuration[i] + (energy - busyPower * activeDuration[i]) / standby;
        }
        private void endSlot() {
            if(dataset==null)uav.advanceTo(getSimulation().clock());
            else cpuPlan.advance(uav,start,duration,dataset.config().cpuPowerW());
            slot++;
            int completed = 0;
            List<String> failures = new ArrayList<>();
            for (int i = 0; i < DEVICES; i++) {
                DeviceSpec d = devices.get(i);
                double consumed = energyAt(i, duration);
                if (!d.powered()) battery[i] = Math.max(0, battery[i] - consumed);
                // An incomplete upload never refreshes data age, including at the 600s cap.
                double distance = uav.getMobilityModel().getDestination().distanceTo(new Location3D(d.x(), d.y(), 0));
                boolean served = candidates[i] && duration + 1e-9 >= flight + workBytes[i] * 8 / rateBps(distance);
                if(dataset!=null)served=served && duration+1e-9>=cpuPlan.deviceFinish(i);
                if (served) completed++;
                boolean delivered=dataset==null ? d.connected()||served
                        : served || (!candidates[i] && d.connected() && localRequired[i]<=duration+1e-9);
                ages[i] = delivered ? 0 : ages[i] + 1;
                if(dataset!=null) {
                    imageSubmitted++;
                    double latency=delivered?(served?cpuPlan.deviceFinish(i):localRequired[i]):Double.NaN;
                    if(delivered) {imageDelivered++; deliveredLatency+=latency;}
                    if(recordTrace) workloadRows.add(String.format(Locale.ROOT,"%d,%d,%d,%.0f,%.9f,%.9f,%s,%.9f",slot,i,imageTasks[i].index(),workBytes[i],imageTasks[i].computeMi(),localRequired[i],delivered,latency));
                }
                if (battery[i] <= 1e-6) failures.add("DEVICE_" + i + "_BATTERY");
                if (ages[i] >= DATA_AGE_LIMIT) failures.add("DEVICE_" + i + "_DATA_AGE");
                if(recordTrace) deviceRows.add(String.format(Locale.ROOT, "%d,%d,%s,%s,%.6f,%s,%s,%.9f,%.9f,%d",
                        slot, i, d.powered(), d.connected(), workBytes[i], candidates[i], served, battery[i], consumed, ages[i]));
            }
            if (uav.getEnergyModel().getBatteryLevel() * 3600 <= 1e-6) failures.add("UAV_BATTERY");
            terminated = !failures.isEmpty(); truncated = !terminated && slot >= maxSlots;
            reason = terminated ? String.join("|", failures) : truncated ? "SLOT_SAFETY_LIMIT" : "RUNNING";
            if(dataset!=null) for(var s:cpuPlan.jobs()) {
                cpuSubmitted++;
                boolean done=s.finish()<=duration+1e-9;
                if(done)cpuCompleted++;
                double executed=Math.min(s.job().mi(),Math.max(0,Math.min(duration,s.finish())-s.start())*dataset.config().uavMips());
                String status=done?"COMPLETED":terminated?"DROPPED_EPISODE_END":"DROPPED_SLOT_CAP";
                if(recordTrace) cpuRows.add(String.format(Locale.ROOT,"%d,%s,%d,%d,%.9f,%.9f,%.9f,%.9f,%.9f,%s",slot,s.job().source(),s.job().device(),s.job().sourceIndex(),start+s.job().ready(),start+s.start(),start+s.finish(),s.job().mi(),executed,status));
            }
            reward = slot + Math.log(Math.max(1e-6, selectedAge) / Math.max(1e-6, oldestAge));
            double[] state = observation();
            var p = uav.getMobilityModel().getCurrentLocation();
            if(recordTrace) slots.add(String.format(Locale.ROOT, "%d,%d,%.9f,%.9f,%.9f,%.6f,%.6f,%.6f,%.9f,%.9f,%d,%d,%d,%.9f,%s,%s,%s",
                    slot, action, start, getSimulation().clock(), duration, p.getXPos(), p.getYPos(), p.getAltitude(),
                    uav.getEnergyModel().getBatteryLevel() * 3600, Arrays.stream(state, 0, DEVICES).min().orElse(0),
                    Arrays.stream(ages).max().orElse(0), completed, capped, reward, terminated, truncated, reason));
            if (terminated || truncated) getSimulation().setSimDone(true);
            else schedule(this, 0.0, START_SLOT);
        }
        public void save(Path dir) throws IOException {
            if (!recordTrace) throw new IllegalStateException("Enable trace at reset before saving an episode");
            Files.createDirectories(dir);
            Files.write(dir.resolve("slots.csv"), slots); Files.write(dir.resolve("devices.csv"), deviceRows);
            List<String> inventory = new ArrayList<>(List.of("device,x_m,y_m,hardware,vision_task,capacity_j,powered,connected"));
            for (int i = 0; i < DEVICES; i++) {
                DeviceSpec d = devices.get(i);
                inventory.add(String.format(Locale.ROOT, "%d,%.6f,%.6f,%s,%s,%.9f,%s,%s", i, d.x(), d.y(),
                        d.hardware(), d.task(), d.capacityJ(), d.powered(), d.connected()));
            }
            Files.write(dir.resolve("layout.csv"), inventory);
            if(dataset!=null) {
                dataset.save(dir);
                Files.write(dir.resolve("dataset-tasks.csv"),workloadRows);
                Files.write(dir.resolve("cpu-tasks.csv"),cpuRows);
                Files.writeString(dir.resolve("dataset-summary.csv"),"images_submitted,images_delivered,images_undelivered,cpu_submitted,cpu_completed,mean_delivered_latency_s,uav_compute_j\n"
                        +String.format(Locale.ROOT,"%d,%d,%d,%d,%d,%.9f,%.9f%n",imageSubmitted,imageDelivered,imageSubmitted-imageDelivered,cpuSubmitted,cpuCompleted,deliveredLatencyMean(),uav.getEnergyModel().getComputeWh()*3600));
            }
        }
    }
    public static void main(String[] args) throws IOException {
        long seed = Long.parseLong(System.getProperty("paper.seed", "42"));
        int powered = Integer.parseInt(System.getProperty("paper.powered", "8"));
        int connected = Integer.parseInt(System.getProperty("paper.connected", "8"));
        Baseline baseline = Baseline.valueOf(System.getProperty("paper.policy", "OLDEST_DATA"));
        int maxSlots = Integer.parseInt(System.getProperty("paper.maxSlots", "200"));
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS = false;
        String mode=System.getProperty("paper.workload","synthetic");
        if(!mode.equals("synthetic")&&!mode.equals("datasets"))throw new IllegalArgumentException("paper.workload must be synthetic or datasets");
        var dataset=mode.equals("datasets")?PaperDatasetWorkload.fromProperties():null;
        var engine = new PureEdgeSim();
        var manager = new Manager(engine, layout(seed, powered, connected), seed + 1, policy(baseline, seed + 2), maxSlots,dataset);
        engine.start();
        Files.createDirectories(Path.of("target"));
        Path dir = Files.createTempDirectory(Path.of("target"), "uav-paper-"); manager.save(dir);
        Files.writeString(dir.resolve("run.txt"), "Source: arXiv:2501.15305v1; environment baseline, not trained DQN.\n"
                +"workload="+mode+"\n"
                + "seed=" + seed + " taskSeed=" + (seed + 1) + " policySeed=" + (seed + 2)
                + " powered=" + powered + " connected=" + connected + " policy=" + baseline + " maxSlots=" + maxSlots
                + "\nConventions: PAPER_ALIGNMENT.md; decimal bytes; literal beta0 dBm; slant range; parallel dedicated links; "
                + "600s clipped work; no 1kB terrestrial output-link cost; epsilon=1e-6 reward.\n"
                + (dataset==null ? "Compute: negligible UAV computation; synthetic task volumes.\n"
                   : "Compute: finite FIFO UAV CPU shared by image and background tasks; completion-based data age; see dataset-config.txt.\n"));
        System.out.println("Paper environment baseline: slots=" + manager.slotsElapsed() + " reason=" + manager.reason()
                + "; output=" + dir.toAbsolutePath());
    }
}
