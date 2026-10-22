package uav.offloading;

import java.util.*;
import uav.scheduling.SchedulingTask;

/** Actual MI stays in the kernel. Policies receive estimated MI, never this record. */
public record OffloadingJob(SchedulingTask task, int device, double estimatedMi) {
    public OffloadingJob {
        Objects.requireNonNull(task);
        if (!Double.isFinite(estimatedMi) || estimatedMi <= 0)
            throw new IllegalArgumentException("Estimated MI must be positive and finite");
        if (task.source() == SchedulingTask.Source.ALIBABA) {
            if (device != -1 || task.readySeconds() != task.arrivalSeconds() || task.inputBytes() != 0)
                throw new IllegalArgumentException("Background tasks originate at UAV, without upload");
        } else if (device < 0) throw new IllegalArgumentException("Image needs a ground device");
    }

    /** Independent streams: assignment/noise cannot change original arrivals, priorities or actual work. */
    public static List<OffloadingJob> assign(List<SchedulingTask> tasks, int devices, long seed, double estimateError) {
        if (devices <= 0 || !Double.isFinite(estimateError) || estimateError < 0 || estimateError >= 1)
            throw new IllegalArgumentException("Invalid device count or relative estimation error");
        var assignment = new Random(seed ^ 0x758FD20AL);
        var estimates = new Random(seed ^ 0x6BBD910CL);
        var result = new ArrayList<OffloadingJob>();
        for (var task : tasks.stream().sorted(Comparator.comparingLong(SchedulingTask::id)).toList()) {
            int device = task.source() == SchedulingTask.Source.RESCUENET ? assignment.nextInt(devices) : -1;
            double mi = task.computeMi() * (1 + estimateError * (2 * estimates.nextDouble() - 1));
            result.add(new OffloadingJob(task, device, mi));
        }
        return List.copyOf(result);
    }
}
