// Known circuits and corner names.
export default {
  circuitUnknown: 'Circuit not recognized',
  circuitUnknownHint: 'The circuit in the file header is not in the known-circuit database, so corners keep their number.',
  circuitMatchedHint: '{name} · {length} km · {named} named corners · confidence {confidence}',
  circuitMatchedNoCorners: '{name} · {length} km · recognized circuit, corner names not available yet · confidence {confidence}',
  circuitLowConfidence: 'low confidence',
  circuitLowConfidenceHint: 'The venue looks like {name}, but the measured lap is {measured} m against {nominal} m expected ({dev} %). It may be another layout or a partial lap, so corner names are hidden.',
  circuitConfidenceHigh: 'high',
  circuitConfidenceMedium: 'medium',
  sectorStartLine: 'Start',
  sectorFinishLine: 'Finish',
};
