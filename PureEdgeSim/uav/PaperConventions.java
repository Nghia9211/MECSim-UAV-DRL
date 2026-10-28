package uav;

import java.util.*;

/** Explicit implementation choices, not additional published parameters. Default preserves historical runs. */
public record PaperConventions(Radio radio,Expiry expiry,Delivery delivery,RewardSnapshot rewardSnapshot,double rewardEpsilon) {
    public enum Radio { LITERAL_DBM, DB_GAIN }
    public enum Expiry { AT_LIMIT, ABOVE_LIMIT }
    public enum Delivery { LEGACY, COMPLETED, ARRIVED }
    public enum RewardSnapshot { BEFORE, AFTER }
    public PaperConventions {
        Objects.requireNonNull(radio);Objects.requireNonNull(expiry);Objects.requireNonNull(delivery);Objects.requireNonNull(rewardSnapshot);
        if(!Double.isFinite(rewardEpsilon)||rewardEpsilon<=0)throw new IllegalArgumentException("Reward epsilon must be finite and positive");
    }
    public static PaperConventions defaults() {
        return new PaperConventions(Radio.LITERAL_DBM,Expiry.AT_LIMIT,Delivery.LEGACY,RewardSnapshot.BEFORE,1e-6);
    }
    public static PaperConventions fromProperties() {
        return new PaperConventions(Radio.valueOf(System.getProperty("paper.radioConvention","LITERAL_DBM")),
                Expiry.valueOf(System.getProperty("paper.expiryConvention","AT_LIMIT")),
                Delivery.valueOf(System.getProperty("paper.deliveryConvention","LEGACY")),
                RewardSnapshot.valueOf(System.getProperty("paper.rewardSnapshot","BEFORE")),
                Double.parseDouble(System.getProperty("paper.rewardEpsilon","1e-6")));
    }
    public double rateBps(double slantMetres) {
        return radio==Radio.LITERAL_DBM?PaperParameters.rateBps(slantMetres):PaperParameters.rateBps(slantMetres,1e-5);
    }
    public boolean expired(int age) {
        return expiry==Expiry.AT_LIMIT?age>=PaperParameters.DATA_AGE_LIMIT:age>PaperParameters.DATA_AGE_LIMIT;
    }
    public Map<String,Object> manifest() {
        return Map.of("radio",radio.name(),"expiry",expiry.name(),"delivery",delivery.name(),"reward_snapshot",rewardSnapshot.name(),"reward_epsilon",rewardEpsilon,
                "backlog","discard at slot end; not varied","output_link","instantaneous; uncalibrated and not varied");
    }
}
