package uav;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.io.IOException;
import static org.junit.jupiter.api.Assertions.*;
class AlibabaWorkloadTest {
    @TempDir Path root;
    @Test void filtersDependenciesInstancesAndInvalidRecords() throws Exception {
        Path csv=root.resolve("batch.csv");
        Files.writeString(csv,"M1,1,j_1,1,Terminated,0,0,100,0.2\nR2_1,1,j_2,1,Terminated,1,3,100,0.2\nM1,2,j_3,1,Terminated,1,3,100,0.2\nbad\nM1,1,j_4,1,Terminated,10,20,50,0.2\nM1,1,j_4,1,Terminated,10,20,50,0.2\nM2,1,j_5,1,Terminated,1,2,100,0.3\n");
        var sample=AlibabaWorkload.readPool(csv,2,100);
        assertEquals(7,sample.scanned()); assertEquals(1,sample.malformed()); assertEquals(4,sample.excluded());
        assertEquals(10,sample.rows().get(0).start());
        assertEquals(50,sample.rows().get(0).planCpu());
    }
    @Test void emptyAndNonfiniteDataFailRatherThanFabricatingWork() throws Exception {
        Path csv=root.resolve("bad.csv"); Files.writeString(csv,"M1,1,j_1,1,Terminated,NaN,2,100,0.2\n");
        assertThrows(IOException.class,()->AlibabaWorkload.readPool(csv,1,10));
        assertThrows(IllegalArgumentException.class,()->AlibabaWorkload.readPool(csv,101,100));
    }
}
