// Tactic & technique metadata mirrored from
// `services/correlator/app/attack.py`. Kept manually-synced (small set,
// changes rarely) so the Cockpit can render readable labels without an
// extra HTTP round trip.

export const TACTIC_NAMES: Record<string, string> = {
  TA0043: "Reconnaissance",
  TA0042: "Resource Development",
  TA0001: "Initial Access",
  TA0002: "Execution",
  TA0003: "Persistence",
  TA0004: "Privilege Escalation",
  TA0005: "Defense Evasion",
  TA0006: "Credential Access",
  TA0007: "Discovery",
  TA0008: "Lateral Movement",
  TA0009: "Collection",
  TA0011: "Command and Control",
  TA0010: "Exfiltration",
  TA0040: "Impact",
};

export const TECHNIQUE_NAMES: Record<string, string> = {
  T1595: "Active Scanning",
  T1592: "Gather Victim Host Information",
  T1190: "Exploit Public-Facing Application",
  T1133: "External Remote Services",
  T1059: "Command and Scripting Interpreter",
  T1071: "Application Layer Protocol",
  T1110: "Brute Force",
  "T1110.001": "Brute Force: Password Guessing",
  "T1110.003": "Brute Force: Password Spraying",
  T1078: "Valid Accounts",
  T1027: "Obfuscated Files or Information",
  T1046: "Network Service Discovery",
  T1486: "Data Encrypted for Impact",
  T1083: "File and Directory Discovery",
  T1505: "Server Software Component",
};

export const TACTIC_ORDER = [
  "TA0043",
  "TA0042",
  "TA0001",
  "TA0002",
  "TA0003",
  "TA0004",
  "TA0005",
  "TA0006",
  "TA0007",
  "TA0008",
  "TA0009",
  "TA0011",
  "TA0010",
  "TA0040",
];

export function tacticName(id: string): string {
  return TACTIC_NAMES[id] ?? id;
}

export function techniqueName(id: string): string {
  return TECHNIQUE_NAMES[id] ?? id;
}
