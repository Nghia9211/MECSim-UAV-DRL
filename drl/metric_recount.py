"""Compare independent metric recounts: counts/identities exact, finite floats tightly bounded."""
import math

EXACT={"scenario","seed","policy","workload_sha256","image_offered","image_ontime","image_completed",
       "background_offered","background_ontime","uav_death_observed","delivered_ontime_images",
       "delivered_completed_images","covered_images","offloaded_images","contact_wait_enabled",
       "offload_eligible_images","reserved_images","reserved_uploaded_images","reserved_delivered_ontime_images"}

def validate_recount(original,recounted):
    if len(original)!=len(recounted):raise AssertionError("Exporter row count")
    rounding={}
    for a,b in zip(original,recounted):
        for key,value in b.items():
            if key not in a:raise AssertionError("Unexpected metric "+key)
            if key in EXACT:
                if a[key]!=value:raise AssertionError("Exporter identity/count mismatch: "+key)
                continue
            if a[key] in ("",None) or value in ("",None):
                if a[key]!=value:raise AssertionError("Exporter missing-value mismatch: "+key)
                continue
            try:x,y=float(a[key]),float(value)
            except (TypeError,ValueError) as exc:raise AssertionError("Invalid metric "+key) from exc
            if not math.isfinite(x) or not math.isfinite(y) or not math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-9):
                raise AssertionError(f"Exporter numeric mismatch: {key} {x} {y}")
            if a[key]==value:continue
            entry=rounding.setdefault(key,dict(rows=0,max_absolute_delta=0.))
            entry["rows"]+=1;entry["max_absolute_delta"]=max(entry["max_absolute_delta"],abs(x-y))
    return dict(status="PASS",rows=len(original),counts_and_identities="exact",
                float_relative_tolerance=1e-12,float_absolute_tolerance=1e-9,rounding=rounding)
