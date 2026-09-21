package uav;

import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Bounded streaming sample of single-instance DAG roots, not full DAG replay. */
public final class AlibabaWorkload {
    public record Row(long line,String task,String job,double start,double end,double planCpu,double planMem) { }
    public record Sample(List<Row> rows,long scanned,long malformed,long excluded) { }
    /** Bounded source pool for the paper dataset extension. */
    public static Sample readPool(Path csv,int limit,long scanLimit) throws IOException {
        if(limit<1 || limit>100000 || scanLimit<limit) throw new IllegalArgumentException("Invalid pool/scan limit");
        List<Row> rows=new ArrayList<>(); Set<String> keys=new HashSet<>();
        long scanned=0,malformed=0,excluded=0;
        try(var reader=Files.newBufferedReader(csv)) {
            String line;
            while(rows.size()<limit && scanned<scanLimit && (line=reader.readLine())!=null) {
                scanned++;
                String[] f=line.split(",",-1);
                try {
                    if(f.length!=9) throw new IllegalArgumentException();
                    long instances=Long.parseLong(f[1]);
                    double start=Double.parseDouble(f[5]),end=Double.parseDouble(f[6]),cpu=Double.parseDouble(f[7]),mem=Double.parseDouble(f[8]);
                    if(instances<1 || f[2].isBlank() || !Double.isFinite(start) || !Double.isFinite(end)
                            || !Double.isFinite(cpu) || !Double.isFinite(mem) || start<0 || end<start || cpu<=0 || mem<0 || mem>100)
                        throw new IllegalArgumentException();
                    // Only recognized roots: avoid dropping dependencies or inventing instance runtimes.
                    if(instances!=1 || !f[0].matches("[A-Za-z]+[0-9]+") || !f[4].equals("Terminated") || end==start) { excluded++; continue; }
                    if(!keys.add(f[2]+"/"+f[0])) { excluded++; continue; }
                    rows.add(new Row(scanned,f[0],f[2],start,end,cpu,mem));
                } catch(IllegalArgumentException e) { malformed++; }
            }
        }
        if(rows.isEmpty()) throw new IOException("No eligible positive-duration single-instance roots in sample");
        return new Sample(List.copyOf(rows),scanned,malformed,excluded);
    }
}
