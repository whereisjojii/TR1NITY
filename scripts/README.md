# `scripts/` — Helper scripts

| Script                 | Purpose                                                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `download_datasets.sh` | (Phase 4) Pull CICIDS2017 + UNSW-NB15 from official mirrors. Datasets are NOT redistributed via this repo.                |
| `synthetic_attack.py`  | (Phase 1) Generate Wazuh + firewall + WAF events for the same source IP — exercises the ingestion + correlation pipeline. |
| `download_geolite2.sh` | (Phase 2) Pull MaxMind GeoLite2 with the user's free license key.                                                         |
| `download_sigma.sh`    | (Phase 2) `git submodule update` for the SigmaHQ rules.                                                                   |
