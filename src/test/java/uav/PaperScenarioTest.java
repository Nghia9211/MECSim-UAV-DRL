package uav;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperScenario.Mode.*;

class PaperScenarioTest {
    @Test void legacyPreservesEveryFieldAndIgnoresShiftSeed() {
        for(long seed:new long[]{0,42,2000000}) for(int powered:new int[]{0,8,12}) {
            var old=PaperSimulation.layout(seed,powered,6);
            assertEquals(old,PaperScenario.layout(seed,powered,6,legacy,891));
            assertEquals(PaperScenario.layoutHash(old),PaperScenario.layoutHash(
                    PaperScenario.layout(seed,powered,6,legacy,-1)));
        }
    }
    @Test void interventionsChangeOnlySelectedFactorsAndComposeIntoFull() {
        var base=PaperSimulation.layout(42,8,6);
        for(long seed=2100000;seed<2100020;seed++) {
            var all=PaperScenario.layout(42,8,6,full,seed);
            for(var mode:PaperScenario.Mode.values()) {
                var result=PaperScenario.layout(42,8,6,mode,seed);
                assertEquals(result,PaperScenario.layout(42,8,6,mode,seed));
                assertEquals(8,result.stream().filter(PaperSimulation.DeviceSpec::powered).count());
                assertEquals(6,result.stream().filter(PaperSimulation.DeviceSpec::connected).count());
                for(int i=0;i<12;i++) {
                    var d=result.get(i); var b=base.get(i); var a=all.get(i);
                    boolean pos=mode==position||mode==full, type=mode==hardware_task||mode==full;
                    boolean cap=mode==capacity||mode==full, pow=mode==power||mode==outage||mode==full;
                    boolean conn=mode==connectivity||mode==outage||mode==full;
                    assertEquals(pos?a.x():b.x(),d.x()); assertEquals(pos?a.y():b.y(),d.y());
                    assertEquals(type?a.hardware():b.hardware(),d.hardware());
                    assertEquals(type?a.task():b.task(),d.task());
                    assertEquals(cap?a.capacityJ():b.capacityJ(),d.capacityJ());
                    assertEquals(pow?a.powered():b.powered(),d.powered());
                    assertEquals(conn?a.connected():b.connected(),d.connected());
                }
            }
            assertNotEquals(base,all);
            assertNotEquals(PaperScenario.layoutHash(base),PaperScenario.layoutHash(all));
        }
    }
    @Test void hashesAndManifestsIdentifyPhysicalLayoutAndExactStreams() {
        var layout=PaperScenario.layout(42,8,8,position,9);
        var m=PaperScenario.manifest(42,8,8,position,9,layout);
        assertEquals(PaperScenario.layoutHash(layout),m.get("layout_sha256"));
        assertEquals(64,((String)m.get("layout_sha256")).length());
        assertEquals(m,PaperScenario.manifest(42,8,8,position,9,layout));
        assertThrows(IllegalArgumentException.class,()->PaperScenario.layout(42,13,8,full,1));
    }
}
