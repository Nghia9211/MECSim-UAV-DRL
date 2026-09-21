package uav;

import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PaperInteractiveTest {
    @Test void abortedEpisodeReleasesGlobalEntities() {
        var engine=new PureEdgeSim();
        new PaperSimulation.Manager(engine,PaperSimulation.layout(42,8,8),43,
                s -> { throw new IllegalStateException("reset"); },200);
        assertThrows(IllegalStateException.class,engine::start);
        var next=new PureEdgeSim();
        var manager=new PaperSimulation.Manager(next,PaperSimulation.layout(42,8,8),43,s -> 0,1);
        assertDoesNotThrow(next::start);
        assertEquals(1,manager.slotsElapsed());
        assertTrue(manager.truncated());
    }

    @Test void disablingTracePreservesTransitionsAndRefusesIncompleteCsv() {
        var first=new PureEdgeSim();
        var traced=new PaperSimulation.Manager(first,PaperSimulation.layout(42,8,8),43,
                PaperSimulation.policy(PaperSimulation.Baseline.OLDEST_DATA,44),200);
        first.start();
        var second=new PureEdgeSim();
        var silent=new PaperSimulation.Manager(second,PaperSimulation.layout(42,8,8),43,
                PaperSimulation.policy(PaperSimulation.Baseline.OLDEST_DATA,44),200);
        silent.setRecordTrace(false);
        second.start();
        assertArrayEquals(traced.observation(),silent.observation());
        assertEquals(first.clock(),second.clock());
        assertEquals(traced.lastReward(),silent.lastReward());
        assertEquals(traced.reason(),silent.reason());
        assertEquals(1,silent.slotRows().size());
        assertThrows(IllegalStateException.class,()->silent.save(java.nio.file.Path.of("target/unused")));
    }
}
