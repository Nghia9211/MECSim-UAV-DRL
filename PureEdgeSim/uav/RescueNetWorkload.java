package uav;

import javax.imageio.ImageIO;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.security.*;

/** Read-only image metadata adapter. Explicit image directory prevents masks becoming tasks. */
public final class RescueNetWorkload {
    public record Metadata(Path image,Path mask,long bytes,int width,int height,String sha256) { }

    /** Read a bounded image metadata pool for the dataset environment. */
    public static List<Metadata> readMetadata(Path images,Path masks,int limit) throws IOException {
        if(limit<1 || limit>100000) throw new IllegalArgumentException("Metadata limit must be 1..100000");
        if(!Files.isDirectory(images)) throw new IOException("Image directory not found: "+images);
        if(masks!=null && (!Files.isDirectory(masks) || Files.isSameFile(images,masks)))
            throw new IOException("Use a separate existing mask directory");
        List<Path> paths;
        // One explicitly selected images folder, not a recursive mixed dataset scan.
        try(var files=Files.list(images)) {
            paths=files.filter(Files::isRegularFile).filter(p->p.getFileName().toString().toLowerCase(Locale.ROOT).matches(".*\\.(jpg|jpeg|png)"))
                    .sorted(Comparator.comparing(p->p.getFileName().toString())).limit(limit).toList();
        }
        if(paths.isEmpty()) throw new IOException("No JPG/PNG images in selected folder (choose the images subfolder)");
        List<Metadata> result=new ArrayList<>();
        for(Path p:paths) {
            int[] size=dimensions(p);
            String name=p.getFileName().toString(); String stem=name.substring(0,name.lastIndexOf('.'));
            Path mask=null;
            if(masks!=null) {
                List<Path> matches=new ArrayList<>();
                for(String candidate:List.of(stem+".png",stem+"_lab.png",stem+"_mask.png")) {
                    Path m=masks.resolve(candidate); if(Files.isRegularFile(m)) matches.add(m);
                }
                if(matches.size()!=1) throw new IOException("Expected one matching mask for "+name+", found "+matches.size());
                mask=matches.get(0);
                if(!Arrays.equals(size,dimensions(mask))) throw new IOException("Mask dimensions differ: "+mask);
            }
            result.add(new Metadata(p.toAbsolutePath(),mask==null?null:mask.toAbsolutePath(),Files.size(p),size[0],size[1],sha256(p)));
        }
        return List.copyOf(result);
    }
    private static int[] dimensions(Path path) throws IOException {
        try(var input=ImageIO.createImageInputStream(path.toFile())) {
            if(input==null) throw new IOException("Cannot read image: "+path);
            var readers=ImageIO.getImageReaders(input);
            if(!readers.hasNext()) throw new IOException("Unsupported/corrupt image: "+path);
            var reader=readers.next();
            try { reader.setInput(input); return new int[]{reader.getWidth(0),reader.getHeight(0)}; }
            finally { reader.dispose(); }
        }
    }
    private static String sha256(Path p) throws IOException {
        try {
            var digest=MessageDigest.getInstance("SHA-256");
            try(var in=Files.newInputStream(p)) { byte[] buffer=new byte[65536]; int n;
                while((n=in.read(buffer))!=-1) digest.update(buffer,0,n); }
            return HexFormat.of().formatHex(digest.digest());
        } catch(NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
}
