package uav;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Dataset-driven extension: measured payloads, explicitly assumed compute, slot-local FIFO CPU. */
public final class PaperDatasetWorkload {
    public record Config(double uavMips, double imageMiPerMegapixel, double cpuPowerW,
                         double referenceMips, double durationScale, double backgroundScale,
                         int backgroundTasksPerSlot) {
        public Config {
            for(double v:new double[]{uavMips,imageMiPerMegapixel,referenceMips,durationScale})
                UAVMobilityModel.requirePositive(v,"compute assumption");
            if(!Double.isFinite(cpuPowerW)||cpuPowerW<0||!Double.isFinite(backgroundScale)||backgroundScale<0
                    ||backgroundTasksPerSlot<0||backgroundTasksPerSlot>1000)
                throw new IllegalArgumentException("Invalid power/background configuration");
        }
    }
    public record ImageTask(int index, RescueNetWorkload.Metadata metadata, double computeMi) { }
    public record Job(String source, int device, long sourceIndex, double ready, double mi) {
        public Job {
            if(!Double.isFinite(ready)||ready<0||!Double.isFinite(mi)||mi<0)
                throw new IllegalArgumentException("Invalid CPU job");
        }
    }
    public record Scheduled(Job job, double start, double finish) { }
    public static final class CpuPlan {
        private final List<Scheduled> jobs;
        public CpuPlan(List<Job> requests,double mips) {
            UAVMobilityModel.requirePositive(mips,"UAV MIPS");
            var sorted=new ArrayList<>(requests);
            // Stable ties: Alibaba is inserted first, then device index.
            sorted.sort(Comparator.comparingDouble(Job::ready));
            var result=new ArrayList<Scheduled>(); double free=0;
            for(var j:sorted) {
                double begin=Math.max(free,j.ready()), finish=begin+j.mi()/mips;
                if(!Double.isFinite(finish)) throw new IllegalArgumentException("CPU schedule overflow");
                result.add(new Scheduled(j,begin,finish)); free=finish;
            }
            jobs=List.copyOf(result);
        }
        public List<Scheduled> jobs() { return jobs; }
        public double finish() { return jobs.isEmpty()?0:jobs.get(jobs.size()-1).finish(); }
        public double deviceFinish(int device) { return jobs.stream().filter(s->s.job().device()==device)
                .mapToDouble(Scheduled::finish).findFirst().orElse(Double.POSITIVE_INFINITY); }
        public double busySeconds(double time) { return jobs.stream().mapToDouble(s->Math.max(0,Math.min(time,s.finish())-s.start())).sum(); }
        public double energyJ(double time,double flight,double cpuW) {
            return Math.min(time,flight)*PaperParameters.FLIGHT_W+Math.max(0,time-flight)*PaperParameters.HOVER_W
                    +busySeconds(time)*cpuW;
        }
        public double poweredDuration(double requested,double flight,double cpuW,double batteryJ) {
            if(energyJ(requested,flight,cpuW)<=batteryJ) return requested;
            double lo=0,hi=requested;
            for(int i=0;i<80;i++) { double mid=(lo+hi)/2; if(energyJ(mid,flight,cpuW)<batteryJ)lo=mid;else hi=mid; }
            return hi;
        }
        public void advance(UAVEdgeNode uav,double absoluteStart,double elapsed,double cpuW) {
            var busy=new UAVEnergyModel.Load(cpuW,0,0);
            for(var s:jobs) {
                if(s.start()>=elapsed)break;
                uav.setLoadAt(absoluteStart+s.start(),busy);
                uav.setLoadAt(absoluteStart+Math.min(s.finish(),elapsed),UAVEnergyModel.Load.IDLE);
                if(s.finish()>=elapsed)break;
            }
            uav.advanceTo(absoluteStart+elapsed);
        }
    }

    private final List<RescueNetWorkload.Metadata> images;
    private final AlibabaWorkload.Sample alibaba;
    private final Config config;
    private final Path source;
    public PaperDatasetWorkload(List<RescueNetWorkload.Metadata> images,AlibabaWorkload.Sample alibaba,Config config,Path source) {
        this.images=List.copyOf(images); this.alibaba=Objects.requireNonNull(alibaba);
        this.config=Objects.requireNonNull(config); this.source=Objects.requireNonNull(source);
        if(images.isEmpty()||alibaba.rows().isEmpty())throw new IllegalArgumentException("Both dataset pools required");
    }
    public Config config() { return config; }
    public int imageCount() { return images.size(); }
    public int backgroundCount() { return alibaba.rows().size(); }
    public PaperDatasetWorkload withBackgroundScale(double scale) {
        return new PaperDatasetWorkload(images,alibaba,new Config(config.uavMips(),config.imageMiPerMegapixel(),
                config.cpuPowerW(),config.referenceMips(),config.durationScale(),scale,config.backgroundTasksPerSlot()),source);
    }
    /** Deterministic per-slot/device selection, independent of action and background setting. */
    public ImageTask image(long seed,int slot,int device) {
        int index=new Random(seed+0x9E3779B97F4A7C15L*(slot*(long)PaperParameters.DEVICES+device+1)).nextInt(images.size());
        var m=images.get(index);
        double mi=m.width()*(double)m.height()/1_000_000*config.imageMiPerMegapixel();
        if(!Double.isFinite(mi)||mi<=0)throw new IllegalArgumentException("Image compute overflow");
        return new ImageTask(index,m,mi);
    }
    public List<Job> background(long seed,int slot) {
        var jobs=new ArrayList<Job>();
        if(config.backgroundScale()==0)return jobs;
        Random random=new Random(seed+0x632BE59BD9B4E019L*(slot+1L));
        for(int i=0;i<config.backgroundTasksPerSlot();i++) {
            var r=alibaba.rows().get(random.nextInt(alibaba.rows().size()));
            double mi=(r.end()-r.start())*r.planCpu()/100*config.referenceMips()*config.durationScale()*config.backgroundScale();
            jobs.add(new Job("ALIBABA",-1,r.line(),0,mi));
        }
        return jobs;
    }
    private static String required(String key) {
        String value=System.getProperty(key);
        if(value==null||value.isBlank())throw new IllegalArgumentException("Missing -D"+key+"; see DATASET_SETUP.md");
        return value;
    }
    public static PaperDatasetWorkload fromProperties() throws IOException {
        Path images=Path.of(required("rescuenet.images")), source=Path.of(required("alibaba.csv"));
        String masks=System.getProperty("rescuenet.masks");
        var pool=RescueNetWorkload.readMetadata(images,masks==null?null:Path.of(masks),Integer.parseInt(System.getProperty("paper.imageLimit","449")));
        var sample=AlibabaWorkload.readPool(source,Integer.parseInt(System.getProperty("paper.alibabaLimit","1000")),
                Long.parseLong(System.getProperty("paper.alibabaScanLimit","100000")));
        var config=new Config(Double.parseDouble(required("paper.uavMips")),Double.parseDouble(required("paper.imageMiPerMegapixel")),
                Double.parseDouble(required("paper.cpuPowerW")),Double.parseDouble(required("alibaba.assumedMips")),
                Double.parseDouble(required("alibaba.durationScale")),Double.parseDouble(required("paper.backgroundScale")),
                Integer.parseInt(required("paper.backgroundTasksPerSlot")));
        return new PaperDatasetWorkload(pool,sample,config,source);
    }
    static String quote(Object s) { return "\""+s.toString().replace("\"","\"\"")+"\""; }
    public void save(Path dir) throws IOException {
        Files.createDirectories(dir);
        var rows=new ArrayList<String>(List.of("index,image,mask,bytes,width,height,sha256"));
        for(int i=0;i<images.size();i++) {var m=images.get(i); rows.add(i+","+quote(m.image())+","+quote(m.mask()==null?"":m.mask())+","+m.bytes()+","+m.width()+","+m.height()+","+m.sha256());}
        Files.write(dir.resolve("rescuenet-pool.csv"),rows);
        rows=new ArrayList<>(List.of("source_line,job,task,start_s,end_s,plan_cpu,plan_mem"));
        for(var r:alibaba.rows())rows.add(r.line()+","+quote(r.job())+","+quote(r.task())+","+r.start()+","+r.end()+","+r.planCpu()+","+r.planMem());
        Files.write(dir.resolve("alibaba-pool.csv"),rows);
        Files.writeString(dir.resolve("dataset-config.txt"),"config="+config+"\nsource="+source.toAbsolutePath()
                +"\nimages="+images.size()+" alibabaRows="+alibaba.rows().size()+" scanned="+alibaba.scanned()+" malformed="+alibaba.malformed()+" excluded="+alibaba.excluded()
                +"\nImage payload=compressed file bytes; UAV MI=megapixels*assumed MI/MP. Local time=file bytes / paper Table 3 rate (uncalibrated)."
                +"\nAlibaba MI=source duration*(requested CPU/100)*referenceMips*durationScale*backgroundScale; NOT observed utilization."
                +"\nFirst eligible source pool, deterministic sampling WITH replacement each slot; source timestamps NOT replayed."
                +"\nOne FIFO CPU, background ready at slot start; image ready after upload. Slot cap 600s; unfinished jobs dropped, no carry-over."
                +"\nImage delivery/age refresh requires computation completion. CPU W assumed, additive to propulsion; no inference, extra radio or output-link energy."
                +"\nState/action remain 24/12; CPU queue/background are not observed by the policy. Extension, not exact paper reproduction.\n");
    }
}
