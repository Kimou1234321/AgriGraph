/** Build a stable fingerprint for scenarios + result to detect duplicate saves. */
export function buildSimulationSnapshot(scenarios, result) {
  return JSON.stringify({ scenarios, result });
}
