package uav;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.nio.file.*;
import java.io.IOException;
import static org.junit.jupiter.api.Assertions.*;
class RescueNetWorkloadTest {
    @TempDir Path root;
    private void png(Path file,int width) throws IOException {
        ImageIO.write(new BufferedImage(width,3,BufferedImage.TYPE_INT_RGB),"png",file.toFile());
    }
    @Test void importsPairedMetadata() throws Exception {
        Path images=Files.createDirectory(root.resolve("images")),masks=Files.createDirectory(root.resolve("masks"));
        png(images.resolve("b.png"),4); png(images.resolve("a.png"),4);
        png(masks.resolve("a_lab.png"),4); png(masks.resolve("b_lab.png"),4);
        var items=RescueNetWorkload.readMetadata(images,masks,2);
        assertEquals(2,items.size()); assertEquals("a.png",items.get(0).image().getFileName().toString());
        assertEquals(4,items.get(0).width()); assertEquals(3,items.get(0).height());
        assertEquals(64,items.get(0).sha256().length());
        assertEquals(Files.size(images.resolve("a.png")),items.get(0).bytes());
    }
    @Test void rejectsMissingAmbiguousAndMismatchedMasks() throws Exception {
        Path images=Files.createDirectory(root.resolve("images")),masks=Files.createDirectory(root.resolve("masks"));
        png(images.resolve("a.png"),4);
        assertThrows(IOException.class,()->RescueNetWorkload.readMetadata(images,masks,2));
        png(masks.resolve("a_lab.png"),5);
        assertThrows(IOException.class,()->RescueNetWorkload.readMetadata(images,masks,2));
        png(masks.resolve("a_lab.png"),4); png(masks.resolve("a_mask.png"),4);
        assertThrows(IOException.class,()->RescueNetWorkload.readMetadata(images,masks,2));
    }
    @Test void absentAndCorruptDataDoNotBecomeSyntheticWork() throws Exception {
        assertThrows(IOException.class,()->RescueNetWorkload.readMetadata(root.resolve("absent"),null,2));
        assertThrows(IOException.class,()->RescueNetWorkload.readMetadata(root,null,2));
        Files.writeString(root.resolve("bad.jpg"),"not an image");
        assertThrows(IOException.class,()->RescueNetWorkload.readMetadata(root,null,2));
        assertThrows(IllegalArgumentException.class,()->RescueNetWorkload.readMetadata(root,null,0));
    }
}
