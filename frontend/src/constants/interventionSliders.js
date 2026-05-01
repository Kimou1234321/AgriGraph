/** Slider definitions and presets for counterfactual interventions (shared by Atlas sidebar). */

export const INTERVENTION_SLIDERS = [
  { key: "num_herds", label: "Number of Herds" },
  { key: "calving_interval", label: "Calving Interval" },
  { key: "six_wk_calving_rate", label: "6-Week Calving Rate" },
  { key: "calves_per_cow_per_year", label: "Calves per Cow per Year" },
  { key: "females_not_calved_pct", label: "Females Not Calved" },
  { key: "avg_lactations", label: "Average Lactations" },
  { key: "current_replacement_rate", label: "Current Replacement Rate" },
  { key: "potential_replacement_rate", label: "Potential Replacement Rate" },
  { key: "cows_culled_pct", label: "Cows Culled" },
  { key: "heifers_calved_22_26mo", label: "Heifers Calved 22-26 Months" },
  { key: "mortality_dead_at_birth", label: "Mortality at Birth" },
  { key: "mortality_dead_28days", label: "Mortality at 28 Days" },
  { key: "replacements_dairy_ai_pct", label: "Replacements to Dairy AI" },
  { key: "births_known_sire_pct", label: "Births with Known Sire" },
  { key: "births_calving_survey_pct", label: "Births in Calving Survey" },
  { key: "recycled_cows_pct", label: "Recycled Cows" },
  { key: "autumn_6wk_calving_rate", label: "Autumn 6-Week Calving Rate" },
];

export const INTERVENTION_PRESETS = {
  "Optimize Reproduction": {
    calving_interval: -0.1,
    six_wk_calving_rate: 0.1,
    calves_per_cow_per_year: 0.08,
    females_not_calved_pct: -0.08,
    heifers_calved_22_26mo: 0.08,
    recycled_cows_pct: 0.1,
    autumn_6wk_calving_rate: 0.08,
  },
  "Reduce Losses": {
    cows_culled_pct: -0.1,
    mortality_dead_at_birth: -0.15,
    mortality_dead_28days: -0.12,
    females_not_calved_pct: -0.05,
    potential_replacement_rate: -0.05,
    avg_lactations: 0.05,
  },
  "Improve Genetics": {
    replacements_dairy_ai_pct: 0.15,
    births_known_sire_pct: 0.1,
    births_calving_survey_pct: 0.1,
    current_replacement_rate: 0.08,
    potential_replacement_rate: 0.06,
    num_herds: 0.05,
  },
};

export function emptyInterventions() {
  return Object.fromEntries(INTERVENTION_SLIDERS.map((slider) => [slider.key, 0]));
}
