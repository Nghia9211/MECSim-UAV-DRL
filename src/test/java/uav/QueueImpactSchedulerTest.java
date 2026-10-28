package uav;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import uav.scheduling.*;
import uav.offloading.*;

class QueueImpactSchedulerTest {
    private TaskScheduler.ReadyTask task(long id,double deadline,double mi,int priority) {
        return new TaskScheduler.ReadyTask(id,SchedulingTask.Source.RESCUENET,0,0,deadline,priority,mi);
    }
    private TaskScheduler.Context context(double battery) {return new TaskScheduler.Context(0,battery,1,2,1,20);}
    @Test void longUrgentTaskCanLoseToTwoShortTasksWithoutMutatingInput() {
        var q=new QueueImpactScheduler(1);
        var ready=List.of(task(0,5,5,3),task(1,4,2,2),task(2,4,2,2));
        assertEquals(1,q.choose(ready,context(1000)));
        assertEquals(3,q.project(ready,context(1000),0).value());
        assertEquals(4,q.project(ready,context(1000),1).value());
        assertEquals(3,ready.size());
        assertEquals(q.choose(ready,context(1000)),q.choose(List.of(ready.get(2),ready.get(0),ready.get(1)),context(1000)));
    }
    @Test void boundaryCompletionAndDepletionAreCounted() {
        var q=new QueueImpactScheduler(1);var ready=List.of(task(0,2,2,3));
        assertEquals(3,q.project(ready,context(6),0).value());
        assertEquals(0,q.project(ready,context(5),0).value());
        assertEquals(5,q.project(ready,context(5),0).energyJ(),1e-8);
    }
    @Test void projectionMatchesKernelWhenQueueKnownAndEstimateExact() {
        var q=new QueueImpactScheduler(1);var ready=List.of(task(0,5,5,3),task(1,4,2,2),task(2,4,2,2));
        var cfg=new OffloadingSimulation.Config(20,1,2,1,1000,List.of(new OffloadingSimulation.Device(1,0,0,0,1000)));
        for(var first:ready) {
            var jobs=ready.stream().map(t->new OffloadingJob(new SchedulingTask(t.id(),t.source(),t.id(),0,0,
                t.deadlineSeconds(),t.priority(),100,t.remainingMi()),0,t.remainingMi())).toList();

            TaskScheduler fixed=(tasks,c)->{if(c.nowSeconds()==0 && tasks.stream().anyMatch(t->t.id()==first.id()))return first.id();return TaskScheduler.baseline(TaskScheduler.Baseline.EDF).choose(tasks,c);};
            var actual=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),fixed);
            var predicted=q.project(ready,context(1000),first.id());
            double value=actual.tasks().stream().filter(o->o.status()==OffloadingSimulation.Status.COMPLETED_ON_TIME)
                .mapToDouble(o->o.job().task().priority()).sum();
            assertEquals(value,predicted.value());assertEquals(actual.uavEnergyJ(),predicted.energyJ(),1e-7);
        }
    }
}
