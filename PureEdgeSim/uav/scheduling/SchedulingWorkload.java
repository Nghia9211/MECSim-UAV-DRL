package uav.scheduling;

import uav.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Two independent physical-time arrival streams, generated once before comparing policies.
 * Resamples source work sizes; does NOT replay Alibaba execution timestamps as arrival times.
 * RescueNet is a proxy image input at a fixed ground source; image labels never set priority.
 */
public final class SchedulingWorkload {
    private SchedulingWorkload() { }
    public record Config(double arrivalWindowSeconds,double imageRatePerSecond,double backgroundRatePerSecond,
            double criticalFraction,double criticalDeadlineSeconds,double imageDeadlineSeconds,double backgroundDeadlineSeconds,
            double imageMiPerMegapixel,double referenceMips,double backgroundWorkScale,double slantDistanceMetres) {
        public Config {
            for(double x:new double[]{arrivalWindowSeconds,criticalDeadlineSeconds,imageDeadlineSeconds,
                    backgroundDeadlineSeconds,imageMiPerMegapixel,referenceMips,backgroundWorkScale})
                if(!Double.isFinite(x)||x<=0)throw new IllegalArgumentException("Invalid workload cost/time");
            for(double x:new double[]{imageRatePerSecond,backgroundRatePerSecond})
                if(!Double.isFinite(x)||x<0||x*arrivalWindowSeconds>10000)
                    throw new IllegalArgumentException("Invalid arrival rate/size");
            if(!Double.isFinite(criticalFraction)||criticalFraction<0||criticalFraction>1
                    ||imageRatePerSecond+backgroundRatePerSecond<=0
                    ||slantDistanceMetres>PaperParameters.RANGE_M)
                throw new IllegalArgumentException("Invalid fraction/link");
            PaperParameters.rateBps(slantDistanceMetres);
        }
    }
    public record Pools(List<RescueNetWorkload.Metadata> images,AlibabaWorkload.Sample alibaba,Path alibabaFile) {
        public Pools {
            images=List.copyOf(images);Objects.requireNonNull(alibaba);Objects.requireNonNull(alibabaFile);
            if(images.isEmpty()||alibaba.rows().isEmpty())throw new IllegalArgumentException("Empty source pool");
        }
        public static Pools read(Path images,Path masks,Path alibaba,int imageLimit,int backgroundLimit,long scanLimit) throws IOException {
            return new Pools(RescueNetWorkload.readMetadata(images,masks,imageLimit),
                    AlibabaWorkload.readPool(alibaba,backgroundLimit,scanLimit),alibaba.toAbsolutePath());
        }
        public void save(Path output) throws IOException {
            Files.createDirectories(output);
            var rows=new ArrayList<String>(List.of("index,image,mask,bytes,width,height,sha256"));
            for(int i=0;i<images.size();i++) {
                var m=images.get(i);rows.add(i+","+quote(m.image())+","+quote(m.mask()==null?"":m.mask())+","+m.bytes()+","+m.width()+","+m.height()+","+m.sha256());
            }
            Files.write(output.resolve("rescuenet-pool.csv"),rows,StandardCharsets.UTF_8);
            rows=new ArrayList<>(List.of("source_line,job,task,start_s,end_s,plan_cpu,plan_mem"));
            for(var r:alibaba.rows())rows.add(r.line()+","+quote(r.job())+","+quote(r.task())+","+r.start()+","+r.end()+","+r.planCpu()+","+r.planMem());
            Files.write(output.resolve("alibaba-pool.csv"),rows,StandardCharsets.UTF_8);
        }
    }
    private static String quote(Object x) {return "\""+x.toString().replace("\"","\"\"")+"\"";}
    public static List<SchedulingTask> generate(Pools pools,Config config,long seed) {
        var result=new ArrayList<SchedulingTask>();
        var arrivals=new Random(seed^0x48A31F09L);var images=new Random(seed^0x61905BB3L);
        var priorities=new Random(seed^0x44BA813FL);
        double time=0;long index=0;
        if(config.imageRatePerSecond()>0)while((time+=gap(arrivals,config.imageRatePerSecond()))<config.arrivalWindowSeconds()) {
            if(result.size()>=20000)throw new IllegalArgumentException("Too many generated tasks");
            int selected=images.nextInt(pools.images().size());var image=pools.images().get(selected);
            boolean critical=priorities.nextDouble()<config.criticalFraction();
            double upload=image.bytes()*8.0/PaperParameters.rateBps(config.slantDistanceMetres());
            double mi=image.width()*(double)image.height()/1e6*config.imageMiPerMegapixel();
            result.add(new SchedulingTask(index++*2,SchedulingTask.Source.RESCUENET,selected,time,time+upload,
                    time+(critical?config.criticalDeadlineSeconds():config.imageDeadlineSeconds()),
                    critical?3:2,image.bytes(),mi));
        }
        arrivals=new Random(seed^0x3D10EF75L);var background=new Random(seed^0x1B71AC03L);time=0;index=0;
        if(config.backgroundRatePerSecond()>0)while((time+=gap(arrivals,config.backgroundRatePerSecond()))<config.arrivalWindowSeconds()) {
            if(result.size()>=20000)throw new IllegalArgumentException("Too many generated tasks");
            var row=pools.alibaba().rows().get(background.nextInt(pools.alibaba().rows().size()));
            double mi=(row.end()-row.start())*row.planCpu()/100*config.referenceMips()*config.backgroundWorkScale();
            result.add(new SchedulingTask(index++*2+1,SchedulingTask.Source.ALIBABA,row.line(),time,time,
                    time+config.backgroundDeadlineSeconds(),1,0,mi));
        }
        result.sort(Comparator.comparingDouble(SchedulingTask::arrivalSeconds).thenComparingLong(SchedulingTask::id));
        return List.copyOf(result);
    }
    private static double gap(Random rng,double rate) {return -Math.log1p(-rng.nextDouble())/rate;}
    public static String csv(List<SchedulingTask> tasks) {
        var out=new StringBuilder("id,source,source_index,arrival_s,ready_s,deadline_s,priority,input_bytes,compute_mi\n");
        for(var t:tasks)out.append(t.id()).append(',').append(t.source()).append(',').append(t.sourceIndex()).append(',')
                .append(t.arrivalSeconds()).append(',').append(t.readySeconds()).append(',').append(t.deadlineSeconds()).append(',')
                .append(t.priority()).append(',').append(t.inputBytes()).append(',').append(t.computeMi()).append('\n');
        return out.toString();
    }
    public static String hash(List<SchedulingTask> tasks) {
        try {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(csv(tasks).getBytes(StandardCharsets.UTF_8)));}
        catch(NoSuchAlgorithmException impossible) {throw new AssertionError(impossible);}
    }
}
