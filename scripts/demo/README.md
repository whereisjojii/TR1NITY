# Demo scripts

## `synth_attack.py`

Fires a 3-event attack chain at the ingestor — same source IP, three sources
(firewall → WAF → Wazuh) — exactly the shape Phase 2's correlator should later
collapse into a single incident.

```bash
# 1. Start the stack (Phase-0 services in dry-run mode)
make up

# 2. Fire the synthetic attack
python scripts/demo/synth_attack.py
```

Expected output:

```
[demo] firing synthetic attack chain at http://localhost:8001
[demo] attacker=203.0.113.45 victim=10.0.0.10

  [OK ] step 1: firewall  (T1595 - Active Scanning)             (202)
  [OK ] step 2: WAF       (T1190 - Exploit Public-Facing App)   (202)
  [OK ] step 3: Wazuh     (T1110 - Brute Force)                 (202)

[demo] all 3 events accepted by ingestor.
```

If `ENABLE_AUTH=true` is set on the ingestor, pass the bearer token:

```bash
python scripts/demo/synth_attack.py --token "$INGESTOR_AUTH_TOKEN"
```
