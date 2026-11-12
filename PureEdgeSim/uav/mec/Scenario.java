package uav.mec;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;

/** One episode input: model + device layout (layout seed) + task list (task seed). Immutable. */
public record Scenario(MecModel model, long layoutSeed, long taskSeed, List<Device> devices, List<Task> tasks) {

    public record Device(int id, double x, double y, MecModel.DeviceType type, double batteryJ) { }

    /** cycles = actual Gcycles (kernel only); estCycles = what policies see. Deadline is absolute. */
    public record Task(long id, int classIndex, String cls, int device, double arrival, double inputBytes,
                       double cycles, double estCycles, double resultBytes, double deadline, int priority) {
        public Task {
            if (!(arrival >= 0 && inputBytes >= 0 && resultBytes >= 0 && cycles > 0 && estCycles > 0 && deadline > arrival))
                throw new IllegalArgumentException("invalid task " + id);
        }
    }

    public Scenario {
        devices = List.copyOf(devices); tasks = List.copyOf(tasks);
    }

    public static Scenario generate(MecModel m, long layoutSeed, long taskSeed) {
        return new Scenario(m, layoutSeed, taskSeed, layout(m, layoutSeed), tasks(m, taskSeed));
    }

    static List<Device> layout(MecModel m, long seed) {
        Random pos = Seeds.random(seed, "layout/position"), type = Seeds.random(seed, "layout/type"),
                battery = Seeds.random(seed, "layout/battery");
        double total = m.deviceTypes().stream().mapToDouble(MecModel.DeviceType::weight).sum();
        List<Device> out = new ArrayList<>();
        for (int i = 0; i < m.devices(); i++) {
            double x = m.areaM() * pos.nextDouble(), y = m.areaM() * pos.nextDouble();
            var t = pick(m.deviceTypes(), MecModel.DeviceType::weight, total, type.nextDouble());
            double b = t.batteryMinJ() + (t.batteryMaxJ() - t.batteryMinJ()) * battery.nextDouble();
            out.add(new Device(i, x, y, t, b));
        }
        return out;
    }

    static List<Task> tasks(MecModel m, long seed) {
        Random arrivals = Seeds.random(seed, "task/arrival"), device = Seeds.random(seed, "task/device"),
                cls = Seeds.random(seed, "task/class"), bytes = Seeds.random(seed, "task/input-bytes"),
                cycles = Seeds.random(seed, "task/cycles"), estimate = Seeds.random(seed, "task/estimate"),
                result = Seeds.random(seed, "task/result-bytes"), deadline = Seeds.random(seed, "task/deadline");
        double rate = m.totalArrivalRate(), total = m.classes().stream().mapToDouble(MecModel.TaskClass::weight).sum();
        List<Task> out = new ArrayList<>();
        double t = 0;
        while (true) {
            t += -Math.log1p(-arrivals.nextDouble()) / rate;
            if (t >= m.arrivalWindowS()) break;
            if (out.size() >= 2_000_000) throw new IllegalArgumentException("too many tasks");
            int d = device.nextInt(m.devices());
            int k = indexOf(m.classes(), MecModel.TaskClass::weight, total, cls.nextDouble());
            var c = m.classes().get(k);
            double actual = Math.max(1e-9, c.cycles().sample(cycles));
            double est = Math.max(1e-9, actual * (1 + m.estimateError() * (2 * estimate.nextDouble() - 1)));
            double due = t + Math.max(1e-6, c.deadlineS().sample(deadline));
            out.add(new Task(out.size(), k, c.name(), d, t, c.inputBytes().sample(bytes), actual, est,
                    c.resultBytes().sample(result), due, c.priority()));
        }
        out.sort(Comparator.comparingDouble(Task::arrival).thenComparingLong(Task::id));
        return out;
    }

    private static <T> T pick(List<T> items, java.util.function.ToDoubleFunction<T> weight, double total, double u) {
        return items.get(indexOf(items, weight, total, u));
    }

    private static <T> int indexOf(List<T> items, java.util.function.ToDoubleFunction<T> weight, double total, double u) {
        double acc = 0;
        for (int i = 0; i < items.size(); i++) {
            acc += weight.applyAsDouble(items.get(i)) / total;
            if (u < acc) return i;
        }
        return items.size() - 1;
    }

    /** SHA-256 of the task list and layout: equal hashes mean policies saw the same episode input. */
    public String hash() {
        var s = new StringBuilder();
        for (var d : devices) s.append(d.id()).append(',').append(d.x()).append(',').append(d.y()).append(',')
                .append(d.type().name()).append(',').append(d.batteryJ()).append('\n');
        for (var t : tasks) s.append(t.id()).append(',').append(t.cls()).append(',').append(t.device()).append(',')
                .append(t.arrival()).append(',').append(t.inputBytes()).append(',').append(t.cycles()).append(',')
                .append(t.estCycles()).append(',').append(t.resultBytes()).append(',').append(t.deadline()).append('\n');
        return Seeds.sha256Hex(s.toString());
    }
}
